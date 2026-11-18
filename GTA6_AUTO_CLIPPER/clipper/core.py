"""Shared config, paths, state DB and helpers."""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import sqlite3
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
STATE_DIR = ROOT / "state"
RAW_DIR = ROOT / "media" / "raw"
EDITS_DIR = ROOT / "media" / "edits"
REVIEW_DIR = STATE_DIR / "review"
DECISIONS_DIR = STATE_DIR / "decisions"
DB_PATH = STATE_DIR / "clipper.db"

for d in (STATE_DIR, RAW_DIR, EDITS_DIR / "ES", EDITS_DIR / "EN", REVIEW_DIR, DECISIONS_DIR):
    d.mkdir(parents=True, exist_ok=True)

LANG_NAMES = {
    "ja": ("japonés", "Japanese"), "ko": ("coreano", "Korean"), "ru": ("ruso", "Russian"),
    "de": ("alemán", "German"), "fr": ("francés", "French"), "pt": ("portugués", "Portuguese"),
    "ar": ("árabe", "Arabic"), "pl": ("polaco", "Polish"), "zh": ("mandarín", "Mandarin"),
    "hi": ("hindi", "Hindi"), "it": ("italiano", "Italian"), "es": ("español", "Spanish"),
    "en": ("inglés", "English"), "tr": ("turco", "Turkish"),
}


def settings() -> dict:
    return yaml.safe_load((CONFIG_DIR / "settings.yaml").read_text())


def watchlist(include_disabled: bool = False) -> list[dict]:
    data = yaml.safe_load((CONFIG_DIR / "watchlist.yaml").read_text())
    out = []
    for group, items in (data.get("groups") or {}).items():
        for it in items or []:
            it = dict(it, group=group)
            if include_disabled or it.get("enabled", True):
                out.append(it)
    return out


def now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def iso(ts: dt.datetime | None = None) -> str:
    return (ts or now_utc()).strftime("%Y-%m-%dT%H:%M:%SZ")


def db() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.executescript(
        """
        CREATE TABLE IF NOT EXISTS clips (
            id TEXT PRIMARY KEY,          -- e.g. TW_abc123 / YT_vid_120
            source TEXT, url TEXT, creator TEXT, creator_handle TEXT, platform TEXT,
            lang TEXT, title TEXT, views INTEGER, created_at TEXT, duration REAL,
            section_start REAL, section_end REAL,
            status TEXT DEFAULT 'discovered', -- discovered|downloaded|transcribed|packet|approved|rejected|rendered|published|failed|takedown
            reason TEXT, test INTEGER DEFAULT 0,
            raw_path TEXT, meta_json TEXT,
            discovered_at TEXT, updated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS posts (
            clip_id TEXT, lang TEXT, platform TEXT, profile TEXT,
            status TEXT, request_id TEXT, scheduled_for TEXT, posted_at TEXT,
            response TEXT, PRIMARY KEY (clip_id, lang, platform)
        );
        """
    )
    return con


def set_status(con, clip_id: str, status: str, reason: str | None = None, **fields):
    cols = {"status": status, "updated_at": iso(), **fields}
    if reason is not None:
        cols["reason"] = reason
    sets = ", ".join(f"{k}=?" for k in cols)
    con.execute(f"UPDATE clips SET {sets} WHERE id=?", (*cols.values(), clip_id))
    con.commit()


def run(cmd: list[str], timeout: int | None = None, check: bool = True, text: bool = True) -> subprocess.CompletedProcess:
    p = subprocess.run(cmd, capture_output=True, text=text, timeout=timeout)
    if check and p.returncode != 0:
        err = p.stderr if text else p.stderr.decode("utf-8", "replace")
        raise RuntimeError(f"cmd failed ({p.returncode}): {' '.join(cmd)[:300]}\n{err[-1500:]}")
    return p


def ffprobe(path: str | Path) -> dict:
    p = run(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", str(path)])
    j = json.loads(p.stdout)
    v = next((s for s in j["streams"] if s["codec_type"] == "video"), {})
    a = next((s for s in j["streams"] if s["codec_type"] == "audio"), None)
    num, _, den = (v.get("avg_frame_rate") or "0/1").partition("/")
    fps = float(num) / float(den or 1) if float(den or 1) else 0.0
    return {
        "duration": float(j["format"].get("duration", 0)),
        "width": v.get("width"), "height": v.get("height"), "fps": round(fps, 2),
        "vcodec": v.get("codec_name"), "has_audio": a is not None,
    }


def safe_id(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "-", s)[:80]


def yt_dlp_base() -> list[str]:
    return ["yt-dlp", "--no-warnings", "--quiet", "--no-progress", "--js-runtimes", "deno"]


def current_focus(cfg: dict) -> dict | None:
    """Regional focus window active now (times in operator_tz)."""
    from zoneinfo import ZoneInfo
    tz = ZoneInfo(cfg.get("operator_tz", "UTC"))
    now = dt.datetime.now(tz).replace(tzinfo=None)
    for f in cfg.get("focus") or []:
        if dt.datetime.fromisoformat(f["from"]) <= now <= dt.datetime.fromisoformat(f["to"]):
            return f
    return None
