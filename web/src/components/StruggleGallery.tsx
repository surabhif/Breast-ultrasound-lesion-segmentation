import { Link } from 'react-router-dom'
import { STRUGGLE_PICKS } from '../data/struggleCases'
import { classLabelDisplay } from '../lib/sampleMeta'

export type StruggleRow = {
  case_id: string
  label: string
  dice: number
  error_type: string
  silhouette_src?: string
  image_src?: string
}

type Props = {
  rows: StruggleRow[]
  /** Optional id for deep links from Results. */
  id?: string
}

const ERROR_PLAIN: Record<string, string> = {
  missed_lesion: 'Missed lesion',
  false_lesion_on_normal: 'False outline on a normal scan',
  wrong_class: 'Wrong harmless / cancerous call',
  under_segmentation: 'Partial outline',
  over_segmentation: 'Outline too large',
  boundary_disagreement: 'Outline mismatch',
}

/** Compact gallery of curated hard BUSI cases (silhouettes from Model Errors). */
export default function StruggleGallery({ rows, id = 'where-model-struggles' }: Props) {
  const byId = new Map(rows.map((r) => [r.case_id, r]))
  const cards = STRUGGLE_PICKS.map((pick) => {
    const row = byId.get(pick.case_id)
    return row ? { ...pick, row } : null
  }).filter((c): c is { case_id: string; reason: string; row: StruggleRow } => c != null)

  if (cards.length === 0) return null

  return (
    <section className="panel struggle-gallery" id={id} style={{ marginTop: '1rem' }}>
      <h2 className="section-title">Where the model struggles</h2>
      <p>
        A short look at real BUSI held-out cases the model got wrong. Outline silhouettes only
        (BUSI ultrasound pixels are not shown). Full filterable list:{' '}
        <Link to="/model-errors">Model Errors explorer</Link>.
      </p>
      <div className="struggle-grid">
        {cards.map(({ reason, row }) => {
          const src = row.silhouette_src ?? row.image_src
          return (
            <article key={row.case_id} className="struggle-card">
              {src ? (
                <img
                  src={`${import.meta.env.BASE_URL}${src}`}
                  alt=""
                  className="mask-thumb"
                  width={200}
                  height={200}
                  loading="lazy"
                  decoding="async"
                />
              ) : (
                <div className="viewer-empty">No silhouette</div>
              )}
              <div>
                <span className={`badge ${row.label}`}>{classLabelDisplay(row.label)}</span>{' '}
                <span className="muted tiny">
                  {ERROR_PLAIN[row.error_type] ?? row.error_type.replaceAll('_', ' ')}
                </span>
              </div>
              <p className="struggle-reason">{reason}</p>
              <p className="tiny muted">
                Outline-overlap (Dice) {row.dice.toFixed(2)} · {row.case_id}
              </p>
            </article>
          )
        })}
      </div>
    </section>
  )
}
