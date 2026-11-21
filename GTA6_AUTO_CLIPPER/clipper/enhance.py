"""Edición propia sobre el clip ya renderizado (contenido original, no un simple re-subido):

1. Repetición comentada: el momento clave otra vez, a cámara lenta, con zoom sobre el detalle, un aro que lo
   señala, la etiqueta REPETICIÓN/REPLAY y un remate escrito.
2. Voz en off (TTS neuronal) en ES/EN: frase de gancho al inicio y comentario sobre la repetición; el audio
   original baja mientras habla la voz.

Campos opcionales de la decisión (tiempos del clip ORIGINAL, box en fracciones del fotograma original):
  "replay": {"start": 12.0, "end": 14.5, "box": [x, y, w, h], "text": {"ES": "...", "EN": "..."}}
  "vo": {"intro": {"ES": "...", "EN": "..."}, "outro": {"ES": "...", "EN": "..."}}
Si faltan, se usan valores por defecto (últimos segundos del recorte y el gancho como intro), para que todos los
clips lleven edición propia. Si algo falla, se conserva el render base.
"""
from __future__ import annotations

import asyncio
import os
import ssl
import tempfile
from pathlib import Path

from .core import ROOT, ffprobe, run

TAG = {"ES": "REPETICIÓN", "EN": "REPLAY"}


def tts(text: str, voice: str, out: Path) -> float:
    """Neural TTS (edge-tts). Uses the session's CA bundle when behind the proxy. Returns seconds."""
    import edge_tts
    import edge_tts.communicate as com
    ca = os.environ.get("SSL_CERT_FILE") or os.environ.get("REQUESTS_CA_BUNDLE") or "/root/.ccr/ca-bundle.crt"
    if ca and os.path.exists(ca):
        com._SSL_CTX = ssl.create_default_context(cafile=ca)
    asyncio.run(edge_tts.Communicate(text, voice, rate="+6%").save(str(out)))
    return ffprobe(out)["duration"]


def _esc(t: str) -> str:
    return (t or "").replace("\\", "").replace("{", "(").replace("}", ")").replace("\n", " ")


def _ring(r: int) -> str:
    k = round(r * 0.5523)
    return (f"m 0 {-r} b {k} {-r} {r} {-k} {r} 0 b {r} {k} {k} {r} 0 {r} "
            f"b {-k} {r} {-r} {k} {-r} 0 b {-r} {-k} {-k} {-r} 0 {-r}")


def _replay_ass(lang: str, text: str, dur: float, cfg: dict, ring: bool) -> str:
    r = cfg["render"]
    W, H, font = r["width"], r["height"], r["font"]
    out = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}", "ScaledBorderAndShadow: yes", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
        "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Tag,{font},70,&H00FFFFFF,&H00FFFFFF,&H00B43CFF,&H00B43CFF,0,0,0,0,100,100,3,0,3,14,0,8,60,60,170,1",
        f"Style: Punch,{font},{r.get('sub_size', 96)},&H0000E5FF,&H0000E5FF,&H00000000,&H78000000,0,0,0,0,100,100,1,0,1,8,3,2,60,60,330,1",
        f"Style: Ring,{font},20,&HFF000000,&HFF000000,&H003C3CFF,&H00000000,0,0,0,0,100,100,0,0,1,12,0,5,0,0,0,1",
        "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        f"Dialogue: 2,0:00:00.00,{_ts(dur)},Tag,,0,0,0,,{{\\fad(120,0)}}{TAG[lang]}",
    ]
    if ring:
        out.append(f"Dialogue: 1,0:00:00.15,{_ts(dur)},Ring,,0,0,0,,{{\\an5\\pos({W // 2},{H // 2})"
                   f"\\fscx140\\fscy140\\t(0,260,\\fscx100\\fscy100)\\p1}}{_ring(int(W * 0.30))}{{\\p0}}")
    if text:
        out.append(f"Dialogue: 2,0:00:00.30,{_ts(dur)},Punch,,0,0,0,,{{\\fscx80\\fscy80\\t(0,160,\\fscx100\\fscy100)}}"
                   f"{_esc(text).upper()}")
    return "\n".join(out) + "\n"


