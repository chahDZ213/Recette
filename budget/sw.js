// budget/sw.js — service worker d'échéance. (portée /budget/)
// Réseau d'abord, cache de secours, et réception des notifications quotidiennes.
const CACHE = "echeance-v1";
const SHELL = ["/budget/", "/budget/index.html", "/budget/manifest.json"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).catch(() => {}));
  self.skipWaiting();
});

self.addEventListener("activate", (e) => {
  e.waitUntil(Promise.all([
    caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== CACHE).map((k) => caches.delete(k)))),
    self.clients.claim(),
  ]));
});

self.addEventListener("fetch", (e) => {
  if (e.request.method !== "GET") return;                       // ne pas intercepter les appels API
  if (!e.request.url.includes("/budget/")) return;              // la portée de mise. reste à mise.
  e.respondWith(
    fetch(e.request)
      .then((res) => {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(e.request, copy)).catch(() => {});
        return res;
      })
      .catch(() => caches.match(e.request).then((r) => r || caches.match("/budget/")))
  );
});

// --- Notification quotidienne (envoyée par api/budget-push.js) ---
self.addEventListener("push", (e) => {
  let data = {};
  try { data = e.data ? e.data.json() : {}; } catch (_) { data = { body: e.data ? e.data.text() : "" }; }
  e.waitUntil(self.registration.showNotification(data.title || "échéance.", {
    body: data.body || "Voici tes échéances du jour.",
    icon: "/budget/icon-192.png",
    badge: "/budget/icon-192.png",
    vibrate: [140, 70, 140],
    tag: data.tag || "echeance-jour",
    renotify: true,
    data: { url: data.url || "/budget/" },
  }));
});

self.addEventListener("notificationclick", (e) => {
  e.notification.close();
  const url = (e.notification.data && e.notification.data.url) || "/budget/";
  e.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((cs) => {
      for (const c of cs) {
        if (c.url.includes("/budget/") && "focus" in c) return c.focus();
      }
      if (self.clients.openWindow) return self.clients.openWindow(url);
    })
  );
});
