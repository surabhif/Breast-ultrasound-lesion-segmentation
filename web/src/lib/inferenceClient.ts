import {
  IMG_SIZE,
  MIN_COMPONENT_AREA,
  MODEL_CACHE,
  MODEL_URL,
  SEG_THRESHOLD,
  ensureModelManifest,
} from './constants'
import { imageToTensor, loadImage, maskToOverlay } from './image'
import { postprocessMask } from './morphology'
import { TTA_SPECS, aggregateTta, type TtaResult } from './tta'
import type { WorkerRequest, WorkerResponse } from '../workers/inference.worker'

export type InferenceResult = {
  clsProb: number
  maskMean: number
  overlay: ImageData
  mask: Float32Array
  softMask: Float32Array
  maskH: number
  maskW: number
  displayWidth: number
  displayHeight: number
}

export type LoadProgress = {
  status: 'idle' | 'checking-cache' | 'downloading' | 'creating-session' | 'ready' | 'error'
  loadedBytes: number
  totalBytes: number | null
  message: string
}

type ProgressCb = (p: LoadProgress) => void

let worker: Worker | null = null
let workerReady: Promise<void> | null = null
let nextId = 1
const pending = new Map<
  number,
  { resolve: (v: { mask: Float32Array; maskH: number; maskW: number; clsProb: number }) => void; reject: (e: Error) => void }
>()
let cachedBuffer: ArrayBuffer | null = null
let inferredSize = IMG_SIZE

function wasmPaths(): string {
  const base = import.meta.env.BASE_URL || '/'
  return `${base}ort/`
}

function ensureWorker(): Promise<void> {
  if (workerReady) return workerReady
  workerReady = new Promise((resolve, reject) => {
    worker = new Worker(new URL('../workers/inference.worker.ts', import.meta.url), {
      type: 'module',
    })
    worker.onmessage = (ev: MessageEvent<WorkerResponse>) => {
      const msg = ev.data
      if (msg.type === 'ready') {
        resolve()
        return
      }
      if (msg.type === 'loaded') return
      if (msg.type === 'result') {
        const p = pending.get(msg.id)
        if (p) {
          pending.delete(msg.id)
          p.resolve({ mask: msg.mask, maskH: msg.maskH, maskW: msg.maskW, clsProb: msg.clsProb })
        }
        return
      }
      if (msg.type === 'error') {
        if (msg.id != null && pending.has(msg.id)) {
          pending.get(msg.id)!.reject(new Error(msg.message))
          pending.delete(msg.id)
        } else {
          reject(new Error(msg.message))
        }
      }
    }
    worker.onerror = (e) => reject(e.error ?? new Error('Worker failed'))
    const cfg: WorkerRequest = { type: 'configure', wasmPaths: wasmPaths() }
    worker.postMessage(cfg)
  })
  return workerReady
}

async function fetchModelBuffer(onProgress?: ProgressCb): Promise<ArrayBuffer> {
  if (cachedBuffer) return cachedBuffer
  const manifest = await ensureModelManifest()
  inferredSize = manifest.img_size && manifest.img_size > 0 ? manifest.img_size : IMG_SIZE
  const modelUrl = MODEL_URL()
  const cacheName = MODEL_CACHE()

  onProgress?.({
    status: 'checking-cache',
    loadedBytes: 0,
    totalBytes: null,
    message: `Checking browser cache (v${manifest.version})…`,
  })

  try {
    const keys = await caches.keys()
    await Promise.all(
      keys.filter((k) => k.startsWith('busi-unet-') && k !== cacheName).map((k) => caches.delete(k)),
    )
  } catch {
    // ignore
  }

  try {
    const cache = await caches.open(cacheName)
    const hit = await cache.match(modelUrl)
    if (hit) {
      const buf = await hit.arrayBuffer()
      cachedBuffer = buf
      onProgress?.({
        status: 'creating-session',
        loadedBytes: buf.byteLength,
        totalBytes: buf.byteLength,
        message: `Loaded model v${manifest.version} from cache…`,
      })
      return buf
    }
  } catch {
    // ignore
  }

  onProgress?.({
    status: 'downloading',
    loadedBytes: 0,
    totalBytes: null,
    message: `Downloading model v${manifest.version}…`,
  })
  const res = await fetch(modelUrl)
  if (!res.ok) throw new Error(`Model download failed (${res.status})`)
  const buf = await res.arrayBuffer()
  cachedBuffer = buf
  try {
    const cache = await caches.open(cacheName)
    await cache.put(modelUrl, new Response(buf.slice(0), { headers: { 'Content-Type': 'application/octet-stream' } }))
  } catch {
    // ignore
  }
  return buf
}

export async function preloadModel(onProgress?: ProgressCb): Promise<void> {
  await ensureWorker()
  const buffer = await fetchModelBuffer(onProgress)
  onProgress?.({
    status: 'creating-session',
    loadedBytes: buffer.byteLength,
    totalBytes: buffer.byteLength,
    message: 'Starting model engine…',
  })
  const loadMsg: WorkerRequest = { type: 'load', buffer: buffer.slice(0) }
  await new Promise<void>((resolve, reject) => {
    const w = worker!
    const prev = w.onmessage
    w.onmessage = (ev: MessageEvent<WorkerResponse>) => {
      const msg = ev.data
      if (msg.type === 'loaded') {
        w.onmessage = prev
        resolve()
        return
      }
      if (msg.type === 'error' && msg.id == null) {
        w.onmessage = prev
        reject(new Error(msg.message))
        return
      }
      prev?.call(w, ev)
    }
    w.postMessage(loadMsg, [loadMsg.buffer])
  })
  // Keep size from model.json (set in fetchModelBuffer); fall back to constant.
  if (!inferredSize) inferredSize = IMG_SIZE
  onProgress?.({
    status: 'ready',
    loadedBytes: buffer.byteLength,
    totalBytes: buffer.byteLength,
    message: 'Model ready',
  })
}

