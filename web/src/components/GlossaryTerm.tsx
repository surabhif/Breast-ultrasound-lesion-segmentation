import { useEffect, useId, useRef, useState, type ReactNode } from 'react'
import { GLOSSARY, type GlossaryKey } from '../lib/glossary'

type Props = {
  term: GlossaryKey
  children?: ReactNode
}

/**
 * Accessible glossary tip: hover (pointer), focus, tap/click, Enter/Space.
 * Esc and outside press close. Works on keyboard and mobile.
 */
export default function GlossaryTerm({ term, children }: Props) {
  const entry = GLOSSARY[term]
  const [open, setOpen] = useState(false)
  const rootRef = useRef<HTMLSpanElement>(null)
  const tipId = useId()
  const btnId = useId()

  useEffect(() => {
    if (!open) return
    const onDoc = (e: MouseEvent | TouchEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false)
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    document.addEventListener('touchstart', onDoc)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDoc)
      document.removeEventListener('touchstart', onDoc)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  const label = children ?? entry.label

  return (
    <span
      className={`glossary-term${open ? ' open' : ''}`}
      ref={rootRef}
      onMouseEnter={() => {
        if (typeof window !== 'undefined' && window.matchMedia('(hover: hover)').matches) {
          setOpen(true)
        }
      }}
      onMouseLeave={() => {
        if (typeof window !== 'undefined' && window.matchMedia('(hover: hover)').matches) {
          setOpen(false)
        }
      }}
    >
      <button
        type="button"
        id={btnId}
        className="glossary-trigger"
        aria-expanded={open}
        aria-controls={tipId}
        onClick={(e) => {
          e.preventDefault()
          setOpen((v) => !v)
        }}
        onFocus={() => setOpen(true)}
        onBlur={(e) => {
          if (!rootRef.current?.contains(e.relatedTarget as Node)) setOpen(false)
        }}
        onKeyDown={(e) => {
          if (e.key === 'Escape') {
            e.preventDefault()
            setOpen(false)
            ;(e.currentTarget as HTMLButtonElement).blur()
          }
        }}
      >
        {label}
      </button>
      <span id={tipId} role="tooltip" className="glossary-tip" hidden={!open}>
        <strong className="glossary-tip-label">{entry.label}</strong>
        <span className="glossary-tip-body">{entry.definition}</span>
      </span>
    </span>
  )
}
