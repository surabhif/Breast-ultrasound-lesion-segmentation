import { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import samplesManifest from '../data/samples.json'
import { MODEL_STATUS } from '../lib/constants'
import {
  getSession,
  runInference,
  type InferenceResult,
  type LoadProgress,
} from '../lib/inference'
import { maskToOverlay } from '../lib/image'

type Sample = (typeof samplesManifest.samples)[number]

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

export default function DemoPage() {
  const [searchParams] = useSearchParams()
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [selectedMeta, setSelectedMeta] = useState<Sample | null>(null)
  const [sourceUrl, setSourceUrl] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<InferenceResult | null>(null)
  const [opacity, setOpacity] = useState(0.5)
  const [loadProgress, setLoadProgress] = useState<LoadProgress>({
    status: 'idle',
    loadedBytes: 0,
    totalBytes: null,
    message: 'Model not loaded yet',
  })
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const objectUrlRef = useRef<string | null>(null)
  const preloadDone = useRef(false)

  useEffect(() => {
    void getSession(setLoadProgress).catch(() => {
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
      ctx.drawImage(overlayCanvas, 0, 0)
    }
    img.src = sourceUrl
  }, [sourceUrl, result, opacity])

  async function analyze(src: string | File, meta?: Sample) {
    setBusy(true)
    setError(null)
    setResult(null)
    try {
      if (objectUrlRef.current) {
        URL.revokeObjectURL(objectUrlRef.current)
        objectUrlRef.current = null
      }
      const url = typeof src === 'string' ? src : URL.createObjectURL(src)
      if (typeof src !== 'string') objectUrlRef.current = url
      setSourceUrl(url)
      setSelectedId(meta?.id ?? null)
      setSelectedMeta(meta ?? null)
      const out = await runInference(src, setLoadProgress)
      setResult(out)
    } catch (err) {
      console.error(err)
      setError(err instanceof Error ? err.message : 'Inference failed')
    } finally {
      setBusy(false)
    }
  }

  useEffect(() => {
    if (preloadDone.current) return
    const id = searchParams.get('sample')
    if (!id) return
    const sample = samplesManifest.samples.find((s) => s.id === id)
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

  return (
    <div className="fade-in demo-page">
      <header className="page-intro">
        <h1>Try the detector</h1>
        <p>
          Choose a real BUSI held-out test image or upload your own ultrasound. Inference runs
          entirely in your browser.
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
          First visit downloads ~{MODEL_STATUS.sizeHintMb} MB ({MODEL_STATUS.label}); later visits
          use the browser cache when available.
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
          <div className="viewer">
            {!sourceUrl && !busy && (
              <div className="viewer-empty">
                <p>No image selected yet.</p>
                <p className="muted">
                  Click a gallery sample to compare the predicted outline with the BUSI label, or
                  upload an image.
                </p>
              </div>
            )}
            {busy && !result && (
              <div className="viewer-empty">
                <p>Running model…</p>
                <p className="muted">Drawing the lesion mask and score locally in your browser.</p>
              </div>
            )}
            {sourceUrl && <canvas ref={canvasRef} aria-label="Ultrasound with lesion overlay" />}
          </div>

          <div className="result-row">
            <div className="gauge" aria-label="Predicted malignant probability">
              <svg viewBox="0 0 120 70" className="gauge-svg" role="img">
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
                  BUSI test sample
                </p>
              ) : (
                <p className="muted">Available for gallery samples only.</p>
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
            <span>Overlay opacity</span>
            <input
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={opacity}
              onChange={(e) => setOpacity(Number(e.target.value))}
              disabled={!result}
            />
            <span className="muted">{Math.round(opacity * 100)}%</span>
          </label>

          <details className="explainer heatmap-explainer">
            <summary>How to read this overlay</summary>
            <p>
              Orange fill is the model&apos;s lesion probability map; the darker outline is a
              thresholded contour. The score is an auxiliary benign-vs-malignant head and is only
              meaningful when a lesion is present. Research demo — not for clinical use.
            </p>
          </details>
        </section>
      </div>
    </div>
  )
}
