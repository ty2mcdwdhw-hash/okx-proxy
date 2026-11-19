#!/usr/bin/env bash
# Ciclo silencioso: toda la salida va a state/logs; en pantalla solo conteos (escudo del operador).
# Uso: ./cycle.sh cycle   |  ./cycle.sh post   (decide+render+publish tras la revisión)  |  ./cycle.sh snapshot
set -u
cd /home/user/GTA6_AUTO_CLIPPER
mkdir -p state/logs
TS=$(date -u +%Y%m%dT%H%M%SZ)
LOG=state/logs/$1_$TS.log
case "$1" in
  cycle)
    timeout 1500 python3 -m clipper cycle >"$LOG" 2>&1; echo "exit=$?"
    echo "errores: $(grep -ciE 'traceback|error' "$LOG")"
    ;;
  post)
    { python3 -m clipper decide; python3 -m clipper render; python3 -m clipper publish; } >"$LOG" 2>&1; echo "exit=$?"
    grep -E '^approved=' "$LOG"
    echo "errores: $(grep -ciE 'traceback|error' "$LOG")"
    ;;
  snapshot)
    R=/home/user/okx-proxy/GTA6_AUTO_CLIPPER
    mkdir -p $R/state_snapshot/decisions
    cp state/clipper.db $R/state_snapshot/clipper.db
    cp state/decisions/*.json $R/state_snapshot/decisions/ 2>/dev/null
    cp state/pillars.txt $R/state_snapshot/ 2>/dev/null
    cp config/settings.yaml $R/config/; cp cycle.sh log.md scoreboard.csv takedowns.md $R/ 2>/dev/null
    cd /home/user/okx-proxy && git add GTA6_AUTO_CLIPPER >/dev/null && \
      git commit -qm "GTA6_AUTO_CLIPPER: cycle snapshot $TS

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_012s2xZPUw2qcNxhKcebRMUH" && echo committed
    for i in 1 2 3 4; do git push -q -u origin claude/youthful-cerf-fcmljs 2>/dev/null && { echo pushed; break; }; sleep $((2**i)); done
    exit 0
    ;;
esac
cd /home/user/GTA6_AUTO_CLIPPER && python3 -m clipper status
echo "pendientes de revisión: $(python3 -m clipper pending | grep -c ' -> ')"
