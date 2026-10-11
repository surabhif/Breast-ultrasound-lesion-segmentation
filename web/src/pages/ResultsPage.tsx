import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { MODEL_VERSION } from '../lib/constants'
import { PLAIN_ABSTRACT } from '../lib/plainAbstract'
import ThresholdExplorer from '../components/ThresholdExplorer'

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
  external?: {
    protocol?: string
    model_version?: string
    internal_busi_int8?: {
      test_dice?: number
      lesion_dice?: number
      cls_roc_auc?: number
      n?: number
    }
    datasets?: Record<
      string,
      {
        n?: number
        n_patients?: number
        test_dice?: number
        test_dice_bootstrap_95ci?: [number, number]
        lesion_dice?: number
        lesion_dice_bootstrap_95ci?: [number, number]
        cls_roc_auc?: number | null
        cls_sensitivity?: number | null
        cls_specificity?: number | null
        cls_ece?: number | null
        attribution?: string
        normal_false_positive_count?: number | null
        normal_n?: number
        subgroups?: Record<string, Record<string, { n: number; dice_mean: number; dice_ci95: number[] }>>
      }
    >
    skipped?: Record<string, string>
  }
  inpaint_experiment?: {
    served_unchanged?: boolean
    decision_sentence?: string
    swap_note?: string
    swap_criteria?: {
      criterion: string
      rule: string
      v1?: number | null
      v2?: number | null
      passed: boolean
    }[]
    before_after_note?: string
    table?: { name: string; dice?: number; lesion_dice?: number; auc?: number }[]
  }
  v2_experiment?: {
    served_unchanged?: boolean
    decision_sentence?: string
    swap_note?: string
    note?: string
    busbra_label?: string
    breast_label?: string
    promotion_rule?: string
    promoted_seed?: number | null
    mean_pass?: boolean
    swap_criteria?: {
      criterion: string
      rule: string
      v1?: number | null
      v2?: number | null
      v2_sd?: number | null
      delta?: number | null
      delta_ci95?: [number | null, number | null] | number[]
      passed: boolean
      note?: string
    }[]
    table?: {
      name: string
      dice?: number
      dice_sd?: number
      lesion_dice?: number
      lesion_dice_sd?: number
      clean_dice?: number
      clean_dice_sd?: number
      busbra_dice?: number
      busbra_dice_sd?: number
      busbra_label?: string
      breast_dice?: number
      breast_dice_sd?: number
      auc?: number
      auc_sd?: number
      int8_mb?: number
      swap_ok?: boolean
    }[]
    config?: Record<string, unknown>
    busbra_split?: Record<string, unknown>
  }
  uncertainty?: {
    spearman_rho?: number
    spearman_p?: number
    dice_at_80_coverage?: number
  }
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

type ScoresPayload = {
  disclaimer: string
  reported_threshold: number
  rows: {
    case_id: string
    split: string
    label: string
    y_true: number
    cls_prob: number
  }[]
}

