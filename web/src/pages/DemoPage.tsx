import { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import samplesManifest from '../data/samples.json'
import externalSamples from '../data/external_samples.json'
import { MODEL_STATUS, SEG_THRESHOLD } from '../lib/constants'
import {
  preloadModel,
  runInference,
  runInferenceTta,
  rethreshold,
  type InferenceResult,
  type LoadProgress,
} from '../lib/inference'
import { downsampleMaskNearest, diceScore, iouScore } from '../lib/metrics'
import { measureLesion, type LesionMeasurements } from '../lib/measure'
import { maskToOverlay } from '../lib/image'
import { overallUncertaintySummary, type TtaResult } from '../lib/tta'
import { sampleHasExpert, sampleSourceLabel, sampleSpacingMm } from '../lib/sampleMeta'

type Sample = {
  id: string
  src: string
  mask_src?: string
  label: string
  groundTruthMalignant?: boolean | null
  hasLesion?: boolean
  case_id?: string
  kind?: string
  annotation_flag?: boolean
  note?: string
  reported_dice_int8?: number
  reported_cls_prob_int8?: number
  pixel_size_mm?: number | null
  orig_width?: number | null
  orig_height?: number | null
  mm_per_mask_px_160?: number | null
  attribution?: string
  dataset?: string
  licence?: string
  birads?: string
}

type CompareMode = 'model' | 'expert' | 'both' | 'difference'

function formatPct(p: number) {
  return `${(p * 100).toFixed(1)}%`
}

function uncertaintyWording(clsProb: number, maskMean: number): string {
  if (maskMean < 0.02) {
    return 'Little lesion evidence in the mask — the benign/malignant score is less meaningful when no lesion is detected.'
  }
  if (clsProb >= 0.35 && clsProb <= 0.65) {
    return 'Score near 0.5: uncertain. Treat as inconclusive, not a diagnosis.'
  }
  if (clsProb > 0.65) {
    return 'Higher score leans malignant in this research model only — not clinical advice.'
  }
  return 'Lower score leans benign in this research model only — not clinical advice.'
}

const ALL_SAMPLES: Sample[] = [
  ...(samplesManifest.samples as Sample[]),
  ...externalSamples.samples.map((s) => ({ ...s, annotation_flag: false })),
]

export default function DemoPage() {
  const [searchParams] = useSearchParams()
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [selectedMeta, setSelectedMeta] = useState<Sample | null>(null)
  const [sourceUrl, setSourceUrl] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<InferenceResult | null>(null)
  const [opacity, setOpacity] = useState(0.5)
  const [compareMode, setCompareMode] = useState<CompareMode>('both')
  const [expertMask, setExpertMask] = useState<Float32Array | null>(null)
  const [browserDice, setBrowserDice] = useState<number | null>(null)
  const [browserIoU, setBrowserIoU] = useState<number | null>(null)
  const [measurements, setMeasurements] = useState<LesionMeasurements | null>(null)
  const [showMeasureOverlay, setShowMeasureOverlay] = useState(true)
  const [segThr, setSegThr] = useState(SEG_THRESHOLD)
  const [clsThr, setClsThr] = useState(0.5)
  const [useTta, setUseTta] = useState(false)
  const [tta, setTta] = useState<TtaResult | null>(null)
  const [showUncertainty, setShowUncertainty] = useState(false)
  const [ttaStep, setTtaStep] = useState<string | null>(null)
  const [loadProgress, setLoadProgress] = useState<LoadProgress>({
    status: 'idle',
    loadedBytes: 0,
    totalBytes: null,
    message: 'Model not loaded yet',
  })
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const objectUrlRef = useRef<string | null>(null)
  const preloadDone = useRef(false)
  const analyzeGen = useRef(0)

  useEffect(() => {
    void preloadModel(setLoadProgress).catch(() => {
      /* progress callback already records error */
    })
    return () => {
      if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current)
    }
  }, [])

  useEffect(() => {
    if (!sourceUrl || !result || !canvasRef.current) return
    const canvas = canvasRef.current
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const img = new Image()
    img.crossOrigin = 'anonymous'
    img.onload = () => {
      canvas.width = result.displayWidth
      canvas.height = result.displayHeight
      ctx.clearRect(0, 0, canvas.width, canvas.height)
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height)

      const mode = selectedMeta?.mask_src ? compareMode : 'model'

      if (mode === 'model' || mode === 'both' || mode === 'difference') {
        if (mode !== 'difference') {
          const overlay = maskToOverlay(
            result.mask,
            result.maskH,
            result.maskW,
            result.displayWidth,
            result.displayHeight,
            opacity,
          )
          const overlayCanvas = document.createElement('canvas')
          overlayCanvas.width = result.displayWidth
          overlayCanvas.height = result.displayHeight
          overlayCanvas.getContext('2d')!.putImageData(overlay, 0, 0)
          if (mode === 'model') ctx.drawImage(overlayCanvas, 0, 0)
          else {
            // both: draw model dashed outline only (lighter fill)
            ctx.globalAlpha = opacity * 0.55
            ctx.drawImage(overlayCanvas, 0, 0)
            ctx.globalAlpha = 1
          }
        }
      }

      if (expertMask && (mode === 'expert' || mode === 'both' || mode === 'difference')) {
        drawExpertOutline(ctx, expertMask, result.maskH, result.maskW, result.displayWidth, result.displayHeight, mode)
      }

      if (mode === 'difference' && expertMask) {
        drawDifference(ctx, result.mask, expertMask, result.maskH, result.maskW, result.displayWidth, result.displayHeight)
      }

      if (showUncertainty && tta) {
        const heat = document.createElement('canvas')
        heat.width = result.maskW
        heat.height = result.maskH
        const hctx = heat.getContext('2d')!
        const imgData = hctx.createImageData(result.maskW, result.maskH)
        for (let i = 0; i < tta.stdMask.length; i++) {
          const v = Math.min(1, tta.stdMask[i]! * 4)
          imgData.data[i * 4] = Math.round(255 * v)
          imgData.data[i * 4 + 1] = Math.round(40 * (1 - v))
          imgData.data[i * 4 + 2] = Math.round(180 * (1 - v))
          imgData.data[i * 4 + 3] = Math.round(160 * v * opacity)
        }
        hctx.putImageData(imgData, 0, 0)
        ctx.drawImage(heat, 0, 0, result.displayWidth, result.displayHeight)
      }

      if (showMeasureOverlay && measurements?.diameterLine) {
        const sx = result.displayWidth / result.maskW
        const sy = result.displayHeight / result.maskH
        const [[x0, y0], [x1, y1]] = measurements.diameterLine
        ctx.strokeStyle = '#1a1a1a'
        ctx.lineWidth = 2
        ctx.beginPath()
        ctx.moveTo(x0 * sx, y0 * sy)
        ctx.lineTo(x1 * sx, y1 * sy)
        ctx.stroke()
        if (measurements.widthLine) {
          const [[wx0, wy0], [wx1, wy1]] = measurements.widthLine
          ctx.setLineDash([4, 3])
          ctx.beginPath()
          ctx.moveTo(wx0 * sx, wy0 * sy)
          ctx.lineTo(wx1 * sx, wy1 * sy)
          ctx.stroke()
          ctx.setLineDash([])
        }
      }
    }
    img.src = sourceUrl
  }, [
    sourceUrl,
    result,
    opacity,
    compareMode,
    expertMask,
    selectedMeta,
    measurements,
    showMeasureOverlay,
    showUncertainty,
    tta,
  ])

  async function loadExpert(meta: Sample | undefined, maskH: number, maskW: number) {
    if (!meta?.mask_src) {
      setExpertMask(null)
      setBrowserDice(null)
      setBrowserIoU(null)
      return null
    }
    const url = `${import.meta.env.BASE_URL}${meta.mask_src}`
    const img = new Image()
    img.crossOrigin = 'anonymous'
    await new Promise<void>((resolve, reject) => {
      img.onload = () => resolve()
      img.onerror = () => reject(new Error('Failed to load expert mask'))
      img.src = url
    })
    const expert = downsampleMaskNearest(img, maskW)
    // height assumed square 160
    void maskH
    return expert
  }

  async function analyze(src: string | File, meta?: Sample) {
    const gen = ++analyzeGen.current
    // Bind selection immediately so GT / spacing cannot lag behind a prior sample.
    setSelectedId(meta?.id ?? null)
    setSelectedMeta(meta ?? null)
    setBusy(true)
    setError(null)
    setResult(null)
    setExpertMask(null)
    setBrowserDice(null)
    setBrowserIoU(null)
    setMeasurements(null)
    setTta(null)
    setTtaStep(null)
    try {
      if (objectUrlRef.current) {
        URL.revokeObjectURL(objectUrlRef.current)
        objectUrlRef.current = null
      }
      const url = typeof src === 'string' ? src : URL.createObjectURL(src)
      if (typeof src !== 'string') objectUrlRef.current = url
      setSourceUrl(url)
      let out: InferenceResult
      if (useTta) {
        const ttaOut = await runInferenceTta(src, setLoadProgress, (i, n) => {
          if (gen === analyzeGen.current) setTtaStep(`TTA ${i}/${n}`)
        })
        if (gen !== analyzeGen.current) return
        setTta(ttaOut.tta)
        out = ttaOut
      } else {
        out = await runInference(src, setLoadProgress, { segThreshold: segThr })
        if (gen !== analyzeGen.current) return
      }
      setResult(out)
      setTtaStep(null)

      const expert = await loadExpert(meta, out.maskH, out.maskW)
      if (gen !== analyzeGen.current) return
      if (expert) {
        setExpertMask(expert)
        const predBin = new Float32Array(out.mask.length)
        for (let i = 0; i < out.mask.length; i++) predBin[i] = out.mask[i]! > segThr ? 1 : 0
        setBrowserDice(diceScore(predBin, expert, 0.5))
        setBrowserIoU(iouScore(predBin, expert, 0.5))
      }

      const spacing = sampleSpacingMm(meta ?? null, out.maskW)
      setMeasurements(measureLesion(out.mask, out.maskH, out.maskW, spacing, segThr))
    } catch (err) {
      if (gen !== analyzeGen.current) return
      console.error(err)
      setError(err instanceof Error ? err.message : 'Inference failed')
    } finally {
      if (gen === analyzeGen.current) setBusy(false)
    }
  }

  useEffect(() => {
    if (preloadDone.current) return
    const id = searchParams.get('sample')
    if (!id) return
    const sample = ALL_SAMPLES.find((s) => s.id === id)
    if (!sample) return
    preloadDone.current = true
    void analyze(`${import.meta.env.BASE_URL}${sample.src}`, sample)
  }, [searchParams])

  const progressPct =
    loadProgress.totalBytes && loadProgress.totalBytes > 0
      ? Math.min(100, Math.round((100 * loadProgress.loadedBytes) / loadProgress.totalBytes))
      : loadProgress.status === 'ready'
        ? 100
        : loadProgress.status === 'downloading'
          ? 15
          : 0

  const hasExpert = sampleHasExpert(selectedMeta)

  return (
    <div className="fade-in demo-page">
      <header className="page-intro">
        <h1>Try the detector</h1>
        <p>
          Choose a BUSI gallery sample or a CC BY BrEaST sample, or upload your own ultrasound.
          Inference runs entirely in your browser. Research demo — not for clinical use.
        </p>
      </header>

      <div className="model-progress panel" aria-live="polite">
        <div className="model-progress-row">
          <strong>Model status</strong>
          <span className="muted">{loadProgress.message}</span>
        </div>
        <div
          className="progress-track"
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={progressPct}
          aria-label="Model download progress"
        >
          <div className="progress-fill" style={{ width: `${progressPct}%` }} />
        </div>
        <p className="muted tiny">
          First visit downloads ~{MODEL_STATUS.sizeHintMb} MB ({MODEL_STATUS.label} v
          {MODEL_STATUS.version}); later visits use the browser cache when available.
        </p>
      </div>

      <div className="demo-layout">
        <section className="panel">
          <h2 className="section-title">Sample gallery</h2>
          <p className="muted" style={{ marginTop: 0 }}>
            {samplesManifest.disclaimer}
          </p>
          <div className="gallery-grid">
            {samplesManifest.samples.map((sample) => (
              <button
                key={sample.id}
                type="button"
                className={`gallery-item${selectedId === sample.id ? ' selected' : ''}`}
                onClick={() => analyze(`${import.meta.env.BASE_URL}${sample.src}`, sample)}
                disabled={busy || loadProgress.status === 'error'}
                aria-pressed={selectedId === sample.id}
              >
                <img
                  src={`${import.meta.env.BASE_URL}${sample.src}`}
                  alt={`${sample.label} ultrasound sample`}
                  width={120}
                  height={120}
                />
                <figcaption>
                  <span className={`badge ${sample.label}`}>{sample.label}</span>
                  {sample.annotation_flag ? ' · flagged marks' : ''}
                </figcaption>
              </button>
            ))}
          </div>

          <h3 className="section-title" style={{ marginTop: '1.25rem' }}>
            CC BY external (BrEaST)
          </h3>
          <p className="muted tiny">{externalSamples.disclaimer}</p>
          <div className="gallery-grid">
            {externalSamples.samples.map((sample) => (
              <button
                key={sample.id}
                type="button"
                className={`gallery-item${selectedId === sample.id ? ' selected' : ''}`}
                onClick={() => analyze(`${import.meta.env.BASE_URL}${sample.src}`, sample)}
                disabled={busy || loadProgress.status === 'error'}
                aria-pressed={selectedId === sample.id}
              >
                <img
                  src={`${import.meta.env.BASE_URL}${sample.src}`}
                  alt={`BrEaST ${sample.label}`}
                  width={120}
                  height={120}
                />
                <figcaption>
                  <span className={`badge ${sample.label}`}>{sample.label}</span> · CC BY
                </figcaption>
              </button>
            ))}
          </div>

          <div className="upload-row">
            <label className="btn secondary">
              Upload your own image
              <input
                className="sr-only"
                type="file"
                accept="image/*"
                disabled={busy || loadProgress.status === 'error'}
                onChange={(e) => {
                  const file = e.target.files?.[0]
                  if (file) void analyze(file)
                  e.target.value = ''
                }}
              />
            </label>
            {busy && <span className="muted">Running model…</span>}
          </div>
          {error && (
            <p className="error-text" role="alert">
              {error}
            </p>
          )}
        </section>

        <section className="panel">
          <h2 className="section-title">Mask overlay &amp; score</h2>

          <div
            className="compare-toggle"
            role="group"
            aria-label="Expert versus model view"
          >
            {(['model', 'expert', 'both', 'difference'] as CompareMode[]).map((m) => (
              <button
                key={m}
                type="button"
                className={compareMode === m ? 'active' : ''}
                disabled={!hasExpert && m !== 'model'}
                aria-pressed={compareMode === m}
                onClick={() => setCompareMode(m)}
              >
                {m}
              </button>
            ))}
          </div>
          {!hasExpert && (
            <p className="muted tiny">Expert / Difference modes need a gallery sample with a mask.</p>
          )}

          <div className="viewer">
            {!sourceUrl && !busy && (
              <div className="viewer-empty">
                <p>No image selected yet.</p>
                <p className="muted">Click a gallery sample or upload an image.</p>
              </div>
            )}
            {busy && !result && (
              <div className="viewer-empty">
                <p>Running model…</p>
              </div>
            )}
            {sourceUrl && <canvas ref={canvasRef} aria-label="Ultrasound with lesion overlay" />}
          </div>

          <div className="score-card" aria-live="polite">
            {hasExpert && browserDice != null ? (
              <>
                <p className="score-card-metrics">
                  <strong>
                    Dice {browserDice.toFixed(2)} · IoU {browserIoU?.toFixed(2)}
                  </strong>
                </p>
                <p className="muted tiny score-card-caption">
                  Browser INT8 vs expert @ 160²
                  {selectedMeta?.reported_dice_int8 != null &&
                    ` · reported INT8 ${selectedMeta.reported_dice_int8.toFixed(2)}`}
                </p>
                {selectedMeta?.label === 'normal' && (
                  <p className="tiny">
                    {result && result.maskMean < 0.01
                      ? 'Expert: no lesion. Model: no lesion ✓ (Dice defined as 1 when both empty).'
                      : 'Expert: no lesion. Model drew a lesion on a normal image ✗'}
                  </p>
                )}
              </>
            ) : (
              <p className="muted tiny">
                {selectedMeta
                  ? 'Per-image Dice appears for samples with expert masks.'
                  : 'Upload has no expert outline — Dice is not shown.'}
              </p>
            )}
          </div>

          <div className="result-row">
            <div className="gauge" aria-label="Predicted malignant probability">
              <svg
                viewBox="0 0 120 70"
                className="gauge-svg"
                role="img"
                aria-label="Gauge showing predicted malignant probability"
              >
                <path
                  d="M10 60 A50 50 0 0 1 110 60"
                  fill="none"
                  stroke="var(--line)"
                  strokeWidth="10"
                  strokeLinecap="round"
                />
                <path
                  d="M10 60 A50 50 0 0 1 110 60"
                  fill="none"
                  stroke="var(--accent)"
                  strokeWidth="10"
                  strokeLinecap="round"
                  strokeDasharray={`${(result ? result.clsProb : 0) * 157} 157`}
                />
                <text x="60" y="52" textAnchor="middle" className="gauge-text">
                  {result ? formatPct(result.clsProb) : '—'}
                </text>
              </svg>
              <div className="gauge-label">P(malignant)</div>
            </div>

            <div className="gt-card">
              <div className="label">Ground truth</div>
              {selectedMeta ? (
                <p>
                  <span className={`badge ${selectedMeta.label}`}>{selectedMeta.label}</span>{' '}
                  {sampleSourceLabel(selectedMeta)}
                </p>
              ) : (
                <p className="muted">No ground truth for uploads.</p>
              )}
              <p className="tiny muted">
                Mean mask activation: {result ? result.maskMean.toFixed(3) : '—'}
              </p>
            </div>
          </div>

          {result && (
            <p className="muted" style={{ marginTop: '0.5rem' }}>
              {uncertaintyWording(result.clsProb, result.maskMean)}
            </p>
          )}

          <label className="opacity-control">
            <span id="opacity-label">Overlay opacity</span>
            <input
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={opacity}
              onChange={(e) => setOpacity(Number(e.target.value))}
              disabled={!result}
              aria-labelledby="opacity-label"
              aria-valuemin={0}
              aria-valuemax={1}
              aria-valuenow={opacity}
              aria-valuetext={`${Math.round(opacity * 100)} percent`}
            />
            <span className="muted">{Math.round(opacity * 100)}%</span>
          </label>

          <label className="opacity-control">
            <span id="seg-thr-label">Mask threshold {segThr.toFixed(2)}</span>
            <input
              type="range"
              min={0.1}
              max={0.9}
              step={0.05}
              value={segThr}
              aria-labelledby="seg-thr-label"
              aria-valuemin={0.1}
              aria-valuemax={0.9}
              aria-valuenow={segThr}
              onChange={(e) => {
                const t = Number(e.target.value)
                setSegThr(t)
                if (result?.softMask) {
                  const next = rethreshold(
                    result.softMask,
                    result.maskH,
                    result.maskW,
                    result.displayWidth,
                    result.displayHeight,
                    t,
                  )
                  setResult({ ...result, mask: next.mask, overlay: next.overlay, maskMean: next.maskMean })
                  if (expertMask) {
                    const predBin = new Float32Array(next.mask.length)
                    for (let i = 0; i < next.mask.length; i++) predBin[i] = next.mask[i]! > t ? 1 : 0
                    setBrowserDice(diceScore(predBin, expertMask, 0.5))
                    setBrowserIoU(iouScore(predBin, expertMask, 0.5))
                  }
                  setMeasurements(
                    measureLesion(
                      next.mask,
                      result.maskH,
                      result.maskW,
                      sampleSpacingMm(selectedMeta, result.maskW),
                      t,
                    ),
                  )
                }
              }}
              disabled={!result}
            />
          </label>

          <label className="opacity-control">
            <span id="cls-thr-label">
              Class threshold {clsThr.toFixed(2)} →{' '}
              {result ? (result.clsProb >= clsThr ? 'malignant' : 'benign') : '—'}
            </span>
            <input
              type="range"
              min={0}
              max={1}
              step={0.01}
              value={clsThr}
              onChange={(e) => setClsThr(Number(e.target.value))}
              disabled={!result}
              aria-labelledby="cls-thr-label"
              aria-valuemin={0}
              aria-valuemax={1}
              aria-valuenow={clsThr}
            />
          </label>

          <div className="mistakes-filters" style={{ marginTop: '0.75rem' }}>
            <label className="radio-inline">
              <input
                type="checkbox"
                checked={useTta}
                onChange={(e) => setUseTta(e.target.checked)}
                aria-label="Estimate uncertainty with eight-fold test-time augmentation"
              />
              Estimate uncertainty (8× TTA — runs in Web Worker)
            </label>
            <label className="radio-inline">
              <input
                type="checkbox"
                checked={showUncertainty}
                onChange={(e) => setShowUncertainty(e.target.checked)}
                disabled={!tta}
                aria-label="Show uncertainty heatmap overlay"
              />
              Show uncertainty heatmap
            </label>
          </div>
          {ttaStep && <p className="muted tiny">{ttaStep}</p>}
          {tta && (
            <div className="score-card" style={{ marginTop: '0.5rem' }}>
              {(() => {
                const u = overallUncertaintySummary(tta.agreement, tta.clsStd)
                return (
                  <>
                    <p className="score-card-metrics">
                      <strong>Outline agreement: {u.outline}</strong>
                      <span className="muted tiny"> ({tta.agreement.toFixed(2)} pairwise Dice)</span>
                    </p>
                    <p className="score-card-metrics">
                      <strong>Score stability: {u.score}</strong>
                      <span className="muted tiny">
                        {' '}
                        (class-score spread {tta.clsStd.toFixed(3)} across TTA passes)
                      </span>
                    </p>
                    <p className="muted tiny">
                      These describe agreement under small flips/brightness changes — not a
                      probability of being wrong.
                    </p>
                    {u.warning && <p className="tiny">{u.warning}</p>}
                  </>
                )
              })()}
            </div>
          )}

          {measurements && (
            <div className="measure-card">
              <h3 className="section-title">Measurements (research only)</h3>
              <p className="muted tiny">
                Not clinical measurements. Computed on the 160×160 model mask
                {measurements.longestDiameterMm != null
                  ? ' with BrEaST spacing (cm→mm, scaled from original size to 160²). Approx. only.'
                  : ' in pixels (no physical spacing for BUSI).'}
              </p>
              <ul className="measure-list">
                <li>
                  Area: <strong>{measurements.areaPx.toFixed(0)} px</strong>
                  {measurements.areaMm2 != null && <> · ~{measurements.areaMm2.toFixed(2)} mm²</>}
                </li>
                <li>
                  Longest diameter:{' '}
                  <strong>{measurements.longestDiameterPx.toFixed(1)} px</strong>
                  {measurements.longestDiameterMm != null && (
                    <> · ~{measurements.longestDiameterMm.toFixed(2)} mm</>
                  )}
                </li>
                <li>
                  Perpendicular width:{' '}
                  <strong>{measurements.perpendicularWidthPx.toFixed(1)} px</strong>
                  {measurements.perpendicularWidthMm != null && (
                    <> · ~{measurements.perpendicularWidthMm.toFixed(2)} mm</>
                  )}
                </li>
                {measurements.depthWidthRatio != null && (
                  <li>Depth/width (bbox): {measurements.depthWidthRatio.toFixed(2)}</li>
                )}
              </ul>
              <label className="radio-inline">
                <input
                  type="checkbox"
                  checked={showMeasureOverlay}
                  onChange={(e) => setShowMeasureOverlay(e.target.checked)}
                  aria-label="Draw diameter and width measurement lines"
                />
                Draw diameter / width lines
              </label>
            </div>
          )}

          {selectedMeta?.attribution && (
            <p className="muted tiny" style={{ marginTop: '0.75rem' }}>
              {selectedMeta.attribution}
            </p>
          )}

          <details className="explainer heatmap-explainer">
            <summary>How to read this overlay</summary>
            <p>
              Orange = model lesion map; blue = expert outline when shown. Difference mode: teal =
              agreement, orange hatch = model-only, blue hatch = expert-only. Dice = 2×overlap ÷
              (expert + model). Research demo — not for clinical use.
            </p>
          </details>
        </section>
      </div>
    </div>
  )
}

