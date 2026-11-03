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

function fitText(
  ctx: CanvasRenderingContext2D,
  text: string,
  maxWidth: number,
): string[] {
  if (ctx.measureText(text).width <= maxWidth) return [text]
  const words = text.split(/\s+/)
  const lines: string[] = []
  let cur = ''
  for (const w of words) {
    const next = cur ? `${cur} ${w}` : w
    if (ctx.measureText(next).width > maxWidth && cur) {
      lines.push(cur)
      cur = w
    } else {
      cur = next
    }
  }
  if (cur) lines.push(cur)
  return lines
}

/** Draw preview + caption strip into a new canvas and return a PNG Blob. */
export async function buildResultPng(input: ResultPngInput): Promise<Blob> {
  const src = input.previewCanvas
  const pad = 16
  const outW = Math.max(src.width, 420)
  const textMax = outW - pad * 2

  // Measure caption height with a scratch context before sizing the canvas.
  const measure = document.createElement('canvas').getContext('2d')
  if (!measure) throw new Error('Canvas 2D unavailable')
  const lean = input.leanLabel ? ` (${input.leanLabel})` : ''
  const scoreLine = `${SCORE_LABEL}: ${formatPct(input.clsProb)}${lean}`
  measure.font = '600 16px sans-serif'
  const scoreLines = fitText(measure, scoreLine, textMax)
  measure.font = '13px sans-serif'
  const disclaimerLines = fitText(measure, DISCLAIMER, textMax)
  const versionLines = input.modelVersion ? [`Model v${input.modelVersion}`] : []
  const captionH = 20 + scoreLines.length * 22 + disclaimerLines.length * 18 + versionLines.length * 18 + 12

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

  let textY = pad + drawH + 28
  ctx.fillStyle = '#f2f7f7'
  ctx.font = '600 16px sans-serif'
  for (const line of scoreLines) {
    ctx.fillText(line, pad, textY)
    textY += 22
  }

  ctx.font = '13px sans-serif'
  ctx.fillStyle = '#cadcdc'
  for (const line of disclaimerLines) {
    ctx.fillText(line, pad, textY)
    textY += 18
  }
  for (const line of versionLines) {
    ctx.fillText(line, pad, textY)
    textY += 18
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
