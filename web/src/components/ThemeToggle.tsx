import { useEffect, useState } from 'react'
import {
  initTheme,
  readStoredPreference,
  resolveTheme,
  toggleTheme,
  type ThemeMode,
} from '../lib/theme'

/** Light / dark switch. Remembers the choice; defaults to system preference. */
export default function ThemeToggle() {
  const [mode, setMode] = useState<ThemeMode>(() => resolveTheme(readStoredPreference()))

  useEffect(() => {
    setMode(initTheme())
    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    const onChange = () => {
      // Only follow system when the visitor has not locked a choice.
      if (readStoredPreference() == null || readStoredPreference() === 'system') {
        setMode(initTheme())
      }
    }
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [])

  return (
    <button
      type="button"
      className="theme-toggle"
      aria-label={mode === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
      title={mode === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
      onClick={() => setMode(toggleTheme(mode))}
    >
      <span aria-hidden="true">{mode === 'dark' ? 'Light' : 'Dark'}</span>
    </button>
  )
}
