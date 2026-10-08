/** Lesion measurements on a binary mask (research only — not clinical). */

export type LesionMeasurements = {
  areaPx: number
  longestDiameterPx: number
  perpendicularWidthPx: number
  diameterLine: [[number, number], [number, number]] | null
  widthLine: [[number, number], [number, number]] | null
  circularity: number | null
  depthWidthRatio: number | null
  areaMm2: number | null
  longestDiameterMm: number | null
  perpendicularWidthMm: number | null
}

function pointsFromMask(mask: Float32Array | Uint8Array, h: number, w: number, thr = 0.5): Array<[number, number]> {
  const pts: Array<[number, number]> = []
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      if (Number(mask[y * w + x]!) > thr) pts.push([x, y])
    }
  }
  return pts
}

/** Max Feret diameter (farthest pixel pair) + perpendicular width through midpoint. */
export function measureLesion(
  mask: Float32Array | Uint8Array,
  height: number,
  width: number,
  pixelSizeMm: number | null = null,
  thr = 0.5,
): LesionMeasurements {
  const pts = pointsFromMask(mask, height, width, thr)
  const areaPx = pts.length
  if (areaPx === 0) {
    return {
      areaPx: 0,
      longestDiameterPx: 0,
      perpendicularWidthPx: 0,
      diameterLine: null,
      widthLine: null,
      circularity: null,
      depthWidthRatio: null,
      areaMm2: pixelSizeMm != null ? 0 : null,
      longestDiameterMm: pixelSizeMm != null ? 0 : null,
      perpendicularWidthMm: pixelSizeMm != null ? 0 : null,
    }
  }

  let best = 0
  let a: [number, number] = pts[0]!
  let b: [number, number] = pts[0]!
  for (let i = 0; i < pts.length; i++) {
    for (let j = i + 1; j < pts.length; j++) {
      const dx = pts[i]![0] - pts[j]![0]
      const dy = pts[i]![1] - pts[j]![1]
      const d2 = dx * dx + dy * dy
      if (d2 > best) {
        best = d2
        a = pts[i]!
        b = pts[j]!
      }
    }
  }
  const longest = Math.sqrt(best)
  const ux = b[0] - a[0]
  const uy = b[1] - a[1]
  const len = Math.hypot(ux, uy) || 1
  const px = -uy / len
  const py = ux / len
  let minP = Infinity
  let maxP = -Infinity
  let minPt: [number, number] = a
  let maxPt: [number, number] = a
  for (const [x, y] of pts) {
    const proj = (x - a[0]) * px + (y - a[1]) * py
    if (proj < minP) {
      minP = proj
      minPt = [x, y]
    }
    if (proj > maxP) {
      maxP = proj
      maxPt = [x, y]
    }
  }
  const perp = maxP - minP

  // Bounding-box depth/width (y = depth from top of image)
  let minX = width
  let maxX = 0
  let minY = height
  let maxY = 0
  for (const [x, y] of pts) {
    if (x < minX) minX = x
    if (x > maxX) maxX = x
    if (y < minY) minY = y
    if (y > maxY) maxY = y
  }
  const boxW = maxX - minX + 1
  const boxH = maxY - minY + 1
  const depthWidthRatio = boxW > 0 ? boxH / boxW : null

  // Circularity from perimeter estimate (4-connected edge count)
  let peri = 0
  for (const [x, y] of pts) {
    const i = y * width + x
    const edge =
      x === 0 ||
      y === 0 ||
      x === width - 1 ||
      y === height - 1 ||
      Number(mask[i - 1]!) <= thr ||
      Number(mask[i + 1]!) <= thr ||
      Number(mask[i - width]!) <= thr ||
      Number(mask[i + width]!) <= thr
    if (edge) peri++
  }
  const circularity = peri > 0 ? (4 * Math.PI * areaPx) / (peri * peri) : null

  const scale = pixelSizeMm
  return {
    areaPx,
    longestDiameterPx: longest,
    perpendicularWidthPx: perp,
    diameterLine: [a, b],
    widthLine: [minPt, maxPt],
    circularity,
    depthWidthRatio,
    areaMm2: scale != null ? areaPx * scale * scale : null,
    longestDiameterMm: scale != null ? longest * scale : null,
    perpendicularWidthMm: scale != null ? perp * scale : null,
  }
}
