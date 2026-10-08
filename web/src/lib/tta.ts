/** Test-time augmentation for uncertainty (agreement under small changes). */

export type TtaResult = {
  meanMask: Float32Array
  stdMask: Float32Array
  entropyMask: Float32Array
  /** Mean pairwise Dice among binarized TTA masks (higher = more agreement). */
  agreement: number
  clsMean: number
  clsStd: number
  n: number
}

function diceBinary(a: Uint8Array, b: Uint8Array): number {
  let inter = 0
  let sa = 0
  let sb = 0
  for (let i = 0; i < a.length; i++) {
    const x = a[i]!
    const y = b[i]!
    sa += x
    sb += y
    inter += x & y
  }
  if (sa + sb === 0) return 1
  return (2 * inter) / (sa + sb)
}

function entropy(p: number): number {
  const q = Math.min(1 - 1e-6, Math.max(1e-6, p))
  return -(q * Math.log2(q) + (1 - q) * Math.log2(1 - q))
}

/** Aggregate N soft masks + class probs into uncertainty maps. */
export function aggregateTta(
  masks: Float32Array[],
  clsProbs: number[],
  thr = 0.4,
): TtaResult {
  const n = masks.length
  if (n === 0) throw new Error('aggregateTta: empty')
  const len = masks[0]!.length
  const meanMask = new Float32Array(len)
  const stdMask = new Float32Array(len)
  const entropyMask = new Float32Array(len)
  for (let i = 0; i < len; i++) {
    let s = 0
    for (let k = 0; k < n; k++) s += masks[k]![i]!
    const m = s / n
    meanMask[i] = m
    let v = 0
    for (let k = 0; k < n; k++) {
      const d = masks[k]![i]! - m
      v += d * d
    }
    stdMask[i] = Math.sqrt(v / n)
    entropyMask[i] = entropy(m)
  }

  const bins = masks.map((m) => {
    const b = new Uint8Array(len)
    for (let i = 0; i < len; i++) b[i] = m[i]! > thr ? 1 : 0
    return b
  })
  let pair = 0
  let count = 0
  for (let i = 0; i < n; i++) {
    for (let j = i + 1; j < n; j++) {
      pair += diceBinary(bins[i]!, bins[j]!)
      count++
    }
  }
  const agreement = count ? pair / count : 1
  const clsMean = clsProbs.reduce((a, b) => a + b, 0) / n
  let cvs = 0
  for (const p of clsProbs) cvs += (p - clsMean) ** 2
  return {
    meanMask,
    stdMask,
    entropyMask,
    agreement,
    clsMean,
    clsStd: Math.sqrt(cvs / n),
    n,
  }
}

export function agreementLabel(agreement: number): 'high' | 'medium' | 'low' {
  if (agreement >= 0.85) return 'high'
  if (agreement >= 0.65) return 'medium'
  return 'low'
}

/** Deterministic TTA specs (identity + flips + mild brightness). Geometry inverted by caller. */
export const TTA_SPECS = [
  { id: 'id', hflip: false, vflip: false, brightness: 1 },
  { id: 'h', hflip: true, vflip: false, brightness: 1 },
  { id: 'v', hflip: false, vflip: true, brightness: 1 },
  { id: 'hv', hflip: true, vflip: true, brightness: 1 },
  { id: 'b085', hflip: false, vflip: false, brightness: 0.85 },
  { id: 'b115', hflip: false, vflip: false, brightness: 1.15 },
  { id: 'hb09', hflip: true, vflip: false, brightness: 0.9 },
  { id: 'vb11', hflip: false, vflip: true, brightness: 1.1 },
] as const

export type TtaSpec = (typeof TTA_SPECS)[number]
