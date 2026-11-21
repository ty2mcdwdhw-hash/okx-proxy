"""Compilación "Top 3" cada N horas con los clips más vistos de la ventana, solo de streamers del idioma elegido.

Usa los vídeos ya editados (media/edits/<LANG>/<ID>_<LANG>.mp4): tarjeta de entrada con voz, #3, #2, #1 con
número grande y voz, y tarjeta final. Se registra como un clip más ('rendered') para que `publish` lo suba.
ESCUDO DEL OPERADOR: solo imprime IDs y conteos.
"""
from __future__ import annotations

import datetime as dt
import json
import tempfile
from pathlib import Path

from .core import DECISIONS_DIR, EDITS_DIR, ROOT, STATE_DIR, db, ffprobe, iso, now_utc, run, settings
from .enhance import _esc, _ts, tts

LAST = STATE_DIR / "top3_last.txt"
TXT = {
    "ES": {"title": "TOP 3", "sub": "GTA VI · ÚLTIMOS 3 DÍAS", "end": "¿CUÁL FUE TU FAVORITO?",
           "intro": "Los tres mejores momentos de GTA seis de los últimos tres días. ¡Vamos!",
           "n": {3: "Número tres.", 2: "Número dos.", 1: "Y el número uno."},
           "outro": "¿Cuál fue tu favorito? Te leo en comentarios.",
           "caption": "Los 3 mejores momentos de GTA VI de los últimos 3 días. ¿Cuál fue tu favorito?",
           "ytitle": "TOP 3 momentos de GTA VI (últimos 3 días)"},
    "EN": {"title": "TOP 3", "sub": "GTA VI · LAST 3 DAYS", "end": "WHICH ONE WAS YOUR FAVORITE?",
           "intro": "The top three GTA six moments from the last three days. Let's go!",
           "n": {3: "Number three.", 2: "Number two.", 1: "And number one."},
           "outro": "Which one was your favorite? Tell me in the comments.",
           "caption": "The top 3 GTA VI moments from the last 3 days. Which one was your favorite?",
           "ytitle": "TOP 3 GTA VI moments (last 3 days)"},
}


def _due(every_h: float) -> bool:
    try:
        last = dt.datetime.strptime(LAST.read_text().strip(), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
    except Exception:
        return True
    return now_utc() - last >= dt.timedelta(hours=every_h)


def pick(con, cfg: dict) -> list:
    t = cfg.get("top3") or {}
    since = iso(now_utc() - dt.timedelta(hours=t.get("window_hours", 72)))
    langs = [l.lower() for l in t.get("source_langs", ["es"])]
    rows = con.execute(
        "SELECT DISTINCT c.id, c.lang, c.creator_handle, c.url, c.views FROM clips c JOIN posts p ON p.clip_id=c.id "
        "WHERE c.status='published' AND c.id NOT LIKE 'TOP3_%' AND p.status IN ('sent','scheduled') "
        "AND COALESCE(p.scheduled_for, p.posted_at) BETWEEN ? AND ?", (since, iso())).fetchall()
    scored = []
    for r in rows:
        if (r["lang"] or "").lower() not in langs:
            continue
        if not all((EDITS_DIR / L / f"{r['id']}_{L}.mp4").exists() for L in ("ES", "EN")):
            continue
        v = 0
        for m in con.execute("SELECT platform, lang, MAX(bucket) b FROM metrics WHERE clip_id=? GROUP BY 1,2", (r["id"],)):
            x = con.execute("SELECT views FROM metrics WHERE clip_id=? AND platform=? AND lang=? AND bucket=?",
                            (r["id"], m["platform"], m["lang"], m["b"])).fetchone()
            v += (x["views"] or 0) if x else 0
        scored.append((v, r["views"] or 0, r))
    scored.sort(key=lambda s: (s[0], s[1]), reverse=True)
    return [s[2] for s in scored[:3]]


def _card_ass(cfg: dict, big: str, small: str, dur: float) -> str:
    r = cfg["render"]
    W, H, font = r["width"], r["height"], r["font"]
    return "\n".join([
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}", "ScaledBorderAndShadow: yes", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
        "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Big,{font},260,&H0000E5FF,&H0000E5FF,&H00000000,&H64000000,0,0,0,0,100,100,4,0,1,12,4,5,60,60,0,1",
        f"Style: Small,{font},84,&H00FFFFFF,&H00FFFFFF,&H00B43CFF,&H00B43CFF,0,0,0,0,100,100,2,0,3,16,0,2,60,60,{H // 2 - 300},1",
        "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        f"Dialogue: 1,0:00:00.00,{_ts(dur)},Big,,0,0,0,,{{\\fscx60\\fscy60\\t(0,220,\\fscx100\\fscy100)}}{_esc(big)}",
        f"Dialogue: 1,0:00:00.20,{_ts(dur)},Small,,0,0,0,,{{\\fad(150,0)}}{_esc(small)}",
    ]) + "\n"


