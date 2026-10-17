// sw.js — service worker minimal (network-first)
const CACHE = "mise-v65";

self.addEventListener("install", (e) => {
  // supabase-js est mis en cache dès l'installation : sans lui, aucune
  // connexion au compte n'est possible, même avec la page déjà chargée.
  e.waitUntil(
    caches.open(CACHE)
      .then((c) => c.addAll(["/", "/index.html", "/vendor/supabase-js-2.117.3.js"]))
      .catch(() => {})
  );
  self.skipWaiting();
});

self.addEventListener("activate", (e) => {
  e.waitUntil(Promise.all([caches.keys().then(ks=>Promise.all(ks.filter(k=>k!==CACHE).map(k=>caches.delete(k)))), self.clients.claim()]));
});

self.addEventListener("fetch", (e) => {
  // Ne pas intercepter les appels API (POST vers /api/extract)
  if (e.request.method !== "GET") return;

  /* Ne jamais intercepter ce qui ne vient pas de notre domaine. Une réponse
     d'un autre domaine est opaque : cache.put() la refuse, et sur Safari le
     clone jamais consommé peut bloquer la réponse — un script tiers finit
     alors par arriver vide, sans la moindre erreur visible. Le navigateur
     gère très bien ces requêtes tout seul. */
  let sameOrigin = false;
  try { sameOrigin = new URL(e.request.url).origin === self.location.origin; } catch (_) {}
  if (!sameOrigin) return;

  e.respondWith(
    fetch(e.request)
      .then((res) => {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(e.request, copy)).catch(() => {});
        return res;
      })
      .catch(() =>
        caches.match(e.request).then((r) => {
          if (r) return r;
          // Repli sur l'accueil UNIQUEMENT pour une navigation de page — jamais pour un
          // script/module/asset, sinon on renverrait du HTML à la place d'un JS et l'app
          // se retrouverait figée (aucun bouton ne réagit). Corrige le bug de l'app 3D /print/.
          if (e.request.mode === "navigate") return caches.match("/");
          return Response.error();
        })
      )
  );
});

// --- Notifications ---
self.addEventListener("push", (e) => {
  let data = {};
  try { data = e.data ? e.data.json() : {}; } catch (_) { data = { body: e.data ? e.data.text() : "" }; }
  const title = data.title || "mise.";
  const body = data.body || "C'est prêt ! 🔔";
  e.waitUntil(self.registration.showNotification(title, {
    body,
    icon: "/icon-192.png",
    badge: "/icon-192.png",
    vibrate: [200, 100, 200],
    tag: data.tag || "mise-timer",
    data: { url: data.url || "/" },
    actions: [{ action: "open", title: "📷 Ajouter une photo" }],
  }));
});

self.addEventListener("notificationclick", (e) => {
  e.notification.close();
  const url = (e.notification.data && e.notification.data.url) || "/";
  e.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((cs) => {
      for (const c of cs) {
        if ("focus" in c) { c.focus(); c.postMessage({ type: "open-photo", url }); return; }
      }
      if (self.clients.openWindow) return self.clients.openWindow(url);
    })
  );
});
