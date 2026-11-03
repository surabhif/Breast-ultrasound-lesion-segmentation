import { SEG_THRESHOLD } from './constants'

/** Mask cutoff range used by the demo outline slider (unchanged from prior UX). */
export const OUTLINE_THR_MIN = 0.1
export const OUTLINE_THR_MAX = 0.9
export const OUTLINE_THR_STEP = 0.05

/**
 * Map stored mask threshold → slider position.
 * Left = Tight (higher cutoff), right = Loose (lower cutoff). Default stays SEG_THRESHOLD.
 */
export function thrToLoosePosition(segThr: number): number {
  return OUTLINE_THR_MAX + OUTLINE_THR_MIN - segThr
}

export function loosePositionToThr(position: number): number {
  return OUTLINE_THR_MAX + OUTLINE_THR_MIN - position
}

export function outlineSliderLabel(segThr: number): string {
  if (Math.abs(segThr - SEG_THRESHOLD) < 1e-6) return 'Default'
  if (segThr > SEG_THRESHOLD) return 'Tighter'
  return 'Looser'
}
