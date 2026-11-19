"""Apply review decisions, publish rendered clips, keep log.md + scoreboard.csv."""
from __future__ import annotations

import csv
import datetime as dt
import json
import os
from pathlib import Path

import requests

from .core import DECISIONS_DIR, EDITS_DIR, LANG_NAMES, ROOT, db, iso, now_utc, set_status, settings

LOG = ROOT / "log.md"
SCORE = ROOT / "scoreboard.csv"
SCORE_COLS = ["post_id", "clip_id", "lang", "platform", "profile", "pillar", "source_creator",
              "source_lang", "duration_s", "status", "scheduled_for", "published_at",
              "views_12h", "views_24h", "views_72h", "likes_24h", "comments_24h", "shares_24h", "notes"]

REQUIRED = ("id", "verdict", "spoiler_level")


def apply_decisions() -> tuple[int, int]:
    """Read state/decisions/*.json (written by the reviewer) and move clips to approved/rejected."""
    con = db()
    ok = bad = 0
    for f in sorted(DECISIONS_DIR.glob("*.json")):
        dec = json.loads(f.read_text())
        row = con.execute("SELECT status FROM clips WHERE id=?", (dec.get("id"),)).fetchone()
        if not row or row["status"] != "packet":
            continue
        missing = [k for k in REQUIRED if k not in dec]
        if dec.get("verdict") == "approve":
            missing += [k for k in ("trim", "hook", "copy") if k not in dec]
        if missing:
            print(f"[decide] {f.name}: faltan campos {missing}")
            continue
        if dec["verdict"] == "approve" and dec["spoiler_level"] == 0:
            set_status(con, dec["id"], "approved", dec.get("reason", ""))
            ok += 1
        else:
            set_status(con, dec["id"], "rejected", f"review: {dec.get('reason', '')}")
            bad += 1
    return ok, bad


def caption(dec: dict, lang: str, row) -> dict:
    c = dec["copy"][lang]
    tags = " ".join(h if h.startswith("#") else "#" + h for h in c.get("hashtags", []))
    handle = "@" + row["creator_handle"].lstrip("@")
    src = (row["lang"] or "").lower()
    es_name, en_name = LANG_NAMES.get(src, (src, src))
    plat = (row["platform"] or "").title()
    if lang == "ES":
        credit = f"🎥: {handle}" + (f" en {plat}" if plat else "") + ("" if src == "es" else f" (Traducido del {es_name})")
    else:
        credit = f"🎥: {handle}" + (f" on {plat}" if plat else "") + ("" if src == "en" else f" (Translated from {en_name})")
    body = f"{c['caption']}\n{credit}"
    yt_title = c.get("title") or c["caption"].split("\n")[0]
    return {
        "title": f"{yt_title} #Shorts"[:100],
        "tiktok_title": f"{body}\n{tags}"[:2200],
        "instagram_title": f"{body}\n{tags}"[:2200],
        "youtube_title": f"{yt_title} #Shorts"[:100],
        "description": f"{body}\n{tags}\nFuente / Source: {row['url']}",
    }


def _posts_today(con, profile: str, platform: str) -> list[str]:
    since = iso(now_utc() - dt.timedelta(hours=24))
    return [r[0] for r in con.execute(
        "SELECT COALESCE(scheduled_for, posted_at) FROM posts WHERE profile=? AND platform=? "
        "AND status IN ('sent','scheduled','queued') AND COALESCE(scheduled_for, posted_at) >= ? ORDER BY 1",
        (profile, platform, since)).fetchall()]


