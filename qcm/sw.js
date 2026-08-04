/* Service worker de l'appli de révision : cache-first, tout est statique. */
const CACHE = 'permisb-verif-v1';
const FICHIERS = [
  './',
  './index.html',
  './questions.js',
  './manifest.json'
];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(FICHIERS)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys()
      .then((noms) => Promise.all(noms.filter((n) => n !== CACHE).map((n) => caches.delete(n))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (e) => {
  if (e.request.method !== 'GET') return;
  e.respondWith(
    caches.match(e.request).then((hit) => hit || fetch(e.request).then((rep) => {
      // On ne met en cache que nos propres fichiers.
      if (rep.ok && new URL(e.request.url).origin === self.location.origin) {
        const copie = rep.clone();
        caches.open(CACHE).then((c) => c.put(e.request, copie));
      }
      return rep;
    }).catch(() => caches.match('./index.html')))
  );
});
