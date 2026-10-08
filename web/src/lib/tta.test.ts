import { describe, expect, it } from 'vitest'
import { aggregateTta, agreementLabel, overallUncertaintySummary, scoreStabilityLabel } from './tta'

describe('aggregateTta', () => {
  it('gives perfect agreement for identical masks', () => {
    const m = new Float32Array([0, 0, 1, 1, 0.9, 0.1])
    const r = aggregateTta([m, new Float32Array(m), new Float32Array(m)], [0.2, 0.2, 0.2], 0.5)
    expect(r.agreement).toBeCloseTo(1, 5)
    expect(r.clsStd).toBeCloseTo(0, 5)
    expect(agreementLabel(r.agreement)).toBe('high')
  })

  it('drops agreement when masks disagree', () => {
    const a = new Float32Array([1, 1, 0, 0])
    const b = new Float32Array([0, 0, 1, 1])
    const r = aggregateTta([a, b], [0.1, 0.9], 0.5)
    expect(r.agreement).toBeLessThan(0.2)
    expect(agreementLabel(r.agreement)).toBe('low')
    expect(r.clsStd).toBeGreaterThan(0.3)
  })
})

describe('overallUncertaintySummary', () => {
  it('warns when outline is high but score spreads', () => {
    expect(scoreStabilityLabel(0.357)).toBe('spread')
    const s = overallUncertaintySummary(0.97, 0.357)
    expect(s.outline).toBe('high')
    expect(s.score).toBe('spread')
    expect(s.warning).toMatch(/score moved/i)
  })
})
