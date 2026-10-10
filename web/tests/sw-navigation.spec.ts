/**
 * Service worker must not hijack real files (report.pdf) with the SPA shell,
 * and must still serve the cached shell for offline SPA navigations.
 */
import { expect, test } from '@playwright/test'

async function waitForActiveServiceWorker(page: import('@playwright/test').Page) {
  await page.goto('./')
  await page.waitForFunction(async () => {
    if (!('serviceWorker' in navigator)) return false
    const reg = await navigator.serviceWorker.getRegistration()
    return Boolean(reg?.active || navigator.serviceWorker.controller)
  })
  // Claim + skipWaiting: one reload so this tab is controlled.
  await page.reload({ waitUntil: 'networkidle' })
  await page.waitForFunction(() => Boolean(navigator.serviceWorker.controller), null, {
    timeout: 60_000,
  })
}

test.describe('Service worker navigation', () => {
  test('online direct /report.pdf is application/pdf (not the HTML shell)', async ({ page }) => {
    test.setTimeout(120_000)
    await waitForActiveServiceWorker(page)

    const controlled = await page.evaluate(() => Boolean(navigator.serviceWorker.controller))
    expect(controlled).toBe(true)

    // Chromium may treat PDF navigation as a download; capture the network response
    // (which still goes through the active service worker) instead of relying on page.goto.
    const responsePromise = page.waitForResponse(
      (r) => r.url().includes('/report.pdf') && r.request().method() === 'GET',
      { timeout: 60_000 },
    )
    await page.goto('./report.pdf', { waitUntil: 'commit' }).catch((err: Error) => {
      if (!/Download is starting/i.test(err.message)) throw err
    })
    const res = await responsePromise
    expect(res.ok()).toBe(true)
    const ct = (res.headers()['content-type'] || '').toLowerCase()
    expect(ct, `content-type was ${ct}`).toMatch(/application\/pdf/)
    expect(ct).not.toMatch(/text\/html/)

    // Body may be unavailable after Chromium starts a PDF download; verify bytes via
    // a same-origin fetch that still goes through the controlling service worker.
    await page.goto('./')
    await page.waitForFunction(() => Boolean(navigator.serviceWorker.controller))
    const viaFetch = await page.evaluate(async () => {
      const r = await fetch(new URL('report.pdf', document.baseURI).href)
      const head = new Uint8Array(await r.arrayBuffer()).slice(0, 5)
      return {
        status: r.status,
        contentType: (r.headers.get('content-type') || '').toLowerCase(),
        magic: String.fromCharCode(...head),
      }
    })
    expect(viaFetch.status).toBe(200)
    expect(viaFetch.contentType).toMatch(/application\/pdf/)
    expect(viaFetch.contentType).not.toMatch(/text\/html/)
    expect(viaFetch.magic).toBe('%PDF-')
  })

  test('offline SPA navigation to /results still gets the HTML shell', async ({
    page,
    context,
  }) => {
    test.setTimeout(120_000)
    await waitForActiveServiceWorker(page)

    // Warm the shell (and /results deep-link fallback if present) while online.
    await page.goto('./results', { waitUntil: 'networkidle' })
    await expect(page.getByRole('heading', { name: /Results/i }).first()).toBeVisible()

    await context.setOffline(true)
    const res = await page.goto('./results', { waitUntil: 'domcontentloaded' })
    expect(res, 'offline /results response').toBeTruthy()
    const ct = (res!.headers()['content-type'] || '').toLowerCase()
    expect(ct).toMatch(/text\/html/)

    await expect(page.locator('#root')).toBeAttached()
    // Shell should boot the SPA even offline (cached assets + React Router).
    await expect(page.getByRole('heading', { name: /Results/i }).first()).toBeVisible({
      timeout: 30_000,
    })
  })
})
