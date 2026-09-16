/**
 * Empaqueta el build en un unico archivo HTML autocontenido.
 *
 *   npm run build && node scripts/build-single-file.mjs
 *   -> dist/tiu-virtual.html
 *
 * Mete el JS, el CSS, las fuentes y la foto dentro del propio HTML, asi el
 * archivo se abre con doble clic (file://) sin servidor ni instalacion. Es
 * para mirar la pantalla rapido: para instalarla como app en el telefono
 * hace falta servir dist/ por HTTPS.
 */
import { readFile, writeFile } from 'node:fs/promises'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const dist = resolve(root, 'dist')

const mime = { woff2: 'font/woff2', jpg: 'image/jpeg', jpeg: 'image/jpeg', png: 'image/png' }
const dataUri = async (file) => {
  const ext = file.split('.').pop()
  const bytes = await readFile(resolve(dist, file))
  return `data:${mime[ext] ?? 'application/octet-stream'};base64,${bytes.toString('base64')}`
}

let html = await readFile(resolve(dist, 'index.html'), 'utf8')

const cssName = html.match(/href="\.\/(assets\/[^"]+\.css)"/)?.[1]
const jsName = html.match(/src="\.\/(assets\/[^"]+\.js)"/)?.[1]
if (!cssName || !jsName) throw new Error('No encontre el CSS/JS del build. ¿Corriste npm run build?')

// CSS: las fuentes se referencian relativas a assets/, se vuelven data URIs.
let css = await readFile(resolve(dist, cssName), 'utf8')
for (const [, file] of css.matchAll(/url\(\.\/([^)]+)\)/g)) {
  css = css.replace(`url(./${file})`, `url(${await dataUri(`assets/${file}`)})`)
}

// JS: la foto vive en public/, aqui se incrusta igual.
let js = await readFile(resolve(dist, jsName), 'utf8')
js = js.replaceAll('"./avatar.jpg"', JSON.stringify(await dataUri('avatar.jpg')))
// Un archivo suelto no tiene service worker ni manifest que registrar.
js = js.replaceAll('</script>', '<\\/script>')

html = html
  .replace(/\s*<link rel="manifest"[^>]*>/, '')
  .replace(/\s*<link rel="apple-touch-icon"[^>]*>/, '')
  .replace(/\s*<link rel="icon"[^>]*>/, '')
  .replace(/\s*<script type="module" crossorigin src="[^"]+"><\/script>/, '')
  .replace(/\s*<link rel="stylesheet" crossorigin href="[^"]+">/, `\n    <style>${css}</style>`)
  .replace('</body>', `  <script type="module">${js}</script>\n  </body>`)

const out = resolve(dist, 'tiu-virtual.html')
await writeFile(out, html)
console.log(`-> ${out}  (${(Buffer.byteLength(html) / 1024).toFixed(0)} kB)`)
