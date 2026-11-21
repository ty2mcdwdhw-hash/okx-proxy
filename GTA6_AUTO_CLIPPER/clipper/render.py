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
HI_CENSOR = "{\\c&H0000E5FF&}"

# Censura "pixelada": en los subs, [[palabra]] se dibuja invisible en la pasada principal (ocupa su sitio) y
# visible (rosa, borde blanco grueso) en una pasada aparte que luego se pixela y se superpone encima.
_OPEN, _CLOSE = "⟦", "⟧"
CENSOR_ON = {"main": "{\\alpha&HFF&}", "censor": "{\\alpha&H00&\\1c&HFFFFFF&\\3c&HB43CFF&}"}
CENSOR_OFF = {"main": "{\\alpha&H00&}", "censor": "{\\alpha&HFF&}"}


def _mark_censored(text: str) -> str:
    """[[a b]] -> each word wrapped in private markers so word splitting keeps them."""
    import re
    return re.sub(r"\[\[(.+?)\]\]", lambda m: " ".join(f"{_OPEN}{w}{_CLOSE}" for w in m.group(1).split()), text or "")


def _plain(w: str) -> str:
    return w.replace(_OPEN, "").replace(_CLOSE, "")


def _censor_tags(text: str, mode: str) -> str:
    return text.replace(_OPEN, CENSOR_ON[mode]).replace(_CLOSE, CENSOR_OFF[mode])


def has_censor(dec: dict, lang: str) -> bool:
    return any("[[" in (s.get(lang) or "") for s in dec.get("subs") or [])


def _chunks(text: str, max_chars: int) -> list[list[str]]:
    words, out, cur = text.split(), [], []
    for w in words:
        if cur and len(_plain(" ".join(cur + [w]))) > max_chars:
            out.append(cur)
            cur = []
        cur.append(w)
    if cur:
        out.append(cur)
    return out


def _dynamic_sub(text: str, a: float, b: float, max_chars: int, mode: str = "main") -> list[str]:
    """Short word groups that pop in; the word being said turns yellow and grows."""
    text = _mark_censored(text)
    groups = _chunks(text, max_chars)
    total = sum(len(_plain(w)) + 1 for g in groups for w in g) or 1
    base = "" if mode == "main" else CENSOR_OFF["censor"]          # censor pass: everything invisible by default
    reset = RESET + base
    t, ev = a, []
    for g in groups:
        g_len = sum(len(_plain(w)) + 1 for w in g)
        g_end = t + (b - a) * g_len / total
        wt = t
        for i, w in enumerate(g):
            w_end = wt + (g_end - t) * (len(_plain(w)) + 1) / g_len
            words = [_esc(x) for x in g]
            hi = HI_CENSOR if _OPEN in words[i] else HI     # censored word: no pop, box stays fixed
            words[i] = f"{hi}{words[i]}{reset}"
            pop = "{\\fscx70\\fscy70\\t(0,120,\\fscx100\\fscy100)}" if i == 0 else ""
            line = _censor_tags(" ".join(words), mode)
            ev.append(f"Dialogue: 0,{_ts(wt)},{_ts(w_end)},Sub,,0,0,0,,{pop}{base}{line}")
            wt = w_end
        t = g_end
    return ev


