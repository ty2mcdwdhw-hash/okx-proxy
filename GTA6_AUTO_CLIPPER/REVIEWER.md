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
5. Rechaza solo si el insulto discriminatorio ES el momento (el clip no se entiende sin él). Si no, censúralo (abajo).

### Censura en vez de rechazo (aviso de Instagram, 18/11 noche; decisión del operador)
El aviso vino de: texto sexual legible en pantalla, un insulto homófobo en el audio, groserías continuas en el audio
y subtítulos/overlays ORIGINALES del streamer con groserías sin censurar. El operador decidió NO quitar estos clips
sino CENSURARLOS con un pixelado llamativo (atrae la mirada). Herramientas en la decisión:
- **Subtítulos:** envuelve cada palabra a censurar en `[[...]]` (p. ej. `"ES": "qué [[cabrón]] el NPC"`). Se renderiza
  como un mosaico pixelado rosa/blanco en el hueco exacto de la palabra. Úsalo para TODAS las groserías fuertes,
  insultos discriminatorios y palabras sexuales explícitas (no uses asteriscos). Hazlo en ES y en EN.
- **Audio:** `"bleep": [[start, end], ...]` (tiempos del clip original, ±0.1 s alrededor de la palabra, sácalos de los
  tiempos por palabra de transcript.json) silencia y pone un pitido. Obligatorio para insultos discriminatorios y
  lenguaje sexual explícito; recomendado para groserías fuertes (máx. ~6 pitidos por clip; si hay más, elige otro trim).
- **Texto en pantalla:** `"pixelate": [{"box": [x, y, w, h], "start": s, "end": e}]` con fracciones (0-1) del fotograma
  ORIGINAL y tiempos del clip original. Para overlays/chat/subtítulos quemados del streamer o carteles con texto
  sexual o grosero. Cubre la zona con margen.
Se sigue rechazando: desnudos/contenido sexual visual (clubs, lapdances), drogas como foco, gore, violencia contra
animales/ancianos. Elige el trim para minimizar censuras cuando el momento lo permita.

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
- Los tiempos de `subs` son del clip original. Localización gamer, groserías fuertes censuradas con `[[...]]` (mosaico pixelado), pronombres neutros en EN.
- Opcionales de censura: `"bleep": [[3.1, 3.5]]`, `"pixelate": [{"box": [0.62, 0.05, 0.36, 0.22], "start": 2.0, "end": 24.5}]` (ver sección de censura).
- `trim`: 7-30 s (55 s si es HOW TO).
