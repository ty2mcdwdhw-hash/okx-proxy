const express = require('express')
const app = express()
const PORT = process.env.PORT || 3000

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
    message: 'OKX CORS Proxy (Railway) ✅',
    endpoints: ['/api/v5/market/ticker', '/api/v5/market/candles', '/api/v5/market/books']
  })
})

app.get('/api/*', async (req, res) => {
  const query = req.url.includes('?') ? '?' + req.url.split('?')[1] : ''
  const url = `https://www.okx.com${req.path}${query}`
  try {
    const response = await fetch(url, {
      headers: {
        'Accept': 'application/json',
        'Accept-Encoding': 'identity',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
      }
    })
    const text = await response.text()
    res.status(response.status).set('Content-Type', 'application/json').send(text)
  } catch(err) {
    res.status(500).json({ error: err.message })
  }
})

app.listen(PORT, () => console.log(`OKX proxy running on port ${PORT}`))
