# Banda de escaneo

Demo de la animación de una banda que recorre una tarjeta de arriba abajo y de
vuelta, y que **se oculta al cruzar una franja** concreta para reaparecer al
salir de ella. Un solo archivo, sin dependencias: abre `banda-escaner.html` en
cualquier navegador.

La tarjeta es de muestra a propósito — institución inventada, datos en cero y
un bloque de barras decorativo que no codifica nada. Lo que interesa aquí es la
técnica, que se aplica igual a cualquier diseño.

## Cómo funciona

**El recorrido.** La banda se anima con `translateY` entre dos posiciones y la
dirección `alternate` se encarga del regreso, así que un solo par de keyframes
cubre ida y vuelta:

```css
.banda { animation: barrido 4.4s linear infinite alternate; }
@keyframes barrido {
  from { transform: translateY(-34px); }   /* justo encima de la tarjeta */
  to   { transform: translateY(740px); }   /* justo debajo */
}
```

Con `linear` el giro en los extremos es seco. Cambiando a `ease-in-out` la
banda frena al llegar y arranca suave, que es otra sensación: vale la pena
probar las dos.

**La desaparición.** El truco es no tocar la banda: la que lleva la máscara es
la capa que la contiene. La máscara es opaca arriba y abajo y transparente en
la franja del medio, así que mientras la banda pasa por ahí no se dibuja.

```css
.capa-banda {
  mask-image: linear-gradient(
    to bottom,
    #000 0 560px,                /* visible */
    transparent 560px 660px,     /* franja oculta */
    #000 660px 100%              /* visible */
  );
}
```

Los topes repetidos (`560px 560px`) son lo que produce un corte duro en vez de
un degradado. Como la máscara vive en la capa y no en la banda, el movimiento
no se entera de nada: no hay que sincronizar la animación con la franja, ni
calcular cuándo apagarla. Se recorta sola, y además se ve el recorte progresivo
al entrar y al salir, que es lo que hace creíble el efecto.

Todas las medidas están como variables CSS en `:root`, así que la franja oculta,
el alto de la banda y la duración se ajustan en un solo sitio.

## Verificación

Muestreando el color de la banda cuadro a cuadro a lo largo de un ciclo
completo: baja en pasos regulares, se recorta al tocar los 560px, desaparece por
completo dentro de la franja, reaparece pasados los 660px y el regreso repite
las mismas posiciones en orden inverso.

## Accesibilidad

Con `prefers-reduced-motion: reduce` la banda se queda quieta. Es una animación
continua y en bucle, del tipo que conviene poder desactivar.
