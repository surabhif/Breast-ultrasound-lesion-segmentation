/**
 * Demo upload / privacy / PDF affordances (no model inference required).
 */
import { expect, test } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'

test.describe('Demo upload + a11y', () => {
  test('drop zone, privacy note, camera input, and axe-clean demo route', async ({ page }) => {
    test.setTimeout(90_000)
    await page.goto('./demo')

    await expect(page.getByRole('heading', { name: 'Try the detector' })).toBeVisible()
    await expect(
      page.getByText('Your image stays in this browser. Nothing is uploaded.'),
    ).toBeVisible()

    const upload = page.locator('#demo-upload-input')
    await expect(upload).toHaveAttribute('accept', 'image/*')
    await expect(upload).toHaveAttribute('type', 'file')

    const camera = page.locator('#demo-camera-input')
    await expect(camera).toHaveAttribute('accept', 'image/*')
    await expect(camera).toHaveAttribute('capture', 'environment')

    await expect(page.getByRole('button', { name: 'Upload image' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Capture with camera' })).toBeVisible()

    await expect(
      page.getByText(/Expert compare and outline-overlap score \(Dice\) are hidden for uploads/),
    ).toBeVisible()

    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
      .analyze()
    expect(results.violations, JSON.stringify(results.violations, null, 2)).toEqual([])
  })
})
