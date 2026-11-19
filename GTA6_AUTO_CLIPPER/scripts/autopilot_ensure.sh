#!/usr/bin/env bash
# Lo llama un hook de Claude Code (SessionStart y UserPromptSubmit): si el piloto no corre, lo arranca.
# Silencioso y rápido: nunca imprime nada (la salida de un hook podría verse en el chat).
cd /home/user/GTA6_AUTO_CLIPPER 2>/dev/null || exit 0
[ -f state/autopilot.disabled ] && exit 0
if [ -f state/autopilot.pid ] && kill -0 "$(cat state/autopilot.pid)" 2>/dev/null; then exit 0; fi
nohup setsid bash scripts/autopilot.sh > /dev/null 2>&1 < /dev/null &
exit 0
