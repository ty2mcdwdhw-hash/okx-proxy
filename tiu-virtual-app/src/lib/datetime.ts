import { config } from '../config/card'

/**
 * Abreviaturas tal como las muestra la app original ("Sept", no "Set"), para
 * que la fecha no dependa de como cada navegador resuelve el locale.
 */
const MONTHS = [
  'Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun',
  'Jul', 'Ago', 'Sept', 'Oct', 'Nov', 'Dic',
]

const WEEKDAYS = [
  'Domingo', 'Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado',
]

const clockFormatter = new Intl.DateTimeFormat('es-PE', {
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
  hour12: false,
  timeZone: config.timeZone,
})

/** Partes numericas de la fecha ya llevadas a la zona horaria configurada. */
const dateFormatter = new Intl.DateTimeFormat('en-US', {
  weekday: 'short',
  day: 'numeric',
  month: 'numeric',
  year: 'numeric',
  timeZone: config.timeZone,
})

const WEEKDAY_INDEX: Record<string, number> = {
  Sun: 0, Mon: 1, Tue: 2, Wed: 3, Thu: 4, Fri: 5, Sat: 6,
}

/** "08:46:38" */
export function formatClock(date: Date): string {
  // Algunos runtimes devuelven "24:00:00" a la medianoche; lo normalizamos.
  return clockFormatter.format(date).replace(/^24/, '00')
}

/** "Miércoles, 16 Sept 2026" */
export function formatLongDate(date: Date): string {
  const parts = dateFormatter.formatToParts(date)
  const get = (type: Intl.DateTimeFormatPartTypes) =>
    parts.find((part) => part.type === type)?.value ?? ''

  const weekday = WEEKDAYS[WEEKDAY_INDEX[get('weekday')] ?? date.getDay()]
  const month = MONTHS[Number(get('month')) - 1]

  return `${weekday}, ${get('day')} ${month} ${get('year')}`
}