export default function ResultsPage() {
  const [data, setData] = useState<Metrics | null>(null)
  const [scores, setScores] = useState<ScoresPayload | null>(null)
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
    fetch(`${import.meta.env.BASE_URL}results/scores.json`)
      .then((r) => (r.ok ? r.json() : null))
      .then((j) => j && setScores(j))
      .catch(() => {})
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
        <p>{PLAIN_ABSTRACT}</p>
        <p className="muted tiny">
          {data.label} · model v{data.model_version ?? MODEL_VERSION}
        </p>
        <p className="report-link-row">
          <a className="btn secondary" href={`${import.meta.env.BASE_URL}report.pdf`} target="_blank" rel="noreferrer">
            Research write-up (PDF)
          </a>
          <Link className="btn secondary" to="/bi-rads">
            BI-RADS context
          </Link>
          <Link className="btn secondary" to="/surgeons-view">
            Surgeon&apos;s view
          </Link>
        </p>
      </header>

      {served && (
        <section className="panel" style={{ marginTop: 0 }}>
          <h2 className="section-title">Training checkpoint vs browser model</h2>
          <p>
            The main scores below are for the <strong>browser model</strong> (v
            {data.model_version ?? MODEL_VERSION}) on the careful test split. The full-precision
            training run sits beside it for comparison.
          </p>
          <details className="tech-details">
            <summary>Technical details</summary>
            <p>
              Browser path: INT8 ONNX via onnxruntime-web (WASM). Training: FP32 PyTorch with
              torchvision/PIL resize. The browser uses the same half-pixel bilinear resize as
              evaluation. Both paths share post-processing (mask threshold{' '}
              {served.seg_threshold ?? 0.4}, min-component area {served.min_component_area ?? 40}).
            </p>
          </details>
          {meaningfulDiff && (
            <p>
              With matched preprocessing, overall outline-overlap score (Dice) on the browser model
              is {fmt(Math.abs(diceDelta ?? 0), 3)} {(diceDelta ?? 0) < 0 ? 'lower' : 'higher'}{' '}
              than training ({fmt(m.test_dice)} → {fmt(served.test_dice)} out of 1). Harmless vs
              cancerous AUC moves {fmt(Math.abs(aucDelta ?? 0), 3)}{' '}
              {(aucDelta ?? 0) < 0 ? 'lower' : 'higher'} ({fmt(m.cls_roc_auc)} →{' '}
              {fmt(served.cls_roc_auc)}). False lump outlines on harmless images:{' '}
              {served.normal_false_positive_count}/{served.normal_n} (same rate as training,
              12/19).
            </p>
          )}
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Metric</th>
                  <th>Full-precision training</th>
                  <th>Browser model (compressed)</th>
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
                  <td>Harmless vs cancerous (AUC)</td>
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

      {data.external && (
        <section className="panel" style={{ marginTop: '1rem' }} id="external-validation">
          <h2 className="section-title">Scores on other public datasets</h2>
          <p>
            We scored a frozen <strong>v1.0.0 browser model</strong> on independent public datasets.
            We did not tune thresholds or architecture on those sets. The protocol is documented in{' '}
            <code>docs/EXTERNAL_VALIDATION_PROTOCOL.md</code>. Confidence intervals cluster by patient
            when patient IDs exist. Images were resized to 160×160, same as the demo.
          </p>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Dataset</th>
                  <th>N</th>
                  <th>Dice</th>
                  <th>Lesion Dice</th>
                  <th>AUC</th>
                  <th>Sens / Spec @ 0.5</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>BUSI internal (browser model)</td>
                  <td>{data.external.internal_busi_int8?.n ?? 112}</td>
                  <td>{fmt(data.external.internal_busi_int8?.test_dice)}</td>
                  <td>{fmt(data.external.internal_busi_int8?.lesion_dice)}</td>
                  <td>{fmt(data.external.internal_busi_int8?.cls_roc_auc)}</td>
                  <td>—</td>
                </tr>
                {Object.entries(data.external.datasets ?? {})
                  .filter(([, row]) => row.test_dice != null)
                  .map(([name, row]) => (
                  <tr key={name}>
                    <td>
                      {name === 'busbra'
                        ? 'BUS-BRA'
                        : name === 'breast'
                          ? 'BrEaST'
                          : name === 'busuclm'
                            ? 'BUS-UCLM'
                            : name}
                    </td>
                    <td>
                      {row.n}
                      {row.n_patients != null ? ` / ${row.n_patients} pts` : ''}
                    </td>
                    <td>
                      {fmt(row.test_dice)} [{fmt(row.test_dice_bootstrap_95ci?.[0])},{' '}
                      {fmt(row.test_dice_bootstrap_95ci?.[1])}]
                    </td>
                    <td>{fmt(row.lesion_dice)}</td>
                    <td>{fmt(row.cls_roc_auc ?? undefined)}</td>
                    <td>
                      {fmt(row.cls_sensitivity ?? undefined)} / {fmt(row.cls_specificity ?? undefined)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div style={{ marginTop: '0.75rem' }}>
            <p className="muted tiny">
              Outline-overlap score (Dice) by dataset (bar scaled 0 to 1)
            </p>
            {[
              {
                name: 'BUSI (browser)',
                dice: data.external.internal_busi_int8?.test_dice,
              },
              ...Object.entries(data.external.datasets ?? {})
                .filter(([, row]) => row.test_dice != null)
                .map(([name, row]) => ({
                name:
                  name === 'busbra'
                    ? 'BUS-BRA'
                    : name === 'breast'
                      ? 'BrEaST'
                      : name === 'busuclm'
                        ? 'BUS-UCLM'
                        : name,
                dice: row.test_dice,
              })),
            ].map((row) => (
              <div className="forest-bar" key={row.name}>
                <span style={{ width: '7rem' }}>{row.name}</span>
                <div className="bar-track">
                  <div
                    className="bar-fill"
                    style={{ width: `${Math.max(0, Math.min(100, (row.dice ?? 0) * 100))}%` }}
                  />
                </div>
                <span>{fmt(row.dice)}</span>
              </div>
            ))}
          </div>
          <p>
            Overall outline-overlap score (Dice) on BUS-BRA stays close to internal BUSI (~0.68 out
            of 1). Harmless vs cancerous AUC falls on new datasets (BUS-BRA ~0.64, BrEaST ~0.72 vs
            internal ~0.93). On BUS-UCLM (n=640, 38 patients; 43 Doppler/combined frames excluded),
            all-image Dice is ~0.386 because 320 of 413 harmless images get a non-empty outline. That
            matches the BUSI pattern (12 of 19 harmless images). Lesion-only Dice (~0.679 [0.593,
            0.755]) is a fairer cross-dataset read: a bit below BUS-BRA (~0.714) and above BrEaST
            (~0.629). BUS-UCLM harmless vs cancerous AUC is ~0.780. Lump outlining holds up better
            than the side score on new data.
          </p>
          <details className="tech-details">
            <summary>Technical details</summary>
            <p className="muted tiny">
              Calibration error (ECE) is worse on external sets than on internal BUSI.
            </p>
          </details>
          {data.external.skipped && Object.keys(data.external.skipped).length > 0 && (
            <p className="muted">
              Not included: UDIAT (requires an institutional licence agreement) and BUSIS (no
              redistribution permitted).
            </p>
          )}
          <p className="muted tiny">
            Attribution: Gómez-Flores et al. 2024 (BUS-BRA, Zenodo CC BY 4.0); Pawłowska et al. 2024
            (BrEaST / TCIA CC BY 4.0); Vallez et al. 2025 (BUS-UCLM, Mendeley CC BY 4.0). Images
            resized for evaluation. Not redistributed in the repo except small CC BY demo samples.
          </p>
        </section>
      )}

      <section className="panel" style={{ marginTop: '1rem' }} id="literature">
        <h2 className="section-title">Comparison with published work</h2>
        <p>
          Full citation table with split/leakage notes lives in{' '}
          <code>docs/LITERATURE_COMPARISON.md</code>. Highlights:
        </p>
        <ul>
          <li>
            Many BUSI papers use <strong>random</strong> 80/20 splits; Pawłowska et al. 2023 document
            ~235 duplicates (~19%). Our numbers use <strong>grouped</strong> near-dup splits.
          </li>
          <li>
            Musah et al. 2025 report BUSI→BrEaST Dice ~0.49 for a different, larger model. Our frozen
            v1 BrEaST Dice is ~0.63 (different recipe and resolution). That is still a real drop on
            new data vs some same-set papers claiming 0.8+ under random splits.
          </li>
          <li>
            Wang 2026 (classification) reports drops from home to outside sets. Our harmless vs
            cancerous AUC drop moves in the same <em>direction</em>.
          </li>
          <li>
            Leakage check (same grouped test): random training did <strong>not</strong> inflate
            validation lump-only Dice vs grouped splits (Δ ≈ −0.018). See{' '}
            <code>results/leakage_ablation.json</code>.
          </li>
        </ul>
        <p className="muted tiny">
          Unverified paper numbers are marked in the markdown doc and are not quoted as facts here.
          Pawłowska’s 235-duplicate list was not machine-ingested for near-duplicate matching stats
          (see technical notes in the markdown doc).
        </p>
      </section>

      <section className="panel metrics-strip">
        <div>
          <div className="metric-label">Test outline-overlap (Dice)</div>
          <div className="metric-value">{fmt(primary.test_dice)}</div>
          <div className="muted tiny">
            95% CI [{fmt(primary.test_dice_bootstrap_95ci?.[0])},{' '}
            {fmt(primary.test_dice_bootstrap_95ci?.[1])}]
          </div>
        </div>
        <div>
          <div className="metric-label">Lesion Dice</div>
          <div className="metric-value">{fmt(primary.lesion_dice)}</div>
          <div className="muted tiny">harmless + cancerous lumps only</div>
        </div>
        <div>
          <div className="metric-label">Test IoU</div>
          <div className="metric-value">{fmt(primary.test_iou)}</div>
        </div>
        <div>
          <div className="metric-label">Harmless vs cancerous (AUC)</div>
          <div className="metric-value">{fmt(primary.cls_roc_auc)}</div>
          <div className="muted tiny">
            sens {fmt(primary.cls_sensitivity ?? m.cls_sensitivity)} · spec{' '}
            {fmt(primary.cls_specificity ?? m.cls_specificity)} @{' '}
            {primary.decision_threshold ?? m.decision_threshold ?? 0.5}
          </div>
        </div>
        <div>
          <div className="metric-label">Calibration error</div>
          <div className="metric-value">{fmt(primary.cls_ece ?? m.cls_ece)}</div>
          <div className="muted tiny">lower is better on held-out test</div>
        </div>
      </section>

      {data.splits_note && (
        <p className="panel muted" style={{ marginTop: '1rem' }}>
          {data.splits_note}
        </p>
      )}

      {(served?.by_label ?? m.by_label) && (
        <section className="panel" style={{ marginTop: '1rem' }}>
          <h2 className="section-title">Outline-overlap score (Dice) by label</h2>
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

      {scores && <ThresholdExplorer data={scores} />}

      {data.v2_experiment && (
        <section className="panel" style={{ marginTop: '1rem' }} id="v2-comparison">
          <h2 className="section-title">Phase 4: next-model candidates vs current v1</h2>
          <p>
            {data.v2_experiment.note ??
              'We trained multi-dataset v2 candidates (BUSI plus patient-grouped BUS-BRA) and compared them to v1 under a fixed swap rule.'}{' '}
            BUS-BRA held-out overlaps v2 training data; v1 scores on the same held-out IDs for a fair
            line (not v1&apos;s full-set 0.714). BrEaST is the only fully external test set. If the
            average across seeds fails any rule, v1 stays. Among passing seeds we pick the median by
            clean Dice, not the best single run. Source: <code>results/v2_experiment.json</code>.
          </p>
          <details className="tech-details">
            <summary>Technical details</summary>
            <p className="muted tiny">
              Candidates use the same INT8 export path as v1. Promotion uses seed means and median
              clean Dice among passes.
            </p>
          </details>
          {data.v2_experiment.promotion_rule && (
            <p className="muted tiny">{data.v2_experiment.promotion_rule}</p>
          )}
          {data.v2_experiment.swap_criteria && data.v2_experiment.swap_criteria.length > 0 && (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Criterion</th>
                    <th>Rule</th>
                    <th>v1</th>
                    <th>v2 mean ± SD</th>
                    <th>Δ (95% CI)</th>
                    <th>Result</th>
                  </tr>
                </thead>
                <tbody>
                  {data.v2_experiment.swap_criteria.map((row) => (
                    <tr key={row.criterion}>
                      <td>
                        {row.criterion}
                        {row.note ? <div className="muted tiny">{row.note}</div> : null}
                      </td>
                      <td>{row.rule}</td>
                      <td>{row.v1 == null ? '—' : row.v1.toFixed(3)}</td>
                      <td>
                        {row.v2 == null
                          ? '—'
                          : row.v2_sd == null
                            ? row.v2.toFixed(3)
                            : `${row.v2.toFixed(3)} ± ${row.v2_sd.toFixed(3)}`}
                      </td>
                      <td>
                        {row.delta == null
                          ? '—'
                          : `${row.delta >= 0 ? '+' : ''}${row.delta.toFixed(4)}${
                              row.delta_ci95 && row.delta_ci95[0] != null && row.delta_ci95[1] != null
                                ? ` [${Number(row.delta_ci95[0]).toFixed(4)}, ${Number(row.delta_ci95[1]).toFixed(4)}]`
                                : ''
                            }`}
                      </td>
                      <td>{row.passed ? 'Pass' : 'Fail'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <p>
            {data.v2_experiment.decision_sentence ??
              (data.v2_experiment.served_unchanged !== false
                ? 'v2 did not meet the rule, so the site keeps serving v1.0.0.'
                : 'v2 met the rule, so the site serves v2.0.0.')}
          </p>
          {data.v2_experiment.table && data.v2_experiment.table.length > 0 && (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Setting</th>
                    <th>Dice</th>
                    <th>Clean Dice</th>
                    <th>BUS-BRA (same-source held-out)</th>
                    <th>BrEaST (external)</th>
                    <th>AUC</th>
                    <th>Model size (MB)</th>
                  </tr>
                </thead>
                <tbody>
                  {data.v2_experiment.table.map((row) => (
                    <tr key={row.name}>
                      <td>{row.name}</td>
                      <td>
                        {fmt(row.dice)}
                        {row.dice_sd != null ? ` ± ${fmt(row.dice_sd)}` : ''}
                      </td>
                      <td>
                        {fmt(row.clean_dice)}
                        {row.clean_dice_sd != null ? ` ± ${fmt(row.clean_dice_sd)}` : ''}
                      </td>
                      <td>
                        {fmt(row.busbra_dice)}
                        {row.busbra_dice_sd != null ? ` ± ${fmt(row.busbra_dice_sd)}` : ''}
                      </td>
                      <td>
                        {fmt(row.breast_dice)}
                        {row.breast_dice_sd != null ? ` ± ${fmt(row.breast_dice_sd)}` : ''}
                      </td>
                      <td>
                        {fmt(row.auc)}
                        {row.auc_sd != null ? ` ± ${fmt(row.auc_sd)}` : ''}
                      </td>
                      <td>{fmt(row.int8_mb, 1)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}

      {data.inpaint_experiment && (
        <section className="panel" style={{ marginTop: '1rem' }} id="caliper-inpaint">
          <h2 className="section-title">What if we erase the calipers?</h2>
          <p>
            Telea inpainting removes detected marker pixels (digitally altered images). E-a scores
            frozen v1 on original vs inpainted test; E-b is a random-region control on clean images;
            E-c retrains on inpainted training data. See <code>results/inpaint_experiment.json</code>.
          </p>
          <h3 className="section-title" style={{ fontSize: '1.05rem' }}>
            Model-swap rule
          </h3>
          {data.inpaint_experiment.swap_criteria && data.inpaint_experiment.swap_criteria.length > 0 && (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Criterion</th>
                    <th>Rule</th>
                    <th>v1</th>
                    <th>v2</th>
                    <th>Result</th>
                  </tr>
                </thead>
                <tbody>
                  {data.inpaint_experiment.swap_criteria.map((row) => (
                    <tr key={row.criterion}>
                      <td>{row.criterion}</td>
                      <td>{row.rule}</td>
                      <td>{row.v1 == null ? '—' : row.v1.toFixed(3)}</td>
                      <td>{row.v2 == null ? '—' : row.v2.toFixed(3)}</td>
                      <td>{row.passed ? 'Pass' : 'Fail'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <p>
            {data.inpaint_experiment.decision_sentence ??
              (data.inpaint_experiment.served_unchanged !== false
                ? 'v2 did not meet the rule, so the site keeps serving v1.0.0.'
                : 'v2 met the rule, so the site serves v2.0.0.')}
          </p>
          {data.inpaint_experiment.table && (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Setting</th>
                    <th>Dice</th>
                    <th>Lesion Dice</th>
                    <th>AUC</th>
                  </tr>
                </thead>
                <tbody>
                  {data.inpaint_experiment.table.map((row) => (
                    <tr key={row.name}>
                      <td>{row.name}</td>
                      <td>{fmt(row.dice)}</td>
                      <td>{fmt(row.lesion_dice)}</td>
                      <td>{fmt(row.auc)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <div className="before-after" style={{ marginTop: '0.75rem' }}>
            <figure>
              <img
                src={`${import.meta.env.BASE_URL}samples/external/breast_03_with_synthetic_calipers.png`}
                alt="BrEaST sample with synthetic calipers"
              />
              <figcaption className="muted tiny">Before (synthetic calipers · digitally altered)</figcaption>
            </figure>
            <figure>
              <img
                src={`${import.meta.env.BASE_URL}samples/external/breast_03_calipers_inpainted.png`}
                alt="Same sample after Telea inpainting"
              />
              <figcaption className="muted tiny">After Telea inpaint · digitally altered · CC BY BrEaST</figcaption>
            </figure>
          </div>
          {data.inpaint_experiment.before_after_note && (
            <p className="muted tiny">{data.inpaint_experiment.before_after_note}</p>
          )}
        </section>
      )}

      {data.uncertainty && (
        <section className="panel" style={{ marginTop: '1rem' }} id="uncertainty">
          <h2 className="section-title">Uncertainty from image flips</h2>
          <p>
            When we flip and brighten images offline, higher uncertainty tends to pair with lower
            outline-overlap score (Dice). At 80% coverage (keep the least uncertain 80%), mean Dice is{' '}
            {fmt(data.uncertainty.dice_at_80_coverage)} out of 1. This measures agreement under small
            changes. It is not a diagnostic probability.
          </p>
          <details className="tech-details">
            <summary>Technical details</summary>
            <p className="muted tiny">
              8-fold test-time augmentation (TTA). Spearman(uncertainty, 1−Dice) ρ ={' '}
              {fmt(data.uncertainty.spearman_rho)} (p={fmt(data.uncertainty.spearman_p, 4)}).
            </p>
          </details>
        </section>
      )}

      <section className="panel" style={{ marginTop: '1rem' }}>
        <h2 className="section-title">Model Errors explorer</h2>
        <p>
          Browse filterable error cases with AI-generated analysis notes (outline silhouettes only for
          BUSI). <Link to="/model-errors">Open model errors explorer →</Link>
        </p>
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
                  Chance cancerous {fmt(mrow.cls_prob)}
                </figcaption>
              </figure>
            ))}
          </div>
        </section>
      )}

      {data.surabhi_prompts?.length > 0 && (
        <section className="panel" style={{ marginTop: '1rem' }}>
          <h2 className="section-title">Discussion prompts</h2>
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