def build_ass(dec: dict, lang: str, dur: float, cfg: dict, row, mode: str = "main") -> str:
    """mode='main': full overlay (censored words invisible). mode='censor': only censored words, for pixelation."""
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
        # same metrics as Sub, opaque box (BorderStyle 3) -> only used in the censor pass
        f"Style: Censor,{font},{r.get('sub_size', 96)},&H00FFFFFF,&H0000E5FF,&H00B43CFF,&H00B43CFF,0,0,0,0,100,100,1,0,3,4,0,2,60,60,{sub_margin},1",
        # GTA VI tag (our own text badge, not Rockstar's logo artwork) and account watermark
        f"Style: Badge,{font},46,&H00FFFFFF,&H00FFFFFF,&H00B43CFF,&H00B43CFF,0,0,0,0,100,100,2,0,3,10,0,7,40,40,{r['video_top'] + 22},1",
        f"Style: WM,{font},44,&H59FFFFFF,&H59FFFFFF,&H90000000,&H00000000,0,0,0,0,100,100,1,0,1,2,0,3,40,40,{H - vid_bottom + 22},1",
        "", "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    if mode == "censor":
        for s in dec.get("subs") or []:
            a, b = s["start"] - t0, s["end"] - t0
            if b <= 0 or a >= dur or "[[" not in (s.get(lang) or ""):
                continue
            a, b = max(a, 0.0), min(b, dur)
            if r.get("dynamic_subs", True):
                out += [e.replace(",Sub,,", ",Censor,,", 1) for e in
                        _dynamic_sub(s[lang], a, b, r.get("sub_chunk_chars", 20), mode)]
            else:
                line = _censor_tags(_esc(_mark_censored(s[lang])), mode)
                out.append(f"Dialogue: 0,{_ts(a)},{_ts(b)},Censor,,0,0,0,,{CENSOR_OFF['censor']}{line}")
        return "\n".join(out) + "\n"
    out += [
        # big hook with pop-in for the first seconds, then a smaller persistent title
        f"Dialogue: 2,{_ts(0)},{_ts(min(hs, dur))},Hook,,0,0,0,,{{\\fscx80\\fscy80\\t(0,180,\\fscx100\\fscy100)\\fad(0,150)}}{hook}",
        f"Dialogue: 1,{_ts(min(hs, dur))},{_ts(dur)},Top,,0,0,0,,{{\\fad(150,0)}}{hook}",
        f"Dialogue: 1,{_ts(0)},{_ts(dur)},Credit,,0,0,0,,{_esc(credit)}",
    ]
    badge = dec.get("badge", r.get("badge", "GTA VI"))
    if badge:
        out.append(f"Dialogue: 3,{_ts(0)},{_ts(dur)},Badge,,0,0,0,,{_esc(badge)}")
    wm = (r.get("watermark") or {}).get(lang)
    if wm:
        out.append(f"Dialogue: 3,{_ts(0)},{_ts(dur)},WM,,0,0,0,,{_esc(wm)}")
    for s in dec.get("subs") or []:
        a, b = s["start"] - t0, s["end"] - t0
        if b <= 0 or a >= dur or not s.get(lang):
            continue
        a, b = max(a, 0.0), min(b, dur)
        if r.get("dynamic_subs", True):
            out += _dynamic_sub(s[lang], a, b, r.get("sub_chunk_chars", 20))
        else:
            line = _censor_tags(_esc(_mark_censored(s[lang])), "main")
            out.append(f"Dialogue: 0,{_ts(a)},{_ts(b)},Sub,,0,0,0,,{line}")
    return "\n".join(out) + "\n"


def _between(spans: list, t0: float, dur: float) -> str:
    """ffmpeg enable expression for [start,end] spans given in original-clip time."""
    parts = []
    for s, e in spans:
        a, b = max(s - t0, 0.0), min(e - t0, dur)
        if b > a:
            parts.append(f"between(t,{a:.2f},{b:.2f})")
    return "+".join(parts)


