"""Prechequeo antes de cada ciclo. Imprime una línea por check (sin contenido de clips) y sale con
código 0 si todo OK, 1 si hay un fallo que impide publicar (Upload-Post) y 2 si solo hay avisos."""
import json, os, shutil, subprocess, sys, time
sys.path.insert(0, "/home/user/GTA6_AUTO_CLIPPER")
os.chdir("/home/user/GTA6_AUTO_CLIPPER")
import requests
from clipper.core import settings
from clipper import twitch_api

cfg = settings()
fatal, warn, out = False, False, []


def check(name, ok, detail, is_fatal=False):
    global fatal, warn
    out.append(f"{'OK ' if ok else ('ERR' if is_fatal else 'AVS')} {name}: {detail}")
    if not ok:
        fatal |= is_fatal
        warn |= not is_fatal


# disco
free_gb = shutil.disk_usage("/home/user").free / 1e9
check("disco", free_gb > 3, f"{free_gb:.1f} GB libres", is_fatal=free_gb < 1)

# Upload-Post: API viva y 6 cuentas conectadas
p = cfg["publish"]
try:
    r = requests.get(f"{p['api_base']}/api/uploadposts/users",
                     headers={"Authorization": f"Apikey {os.environ.get(p['api_key_env'], 'proxy-injected')}"}, timeout=30)
    profs = {x.get("username"): {k for k, v in (x.get("social_accounts") or {}).items() if v} for x in r.json().get("profiles", [])}
    missing = [f"{lang}:{pl}" for lang, prof in p["profiles"].items() for pl in p["platforms"] if pl not in profs.get(prof, set())]
    check("upload-post", r.ok and not missing, f"HTTP {r.status_code}, " + ("6/6 cuentas" if not missing else f"desconectadas {missing}"),
          is_fatal=not r.ok)
except Exception as ex:
    check("upload-post", False, f"sin respuesta ({str(ex)[:80]})", is_fatal=True)

# Twitch Helix
try:
    j = twitch_api.get(cfg, "streams", {"game_id": cfg["twitch_api"]["game_id"], "first": 5})
    check("twitch", "data" in j, f"{len(j.get('data', []))} streams de muestra")
except Exception as ex:
    check("twitch", False, f"error ({str(ex)[:80]})")

# herramientas
for tool in ("ffmpeg", "yt-dlp", "claude"):
    check(tool, shutil.which(tool) is not None, "instalado" if shutil.which(tool) else "NO encontrado", is_fatal=tool == "ffmpeg")
try:
    import faster_whisper  # noqa: F401
    check("whisper", True, "importa")
except Exception as ex:
    check("whisper", False, str(ex)[:80])

# cola de publicación: algún post vencido que no se haya enviado (programado hace >2 h y sin request_id)
import sqlite3
c = sqlite3.connect("state/clipper.db")
stuck = c.execute("select count(*) from posts where status='scheduled' and request_id is null").fetchone()[0]
check("cola", stuck == 0, f"{stuck} posts programados sin request_id")

print("\n".join(out))
sys.exit(1 if fatal else (2 if warn else 0))
