/** Light / dark theme helpers. Remembers a user choice; otherwise follows the system. */

export type ThemeMode = 'light' | 'dark'
export type ThemePreference = ThemeMode | 'system'

export const THEME_STORAGE_KEY = 'busi-theme'

export function getSystemTheme(): ThemeMode {
  const mq = typeof globalThis.matchMedia === 'function' ? globalThis.matchMedia : null
  if (!mq) return 'light'
  return mq('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

export function readStoredPreference(): ThemePreference | null {
  try {
    const raw = localStorage.getItem(THEME_STORAGE_KEY)
    if (raw === 'light' || raw === 'dark' || raw === 'system') return raw
  } catch {
    // ignore (private mode / blocked storage)
  }
  return null
}

export function writeStoredPreference(pref: ThemePreference): void {
  try {
    localStorage.setItem(THEME_STORAGE_KEY, pref)
  } catch {
    // ignore
  }
}

/** Resolve the effective light/dark mode from a stored preference (or system). */
export function resolveTheme(pref: ThemePreference | null = readStoredPreference()): ThemeMode {
  if (pref === 'light' || pref === 'dark') return pref
  return getSystemTheme()
}

export function applyTheme(mode: ThemeMode): void {
  const root = document.documentElement
  root.setAttribute('data-theme', mode)
  root.style.colorScheme = mode
  const meta = document.querySelector('meta[name="theme-color"]')
  if (meta) meta.setAttribute('content', mode === 'dark' ? '#0f1a1a' : '#297373')
}

/** Toggle between light and dark, persist the choice, and apply it. */
export function toggleTheme(current: ThemeMode): ThemeMode {
  const next: ThemeMode = current === 'dark' ? 'light' : 'dark'
  writeStoredPreference(next)
  applyTheme(next)
  return next
}

/** Apply saved preference (or system) on first paint. */
export function initTheme(): ThemeMode {
  const mode = resolveTheme()
  applyTheme(mode)
  return mode
}
