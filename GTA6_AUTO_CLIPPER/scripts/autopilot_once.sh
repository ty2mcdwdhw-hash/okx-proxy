#!/usr/bin/env bash
# Una iteración completa del ciclo, sin depender de la conversación de Claude.
# discover/process -> revisión con un Claude aislado (claude -p) -> decide/render/publish -> commit/push.
# ESCUDO DEL OPERADOR: nada de contenido de clips va al log resumido (state/autopilot.log).
set -u
cd /home/user/GTA6_AUTO_CLIPPER || exit 1
LOG=state/autopilot.log
ts() { TZ=America/Lima date "+%d/%m %H:%M"; }
say() { echo "[$(ts)] $*" >> "$LOG"; }

REPO=/home/user/okx-proxy
BR=claude/gallant-bardeen-s7mk6r
# Propiedad: solo una sesión publica. Si en GitHub figura otra sesión como dueña, este piloto se apaga.
ME=$(cat state/owner.txt 2>/dev/null)
OWNER=$(cd "$REPO" && git fetch -q origin "$BR" 2>/dev/null && git show FETCH_HEAD:GTA6_AUTO_CLIPPER/state_snapshot/OWNER 2>/dev/null)
if [ -n "$ME" ] && [ -n "$OWNER" ] && [ "$OWNER" != "$ME" ]; then
  say "piloto: otra sesión tomó el control ($OWNER); me apago para no duplicar publicaciones"
  touch state/autopilot.disabled
  kill "$(cat state/autopilot.pid 2>/dev/null)" 2>/dev/null
  exit 0
fi

say "ciclo: inicio"
timeout 3m python3 scripts/preflight.py > state/preflight.txt 2>&1
PF=$?
say "prechequeo: $([ $PF -eq 0 ] && echo 'todo OK' || grep -E '^(ERR|AVS)' state/preflight.txt | tr '\n' ';')"
if [ $PF -eq 1 ] || [ $PF -eq 124 ]; then
  say "ciclo: saltado por fallo crítico en el prechequeo (no se publica a ciegas)"
  exit 0
fi
timeout 40m python3 -m clipper cycle > state/cycle.log 2>&1 || say "ciclo: cycle terminó con código $?"
python3 -c "import json,glob; p=sorted({json.load(open(f)).get('pillar','') for f in glob.glob('state/decisions/*.json') if json.load(open(f)).get('verdict')=='approve'}); print('PILLARS:', '; '.join(p))" > state/pillars.txt 2>/dev/null

PENDING=$(python3 -c "import sqlite3;c=sqlite3.connect('state/clipper.db');print(c.execute(\"select count(*) from clips where status='packet' and id not like 'LOCAL_%'\").fetchone()[0])")
say "ciclo: pendientes de revisión=$PENDING"

if [ "$PENDING" -gt 0 ]; then
  MAX=1   # 21/11: volumen bajo, solo el mejor clip del ciclo (o ninguno)
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

# bandeja: traer lo último de GitHub e importar clips ya recortados y revisados (inbox/<ID>/)
( cd "$REPO" && git fetch -q origin "$BR" && git merge -q --no-edit -X theirs FETCH_HEAD ) > /dev/null 2>&1
python3 -m clipper import-inbox > state/inbox.log 2>&1 || say "bandeja: import-inbox terminó con código $?"
grep -q "^inbox: importados=0 ya_existian=0 invalidos=0" state/inbox.log || say "bandeja: $(tail -1 state/inbox.log)"
python3 -m clipper decide > state/decide.log 2>&1
python3 -m clipper render > state/render.log 2>&1
# Top 3 cada 3 días (solo streamers hispanohablantes); queda como clip 'rendered' y se publica a continuación
python3 -m clipper top3 > state/top3.log 2>&1
grep -q "^\[top3\] TOP3_" state/top3.log && say "top3: $(grep -o 'TOP3_[0-9]*: .*' state/top3.log | tail -1)"
python3 -m clipper publish > state/publish.log 2>&1
say "publicación: $(tail -1 state/decide.log) | posts=$(grep -c -- '-> ' state/publish.log) errores=$(grep -ci error state/publish.log) render_fail=$(grep -c FAILED state/render.log)"
python3 -m clipper purge-raw > /dev/null 2>&1

# copia del estado en cada ciclo (para migrar de sesión sin perder nada)
mkdir -p state_snapshot/decisions
python3 -c "import sqlite3; s=sqlite3.connect('state/clipper.db'); d=sqlite3.connect('state_snapshot/clipper.db'); s.backup(d); d.close()"
cp -u state/decisions/*.json state_snapshot/decisions/ 2>/dev/null
cp state/pillars.txt state_snapshot/ 2>/dev/null
[ -n "$ME" ] && echo "$ME" > state_snapshot/OWNER
git add -A > /dev/null 2>&1; git add -f state_snapshot > /dev/null 2>&1
git -c user.name="Claude" -c user.email="noreply@anthropic.com" commit -q -m "Autopilot cycle" > /dev/null 2>&1
( cd "$REPO" && git fetch -q origin "$BR" && git merge -q --no-edit -X theirs FETCH_HEAD ) > /dev/null 2>&1
git archive HEAD | tar -x -C "$REPO/GTA6_AUTO_CLIPPER"
( cd "$REPO" && git add -A -f GTA6_AUTO_CLIPPER > /dev/null 2>&1 && \
  git -c user.name="Claude" -c user.email="noreply@anthropic.com" commit -q -m "GTA6_AUTO_CLIPPER: autopilot cycle

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
" > /dev/null 2>&1; \
  for i in 1 2 3; do git push -q origin claude/gallant-bardeen-s7mk6r > /dev/null 2>&1 && break; sleep $((i*10)); done )
say "ciclo: fin"
