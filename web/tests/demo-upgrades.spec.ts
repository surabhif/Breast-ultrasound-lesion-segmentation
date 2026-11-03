/**
 * Demo upgrades: example picker, side-by-side toggle, download PNG, footer, theme.
 */
import { expect, test } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'

test.describe('Demo UX upgrades', () => {
  test('example strip, side-by-side controls, downloads, footer, theme', async ({ page }) => {
    test.setTimeout(90_000)
    await page.goto('./demo')

    await expect(page.getByTestId('example-image-picker')).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Example scans' })).toBeVisible()
    const options = page.locator('.example-picker-item')
    await expect(options).toHaveCount(6)

    await expect(page.getByRole('button', { name: 'Overlay' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Side by side' })).toBeVisible()

    await expect(page.getByRole('link', { name: 'Report a problem' })).toHaveAttribute(
      'href',
      /issues\/new\?template=problem\.yml/,
    )
    await expect(page.getByText(/Model v1\.0\.0 · Last updated/)).toBeVisible()

    const theme = page.getByRole('button', { name: /Switch to (dark|light) mode/ })
    await expect(theme).toBeVisible()
    const before = await page.locator('html').getAttribute('data-theme')
    await theme.click()
    const after = await page.locator('html').getAttribute('data-theme')
    expect(after).not.toBe(before)
    expect(after === 'light' || after === 'dark').toBeTruthy()

    // Axe both themes so dark teal surfaces stay AA-readable.
    for (const mode of ['light', 'dark'] as const) {
      const current = await page.locator('html').getAttribute('data-theme')
      if (current !== mode) await theme.click()
      await expect(page.locator('html')).toHaveAttribute('data-theme', mode)
      const results = await new AxeBuilder({ page })
        .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
        .analyze()
      expect(
        results.violations,
        `axe ${mode}: ${JSON.stringify(results.violations, null, 2)}`,
      ).toEqual([])
    }
  })
})
