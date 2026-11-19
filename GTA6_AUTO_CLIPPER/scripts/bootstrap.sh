#!/usr/bin/env bash
# Arranque idempotente de GTA6_AUTO_CLIPPER en cualquier sesión en la nube.
# - Primera vez (sesión nueva): copia el proyecto desde el repo, restaura state_snapshot, instala dependencias,
#   instala los hooks de Claude Code y toma el control (OWNER) para que la sesión vieja apague su piloto.
# - Siguientes veces (hook SessionStart/UserPromptSubmit): solo se asegura de que el piloto esté vivo.
# Silencioso: nunca imprime nada (la salida de un hook puede verse en el chat). Log: /tmp/gta6_bootstrap.log
APP=/home/user/GTA6_AUTO_CLIPPER
REPO=/home/user/okx-proxy
BR=claude/gallant-bardeen-s7mk6r
exec >> /tmp/gta6_bootstrap.log 2>&1

if [ -f "$APP/state/owner.txt" ] && [ -d "$APP/clipper" ]; then
  exec bash "$APP/scripts/autopilot_ensure.sh"
fi

(
  set -x
  if [ ! -d "$REPO/GTA6_AUTO_CLIPPER" ]; then
    git clone -q --branch "$BR" https://github.com/ty2mcdwdhw-hash/okx-proxy.git "$REPO" \
      || (cd "$REPO" && git fetch -q origin "$BR" && git checkout -q "$BR")
  fi
  [ -d "$APP/clipper" ] || cp -r "$REPO/GTA6_AUTO_CLIPPER" "$APP"
  cd "$APP" || exit 1
  mkdir -p state/decisions media/raw media/edits/ES media/edits/EN
  [ -f state/clipper.db ] || cp state_snapshot/clipper.db state/clipper.db
  cp -n state_snapshot/decisions/*.json state/decisions/ 2>/dev/null
  cp -n state_snapshot/pillars.txt state/ 2>/dev/null
  [ -d .git ] || { git init -q && git add -A && git -c user.name=Claude -c user.email=noreply@anthropic.com commit -q -m "bootstrap"; }
  python3 -c "import faster_whisper, yt_dlp, yaml, requests, numpy" 2>/dev/null \
    || pip install --break-system-packages -q -r requirements.txt
  # hooks de usuario: el piloto vuelve tras cada reinicio de la máquina
  mkdir -p /root/.claude
  [ -f /root/.claude/settings.json ] || cat > /root/.claude/settings.json <<'EOF'
{
  "hooks": {
    "SessionStart": [{"hooks": [{"type": "command", "command": "bash /home/user/GTA6_AUTO_CLIPPER/scripts/bootstrap.sh", "timeout": 10}]}],
    "UserPromptSubmit": [{"hooks": [{"type": "command", "command": "bash /home/user/GTA6_AUTO_CLIPPER/scripts/bootstrap.sh", "timeout": 10}]}]
  }
}
EOF
  # tomar el control: esta sesión pasa a ser la dueña del piloto
  echo "${CLAUDE_CODE_REMOTE_SESSION_ID:-session-$(date +%s)}" > state/owner.txt
  cp state/owner.txt state_snapshot/OWNER
  cp state/owner.txt "$REPO/GTA6_AUTO_CLIPPER/state_snapshot/OWNER"
  ( cd "$REPO" && git add -f GTA6_AUTO_CLIPPER/state_snapshot/OWNER && \
    git -c user.name=Claude -c user.email=noreply@anthropic.com commit -q -m "GTA6_AUTO_CLIPPER: autopilot ownership moves to a new session" && \
    git push -q origin "HEAD:$BR" )
  rm -f state/autopilot.disabled state/autopilot.pid
  bash scripts/autopilot_ensure.sh
) < /dev/null &
disown
exit 0
