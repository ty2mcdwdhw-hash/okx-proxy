// ══════════════════════════════════════════════════════════
//  PROXY CORS — v5.7 (Binance Futuros USDⓈ-M + OKX)
// ══════════════════════════════════════════════════════════
// Cambio respecto a v5.6: además de OKX (/api/*) ahora expone Binance Futuros
// (/fapi/*). La ejecución real es en Binance, así que analizar sobre el mismo
// libro elimina el spread entre exchanges como fuente silenciosa de barridos
// de SL (los niveles calculados son directamente ejecutables).
//
// Los dos backends conviven a propósito: el HTML detecta al arrancar si /fapi
// responde y usa Binance; si no, sigue con OKX sin romperse. Eso permite
// desplegar esto sin coordinar con el cliente y hacer rollback trivial.
//
// Despliegue: repo `okx-proxy` → Render lo recoge del push a main.

const express = require('express')
const app = express()
const PORT = process.env.PORT || 3000

const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'

app.use((req, res, next) => {
  res.header('Access-Control-Allow-Origin', '*')
  res.header('Access-Control-Allow-Methods', 'GET, OPTIONS')
  res.header('Access-Control-Allow-Headers', '*')
  if (req.method === 'OPTIONS') return res.sendStatus(200)
  next()
})

app.get('/', (req, res) => {
  res.json({
    status: 'ok',
    message: 'Market Data CORS Proxy v5.7 (Binance + OKX) ✅',
    binance: ['/fapi/v1/ticker/24hr', '/fapi/v1/klines', '/fapi/v1/depth', '/fapi/v1/premiumIndex'],
    okx: ['/api/v5/market/ticker', '/api/v5/market/candles', '/api/v5/market/books', '/api/v5/public/funding-rate'],
  })
})

// Helper de fetch con timeout — Render free tier no debe quedarse colgado
async function passthrough(url, res) {
  const ctrl = new AbortController()
  const timer = setTimeout(() => ctrl.abort(), 15000)
  try {
    const response = await fetch(url, {
      signal: ctrl.signal,
      headers: {
        'Accept': 'application/json',
        'Accept-Encoding': 'identity',
        'User-Agent': UA,
      }
    })
    const text = await response.text()
    res.status(response.status).set('Content-Type', 'application/json').send(text)
  } catch (err) {
    const aborted = err.name === 'AbortError'
    res.status(aborted ? 504 : 500).json({ error: aborted ? 'upstream timeout' : err.message })
  } finally {
    clearTimeout(timer)
  }
}

// ── BINANCE FUTUROS USDⓈ-M ──
// Se prueban varios hosts: si uno responde 451 (restricción geográfica) o falla,
// se intenta el siguiente antes de dar error. Render corre en EE.UU., donde
// fapi.binance.com normalmente responde bien; los alternativos son red de
// seguridad por si cambia la política de la IP del datacenter.
const BINANCE_HOSTS = [
  'https://fapi.binance.com',
  'https://fapi1.binance.com',
  'https://fapi2.binance.com',
]

app.get('/fapi/*', async (req, res) => {
  const query = req.url.includes('?') ? '?' + req.url.split('?')[1] : ''
  let lastStatus = null, lastBody = null

  for (const host of BINANCE_HOSTS) {
    const ctrl = new AbortController()
    const timer = setTimeout(() => ctrl.abort(), 15000)
    try {
      const response = await fetch(`${host}${req.path}${query}`, {
        signal: ctrl.signal,
        headers: { 'Accept': 'application/json', 'Accept-Encoding': 'identity', 'User-Agent': UA }
      })
      const text = await response.text()
      if (response.ok) {
        clearTimeout(timer)
        return res.status(200).set('Content-Type', 'application/json').send(text)
      }
      // 451 = bloqueo geográfico; 403 = restricción. Probar el host siguiente.
      lastStatus = response.status
      lastBody = text
    } catch (err) {
      lastStatus = err.name === 'AbortError' ? 504 : 502
      lastBody = JSON.stringify({ error: err.message })
    } finally {
      clearTimeout(timer)
    }
  }
  // Ningún host de Binance sirvió. Se devuelve el error para que el cliente
  // active su fallback a OKX (el HTML lo hace de forma transparente).
  res.status(lastStatus || 502)
     .set('Content-Type', 'application/json')
     .send(lastBody || JSON.stringify({ error: 'binance unreachable' }))
})

// ── OKX (se mantiene: fallback del cliente y compatibilidad con v5.6) ──
app.get('/api/*', async (req, res) => {
  const query = req.url.includes('?') ? '?' + req.url.split('?')[1] : ''
  await passthrough(`https://www.okx.com${req.path}${query}`, res)
})

app.listen(PORT, () => console.log(`Market data proxy v5.7 (Binance+OKX) on port ${PORT}`))
