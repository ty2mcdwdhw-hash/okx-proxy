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
    """None = publish now. Otherwise the earliest time that respects caps and min gap."""
    p = cfg["publish"]
    gap = dt.timedelta(minutes=p["min_gap_minutes"])
    slot = now_utc()
    for plat in platforms:
        times = [dt.datetime.strptime(t, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
                 for t in _posts_today(con, profile, plat)]
        if times:
            slot = max(slot, max(times) + gap)
        cap = p["daily_caps"].get(plat, 999)
        if len(times) >= cap:
            slot = max(slot, times[len(times) - cap] + dt.timedelta(hours=24))
    return None if slot <= now_utc() + dt.timedelta(minutes=1) else slot


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
    for row in rows:
        dec = json.loads((DECISIONS_DIR / f"{row['id']}.json").read_text())
        for lang in ("ES", "EN"):
            mp4 = EDITS_DIR / lang / f"{row['id']}_{lang}.mp4"
            profile = p["profiles"][lang]
            todo = [pl for pl in p["platforms"] if not con.execute(
                "SELECT 1 FROM posts WHERE clip_id=? AND lang=? AND platform=? AND status IN ('sent','scheduled','queued')",
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
            slot = _next_slot(con, profile, todo, cfg)
            fields = {"user": profile, "platform[]": todo, **caption(dec, lang, row),
                      "privacy_level": p["tiktok_privacy"], "async_upload": "true",
                      "external_id": f"{row['id']}_{lang}"}
            if slot:
                fields["scheduled_date"] = iso(slot)
            if dry or row["test"]:
                status, resp = "queued", {"dry_run": True, "fields": {k: v for k, v in fields.items()}}
            else:
                resp = _upload(mp4, fields, cfg, idem=f"{row['id']}_{lang}")
                ok = resp.get("_http") in (200, 201, 202) and resp.get("success", True) is not False
                status = ("scheduled" if slot else "sent") if ok else "error"
            for pl in todo:
                con.execute("INSERT OR REPLACE INTO posts VALUES (?,?,?,?,?,?,?,?,?)",
                            (row["id"], lang, pl, profile, status,
                             resp.get("request_id") or resp.get("job_id"),
                             iso(slot) if slot else None, None if slot else iso(),
                             json.dumps(resp, ensure_ascii=False)[:4000]))
                _score_row(row, dec, lang, pl, profile, status, slot)
            con.commit()
            _log(row, dec, lang, todo, status, slot, resp)
            print(f"[publish] {row['id']} {lang} {todo} -> {status}{' @' + iso(slot) if slot else ''}")
        sts = [r["status"] for r in con.execute("SELECT status FROM posts WHERE clip_id=?", (row["id"],)).fetchall()]
        if sts and all(s_ in ("sent", "scheduled", "queued") for s_ in sts) and len(sts) >= 2 * len(p["platforms"]):
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
