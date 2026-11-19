# HANDOFF — continuar GTA6_AUTO_CLIPPER en una sesión nueva

La sesión anterior agotó su tiempo de vida (19/11/2026 ~01:00 UTC). Todo lo necesario está en esta rama.

## Arranque (en la sesión nueva, en la nube, entorno Default)
```bash
cd /home/user && git clone -q --branch claude/gallant-bardeen-s7mk6r https://github.com/ty2mcdwdhw-hash/okx-proxy.git okx-proxy || (cd okx-proxy && git fetch origin claude/gallant-bardeen-s7mk6r && git checkout claude/gallant-bardeen-s7mk6r && git pull --ff-only)
cp -r /home/user/okx-proxy/GTA6_AUTO_CLIPPER /home/user/GTA6_AUTO_CLIPPER
cd /home/user/GTA6_AUTO_CLIPPER && pip install --break-system-packages -q -r requirements.txt
mkdir -p state/decisions && cp state_snapshot/clipper.db state/clipper.db && cp state_snapshot/decisions/*.json state/decisions/ && cp state_snapshot/pillars.txt state/ 2>/dev/null
python3 -m clipper status
```
- Las claves de Upload-Post (api.upload-post.com) y Twitch (api.twitch.tv) están guardadas en el entorno: el proxy las inyecta. No hay que pedirlas.
- La red del entorno Default es abierta (necesaria para los CDN de Twitch/Kick).

## Ciclo automático
Crear con CronCreate (`13,43 * * * *`) el mensaje de ciclo de abajo. Si el servidor se reinicia, el programador se pierde: cada ciclo debe comprobar con CronList que sigue programado.

## Reglas clave (ver REVIEWER.md y REVIEW_AGENT.md)
- **Escudo del operador:** el operador ve todo el chat en su celular. Nunca abrir imágenes, imprimir transcripciones/títulos/packet.md ni enviar videos en la sesión principal. La revisión la hace un subagente (Agent general-purpose con REVIEW_AGENT.md).
- Los clips SÍ pueden tener historia; marcar `story`/`operator_safe`; copy de clips con historia oculto en las fichas.
- Topes: TikTok 15/24 h por cuenta (lookahead 8 h); YouTube 10/día por canal (reinicio medianoche Pacífico = 03:00 Lima, lookahead 6 h); Instagram 48/día, 2/h (lookahead 12 h). Margen de 10 min en topes móviles.
- `"priority": true` en una decisión = clip viral, va primero en todas las colas.
- Foco regional en `config/settings.yaml` (`focus`): 19/11 00:00-12:00 Lima = América (es 25, en 15, pt 8). Después: definir la ventana del día 2 con el operador.
- 6 cuentas: perfil `GTA6_ES` (TikTok @gta6_es1, Instagram @gta_6es, YouTube @gta_6es) y perfil `default` = EN (TikTok @gta6_en2, Instagram @gta6_en, YouTube @gta6_en).

## Pendiente
- Video local de DaniRep ("mi primera vez en gta", 314 MB, carpeta GTA6 del Mac del operador): se transfirió pero la sesión expiró durante el procesamiento. Repetir: conectar la carpeta GTA6 del Mac (list_computer_folders + request_computer_folder), dividir en partes de 90 MB, subir a una rama temporal `media-upload-tmp` desde el Mac con `gh auth git-credential`, clonarla aquí, verificar sha256, borrar la rama con `gh api -X DELETE repos/ty2mcdwdhw-hash/okx-proxy/git/refs/heads/media-upload-tmp` desde el Mac, cortar en tramos de 45 s (ids LOCAL_danirep_XXXXX, creator DaniRep, lang es), transcribir y pasar al agente revisor (5 mejores momentos).
- Clip viral de IlloJuan (borró el juego): ya programado con prioridad en las 6 cuentas (IG enviado; YouTube 03:10 y TikTok 06:56 Lima del 19/11).
- Día 2 = día de mejora: informe de métricas (scoreboard.csv, vistas 12/24/72 h) y segunda cuenta de TikTok por idioma si el operador la crea (repartir clips entre perfiles).
- Revisar si TikTok marca 0 vistas (alcance limitado en cuentas nuevas) cuando haya métricas de 24 h.