def _rank_ass(cfg: dict, n: int, dur: float) -> str:
    r = cfg["render"]
    W, H, font = r["width"], r["height"], r["font"]
    return "\n".join([
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}", "ScaledBorderAndShadow: yes", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
        "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Rank,{font},300,&H0000E5FF,&H0000E5FF,&H00000000,&H64000000,0,0,0,0,100,100,2,0,1,14,5,5,0,0,0,1",
        f"Style: Tag,{font},70,&H00FFFFFF,&H00FFFFFF,&H00B43CFF,&H00B43CFF,0,0,0,0,100,100,3,0,3,14,0,9,40,40,{r['video_top'] + 20},1",
        "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        f"Dialogue: 5,0:00:00.00,0:00:01.60,Rank,,0,0,0,,{{\\fscx150\\fscy150\\t(0,200,\\fscx100\\fscy100)\\fad(0,250)}}#{n}",
        f"Dialogue: 5,0:00:01.60,{_ts(dur)},Tag,,0,0,0,,#{n}",
    ]) + "\n"


def _render(lang: str, clips: list, cfg: dict, out: Path) -> float:
    r, e = cfg["render"], cfg.get("enhance") or {}
    W, H, fps = r["width"], r["height"], 30
    voice = (e.get("voices") or {}).get(lang, "es-MX-JorgeNeural" if lang == "ES" else "en-US-AndrewNeural")
    fontsdir = ROOT / r["fontsdir"]
    T = TXT[lang]
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        segs = []
        # tarjeta de entrada
        idur = tts(T["intro"], voice, td / "intro.mp3")
        cdur = max(2.8, idur + 0.5)
        (td / "in.ass").write_text(_card_ass(cfg, T["title"], T["sub"], cdur))
        run(["ffmpeg", "-hide_banner", "-y", "-f", "lavfi", "-i", f"color=c=0x1a0b2e:s={W}x{H}:r={fps}:d={cdur:.2f}",
             "-i", str(td / "intro.mp3"), "-filter_complex",
             f"[0:v]ass={td / 'in.ass'}:fontsdir={fontsdir},format=yuv420p[v];"
             f"[1:a]aformat=sample_rates=48000:channel_layouts=stereo,adelay=150|150,apad=whole_dur={cdur:.2f}[a]",
             "-map", "[v]", "-map", "[a]", "-t", f"{cdur:.2f}", "-c:v", "libx264", "-preset", r["preset"], "-crf", str(r["crf"]),
             "-c:a", "aac", "-ar", "48000", str(td / "s0.mp4")], timeout=300)
        segs.append(td / "s0.mp4")
        # #3, #2, #1 (los clips llegan ordenados de mejor a peor)
        for n, row in zip((3, 2, 1), list(reversed(clips))):
            src = EDITS_DIR / lang / f"{row['id']}_{lang}.mp4"
            m = ffprobe(src)
            ndur = tts(T["n"][n], voice, td / f"n{n}.mp3")
            (td / f"r{n}.ass").write_text(_rank_ass(cfg, n, m["duration"]))
            a_in = "[0:a]aformat=sample_rates=48000:channel_layouts=stereo" if m["has_audio"] else \
                f"anullsrc=r=48000:cl=stereo,atrim=0:{m['duration']:.2f}"
            run(["ffmpeg", "-hide_banner", "-y", "-i", str(src), "-i", str(td / f"n{n}.mp3"), "-filter_complex",
                 f"[0:v]fps={fps},scale={W}:{H},setsar=1,ass={td / f'r{n}.ass'}:fontsdir={fontsdir},format=yuv420p[v];"
                 f"{a_in},volume='if(between(t,0,{ndur + 0.2:.2f}),0.25,1)':eval=frame[o];"
                 f"[1:a]aformat=sample_rates=48000:channel_layouts=stereo,adelay=100|100,volume=1.6[n];"
                 f"[o][n]amix=inputs=2:normalize=0:duration=first[a]",
                 "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", r["preset"], "-crf", str(r["crf"]),
                 "-c:a", "aac", "-ar", "48000", str(td / f"s{4 - n}.mp4")], timeout=600)
            segs.append(td / f"s{4 - n}.mp4")
        # tarjeta final
        odur = tts(T["outro"], voice, td / "outro.mp3")
        edur = max(2.8, odur + 0.6)
        (td / "end.ass").write_text(_card_ass(cfg, "?", T["end"], edur))
        run(["ffmpeg", "-hide_banner", "-y", "-f", "lavfi", "-i", f"color=c=0x1a0b2e:s={W}x{H}:r={fps}:d={edur:.2f}",
             "-i", str(td / "outro.mp3"), "-filter_complex",
             f"[0:v]ass={td / 'end.ass'}:fontsdir={fontsdir},format=yuv420p[v];"
             f"[1:a]aformat=sample_rates=48000:channel_layouts=stereo,adelay=150|150,apad=whole_dur={edur:.2f}[a]",
             "-map", "[v]", "-map", "[a]", "-t", f"{edur:.2f}", "-c:v", "libx264", "-preset", r["preset"], "-crf", str(r["crf"]),
             "-c:a", "aac", "-ar", "48000", str(td / "s4.mp4")], timeout=300)
        segs.append(td / "s4.mp4")
        ins, chain = [], ""
        for i, s in enumerate(segs):
            ins += ["-i", str(s)]
            chain += f"[{i}:v][{i}:a]"
        run(["ffmpeg", "-hide_banner", "-y", *ins, "-filter_complex",
             f"{chain}concat=n={len(segs)}:v=1:a=1[v][a0];[a0]loudnorm=I=-14:TP=-1.5:LRA=11[a]",
             "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", r["preset"], "-crf", str(r["crf"]),
             "-pix_fmt", "yuv420p", "-profile:v", "high", "-c:a", "aac", "-b:a", "160k", "-ar", "48000",
             "-movflags", "+faststart", str(out)], timeout=900)
    return ffprobe(out)["duration"]


