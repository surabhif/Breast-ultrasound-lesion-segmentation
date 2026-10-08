import * as ort from 'onnxruntime-web'
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

export type InferenceResult = {
  clsProb: number
  maskMean: number
  overlay: ImageData
  mask: Float32Array
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

let sessionPromise: Promise<ort.InferenceSession> | null = null
let cachedBuffer: ArrayBuffer | null = null
let inferredSize = IMG_SIZE

function configureOrt(): void {
  ort.env.wasm.wasmPaths = 'https://cdn.jsdelivr.net/npm/onnxruntime-web@1.30.0/dist/'
  ort.env.wasm.numThreads = 1
}

async function fetchModelBuffer(onProgress?: ProgressCb): Promise<ArrayBuffer> {
  if (cachedBuffer) return cachedBuffer

  const manifest = await ensureModelManifest()
  const modelUrl = MODEL_URL()
  const cacheName = MODEL_CACHE()

  onProgress?.({
    status: 'checking-cache',
    loadedBytes: 0,
    totalBytes: null,
    message: `Checking browser cache (v${manifest.version})…`,
  })

  try {
    // Drop stale cache buckets from older model versions.
    const keys = await caches.keys()
    await Promise.all(
      keys
        .filter((k) => k.startsWith('busi-unet-') && k !== cacheName)
        .map((k) => caches.delete(k)),
    )
  } catch {
    // Cache API may be unavailable
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
    // Cache API may be unavailable
  }

  onProgress?.({
    status: 'downloading',
    loadedBytes: 0,
    totalBytes: null,
    message: `Downloading model v${manifest.version}…`,
  })

  const res = await fetch(modelUrl)
  if (!res.ok) throw new Error(`Model download failed (${res.status})`)
  const total = Number(res.headers.get('Content-Length')) || null
  const reader = res.body?.getReader()
  if (!reader) {
    const buf = await res.arrayBuffer()
    cachedBuffer = buf
    return buf
  }

  const chunks: Uint8Array[] = []
  let loaded = 0
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    if (value) {
      chunks.push(value)
      loaded += value.byteLength
      onProgress?.({
        status: 'downloading',
        loadedBytes: loaded,
        totalBytes: total,
        message: total
          ? `Downloading model… ${(loaded / 1e6).toFixed(1)} / ${(total / 1e6).toFixed(1)} MB`
          : `Downloading model… ${(loaded / 1e6).toFixed(1)} MB`,
      })
    }
  }

  const merged = new Uint8Array(loaded)
  let offset = 0
  for (const c of chunks) {
    merged.set(c, offset)
    offset += c.byteLength
  }
  const buf = merged.buffer
  cachedBuffer = buf

  try {
    const cache = await caches.open(cacheName)
    await cache.put(
      modelUrl,
      new Response(buf.slice(0), {
        headers: { 'Content-Type': 'application/octet-stream' },
      }),
    )
  } catch {
    // ignore
  }

  return buf
}

export async function preloadModel(onProgress?: ProgressCb): Promise<ort.InferenceSession> {
  const alreadyLoading = Boolean(sessionPromise)
  if (!sessionPromise) {
    sessionPromise = (async () => {
      try {
        configureOrt()
        const buffer = await fetchModelBuffer(onProgress)
        onProgress?.({
          status: 'creating-session',
          loadedBytes: buffer.byteLength,
          totalBytes: buffer.byteLength,
          message: 'Initializing ONNX Runtime…',
        })
        const session = await ort.InferenceSession.create(buffer, {
          executionProviders: ['wasm'],
          graphOptimizationLevel: 'all',
        })
        // Default to training size; override if metadata exposes a numeric H/W.
        inferredSize = IMG_SIZE
        try {
          const anySession = session as unknown as {
            inputMetadata?: Record<string, { dimensions?: (number | string)[] }>
          }
          const meta = anySession.inputMetadata
          const first = meta ? Object.values(meta)[0] : undefined
          const dims = first?.dimensions
          if (dims && typeof dims[2] === 'number') inferredSize = dims[2]
        } catch {
          inferredSize = IMG_SIZE
        }
        onProgress?.({
          status: 'ready',
          loadedBytes: buffer.byteLength,
          totalBytes: buffer.byteLength,
          message: 'Model ready',
        })
        return session
      } catch (err) {
        sessionPromise = null
        onProgress?.({
          status: 'error',
          loadedBytes: 0,
          totalBytes: null,
          message: err instanceof Error ? err.message : 'Failed to load model',
        })
        throw err
      }
    })()
  }
  const session = await sessionPromise
  if (alreadyLoading && cachedBuffer) {
    onProgress?.({
      status: 'ready',
      loadedBytes: cachedBuffer.byteLength,
      totalBytes: cachedBuffer.byteLength,
      message: 'Model ready',
    })
  }
  return session
}

export async function getSession(onProgress?: ProgressCb): Promise<ort.InferenceSession> {
  return preloadModel(onProgress)
}

export async function runInference(
  source: string | File,
  onProgress?: ProgressCb,
): Promise<InferenceResult> {
  const session = await getSession(onProgress)
  const img = await loadImage(source)
  const width = img.naturalWidth
  const height = img.naturalHeight
  const size = inferredSize || IMG_SIZE

  const tensorData = imageToTensor(img, 0, 0, width, height, size)
  const input = new ort.Tensor('float32', tensorData, [1, 3, size, size])
  const out = await session.run({ input })
  const names = session.outputNames
  const segTensor = out.seg_mask ?? (names[0] ? out[names[0]] : undefined)
  const clsTensor = out.cls_prob ?? (names[1] ? out[names[1]] : undefined)
  if (!segTensor || !clsTensor) {
    throw new Error(`ONNX model must output seg_mask, cls_prob (got: ${names.join(', ')})`)
  }

  const rawMask = segTensor.data as Float32Array
  const [, , maskH, maskW] = segTensor.dims as [number, number, number, number]
  const clsProb = (clsTensor.data as Float32Array)[0] ?? 0

  // Match Python eval: threshold 0.4 + drop connected components < 40 px.
  const mask = postprocessMask(rawMask, maskH, maskW, SEG_THRESHOLD, MIN_COMPONENT_AREA)

  let maskSum = 0
  for (let i = 0; i < mask.length; i++) maskSum += mask[i]!
  const maskMean = maskSum / mask.length

  const displayWidth = Math.min(640, width)
  const displayHeight = Math.round((height / width) * displayWidth)
  const overlay = maskToOverlay(mask, maskH, maskW, displayWidth, displayHeight, 1, SEG_THRESHOLD)

  return {
    clsProb,
    maskMean,
    overlay,
    mask,
    maskH,
    maskW,
    displayWidth,
    displayHeight,
  }
}
