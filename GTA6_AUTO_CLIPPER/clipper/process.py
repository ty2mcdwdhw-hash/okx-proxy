"""Download -> probe -> letterbox check -> transcribe -> review packet."""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from .core import RAW_DIR, REVIEW_DIR, db, ffprobe, run, set_status, settings, yt_dlp_base


def download(row) -> Path:
    out = RAW_DIR / f"{row['id']}.mp4"
    if out.exists() and out.stat().st_size > 0:
        return out
    cmd = yt_dlp_base() + [
        "-f", "bv*[height<=1080][fps<=60]+ba/b[height<=1080]/bv*+ba/b",
        "--merge-output-format", "mp4", "-o", str(out),
    ]
    if row["section_start"] is not None:
        cmd += ["--download-sections", f"*{row['section_start']:.1f}-{row['section_end']:.1f}",
                "--force-keyframes-at-cuts"]
    run(cmd + [row["url"]], timeout=900)
    if not out.exists():  # yt-dlp may pick another container
        alt = sorted(RAW_DIR.glob(f"{row['id']}.*"))
        if not alt:
            raise RuntimeError("download produced no file")
        alt[0].rename(out)
    return out


def letterbox_ratio(path: Path, duration: float) -> float:
    """Share of sampled frames whose picture has cinematic black bars (top+bottom)."""
    hits = total = 0
    meta = ffprobe(path)
    H = meta["height"] or 1
    for i in range(6):
        t = duration * (i + 0.5) / 6
        p = run(["ffmpeg", "-hide_banner", "-ss", f"{t:.2f}", "-i", str(path), "-frames:v", "3",
                 "-vf", "cropdetect=limit=24:round=2:reset=0", "-f", "null", "-"], check=False, timeout=60)
        m = re.findall(r"crop=(\d+):(\d+):(\d+):(\d+)", p.stderr)
        if not m:
            continue
        w, h, x, y = map(int, m[-1])
        total += 1
        # full-width picture with >=9% black on both top and bottom = letterbox
        if w >= 0.95 * (meta["width"] or w) and y >= 0.09 * H and (H - h - y) >= 0.09 * H:
            hits += 1
    return hits / total if total else 0.0


@lru_cache(maxsize=1)
def _whisper():
    from faster_whisper import WhisperModel
    t = settings()["transcribe"]
    return WhisperModel(t["model"], device="cpu", compute_type=t["compute_type"])


def transcribe(path: Path, lang_hint: str | None) -> dict:
    import numpy as np
    model = _whisper()
    pcm = run(["ffmpeg", "-hide_banner", "-nostdin", "-i", str(path), "-vn", "-ac", "1", "-ar", "16000",
               "-f", "s16le", "-"], timeout=300, check=False, text=False).stdout
    audio = np.frombuffer(pcm, np.int16).astype(np.float32) / 32768.0
    if audio.size < 16000:
        return {"language": lang_hint, "language_prob": 0.0, "lang_hint": lang_hint, "segments": []}
    segs, info = model.transcribe(audio, language=None, vad_filter=True, beam_size=5, word_timestamps=True)
    segs = [{"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip(),
             "words": [[round(w.start, 2), round(w.end, 2), w.word.strip()] for w in (s.words or [])]}
            for s in segs]
    return {"language": info.language, "language_prob": round(info.language_probability, 2),
            "lang_hint": lang_hint, "segments": segs}


def contact_sheet(path: Path, duration: float, out: Path, n: int = 8) -> None:
    fps = n / max(duration, 1)
    run(["ffmpeg", "-hide_banner", "-y", "-i", str(path), "-vf",
         f"fps={fps:.4f},scale=480:-2,tile=4x2:padding=4", "-frames:v", "1", "-q:v", "4", str(out)],
        timeout=180)


def build_packet(row, raw: Path, meta: dict, tr: dict, lb: float) -> Path:
    d = REVIEW_DIR / row["id"]
    d.mkdir(parents=True, exist_ok=True)
    contact_sheet(raw, meta["duration"], d / "contact.jpg")
    (d / "transcript.json").write_text(json.dumps(tr, ensure_ascii=False, indent=1))
    lines = [f"# {row['id']}",
             f"- creator: {row['creator']} ({row['platform']}:{row['creator_handle']})",
             f"- url: {row['url']}",
             f"- title: {row['title']}",
             f"- views: {row['views']} | created: {row['created_at']}",
             f"- duration: {meta['duration']:.1f}s | {meta['width']}x{meta['height']} @ {meta['fps']}fps",
             f"- lang: detected={tr['language']} ({tr['language_prob']}) hint={row['lang']}",
             f"- letterbox_ratio: {lb:.2f}",
             "", "## transcript"]
    lines += [f"[{s['start']:6.2f}-{s['end']:6.2f}] {s['text']}" for s in tr["segments"]] or ["(sin voz)"]
    (d / "packet.md").write_text("\n".join(lines) + "\n")
    return d


def process(limit: int = 50, test_only: bool = False) -> list[str]:
    cfg = settings()
    con = db()
    from .core import current_focus
    focus = current_focus(cfg)
    langs = set((focus or {}).get("langs") or [])
    q = "SELECT * FROM clips WHERE status='discovered'" + (" AND test=1" if test_only else "")
    rows = sorted(con.execute(q).fetchall(),
                  key=lambda r: ((r["lang"] or "") in langs, r["views"] or 0), reverse=True)[:limit]
    if focus:
        print(f"[process] foco regional: {focus['name']} ({', '.join(sorted(langs))})")
    done = []
    for row in rows:
        cid = row["id"]
        try:
            raw = download(row)
            meta = ffprobe(raw)
            set_status(con, cid, "downloaded", raw_path=str(raw), meta_json=json.dumps(meta))
            if meta["duration"] < cfg["clip"]["min_seconds"]:
                set_status(con, cid, "rejected", "too short")
                continue
            lb = letterbox_ratio(raw, meta["duration"])
            if cfg["spoiler"]["letterbox_reject"] and lb >= 0.5:
                set_status(con, cid, "rejected", f"letterbox {lb:.2f} (probable cinemática)")
                continue
            tr = transcribe(raw, row["lang"])
            build_packet(row, raw, meta, tr, lb)
            set_status(con, cid, "packet", lang=tr["language"] if tr["language_prob"] > 0.6 else row["lang"])
            done.append(cid)
            print(f"[process] {cid} -> packet ({meta['duration']:.0f}s, {tr['language']})")
        except Exception as ex:
            set_status(con, cid, "failed", str(ex)[:500])
            print(f"[process] {cid} FAILED: {str(ex)[:200]}")
    return done
