#!/usr/bin/env node
/**
 * In-browser timing: single-view vs 2-view (orig + horizontal flip) soft-mask average.
 * Uses the existing __BUSI_PARITY__.runInference hook — no app UI changes.
 *
 * Usage (from repo root, after `cd web && npm run build`):
 *   node scripts/measure_tta_browser_time.mjs
 *
 * Writes browser_timing into results/tta_averaging.json when present.
 */
import { createRequire } from 'node:module'
import { spawn } from 'node:child_process'
import { readFileSync, writeFileSync, existsSync } from 'node:fs'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const REPO = resolve(__dirname, '..')
const WEB = resolve(REPO, 'web')
const require = createRequire(resolve(WEB, 'package.json'))
const { chromium } = require('playwright')
const RESULTS = resolve(REPO, 'results/tta_averaging.json')
const PORT = 4177

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms))
}

async function waitForHttp(url, tries = 60) {
  for (let i = 0; i < tries; i++) {
    try {
      const res = await fetch(url)
      if (res.ok || res.status === 404) return
    } catch {
      // retry
    }
    await sleep(500)
  }
  throw new Error(`Server did not start: ${url}`)
}

async function main() {
  if (!existsSync(resolve(WEB, 'dist/index.html'))) {
    console.error('Missing web/dist — run: cd web && npm run build')
    process.exit(1)
  }

  const preview = spawn(
    'npx',
    ['vite', 'preview', '--host', '127.0.0.1', '--port', String(PORT)],
    { cwd: WEB, stdio: ['ignore', 'pipe', 'pipe'] },
  )
  preview.stderr.on('data', (d) => process.stderr.write(d))
  try {
    await waitForHttp(`http://127.0.0.1:${PORT}/`)
    const browser = await chromium.launch()
    const page = await browser.newPage()
    await page.goto(`http://127.0.0.1:${PORT}/`, { waitUntil: 'networkidle' })
    await page.waitForFunction(() => Boolean(window.__BUSI_PARITY__))

    const ref = JSON.parse(readFileSync(resolve(REPO, 'tests/parity/reference.json'), 'utf8'))
    const gallery = ref.cases.filter((c) => c.kind === 'gallery').slice(0, 6)
    if (gallery.length < 3) throw new Error('Need ≥3 gallery parity cases for timing')

    // Warmup (loads model)
    await page.evaluate(async (src) => {
      const api = window.__BUSI_PARITY__
      const url = new URL(src.replace(/^\//, ''), location.href).href
      await api.runInference(url)
    }, gallery[0].src)

    const rows = []
    for (const c of gallery) {
      const timed = await page.evaluate(async (src) => {
        const api = window.__BUSI_PARITY__
        const url = new URL(src.replace(/^\//, ''), location.href).href

        const t0 = performance.now()
        const single = await api.runInference(url)
        const singleMs = performance.now() - t0

        const t1 = performance.now()
        const a = await api.runInference(url)
        const img = await createImageBitmap(await (await fetch(url)).blob())
        const canvas = document.createElement('canvas')
        canvas.width = img.width
        canvas.height = img.height
        const ctx = canvas.getContext('2d')
        ctx.translate(img.width, 0)
        ctx.scale(-1, 1)
        ctx.drawImage(img, 0, 0)
        const blob = await new Promise((res) => canvas.toBlob((b) => res(b), 'image/png'))
        const file = new File([blob], 'flip.png', { type: 'image/png' })
        const b = await api.runInference(file)

        const h = b.maskH
        const w = b.maskW
        const restored = new Float32Array(b.softMask.length)
        for (let y = 0; y < h; y++) {
          for (let x = 0; x < w; x++) {
            restored[y * w + x] = b.softMask[y * w + (w - 1 - x)]
          }
        }
        const mean = new Float32Array(a.softMask.length)
        for (let i = 0; i < mean.length; i++) mean[i] = 0.5 * (a.softMask[i] + restored[i])
        const clsMean = 0.5 * (a.clsProb + b.clsProb)
        const avgMs = performance.now() - t1

        let softMax = 0
        for (let i = 0; i < mean.length; i++) if (mean[i] > softMax) softMax = mean[i]

        return {
          singleMs,
          avgMs,
          singleCls: single.clsProb,
          avgCls: clsMean,
          softMax,
        }
      }, c.src)

      rows.push({ id: c.id, ...timed })
      console.log(
        `${c.id}: single=${timed.singleMs.toFixed(0)}ms  hflip2=${timed.avgMs.toFixed(0)}ms  ratio=${(
          timed.avgMs / timed.singleMs
        ).toFixed(2)}`,
      )
    }

    const singleMean = rows.reduce((s, r) => s + r.singleMs, 0) / rows.length
    const avgMean = rows.reduce((s, r) => s + r.avgMs, 0) / rows.length
    const timing = {
      n_images: rows.length,
      single_ms_mean: singleMean,
      hflip2_ms_mean: avgMean,
      ratio: avgMean / singleMean,
      per_image: rows,
      note: 'Chromium via vite preview on this VM; model download excluded (warmup). Soft-mask average of original + horizontal flip.',
    }
    console.log('\nSummary', {
      single_ms_mean: singleMean,
      hflip2_ms_mean: avgMean,
      ratio: avgMean / singleMean,
    })

    if (existsSync(RESULTS)) {
      const out = JSON.parse(readFileSync(RESULTS, 'utf8'))
      out.browser_timing = timing
      writeFileSync(RESULTS, JSON.stringify(out, null, 2) + '\n')
      console.log('Updated', RESULTS)
    }

    await browser.close()
  } finally {
    preview.kill('SIGTERM')
  }
}

main().catch((err) => {
  console.error(err)
  process.exit(1)
})
