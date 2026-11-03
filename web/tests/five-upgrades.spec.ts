/**
 * Five site upgrades: struggle gallery, Tight/Loose outline, loading tips,
 * print stylesheet hooks, phone-friendly chrome.
 */
import { expect, test } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import { SEG_THRESHOLD } from '../src/lib/constants'

test.describe('Five site upgrades', () => {
  test('Model Errors shows Where the model struggles gallery', async ({ page }) => {
    await page.goto('./model-errors')
    const gallery = page.locator('#where-model-struggles')
    await expect(gallery.getByRole('heading', { name: 'Where the model struggles' })).toBeVisible()
    const cards = gallery.locator('.struggle-card')
    await expect(cards).toHaveCount(6)
    await expect(cards.first().locator('.struggle-reason')).not.toBeEmpty()
    await expect(page.getByRole('link', { name: 'Model Errors explorer' }).first()).toBeVisible()
  })

  test('Results links to the struggle gallery', async ({ page }) => {
    await page.goto('./results')
    const link = page.getByRole('link', { name: 'Where the model struggles' })
    await expect(link).toHaveAttribute('href', /model-errors#where-model-struggles/)
  })

  test('Demo outline slider defaults to SEG_THRESHOLD and exposes Tight/Loose', async ({
    page,
  }) => {
    test.setTimeout(120_000)
    await page.goto('./demo')

    const slider = page.getByTestId('outline-tight-loose')
    await expect(slider).toBeVisible()
    await expect(page.getByText(/A looser outline includes areas the model is less sure about/i)).toBeVisible()

    // Default position maps to SEG_THRESHOLD (Tight←→Loose inversion: 0.9+0.1-thr).
    const defaultPos = 0.9 + 0.1 - SEG_THRESHOLD
    await expect(slider).toHaveValue(String(defaultPos))
    await expect(page.getByText(/Outline: Tight \/ Loose \(Default\)/)).toBeVisible()

    // Loading tip appears while model is not yet ready (or status panel is present).
    const tip = page.getByTestId('loading-tip')
    const status = page.locator('.model-progress')
    await expect(status).toBeVisible()
    // Tip may flash briefly; if already ready, ensure status copy mentions cache / MB.
    if (await tip.count()) {
      await expect(tip).toBeVisible()
    } else {
      await expect(status).toContainText(/MB|cache|ready|Model/i)
    }
  })

  test('print stylesheet keeps disclaimer and hides nav chrome', async ({ page }) => {
    await page.goto('./about')
    await page.emulateMedia({ media: 'print' })
    await expect(page.locator('.site-notice')).toBeVisible()
    await expect(page.locator('.how-built')).toBeVisible()
    await expect(page.locator('.site-header')).toBeHidden()
    await expect(page.locator('.theme-toggle')).toBeHidden()
  })

  test('phone widths: no horizontal page overflow on key routes', async ({ page }) => {
    test.setTimeout(90_000)
    const routes = ['/', './demo', './results', './model-errors', './about', './why']
    for (const size of [
      { width: 360, height: 740 },
      { width: 390, height: 844 },
    ]) {
      await page.setViewportSize(size)
      for (const route of routes) {
        await page.goto(route)
        const overflow = await page.evaluate(() => {
          const doc = document.documentElement
          return {
            scrollWidth: doc.scrollWidth,
            clientWidth: doc.clientWidth,
          }
        })
        expect(
          overflow.scrollWidth,
          `${route} @ ${size.width}x${size.height} overflow`,
        ).toBeLessThanOrEqual(overflow.clientWidth + 1)
      }
    }
  })

  test('Model Errors axe at phone width', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 })
    await page.goto('./model-errors')
    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa'])
      .analyze()
    expect(
      results.violations,
      `axe: ${JSON.stringify(results.violations, null, 2)}`,
    ).toEqual([])
  })
})