def _pixelate_src(dec: dict, meta: dict, t0: float, dur: float) -> tuple[str, str]:
    """Pixelate on-screen text regions of the SOURCE (streamer overlays, chat, burned subs).
    dec['pixelate'] = [{"box": [x, y, w, h] (fractions of the source frame), "start": s, "end": e}]"""
    sw, sh = meta.get("width") or 1920, meta.get("height") or 1080
    chain, cur, k = [], "[0:v]", 0
    for p in dec.get("pixelate") or []:
        x, y, w, h = p["box"]
        cw, ch = max(int(sw * w) // 2 * 2, 8), max(int(sh * h) // 2 * 2, 8)
        cx, cy = int(sw * x), int(sh * y)
        en = _between([(p.get("start", t0), p.get("end", t0 + dur))], t0, dur)
        if not en:
            continue
        bpx = max(12, sw // 40)                      # ~48 px blocks on a 1920 source
        blk = max(cw // bpx, 1), max(ch // bpx, 1)
        chain.append(f"{cur}split=2[pb{k}][pc{k}];[pc{k}]crop={cw}:{ch}:{cx}:{cy},"
                     f"scale={blk[0]}:{blk[1]}:flags=area,scale={cw}:{ch}:flags=neighbor[pz{k}];"
                     f"[pb{k}][pz{k}]overlay={cx}:{cy}:enable='{en}'[px{k}]")
        cur, k = f"[px{k}]", k + 1
    return ";".join(chain), cur


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
    pix_chain, src = _pixelate_src(dec, meta, t0, dur)
    pre = pix_chain + ";" if pix_chain else ""
    if r["layout"] == "blur":
        fw = int(W * r["zoom"]) // 2 * 2
        vf = (f"{pre}{src}split=2[a][b];[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
              f"boxblur=24:2,eq=brightness=-0.18[bg];[b]scale={fw}:-2,crop={W}:ih[fg];"
              f"[bg][fg]overlay=0:{r['video_top']},fps={fps}")
    else:  # fill: center crop to 9:16
        vf = f"{pre}{src}scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={fps}"
    # audio: bleep = [[start, end], ...] in original-clip time -> mute + 1 kHz tone
    bleep_en = _between(dec.get("bleep") or [], t0, dur)
    outs = []
    for lang in LANGS:
        ass = EDITS_DIR / lang / f"{clip_id}_{lang}.ass"
        ass.write_text(build_ass(dec, lang, dur, cfg, row))
        mp4 = EDITS_DIR / lang / f"{clip_id}_{lang}.mp4"
        fontsdir = ROOT / r["fontsdir"]
        if has_censor(dec, lang):
            cass = EDITS_DIR / lang / f"{clip_id}_{lang}.censor.ass"
            cass.write_text(build_ass(dec, lang, dur, cfg, row, mode="censor"))
            px = int(r.get("censor_pixel", 26))
            graph = (f"{vf},ass={ass}:fontsdir={fontsdir}[vm];"
                     f"color=c=black:s={W}x{H}:r={fps}:d={dur:.2f},format=rgb24,ass={cass}:fontsdir={fontsdir},"
                     f"scale={W // px}:{H // px}:flags=area,lutrgb=r='min(255,val*1.8)':g='min(255,val*1.8)':b='min(255,val*1.8)',"
                     f"scale={W}:{H}:flags=neighbor,format=rgba,colorkey=0x000000:0.55:0.0[cz];[vm][cz]overlay=0:0:shortest=1[v]")
        else:
            graph = f"{vf},ass={ass}:fontsdir={fontsdir}[v]"
        cmd = ["ffmpeg", "-hide_banner", "-y", "-ss", f"{t0:.2f}", "-to", f"{t1:.2f}", "-i", str(raw)]
        amap = None
        if meta["has_audio"]:
            ln = "loudnorm=I=-14:TP=-1.5:LRA=11," if r["loudnorm"] else ""
            if bleep_en:
                graph += (f";[0:a]{ln}aformat=sample_rates=48000:channel_layouts=stereo,"
                          f"volume=volume=0:enable='{bleep_en}'[am];"
                          f"aevalsrc='0.22*sin(2*PI*1000*t)*gt({bleep_en},0)':s=48000:d={dur:.2f},"
                          f"aformat=sample_rates=48000:channel_layouts=stereo[bp];"
                          f"[am][bp]amix=inputs=2:normalize=0:duration=first[a]")
                amap = "[a]"
            else:
                amap = "0:a:0"
        cmd += ["-filter_complex", graph, "-map", "[v]"]
        if amap:
            cmd += ["-map", amap, "-c:a", "aac", "-b:a", "160k", "-ar", "48000"]
            if amap == "0:a:0" and r["loudnorm"]:
                cmd += ["-af", "loudnorm=I=-14:TP=-1.5:LRA=11"]
        cmd += ["-c:v", "libx264", "-preset", r["preset"], "-crf", str(r["crf"]), "-pix_fmt", "yuv420p",
                "-profile:v", "high", "-movflags", "+faststart", str(mp4)]
        run(cmd, timeout=900)
        try:                                   # edición propia: repetición comentada + voz en off
            from .enhance import enhance
            enhance(mp4, raw, dec, lang, row, cfg)
        except Exception as ex:
            print(f"[render] {clip_id} {lang}: edición propia omitida ({str(ex)[-300:]})")
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
