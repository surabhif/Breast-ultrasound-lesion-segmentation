/** Dice / IoU helpers matching Python `busi_data.dice_score` / `iou_score`. */

export function diceScore(pred: Uint8Array | Float32Array | boolean[], gt: Uint8Array | Float32Array | boolean[], threshold = 0.5): number {
  let predSum = 0
  let gtSum = 0
  let inter = 0
  const n = Math.min(pred.length, gt.length)
  for (let i = 0; i < n; i++) {
    const p = Number(pred[i]!) > threshold
    const g = Number(gt[i]!) > threshold
    if (p) predSum++
    if (g) gtSum++
    if (p && g) inter++
  }
  if (predSum === 0 && gtSum === 0) return 1
  const eps = 1e-6
  return (2 * inter + eps) / (predSum + gtSum + eps)
}

export function iouScore(pred: Uint8Array | Float32Array | boolean[], gt: Uint8Array | Float32Array | boolean[], threshold = 0.5): number {
  let inter = 0
  let uni = 0
  const n = Math.min(pred.length, gt.length)
  for (let i = 0; i < n; i++) {
    const p = Number(pred[i]!) > threshold
    const g = Number(gt[i]!) > threshold
    if (p && g) inter++
    if (p || g) uni++
  }
  if (uni === 0) return 1
  const eps = 1e-6
  return (inter + eps) / (uni + eps)
}

/** Nearest-neighbour downsample of a full-res grayscale mask ImageData/canvas to outSize² binary. */
export function downsampleMaskNearest(
  source: HTMLImageElement | HTMLCanvasElement,
  outSize: number,
): Float32Array {
  const canvas = document.createElement('canvas')
  canvas.width = outSize
  canvas.height = outSize
  const ctx = canvas.getContext('2d', { willReadFrequently: true })!
  ctx.imageSmoothingEnabled = false
  ctx.drawImage(source, 0, 0, outSize, outSize)
  const { data } = ctx.getImageData(0, 0, outSize, outSize)
  const out = new Float32Array(outSize * outSize)
  for (let i = 0; i < out.length; i++) {
    out[i] = data[i * 4]! > 127 ? 1 : 0
  }
  return out
}
