import { describe, expect, it } from 'vitest'
import { LOADING_TIPS, tipAt } from './loadingTips'

describe('loadingTips', () => {
  it('ships about eight plain tips without clinical diagnosis claims', () => {
    expect(LOADING_TIPS.length).toBeGreaterThanOrEqual(7)
    expect(LOADING_TIPS.length).toBeLessThanOrEqual(10)
    for (const tip of LOADING_TIPS) {
      expect(tip.length).toBeGreaterThan(20)
      expect(tip).not.toMatch(/\b(treat|cure|prescribe)\b/i)
      expect(tip).not.toMatch(/\bAI-powered\b|\bleverage\b|\brobust\b|\bseamless\b/i)
    }
    expect(LOADING_TIPS.some((t) => /BUSI/i.test(t))).toBe(true)
    expect(LOADING_TIPS.some((t) => /research demo/i.test(t))).toBe(true)
  })

  it('rotates tips by tick', () => {
    expect(tipAt(0)).toBe(LOADING_TIPS[0])
    expect(tipAt(LOADING_TIPS.length)).toBe(LOADING_TIPS[0])
    expect(tipAt(1)).toBe(LOADING_TIPS[1])
  })
})
