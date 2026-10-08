import { defineConfig, devices } from '@playwright/test'

const basePath = process.env.VITE_BASE || '/'
const port = 4173

export default defineConfig({
  testDir: './tests',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  timeout: 120_000,
  use: {
    ...devices['Desktop Chrome'],
    baseURL: `http://127.0.0.1:${port}${basePath}`,
    trace: 'on-first-retry',
  },
  webServer: {
    command: `npx vite preview --host 127.0.0.1 --port ${port}`,
    url: `http://127.0.0.1:${port}${basePath}`,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
})
