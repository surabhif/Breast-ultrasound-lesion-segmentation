import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

describe('PWA / model cache key wiring', () => {
  it('current.json cache_key matches busi-unet versioned pattern used by SW + MODEL_CACHE', () => {
    const curPath = resolve(__dirname, '../../public/models/current.json')
    const cur = JSON.parse(readFileSync(curPath, 'utf8')) as {
      version: string
      cache_key: string
      path: string
      sha256: string
    }
    expect(cur.cache_key).toMatch(/^busi-unet-v/)
    expect(cur.cache_key).toContain(cur.version)
    expect(cur.cache_key).toContain(cur.sha256.slice(0, 8))
  })

  it('service worker purges old busi- caches when cache_key changes', () => {
    const sw = readFileSync(resolve(__dirname, '../../public/sw.js'), 'utf8')
    expect(sw).toContain('busi-shell-')
    expect(sw).toContain('SHELL_REVISION')
    expect(sw).toContain("SHELL_REVISION = 'v2'")
    expect(sw).toContain('busi-unet-')
    expect(sw).toContain('cache_key')
    expect(sw).toContain('caches.delete')
    expect(sw).toContain('models/current.json')
    expect(sw).toContain('busi_unet.onnx')
    expect(sw).toContain('skipWaiting')
    expect(sw).toContain('clients.claim')
    expect(sw).toContain('pathnameHasExtension')
    expect(sw).toContain('isCacheFirstAsset')
    // Navigations / shell docs must try the network before any HTML fallback.
    expect(sw).toMatch(/spaNav \|\| shellDoc/)
    expect(sw).toContain('cachedAppShell')
  })

  it('manifest exists and uses brand teal theme', () => {
    const man = JSON.parse(
      readFileSync(resolve(__dirname, '../../public/manifest.webmanifest'), 'utf8'),
    ) as { theme_color: string; name: string; display: string }
    expect(man.theme_color).toBe('#297373')
    expect(man.display).toBe('standalone')
    expect(man.name.toLowerCase()).toMatch(/ultrasound/)
  })
})
