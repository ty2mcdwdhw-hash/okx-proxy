import { useEffect, useState } from 'react'

/**
 * Reloj que avanza cada segundo. Se re-sincroniza con el borde del segundo
 * (y al volver del segundo plano) para que no se desfase como lo haria un
 * setInterval fijo.
 */
export function useNow(): Date {
  const [now, setNow] = useState(() => new Date())

  useEffect(() => {
    let timer: number

    const tick = () => {
      const current = new Date()
      setNow(current)
      timer = window.setTimeout(tick, 1000 - (current.getTime() % 1000))
    }

    tick()

    const resync = () => {
      if (document.visibilityState === 'visible') {
        window.clearTimeout(timer)
        tick()
      }
    }

    document.addEventListener('visibilitychange', resync)
    return () => {
      window.clearTimeout(timer)
      document.removeEventListener('visibilitychange', resync)
    }
  }, [])

  return now
}
