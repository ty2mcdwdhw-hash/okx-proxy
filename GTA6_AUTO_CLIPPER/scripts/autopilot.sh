#!/usr/bin/env bash
# Bucle del piloto automático: una iteración cada 30 min (a los :13 y :43 aprox.).
# Un solo bucle a la vez (flock). Lo relanza autopilot_ensure.sh tras un reinicio de la máquina.
cd /home/user/GTA6_AUTO_CLIPPER || exit 1
exec 9> state/autopilot.lock
flock -n 9 || exit 0
echo $$ > state/autopilot.pid
echo "[$(TZ=America/Lima date '+%d/%m %H:%M')] piloto: arrancado (pid $$)" >> state/autopilot.log
while true; do
  [ -f state/autopilot.pause ] && { sleep 60; continue; }
  # no pisar un ciclo lanzado a mano
  while pgrep -f "clipper (cycle|render|publish)" > /dev/null; do sleep 30; done
  date +%s > state/autopilot.heartbeat
  bash scripts/autopilot_once.sh
  date +%s > state/autopilot.heartbeat
  # dormir hasta el próximo :13 o :43
  m=$(date +%-M); s=$(date +%-S)
  if [ "$m" -lt 13 ]; then t=$((13 - m)); elif [ "$m" -lt 43 ]; then t=$((43 - m)); else t=$((73 - m)); fi
  sleep $(( t * 60 - s ))
done
