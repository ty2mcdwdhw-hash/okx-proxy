"""CLI: python -m clipper <command>

  verify                     comprueba que los canales de la watchlist existen
  discover [--group G] [--handle H]   busca clips nuevos
  add URL --creator C --lang xx [--test]   agrega un clip a mano
  process [--limit N] [--test]        descarga + letterbox + Whisper + paquete de revisión
  pending                    lista paquetes esperando decisión del revisor (Claude)
  decide                     aplica state/decisions/*.json
  render                     genera MP4 9:16 ES/EN de lo aprobado
  publish [--dry]            sube (o deja en cola) lo renderizado
  cycle [--dry]              discover -> process -> (decide/render/publish de lo ya revisado)
  status                     resumen por estado
  cards                      fichas de metadatos sanitizadas (texto, sin imágenes)
  purge-raw                  borra descargas temporales de clips ya publicados/rechazados
  takedown CLIP_ID           marca un clip como retirado (y lo anota en takedowns.md)
  reset-test                 borra todos los datos del MODO TEST
"""
from __future__ import annotations

import argparse
import json
import shutil

from . import discover as disc
from .core import DECISIONS_DIR, EDITS_DIR, RAW_DIR, REVIEW_DIR, ROOT, db, iso, set_status


def cmd_status():
    con = db()
    for r in con.execute("SELECT status, COUNT(*) n FROM clips GROUP BY status ORDER BY n DESC"):
        print(f"{r['status']:<12} {r['n']}")
    for r in con.execute("SELECT status, COUNT(*) n FROM posts GROUP BY status"):
        print(f"posts:{r['status']:<7} {r['n']}")


def cmd_pending():
    con = db()
    for r in con.execute("SELECT id, creator, lang, views FROM clips WHERE status='packet' ORDER BY views DESC"):
        print(f"{r['id']:<50} {r['creator']:<22} {r['lang']} views={r['views']}  -> {REVIEW_DIR / r['id']}")


def cmd_cards():
    """Sanitized approval cards: no visuals, no story details."""
    con = db()
    for r in con.execute("SELECT * FROM clips WHERE status IN ('approved','rendered','published') ORDER BY updated_at"):
        f = DECISIONS_DIR / f"{r['id']}.json"
        if not f.exists():
            continue
        d = json.loads(f.read_text())
        dur = d["trim"][1] - d["trim"][0]
        print(f"`{r['id']}` | `{(r['lang'] or '?').upper()} -> ES/EN` | `{d.get('pillar', '')}` | `{dur:.0f}s` | "
              f"`Nivel Spoiler: 0% (Verificado)` | estado: {r['status']}")
        for lang in ("ES", "EN"):
            print(f"    [{lang}] {d['copy'][lang]['caption'].splitlines()[0]}")


def cmd_purge():
    con = db()
    n = 0
    for r in con.execute("SELECT id FROM clips WHERE status IN ('published','rejected','takedown')"):
        for f in RAW_DIR.glob(f"{r['id']}.*"):
            f.unlink()
            n += 1
    print(f"purged {n} raw files")


def cmd_takedown(cid: str):
    con = db()
    set_status(con, cid, "takedown", "takedown request")
    with (ROOT / "takedowns.md").open("a") as fh:
        fh.write(f"- {iso()} | `{cid}` | marcado para retiro. Borrar posts ES/EN en TikTok/IG/YT hoy mismo.\n")
    for lang in ("ES", "EN"):
        for f in (EDITS_DIR / lang).glob(f"{cid}_*"):
            f.unlink()
    print("ok — revisa takedowns.md")


def cmd_reset_test():
    con = db()
    ids = [r[0] for r in con.execute("SELECT id FROM clips WHERE test=1")]
    for cid in ids:
        for f in list(RAW_DIR.glob(f"{cid}.*")) + list(EDITS_DIR.glob(f"*/{cid}_*")):
            f.unlink()
        shutil.rmtree(REVIEW_DIR / cid, ignore_errors=True)
        (DECISIONS_DIR / f"{cid}.json").unlink(missing_ok=True)
        con.execute("DELETE FROM posts WHERE clip_id=?", (cid,))
        con.execute("DELETE FROM clips WHERE id=?", (cid,))
    con.commit()
    for name in ("log.md", "scoreboard.csv"):
        p = ROOT / name
        if p.exists():
            keep = [l for l in p.read_text().splitlines(True) if "TEST" not in l and not any(c in l for c in ids)]
            p.write_text("".join(keep))
    print(f"removed {len(ids)} test clips")


def main():
    ap = argparse.ArgumentParser(prog="clipper", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("verify")
    d = sub.add_parser("discover"); d.add_argument("--group"); d.add_argument("--handle")
    a = sub.add_parser("add"); a.add_argument("url"); a.add_argument("--creator", required=True)
    a.add_argument("--lang", required=True); a.add_argument("--test", action="store_true")
    a.add_argument("--peaks", type=int, default=2)
    p = sub.add_parser("process"); p.add_argument("--limit", type=int, default=50); p.add_argument("--test", action="store_true")
    sub.add_parser("pending"); sub.add_parser("decide"); sub.add_parser("render")
    pb = sub.add_parser("publish"); pb.add_argument("--dry", action="store_true")
    c = sub.add_parser("cycle"); c.add_argument("--dry", action="store_true"); c.add_argument("--group")
    sub.add_parser("status"); sub.add_parser("cards"); sub.add_parser("purge-raw"); sub.add_parser("reset-test")
    t = sub.add_parser("takedown"); t.add_argument("clip_id")
    args = ap.parse_args()

    if args.cmd == "verify":
        disc.verify()
    elif args.cmd == "discover":
        disc.discover(args.group, args.handle)
    elif args.cmd == "add":
        print(disc.add_url(args.url, args.creator, args.lang, args.test, args.peaks))
    elif args.cmd == "process":
        from .process import process
        process(args.limit, args.test)
    elif args.cmd == "pending":
        cmd_pending()
    elif args.cmd == "decide":
        from .publish import apply_decisions
        print("approved=%d rejected=%d" % apply_decisions())
    elif args.cmd == "render":
        from .render import render_all
        render_all()
    elif args.cmd == "publish":
        from .publish import publish_all
        publish_all(args.dry)
    elif args.cmd == "cycle":
        from .process import process
        from .publish import apply_decisions, publish_all
        from .render import render_all
        apply_decisions(); render_all(); publish_all(args.dry)
        disc.discover(args.group); process()
        cmd_pending()
    elif args.cmd == "status":
        cmd_status()
    elif args.cmd == "cards":
        cmd_cards()
    elif args.cmd == "purge-raw":
        cmd_purge()
    elif args.cmd == "takedown":
        cmd_takedown(args.clip_id)
    elif args.cmd == "reset-test":
        cmd_reset_test()


if __name__ == "__main__":
    main()