function invertFlip(mask: Float32Array, h: number, w: number, hflip: boolean, vflip: boolean): Float32Array {
  if (!hflip && !vflip) return mask
  const out = new Float32Array(mask.length)
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const sx = hflip ? w - 1 - x : x
      const sy = vflip ? h - 1 - y : y
      out[y * w + x] = mask[sy * w + sx]!
    }
  }
  return out
}

async function workerInfer(tensor: Float32Array, size: number) {
  await ensureWorker()
  if (!worker) throw new Error('no worker')
  const id = nextId++
  return new Promise<{ mask: Float32Array; maskH: number; maskW: number; clsProb: number }>((resolve, reject) => {
    pending.set(id, { resolve, reject })
    const msg: WorkerRequest = { type: 'infer', id, tensor, size }
    worker!.postMessage(msg, [tensor.buffer])
  })
}

export function cancelInference(): void {
  worker?.postMessage({ type: 'cancel' } satisfies WorkerRequest)
}

export async function runInference(
  source: string | File,
  onProgress?: ProgressCb,
  opts?: { segThreshold?: number },
): Promise<InferenceResult> {
  await preloadModel(onProgress)
  const img = await loadImage(source)
  const width = img.naturalWidth
  const height = img.naturalHeight
  const size = inferredSize || IMG_SIZE
  const tensorData = imageToTensor(img, 0, 0, width, height, size)
  const soft = await workerInfer(new Float32Array(tensorData), size)
  const thr = opts?.segThreshold ?? SEG_THRESHOLD
  const mask = postprocessMask(soft.mask, soft.maskH, soft.maskW, thr, MIN_COMPONENT_AREA)
  let maskSum = 0
  for (let i = 0; i < mask.length; i++) maskSum += mask[i]!
  const displayWidth = Math.min(640, width)
  const displayHeight = Math.round((height / width) * displayWidth)
  const overlay = maskToOverlay(mask, soft.maskH, soft.maskW, displayWidth, displayHeight, 1, thr)
  return {
    clsProb: soft.clsProb,
    maskMean: maskSum / mask.length,
    overlay,
    mask,
    softMask: soft.mask,
    maskH: soft.maskH,
    maskW: soft.maskW,
    displayWidth,
    displayHeight,
  }
}

/** Run 8× TTA in the worker; returns soft-mean uncertainty maps. */
export async function runInferenceTta(
  source: string | File,
  onProgress?: ProgressCb,
  onStep?: (i: number, n: number) => void,
): Promise<InferenceResult & { tta: TtaResult }> {
  await preloadModel(onProgress)
  const img = await loadImage(source)
  const width = img.naturalWidth
  const height = img.naturalHeight
  const size = inferredSize || IMG_SIZE
  const masks: Float32Array[] = []
  const probs: number[] = []
  for (let i = 0; i < TTA_SPECS.length; i++) {
    const spec = TTA_SPECS[i]!
    onStep?.(i + 1, TTA_SPECS.length)
    // Brightness via canvas draw
    const canvas = document.createElement('canvas')
    canvas.width = width
    canvas.height = height
    const ctx = canvas.getContext('2d')!
    ctx.filter = `brightness(${spec.brightness})`
    if (spec.hflip || spec.vflip) {
      ctx.translate(spec.hflip ? width : 0, spec.vflip ? height : 0)
      ctx.scale(spec.hflip ? -1 : 1, spec.vflip ? -1 : 1)
    }
    ctx.drawImage(img, 0, 0)
    const flipped = document.createElement('img')
    await new Promise<void>((res, rej) => {
      flipped.onload = () => res()
      flipped.onerror = () => rej(new Error('TTA canvas encode failed'))
      flipped.src = canvas.toDataURL('image/png')
    })
    const tensorData = imageToTensor(flipped, 0, 0, width, height, size)
    const soft = await workerInfer(new Float32Array(tensorData), size)
    const restored = invertFlip(soft.mask, soft.maskH, soft.maskW, spec.hflip, spec.vflip)
    masks.push(restored)
    probs.push(soft.clsProb)
  }
  const tta = aggregateTta(masks, probs, SEG_THRESHOLD)
  const mask = postprocessMask(tta.meanMask, size, size, SEG_THRESHOLD, MIN_COMPONENT_AREA)
  let maskSum = 0
  for (let i = 0; i < mask.length; i++) maskSum += mask[i]!
  const displayWidth = Math.min(640, width)
  const displayHeight = Math.round((height / width) * displayWidth)
  const overlay = maskToOverlay(mask, size, size, displayWidth, displayHeight, 1, SEG_THRESHOLD)
  return {
    clsProb: tta.clsMean,
    maskMean: maskSum / mask.length,
    overlay,
    mask,
    softMask: tta.meanMask,
    maskH: size,
    maskW: size,
    displayWidth,
    displayHeight,
    tta,
  }
}

/** Re-threshold an existing soft mask without re-running the model. */
export function rethreshold(
  softMask: Float32Array,
  maskH: number,
  maskW: number,
  displayWidth: number,
  displayHeight: number,
  thr: number,
): { mask: Float32Array; overlay: ImageData; maskMean: number } {
  const mask = postprocessMask(softMask, maskH, maskW, thr, MIN_COMPONENT_AREA)
  let maskSum = 0
  for (let i = 0; i < mask.length; i++) maskSum += mask[i]!
  return {
    mask,
    overlay: maskToOverlay(mask, maskH, maskW, displayWidth, displayHeight, 1, thr),
    maskMean: maskSum / mask.length,
  }
}
