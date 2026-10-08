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

/**
 * Half-pixel-center bilinear resize of RGBA → RGB float planes.
 * Must match `scripts/busi_data.py:resize_rgb_bilinear` exactly.
 */
export function resizeRgbBilinear(
  rgba: Uint8ClampedArray,
  srcW: number,
  srcH: number,
  outSize: number,
): Float32Array {
  const out = new Float32Array(3 * outSize * outSize)
  const plane = outSize * outSize
  for (let y = 0; y < outSize; y++) {
    let sy = ((y + 0.5) * srcH) / outSize - 0.5
    if (sy < 0) sy = 0
    if (sy > srcH - 1) sy = srcH - 1
    const y0 = Math.floor(sy)
    const y1 = Math.min(y0 + 1, srcH - 1)
    const fy = sy - y0
    for (let x = 0; x < outSize; x++) {
      let sx = ((x + 0.5) * srcW) / outSize - 0.5
      if (sx < 0) sx = 0
      if (sx > srcW - 1) sx = srcW - 1
      const x0 = Math.floor(sx)
      const x1 = Math.min(x0 + 1, srcW - 1)
      const fx = sx - x0
      const i00 = (y0 * srcW + x0) * 4
      const i01 = (y0 * srcW + x1) * 4
      const i10 = (y1 * srcW + x0) * 4
      const i11 = (y1 * srcW + x1) * 4
      const w00 = (1 - fx) * (1 - fy)
      const w01 = fx * (1 - fy)
      const w10 = (1 - fx) * fy
      const w11 = fx * fy
      const o = y * outSize + x
      for (let c = 0; c < 3; c++) {
        const v =
          rgba[i00 + c]! * w00 + rgba[i01 + c]! * w01 + rgba[i10 + c]! * w10 + rgba[i11 + c]! * w11
        out[c * plane + o] = v
      }
    }
  }
  return out
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
  // Read source pixels at native resolution (no browser resize), then apply the
  // same bilinear as Python so ORT-web matches onnxruntime CPU.
  const canvas = document.createElement('canvas')
  canvas.width = sw
  canvas.height = sh
  const ctx = canvas.getContext('2d', { willReadFrequently: true })
  if (!ctx) throw new Error('Canvas 2D unavailable')
  ctx.drawImage(img, sx, sy, sw, sh, 0, 0, sw, sh)
  const { data } = ctx.getImageData(0, 0, sw, sh)
  const rgb = resizeRgbBilinear(data, sw, sh, outSize)
  const out = new Float32Array(3 * outSize * outSize)
  const plane = outSize * outSize
  for (let i = 0; i < plane; i++) {
    out[i] = (rgb[i]! / 255 - IMAGENET_MEAN[0]) / IMAGENET_STD[0]
    out[plane + i] = (rgb[plane + i]! / 255 - IMAGENET_MEAN[1]) / IMAGENET_STD[1]
    out[2 * plane + i] = (rgb[2 * plane + i]! / 255 - IMAGENET_MEAN[2]) / IMAGENET_STD[2]
  }
  return out
}

/**
 * Soft lesion mask → translucent orange overlay + outline.
 * Callers should pass a mask that already had val-tuned post-processing
 * (`postprocessMask`: threshold 0.4 + min-component area 40) so the overlay
 * matches the evaluated Python pipeline.
 */
export function maskToOverlay(
  mask: Float32Array,
  maskH: number,
  maskW: number,
  outW: number,
  outH: number,
  opacity: number,
  threshold = 0.4,
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
