"""Render an approved decision into 9:16 MP4s (ES and EN) with burned hook + subtitles."""
from __future__ import annotations

import json
from pathlib import Path

from .core import DECISIONS_DIR, EDITS_DIR, LANG_NAMES, ROOT, db, ffprobe, run, set_status, settings

LANGS = ("ES", "EN")


def _ts(t: float) -> str:
    t = max(0.0, t)
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def _esc(text: str) -> str:
    return (text or "").replace("\\", "").replace("{", "(").replace("}", ")").replace("\n", "\\N")


HI = "{\\c&H0000E5FF&\\fscx115\\fscy115}"   # active word: yellow + bigger
RESET = "{\\r}"


def _chunks(text: str, max_chars: int) -> list[list[str]]:
    words, out, cur = text.split(), [], []
    for w in words:
        if cur and len(" ".join(cur + [w])) > max_chars:
            out.append(cur)
            cur = []
        cur.append(w)
    if cur:
        out.append(cur)
    return out


def _dynamic_sub(text: str, a: float, b: float, max_chars: int) -> list[str]:
    """Short word groups that pop in; the word being said turns yellow and grows."""
    groups = _chunks(text, max_chars)
    total = sum(len(w) + 1 for g in groups for w in g) or 1
    t, ev = a, []
    for g in groups:
        g_len = sum(len(w) + 1 for w in g)
        g_end = t + (b - a) * g_len / total
        wt = t
        for i, w in enumerate(g):
            w_end = wt + (g_end - t) * (len(w) + 1) / g_len
            words = [_esc(x) for x in g]
            words[i] = f"{HI}{words[i]}{RESET}"
            pop = "{\\fscx70\\fscy70\\t(0,120,\\fscx100\\fscy100)}" if i == 0 else ""
            ev.append(f"Dialogue: 0,{_ts(wt)},{_ts(w_end)},Sub,,0,0,0,,{pop}{' '.join(words)}")
            wt = w_end
        t = g_end
    return ev


def build_ass(dec: dict, lang: str, dur: float, cfg: dict, row) -> str:
    r = cfg["render"]
    W, H, font = r["width"], r["height"], r["font"]
    vid_h = round(W * 9 / 16 * r["zoom"]) if r["layout"] == "blur" else H
    vid_bottom = r["video_top"] + vid_h if r["layout"] == "blur" else int(H * 0.72)
    sub_margin = max(330, H - vid_bottom - 190)   # bottom of subs ~190px under the video
    t0 = dec["trim"][0]
    hook = _esc(dec["hook"][lang].upper())
    src_lang = (row["lang"] or "").lower()
    es_name, en_name = LANG_NAMES.get(src_lang, (src_lang, src_lang))
    credit = dec.get("label", {}).get(lang) or (
        f"@{row['creator_handle'].lstrip('@')}" +
        ("" if src_lang == lang.lower() else (f" · traducido del {es_name}" if lang == "ES" else f" · translated from {en_name}")))
    hs = r["hook_seconds"]
    out = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}", "WrapStyle: 0",
        "ScaledBorderAndShadow: yes", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
        "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Hook,{font},{r.get('hook_size', 122)},&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,0,0,0,0,100,100,1,0,1,8,3,8,60,60,190,1",
        f"Style: Top,{font},{r.get('title_size', 86)},&H0000E5FF,&H0000E5FF,&H00000000,&H64000000,0,0,0,0,100,100,1,0,1,6,2,8,60,60,250,1",
        f"Style: Credit,{font},44,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,0,0,0,0,100,100,1,0,1,3,1,8,70,70,{r['video_top'] - 70},1",
        f"Style: Sub,{font},{r.get('sub_size', 96)},&H00FFFFFF,&H0000E5FF,&H00000000,&H78000000,0,0,0,0,100,100,1,0,1,7,3,2,60,60,{sub_margin},1",
        "", "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        # big hook with pop-in for the first seconds, then a smaller persistent title
        f"Dialogue: 2,{_ts(0)},{_ts(min(hs, dur))},Hook,,0,0,0,,{{\\fscx80\\fscy80\\t(0,180,\\fscx100\\fscy100)\\fad(0,150)}}{hook}",
        f"Dialogue: 1,{_ts(min(hs, dur))},{_ts(dur)},Top,,0,0,0,,{{\\fad(150,0)}}{hook}",
        f"Dialogue: 1,{_ts(0)},{_ts(dur)},Credit,,0,0,0,,{_esc(credit)}",
    ]
    for s in dec.get("subs") or []:
        a, b = s["start"] - t0, s["end"] - t0
        if b <= 0 or a >= dur or not s.get(lang):
            continue
        a, b = max(a, 0.0), min(b, dur)
        if r.get("dynamic_subs", True):
            out += _dynamic_sub(s[lang], a, b, r.get("sub_chunk_chars", 20))
        else:
            out.append(f"Dialogue: 0,{_ts(a)},{_ts(b)},Sub,,0,0,0,,{_esc(s[lang])}")
    return "\n".join(out) + "\n"


