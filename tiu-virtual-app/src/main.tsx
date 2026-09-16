import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import './styles.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)

// El service worker solo se registra en produccion (build/preview). Sin el la
// app funciona igual: solo pierde el modo sin conexion. Abierta como archivo
// suelto (file://) el navegador ni siquiera deja registrarlo, y eso lanza de
// forma sincrona, asi que el try/catch tambien hace falta.
if (import.meta.env.PROD && 'serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    try {
      navigator.serviceWorker.register('./sw.js').catch(() => {})
    } catch {
      /* sin modo offline */
    }
  })
}
