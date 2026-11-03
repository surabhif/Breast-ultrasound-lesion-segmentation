import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import { STRUGGLE_PICKS } from './struggleCases'

type MistakeRow = {
  case_id: string
  label: string
  dice: number
  error_type: string
  silhouette_src?: string
}

describe('struggleCases', () => {
  it('curates 4–6 real BUSI mistakes.json rows with silhouettes', () => {
    expect(STRUGGLE_PICKS.length).toBeGreaterThanOrEqual(4)
    expect(STRUGGLE_PICKS.length).toBeLessThanOrEqual(6)

    const raw = JSON.parse(
      readFileSync(resolve(__dirname, '../../public/results/mistakes.json'), 'utf8'),
    ) as { rows: MistakeRow[] }
    const byId = new Map(raw.rows.map((r) => [r.case_id, r]))

    const types = new Set<string>()
    for (const pick of STRUGGLE_PICKS) {
      const row = byId.get(pick.case_id)
      expect(row, `missing case ${pick.case_id}`).toBeTruthy()
      expect(row!.silhouette_src).toMatch(/^results\/mistakes_silhouettes\//)
      expect(pick.reason.length).toBeGreaterThan(20)
      expect(pick.reason).not.toMatch(/\d\.\d{2,}/) // do not invent extra decimals in copy
      types.add(row!.error_type)
    }

    // Cover the story types called out in the upgrade brief.
    expect(types.has('missed_lesion')).toBe(true)
    expect(types.has('false_lesion_on_normal')).toBe(true)
    expect(types.has('wrong_class')).toBe(true)
    expect(
      types.has('under_segmentation') || types.has('over_segmentation'),
    ).toBe(true)
  })
})