def render_one(clip_id: str) -> list[Path]:
    cfg = settings()
    r = cfg["render"]
    con = db()
    row = con.execute("SELECT * FROM clips WHERE id=?", (clip_id,)).fetchone()
    dec = json.loads((DECISIONS_DIR / f"{clip_id}.json").read_text())
    raw = Path(row["raw_path"])
    meta = ffprobe(raw)
    t0, t1 = dec["trim"]
    t1 = min(t1, meta["duration"])
    dur = t1 - t0
    fps = min(meta["fps"] or 30, r["fps_max"])
    W, H = r["width"], r["height"]
    if r["layout"] == "blur":
        fw = int(W * r["zoom"]) // 2 * 2
        vf = (f"[0:v]split=2[a][b];[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
              f"boxblur=24:2,eq=brightness=-0.18[bg];[b]scale={fw}:-2,crop={W}:ih[fg];"
              f"[bg][fg]overlay=0:{r['video_top']},fps={fps}")
    else:  # fill: center crop to 9:16
        vf = f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={fps}"
    outs = []
    for lang in LANGS:
        ass = EDITS_DIR / lang / f"{clip_id}_{lang}.ass"
        ass.write_text(build_ass(dec, lang, dur, cfg, row))
        mp4 = EDITS_DIR / lang / f"{clip_id}_{lang}.mp4"
        fontsdir = ROOT / r["fontsdir"]
        graph = f"{vf},ass={ass}:fontsdir={fontsdir}[v]"
        cmd = ["ffmpeg", "-hide_banner", "-y", "-ss", f"{t0:.2f}", "-to", f"{t1:.2f}", "-i", str(raw),
               "-filter_complex", graph, "-map", "[v]"]
        if meta["has_audio"]:
            cmd += ["-map", "0:a:0", "-c:a", "aac", "-b:a", "160k", "-ar", "48000"]
            if r["loudnorm"]:
                cmd += ["-af", "loudnorm=I=-14:TP=-1.5:LRA=11"]
        cmd += ["-c:v", "libx264", "-preset", r["preset"], "-crf", str(r["crf"]), "-pix_fmt", "yuv420p",
                "-profile:v", "high", "-movflags", "+faststart", str(mp4)]
        run(cmd, timeout=900)
        outs.append(mp4)
    set_status(con, clip_id, "rendered")
    return outs


def render_all() -> list[str]:
    con = db()
    done = []
    for row in con.execute("SELECT id FROM clips WHERE status='approved'").fetchall():
        try:
            render_one(row["id"])
            done.append(row["id"])
            print(f"[render] {row['id']} -> ES/EN")
        except Exception as ex:
            set_status(con, row["id"], "failed", f"render: {str(ex)[:400]}")
            print(f"[render] {row['id']} FAILED: {str(ex)[:300]}")
    return done
