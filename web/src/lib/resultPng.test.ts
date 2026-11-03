import { describe, expect, it } from 'vitest'
import { resultPngCaption } from './resultPng'

describe('result PNG caption', () => {
  it('includes benign/malignant score and research-demo disclaimer', () => {
    const { scoreLine, disclaimer } = resultPngCaption(0.812, 'leans cancerous')
    expect(scoreLine).toBe('Benign / malignant score: 81.2% (leans cancerous)')
    expect(disclaimer).toBe('Research demo, not for clinical use')
  })

  it('omits lean label when not provided', () => {
    const { scoreLine } = resultPngCaption(0.12)
    expect(scoreLine).toBe('Benign / malignant score: 12.0%')
  })
})