def _next_slot(con, profile: str, platforms: list[str], cfg: dict) -> dt.datetime | None:
    """Earliest time >= now that keeps min gap from every post of this account and the 24 h cap.
    Fills holes in the schedule instead of always appending at the end. None = publish now."""
    p = cfg["publish"]
    gap = dt.timedelta(minutes=p["min_gap_minutes"])
    now = now_utc()
    cand = now
    for plat in platforms:
        rows = con.execute(
            "SELECT COALESCE(scheduled_for, posted_at) FROM posts WHERE profile=? AND platform=? "
            "AND status IN ('sent','scheduled','queued') AND COALESCE(scheduled_for, posted_at) IS NOT NULL",
            (profile, plat)).fetchall()
        times = sorted(dt.datetime.strptime(r[0], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc) for r in rows)
        cap = p["daily_caps"].get(plat, 999)
        reset_tz = (p.get("daily_reset_tz") or {}).get(plat)
        for _ in range(500):
            moved = False
            for t in times:
                if abs(t - cand) < gap:
                    cand = t + gap
                    moved = True
            window = [t for t in times if cand - dt.timedelta(hours=24) < t <= cand + dt.timedelta(hours=24)]
            # rolling cap: in any 24 h window containing cand there must be room
            before = [t for t in times if cand - dt.timedelta(hours=24) < t <= cand]
            if reset_tz:
                # platform limit resets at local midnight of reset_tz (YouTube: Pacific time)
                from zoneinfo import ZoneInfo
                tz = ZoneInfo(reset_tz)
                day = cand.astimezone(tz).date()
                same_day = [t for t in times if t.astimezone(tz).date() == day]
                if len(same_day) >= cap:
                    nxt = dt.datetime.combine(day + dt.timedelta(days=1), dt.time(0, 10), tz)
                    cand = nxt.astimezone(dt.timezone.utc)
                    moved = True
            elif len(before) >= cap:
                cand = before[len(before) - cap] + dt.timedelta(hours=24) + dt.timedelta(minutes=10)
                moved = True
            if not moved:
                break
    return None if cand <= now + dt.timedelta(minutes=1) else cand


def _upload(file: Path, fields: dict, cfg: dict, idem: str) -> dict:
    p = cfg["publish"]
    key = os.environ.get(p["api_key_env"], "proxy-injected")
    data = [(k, v) for k, v in fields.items() if k != "platform[]"]
    data += [("platform[]", pl) for pl in fields["platform[]"]]
    with open(file, "rb") as fh:
        r = requests.post(f"{p['api_base']}/api/upload",
                          headers={"Authorization": f"Apikey {key}", "Idempotency-Key": idem},
                          data=data, files={"video": (file.name, fh, "video/mp4")}, timeout=600)
    try:
        body = r.json()
    except ValueError:
        body = {"raw": r.text[:500]}
    body["_http"] = r.status_code
    return body


_CONNECTED: dict[str, set] = {}


def connected_platforms(profile: str, cfg: dict) -> set:
    """Platforms actually connected to an Upload-Post profile (cached per run)."""
    if profile not in _CONNECTED:
        p = cfg["publish"]
        key = os.environ.get(p["api_key_env"], "proxy-injected")
        try:
            r = requests.get(f"{p['api_base']}/api/uploadposts/users",
                             headers={"Authorization": f"Apikey {key}"}, timeout=30)
            for prof in r.json().get("profiles", []):
                _CONNECTED[prof.get("username")] = {k for k, v in (prof.get("social_accounts") or {}).items() if v}
        except Exception as ex:
            print(f"[publish] no pude leer perfiles: {ex}")
        _CONNECTED.setdefault(profile, set())
    return _CONNECTED[profile]


