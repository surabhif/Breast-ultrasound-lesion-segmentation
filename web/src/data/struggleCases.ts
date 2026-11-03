/**
 * Curated “Where the model struggles” gallery.
 * Each case_id must exist in results/mistakes.json (BUSI held-out).
 * Silhouettes, labels, and Dice come from that file — not invented here.
 */

export type StrugglePick = {
  case_id: string
  /** One plain sentence — what went wrong. */
  reason: string
}

/** Four to six real hard cases spanning miss / false outline / wrong call / partial. */
export const STRUGGLE_PICKS: StrugglePick[] = [
  {
    case_id: 'benign/benign (114).png',
    reason: 'The expert marked a lump here, but the model drew almost nothing.',
  },
  {
    case_id: 'normal/normal (126).png',
    reason: 'This scan has no lump, but the model still drew an outline.',
  },
  {
    case_id: 'benign/benign (37).png',
    reason: 'BUSI labels this lump harmless, but the model’s score leaned cancerous.',
  },
  {
    case_id: 'malignant/malignant (174).png',
    reason: 'BUSI labels this lump cancerous, but the model’s score leaned harmless.',
  },
  {
    case_id: 'benign/benign (383).png',
    reason: 'The model only outlined part of the lump the expert marked.',
  },
  {
    case_id: 'malignant/malignant (177).png',
    reason: 'The model outline spilled well past the expert outline.',
  },
]
