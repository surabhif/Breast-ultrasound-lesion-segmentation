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
    body: 'Breast ultrasound helps characterize masses found on mammography or physical exam, especially in dense breasts. It shows soft tissue without ionizing radiation. This research demo studies how a model can outline a lesion on a public ultrasound image — never as a clinical tool.',
    alt: 'A stylized breast ultrasound frame with a dark lesion region highlighted against grayscale tissue.',
    callouts: [
      { label: 'BUSI dataset', detail: 'Public breast ultrasound images with masks (Al-Dhabyani et al. 2020)' },
      { label: 'Education only', detail: 'Not for diagnosis, triage, or screening' },
    ],
  },
  {
    id: 'labels',
    kicker: 'Step 2 · Categories',
    shortTitle: 'Labels',
    title: 'Benign, malignant, and normal',
    body: 'BUSI labels each image as benign, malignant, or normal. Benign and malignant cases include a ground-truth lesion mask; normal images have no lesion. This project trains a U-Net to predict a mask and an auxiliary benign-vs-malignant score when a lesion is present.',
    alt: 'Three labeled tiles: benign, malignant, and normal ultrasound categories used by the BUSI dataset.',
    callouts: [
      { label: 'Benign / malignant', detail: 'Lesion present; mask outlines the region of interest' },
      { label: 'Normal', detail: 'Trained with empty masks so the model can learn “no lesion”' },
    ],
  },
  {
    id: 'segmentation',
    kicker: 'Step 3 · Task',
    shortTitle: 'Segmentation',
    title: 'What lesion segmentation means',
    body: 'Segmentation means drawing a pixel-level outline of the lesion — not just saying “something is there.” The demo overlays the predicted mask on the ultrasound and lets you adjust opacity. A separate head estimates P(malignant) for research comparison with the BUSI label.',
    alt: 'An ultrasound frame with an orange semi-transparent lesion mask and a darker contour outline.',
    callouts: [
      { label: 'Mask overlay', detail: 'Predicted lesion region with adjustable opacity' },
      { label: 'Auxiliary score', detail: 'Benign-vs-malignant probability when a lesion is present' },
    ],
  },
  {
    id: 'pitfalls',
    kicker: 'Step 4 · Honest data issues',
    shortTitle: 'Pitfalls',
    title: 'Calipers, duplicates, and missing patient IDs',
    body: 'BUSI has no patient IDs, so true patient-level splits are impossible. Many frames contain caliper marks or near-duplicates that can inflate scores if they leak across train and test. This project groups near-duplicates with perceptual hashing and audits caliper/text marks so reported metrics stay honest.',
    alt: 'Icons representing caliper marks on an ultrasound, near-duplicate frames, and grouped train/test splits.',
    callouts: [
      { label: 'Grouped splits', detail: 'Near-duplicate groups stay in one split only' },
      { label: 'Cleaning study', detail: 'Measures how flagged marks affect Dice and AUC' },
    ],
  },
  {
    id: 'browser',
    kicker: 'Step 5 · Into this demo',
    shortTitle: 'Browser demo',
    title: 'From training run to your browser',
    body: 'A ResNet-18 U-Net is trained on CPU, exported to ONNX, and quantized for a small download. The GitHub Pages site runs inference entirely in your browser with ONNX Runtime Web — nothing is uploaded to a server. Start with a held-out BUSI test sample, then read Results and the model card for metrics and limits.',
    alt: 'A progress bar downloading a small ONNX model, then a BUSI sample with a mask overlay in the browser.',
    callouts: [
      { label: 'ONNX in-browser', detail: 'Weights download once; later visits use cache when available' },
      { label: 'Held-out samples', detail: 'Gallery images come from the grouped test split' },
    ],
  },
]

export const EXPLAINER_SOURCES = [
  {
    label: 'BUSI dataset paper',
    href: 'https://doi.org/10.1016/j.dib.2019.104863',
  },
]
