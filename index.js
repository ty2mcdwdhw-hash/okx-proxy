// ══════════════════════════════════════════════════════════
//  PROXY CORS — v5.7.1 (Binance Futuros USDⓈ-M + OKX)
// ══════════════════════════════════════════════════════════
// v5.7 exponía Binance vía fetch(), pero fetch() prohíbe fijar el header
// Accept-Encoding manualmente (la spec lo bloquea) y lo ignora en silencio.
// Si Binance respondía comprimido y algo fallaba en la descompresión
// automática, el resultado era un 200 con cuerpo vacío — sin ningún error
// visible. v5.7.1 usa el módulo https nativo de Node para el tramo Binance,
// donde Accept-Encoding: identity sí se respeta de verdad, y agrega logs en
// cada paso para poder diagnosticar desde los logs de Render si algo más
// falla — en vez de adivinar a ciegas otra vez.

const express = require('express')
const https = require('https')
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
    message: 'Market Data CORS Proxy v5.7.1 (Binance + OKX) ✅',
    binance: ['/fapi/v1/ticker/24hr', '/fapi/v1/klines', '/fapi/v1/depth', '/fapi/v1/premiumIndex'],
    okx: ['/api/v5/market/ticker', '/api/v5/market/candles', '/api/v5/market/books', '/api/v5/public/funding-rate'],
  })
})

// ── Passthrough OKX: sigue usando fetch(), sin cambios (venía funcionando bien) ──
async function passthrough(url, res) {
  const ctrl = new AbortController()
  const timer = setTimeout(() => ctrl.abort(), 15000)
  try {
    const response = await fetch(url, {
      signal: ctrl.signal,
      headers: { 'Accept': 'application/json', 'User-Agent': UA }
    })
    const text = await response.text()
    console.log(`[OKX] ${url} → ${response.status}, ${text.length} bytes`)
    res.status(response.status).set('Content-Type', 'application/json').send(text)
  } catch (err) {
    const aborted = err.name === 'AbortError'
    console.error(`[OKX] ${url} → ERROR: ${err.message}`)
    res.status(aborted ? 504 : 500).json({ error: aborted ? 'upstream timeout' : err.message })
  } finally {
    clearTimeout(timer)
  }
}

// ── Passthrough Binance vía https nativo (Accept-Encoding sí se respeta aquí) ──
function fetchViaHttps(url, timeoutMs) {
  return new Promise((resolve, reject) => {
    const req = https.get(url, {
      headers: {
        'Accept': 'application/json',
        'Accept-Encoding': 'identity',  // aquí SÍ funciona: no es fetch(), no está prohibido
        'User-Agent': UA,
      },
      timeout: timeoutMs,
    }, (res) => {
      let data = ''
      res.setEncoding('utf8')
      res.on('data', chunk => { data += chunk })
      res.on('end', () => resolve({ status: res.statusCode, body: data }))
    })
    req.on('timeout', () => { req.destroy(new Error('request timeout')) })
    req.on('error', reject)
  })
}

const BINANCE_HOSTS = [
  'https://fapi.binance.com',
  'https://fapi1.binance.com',
  'https://fapi2.binance.com',
]

app.get('/fapi/*', async (req, res) => {
  const query = req.url.includes('?') ? '?' + req.url.split('?')[1] : ''
  let lastStatus = null, lastBody = null

  for (const host of BINANCE_HOSTS) {
    const url = `${host}${req.path}${query}`
    try {
      const { status, body } = await fetchViaHttps(url, 15000)
      console.log(`[Binance] ${url} → status ${status}, ${body.length} bytes`)
      if (status >= 200 && status < 300 && body.length > 0) {
        return res.status(200).set('Content-Type', 'application/json').send(body)
      }
      lastStatus = status
      lastBody = body || JSON.stringify({ error: `empty body from ${host}, status ${status}` })
    } catch (err) {
      console.error(`[Binance] ${url} → ERROR: ${err.message}`)
      lastStatus = err.message === 'request timeout' ? 504 : 502
      lastBody = JSON.stringify({ error: err.message })
    }
  }
  console.error(`[Binance] TODOS los hosts fallaron para ${req.path}${query} — último status ${lastStatus}`)
  res.status(lastStatus || 502)
     .set('Content-Type', 'application/json')
     .send(lastBody || JSON.stringify({ error: 'binance unreachable' }))
})

// ── OKX (fallback del cliente y compatibilidad con v5.6) ──
app.get('/api/*', async (req, res) => {
  const query = req.url.includes('?') ? '?' + req.url.split('?')[1] : ''
  await passthrough(`https://www.okx.com${req.path}${query}`, res)
})

app.listen(PORT, () => console.log(`Market data proxy v5.7.1 (Binance+OKX) on port ${PORT}`))
