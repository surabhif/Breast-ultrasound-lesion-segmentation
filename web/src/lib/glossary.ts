/** Short plain-language glossary for site hover/tap tips. */

export type GlossaryKey =
  | 'dice'
  | 'auc'
  | 'birads'
  | 'lesion'
  | 'margin'
  | 'ultrasound'
  | 'outline'
  | 'threshold'

export type GlossaryEntry = {
  label: string
  definition: string
}

export const GLOSSARY: Record<GlossaryKey, GlossaryEntry> = {
  dice: {
    label: 'Dice',
    definition:
      'Outline-overlap score from 0 to 1. Higher means the model outline and the expert outline cover more of the same pixels.',
  },
  auc: {
    label: 'AUC',
    definition:
      'A score from 0 to 1 for how well the model ranks cancerous lumps above harmless ones across many images. 0.5 is chance; closer to 1 is better ranking.',
  },
  birads: {
    label: 'BI-RADS',
    definition:
      'A common radiology reporting scale for breast imaging findings. This research demo does not output BI-RADS grades.',
  },
  lesion: {
    label: 'Lesion',
    definition:
      'Here it means a lump or mass seen on the ultrasound image. Normal (no lump) images have no lesion.',
  },
  margin: {
    label: 'Margin',
    definition:
      'The edge of a lump. Smooth or irregular edges can matter in clinical reading; this demo only draws a pixel outline.',
  },
  ultrasound: {
    label: 'Ultrasound',
    definition:
      'An imaging method that uses sound waves to make a picture of tissue. Breast ultrasound is common for looking at lumps.',
  },
  outline: {
    label: 'Outline',
    definition:
      'The pixel mask around a lump. The model predicts one; gallery samples also show an expert outline for comparison.',
  },
  threshold: {
    label: 'Threshold',
    definition:
      'A cut-off number. Pixels above the mask threshold become the drawn outline; the class threshold turns the score into a harmless vs cancerous label for display.',
  },
}

export const GLOSSARY_KEYS = Object.keys(GLOSSARY) as GlossaryKey[]
