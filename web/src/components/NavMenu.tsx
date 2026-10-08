import { useEffect, useId, useRef, useState } from 'react'
import { NavLink, useLocation } from 'react-router-dom'

type Item = { to: string; label: string }

type Props = {
  label: string
  items: Item[]
}

/** Accessible disclosure menu for grouped primary-nav links. */
export default function NavMenu({ label, items }: Props) {
  const [open, setOpen] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)
  const buttonId = useId()
  const menuId = useId()
  const location = useLocation()
  const active = items.some((i) => location.pathname === i.to)

  useEffect(() => {
    setOpen(false)
  }, [location.pathname])

  useEffect(() => {
    if (!open) return
    const onDoc = (e: MouseEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false)
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDoc)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  return (
    <div className={`nav-menu${active ? ' active-group' : ''}`} ref={rootRef}>
      <button
        type="button"
        id={buttonId}
        className="nav-menu-trigger"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={menuId}
        onClick={() => setOpen((v) => !v)}
      >
        {label}
        <span className="nav-menu-caret" aria-hidden="true">
          ▾
        </span>
      </button>
      <ul
        id={menuId}
        role="menu"
        aria-labelledby={buttonId}
        className={`nav-menu-list${open ? ' open' : ''}`}
        hidden={!open}
      >
        {items.map((item) => (
          <li key={item.to} role="none">
            <NavLink
              role="menuitem"
              to={item.to}
              className="nav-menu-item"
              onClick={() => setOpen(false)}
            >
              {item.label}
            </NavLink>
          </li>
        ))}
      </ul>
    </div>
  )
}
