/**
 * Short, accurate one-liners shown while the ONNX model downloads the first time.
 * Stick to project facts — no medical claims beyond “research demo”.
 */

export const LOADING_TIPS: readonly string[] = [
  'BUSI is a public set of breast ultrasound photos used in research papers.',
  'This site is a research demo. It is not for diagnosis or care decisions.',
  'The model runs in your browser. Your image stays on this device.',
  'Outlines show where the model thinks a lump might be — not a doctor’s reading.',
  'Harmless vs cancerous here is only a research score, not a BI-RADS category.',
  'Near-identical photos are kept together so training and testing do not share the same frame.',
  'The served model is version 1.0.0 (about 12 MB on first visit).',
  'Later visits can reuse the cached model file when the browser allows it.',
]

/** Pick tip index from an elapsed tick so tips rotate without randomness flicker. */
export function tipAt(tick: number, tips: readonly string[] = LOADING_TIPS): string {
  if (tips.length === 0) return ''
  const i = ((tick % tips.length) + tips.length) % tips.length
  return tips[i]!
}
