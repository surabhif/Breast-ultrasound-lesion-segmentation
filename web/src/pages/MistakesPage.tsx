import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

type MistakeRow = {
  case_id: string
  label: string
  dice: number
  cls_prob: number
  error_type: string
  annotation_flag?: boolean
  note?: string
  note_source?: string
  silhouette_src?: string
  image_src?: string
  dataset?: string
}

type MistakesPayload = {
  disclaimer: string
  notes_label: string
  legend?: { expert?: string; model?: string; overlap?: string }
  rows: MistakeRow[]
}

const ERROR_TYPES = [
  'all',
  'false_lesion_on_normal',
  'missed_lesion',
  'under_segmentation',
  'over_segmentation',
  'wrong_class',
  'boundary_disagreement',
] as const

export default function MistakesPage() {
  const [data, setData] = useState<MistakesPayload | null>(null)
  const [label, setLabel] = useState('all')
  const [errorType, setErrorType] = useState<(typeof ERROR_TYPES)[number]>('all')
  const [flaggedOnly, setFlaggedOnly] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetch(`${import.meta.env.BASE_URL}results/mistakes.json`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      })
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load'))
  }, [])

  const filtered = useMemo(() => {
    if (!data) return []
    return data.rows.filter((r) => {
      if (label !== 'all' && r.label !== label) return false
      if (errorType !== 'all' && r.error_type !== errorType) return false
      if (flaggedOnly && !r.annotation_flag) return false
      return true
    })
  }, [data, label, errorType, flaggedOnly])

  const counts = useMemo(() => {
    const c: Record<string, number> = {}
    for (const r of data?.rows ?? []) c[r.error_type] = (c[r.error_type] ?? 0) + 1
    return c
  }, [data])

  if (error) {
    return (
      <div className="fade-in">
        <h1>Model Errors explorer</h1>
        <p className="error-text">{error}</p>
      </div>
    )
  }
  if (!data) {
    return (
      <div className="fade-in">
        <h1>Model Errors explorer</h1>
        <p className="muted">Loading…</p>
      </div>
    )
  }

  return (
    <div className="fade-in mistakes-page">
      <header className="page-intro">
        <h1>Model Errors explorer</h1>
        <p>
          Browse hard cases from the BUSI test set. BUSI ultrasound pixels are not shown here
          (licence). Cards use outline-only silhouettes. Full CC BY images appear only when noted.
          See also <Link to="/results">Results</Link>.
        </p>
        <p className="muted tiny">{data.disclaimer}</p>
      </header>

      <section className="panel">
        <h2 className="section-title">Error-type counts</h2>
        <div className="mistakes-count-row">
          {Object.entries(counts).map(([k, v]) => (
            <div key={k} className="mistakes-count-chip">
              <strong>{v}</strong>
              <span className="muted tiny">{k.replaceAll('_', ' ')}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="panel" style={{ marginTop: '1rem' }}>
        <div className="mistakes-filters">
          <label>
            Label{' '}
            <select value={label} onChange={(e) => setLabel(e.target.value)}>
              <option value="all">all</option>
              <option value="benign">benign</option>
              <option value="malignant">malignant</option>
              <option value="normal">normal</option>
            </select>
          </label>
          <label>
            Error type{' '}
            <select
              value={errorType}
              onChange={(e) => setErrorType(e.target.value as (typeof ERROR_TYPES)[number])}
            >
              {ERROR_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t.replaceAll('_', ' ')}
                </option>
              ))}
            </select>
          </label>
          <label className="radio-inline">
            <input
              type="checkbox"
              checked={flaggedOnly}
              onChange={(e) => setFlaggedOnly(e.target.checked)}
            />
            Caliper/text flagged only
          </label>
        </div>
        <p className="muted tiny">
          Showing {filtered.length} / {data.rows.length}. Notes marked “{data.notes_label}”.
        </p>
        <ul className="mistakes-legend" aria-label="Silhouette legend">
          <li>
            <span className="legend-swatch legend-expert" />{' '}
            {data.legend?.expert ?? 'Expert outline (blue)'}
          </li>
          <li>
            <span className="legend-swatch legend-model" />{' '}
            {data.legend?.model ?? 'Model outline (orange)'}
          </li>
          <li>
            <span className="legend-swatch legend-overlap" />{' '}
            {data.legend?.overlap ?? 'Agreement fill (teal)'}
          </li>
        </ul>
        <div className="mistakes-grid">
          {filtered.map((row) => (
            <article key={row.case_id} className="mistake-card">
              {row.silhouette_src || row.image_src ? (
                <img
                  src={`${import.meta.env.BASE_URL}${row.silhouette_src ?? row.image_src}`}
                  alt=""
                  className="mask-thumb"
                />
              ) : (
                <div className="viewer-empty">No silhouette</div>
              )}
              <div>
                <span className={`badge ${row.label}`}>{row.label}</span>{' '}
                <span className="muted tiny">{row.error_type.replaceAll('_', ' ')}</span>
              </div>
              <p className="tiny">
                Dice {row.dice.toFixed(2)} · P(M) {row.cls_prob.toFixed(2)}
                {row.annotation_flag ? ' · flagged marks' : ''}
              </p>
              <p className="muted tiny">{row.case_id}</p>
              {row.note && (
                <p className="mistake-note">
                  <em>{row.note_source ?? data.notes_label}:</em> {row.note}
                </p>
              )}
            </article>
          ))}
        </div>
      </section>
    </div>
  )
}
