# GTA6_AUTO_CLIPPER

Pipeline para la red de canales *faceless* de GTA VI (ES / EN) en YT Shorts, IG Reels y TikTok.
Funciona con escudo anti-spoilers: el operador nunca ve los videos (ver `REVIEWER.md`).

```
Twitch / Kick (clips más vistos de cada canal)  ─┐
YouTube (VOD + picos "más repetidos")*          ─┤→ discover → process → [revisor] → render 9:16 ES/EN → publish
URL manual (`add`)                               ─┘     yt-dlp   Whisper   decisions    FFmpeg+ASS        Upload-Post
```
\* YouTube bloquea las descargas desde IPs de nube. Solo se activa (`youtube_enabled`) al correr en un PC propio.

## Instalación
```bash
pip install -r requirements.txt     # también requiere ffmpeg con libass
```

## Comandos
| comando | qué hace |
|---|---|
| `python -m clipper verify` | comprueba que los canales de `config/watchlist.yaml` existen |
| `python -m clipper discover [--group launch_asia]` | busca los clips más vistos de la ventana configurada |
| `python -m clipper add URL --creator H --lang ja` | agrega un clip a mano |
| `python -m clipper process` | descarga, detecta letterbox (cinemáticas), transcribe y arma el paquete de revisión |
| `python -m clipper pending` | paquetes esperando decisión |
| `python -m clipper decide` | aplica `state/decisions/*.json` |
| `python -m clipper render` | MP4 1080x1920 H.264/AAC con gancho, crédito y subtítulos ES y EN |
| `python -m clipper publish [--dry]` | publica en Upload-Post respetando topes diarios y separación mínima |
| `python -m clipper cycle` | todo lo anterior en un paso |
| `python -m clipper cards` | fichas sanitizadas (solo texto) para el operador |
| `python -m clipper takedown ID` | marca un retiro y lo anota en `takedowns.md` |
| `python -m clipper purge-raw` | borra las descargas temporales |
| `python -m clipper reset-test` | borra los datos del MODO TEST |

## Publicación (Upload-Post)
- Un *profile* por idioma: `gta6_es` y `gta6_en`. Cada uno conecta TikTok, Instagram y YouTube.
- La API key nunca va en el repo. En la sesión en la nube la inyecta el proxy; en local va en `UPLOAD_POST_API_KEY`.
- Topes por cuenta y día en `config/settings.yaml` (`daily_caps`). Lo que se pase de tope se programa con `scheduled_date`.
- Los clips del MODO TEST nunca se publican (quedan como `queued`).

## Archivos
`playbook.md` · `facts.md` · `watchlist.md` · `idea-bank.md` · `log.md` · `scoreboard.csv` · `learning.md` · `takedowns.md` · `media/edits/{ES,EN}`
