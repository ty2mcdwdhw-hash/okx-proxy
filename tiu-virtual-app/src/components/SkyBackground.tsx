/**
 * Fondo ilustrado: cielo con nubes que se desplazan y, al pie, la silueta del
 * campus que asoma a los costados del carnet.
 *
 * Las nubes, su recorrido y su velocidad salen del video de referencia:
 *
 * - El patron se repite exacto cada 4.00 s (autocorrelacion del fondo: la
 *   diferencia entre dos fotogramas separados 4 s es 0.007 sobre 255).
 * - Se desplazan hacia la izquierda a 131 px/s, en linea recta (siguiendo una
 *   nube cuadro a cuadro el ajuste lineal deja 0.3 px de error).
 * - 4 s x 131 px/s = 524 px: ese es el ancho del patron. Reconstruyendolo a
 *   partir de los fotogramas aparecen las seis nubes de CLOUDS.
 *
 * El grupo lleva dos copias del patron, separadas justo 524 px, y la animacion
 * lo corre esa misma distancia: al terminar, la segunda copia queda donde
 * estaba la primera y el ciclo empalma sin salto.
 */

/** Ancho del patron que se repite, en unidades del diseno. */
const TILE = 524

/** Proporcion de la silueta (viewBox 100 x 31.5). */
const CLOUD_RATIO = 100 / 31.5

/** Nubes del patron: x/y de la esquina superior izquierda y ancho. */
const CLOUDS = [
  { x: 32.9, y: 420.6, w: 90.3 },
  { x: 151.8, y: 373.8, w: 57.7 },
  { x: 272.2, y: 453.0, w: 18.0 },
  { x: 308.2, y: 404.0, w: 37.3 },
  { x: 403.2, y: 461.4, w: 43.3 },
  { x: 445.8, y: 360.0, w: 66.7 },
]

export function SkyBackground() {
  return (
    <svg
      className="sky"
      viewBox="0 0 402 874"
      preserveAspectRatio="xMidYMax slice"
      aria-hidden="true"
      focusable="false"
    >
      <defs>
        {/* Silueta trazada del borde de una nube del video (98.6% de
            coincidencia con el original). */}
        <symbol id="cloud" viewBox="0 0 100 31.5">
          <path d="M0 31.5L0.0 26.8C0.4 26.1 1.7 24.0 2.6 22.8C3.6 21.7 4.7 20.7 5.6 20.1C6.6 19.4 7.3 19.2 8.2 19.0C9.2 18.8 10.2 18.7 11.2 18.8C12.2 18.9 13.3 19.3 14.2 19.6C15.2 20.0 15.9 20.9 16.9 20.9C17.8 20.9 18.9 20.8 19.9 19.5C20.8 18.3 21.9 14.8 22.8 13.3C23.8 11.8 24.5 11.2 25.5 10.4C26.4 9.6 27.5 8.9 28.5 8.4C29.4 8.0 30.1 7.8 31.1 7.5C32.0 7.3 33.1 7.1 34.1 7.0C35.1 7.0 36.1 7.2 37.1 7.4C38.0 7.5 38.8 7.7 39.7 8.0C40.6 8.4 41.7 9.6 42.7 9.5C43.7 9.5 44.8 8.7 45.7 7.9C46.6 7.1 47.4 5.7 48.3 4.7C49.3 3.8 50.4 3.0 51.3 2.4C52.2 1.7 53.0 1.4 53.9 1.0C54.9 0.6 55.9 0.3 56.9 0.1C57.9 -0.0 59.0 0.0 59.9 0.0C60.9 -0.0 61.6 0.0 62.5 0.0C63.5 0.0 64.5 -0.0 65.5 0.0C66.5 0.0 67.6 0.0 68.5 0.2C69.5 0.3 70.2 0.5 71.2 0.9C72.1 1.3 73.2 1.9 74.2 2.5C75.1 3.0 75.8 3.5 76.8 4.3C77.7 5.2 78.8 6.1 79.8 7.4C80.8 8.8 81.8 10.3 82.8 12.5C83.7 14.6 84.5 18.6 85.4 20.3C86.3 22.0 87.4 22.1 88.4 22.5C89.4 22.8 90.4 22.4 91.4 22.6C92.3 22.7 93.1 22.9 94.0 23.4C94.9 23.8 96.0 24.3 97.0 25.3C98.0 26.2 99.5 28.3 100.0 28.9L100 31.5Z" fill="currentColor" />
        </symbol>
      </defs>

      <rect width="402" height="874" fill="#F7F9FC" />

      {/* Suelo: por debajo de ~648 el fondo es de un tono parejo. */}
      <rect y="648" width="402" height="226" fill="#F0F3FC" />

      {/* Campus: solo se asoma a los lados del carnet. */}
      <g className="sky__skyline">
        <g fill="#E8EBFC">
          <rect x="340" y="574" width="78" height="74" rx="4" />
          <rect x="300" y="602" width="44" height="46" rx="4" />
          <rect x="-16" y="596" width="52" height="52" rx="4" />
        </g>
        <g fill="#DCE0FB">
          <rect x="352" y="562" width="54" height="86" rx="4" />
          <circle cx="12" cy="560" r="30" />
          <circle cx="-10" cy="592" r="26" />
          <circle cx="34" cy="600" r="20" />
          <circle cx="6" cy="624" r="24" />
        </g>
        <g fill="#C0C7FA">
          <rect x="386" y="606" width="9" height="12" rx="2" />
          <rect x="368" y="606" width="9" height="12" rx="2" />
          <rect x="386" y="628" width="9" height="12" rx="2" />
          <rect x="368" y="628" width="9" height="12" rx="2" />
          <rect x="9" y="586" width="7" height="62" rx="3" />
        </g>
      </g>

      {/* Nubes: dos copias del patron, desplazandose juntas. */}
      <g className="sky__clouds" color="#C8CFFB">
        {[0, TILE].map((offset) =>
          CLOUDS.map((cloud) => (
            <use
              key={`${offset}-${cloud.x}`}
              href="#cloud"
              x={cloud.x + offset}
              y={cloud.y}
              width={cloud.w}
              height={cloud.w / CLOUD_RATIO}
            />
          )),
        )}
      </g>
    </svg>
  )
}
