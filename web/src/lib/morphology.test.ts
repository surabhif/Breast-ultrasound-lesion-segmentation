/** Unit tests for morphology / post-process (Vitest). */
import { describe, expect, it } from 'vitest'
import { postprocessMask, removeSmallComponents } from './morphology'

describe('removeSmallComponents', () => {
  it('keeps components >= minArea and drops smaller ones', () => {
    // 5x5 grid with a 1-pixel blob and a 4-pixel blob
    const bin = new Uint8Array([
      0, 0, 0, 0, 0,
      0, 1, 0, 0, 0,
      0, 0, 0, 1, 1,
      0, 0, 0, 1, 1,
      0, 0, 0, 0, 0,
    ])
    const out = removeSmallComponents(bin, 5, 5, 3)
    expect(out[1 * 5 + 1]).toBe(0) // single pixel gone
    expect(out[2 * 5 + 3]).toBe(1)
    expect(out[2 * 5 + 4]).toBe(1)
    expect(out[3 * 5 + 3]).toBe(1)
    expect(out[3 * 5 + 4]).toBe(1)
  })

  it('matches empty mask → empty', () => {
    const bin = new Uint8Array(9)
    const out = removeSmallComponents(bin, 3, 3, 40)
    expect([...out]).toEqual([0, 0, 0, 0, 0, 0, 0, 0, 0])
  })
})

describe('postprocessMask', () => {
  it('zeros soft values below threshold and small components', () => {
    const soft = new Float32Array([
      0.1, 0.9, 0.0,
      0.0, 0.0, 0.0,
      0.8, 0.8, 0.8,
    ])
    // minArea=2 keeps the bottom row (3 px), drops the single 0.9
    const out = postprocessMask(soft, 3, 3, 0.4, 2)
    expect(out[1]).toBe(0)
    expect(out[6]).toBeCloseTo(0.8)
    expect(out[7]).toBeCloseTo(0.8)
    expect(out[8]).toBeCloseTo(0.8)
  })
})
