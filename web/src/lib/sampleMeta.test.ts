import { describe, expect, it } from 'vitest'
import {
  classLabelDisplay,
  sampleHasExpert,
  sampleSourceLabel,
  sampleSpacingMm,
} from './sampleMeta'

describe('classLabelDisplay', () => {
  it('maps BUSI labels without treating normal as harmless', () => {
    expect(classLabelDisplay('benign')).toBe('harmless (benign)')
    expect(classLabelDisplay('malignant')).toBe('cancerous (malignant)')
    expect(classLabelDisplay('normal')).toBe('normal (no lump)')
  })
})

describe('sampleSourceLabel / spacing', () => {
  it('labels BrEaST samples as CC BY, not BUSI', () => {
    const breast = {
      id: 'breast-breast_03_malignant',
      label: 'malignant',
      dataset: 'breast',
      mask_src: 'samples/external/breast_03_malignant_mask.png',
      mm_per_mask_px_160: 0.23,
    }
    expect(sampleSourceLabel(breast)).toBe('BrEaST CC BY')
    expect(sampleHasExpert(breast)).toBe(true)
    expect(sampleSpacingMm(breast, 160)).toBeCloseTo(0.23, 5)
  })

  it('labels BUSI samples as BUSI test sample', () => {
    const busi = {
      id: 'benign-1',
      label: 'benign',
      mask_src: 'samples/benign_mask.png',
    }
    expect(sampleSourceLabel(busi)).toBe('BUSI test sample')
    expect(sampleSpacingMm(busi, 160)).toBeNull()
  })

  it('uploads have no ground truth and no spacing', () => {
    expect(sampleSourceLabel(null)).toMatch(/gallery samples only/i)
    expect(sampleHasExpert(null)).toBe(false)
    expect(sampleSpacingMm(undefined, 160)).toBeNull()
  })
})
