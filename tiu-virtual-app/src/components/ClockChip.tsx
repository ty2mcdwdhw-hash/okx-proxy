import { formatClock, formatLongDate } from '../lib/datetime'

/**
 * Reloj vivo + fecha. En la app original el segundero es justamente lo que
 * distingue la pantalla abierta de una captura de pantalla.
 */
export function ClockChip({ now }: { now: Date }) {
  return (
    <div className="clock">
      <div className="clock__chip">
        <time className="clock__time" dateTime={now.toISOString()}>
          {formatClock(now)}
        </time>
      </div>
      <p className="clock__date">{formatLongDate(now)}</p>
    </div>
  )
}
