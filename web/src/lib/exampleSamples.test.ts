import { describe, expect, it } from 'vitest'
import { getExampleStripSamples } from './exampleSamples'
import samplesManifest from '../data/samples.json'

describe('example image strip', () => {
  it('returns six BUSI samples: 2 normal, 2 benign, 2 malignant', () => {
    const strip = getExampleStripSamples()
    expect(strip).toHaveLength(6)
    expect(strip.map((s) => s.label)).toEqual([
      'normal',
      'normal',
      'benign',
      'benign',
      'malignant',
      'malignant',
    ])
  })

  it('uses only public sample paths already in the repo manifest', () => {
    const ids = new Set(samplesManifest.samples.map((s) => s.id))
    for (const sample of getExampleStripSamples()) {
      expect(ids.has(sample.id)).toBe(true)
      expect(sample.src).toMatch(/^samples\/sample_/)
    }
  })
})