def _ts(t: float) -> str:
    t = max(0.0, t)
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def _crop_for(box, sw: int, sh: int, zoom: float) -> tuple[int, int, int, int]:
    """9:16 crop window around the box (or the centre), clamped to the source frame."""
    if box:
        x, y, w, h = box
        cx, cy = (x + w / 2) * sw, (y + h / 2) * sh
        ch = max(h * sh, w * sw * 16 / 9) * 1.25
    else:
        cx, cy = sw / 2, sh / 2
        ch = sh / zoom
    ch = min(max(ch, sh * 0.42), sh)
    cw = min(ch * 9 / 16, sw)
    ch = cw * 16 / 9
    cw, ch = int(cw) // 2 * 2, int(ch) // 2 * 2
    x0 = int(min(max(cx - cw / 2, 0), sw - cw))
    y0 = int(min(max(cy - ch / 2, 0), sh - ch))
    return cw, ch, x0, y0


def enhance(base: Path, raw: Path, dec: dict, lang: str, row, cfg: dict) -> bool:
    """Replace `base` (rendered clip) with base + commented replay + voice-over. Returns True if applied."""
    from .render import _pixelate_src, _between
    e = cfg.get("enhance") or {}
    if not (e.get("replay", True) or e.get("vo", True)):
        return False
    r = cfg["render"]
    W, H = r["width"], r["height"]
    bmeta, smeta = ffprobe(base), ffprobe(raw)
    bdur, fps = bmeta["duration"], bmeta["fps"] or 30
    t0, t1 = dec["trim"][0], min(dec["trim"][1], smeta["duration"])
    rep = dict(dec.get("replay") or {})
    do_rep = e.get("replay", True)
    if do_rep and not rep:                         # por defecto: los últimos segundos del recorte
        rep = {"start": max(t0, t1 - 3.2), "end": max(t0 + 0.5, t1 - 0.2)}
    rs, re_ = (max(t0, float(rep.get("start", t0))), min(t1, float(rep.get("end", t1)))) if do_rep else (0, 0)
    re_ = min(re_, rs + float(e.get("replay_max_seconds", 3.5)))
    do_rep = do_rep and re_ - rs >= 0.6
    speed = float(e.get("replay_speed", 0.5))
    vo = dec.get("vo") or {}
    intro_t = ((vo.get("intro") or {}).get(lang) or dec.get("hook", {}).get(lang) or "") if e.get("vo", True) else ""
    outro_t = ((vo.get("outro") or {}).get(lang) or (rep.get("text") or {}).get(lang) or "") if e.get("vo", True) else ""
    voice = (e.get("voices") or {}).get(lang, "es-MX-JorgeNeural" if lang == "ES" else "en-US-AndrewNeural")
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        ia = oa = None
        idur = odur = 0.0
        try:
            if intro_t:
                idur, ia = tts(intro_t, voice, td / "intro.mp3"), td / "intro.mp3"
            if outro_t:
                odur, oa = tts(outro_t, voice, td / "outro.mp3"), td / "outro.mp3"
        except Exception as ex:                     # sin voz: seguimos solo con la repetición
            print(f"[enhance] TTS falló ({str(ex)[:120]})")
            ia = oa = None
            idur = odur = 0.0
        if not do_rep and not (ia or oa):
            return False
        rdur = (re_ - rs) / speed if do_rep else 0.0
        pad = max(0.0, (odur + 0.6) - rdur) if (do_rep and oa) else 0.0
        total = bdur + rdur + pad
        inputs = ["-i", str(base)]
        if do_rep:
            inputs += ["-ss", f"{rs:.2f}", "-to", f"{re_:.2f}", "-i", str(raw)]
        idx = {}
        n = 1 + (1 if do_rep else 0)
        if ia:
            inputs += ["-i", str(ia)]
            idx["ia"] = n
            n += 1
        if oa:
            inputs += ["-i", str(oa)]
            idx["oa"] = n
        g = [f"[0:v]setpts=PTS-STARTPTS,fps={fps},scale={W}:{H},setsar=1,format=yuv420p[bv]"]
        g.append(f"[0:a]asetpts=PTS-STARTPTS,aformat=sample_rates=48000:channel_layouts=stereo[ba]" if bmeta["has_audio"]
                 else f"anullsrc=r=48000:cl=stereo,atrim=0:{bdur:.3f}[ba]")
        if do_rep:
            pix, src = _pixelate_src(dec, smeta, rs, re_ - rs)
            pix = pix.replace("[0:v]", "[1:v]")
            src = "[1:v]" if src == "[0:v]" else src
            cw, ch, x0, y0 = _crop_for(rep.get("box"), smeta["width"] or 1920, smeta["height"] or 1080,
                                       float(e.get("replay_zoom", 1.5)))
            rass = td / "replay.ass"
            rass.write_text(_replay_ass(lang, (rep.get("text") or {}).get(lang, ""), rdur + pad, cfg, ring=True))
            fontsdir = ROOT / r["fontsdir"]
            tp = f",tpad=stop_mode=clone:stop_duration={pad:.2f}" if pad > 0 else ""
            g.append((pix + ";" if pix else "") +
                     f"{src}setpts=(PTS-STARTPTS)/{speed},crop={cw}:{ch}:{x0}:{y0},scale={W}:{H},fps={fps}{tp},"
                     f"eq=saturation=1.15:contrast=1.05,setsar=1,format=yuv420p,ass={rass}:fontsdir={fontsdir}[rv]")
            muted = bool(_between(dec.get("bleep") or [], rs, re_ - rs))   # no repetir palabras pitadas
            if smeta["has_audio"] and not muted:
                g.append(f"[1:a]asetpts=PTS-STARTPTS,atempo={speed},volume=0.55,"
                         f"aformat=sample_rates=48000:channel_layouts=stereo,apad=whole_dur={rdur + pad:.3f}[ra]")
            else:
                g.append(f"anullsrc=r=48000:cl=stereo,atrim=0:{rdur + pad:.3f}[ra]")
            g.append("[bv][ba][rv][ra]concat=n=2:v=1:a=1[v][am]")
        else:
            g.append("[bv]null[v];[ba]anull[am]")
        duck = float(e.get("duck", 0.25))
        i0, i1 = 0.15, 0.15 + idur
        o0 = (bdur + 0.25) if do_rep else max(0.0, bdur - odur - 0.3)
        o1 = o0 + odur
        spans = [f"between(t,{i0:.2f},{i1:.2f})"] if ia else []
        spans += [f"between(t,{o0:.2f},{o1:.2f})"] if oa else []
        cond = "+".join(spans) or "0"
        mix, k = ["[ad]"], 1
        g.append(f"[am]volume='if({cond},{duck},1)':eval=frame[ad]")
        for name, start in (("ia", i0), ("oa", o0)):
            if name in idx:
                ms = int(start * 1000)
                g.append(f"[{idx[name]}:a]aformat=sample_rates=48000:channel_layouts=stereo,"
                         f"adelay={ms}|{ms},volume=1.6[{name}]")
                mix.append(f"[{name}]")
                k += 1
        g.append(f"{''.join(mix)}amix=inputs={k}:normalize=0:duration=first,"
                 f"loudnorm=I=-14:TP=-1.5:LRA=11[a]")
        out = td / "out.mp4"
        cmd = ["ffmpeg", "-hide_banner", "-y", *inputs, "-filter_complex", ";".join(g), "-map", "[v]", "-map", "[a]",
               "-t", f"{total:.2f}", "-c:v", "libx264", "-preset", r["preset"], "-crf", str(r["crf"]),
               "-pix_fmt", "yuv420p", "-profile:v", "high", "-c:a", "aac", "-b:a", "160k", "-ar", "48000",
               "-movflags", "+faststart", str(out)]
        run(cmd, timeout=900)
        os.replace(out, base)
    return True
