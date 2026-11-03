/**
 * Ordered BUSI gallery strip: 2 normal, 2 benign, 2 malignant.
 * Uses the public sample images already shipped in the repo.
 */

import samplesManifest from '../data/samples.json'

export type ExampleSample = (typeof samplesManifest.samples)[number]

const ORDER: Array<{ label: 'normal' | 'benign' | 'malignant'; take: number }> = [
  { label: 'normal', take: 2 },
  { label: 'benign', take: 2 },
  { label: 'malignant', take: 2 },
]

/** Six BUSI examples in a fixed visitor-facing order. */
export function getExampleStripSamples(
  samples: ExampleSample[] = samplesManifest.samples as ExampleSample[],
): ExampleSample[] {
  const out: ExampleSample[] = []
  for (const { label, take } of ORDER) {
    const matched = samples.filter((s) => s.label === label).slice(0, take)
    out.push(...matched)
  }
  return out
}

export const EXAMPLE_STRIP_DISCLAIMER = samplesManifest.disclaimer
