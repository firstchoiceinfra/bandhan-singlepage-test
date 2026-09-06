// Bandhan.com — minimal service worker
// Keeps things safe for a dynamic Streamlit app: we do NOT aggressively
// cache pages (Streamlit's content changes per session), we only let the
// browser register a worker so "Add to Home Screen" / install prompts work,
// and cache the app icon so it shows instantly once installed.

const CACHE_NAME = "bandhan-shell-v1";
const SHELL_FILES = [
  "app/static/icon-192.png",
  "app/static/icon-512.png"
];

self.addEventListener("install", (event) => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL_FILES).catch(() => {}))
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

// Pass-through fetch: don't intercept normal navigation/API calls,
// since Streamlit relies on live WebSocket + dynamic responses.
self.addEventListener("fetch", (event) => {
  if (SHELL_FILES.some((f) => event.request.url.includes(f))) {
    event.respondWith(
      caches.match(event.request).then((cached) => cached || fetch(event.request))
    );
  }
});
