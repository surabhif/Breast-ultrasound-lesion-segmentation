import { describe, expect, it } from 'vitest'
import { GLOSSARY, GLOSSARY_KEYS } from './glossary'

describe('glossary', () => {
  it('defines every required term with plain text', () => {
    const required = [
      'dice',
      'auc',
      'birads',
      'lesion',
      'margin',
      'ultrasound',
      'outline',
      'threshold',
    ]
    expect(GLOSSARY_KEYS.sort()).toEqual([...required].sort())
    for (const key of required) {
      const entry = GLOSSARY[key as keyof typeof GLOSSARY]
      expect(entry.label.length).toBeGreaterThan(1)
      expect(entry.definition.length).toBeGreaterThan(20)
      expect(entry.definition).not.toMatch(/\b(robust|comprehensive|leverage|seamless|delve)\b/i)
      expect(entry.definition).not.toMatch(/\b(D\d+|E-a|C3|MODEL_POLICY)\b/)
    }
  })
})
