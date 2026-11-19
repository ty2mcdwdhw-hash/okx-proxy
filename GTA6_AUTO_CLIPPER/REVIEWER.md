# Protocolo del revisor (Claude)

## Escudo anti-spoiler = protección del OPERADOR (no de los clips)
- Los clips **sí pueden** incluir historia, cinemáticas, misiones y personajes. Es contenido válido y suele ser el más viral.
- El operador **nunca** debe ver ni leer nada del juego: en el chat no se muestran fotogramas, videos de GTA VI, ni descripciones, títulos, hooks o captions que cuenten algo de la historia.
- Lo que sí se le muestra: conteos y fichas `ID | idioma -> ES/EN | pilar | duración | estado`. El copy solo se muestra si `operator_safe: true` (clip sin nada de historia); si no, aparece "🔒 copy oculto".
- No uses nombres de personajes, misiones ni giros en los mensajes al operador, ni siquiera en resúmenes o motivos de rechazo (usa motivos genéricos).

## Rechazo (seguridad de plataforma y calidad)
1. Desnudos, contenido sexual explícito (clubs/lapdances), violencia gráfica extrema.
2. Consumo explícito de drogas como foco del clip.
3. Contenido que no es GTA VI, clips sin momento claro, duplicados de temas ya publicados.
4. Música con copyright como protagonista.
5. Insultos discriminatorios (homófobos, racistas, etc.) en CUALQUIER punto del audio, aunque sea de pasada, y aunque nuestros subtítulos lo censuren.

### Reglas endurecidas (aviso de Instagram, 18/11 noche)
Auditoría tras un aviso de Normas comunitarias: las causas fueron lenguaje sexual legible en pantalla, un insulto homófobo en el audio, groserías fuertes continuas en el audio y subtítulos/textos ORIGINALES del streamer (overlays, chat, subs quemados) con groserías sin censurar. Por eso:
6. Rechaza si en el fotograma se lee texto sexual o grosero (overlays del stream, chat, subtítulos quemados del streamer, carteles del juego). Revisa el contact sheet buscando texto legible.
7. Rechaza si el audio tiene groserías fuertes de forma continua (más de 2-3 en el tramo recortado) o cualquier contenido sexual verbal explícito. Una grosería aislada se permite si nuestros subtítulos la censuran.
8. Elige el trim para dejar fuera insultos y groserías cuando el momento lo permita.
9. Ante la duda en seguridad, rechaza: Instagram penaliza la cuenta entera, no solo el post.

## Selección
- Prioriza por vistas y por momento: reacciones fuertes, momentos épicos/graciosos, física, conducción, mapa, NPCs, y también momentos de historia potentes.
- Respeta topes diarios de TikTok (15/cuenta): elige lo mejor.

## Salida: `state/decisions/<ID>.json`
```json
{"id": "TW_123", "verdict": "approve", "spoiler_level": 0, "story": true, "operator_safe": false,
 "reason": "genérico, sin trama", "pillar": "Historia / Reacciones", "trim": [2.0, 24.5],
 "hook": {"ES": "...", "EN": "..."}, "subs": [{"start": 3.1, "end": 5.0, "ES": "...", "EN": "..."}],
 "copy": {"ES": {"title": "...", "caption": "...", "hashtags": ["GTA6"]}, "EN": {"title": "...", "caption": "...", "hashtags": ["GTA6"]}}}
```
- `spoiler_level` se mantiene en 0 por compatibilidad (el filtro de publicación lo exige); ya no mide historia.
- Los tiempos de `subs` son del clip original. Localización gamer, groserías fuertes censuradas, pronombres neutros en EN.
- `trim`: 7-30 s (55 s si es HOW TO).
