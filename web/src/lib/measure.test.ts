import { describe, expect, it } from 'vitest'
import { measureLesion } from './measure'

describe('measureLesion', () => {
  it('returns zeros for an empty mask', () => {
    const mask = new Float32Array(16)
    const m = measureLesion(mask, 4, 4, 0.1)
    expect(m.areaPx).toBe(0)
    expect(m.longestDiameterPx).toBe(0)
    expect(m.areaMm2).toBe(0)
  })

  it('measures a filled rectangle', () => {
    const h = 10
    const w = 10
    const mask = new Float32Array(h * w)
    for (let y = 2; y <= 7; y++) {
      for (let x = 1; x <= 8; x++) {
        mask[y * w + x] = 1
      }
    }
    const m = measureLesion(mask, h, w, null)
    expect(m.areaPx).toBe(48)
    expect(m.longestDiameterPx).toBeGreaterThan(7)
    expect(m.perpendicularWidthPx).toBeGreaterThan(4)
    expect(m.diameterLine).not.toBeNull()
    expect(m.areaMm2).toBeNull()
  })

  it('scales to mm when pixel spacing is known', () => {
    const mask = new Float32Array([1, 1, 0, 0])
    const m = measureLesion(mask, 2, 2, 0.5)
    expect(m.areaMm2).toBeCloseTo(2 * 0.5 * 0.5)
    expect(m.longestDiameterMm).toBeCloseTo(m.longestDiameterPx * 0.5)
  })
})
