/**
 * Build a downloadable PNG of the scan with outline, class score, and disclaimer.
 * Client-side only — no upload.
 */

export type ResultPngInput = {
  /** Canvas already showing the scan with the model outline. */
  previewCanvas: HTMLCanvasElement
  clsProb: number
  /** Optional lean label for the class score line. */
  leanLabel?: string | null
  modelVersion?: string
}

const DISCLAIMER = 'Research demo, not for clinical use'
const SCORE_LABEL = 'Benign / malignant score'

function formatPct(p: number): string {
  return `${(p * 100).toFixed(1)}%`
}

/** Draw preview + caption strip into a new canvas and return a PNG Blob. */
export async function buildResultPng(input: ResultPngInput): Promise<Blob> {
  const src = input.previewCanvas
  const pad = 16
  const captionH = 88
  const outW = Math.max(src.width, 360)
  const outH = src.height + captionH + pad * 2
  const canvas = document.createElement('canvas')
  canvas.width = outW
  canvas.height = outH
  const ctx = canvas.getContext('2d')
  if (!ctx) throw new Error('Canvas 2D unavailable')

  ctx.fillStyle = '#0e0e0e'
  ctx.fillRect(0, 0, outW, outH)

  const drawW = Math.min(src.width, outW - pad * 2)
  const drawH = Math.round((src.height / src.width) * drawW)
  const dx = Math.round((outW - drawW) / 2)
  ctx.drawImage(src, dx, pad, drawW, drawH)

  const textY = pad + drawH + 28
  ctx.fillStyle = '#f2f7f7'
  ctx.font = '600 16px sans-serif'
  const lean = input.leanLabel ? ` (${input.leanLabel})` : ''
  ctx.fillText(`${SCORE_LABEL}: ${formatPct(input.clsProb)}${lean}`, pad, textY)

  ctx.font = '13px sans-serif'
  ctx.fillStyle = '#cadcdc'
  ctx.fillText(DISCLAIMER, pad, textY + 24)
  if (input.modelVersion) {
    ctx.fillText(`Model v${input.modelVersion}`, pad, textY + 44)
  }

  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (!blob) reject(new Error('PNG export failed'))
      else resolve(blob)
    }, 'image/png')
  })
}

/** Trigger a browser download for a PNG blob. */
export function downloadResultPng(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.rel = 'noopener'
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 2_000)
}

/** Pure caption helpers (unit-tested without canvas). */
export function resultPngCaption(clsProb: number, leanLabel?: string | null): {
  scoreLine: string
  disclaimer: string
} {
  const lean = leanLabel ? ` (${leanLabel})` : ''
  return {
    scoreLine: `${SCORE_LABEL}: ${formatPct(clsProb)}${lean}`,
    disclaimer: DISCLAIMER,
  }
}