def build_top3(force: bool = False) -> str | None:
    cfg = settings()
    t = cfg.get("top3") or {}
    if not force and not _due(t.get("every_hours", 72)):
        return None
    con = db()
    clips = pick(con, cfg)
    if len(clips) < 3:
        print(f"[top3] solo {len(clips)} clips elegibles; se reintenta en el próximo ciclo")
        return None
    tid = "TOP3_" + now_utc().strftime("%Y%m%d%H%M")
    dur = 0.0
    for lang in ("ES", "EN"):
        dur = _render(lang, clips, cfg, EDITS_DIR / lang / f"{tid}_{lang}.mp4")
    handles = ", ".join("@" + (c["creator_handle"] or "").lstrip("@") for c in clips)
    story = False
    for c in clips:
        try:
            story = story or bool(json.loads((DECISIONS_DIR / f"{c['id']}.json").read_text()).get("story"))
        except Exception:
            pass
    tags = ["GTA6", "GTAVI", "GTAVIClips", "Top3"]
    dec = {"id": tid, "verdict": "approve", "spoiler_level": 0, "story": story, "operator_safe": not story,
           "reason": "top3", "pillar": "Top 3", "priority": True, "trim": [0, round(dur, 2)],
           "hook": {"ES": "TOP 3", "EN": "TOP 3"}, "parts": [c["id"] for c in clips],
           "credit": {"ES": f"🎥: {handles}", "EN": f"🎥: {handles}"},
           "copy": {L: {"title": TXT[L]["ytitle"], "caption": TXT[L]["caption"], "hashtags": tags} for L in ("ES", "EN")}}
    (DECISIONS_DIR / f"{tid}.json").write_text(json.dumps(dec, ensure_ascii=False, indent=1))
    now = iso()
    con.execute(
        "INSERT OR REPLACE INTO clips (id, source, url, creator, creator_handle, platform, lang, title, views, created_at,"
        " duration, status, reason, test, raw_path, meta_json, discovered_at, updated_at)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (tid, "top3", " ".join(c["url"] or "" for c in clips), "Top 3", "varios", "", "es", "Top 3",
         10 ** 9, now, dur, "rendered", "top3", 0, "", json.dumps({"parts": dec["parts"]}), now, now))
    con.commit()
    LAST.write_text(now)
    print(f"[top3] {tid}: {len(clips)} clips, {dur:.0f} s")
    return tid
