import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import { HOW_BUILT_STATEMENT } from '../components/HowBuilt'
import measurement from '../data/measurement_agreement.json'

describe('Phase 3 honesty + data wiring', () => {
  it('HowBuilt statement names Cursor and Surabhi without task claims', () => {
    expect(HOW_BUILT_STATEMENT).toMatch(/Cursor/)
    expect(HOW_BUILT_STATEMENT).toMatch(/Surabhi Fadnavis/)
    expect(HOW_BUILT_STATEMENT).toMatch(/code, analysis, text, and video/)
    expect(HOW_BUILT_STATEMENT).not.toMatch(/owns the research/)
  })

  it('measurement_agreement copy matches repo results JSON on key fields', () => {
    const root = resolve(__dirname, '../../../results/measurement_agreement.json')
    const canonical = JSON.parse(readFileSync(root, 'utf8')) as typeof measurement
    expect(measurement.n).toBe(canonical.n)
    expect(measurement.longest_diameter_mm.pearson_proxy_for_icc).toBe(
      canonical.longest_diameter_mm.pearson_proxy_for_icc,
    )
    expect(measurement.longest_diameter_mm.t1_t2_20mm_discordance_rate).toBe(
      canonical.longest_diameter_mm.t1_t2_20mm_discordance_rate,
    )
  })
})
