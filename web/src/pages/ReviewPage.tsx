import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import externalSamples from '../data/external_samples.json'

const TOKEN = 'busi-review-2026'
const STORAGE_KEY = 'busi-clinician-review-v1'

type Answer = {
  sampleId: string
  usefulness: number | null
  teaching: 'help' | 'neutral' | 'hurt' | null
  note: string
}

type Store = {
  reviewerName: string
  role: string
  overall: string
  answers: Record<string, Answer>
  updatedAt: string
}

function loadStore(): Store {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) return JSON.parse(raw) as Store
  } catch {
    /* ignore */
  }
  return {
    reviewerName: '',
    role: '',
    overall: '',
    answers: {},
    updatedAt: new Date().toISOString(),
  }
}

export default function ReviewPage() {
  const [params] = useSearchParams()
  const ok = params.get('k') === TOKEN
  const [store, setStore] = useState<Store>(() => loadStore())

  useEffect(() => {
    const next = { ...store, updatedAt: new Date().toISOString() }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
  }, [store])

  const samples = externalSamples.samples

  const csv = useMemo(() => {
    const header = [
      'reviewer_name',
      'role',
      'sample_id',
      'label',
      'usefulness_1to5',
      'teaching',
      'note',
      'overall',
      'exported_at',
    ]
    const rows = samples.map((s) => {
      const a = store.answers[s.id] ?? {
        sampleId: s.id,
        usefulness: null,
        teaching: null,
        note: '',
      }
      return [
        store.reviewerName,
        store.role,
        s.id,
        s.label,
        a.usefulness ?? '',
        a.teaching ?? '',
        JSON.stringify(a.note ?? ''),
        JSON.stringify(store.overall ?? ''),
        new Date().toISOString(),
      ].join(',')
    })
    return [header.join(','), ...rows].join('\n')
  }, [samples, store])

  if (!ok) {
    return (
      <article className="panel prose fade-in">
        <h1>Review</h1>
        <p className="muted">
          Private clinician review page. Open with the token link provided by the project owner
          (<code>/review?k=…</code>). Not listed in the site navigation.
        </p>
      </article>
    )
  }

  function setAnswer(id: string, patch: Partial<Answer>) {
    setStore((prev) => {
      const cur = prev.answers[id] ?? {
        sampleId: id,
        usefulness: null,
        teaching: null,
        note: '',
      }
      return {
        ...prev,
        answers: { ...prev.answers, [id]: { ...cur, ...patch, sampleId: id } },
      }
    })
  }

  function downloadCsv() {
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `busi-clinician-review-${Date.now()}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="fade-in review-page">
      <header className="page-intro">
        <h1>Clinician review (private)</h1>
        <p>
          Research demo — not for clinical use. Answers stay in this browser (
          <code>localStorage</code>) until you export CSV. No server uploads. Protocol:{' '}
          <code>docs/CLINICIAN_REVIEW.md</code>.
        </p>
        <p className="muted tiny">{externalSamples.disclaimer}</p>
      </header>

      <section className="panel">
        <h2 className="section-title">About you</h2>
        <label className="review-field">
          Name (optional until you consent to acknowledgement)
          <input
            value={store.reviewerName}
            onChange={(e) => setStore({ ...store, reviewerName: e.target.value })}
          />
        </label>
        <label className="review-field">
          Role (e.g. breast radiologist, surgical oncologist)
          <input value={store.role} onChange={(e) => setStore({ ...store, role: e.target.value })} />
        </label>
        <label className="review-field">
          Overall comments on disclaimers / Results wording
          <textarea
            rows={3}
            value={store.overall}
            onChange={(e) => setStore({ ...store, overall: e.target.value })}
          />
        </label>
        <button type="button" className="btn" onClick={downloadCsv}>
          Export CSV
        </button>
      </section>

      {samples.map((s) => {
        const a = store.answers[s.id]
        return (
          <section key={s.id} className="panel" style={{ marginTop: '1rem' }}>
            <h2 className="section-title">
              <span className={`badge ${s.label}`}>{s.label}</span> {s.id}
            </h2>
            <p className="muted tiny">{s.attribution}</p>
            <div className="review-grid">
              <img src={`${import.meta.env.BASE_URL}${s.src}`} alt={`BrEaST ${s.label}`} />
              <img
                src={`${import.meta.env.BASE_URL}${s.mask_src}`}
                alt="Expert tumor mask"
                className="mask-thumb"
              />
            </div>
            <label className="review-field">
              Outline usefulness (1–5)
              <input
                type="number"
                min={1}
                max={5}
                value={a?.usefulness ?? ''}
                onChange={(e) =>
                  setAnswer(s.id, {
                    usefulness: e.target.value === '' ? null : Number(e.target.value),
                  })
                }
              />
            </label>
            <fieldset className="review-field">
              <legend>Would this outline help or hurt a teaching discussion?</legend>
              {(['help', 'neutral', 'hurt'] as const).map((v) => (
                <label key={v} className="radio-inline">
                  <input
                    type="radio"
                    name={`teach-${s.id}`}
                    checked={a?.teaching === v}
                    onChange={() => setAnswer(s.id, { teaching: v })}
                  />
                  {v}
                </label>
              ))}
            </fieldset>
            <label className="review-field">
              Note (optional)
              <textarea
                rows={2}
                value={a?.note ?? ''}
                onChange={(e) => setAnswer(s.id, { note: e.target.value })}
              />
            </label>
          </section>
        )
      })}
    </div>
  )
}
