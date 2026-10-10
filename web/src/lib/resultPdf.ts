/**
 * Minimal one-page PDF builder (no external deps).
 * Embeds a JPEG preview plus text lines for metrics / disclaimer.
 */

export type ResultPdfMeasurementLines = {
  areaPx: number
  areaMm2: number | null
  longestDiameterPx: number
  longestDiameterMm: number | null
  perpendicularWidthPx: number
  perpendicularWidthMm: number | null
}

export type ResultPdfInput = {
  /** JPEG bytes of the overlay preview (canvas.toBlob('image/jpeg')). */
  previewJpeg: Uint8Array
  previewWidth: number
  previewHeight: number
  clsProb: number
  dice: number | null
  iou: number | null
  measurements: ResultPdfMeasurementLines | null
  modelVersion: string
  sampleLabel?: string | null
  generatedAt?: Date
}

const PAGE_W = 612
const PAGE_H = 792
const MARGIN = 48

function pdfEscape(text: string): string {
  return text.replace(/\\/g, '\\\\').replace(/\(/g, '\\(').replace(/\)/g, '\\)')
}

function wrapLines(text: string, maxChars: number): string[] {
  const words = text.split(/\s+/)
  const lines: string[] = []
  let cur = ''
  for (const w of words) {
    const next = cur ? `${cur} ${w}` : w
    if (next.length > maxChars && cur) {
      lines.push(cur)
      cur = w
    } else {
      cur = next
    }
  }
  if (cur) lines.push(cur)
  return lines
}

