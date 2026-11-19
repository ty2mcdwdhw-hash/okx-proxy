"""Importador de bandeja: clips ya recortados y revisados que llegan por git.

Cada carpeta /home/user/okx-proxy/GTA6_AUTO_CLIPPER/inbox/<ID>/ trae:
  clip.mp4       fragmento ya recortado
  decision.json  esquema de REVIEWER.md (trim relativo al fragmento)
  meta.json      creator, creator_handle, lang, title, views, priority (opcionales: platform, url)
Se inserta el clip como 'approved', se copian vídeo y decisión al estado local y se hace
`git rm -r` + commit de la carpeta en el repo, para que el push del ciclo la vacíe en GitHub.
ESCUDO DEL OPERADOR: la salida solo lleva IDs y conteos, nunca títulos ni copy.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

from .core import DECISIONS_DIR, RAW_DIR, db, ffprobe, iso

REPO = Path(os.environ.get("GTA6_REPO", "/home/user/okx-proxy"))  # GTA6_REPO solo para pruebas
INBOX = REPO / "GTA6_AUTO_CLIPPER" / "inbox"
ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,80}$")
# si el clip ya existe en uno de estos estados, no se pisan su vídeo ni su decisión
LOCKED = ("rendered", "published", "takedown")


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True)


def _problems(cid: str, folder: Path, dec: dict, meta: dict) -> list[str]:
    out = []
    if not (folder / "clip.mp4").is_file():
        out.append("falta clip.mp4")
    if dec.get("id", cid) != cid:
        out.append("id de decision.json no coincide con la carpeta")
    if dec.get("verdict") != "approve" or dec.get("spoiler_level", 0) != 0:
        out.append("decision no es approve con spoiler_level 0")
    for k in ("trim", "hook", "copy"):
        if k not in dec:
            out.append(f"falta {k} en decision.json")
    for lang in ("ES", "EN"):
        if lang not in (dec.get("copy") or {}):
            out.append(f"falta copy {lang}")
    for k in ("creator", "creator_handle", "lang"):
        if not meta.get(k):
            out.append(f"falta {k} en meta.json")
    return out


def import_inbox() -> dict:
    stats = {"importados": 0, "ya_existian": 0, "invalidos": 0}
    if not INBOX.is_dir():
        return stats
    con = db()
    removed: list[str] = []
    for folder in sorted(p for p in INBOX.iterdir() if p.is_dir()):
        cid = folder.name
        try:
            if not ID_RE.match(cid):
                raise ValueError("ID de carpeta no válido")
            dec = json.loads((folder / "decision.json").read_text())
            meta = json.loads((folder / "meta.json").read_text())
            probs = _problems(cid, folder, dec, meta)
            if probs:
                raise ValueError("; ".join(probs))
            dur = ffprobe(folder / "clip.mp4")["duration"]
        except Exception as ex:  # se deja la carpeta en su sitio para corregirla
            stats["invalidos"] += 1
            print(f"[inbox] {cid}: inválido ({str(ex)[:200]})")
            continue

        dec["id"] = cid
        if meta.get("priority") and "priority" not in dec:
            dec["priority"] = True
        raw = RAW_DIR / f"{cid}.mp4"
        row = con.execute("SELECT status FROM clips WHERE id=?", (cid,)).fetchone()
        if row is None:
            now = iso()
            con.execute(
                "INSERT INTO clips (id, source, url, creator, creator_handle, platform, lang, title, views,"
                " created_at, duration, status, reason, test, raw_path, meta_json, discovered_at, updated_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (cid, "inbox", meta.get("url", ""), meta["creator"], meta["creator_handle"],
                 meta.get("platform", ""), meta["lang"], meta.get("title", ""), int(meta.get("views") or 0),
                 now, dur, "approved", dec.get("reason", "inbox"), 0, str(raw),
                 json.dumps(meta, ensure_ascii=False), now, now))
            con.commit()
            stats["importados"] += 1
            locked = False
        else:
            stats["ya_existian"] += 1
            locked = row["status"] in LOCKED
        if not locked:
            shutil.copyfile(folder / "clip.mp4", raw)
            (DECISIONS_DIR / f"{cid}.json").write_text(json.dumps(dec, ensure_ascii=False, indent=1))
        print(f"[inbox] {cid}: {'importado' if row is None else 'ya existía' + (' (sin tocar)' if locked else '')}")

        rel = folder.relative_to(REPO)
        if _git("rm", "-r", "-q", "--", str(rel)).returncode == 0:
            removed.append(str(rel))
        shutil.rmtree(folder, ignore_errors=True)  # restos no versionados
    if removed:
        p = _git("-c", "user.name=Claude", "-c", "user.email=noreply@anthropic.com", "commit", "-q",
                 "-m", "GTA6_AUTO_CLIPPER: inbox imported\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>",
                 "--", *removed)
        if p.returncode != 0:
            print(f"[inbox] aviso: commit falló ({p.stderr.strip()[:200]})")
    return stats
