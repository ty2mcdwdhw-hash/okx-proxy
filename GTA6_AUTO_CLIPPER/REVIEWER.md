# Protocolo del revisor (Claude): escudo anti-spoilers

El operador humano **no ve** videos, imágenes ni detalles de historia. El único que mira los
fotogramas es el revisor (Claude), y nunca los muestra en el chat.

## Entrada
`python -m clipper pending` lista los paquetes de `state/review/<ID>/`:
- `packet.md`: metadatos + transcripción con tiempos
- `contact.jpg`: 8 fotogramas del clip (solo para el revisor)
- `transcript.json`

## Reglas de rechazo (cualquiera = `reject`)
1. Cinemáticas, escenas con barras negras, diálogos de misión, cartel de misión, créditos.
2. Muertes de personajes de la historia, finales, giros de trama, nombres de misiones.
3. Contenido que no es GTA (IRL, otros juegos, deportes, transmisiones de TV de terceros).
4. Desnudos, violencia gráfica extrema, contenido sexual, apuestas o casinos.
5. Música con copyright claramente audible como protagonista.
6. Sin valor sistémico: el clip no muestra físicas, conducción, clima, mapa, gráficos, NPCs, bugs ni mecánicas.

Ante la duda: `reject`. `spoiler_level` debe ser `0` para publicar.

## Salida: `state/decisions/<ID>.json`
```json
{
  "id": "TW_123",
  "verdict": "approve",
  "spoiler_level": 0,
  "reason": "Conducción en autopista, sin historia",
  "pillar": "Físicas y Gameplay",
  "trim": [2.0, 24.5],
  "hook": {"ES": "...", "EN": "..."},
  "subs": [{"start": 3.1, "end": 5.0, "ES": "...", "EN": "..."}],
  "copy": {
    "ES": {"title": "...", "caption": "...", "hashtags": ["GTA6", "GTAVI", "GTAVIClips"]},
    "EN": {"title": "...", "caption": "...", "hashtags": ["GTA6", "GTAVI", "GTAVIClips"]}
  }
}
```
- Los tiempos de `subs` son del clip original (no recortado). `render` los desplaza.
- Los subtítulos son localización gamer, no traducción literal: *wanted level, handling, spawn, glitch*.
- Censura las groserías fuertes en los subtítulos.
- No asumas el género del streamer: en EN evita he/his/she/her (usa the/their o reescribe la frase).
- `trim`: entre 7 y 30 s (55 s si es HOW TO). Cortar silencios iniciales y terminar en el remate.
- Pilares: Noticias Oficiales · Trucos y Mecánicas · Físicas y Gameplay · Comparativas GTA 5 vs 6 · Spotlights · Recap Diario · Preguntas a la Comunidad.

## Ciclo
```bash
python -m clipper cycle      # aplica decisiones, renderiza, publica, descubre y procesa lo nuevo
python -m clipper pending    # -> el revisor escribe decisiones
python -m clipper cycle
```
