/**
 * Datos que muestra el carnet.
 *
 * Este proyecto es una RECREACION de interfaz con fines de practica: no se
 * conecta a ningun sistema academico ni valida nada. Cambia estos valores
 * para adaptar la pantalla.
 */
export type StudentCard = {
  /** Nombres, tal como se ven en la primera linea roja del carnet. */
  firstNames: string
  /** Apellidos (segunda linea roja). */
  lastNames: string
  studentCode: string
  bannerId: string
  program: string
  campus: string
  /** Ruta de la foto circular (relativa a /public). */
  photo: string
}

export type AppConfig = {
  /** Titulo de la barra superior. */
  title: string
  student: StudentCard
  /** Zona horaria del reloj. Usa undefined para la del dispositivo. */
  timeZone: string | undefined
  locale: string
  /**
   * Muestra el sello "SIMULACION" al pie de la pantalla.
   * Dejalo activado: esta pantalla imita un documento de identidad y el sello
   * es lo que la mantiene como demo y no como una credencial falsa.
   */
  showDemoBadge: boolean
}

export const config: AppConfig = {
  title: 'TIU VIRTUAL',
  // Datos de ejemplo: cambialos por los tuyos (y reemplaza public/avatar.jpg).
  student: {
    firstNames: 'NOMBRE APELLIDO',
    lastNames: 'A*** B***',
    studentCode: 'U000000000',
    bannerId: 'N00000000',
    program: 'ING. DE SOFTWARE',
    campus: 'Campus Ejemplo',
    photo: './avatar.jpg',
  },
  timeZone: 'America/Lima',
  locale: 'es-PE',
  showDemoBadge: true,
}