function drawExpertOutline(
  ctx: CanvasRenderingContext2D,
  expert: Float32Array,
  maskH: number,
  maskW: number,
  outW: number,
  outH: number,
  mode: CompareMode,
) {
  const sx = outW / maskW
  const sy = outH / maskH
  ctx.strokeStyle = '#2B6CB0'
  ctx.lineWidth = mode === 'both' ? 2.5 : 2
  ctx.setLineDash(mode === 'both' ? [] : [])
  for (let y = 1; y < maskH - 1; y++) {
    for (let x = 1; x < maskW - 1; x++) {
      const i = y * maskW + x
      if (expert[i]! <= 0.5) continue
      const edge =
        expert[i - 1]! <= 0.5 ||
        expert[i + 1]! <= 0.5 ||
        expert[i - maskW]! <= 0.5 ||
        expert[i + maskW]! <= 0.5
      if (!edge) continue
      ctx.fillStyle = '#2B6CB0'
      ctx.fillRect(x * sx, y * sy, Math.max(sx, 1.5), Math.max(sy, 1.5))
    }
  }
  if (mode === 'expert') {
    // light blue fill
    for (let y = 0; y < maskH; y++) {
      for (let x = 0; x < maskW; x++) {
        if (expert[y * maskW + x]! > 0.5) {
          ctx.fillStyle = 'rgba(43,108,176,0.25)'
          ctx.fillRect(x * sx, y * sy, sx, sy)
        }
      }
    }
  }
}

function drawDifference(
  ctx: CanvasRenderingContext2D,
  model: Float32Array,
  expert: Float32Array,
  maskH: number,
  maskW: number,
  outW: number,
  outH: number,
) {
  const sx = outW / maskW
  const sy = outH / maskH
  for (let y = 0; y < maskH; y++) {
    for (let x = 0; x < maskW; x++) {
      const i = y * maskW + x
      const m = model[i]! > SEG_THRESHOLD
      const e = expert[i]! > 0.5
      if (m && e) ctx.fillStyle = 'rgba(41,115,115,0.45)'
      else if (m && !e) ctx.fillStyle = 'rgba(196,92,38,0.45)'
      else if (!m && e) ctx.fillStyle = 'rgba(43,108,176,0.45)'
      else continue
      ctx.fillRect(x * sx, y * sy, sx, sy)
    }
  }
}
