/** Shared constants matching training / ONNX export contract. */

export const IMG_SIZE = 160

/** ImageNet mean/std used in training preprocessing. */
export const IMAGENET_MEAN = [0.485, 0.456, 0.406] as const
export const IMAGENET_STD = [0.229, 0.224, 0.225] as const

/** Val-tuned segmentation post-processing (see results/postprocess.json). */
export const SEG_THRESHOLD = 0.4
export const MIN_COMPONENT_AREA = 40
export const CLS_THRESHOLD = 0.5

/** Semantic model version for the currently shipped INT8 weights. */
export const MODEL_VERSION = '1.0.0'

export type ModelManifest = {
  version: string
  sha256: string
  filename: string
  size_bytes: number
  quantization: string
  /** Spatial input size for ONNX (default 160 for v1.0.0). */
  img_size?: number
  architecture?: string
  model_kind?: string
  postprocess: {
    seg_threshold: number
    min_component_area: number
    cls_threshold: number
  }
  metrics_note?: string
}

type CurrentPointer = {
  version: string
  path: string
  sha256: string
  cache_key: string
}

let manifestPromise: Promise<ModelManifest> | null = null
let currentPointer: CurrentPointer | null = null

/** Load `models/current.json` then the versioned `model.json` (once). */
export async function ensureModelManifest(): Promise<ModelManifest> {
  if (!manifestPromise) {
    manifestPromise = (async () => {
      const base = import.meta.env.BASE_URL
      const curRes = await fetch(`${base}models/current.json`, { cache: 'no-cache' })
      if (!curRes.ok) throw new Error(`Failed to load models/current.json (${curRes.status})`)
      const cur = (await curRes.json()) as CurrentPointer
      currentPointer = cur
      const manRes = await fetch(`${base}${cur.path.replace(/^\//, '')}/model.json`, {
        cache: 'no-cache',
      })
      if (!manRes.ok) throw new Error(`Failed to load model.json (${manRes.status})`)
      return (await manRes.json()) as ModelManifest
    })()
  }
  return manifestPromise
}

/** Versioned ONNX URL (uses current.json pointer after ensureModelManifest). */
export function MODEL_URL(): string {
  const base = import.meta.env.BASE_URL
  if (currentPointer) {
    return `${base}${currentPointer.path.replace(/^\//, '')}/busi_unet.onnx`
  }
  return `${base}models/v${MODEL_VERSION}/busi_unet.onnx`
}

/** Cache API bucket — version + sha8 so updates are never shadowed. */
export function MODEL_CACHE(): string {
  if (currentPointer?.cache_key) return currentPointer.cache_key
  return `busi-unet-v${MODEL_VERSION}`
}

/**
 * Visitor-facing model label. Paths / quantization notes live in the README
 * and on the Model card “Current served model” section.
 */
export const MODEL_STATUS = {
  kind: 'resnet18_unet' as const,
  label: 'ResNet-18 U-Net',
  sizeHintMb: 12,
  version: MODEL_VERSION,
}

export const SITE = {
  title: 'Breast Ultrasound Lesion Segmentation',
  shortTitle: 'BUSI Lesion Seg',
  tagline: 'In-browser research demo on the BUSI ultrasound dataset',
  githubUrl: 'https://github.com/surabhif/Breast-ultrasound-lesion-segmentation',
  pagesUrl: 'https://surabhif.github.io/Breast-ultrasound-lesion-segmentation/',
}
