const CACHE_NAME = 'spendwise-shell-v5';
const NEVER_CACHE_PATHS = [
  '/',
  '/signup/',
  '/signup/verify/',
  '/login/',
  '/logout/',
  '/forgot-password/',
  '/forgot-password/verify/',
  '/forgot-password/reset/',
];

const isNeverCacheRequest = (request) => {
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return false;
  if (request.mode === 'navigate') return true;
  return NEVER_CACHE_PATHS.some((path) => url.pathname === path);
};

self.addEventListener('install', (event) => {
  event.waitUntil(self.skipWaiting());
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(
        keys
          .filter((key) => key.startsWith('spendwise-shell-') && key !== CACHE_NAME)
          .map((key) => caches.delete(key))
      ))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const { request } = event;
  if (request.method !== 'GET') return;

  if (isNeverCacheRequest(request)) {
    event.respondWith(fetch(request));
    return;
  }

  event.respondWith(
    fetch(request)
      .then((response) => {
        if (!response || !response.ok || response.type !== 'basic') {
          return response;
        }
        const clone = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
        return response;
      })
      .catch(() => caches.match(request))
  );
});
