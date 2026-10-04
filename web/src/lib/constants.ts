/** Shared constants matching training / ONNX export contract. */

export const IMG_SIZE = 128

/** ImageNet mean/std used in training preprocessing. */
export const IMAGENET_MEAN = [0.485, 0.456, 0.406] as const
export const IMAGENET_STD = [0.229, 0.224, 0.225] as const

/** Bundled model path (under Vite public/). */
export const MODEL_URL = `${import.meta.env.BASE_URL}models/busi_unet.onnx`

/** Cache name for the ONNX weights in the browser Cache API. */
export const MODEL_CACHE = 'busi-unet-v1'

/**
 * Visitor-facing model label. Paths / quantization notes live in the README
 * and on the Model card “Current served model” section.
 */
export const MODEL_STATUS = {
  kind: 'resnet18_unet' as const,
  label: 'ResNet-18 U-Net',
  sizeHintMb: 16,
}

export const SITE = {
  title: 'Breast Ultrasound Lesion Segmentation',
  shortTitle: 'BUSI Lesion Seg',
  tagline: 'In-browser research demo on the BUSI ultrasound dataset',
  githubUrl: 'https://github.com/surabhif/Breast-ultrasound-lesion-segmentation',
  pagesUrl: 'https://surabhif.github.io/Breast-ultrasound-lesion-segmentation/',
}
