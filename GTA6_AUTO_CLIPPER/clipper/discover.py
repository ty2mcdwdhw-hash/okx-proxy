"""Find candidate moments from the watchlist.

Twitch / Kick: viewer-made clips of the channel (sorted by views) — the audience already
picked the best moments. YouTube: newest uploads/VODs; long VODs are cut around
the "most replayed" heatmap peaks; shorts are taken whole.
"""
from __future__ import annotations

import datetime as dt
import json
import re

from .core import db, iso, now_utc, run, settings, watchlist, yt_dlp_base

TITLE_SPLIT = re.compile(r"[\s\W_]+", re.UNICODE)


def blocked_title(title: str, cfg: dict) -> str | None:
    t = (title or "").lower()
    words = set(TITLE_SPLIT.split(t))
    for term in cfg["spoiler"]["title_blocklist"]:
        term_l = term.lower()
        if term_l.isascii() and " " not in term_l:
            if term_l in words:
                return term
        elif term_l in t:  # non-latin scripts have no word boundaries
            return term
    return None


def _insert(con, row: dict) -> bool:
    if con.execute("SELECT 1 FROM clips WHERE id=?", (row["id"],)).fetchone():
        return False
    row = {**row, "discovered_at": iso(), "updated_at": iso()}
    cols = ",".join(row)
    con.execute(f"INSERT INTO clips ({cols}) VALUES ({','.join('?' * len(row))})", tuple(row.values()))
    con.commit()
    return True


def _ytdlp_json(args: list[str], timeout: int = 180) -> dict | None:
    p = run(yt_dlp_base() + ["-J"] + args, timeout=timeout, check=False)
    if p.returncode != 0 or not p.stdout.strip():
        return None
    return json.loads(p.stdout)


