import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const store = new Map<string, string>()

const docEl = {
  attrs: new Map<string, string>(),
  style: { colorScheme: '' } as { colorScheme: string },
  setAttribute(k: string, v: string) {
    this.attrs.set(k, v)
  },
  getAttribute(k: string) {
    return this.attrs.get(k) ?? null
  },
  removeAttribute(k: string) {
    this.attrs.delete(k)
  },
}

beforeEach(() => {
  store.clear()
  docEl.attrs.clear()
  docEl.style.colorScheme = ''
  vi.resetModules()
  vi.stubGlobal('localStorage', {
    getItem: (k: string) => store.get(k) ?? null,
    setItem: (k: string, v: string) => {
      store.set(k, v)
    },
    removeItem: (k: string) => {
      store.delete(k)
    },
    clear: () => store.clear(),
  })
  vi.stubGlobal('document', {
    documentElement: docEl,
    querySelector: () => null,
  })
  vi.stubGlobal(
    'matchMedia',
    vi.fn().mockImplementation((query: string) => ({
      matches: String(query).includes('dark'),
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })),
  )
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('theme helpers', () => {
  it('resolves system preference when nothing is stored', async () => {
    const theme = await import('./theme')
    expect(theme.getSystemTheme()).toBe('dark')
    expect(theme.resolveTheme(null)).toBe('dark')
  })

  it('remembers an explicit light or dark choice', async () => {
    const theme = await import('./theme')
    theme.writeStoredPreference('light')
    expect(theme.readStoredPreference()).toBe('light')
    expect(theme.resolveTheme()).toBe('light')
    theme.writeStoredPreference('dark')
    expect(theme.resolveTheme()).toBe('dark')
    expect(store.get(theme.THEME_STORAGE_KEY)).toBe('dark')
  })

  it('toggles and applies data-theme on the document', async () => {
    const theme = await import('./theme')
    theme.applyTheme('light')
    expect(docEl.getAttribute('data-theme')).toBe('light')
    const next = theme.toggleTheme('light')
    expect(next).toBe('dark')
    expect(docEl.getAttribute('data-theme')).toBe('dark')
    expect(theme.readStoredPreference()).toBe('dark')
  })
})
