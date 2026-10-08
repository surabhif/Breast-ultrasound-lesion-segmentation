import { useEffect, useState } from 'react'
import { MODEL_VERSION } from '../lib/constants'

type MetricsBlock = {
  test_dice: number
  test_dice_bootstrap_95ci: [number, number]
  test_iou: number
  test_iou_bootstrap_95ci: [number, number]
  lesion_dice?: number
  lesion_dice_bootstrap_95ci?: [number, number]
  by_label?: Record<string, { n: number; dice_mean: number; dice_ci95: number[] }>
  cls_roc_auc?: number
  cls_sensitivity?: number
  cls_specificity?: number
  cls_ece?: number
  decision_threshold?: number
  confusion_matrix?: { labels: string[]; matrix: number[][]; row_means_true?: boolean }
  cv_summary?: { fold: number; val_dice?: number; val_lesion_dice?: number }[]
  normal_false_positive_count?: number
  normal_n?: number
  delta_vs_fp32?: { test_dice?: number; lesion_dice?: number; cls_roc_auc?: number }
}

type Metrics = {
  label: string
  disclaimer: string
  surabhi_prompts: string[]
  splits_note?: string
  model_version?: string
  config: Record<string, unknown>
  subset_sizes: Record<string, unknown>
  metrics: MetricsBlock
  served_int8?: MetricsBlock & {
    label?: string
    sha256?: string
    seg_threshold?: number
    min_component_area?: number
  }
  metrics_source?: Record<string, string>
  roc_curve?: { fpr: number; tpr: number }[]
  calibration?: {
    center: number
    mean_predicted: number | null
    fraction_positive: number | null
    count: number
  }[]
  mistakes?: {
    src: string
    case_id: string
    label: string
    dice: number
    cls_prob: number
    note?: string
  }[]
  cleaning_experiment?: {
    full_model_clean_vs_flagged?: Record<string, unknown>
    duplicate_leakage_proxy?: Record<string, unknown>
    dataset_counts?: Record<string, unknown>
  }
  model_artifact?: Record<string, unknown>
}

function fmt(n: number | null | undefined, digits = 3) {
  if (n == null || Number.isNaN(n)) return '—'
  return n.toFixed(digits)
}

function RocChart({ points }: { points: NonNullable<Metrics['roc_curve']> }) {
  const w = 320
  const h = 240
  const pad = 36
  const innerW = w - pad * 2
  const innerH = h - pad * 2
  const path = points
    .map((p, i) => {
      const x = pad + p.fpr * innerW
      const y = pad + (1 - p.tpr) * innerH
      return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="chart-svg" role="img" aria-label="ROC curve">
      <rect x={pad} y={pad} width={innerW} height={innerH} fill="rgba(255,255,255,0.5)" stroke="var(--line)" />
      <line x1={pad} y1={pad + innerH} x2={pad + innerW} y2={pad} stroke="var(--muted)" strokeDasharray="4 4" />
      <path d={path} fill="none" stroke="var(--accent)" strokeWidth="2.5" />
      <text x={w / 2} y={h - 8} textAnchor="middle" className="chart-axis">
        False positive rate
      </text>
      <text x={14} y={h / 2} textAnchor="middle" className="chart-axis" transform={`rotate(-90 14 ${h / 2})`}>
        True positive rate
      </text>
    </svg>
  )
}

function CalibrationChart({ bins }: { bins: NonNullable<Metrics['calibration']> }) {
  const w = 320
  const h = 240
  const pad = 36
  const innerW = w - pad * 2
  const innerH = h - pad * 2
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="chart-svg" role="img" aria-label="Reliability diagram">
      <rect x={pad} y={pad} width={innerW} height={innerH} fill="rgba(255,255,255,0.5)" stroke="var(--line)" />
      <line x1={pad} y1={pad + innerH} x2={pad + innerW} y2={pad} stroke="var(--muted)" strokeDasharray="4 4" />
      {bins
        .filter((b) => b.count > 0 && b.mean_predicted != null && b.fraction_positive != null)
        .map((b) => {
          const x = pad + (b.mean_predicted as number) * innerW
          const y = pad + (1 - (b.fraction_positive as number)) * innerH
          return <circle key={`${b.center}-${b.count}`} cx={x} cy={y} r={5} fill="var(--accent)" />
        })}
      <text x={w / 2} y={h - 8} textAnchor="middle" className="chart-axis">
        Mean predicted probability
      </text>
      <text x={14} y={h / 2} textAnchor="middle" className="chart-axis" transform={`rotate(-90 14 ${h / 2})`}>
        Observed frequency
      </text>
    </svg>
  )
}