def publish_all(dry: bool = False) -> list[str]:
    cfg = settings()
    p = cfg["publish"]
    con = db()
    done = []
    rows = con.execute("SELECT * FROM clips WHERE status='rendered' ORDER BY views DESC").fetchall()
    if p["provider"] == "queue" and not dry:
        live = [r for r in rows if not r["test"]]
        print(f"[publish] provider=queue: {len(live)} clips listos en media/edits, esperando conexión de Upload-Post")
        rows = [r for r in rows if r["test"]]
    def _prio(r):
        f = DECISIONS_DIR / f"{r['id']}.json"
        try:
            return bool(json.loads(f.read_text()).get("priority"))
        except Exception:
            return False
    rows = sorted(rows, key=lambda r: (_prio(r), r["views"] or 0), reverse=True)
    for row in rows:
        dec = json.loads((DECISIONS_DIR / f"{row['id']}.json").read_text())
        for lang in ("ES", "EN"):
            mp4 = EDITS_DIR / lang / f"{row['id']}_{lang}.mp4"
            profile = p["profiles"][lang]
            todo = [pl for pl in p["platforms"] if not con.execute(
                "SELECT 1 FROM posts WHERE clip_id=? AND lang=? AND platform=? AND status IN ('sent','scheduled','queued','skipped')",
                (row["id"], lang, pl)).fetchone()]
            if not (dry or row["test"]):
                todo = [pl for pl in todo if pl in connected_platforms(profile, cfg)]
                age_h = (now_utc() - dt.datetime.strptime(row["discovered_at"], "%Y-%m-%dT%H:%M:%SZ")
                         .replace(tzinfo=dt.timezone.utc)).total_seconds() / 3600
                already = con.execute("SELECT 1 FROM posts WHERE clip_id=? AND lang=?", (row["id"], lang)).fetchone()
                if already and age_h > p.get("max_backlog_hours", 36):
                    todo = []
            if not todo:
                continue
            # each platform gets its own slot (a full TikTok must not delay Instagram/YouTube)
            groups: dict = {}
            for pl in todo:
                prio = bool(dec.get("priority"))
                pcfg = cfg
                if prio:  # viral clip: tighter spacing, ignore lookahead (caps still apply)
                    pcfg = {**cfg, "publish": {**p, "min_gap_minutes": 5}}
                sl = _next_slot(con, profile, [pl], pcfg)
                ahead = p.get("max_schedule_ahead_hours", {}).get(pl)
                if sl and ahead and not prio and sl > now_utc() + dt.timedelta(hours=ahead):
                    con.execute("INSERT OR REPLACE INTO posts VALUES (?,?,?,?,?,?,?,?,?)",
                                (row["id"], lang, pl, profile, "skipped", None, None, None,
                                 json.dumps({"reason": f"cola de {pl} llena más de {ahead} h"})))
                    continue
                groups.setdefault(iso(sl) if sl else None, []).append(pl)
            for key, plats in groups.items():
                slot = dt.datetime.strptime(key, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc) if key else None
                fields = {"user": profile, "platform[]": plats, **caption(dec, lang, row),
                          "privacy_level": p["tiktok_privacy"], "async_upload": "true",
                          "external_id": f"{row['id']}_{lang}"}
                if slot:
                    fields["scheduled_date"] = iso(slot)
                if dry or row["test"]:
                    status, resp = "queued", {"dry_run": True, "fields": {k: v for k, v in fields.items()}}
                else:
                    resp = _upload(mp4, fields, cfg, idem=f"{row['id']}_{lang}_{'-'.join(sorted(plats))}_{key or 'now'}")
                    ok = resp.get("_http") in (200, 201, 202) and resp.get("success", True) is not False
                    status = ("scheduled" if slot else "sent") if ok else "error"
                for pl in plats:
                    con.execute("INSERT OR REPLACE INTO posts VALUES (?,?,?,?,?,?,?,?,?)",
                                (row["id"], lang, pl, profile, status,
                                 resp.get("request_id") or resp.get("job_id"),
                                 iso(slot) if slot else None, None if slot else iso(),
                                 json.dumps(resp, ensure_ascii=False)[:4000]))
                    _score_row(row, dec, lang, pl, profile, status, slot)
                con.commit()
                _log(row, dec, lang, plats, status, slot, resp)
                print(f"[publish] {row['id']} {lang} {plats} -> {status}{' @' + iso(slot) if slot else ''}")
        sts = [r["status"] for r in con.execute("SELECT status FROM posts WHERE clip_id=?", (row["id"],)).fetchall()]
        if sts and all(s_ in ("sent", "scheduled", "queued", "skipped") for s_ in sts) and len(sts) >= 2 * len(p["platforms"]):
            set_status(con, row["id"], "published")
            done.append(row["id"])
    return done


