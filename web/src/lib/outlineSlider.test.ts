import { describe, expect, it } from 'vitest'
import { SEG_THRESHOLD } from './constants'
import {
  OUTLINE_THR_MAX,
  OUTLINE_THR_MIN,
  loosePositionToThr,
  outlineSliderLabel,
  thrToLoosePosition,
} from './outlineSlider'

describe('outlineSlider', () => {
  it('keeps the default mask cutoff at SEG_THRESHOLD (0.4)', () => {
    expect(SEG_THRESHOLD).toBe(0.4)
    expect(outlineSliderLabel(SEG_THRESHOLD)).toBe('Default')
    const pos = thrToLoosePosition(SEG_THRESHOLD)
    expect(loosePositionToThr(pos)).toBeCloseTo(SEG_THRESHOLD, 10)
  })

  it('maps Tight (left) to a higher cutoff and Loose (right) to a lower cutoff', () => {
    expect(loosePositionToThr(OUTLINE_THR_MIN)).toBeCloseTo(OUTLINE_THR_MAX, 10)
    expect(loosePositionToThr(OUTLINE_THR_MAX)).toBeCloseTo(OUTLINE_THR_MIN, 10)
    expect(outlineSliderLabel(0.7)).toBe('Tighter')
    expect(outlineSliderLabel(0.2)).toBe('Looser')
  })

  it('round-trips positions across the slider range', () => {
    for (const thr of [0.1, 0.25, 0.4, 0.55, 0.9]) {
      expect(loosePositionToThr(thrToLoosePosition(thr))).toBeCloseTo(thr, 10)
    }
  })
})
