/* Service worker minimo: deja la app disponible sin conexion.

   Estrategias, segun que tan estable es cada archivo:
   - documento: red primero (asi una version nueva reemplaza a la anterior),
     con la copia en cache como respaldo si no hay senal.
   - /assets/: cache primero. Vite les pone un hash en el nombre, asi que un
     archivo con ese nombre nunca cambia de contenido.
   - el resto (avatar.jpg, iconos, manifest): red primero. Conservan el mismo
     nombre entre versiones, y si se cachearan para siempre, cambiar la foto y
     volver a publicar no se notaria hasta limpiar el navegador. */
const CACHE = 'tiu-virtual-v2'

self.addEventListener('install', (event) => {
  self.skipWaiting()
  event.waitUntil(caches.open(CACHE).then((cache) => cache.add('./')))
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== CACHE).map((key) => caches.delete(key))))
      .then(() => self.clients.claim()),
  )
})

const save = (request, response) => {
  const copy = response.clone()
  caches.open(CACHE).then((cache) => cache.put(request, copy))
  return response
}

self.addEventListener('fetch', (event) => {
  const { request } = event
  if (request.method !== 'GET' || new URL(request.url).origin !== self.location.origin) return

  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then((response) => save('./', response))
        .catch(() => caches.match('./').then((cached) => cached ?? Response.error())),
    )
    return
  }

  const immutable = new URL(request.url).pathname.includes('/assets/')

  event.respondWith(
    immutable
      ? caches.match(request).then((cached) => cached ?? fetch(request).then((r) => save(request, r)))
      : fetch(request)
          .then((response) => save(request, response))
          .catch(() => caches.match(request).then((cached) => cached ?? Response.error())),
  )
})
