/** Educational step copy — plain language, not medical advice. */

export type ExplainerStepId =
  | 'ultrasound'
  | 'labels'
  | 'segmentation'
  | 'pitfalls'
  | 'browser'

export type ExplainerStep = {
  id: ExplainerStepId
  title: string
  shortTitle: string
  kicker: string
  body: string
  /** Screen-reader / reduced-motion text alternative for the visual panel */
  alt: string
  callouts?: { label: string; detail: string }[]
}

export const EXPLAINER_STEPS: ExplainerStep[] = [
  {
    id: 'ultrasound',
    kicker: 'Step 1 · Imaging',
    shortTitle: 'Ultrasound',
    title: 'Why breast ultrasound matters',
    body: 'Breast ultrasound helps describe masses found on a mammogram or exam, especially in dense breasts. It shows soft tissue without X-ray radiation. This research demo studies how a program can outline a lump on a public ultrasound image. It is never a clinical tool.',
    alt: 'A stylized breast ultrasound frame with a dark lump region highlighted against grayscale tissue.',
    callouts: [
      { label: 'BUSI dataset', detail: 'Public breast ultrasound images with outlines (Al-Dhabyani et al. 2020)' },
      { label: 'Education only', detail: 'Not for diagnosis, triage, or screening' },
    ],
  },
  {
    id: 'labels',
    kicker: 'Step 2 · Categories',
    shortTitle: 'Labels',
    title: 'Harmless, cancerous, and normal',
    body: 'BUSI labels each image as harmless (benign), cancerous (malignant), or normal. Harmless and cancerous cases include an expert outline of the lump. Normal images have no lump. This project trains a network to predict an outline and a second score for telling harmless from cancerous lumps when a lump is present.',
    alt: 'Three labeled tiles: harmless, cancerous, and normal ultrasound categories used by the BUSI dataset.',
    callouts: [
      { label: 'Harmless / cancerous', detail: 'A lump is present; the mask outlines that region' },
      { label: 'Normal', detail: 'Trained with empty outlines so the model can learn “no lump”' },
    ],
  },
  {
    id: 'segmentation',
    kicker: 'Step 3 · Task',
    shortTitle: 'Segmentation',
    title: 'What outlining a lump means',
    body: 'Outlining means drawing the lump pixel by pixel. It is more than saying something is there. The demo overlays the predicted outline on the ultrasound. You can fade the overlay. A separate score estimates how cancerous a lump looks, for research comparison with the BUSI label.',
    alt: 'An ultrasound frame with an orange semi-transparent lump mask and a darker contour outline.',
    callouts: [
      { label: 'Mask overlay', detail: 'Predicted lump region with adjustable opacity' },
      { label: 'Second score', detail: 'Harmless vs cancerous probability when a lump is present' },
    ],
  },
  {
    id: 'pitfalls',
    kicker: 'Step 4 · Data pitfalls',
    shortTitle: 'Pitfalls',
    title: 'Calipers, near-copies, and missing patient IDs',
    body: 'BUSI has no patient IDs, so true patient-level splits are impossible. Many frames contain measurement marks or near-identical copies that can inflate scores if they appear in both training and testing. This project keeps near-identical photo groups together and audits caliper and text marks so reported metrics stay careful.',
    alt: 'Icons representing caliper marks on an ultrasound, near-identical frames, and grouped train/test splits.',
    callouts: [
      { label: 'Grouped splits', detail: 'Near-identical photo groups stay in one split only' },
      { label: 'Cleaning study', detail: 'Measures how flagged marks affect outline-overlap and ranking scores' },
    ],
  },
  {
    id: 'browser',
    kicker: 'Step 5 · This demo',
    shortTitle: 'Browser demo',
    title: 'From training run to your browser',
    body: 'A compact network is trained on CPU, then shrunk for a small download. The site runs that model entirely in your browser. Nothing is uploaded to a server. Start with a BUSI test sample, then read Results and the model card for numbers and limits.',
    alt: 'A progress bar downloading a small model file, then a BUSI sample with a mask overlay in the browser.',
    callouts: [
      { label: 'Runs on your device', detail: 'Weights download once; later visits use cache when available' },
      { label: 'Test samples', detail: 'Gallery images come from the careful test split' },
    ],
  },
]

export const EXPLAINER_SOURCES = [
  {
    label: 'BUSI dataset paper',
    href: 'https://doi.org/10.1016/j.dib.2019.104863',
  },
]
