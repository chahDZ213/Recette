// Service worker StudyPilot : app utilisable hors ligne (l'IA nécessite le réseau).
const V = "studypilot-v1";
const FILES = ["./", "index.html", "styles.css", "app.js", "manifest.json", "icon.svg",
  "engine/curriculum.js", "engine/srs.js", "engine/grades.js", "engine/planner.js", "engine/errors.js", "engine/store.js", "/vendor/supabase-js-2.117.3.js"];
self.addEventListener("install", (e) => { e.waitUntil(caches.open(V).then((c) => c.addAll(FILES))); self.skipWaiting(); });
self.addEventListener("activate", (e) => { e.waitUntil(caches.keys().then((k) => Promise.all(k.filter((x) => x.startsWith("studypilot-") && x !== V).map((x) => caches.delete(x))))); self.clients.claim(); });
self.addEventListener("fetch", (e) => {
  const u = new URL(e.request.url);
  if (e.request.method !== "GET" || u.origin !== location.origin || u.pathname.startsWith("/api/")) return;
  e.respondWith(fetch(e.request).then((r) => { const c = r.clone(); caches.open(V).then((x) => x.put(e.request, c)); return r; }).catch(() => caches.match(e.request)));
});
