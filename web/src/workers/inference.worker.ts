/// <reference lib="webworker" />
import * as ort from 'onnxruntime-web'

export type WorkerRequest =
  | { type: 'configure'; wasmPaths: string }
  | { type: 'load'; buffer: ArrayBuffer }
  | { type: 'infer'; id: number; tensor: Float32Array; size: number }
  | { type: 'cancel' }

export type WorkerResponse =
  | { type: 'ready' }
  | { type: 'loaded' }
  | { type: 'result'; id: number; mask: Float32Array; maskH: number; maskW: number; clsProb: number }
  | { type: 'error'; id?: number; message: string }

let session: ort.InferenceSession | null = null
let cancelled = false

function configure(wasmPaths: string) {
  ort.env.wasm.wasmPaths = wasmPaths
  ort.env.wasm.numThreads = 1
  // Move ORT compute off the worker's sync path when supported.
  try {
    ;(ort.env.wasm as { proxy?: boolean }).proxy = true
  } catch {
    // optional
  }
}

self.onmessage = async (ev: MessageEvent<WorkerRequest>) => {
  const msg = ev.data
  try {
    if (msg.type === 'configure') {
      configure(msg.wasmPaths)
      ;(self as unknown as Worker).postMessage({ type: 'ready' } satisfies WorkerResponse)
      return
    }
    if (msg.type === 'cancel') {
      cancelled = true
      return
    }
    if (msg.type === 'load') {
      cancelled = false
      session = await ort.InferenceSession.create(msg.buffer, {
        executionProviders: ['wasm'],
        graphOptimizationLevel: 'all',
      })
      ;(self as unknown as Worker).postMessage({ type: 'loaded' } satisfies WorkerResponse)
      return
    }
    if (msg.type === 'infer') {
      cancelled = false
      if (!session) throw new Error('Worker session not loaded')
      const input = new ort.Tensor('float32', msg.tensor, [1, 3, msg.size, msg.size])
      const out = await session.run({ input })
      if (cancelled) return
      const names = session.outputNames
      const segTensor = out.seg_mask ?? (names[0] ? out[names[0]] : undefined)
      const clsTensor = out.cls_prob ?? (names[1] ? out[names[1]] : undefined)
      if (!segTensor || !clsTensor) throw new Error(`bad outputs: ${names.join(',')}`)
      const rawMask = segTensor.data as Float32Array
      const mask = new Float32Array(rawMask) // copy for transfer
      const [, , maskH, maskW] = segTensor.dims as [number, number, number, number]
      const clsProb = (clsTensor.data as Float32Array)[0] ?? 0
      const resp: WorkerResponse = { type: 'result', id: msg.id, mask, maskH, maskW, clsProb }
      ;(self as unknown as Worker).postMessage(resp, [mask.buffer])
    }
  } catch (err) {
    const resp: WorkerResponse = {
      type: 'error',
      id: msg.type === 'infer' ? msg.id : undefined,
      message: err instanceof Error ? err.message : String(err),
    }
    ;(self as unknown as Worker).postMessage(resp)
  }
}

export {}
