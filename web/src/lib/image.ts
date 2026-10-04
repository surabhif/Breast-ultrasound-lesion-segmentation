/** Image preprocessing and mask overlay helpers for in-browser inference. */

import { IMG_SIZE, IMAGENET_MEAN, IMAGENET_STD } from './constants'

export async function loadImage(source: string | File): Promise<HTMLImageElement> {
  const url = typeof source === 'string' ? source : URL.createObjectURL(source)
  try {
    const img = new Image()
    img.crossOrigin = 'anonymous'
    await new Promise<void>((resolve, reject) => {
      img.onload = () => resolve()
      img.onerror = () => reject(new Error('Failed to load image'))
      img.src = url
    })
    return img
  } finally {
    if (typeof source !== 'string') URL.revokeObjectURL(url)
  }
}

/** Convert an image (optionally a crop) to ImageNet-normalized CHW float32. */
export function imageToTensor(
  img: HTMLImageElement,
  sx = 0,
  sy = 0,
  sw = img.naturalWidth,
  sh = img.naturalHeight,
  outSize = IMG_SIZE,
): Float32Array {
  const canvas = document.createElement('canvas')
  canvas.width = outSize
  canvas.height = outSize
  const ctx = canvas.getContext('2d', { willReadFrequently: true })
  if (!ctx) throw new Error('Canvas 2D unavailable')
  ctx.drawImage(img, sx, sy, sw, sh, 0, 0, outSize, outSize)
  const { data } = ctx.getImageData(0, 0, outSize, outSize)
  const out = new Float32Array(3 * outSize * outSize)
  const plane = outSize * outSize
  for (let i = 0; i < plane; i++) {
    const r = data[i * 4]! / 255
    const g = data[i * 4 + 1]! / 255
    const b = data[i * 4 + 2]! / 255
    out[i] = (r - IMAGENET_MEAN[0]) / IMAGENET_STD[0]
    out[plane + i] = (g - IMAGENET_MEAN[1]) / IMAGENET_STD[1]
    out[2 * plane + i] = (b - IMAGENET_MEAN[2]) / IMAGENET_STD[2]
  }
  return out
}

/** Soft lesion mask → translucent orange overlay + outline. */
export function maskToOverlay(
  mask: Float32Array,
  maskH: number,
  maskW: number,
  outW: number,
  outH: number,
  opacity: number,
  threshold = 0.45,
): ImageData {
  const canvas = document.createElement('canvas')
  canvas.width = maskW
  canvas.height = maskH
  const ctx = canvas.getContext('2d')!
  const img = ctx.createImageData(maskW, maskH)
  for (let i = 0; i < mask.length; i++) {
    const v = mask[i]!
    const a = v > threshold ? Math.min(255, Math.round(opacity * 200 * Math.min(1, (v - threshold) / 0.4 + 0.35))) : 0
    img.data[i * 4] = 196
    img.data[i * 4 + 1] = 92
    img.data[i * 4 + 2] = 38
    img.data[i * 4 + 3] = a
  }
  ctx.putImageData(img, 0, 0)

  // Upscale soft mask
  const out = document.createElement('canvas')
  out.width = outW
  out.height = outH
  const octx = out.getContext('2d')!
  octx.imageSmoothingEnabled = true
  octx.drawImage(canvas, 0, 0, outW, outH)

  // Outline from thresholded mask
  const scaled = document.createElement('canvas')
  scaled.width = outW
  scaled.height = outH
  const sctx = scaled.getContext('2d')!
  sctx.imageSmoothingEnabled = false
  // reuse low-res binary
  const bin = ctx.createImageData(maskW, maskH)
  for (let i = 0; i < mask.length; i++) {
    const on = mask[i]! > threshold ? 255 : 0
    bin.data[i * 4] = on
    bin.data[i * 4 + 1] = on
    bin.data[i * 4 + 2] = on
    bin.data[i * 4 + 3] = 255
  }
  ctx.putImageData(bin, 0, 0)
  sctx.drawImage(canvas, 0, 0, outW, outH)
  const binBig = sctx.getImageData(0, 0, outW, outH)
  const overlay = octx.getImageData(0, 0, outW, outH)

  for (let y = 1; y < outH - 1; y++) {
    for (let x = 1; x < outW - 1; x++) {
      const i = y * outW + x
      const c = binBig.data[i * 4]! > 127
      if (!c) continue
      const edge =
        binBig.data[((y - 1) * outW + x) * 4]! < 127 ||
        binBig.data[((y + 1) * outW + x) * 4]! < 127 ||
        binBig.data[(y * outW + x - 1) * 4]! < 127 ||
        binBig.data[(y * outW + x + 1) * 4]! < 127
      if (edge) {
        overlay.data[i * 4] = 180
        overlay.data[i * 4 + 1] = 40
        overlay.data[i * 4 + 2] = 50
        overlay.data[i * 4 + 3] = Math.min(255, Math.round(230 * Math.max(opacity, 0.55)))
      }
    }
  }
  return overlay
}
