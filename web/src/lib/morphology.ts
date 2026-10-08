/** Connected-component helpers matching Python `remove_small_components`. */

/**
 * Remove connected components (4-connected) smaller than `minArea` from a
 * binary mask. Matches `scripts/busi_data.py:remove_small_components`, which
 * uses scipy.ndimage.label (default structure = 4-connectivity).
 */
export function removeSmallComponents(
  binary: Uint8Array | boolean[],
  height: number,
  width: number,
  minArea: number,
): Uint8Array {
  const n = height * width
  const out = new Uint8Array(n)
  if (minArea <= 0) {
    for (let i = 0; i < n; i++) out[i] = binary[i] ? 1 : 0
    return out
  }

  const visited = new Uint8Array(n)
  const qx = new Int32Array(n)
  const qy = new Int32Array(n)

  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const start = y * width + x
      if (!binary[start] || visited[start]) continue

      let qh = 0
      let qt = 0
      qx[qt] = x
      qy[qt] = y
      qt++
      visited[start] = 1

      const cells: number[] = []
      while (qh < qt) {
        const cx = qx[qh]!
        const cy = qy[qh]!
        qh++
        const ci = cy * width + cx
        cells.push(ci)
        const neighbors = [
          [cx - 1, cy],
          [cx + 1, cy],
          [cx, cy - 1],
          [cx, cy + 1],
        ] as const
        for (const [nx, ny] of neighbors) {
          if (nx < 0 || ny < 0 || nx >= width || ny >= height) continue
          const ni = ny * width + nx
          if (!binary[ni] || visited[ni]) continue
          visited[ni] = 1
          qx[qt] = nx
          qy[qt] = ny
          qt++
        }
      }

      if (cells.length >= minArea) {
        for (const i of cells) out[i] = 1
      }
    }
  }
  return out
}

/**
 * Threshold a soft mask and drop small components.
 * Returns a Float32Array of 0/1 suitable for overlay (same length as input).
 */
export function postprocessMask(
  soft: Float32Array,
  height: number,
  width: number,
  threshold = 0.4,
  minArea = 40,
): Float32Array {
  const binary = new Uint8Array(soft.length)
  for (let i = 0; i < soft.length; i++) binary[i] = soft[i]! > threshold ? 1 : 0
  const kept = removeSmallComponents(binary, height, width, minArea)
  const out = new Float32Array(soft.length)
  for (let i = 0; i < soft.length; i++) {
    // Keep soft values where the component survived; zero otherwise.
    out[i] = kept[i] ? soft[i]! : 0
  }
  return out
}
