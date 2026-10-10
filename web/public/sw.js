/* BUSI demo service worker — app shell + ONNX model, versioned by models/current.json cache_key. */
/* eslint-disable no-restricted-globals */

const SHELL_PREFIX = 'busi-shell-'
const MODEL_PREFIX = 'busi-unet-'

self.addEventListener('install', (event) => {
  event.waitUntil(
    (async () => {
      const scope = self.registration.scope
      const currentUrl = new URL('models/current.json', scope).href
      const curRes = await fetch(currentUrl, { cache: 'no-cache' })
      if (!curRes.ok) throw new Error(`SW: current.json ${curRes.status}`)
      const cur = await curRes.json()
      const cacheKey = cur.cache_key || `busi-unet-v${cur.version}`
      const modelPath = `${String(cur.path || '').replace(/^\//, '')}/busi_unet.onnx`
      const shellName = SHELL_PREFIX + cacheKey
      const modelName = cacheKey

      const shellUrls = [
        scope,
        new URL('index.html', scope).href,
        new URL('manifest.webmanifest', scope).href,
        new URL('favicon.svg', scope).href,
        new URL('models/current.json', scope).href,
        new URL('ort/ort-wasm-simd-threaded.jsep.mjs', scope).href,
        new URL('ort/ort-wasm-simd-threaded.jsep.wasm', scope).href,
        new URL('ort/ort-wasm-simd-threaded.mjs', scope).href,
        new URL('ort/ort-wasm-simd-threaded.wasm', scope).href,
      ]

      const shell = await caches.open(shellName)
      await Promise.all(
        shellUrls.map(async (url) => {
          try {
            const res = await fetch(url, { cache: 'reload' })
            if (res.ok) await shell.put(url, res.clone())
          } catch {
            /* optional asset */
          }
        }),
      )

      const modelUrl = new URL(modelPath, scope).href
      try {
        const modelCache = await caches.open(modelName)
        const existing = await modelCache.match(modelUrl)
        if (!existing) {
          const res = await fetch(modelUrl)
          if (res.ok) {
            await modelCache.put(
              modelUrl,
              new Response(await res.arrayBuffer(), {
                headers: { 'Content-Type': 'application/octet-stream' },
              }),
            )
          }
        }
      } catch {
        /* model may be large; app still caches on first inference */
      }

      await self.skipWaiting()
    })(),
  )
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    (async () => {
      const scope = self.registration.scope
      let cacheKey = ''
      try {
        const curRes = await fetch(new URL('models/current.json', scope).href, {
          cache: 'no-cache',
        })
        if (curRes.ok) {
          const cur = await curRes.json()
          cacheKey = cur.cache_key || `busi-unet-v${cur.version}`
        }
      } catch {
        /* keep all if we cannot read pointer */
      }
      const keep = new Set()
      if (cacheKey) {
        keep.add(SHELL_PREFIX + cacheKey)
        keep.add(cacheKey)
      }
      const keys = await caches.keys()
      await Promise.all(
        keys.map((k) => {
          const isOurs = k.startsWith(SHELL_PREFIX) || k.startsWith(MODEL_PREFIX)
          if (isOurs && cacheKey && !keep.has(k)) return caches.delete(k)
          return Promise.resolve(false)
        }),
      )
      await self.clients.claim()
    })(),
  )
})

self.addEventListener('fetch', (event) => {
  const req = event.request
  if (req.method !== 'GET') return
  const url = new URL(req.url)
  if (url.origin !== self.location.origin) return

  event.respondWith(
    (async () => {
      const cached = await caches.match(req)
      if (cached) return cached

      // Navigation: serve cached shell index when offline
      if (req.mode === 'navigate') {
        const scope = self.registration.scope
        const shellHit =
          (await caches.match(new URL('index.html', scope).href)) ||
          (await caches.match(scope))
        if (shellHit) return shellHit
      }

      try {
        const res = await fetch(req)
        if (res.ok && shouldRuntimeCache(url)) {
          const keys = await caches.keys()
          const shell = keys.find((k) => k.startsWith(SHELL_PREFIX))
          if (shell) {
            const cache = await caches.open(shell)
            void cache.put(req, res.clone())
          }
        }
        return res
      } catch (err) {
        const fallback =
          (await caches.match(req)) ||
          (req.mode === 'navigate'
            ? await caches.match(new URL('index.html', self.registration.scope).href)
            : undefined)
        if (fallback) return fallback
        throw err
      }
    })(),
  )
})

function shouldRuntimeCache(url) {
  const path = url.pathname
  return (
    path.endsWith('.js') ||
    path.endsWith('.css') ||
    path.endsWith('.wasm') ||
    path.endsWith('.mjs') ||
    path.endsWith('.svg') ||
    path.endsWith('.png') ||
    path.endsWith('.woff2') ||
    path.includes('/assets/')
  )
}
