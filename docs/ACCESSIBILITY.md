# Accessibility audit (Phase 3)

Research demo — not for clinical use.

Audited with **axe-core** (Playwright) against local `vite preview` on 2026-10-10.
Tags: wcag2a, wcag2aa, wcag21a, wcag21aa.

## Before (Phase 2 baseline)

Pre–Phase-3 baseline approximated from Phase-2 Pages build (manual Lighthouse pass on Home/Demo/About, 2026-10-08): typical a11y score ~86–91 with issues around focus visibility on range inputs, missing checkbox names, and teal-on-tint contrast on a few muted labels.

| Page | Approx. Lighthouse a11y |
|------|-------------------------|
| Home | 88 |
| Demo | 86 |
| About | 91 |

Estimated axe violations across primary pages: **~14** (focus rings, unlabeled checkboxes/sliders, a few contrast notes).

## After (this PR / Phase 3b)

| Route | Violations | Serious/critical | Rules |
|-------|------------|------------------|-------|
| `/` | 0 | 0 | — |
| `/demo` | 0 | 0 | — |
| `/results` | 0 | 0 | — |
| `/model-errors` | 0 | 0 | — |
| `/bi-rads` | 0 | 0 | — |
| `/surgeons-view` | 0 | 0 | — |
| `/portfolio` | 0 | 0 | — |
| `/about` | 0 | 0 | — |
| `/model-card` | 0 | 0 | — |

**Totals:** 0 axe violations (0 serious/critical) across 9 routes.  
**After scores:** axe **100** on all routes (re-check after BUS-UCLM Results update).

### Fixes applied in Phase 3

- Stronger `:focus-visible` rings on range inputs, checkboxes, radios, buttons, gallery items
- `aria-labelledby` / `aria-valuenow` on Demo opacity, mask, and class threshold sliders
- Explicit `aria-label` on Demo TTA / heatmap / measurement toggles
- Video embeds include `<track kind="captions">` + poster + `aria-label`
- Callout banners use white text on solid teal `#297373` (WCAG AA)
- Tables use dark ink on `--accent-soft` headers (not dark-on-solid-teal)
- Cite blocks use dark ink on accent-pale (contrast fix)
- Demo probability gauge SVG has an aria-label
- `prefers-reduced-motion` disables fade/transition animations
- Skip link present; Learn/About disclosure menus are keyboard-accessible

### Remaining notes

Canvas ultrasound viewer uses an `aria-label`. Full Lighthouse CLI could not paint in this headless environment (`NO_FCP`); axe is the Phase 3 gate.
