# Recuperación si el contenedor se reinició

Si `/home/user/GTA6_AUTO_CLIPPER` no existe o faltan dependencias:

```bash
cd /home/user/okx-proxy && git fetch origin claude/gallant-bardeen-s7mk6r && git checkout claude/gallant-bardeen-s7mk6r && git pull --ff-only
cp -r /home/user/okx-proxy/GTA6_AUTO_CLIPPER /home/user/GTA6_AUTO_CLIPPER
cd /home/user/GTA6_AUTO_CLIPPER && pip install --break-system-packages -q -r requirements.txt
python3 -m clipper status
```
La base `state/clipper.db` no está en git: si se perdió, el sistema vuelve a descubrir clips. Los posts ya publicados no se repiten porque Upload-Post usa `Idempotency-Key = <clip>_<idioma>`.
Las claves de Upload-Post y Twitch las inyecta el proxy: no hace falta configurarlas otra vez.
