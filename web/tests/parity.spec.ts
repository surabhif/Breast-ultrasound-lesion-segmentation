/**
 * Browser pipeline vs Python ONNX reference (tests/parity/reference.json).
 * Requires a production build already present in web/dist (CI builds first).
 */
import { expect, test } from '@playwright/test'
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

type RefCase = {
  id: string
  src: string
  kind: string
  cls_prob: number
  pred_area: number
  mask_mean: number
}

type Reference = {
  model_version: string
  tolerances: { cls_prob_abs: number; pred_area_abs: number }
  cases: RefCase[]
}

const refPath = resolve(dirname(fileURLToPath(import.meta.url)), '../../tests/parity/reference.json')
const reference = JSON.parse(readFileSync(refPath, 'utf8')) as Reference

test.describe('Python ↔ browser parity', () => {
  test('model version and gallery inference match reference within tolerance', async ({
    page,
  }) => {
    test.setTimeout(180_000)

    await page.goto('./')
    await page.waitForFunction(() => Boolean(window.__BUSI_PARITY__))

    const version = await page.evaluate(() => window.__BUSI_PARITY__!.MODEL_VERSION)
    expect(version).toBe(reference.model_version)

    const thr = await page.evaluate(() => ({
      seg: window.__BUSI_PARITY__!.SEG_THRESHOLD,
      min: window.__BUSI_PARITY__!.MIN_COMPONENT_AREA,
    }))
    expect(thr.seg).toBe(0.4)
    expect(thr.min).toBe(40)

    const tol = reference.tolerances
    const gallery = reference.cases.filter((c) => c.kind === 'gallery')
    expect(gallery.length).toBeGreaterThanOrEqual(6)

    for (const c of gallery) {
      const result = await page.evaluate(async (src) => {
        const api = window.__BUSI_PARITY__!
        const url = new URL(src.replace(/^\//, ''), window.location.href).href
        const out = await api.runInference(url)
        let predArea = 0
        for (let i = 0; i < out.mask.length; i++) {
          if (out.mask[i]! > api.SEG_THRESHOLD) predArea++
        }
        return {
          clsProb: out.clsProb,
          predArea,
          maskMean: out.maskMean,
          maskH: out.maskH,
          maskW: out.maskW,
        }
      }, c.src)

      expect(Math.abs(result.clsProb - c.cls_prob), `cls ${c.id}`).toBeLessThanOrEqual(
        tol.cls_prob_abs,
      )
      expect(Math.abs(result.predArea - c.pred_area), `area ${c.id}`).toBeLessThanOrEqual(
        tol.pred_area_abs,
      )
      expect(result.maskH).toBe(160)
      expect(result.maskW).toBe(160)
    }
  })

  test('morphology hook drops sub-min-area components', async ({ page }) => {
    await page.goto('./')
    await page.waitForFunction(() => Boolean(window.__BUSI_PARITY__))

    const kept = await page.evaluate(() => {
      const soft = new Float32Array(9)
      soft[1] = 0.9
      soft[6] = 0.8
      soft[7] = 0.8
      soft[8] = 0.8
      const out = window.__BUSI_PARITY__!.postprocessMask(soft, 3, 3, 0.4, 2)
      return [out[1], out[6], out[7], out[8]]
    })
    expect(kept[0]).toBe(0)
    expect(kept[1]).toBeCloseTo(0.8)
    expect(kept[2]).toBeCloseTo(0.8)
    expect(kept[3]).toBeCloseTo(0.8)
  })
})
