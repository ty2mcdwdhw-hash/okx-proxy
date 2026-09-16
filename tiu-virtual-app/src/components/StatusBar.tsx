import { formatClock } from '../lib/datetime'

/**
 * Barra de estado simulada (hora, senal, 5G, bateria).
 *
 * Solo se dibuja en el navegador: cuando la PWA corre instalada en el iPhone,
 * la barra real del sistema ocupa ese espacio y esta se oculta por CSS.
 */
export function StatusBar({ now }: { now: Date }) {
  const time = formatClock(now).slice(0, 5)

  return (
    <div className="status-bar" aria-hidden="true">
      <span className="status-bar__time">{time}</span>
      <span className="status-bar__location">
        <svg viewBox="0 0 24 24" width="13" height="13">
          <path d="M22 2 2 11l8 3 3 8Z" fill="currentColor" />
        </svg>
      </span>
      <span className="status-bar__right">
        <svg viewBox="0 0 18 12" width="18" height="12" className="status-bar__signal">
          <rect x="0" y="8" width="3" height="4" rx="1" fill="currentColor" />
          <rect x="5" y="5.5" width="3" height="6.5" rx="1" fill="currentColor" />
          <rect x="10" y="3" width="3" height="9" rx="1" fill="currentColor" />
          <rect x="15" y="0" width="3" height="12" rx="1" fill="currentColor" />
        </svg>
        <span className="status-bar__network">5G</span>
        <span className="status-bar__battery">
          <span className="status-bar__battery-level">74</span>
        </span>
      </span>
    </div>
  )
}
