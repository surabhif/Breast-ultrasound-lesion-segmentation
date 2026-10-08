import { describe, expect, it } from 'vitest'
import { diceScore, iouScore } from './metrics'
import { measureLesion } from './measure'

describe('diceScore', () => {
  it('empty/empty → 1', () => {
    expect(diceScore(new Float32Array(4), new Float32Array(4))).toBe(1)
  })

  it('perfect overlap → ~1', () => {
    const a = new Float32Array([1, 1, 0, 0])
    expect(diceScore(a, a)).toBeCloseTo(1, 5)
  })

  it('no overlap → ~0', () => {
    const p = new Float32Array([1, 1, 0, 0])
    const g = new Float32Array([0, 0, 1, 1])
    expect(diceScore(p, g)).toBeLessThan(0.01)
  })
})

describe('iouScore', () => {
  it('empty/empty → 1', () => {
    expect(iouScore(new Float32Array(4), new Float32Array(4))).toBe(1)
  })
})

describe('measureLesion', () => {
  it('measures a 3x3 block', () => {
    const m = new Float32Array(25)
    for (let y = 1; y <= 3; y++) for (let x = 1; x <= 3; x++) m[y * 5 + x] = 1
    const out = measureLesion(m, 5, 5)
    expect(out.areaPx).toBe(9)
    expect(out.longestDiameterPx).toBeGreaterThan(2)
    expect(out.diameterLine).not.toBeNull()
  })

  it('converts mm when spacing given', () => {
    const m = new Float32Array([1, 1, 0, 0])
    const out = measureLesion(m, 2, 2, 0.5)
    expect(out.areaMm2).toBeCloseTo(2 * 0.25, 5)
  })
})
