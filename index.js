// ══════════════════════════════════════════════════════════
//  PROXY CORS — v5.9 (OKX + Yahoo Finance)
// ══════════════════════════════════════════════════════════
// v5.7.1 intentó añadir Binance Futuros y se descartó: Binance bloquea las IPs
// de proveedores cloud (451/302 verificado en producción el 7/8/26). No es un
// problema de país sino de rango ASN, así que ninguna IP de hosting barato pasa.
//
// v5.9 añade Yahoo Finance, que tenía un problema DISTINTO: Yahoo no envía
// Access-Control-Allow-Origin para NINGÚN origen — su API no está pensada para
// consumo desde navegador. Servir el HTML por HTTP no lo arreglaba (diagnóstico
// inicial equivocado). Enrutarlo por este proxy sí, porque aquí se añade el
// header CORS. Con esto el sesgo macro S&P/NASDAQ/DXY y el módulo NYSE momentum
// pasan a tener datos por primera vez.

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
    message: 'Market Data CORS Proxy v5.9 (OKX + Yahoo) ✅',
    okx: ['/api/v5/market/ticker', '/api/v5/market/tickers', '/api/v5/market/candles', '/api/v5/market/books', '/api/v5/public/funding-rate'],
    yahoo: ['/yahoo/v8/finance/chart/{symbol}'],
    note: 'Binance descartado: bloquea IPs de proveedores cloud (451/302)',
  })
})

async function passthrough(url, res, tag) {
  const ctrl = new AbortController()
  const timer = setTimeout(() => ctrl.abort(), 15000)
  try {
    const response = await fetch(url, {
      signal: ctrl.signal,
      headers: { 'Accept': 'application/json', 'User-Agent': UA }
    })
    const text = await response.text()
    console.log(`[${tag}] ${url} → ${response.status}, ${text.length} bytes`)
    res.status(response.status).set('Content-Type', 'application/json').send(text)
  } catch (err) {
    const aborted = err.name === 'AbortError'
    console.error(`[${tag}] ${url} → ERROR: ${err.message}`)
    res.status(aborted ? 504 : 500).json({ error: aborted ? 'upstream timeout' : err.message })
  } finally {
    clearTimeout(timer)
  }
}

// ── YAHOO FINANCE (nuevo en v5.9) ──
// Se prueban ambos hosts: query1 falla intermitentemente, query2 suele responder.
const YAHOO_HOSTS = ['https://query1.finance.yahoo.com', 'https://query2.finance.yahoo.com']

app.get('/yahoo/*', async (req, res) => {
  const path = req.path.replace(/^\/yahoo/, '')
  const query = req.url.includes('?') ? '?' + req.url.split('?')[1] : ''
  let lastErr = null

  for (const host of YAHOO_HOSTS) {
    const ctrl = new AbortController()
    const timer = setTimeout(() => ctrl.abort(), 12000)
    try {
      const r = await fetch(`${host}${path}${query}`, {
        signal: ctrl.signal,
        headers: { 'Accept': 'application/json', 'User-Agent': UA }
      })
      const text = await r.text()
      console.log(`[Yahoo] ${host}${path} → ${r.status}, ${text.length} bytes`)
      if (r.ok && text.length > 0) {
        clearTimeout(timer)
        return res.status(200).set('Content-Type', 'application/json').send(text)
      }
      lastErr = { status: r.status, body: text }
    } catch (err) {
      console.error(`[Yahoo] ${host}${path} → ERROR: ${err.message}`)
      lastErr = { status: err.name === 'AbortError' ? 504 : 502, body: JSON.stringify({ error: err.message }) }
    } finally {
      clearTimeout(timer)
    }
  }
  res.status(lastErr?.status || 502)
     .set('Content-Type', 'application/json')
     .send(lastErr?.body || JSON.stringify({ error: 'yahoo unreachable' }))
})

// ── OKX ──
app.get('/api/*', async (req, res) => {
  const query = req.url.includes('?') ? '?' + req.url.split('?')[1] : ''
  await passthrough(`https://www.okx.com${req.path}${query}`, res, 'OKX')
})

app.listen(PORT, () => console.log(`Market data proxy v5.9 (OKX+Yahoo) on port ${PORT}`))
