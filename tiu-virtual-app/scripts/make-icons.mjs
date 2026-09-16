/**
 * Genera los iconos de la PWA (public/icons) renderizando un SVG con la
 * misma tipografia y colores del carnet.
 *
 *   node scripts/make-icons.mjs
 *
 * Requiere Playwright (npx playwright install chromium) y solo hay que
 * volver a correrlo si cambian los colores o el nombre de la app.
 */
import { chromium } from 'playwright'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const outDir = resolve(root, 'public/icons')

const font = await readFile(resolve(root, 'src/assets/fonts/fjallaone-latin.woff2'))
const fontFace = `@font-face{font-family:'Fjalla One';src:url(data:font/woff2;base64,${font.toString(
  'base64',
)}) format('woff2');font-display:block}`

const page = (size, padding, radius) => `<!doctype html>
<meta charset="utf-8">
<style>
  ${fontFace}
  html,body{margin:0;width:${size}px;height:${size}px}
  .icon{
    width:${size}px;height:${size}px;border-radius:${radius}px;
    background:#DAD9FC;display:flex;flex-direction:column;
    align-items:center;justify-content:center;gap:${size * 0.03}px;
  }
  .mark{
    font-family:'Fjalla One';color:#EB4B46;line-height:1;
    font-size:${(size - padding * 2) * 0.46}px;letter-spacing:${size * -0.005}px;
  }
  .sub{
    font-family:'Fjalla One';color:#455168;line-height:1;
    font-size:${(size - padding * 2) * 0.135}px;letter-spacing:${size * 0.012}px;
  }
</style>
<div class="icon"><span class="mark">TIU</span><span class="sub">VIRTUAL</span></div>`

const browser = await chromium.launch()
await mkdir(outDir, { recursive: true })

const targets = [
  { file: 'icon-192.png', size: 192, padding: 24, radius: 42 },
  { file: 'icon-512.png', size: 512, padding: 64, radius: 112 },
  { file: 'icon-maskable-512.png', size: 512, padding: 128, radius: 0 },
  { file: 'apple-touch-icon.png', size: 180, padding: 22, radius: 0 },
]

for (const { file, size, padding, radius } of targets) {
  const tab = await browser.newPage({ viewport: { width: size, height: size } })
  await tab.setContent(page(size, padding, radius))
  await tab.waitForTimeout(300)
  const buffer = await tab.screenshot({ omitBackground: false })
  await writeFile(resolve(outDir, file), buffer)
  await tab.close()
  console.log('->', file)
}

await browser.close()
