#!/usr/bin/env bash
# Una iteración completa del ciclo, sin depender de la conversación de Claude.
# discover/process -> revisión con un Claude aislado (claude -p) -> decide/render/publish -> commit/push.
# ESCUDO DEL OPERADOR: nada de contenido de clips va al log resumido (state/autopilot.log).
set -u
cd /home/user/GTA6_AUTO_CLIPPER || exit 1
LOG=state/autopilot.log
ts() { TZ=America/Lima date "+%d/%m %H:%M"; }
say() { echo "[$(ts)] $*" >> "$LOG"; }

say "ciclo: inicio"
timeout 40m python3 -m clipper cycle > state/cycle.log 2>&1 || say "ciclo: cycle terminó con código $?"
python3 -c "import json,glob; p=sorted({json.load(open(f)).get('pillar','') for f in glob.glob('state/decisions/*.json') if json.load(open(f)).get('verdict')=='approve'}); print('PILLARS:', '; '.join(p))" > state/pillars.txt 2>/dev/null

PENDING=$(python3 -c "import sqlite3;c=sqlite3.connect('state/clipper.db');print(c.execute(\"select count(*) from clips where status='packet' and id not like 'LOCAL_%'\").fetchone()[0])")
say "ciclo: pendientes de revisión=$PENDING"

if [ "$PENDING" -gt 0 ]; then
  MAX=3
  [ "$(TZ=America/Lima date +%Y%m%d%H)" -ge 2026111900 ] && MAX=4
  PROMPT="$(sed "s/{MAX}/$MAX/g" REVIEW_AGENT.md)

INDICACIONES DEL CICLO: lee state/pillars.txt y los hooks aprobados para no repetir temas; varía temas; aplica la
censura pixelada ([[palabra]], bleep, pixelate) en vez de rechazar por lenguaje o texto en pantalla; marca
\"priority\": true solo en momentos claramente virales; IGNORA los clips cuyo id empiece por LOCAL_ (no los toques).
Trabaja solo dentro de /home/user/GTA6_AUTO_CLIPPER y el directorio temporal /tmp/autopilot_review."
  mkdir -p /tmp/autopilot_review
  # Claude aislado: entorno mínimo (sin variables de la sesión remota), así no aparece en el chat del operador.
  ( cd /home/user/GTA6_AUTO_CLIPPER && timeout 30m env -i PATH="$PATH" HOME="$HOME" \
      HTTPS_PROXY="${HTTPS_PROXY:-}" HTTP_PROXY="${HTTP_PROXY:-}" NO_PROXY="${NO_PROXY:-}" \
      NODE_EXTRA_CA_CERTS="${NODE_EXTRA_CA_CERTS:-}" SSL_CERT_FILE="${SSL_CERT_FILE:-}" \
      REQUESTS_CA_BUNDLE="${REQUESTS_CA_BUNDLE:-}" ANTHROPIC_BASE_URL="${ANTHROPIC_BASE_URL:-}" \
      claude -p "$PROMPT" --permission-mode acceptEdits \
        --allowedTools "Bash" "Read" "Write" "Edit" "Glob" "Grep" \
      > state/review_last.txt 2>&1 ) || say "revisión: claude -p terminó con código $?"
  # el resumen del revisor ya viene sin spoilers (formato de REVIEW_AGENT.md); guardamos solo las filas de aprobados
  grep -E "^\s*[-*|]?\s*\`?(TW_|KK_|YT_|LOCAL_)" state/review_last.txt | head -8 | sed "s/^/[$(ts)]   aprobado: /" >> "$LOG"
fi

python3 -m clipper decide > state/decide.log 2>&1
python3 -m clipper render > state/render.log 2>&1
python3 -m clipper publish > state/publish.log 2>&1
say "publicación: $(tail -1 state/decide.log) | posts=$(grep -c -- '-> ' state/publish.log) errores=$(grep -ci error state/publish.log) render_fail=$(grep -c FAILED state/render.log)"
python3 -m clipper purge-raw > /dev/null 2>&1

git add -A > /dev/null 2>&1
git -c user.name="Claude" -c user.email="noreply@anthropic.com" commit -q -m "Autopilot cycle" > /dev/null 2>&1
git archive HEAD | tar -x -C /home/user/okx-proxy/GTA6_AUTO_CLIPPER
( cd /home/user/okx-proxy && git add -A GTA6_AUTO_CLIPPER > /dev/null 2>&1 && \
  git -c user.name="Claude" -c user.email="noreply@anthropic.com" commit -q -m "GTA6_AUTO_CLIPPER: autopilot cycle

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_012s2xZQegwGcgHuj7bDPLDm" > /dev/null 2>&1; \
  for i in 1 2 3; do git push -q origin claude/gallant-bardeen-s7mk6r > /dev/null 2>&1 && break; sleep $((i*10)); done )
say "ciclo: fin"
