// AutoPilot PWA Service Worker
const CACHE_VERSION = 'autopilot-v1';
const STATIC_ASSETS = [
  '/app/static/manifest.json',
  '/app/static/icon-192.png',
  '/app/static/icon-512.png',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_VERSION).then((cache) => cache.addAll(STATIC_ASSETS).catch(() => {}))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_VERSION).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

// Network-first для всего, fallback на кэш и оффлайн-страницу
self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  // Не кэшируем websockets и API стримы Streamlit
  if (url.pathname.includes('/_stcore/stream') || url.pathname.includes('/_stcore/health')) return;

  event.respondWith(
    fetch(req)
      .then((res) => {
        if (res && res.status === 200 && res.type === 'basic') {
          const clone = res.clone();
          caches.open(CACHE_VERSION).then((c) => c.put(req, clone)).catch(() => {});
        }
        return res;
      })
      .catch(() =>
        caches.match(req).then((cached) =>
          cached || new Response(
            '<!doctype html><meta charset=utf-8><title>Оффлайн</title>' +
            '<style>body{font-family:system-ui;background:#0F0F1A;color:#e2e8f0;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;text-align:center}h1{font-size:64px;margin:0}p{color:#94a3b8}</style>' +
            '<div><h1>📡</h1><h2>Нет интернета</h2><p>AutoPilot вернётся, как только сеть станет доступной</p></div>',
            { headers: { 'Content-Type': 'text/html; charset=utf-8' } }
          )
        )
      )
  );
});