def clip_channel(creator: dict, cfg: dict, con) -> list[str]:
    """Twitch or Kick: list the channel's viewer clips, most viewed first."""
    d = cfg["discovery"]
    plat = creator["platform"]
    if plat == "twitch":
        url = f"https://www.twitch.tv/{creator['handle']}/clips?filter=clips&range={d['twitch_range']}"
        prefix = "TW"
    else:
        url = f"https://kick.com/{creator['handle']}/clips"
        prefix = "KK"
    games = d.get("game_filter") or []
    games = [g.lower() for g in ([games] if isinstance(games, str) else games)]
    j = _ytdlp_json(["--flat-playlist", "--playlist-end", "40", url])
    if not j:
        return []
    cutoff = (now_utc() - dt.timedelta(hours=d["lookback_hours"])).timestamp()
    if d.get("not_before"):
        nb = dt.datetime.strptime(d["not_before"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
        cutoff = max(cutoff, nb.timestamp())
    new = []
    entries = sorted(j.get("entries") or [], key=lambda e: e.get("view_count") or 0, reverse=True)
    taken = con.execute("SELECT COUNT(*) FROM clips WHERE creator_handle=? AND status!='rejected'",
                        (creator["handle"],)).fetchone()[0]
    for e in entries:
        if taken + len(new) >= d["per_creator_max"]:
            break
        if (e.get("timestamp") or 0) < cutoff and not creator.get("test"):
            continue
        if (e.get("view_count") or 0) < d["min_views"]:
            continue
        cats = [c.lower() for c in (e.get("categories") or [])]
        if games and cats and not creator.get("test") and not any(g in c for g in games for c in cats):
            continue  # Kick reports the category; Twitch listing does not
        cid = f"{prefix}_{e['id']}"
        row = dict(id=cid, source=f"{plat}_clip", url=e["url"], creator=creator["name"],
                   creator_handle=creator["handle"], platform=plat,
                   lang=(e.get("language") or creator["lang"]).lower()[:2], title=e.get("title"),
                   views=e.get("view_count"), duration=e.get("duration"),
                   created_at=iso(dt.datetime.fromtimestamp(e["timestamp"], dt.timezone.utc)) if e.get("timestamp") else None,
                   test=int(bool(creator.get("test"))))
        hit = blocked_title(row["title"], cfg)
        if hit:
            row.update(status="rejected", reason=f"title blocklist: {hit}")
        if _insert(con, row) and not hit:
            new.append(cid)
    return new


def _cutoff_ts(cfg: dict) -> float:
    d = cfg["discovery"]
    cutoff = (now_utc() - dt.timedelta(hours=d["lookback_hours"])).timestamp()
    if d.get("not_before"):
        nb = dt.datetime.strptime(d["not_before"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
        cutoff = max(cutoff, nb.timestamp())
    return cutoff


def twitch_helix(creator: dict, cfg: dict, con, broadcaster_id: str) -> list[str]:
    """Twitch via the official API: exact game per clip, so off-topic clips never get downloaded."""
    from . import twitch_api
    d = cfg["discovery"]
    since = iso(dt.datetime.fromtimestamp(_cutoff_ts(cfg), dt.timezone.utc))
    game = str(cfg["twitch_api"]["game_id"])
    taken = con.execute("SELECT COUNT(*) FROM clips WHERE creator_handle=? AND status!='rejected'",
                        (creator["handle"],)).fetchone()[0]
    new = []
    for c in sorted(twitch_api.clips(cfg, broadcaster_id, since, 50), key=lambda c: c["view_count"], reverse=True):
        if taken + len(new) >= d["per_creator_max"]:
            break
        if str(c.get("game_id")) != game or c["view_count"] < d["min_views"]:
            continue
        row = dict(id=f"TW_{c['id']}"[:80], source="twitch_clip", url=c["url"], creator=creator["name"],
                   creator_handle=creator["handle"], platform="twitch",
                   lang=(c.get("language") or creator["lang"])[:2].lower(), title=c.get("title"),
                   views=c["view_count"], duration=c.get("duration"), created_at=c.get("created_at"))
        hit = blocked_title(row["title"], cfg)
        if hit:
            row.update(status="rejected", reason=f"title blocklist: {hit}")
        if _insert(con, row) and not hit:
            new.append(row["id"])
    return new


def _heat_peaks(heatmap: list[dict], k: int, min_sep: float) -> list[float]:
    pts = sorted(heatmap or [], key=lambda h: h.get("value", 0), reverse=True)
    peaks: list[float] = []
    for h in pts:
        c = (h["start_time"] + h["end_time"]) / 2
        if all(abs(c - p) >= min_sep for p in peaks):
            peaks.append(c)
        if len(peaks) >= k:
            break
    return peaks


def youtube(creator: dict, cfg: dict, con) -> list[str]:
    d = cfg["discovery"]
    handle = creator["handle"] if creator["handle"].startswith("@") else "@" + creator["handle"]
    cutoff = now_utc() - dt.timedelta(hours=d["lookback_hours"])
    new: list[str] = []
    taken = con.execute("SELECT COUNT(*) FROM clips WHERE creator_handle=? AND status!='rejected'",
                        (creator["handle"],)).fetchone()[0]
    for tab in d["youtube_tabs"]:
        lst = _ytdlp_json(["--flat-playlist", "--playlist-end", str(d["youtube_max_items"]),
                           f"https://www.youtube.com/{handle}/{tab}"])
        for e in (lst or {}).get("entries") or []:
            if taken + len(new) >= d["per_creator_max"]:
                return new
            vid = e.get("id")
            if not vid or con.execute("SELECT 1 FROM clips WHERE id LIKE ?", (f"YT_{vid}%",)).fetchone():
                continue
            info = _ytdlp_json([f"https://www.youtube.com/watch?v={vid}"], timeout=120)
            if not info or info.get("is_live") or info.get("live_status") in ("is_upcoming", "is_live"):
                continue  # VOD not ready yet; picked up on a later cycle
            ts = info.get("timestamp") or 0
            if ts and dt.datetime.fromtimestamp(ts, dt.timezone.utc) < cutoff and not creator.get("test"):
                continue
            base = dict(source=f"youtube_{tab}", url=info["webpage_url"], creator=creator["name"],
                        creator_handle=creator["handle"], platform="youtube",
                        lang=(info.get("language") or creator["lang"])[:2].lower(), title=info.get("title"),
                        views=info.get("view_count"),
                        created_at=iso(dt.datetime.fromtimestamp(ts, dt.timezone.utc)) if ts else None,
                        test=int(bool(creator.get("test"))))
            hit = blocked_title(base["title"], cfg)
            dur = info.get("duration") or 0
            if dur <= 75:  # short / clip: take whole
                row = dict(base, id=f"YT_{vid}", duration=dur)
                if hit:
                    row.update(status="rejected", reason=f"title blocklist: {hit}")
                if _insert(con, row) and not hit:
                    new.append(row["id"])
                continue
            if hit:
                _insert(con, dict(base, id=f"YT_{vid}_0", duration=dur, status="rejected",
                                  reason=f"title blocklist: {hit}"))
                continue
            pre, post = d["youtube_segment"]
            for c in _heat_peaks(info.get("heatmap"), d["youtube_peaks_per_vod"], 60):
                if taken + len(new) >= d["per_creator_max"]:
                    break
                s, en = max(0.0, c + pre), min(dur, c + post)
                row = dict(base, id=f"YT_{vid}_{int(s)}", duration=en - s, section_start=s, section_end=en)
                if _insert(con, row):
                    new.append(row["id"])
    return new


def add_url(url: str, creator: str, lang: str, test: bool = False, peaks: int = 2) -> list[str]:
    """Manually add one URL (Twitch/Kick clip or VOD, YouTube video/short, TikTok, X...).
    Long videos are cut around their most-replayed peaks (or the middle if there is no heatmap)."""
    cfg = settings()
    con = db()
    info = _ytdlp_json([url], timeout=180)
    if not info:
        return []
    key = info.get("extractor_key", "x")[:6].upper()
    base = dict(source="manual", url=info.get("webpage_url") or url, creator=creator,
                creator_handle=creator, platform=info.get("extractor_key", "").lower().replace("clips", "").replace("clip", ""),
                lang=lang, title=info.get("title"), views=info.get("view_count"), test=int(test),
                created_at=iso(dt.datetime.fromtimestamp(info["timestamp"], dt.timezone.utc)) if info.get("timestamp") else None)
    dur = info.get("duration") or 0
    if dur <= 75:
        cid = f"MAN_{key}_{info['id']}"[:80]
        return [cid] if _insert(con, dict(base, id=cid, duration=dur)) else []
    pre, post = cfg["discovery"]["youtube_segment"]
    centers = _heat_peaks(info.get("heatmap"), peaks, 60) or [dur / 2]
    out = []
    for c in centers:
        s, e = max(0.0, c + pre), min(dur, c + post)
        cid = f"MAN_{key}_{info['id']}_{int(s)}"[:80]
        if _insert(con, dict(base, id=cid, duration=e - s, section_start=s, section_end=e)):
            out.append(cid)
    return out


def discover(only_group: str | None = None, only_handle: str | None = None) -> list[str]:
    cfg = settings()
    con = db()
    found = []
    creators = watchlist()
    helix = False
    ids: dict[str, str] = {}
    try:
        from . import twitch_api
        helix = twitch_api.enabled(cfg)
        if helix:
            known = {c["handle"].lower() for c in creators if c["platform"] == "twitch"}
            if not (only_group or only_handle):
                live = twitch_api.live_channels(cfg)
                top = ", ".join(f"{x['login']}:{x['lang']}:{x['viewers']}" for x in live[:12])
                print(f"[discover] Twitch en vivo con GTA VI: {len(live)} canales seleccionados ({top})")
                for s_ in live:
                    if s_["login"].lower() not in known:
                        creators.append({"name": s_["name"], "platform": "twitch", "handle": s_["login"],
                                         "lang": s_["lang"], "group": "live_ranking"})
                        ids[s_["login"]] = s_["id"]
            missing = [c["handle"] for c in creators if c["platform"] == "twitch" and c["handle"] not in ids]
            ids.update(twitch_api.user_ids(cfg, missing))
    except Exception as ex:
        print(f"[discover] Twitch API no disponible ({str(ex)[:150]}); uso yt-dlp")
        helix = False
    for c in creators:
        if only_group and c["group"] != only_group:
            continue
        if only_handle and c["handle"].lstrip("@").lower() != only_handle.lstrip("@").lower():
            continue
        if c["platform"] == "youtube" and not cfg["discovery"].get("youtube_enabled", True):
            continue
        try:
            if c["platform"] == "twitch" and helix and not c.get("test"):
                if c["handle"] not in ids:
                    continue
                got = twitch_helix(c, cfg, con, ids[c["handle"]])
            else:
                fn = youtube if c["platform"] == "youtube" else clip_channel
                got = fn(c, cfg, con)
            print(f"[discover] {c['name']:<32} +{len(got)}")
            found += got
        except Exception as ex:  # keep going on one bad channel
            print(f"[discover] {c['name']}: ERROR {str(ex)[:200]}")
    return found


def verify() -> None:
    """Check every watchlist channel resolves."""
    for c in watchlist(include_disabled=True):
        if c["platform"] == "twitch":
            url = f"https://www.twitch.tv/{c['handle']}/clips?filter=clips&range=all"
        elif c["platform"] == "kick":
            url = f"https://kick.com/{c['handle']}/clips"
        else:
            h = c["handle"] if c["handle"].startswith("@") else "@" + c["handle"]
            url = f"https://www.youtube.com/{h}/videos"
        j = _ytdlp_json(["--flat-playlist", "--playlist-end", "1", url], timeout=90)
        ok = bool(j and (j.get("entries") is not None))
        title = (j or {}).get("channel") or (j or {}).get("uploader") or (j or {}).get("title") or ""
        print(f"{'OK ' if ok else 'XX '} {c['platform']:<8} {c['handle']:<22} {c['name']:<32} {title[:40]}")
