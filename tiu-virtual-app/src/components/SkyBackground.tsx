/**
 * Fondo ilustrado: cielo claro con nubes planas y, al pie, la silueta del
 * campus (arboles a la izquierda, edificios a la derecha) que asoma a los
 * costados del carnet.
 *
 * El viewBox usa el mismo sistema de coordenadas que el diseno (402 x 874),
 * y con "xMidYMax slice" se recorta sin deformarse en pantallas mas altas.
 */
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
        <linearGradient id="sky-gradient" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#F7F9FC" />
          <stop offset="0.55" stopColor="#F4F6FD" />
          <stop offset="1" stopColor="#EDF0FC" />
        </linearGradient>
        {/* Nube base: dos bultos y una panza recta, como en el original. */}
        <symbol id="cloud" viewBox="0 0 100 44">
          <path
            d="M6 44h88a6 6 0 0 0 0-12h-6a17 17 0 0 0-27-17 13 13 0 0 0-21 6 12 12 0 0 0-17 11 6 6 0 0 0-17 4 6 6 0 0 0 0 8Z"
            fill="currentColor"
          />
        </symbol>
      </defs>

      <rect width="402" height="874" fill="url(#sky-gradient)" />

      {/* Silueta del campus: apenas se asoma a los lados del carnet. */}
      <g className="sky__skyline">
        <rect x="-10" y="742" width="422" height="132" fill="#EEF1FC" />
        <g fill="#EAEEFB">
          <rect x="344" y="596" width="74" height="150" rx="6" />
          <rect x="306" y="646" width="46" height="100" rx="5" />
          <rect x="378" y="548" width="28" height="60" rx="4" />
          <rect x="-16" y="664" width="52" height="82" rx="5" />
        </g>
        <g fill="#F3F5FD">
          <rect x="356" y="616" width="9" height="13" rx="2" />
          <rect x="374" y="616" width="9" height="13" rx="2" />
          <rect x="392" y="616" width="9" height="13" rx="2" />
          <rect x="356" y="646" width="9" height="13" rx="2" />
          <rect x="374" y="646" width="9" height="13" rx="2" />
          <rect x="392" y="646" width="9" height="13" rx="2" />
          <rect x="314" y="668" width="8" height="12" rx="2" />
          <rect x="332" y="668" width="8" height="12" rx="2" />
        </g>
        {/* Arboles */}
        <g fill="#E6EBFA">
          <circle cx="14" cy="586" r="30" />
          <circle cx="-10" cy="618" r="26" />
          <circle cx="36" cy="626" r="22" />
          <circle cx="4" cy="684" r="28" />
          <circle cx="394" cy="700" r="22" />
        </g>
        <g fill="#EEF1FC">
          <rect x="9" y="612" width="7" height="134" rx="3" />
          <rect x="1" y="700" width="6" height="46" rx="3" />
        </g>
      </g>

      {/* Nubes, con las medidas de la pantalla original */}
      <g className="sky__clouds" color="#EAEDFB">
        <use href="#cloud" x="44" y="374" width="50" height="27" />
        <use href="#cloud" x="333" y="355" width="72" height="41" />
        <use href="#cloud" x="-8" y="428" width="30" height="23" />
        <use href="#cloud" x="154" y="446" width="30" height="17" />
        <use href="#cloud" x="294" y="459" width="48" height="22" />
      </g>

    </svg>
  )
}