def _score_row(row, dec, lang, platform, profile, status, slot):
    new = not SCORE.exists()
    with SCORE.open("a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=SCORE_COLS)
        if new:
            w.writeheader()
        w.writerow({"post_id": f"{row['id']}_{lang}_{platform}", "clip_id": row["id"], "lang": lang,
                    "platform": platform, "profile": profile, "pillar": dec.get("pillar", ""),
                    "source_creator": row["creator_handle"], "source_lang": row["lang"],
                    "duration_s": round(dec["trim"][1] - dec["trim"][0], 1), "status": status,
                    "scheduled_for": iso(slot) if slot else "", "published_at": "" if slot else iso(),
                    "notes": "TEST" if row["test"] else ""})


def _log(row, dec, lang, platforms, status, slot, resp):
    if not LOG.exists():
        LOG.write_text("# log.md — registro cronológico de publicaciones\n\n")
    err = "" if status != "error" else f" | error: {str(resp)[:200]}"
    with LOG.open("a") as fh:
        fh.write(f"- {iso()} | `{row['id']}_{lang}` | {dec.get('pillar', '')} | {','.join(platforms)} | "
                 f"{status}{' @' + iso(slot) if slot else ''} | 🎥 @{row['creator_handle'].lstrip('@')} "
                 f"({row['lang']}->{lang}) | Spoiler: 0% (Verificado){err}\n")


# ---------------------------------------------------------------- metrics
BUCKETS = (12, 24, 72)


def _metrics_table(con):
    con.execute("""CREATE TABLE IF NOT EXISTS metrics (
        clip_id TEXT, lang TEXT, platform TEXT, bucket INTEGER, views INTEGER, likes INTEGER,
        comments INTEGER, shares INTEGER, fetched_at TEXT, PRIMARY KEY (clip_id, lang, platform, bucket))""")


def fetch_metrics() -> int:
    """Fill 12h/24h/72h snapshots for published posts (Upload-Post post-analytics)."""
    cfg = settings()
    p = cfg["publish"]
    key = os.environ.get(p["api_key_env"], "proxy-injected")
    con = db()
    _metrics_table(con)
    now = now_utc()
    n = 0
    for r in con.execute("SELECT * FROM posts WHERE status IN ('sent','scheduled') AND request_id IS NOT NULL").fetchall():
        when = r["scheduled_for"] or r["posted_at"]
        if not when:
            continue
        age_h = (now - dt.datetime.strptime(when, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)).total_seconds() / 3600
        due = [b for b in BUCKETS if age_h >= b and not con.execute(
            "SELECT 1 FROM metrics WHERE clip_id=? AND lang=? AND platform=? AND bucket=?",
            (r["clip_id"], r["lang"], r["platform"], b)).fetchone()]
        if not due:
            continue
        try:
            resp = requests.get(f"{p['api_base']}/api/uploadposts/post-analytics/{r['request_id']}",
                                params={"platform": r["platform"]}, headers={"Authorization": f"Apikey {key}"}, timeout=30)
            m = ((resp.json().get("platforms") or {}).get(r["platform"]) or {}).get("post_metrics") or {}
        except Exception as ex:
            print(f"[metrics] {r['clip_id']} {r['platform']}: {ex}")
            continue
        if not m:
            continue
        for b in due:
            con.execute("INSERT OR REPLACE INTO metrics VALUES (?,?,?,?,?,?,?,?,?)",
                        (r["clip_id"], r["lang"], r["platform"], b, m.get("views"), m.get("likes"),
                         m.get("comments"), m.get("shares"), iso()))
            n += 1
    con.commit()
    write_scoreboard()
    return n


def write_scoreboard() -> None:
    """Rebuild scoreboard.csv from the posts + metrics tables."""
    con = db()
    _metrics_table(con)
    met = {}
    for m in con.execute("SELECT * FROM metrics"):
        met[(m["clip_id"], m["lang"], m["platform"], m["bucket"])] = m
    with SCORE.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=SCORE_COLS)
        w.writeheader()
        for r in con.execute("SELECT p.*, c.creator_handle, c.lang AS src_lang, c.test FROM posts p "
                             "JOIN clips c ON c.id=p.clip_id ORDER BY COALESCE(p.scheduled_for, p.posted_at)"):
            f = DECISIONS_DIR / f"{r['clip_id']}.json"
            dec = json.loads(f.read_text()) if f.exists() else {}
            g = lambda b, k: (met.get((r["clip_id"], r["lang"], r["platform"], b)) or {k: ""})[k]
            w.writerow({"post_id": f"{r['clip_id']}_{r['lang']}_{r['platform']}", "clip_id": r["clip_id"],
                        "lang": r["lang"], "platform": r["platform"], "profile": r["profile"],
                        "pillar": dec.get("pillar", ""), "source_creator": r["creator_handle"],
                        "source_lang": r["src_lang"],
                        "duration_s": round(dec["trim"][1] - dec["trim"][0], 1) if dec.get("trim") else "",
                        "status": r["status"], "scheduled_for": r["scheduled_for"] or "",
                        "published_at": r["posted_at"] or "", "views_12h": g(12, "views"),
                        "views_24h": g(24, "views"), "views_72h": g(72, "views"), "likes_24h": g(24, "likes"),
                        "comments_24h": g(24, "comments"), "shares_24h": g(24, "shares"),
                        "notes": "TEST" if r["test"] else ""})