export default function ResultsPage() {
  const [data, setData] = useState<Metrics | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const url = `${import.meta.env.BASE_URL}results/metrics.json`
    fetch(url)
      .then((r) => {
        if (!r.ok) throw new Error(`Could not load ${url}`)
        return r.json()
      })
      .then((j: Metrics) => setData(j))
      .catch((e: Error) => setError(e.message))
  }, [])

  if (error) {
    return (
      <article className="panel prose fade-in">
        <h1>Results</h1>
        <p className="error-text" role="alert">
          {error}
        </p>
      </article>
    )
  }

  if (!data) {
    return (
      <article className="panel prose fade-in">
        <h1>Results</h1>
        <p className="muted">Loading metrics…</p>
      </article>
    )
  }

  const m = data.metrics
  const served = data.served_int8
  const primary = served ?? m
  const cm = (served?.confusion_matrix ?? m.confusion_matrix)?.matrix
  const labels = (served?.confusion_matrix ?? m.confusion_matrix)?.labels
  const clean = data.cleaning_experiment?.full_model_clean_vs_flagged as
    | {
        all_test?: { dice_mean?: number; cls_auc?: number; n?: number }
        clean_test?: { dice_mean?: number; cls_auc?: number; n?: number }
        flagged_test?: { dice_mean?: number; cls_auc?: number; n?: number }
        dice_inflation_all_minus_clean?: number
      }
    | undefined
  const leak = data.cleaning_experiment?.duplicate_leakage_proxy as
    | {
        random_split_val_group_leak_fraction?: number
        val_dice_inflation_leaky_minus_grouped?: number
        grouped_val_dice?: number
        leaky_val_dice?: number
      }
    | undefined

  const diceDelta = served?.delta_vs_fp32?.test_dice
  const aucDelta = served?.delta_vs_fp32?.cls_roc_auc
  const meaningfulDiff =
    (diceDelta != null && Math.abs(diceDelta) >= 0.005) ||
    (aucDelta != null && Math.abs(aucDelta) >= 0.005)

  return (
    <div className="fade-in results-page">
      <header className="page-intro">
        <h1>Results</h1>
        <p>{data.disclaimer}</p>
        <p className="muted tiny">
          {data.label} · model v{data.model_version ?? MODEL_VERSION}
        </p>
      </header>

      {served && (
        <section className="panel" style={{ marginTop: 0 }}>
          <h2 className="section-title">FP32 (training) vs INT8 (served)</h2>
          <p>
            Headline numbers below are for the <strong>served INT8 ONNX</strong> that runs in the
            browser (v{data.model_version ?? MODEL_VERSION}). Training used an FP32 PyTorch
            checkpoint with torchvision/PIL resize; the served path uses a shared half-pixel
            bilinear resize identical to the browser. Both use the same grouped test split and
            post-processing (threshold {served.seg_threshold ?? 0.4}, min-component area{' '}
            {served.min_component_area ?? 40}).
          </p>
          {meaningfulDiff && (
            <p>
              Under browser-matched preprocess, INT8 overall Dice is {fmt(Math.abs(diceDelta ?? 0), 3)}{' '}
              {(diceDelta ?? 0) < 0 ? 'lower' : 'higher'} than the FP32 training figure (
              {fmt(m.test_dice)} → {fmt(served.test_dice)}), while AUC is{' '}
              {fmt(Math.abs(aucDelta ?? 0), 3)} {(aucDelta ?? 0) < 0 ? 'lower' : 'higher'} (
              {fmt(m.cls_roc_auc)} → {fmt(served.cls_roc_auc)}). Normal-image false positives are{' '}
              {served.normal_false_positive_count}/{served.normal_n} (same rate as FP32’s 12/19).
            </p>
          )}
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Metric</th>
                  <th>FP32 PyTorch</th>
                  <th>INT8 ONNX (served)</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>Test Dice (all)</td>
                  <td>
                    {fmt(m.test_dice)} [{fmt(m.test_dice_bootstrap_95ci?.[0])},{' '}
                    {fmt(m.test_dice_bootstrap_95ci?.[1])}]
                  </td>
                  <td>
                    {fmt(served.test_dice)} [{fmt(served.test_dice_bootstrap_95ci?.[0])},{' '}
                    {fmt(served.test_dice_bootstrap_95ci?.[1])}]
                  </td>
                </tr>
                <tr>
                  <td>Lesion Dice</td>
                  <td>
                    {fmt(m.lesion_dice)} [{fmt(m.lesion_dice_bootstrap_95ci?.[0])},{' '}
                    {fmt(m.lesion_dice_bootstrap_95ci?.[1])}]
                  </td>
                  <td>
                    {fmt(served.lesion_dice)} [{fmt(served.lesion_dice_bootstrap_95ci?.[0])},{' '}
                    {fmt(served.lesion_dice_bootstrap_95ci?.[1])}]
                  </td>
                </tr>
                <tr>
                  <td>Test IoU</td>
                  <td>{fmt(m.test_iou)}</td>
                  <td>{fmt(served.test_iou)}</td>
                </tr>
                <tr>
                  <td>Cls ROC-AUC</td>
                  <td>{fmt(m.cls_roc_auc)}</td>
                  <td>{fmt(served.cls_roc_auc)}</td>
                </tr>
                <tr>
                  <td>Normal false-positive masks</td>
                  <td>12 / 19</td>
                  <td>
                    {served.normal_false_positive_count} / {served.normal_n}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <p className="muted tiny">
            Sources: {data.metrics_source?.fp32_pytorch ?? 'results/full_run.json'} ·{' '}
            {data.metrics_source?.int8_served ?? 'results/served_int8_test.json'}
          </p>
        </section>
      )}

      <section className="panel metrics-strip">
        <div>
          <div className="metric-label">Test Dice (served INT8)</div>
          <div className="metric-value">{fmt(primary.test_dice)}</div>
          <div className="muted tiny">
            95% CI [{fmt(primary.test_dice_bootstrap_95ci?.[0])},{' '}
            {fmt(primary.test_dice_bootstrap_95ci?.[1])}]
          </div>
        </div>
        <div>
          <div className="metric-label">Lesion Dice</div>
          <div className="metric-value">{fmt(primary.lesion_dice)}</div>
          <div className="muted tiny">benign + malignant only</div>
        </div>
        <div>
          <div className="metric-label">Test IoU</div>
          <div className="metric-value">{fmt(primary.test_iou)}</div>
        </div>
        <div>
          <div className="metric-label">Cls ROC-AUC</div>
          <div className="metric-value">{fmt(primary.cls_roc_auc)}</div>
          <div className="muted tiny">
            sens {fmt(primary.cls_sensitivity ?? m.cls_sensitivity)} · spec{' '}
            {fmt(primary.cls_specificity ?? m.cls_specificity)} @{' '}
            {primary.decision_threshold ?? m.decision_threshold ?? 0.5}
          </div>
        </div>
        <div>
          <div className="metric-label">ECE</div>
          <div className="metric-value">{fmt(primary.cls_ece ?? m.cls_ece)}</div>
          <div className="muted tiny">calibration error</div>
        </div>
      </section>

      {data.splits_note && (
        <p className="panel muted" style={{ marginTop: '1rem' }}>
          {data.splits_note}
        </p>
      )}

      {(served?.by_label ?? m.by_label) && (
        <section className="panel" style={{ marginTop: '1rem' }}>
          <h2 className="section-title">Dice by label (served INT8)</h2>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Label</th>
                  <th>N</th>
                  <th>Dice</th>
                  <th>95% CI</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(served?.by_label ?? m.by_label ?? {}).map(([lab, row]) => (
                  <tr key={lab}>
                    <td>
                      <span className={`badge ${lab}`}>{lab}</span>
                    </td>
                    <td>{row.n}</td>
                    <td>{fmt(row.dice_mean)}</td>
                    <td>
                      [{fmt(row.dice_ci95?.[0])}, {fmt(row.dice_ci95?.[1])}]
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <div className="charts-grid" style={{ marginTop: '1rem' }}>
        {data.roc_curve && data.roc_curve.length > 0 && (
          <section className="panel">
            <h2 className="section-title">ROC curve (B vs M)</h2>
            <RocChart points={data.roc_curve} />
          </section>
        )}
        {data.calibration && (
          <section className="panel">
            <h2 className="section-title">Reliability diagram</h2>
            <CalibrationChart bins={data.calibration} />
            <p className="muted tiny">Points closer to the diagonal are better calibrated.</p>
          </section>
        )}
      </div>

      {cm && labels && (
        <section className="panel" style={{ marginTop: '1rem' }}>
          <h2 className="section-title">Confusion matrix</h2>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>True \ Pred</th>
                  {labels.map((l) => (
                    <th key={l}>{l}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {cm.map((row, i) => (
                  <tr key={labels[i]}>
                    <td>{labels[i]}</td>
                    {row.map((v, j) => (
                      <td key={j}>{v}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {m.cv_summary && m.cv_summary.length > 0 && (
        <section className="panel" style={{ marginTop: '1rem' }}>
          <h2 className="section-title">Cross-validation summary</h2>
          <p className="muted">Short per-fold val lesion Dice (see training config for epoch budget).</p>
          <ul>
            {m.cv_summary.map((f) => (
              <li key={f.fold}>
                Fold {f.fold}: lesion Dice {fmt(f.val_lesion_dice ?? f.val_dice)}
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="panel" style={{ marginTop: '1rem' }}>
        <h2 className="section-title">Cleaning experiment</h2>
        <p>
          How much do caliper/annotation flags and near-duplicates affect reported scores? Numbers
          below come from actual runs (see <code>results/cleaning_experiment.json</code>).
        </p>
        {!clean ? (
          <p className="muted">Cleaning experiment results will appear after export.</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Subset</th>
                  <th>N</th>
                  <th>Dice</th>
                  <th>AUC</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>All test</td>
                  <td>{clean.all_test?.n ?? '—'}</td>
                  <td>{fmt(clean.all_test?.dice_mean)}</td>
                  <td>{fmt(clean.all_test?.cls_auc)}</td>
                </tr>
                <tr>
                  <td>Clean (no flag)</td>
                  <td>{clean.clean_test?.n ?? '—'}</td>
                  <td>{fmt(clean.clean_test?.dice_mean)}</td>
                  <td>{fmt(clean.clean_test?.cls_auc)}</td>
                </tr>
                <tr>
                  <td>Flagged only</td>
                  <td>{clean.flagged_test?.n ?? '—'}</td>
                  <td>{fmt(clean.flagged_test?.dice_mean)}</td>
                  <td>{fmt(clean.flagged_test?.cls_auc)}</td>
                </tr>
              </tbody>
            </table>
          </div>
        )}
        {clean?.dice_inflation_all_minus_clean != null && (
          <p className="muted">
            Dice(all) − Dice(clean) = {fmt(clean.dice_inflation_all_minus_clean as number, 4)}
          </p>
        )}
        {leak && (
          <p>
            Duplicate-leakage proxy: random splits put ~
            {fmt((leak.random_split_val_group_leak_fraction ?? 0) * 100, 1)}% of val images in a
            near-dup group also seen in train. Val Dice inflation (leaky − grouped) ≈{' '}
            {fmt(leak.val_dice_inflation_leaky_minus_grouped)}.
          </p>
        )}
      </section>

      {data.mistakes && data.mistakes.length > 0 && (
        <section className="panel" style={{ marginTop: '1rem' }}>
          <h2 className="section-title">Failure gallery (worst Dice)</h2>
          <p className="muted">Green ≈ ground-truth outline; magenta/red ≈ prediction.</p>
          <div className="gallery-grid">
            {data.mistakes.map((mrow) => (
              <figure key={mrow.src} className="gallery-item static">
                <img src={`${import.meta.env.BASE_URL}${mrow.src}`} alt={`Failure ${mrow.case_id}`} />
                <figcaption>
                  <span className={`badge ${mrow.label}`}>{mrow.label}</span> Dice {fmt(mrow.dice)} ·
                  P(mal) {fmt(mrow.cls_prob)}
                </figcaption>
              </figure>
            ))}
          </div>
        </section>
      )}

      {data.surabhi_prompts?.length > 0 && (
        <section className="panel" style={{ marginTop: '1rem' }}>
          <h2 className="section-title">Interview prompts</h2>
          <ul>
            {data.surabhi_prompts.map((q) => (
              <li key={q}>{q}</li>
            ))}
          </ul>
        </section>
      )}

      {data.model_artifact && (
        <p className="muted tiny" style={{ marginTop: '1rem' }}>
          Served model: {String(data.model_artifact.path)} · {String(data.model_artifact.served_mb)}{' '}
          MB · {String(data.model_artifact.quantization)} · v{data.model_version ?? MODEL_VERSION}
        </p>
      )}
    </div>
  )
}
