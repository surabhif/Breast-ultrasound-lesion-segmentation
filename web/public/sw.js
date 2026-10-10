/* BUSI demo service worker — app shell + ONNX model, versioned by models/current.json cache_key. */
/* eslint-disable no-restricted-globals */

const SHELL_PREFIX = 'busi-shell-'
/** Bump when shell fetch/nav strategy changes so activate purges hijacked caches. */
const SHELL_REVISION = 'v2'
const MODEL_PREFIX = 'busi-unet-'

function shellCacheName(cacheKey) {
  return `${SHELL_PREFIX}${SHELL_REVISION}-${cacheKey}`
}

/** True when the last path segment looks like a real file (report.pdf, video.mp4, …). */
function pathnameHasExtension(pathname) {
  const seg = pathname.split('/').filter(Boolean).pop() || ''
  return /\.[a-zA-Z0-9]{1,12}$/.test(seg)
}

function isScopeRootOrIndex(url, scope) {
  const scopeUrl = new URL(scope)
  const indexUrl = new URL('index.html', scope)
  return (
    url.pathname === scopeUrl.pathname ||
    url.pathname === indexUrl.pathname ||
    url.href === scopeUrl.href ||
    url.href === indexUrl.href
  )
}

/** Model weights, ORT WASM, and Vite hashed /assets — safe to serve cache-first. */
function isCacheFirstAsset(url) {
  const p = url.pathname
  if (p.includes('/assets/')) return true
  if (p.endsWith('.onnx')) return true
  if (p.endsWith('.wasm')) return true
  if (p.includes('/ort/') && (p.endsWith('.mjs') || p.endsWith('.js'))) return true
  return false
}

async function openCurrentShellCache() {
  const keys = await caches.keys()
  const shell = keys.find((k) => k.startsWith(`${SHELL_PREFIX}${SHELL_REVISION}-`))
  return shell ? caches.open(shell) : null
}

async function putInShellCache(req, res) {
  try {
    const cache = await openCurrentShellCache()
    if (cache) await cache.put(req, res.clone())
  } catch {
    /* ignore quota / abort */
  }
}

async function cachedAppShell(scope) {
  return (
    (await caches.match(new URL('index.html', scope).href)) ||
    (await caches.match(scope)) ||
    null
  )
}

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
      const shellName = shellCacheName(cacheKey)
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
        keep.add(shellCacheName(cacheKey))
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

  const scope = self.registration.scope
  const navigate = req.mode === 'navigate'
  const spaNav = navigate && !pathnameHasExtension(url.pathname)
  const shellDoc = isScopeRootOrIndex(url, scope)
  const cacheFirst = isCacheFirstAsset(url)

  event.respondWith(
    (async () => {
      // Cache-first: ONNX, WASM, hashed /assets only.
      if (cacheFirst) {
        const cached = await caches.match(req)
        if (cached) return cached
        const res = await fetch(req)
        if (res.ok) {
          try {
            const keys = await caches.keys()
            const bucket =
              keys.find((k) => k.startsWith(`${SHELL_PREFIX}${SHELL_REVISION}-`)) ||
              keys.find((k) => k.startsWith(MODEL_PREFIX))
            if (bucket) {
              const cache = await caches.open(bucket)
              await cache.put(req, res.clone())
            }
          } catch {
            /* ignore */
          }
        }
        return res
      }

      // Network-first for SPA navigations and the app shell documents (index / scope root).
      // Shell fallback only when the network fails, and never for real files (.pdf, .mp4, …).
      if (spaNav || shellDoc) {
        try {
          const res = await fetch(req)
          if (res.ok) await putInShellCache(req, res)
          return res
        } catch (err) {
          const shell = await cachedAppShell(scope)
          if (shell) return shell
          const cached = await caches.match(req)
          if (cached) return cached
          throw err
        }
      }

      // File requests (including navigate to report.pdf / video / images): network, then
      // that URL's own cache entry — never the HTML shell.
      try {
        const res = await fetch(req)
        return res
      } catch (err) {
        const cached = await caches.match(req)
        if (cached) return cached
        throw err
      }
    })(),
  )
})
