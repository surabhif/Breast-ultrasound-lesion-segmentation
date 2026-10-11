/** Helpers for demo gallery sample identity / ground-truth display. */

export type DemoSampleMeta = {
  id: string
  label: string
  dataset?: string
  mask_src?: string
  mm_per_mask_px_160?: number | null
  pixel_size_mm?: number | null
  orig_width?: number | null
  orig_height?: number | null
}

/**
 * Reader-facing BUSI class label.
 * normal = no lump at all; harmless = a benign lump is present.
 */
export function classLabelDisplay(label: string): string {
  switch (label) {
    case 'benign':
      return 'harmless (benign)'
    case 'malignant':
      return 'cancerous (malignant)'
    case 'normal':
      return 'normal (no lump)'
    default:
      return label
  }
}

/** Plain-language source line for the ground-truth card. */
export function sampleSourceLabel(meta: DemoSampleMeta | null | undefined): string {
  if (!meta) return 'Available for gallery samples only.'
  if (meta.dataset === 'breast') return 'BrEaST CC BY'
  if (meta.dataset === 'busbra') return 'BUS-BRA CC BY'
  return 'BUSI test sample'
}

/** Whether the sample has an expert mask to compare against. */
export function sampleHasExpert(meta: DemoSampleMeta | null | undefined): boolean {
  return Boolean(meta?.mask_src)
}

/**
 * Physical spacing (mm per 160² mask pixel) for measurements.
 * BrEaST ships mm_per_mask_px_160; BUSI has none; uploads have none.
 */
export function sampleSpacingMm(
  meta: DemoSampleMeta | null | undefined,
  maskW: number,
): number | null {
  if (!meta) return null
  if (meta.mm_per_mask_px_160 != null && Number.isFinite(meta.mm_per_mask_px_160)) {
    return meta.mm_per_mask_px_160
  }
  if (
    meta.pixel_size_mm != null &&
    meta.orig_width &&
    meta.orig_height &&
    maskW > 0
  ) {
    return (meta.pixel_size_mm * (meta.orig_width + meta.orig_height)) / 2 / maskW
  }
  return null
}
