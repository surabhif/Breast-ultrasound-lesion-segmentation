import { useMemo, useState } from 'react'

type ScoreRow = {
  case_id: string
  split: string
  label: string
  y_true: number
  cls_prob: number
}

type ScoresPayload = {
  disclaimer: string
  reported_threshold: number
  rows: ScoreRow[]
}

function metricsAt(rows: ScoreRow[], thr: number) {
  let tp = 0
  let tn = 0
  let fp = 0
  let fn = 0
  for (const r of rows) {
    const pred = r.cls_prob >= thr ? 1 : 0
    if (pred === 1 && r.y_true === 1) tp++
    else if (pred === 0 && r.y_true === 0) tn++
    else if (pred === 1 && r.y_true === 0) fp++
    else fn++
  }
  const sens = tp + fn ? tp / (tp + fn) : 0
  const spec = tn + fp ? tn / (tn + fp) : 0
  const ppv = tp + fp ? tp / (tp + fp) : 0
  const npv = tn + fn ? tn / (tn + fn) : 0
  return { tp, tn, fp, fn, sens, spec, ppv, npv }
}

export default function ThresholdExplorer({ data }: { data: ScoresPayload }) {
  const [thr, setThr] = useState(data.reported_threshold ?? 0.5)
  const [split, setSplit] = useState<'test' | 'val'>('test')

  const rows = useMemo(
    () => data.rows.filter((r) => r.split === split),
    [data.rows, split],
  )
  const m = useMemo(() => metricsAt(rows, thr), [rows, thr])
  const prev = rows.length ? rows.filter((r) => r.y_true === 1).length / rows.length : 0

  return (
    <section className="panel" id="operating-point" style={{ marginTop: '1rem' }}>
      <h2 className="section-title">Choose an operating point</h2>
      <p>
        Slide the classification threshold over held-out B/M scores (served INT8). The reported
        point <strong>0.5</strong> was chosen on validation before looking at test.
      </p>
      <div className="mistakes-filters">
        <label>
          Split{' '}
          <select value={split} onChange={(e) => setSplit(e.target.value as 'test' | 'val')}>
            <option value="test">test</option>
            <option value="val">val</option>
          </select>
        </label>
        <button type="button" className="btn secondary" onClick={() => setThr(0.5)}>
          Reported 0.5
        </button>
        <button
          type="button"
          className="btn secondary"
          onClick={() => {
            // find thr with sens >= 0.95 if possible
            let best = 0.5
            for (let t = 0; t <= 1.001; t += 0.01) {
              const mm = metricsAt(rows, t)
              if (mm.sens >= 0.95) best = t
            }
            setThr(Number(best.toFixed(2)))
          }}
        >
          High sensitivity (≥95% if possible)
        </button>
      </div>
      <label className="threshold-slider">
        Threshold {thr.toFixed(2)}
        <input
          type="range"
          min={0}
          max={1}
          step={0.01}
          value={thr}
          onChange={(e) => setThr(Number(e.target.value))}
          aria-valuemin={0}
          aria-valuemax={1}
          aria-valuenow={thr}
        />
      </label>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th />
              <th>Pred M</th>
              <th>Pred B</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <th>True M</th>
              <td>{m.tp}</td>
              <td>{m.fn}</td>
            </tr>
            <tr>
              <th>True B</th>
              <td>{m.fp}</td>
              <td>{m.tn}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <p>
        Sens {m.sens.toFixed(3)} · Spec {m.spec.toFixed(3)} · PPV {m.ppv.toFixed(3)} · NPV{' '}
        {m.npv.toFixed(3)}
      </p>
      <p className="muted tiny">
        {data.disclaimer} Current {split} prevalence (malignant): {(100 * prev).toFixed(0)}% (n=
        {rows.length}).
      </p>
    </section>
  )
}