/** Build a single-page PDF Blob with preview image + result summary. */
export function buildResultPdf(input: ResultPdfInput): Blob {
  const when = (input.generatedAt ?? new Date()).toISOString().slice(0, 19).replace('T', ' ')
  const maxPreviewW = PAGE_W - 2 * MARGIN
  const maxPreviewH = 320
  const scale = Math.min(maxPreviewW / input.previewWidth, maxPreviewH / input.previewHeight, 1)
  const imgW = Math.max(1, Math.round(input.previewWidth * scale))
  const imgH = Math.max(1, Math.round(input.previewHeight * scale))
  const imgX = MARGIN
  const imgY = PAGE_H - MARGIN - 28 - imgH

  // Helvetica / WinAnsi: keep ASCII-safe punctuation in the content stream.
  const lines: string[] = [
    'Breast Ultrasound Lesion Segmentation - research result',
    `Generated: ${when} UTC`,
    `Model version: ${input.modelVersion}`,
  ]
  if (input.sampleLabel) lines.push(`Sample: ${input.sampleLabel}`)
  lines.push(`P(malignant): ${(input.clsProb * 100).toFixed(1)}%`)
  if (input.dice != null) {
    lines.push(`Dice: ${input.dice.toFixed(2)}${input.iou != null ? ` | IoU: ${input.iou.toFixed(2)}` : ''}`)
  } else {
    lines.push('Dice: n/a (no expert mask for this image)')
  }
  if (input.measurements) {
    const m = input.measurements
    let area = `Area: ${m.areaPx.toFixed(0)} px`
    if (m.areaMm2 != null) area += ` (~${m.areaMm2.toFixed(2)} mm2)`
    lines.push(area)
    let diam = `Longest diameter: ${m.longestDiameterPx.toFixed(1)} px`
    if (m.longestDiameterMm != null) diam += ` (~${m.longestDiameterMm.toFixed(2)} mm)`
    lines.push(diam)
    let width = `Perp. width: ${m.perpendicularWidthPx.toFixed(1)} px`
    if (m.perpendicularWidthMm != null) width += ` (~${m.perpendicularWidthMm.toFixed(2)} mm)`
    lines.push(width)
  }
  lines.push('')
  lines.push(...wrapLines('Research demo only - not for clinical use or diagnosis.', 72))
  lines.push(...wrapLines('Your image stays in this browser. Nothing is uploaded.', 72))

  const contentOps: string[] = []
  contentOps.push('q')
  contentOps.push(`${imgW} 0 0 ${imgH} ${imgX} ${imgY} cm`)
  contentOps.push('/Im1 Do')
  contentOps.push('Q')

  const textY = imgY - 22
  contentOps.push('BT')
  contentOps.push('/F1 11 Tf')
  contentOps.push(`${MARGIN} ${textY} Td`)
  lines.forEach((line, idx) => {
    if (idx > 0) contentOps.push('0 -15 Td')
    contentOps.push(`(${pdfEscape(line)}) Tj`)
  })
  contentOps.push('ET')
  const contentStream = contentOps.join('\n')

  const jpeg = input.previewJpeg
  const objects: (string | Uint8Array)[] = []
  // 1 Catalog
  objects.push('<< /Type /Catalog /Pages 2 0 R >>')
  // 2 Pages
  objects.push('<< /Type /Pages /Kids [3 0 R] /Count 1 >>')
  // 3 Page
  objects.push(
    `<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${PAGE_W} ${PAGE_H}] ` +
      `/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> /XObject << /Im1 6 0 R >> >> >>`,
  )
  // 4 Contents
  objects.push(`<< /Length ${contentStream.length} >>\nstream\n${contentStream}\nendstream`)
  // 5 Font
  objects.push('<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>')
  // 6 Image XObject — binary JPEG (placeholder; written as bytes below)
  objects.push('__IMAGE__')
  const imgHeader =
    `<< /Type /XObject /Subtype /Image /Width ${input.previewWidth} /Height ${input.previewHeight} ` +
    `/ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length ${jpeg.byteLength} >>\nstream\n`
  const imgFooter = '\nendstream'
  const imgObj = concatBytes(
    new TextEncoder().encode(imgHeader),
    jpeg,
    new TextEncoder().encode(imgFooter),
  )

  const enc = new TextEncoder()
  const parts: Uint8Array[] = []
  const pushStr = (s: string) => parts.push(enc.encode(s))

  pushStr('%PDF-1.4\n')
  const offsets: number[] = [0]
  let offset = byteLength(parts)

  for (let i = 0; i < objects.length; i++) {
    offsets.push(offset)
    const n = i + 1
    if (objects[i] === '__IMAGE__') {
      pushStr(`${n} 0 obj\n`)
      parts.push(imgObj)
      pushStr('\nendobj\n')
    } else {
      pushStr(`${n} 0 obj\n${objects[i] as string}\nendobj\n`)
    }
    offset = byteLength(parts)
  }

  const xrefStart = offset
  pushStr(`xref\n0 ${objects.length + 1}\n`)
  pushStr('0000000000 65535 f \n')
  for (let i = 1; i <= objects.length; i++) {
    pushStr(`${String(offsets[i]).padStart(10, '0')} 00000 n \n`)
  }
  pushStr(`trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\n`)
  pushStr(`startxref\n${xrefStart}\n%%EOF\n`)

  return new Blob(parts as BlobPart[], { type: 'application/pdf' })
}

function byteLength(parts: Uint8Array[]): number {
  return parts.reduce((n, p) => n + p.byteLength, 0)
}

function concatBytes(...chunks: Uint8Array[]): Uint8Array {
  const total = chunks.reduce((n, c) => n + c.byteLength, 0)
  const out = new Uint8Array(total)
  let o = 0
  for (const c of chunks) {
    out.set(c, o)
    o += c.byteLength
  }
  return out
}

/** Trigger a browser download of the result PDF. */
export function downloadResultPdf(blob: Blob, filename = 'busi-result.pdf'): void {
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

/** Encode an HTMLCanvasElement to JPEG bytes for the PDF. */
export async function canvasToJpegBytes(
  canvas: HTMLCanvasElement,
  quality = 0.88,
): Promise<Uint8Array> {
  const blob = await new Promise<Blob | null>((resolve) =>
    canvas.toBlob((b) => resolve(b), 'image/jpeg', quality),
  )
  if (!blob) throw new Error('Could not encode preview JPEG for PDF')
  return new Uint8Array(await blob.arrayBuffer())
}
