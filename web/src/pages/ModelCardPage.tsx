import { SITE, MODEL_STATUS } from '../lib/constants'

export default function ModelCardPage() {
  return (
    <article className="panel prose fade-in">
      <header className="page-intro">
        <h1>Model card</h1>
        <p>
          Mitchell et al.–style documentation for the served BUSI lesion segmentation model.
          Research demo, not for clinical use.
        </p>
      </header>

      <h2>Model details</h2>
      <ul>
        <li>
          <strong>Architecture:</strong> U-Net with ResNet-18 ImageNet encoder and an auxiliary
          benign-vs-malignant classification head
        </li>
        <li>
          <strong>Input:</strong> RGB ultrasound resized to 128×128, ImageNet normalized
        </li>
        <li>
          <strong>Outputs:</strong> lesion probability map (<code>seg_mask</code>) and P(malignant)
          (<code>cls_prob</code>)
        </li>
        <li>
          <strong>Served artifact:</strong> <code>models/busi_unet.onnx</code> ({MODEL_STATUS.label}
          , ~{MODEL_STATUS.sizeHintMb} MB target after quantization)
        </li>
        <li>
          <strong>Framework:</strong> PyTorch training → ONNX → onnxruntime-web (WASM)
        </li>
      </ul>

      <h2 id="current-model">Current served model</h2>
      <p>
        The GitHub Pages build serves the ONNX file committed under <code>web/public/models/</code>.
        Status text lives in <code>MODEL_STATUS.txt</code> next to the weights. Metrics on the
        Results page are produced by the same checkpoint used for export — not hand-written.
      </p>

      <h2>Intended use</h2>
      <ul>
        <li>Education and research demonstration of ultrasound lesion segmentation</li>
        <li>Interview-ready discussion of leakage, calibration, and dataset artifacts</li>
        <li>
          <strong>Not</strong> intended for diagnosis, screening, triage, or any clinical decision
        </li>
      </ul>

      <h2>Training data</h2>
      <p>
        BUSI (Al-Dhabyani et al., 2020): benign / malignant / normal breast ultrasound PNGs with
        masks. Multi-mask lesions are OR-merged. Near-duplicates are grouped via perceptual hashing.
        An automated heuristic flags likely caliper marks and burned-in text; the audit CSV is
        committed under <code>results/</code>.
      </p>

      <h2>Splits</h2>
      <p>
        Held-out test (~15%) plus 5-fold cross-validation on the remainder, stratified by label and
        grouped so near-duplicate clusters never cross splits. <strong>True patient-level splits
        are not possible</strong> because BUSI publishes no patient IDs.
      </p>

      <h2>Metrics</h2>
      <p>
        Primary: Dice and IoU per image (mean with bootstrap 95% CIs), overall and by
        benign/malignant/normal; lesion-only Dice excludes normals. Classification: ROC-AUC,
        sensitivity/specificity at threshold 0.5, confusion matrix, reliability diagram / ECE. See
        the Results page for the numbers from the actual training run.
      </p>

      <h2 id="limitations">Limitations</h2>
      <ul>
        <li>Single public dataset; scanner / population shift is untested</li>
        <li>No patient IDs → residual leakage risk beyond near-duplicate hashing</li>
        <li>Caliper and HUD artifacts may still act as shortcuts</li>
        <li>Low resolution (128²) for CPU/browser practicality — fine detail is lost</li>
        <li>Classification head is auxiliary and poorly defined for “normal” images</li>
        <li>Small test set → wide confidence intervals</li>
      </ul>

      <h2>Ethical considerations</h2>
      <p>
        Incorrect lesion outlines or malignancy scores could cause harm if misused clinically.
        Always show the research disclaimer. Do not collect or upload identifiable patient studies
        to public demos. Prefer local/browser inference so images need not leave the device.
      </p>

      <h2>Citation</h2>
      <p>
        Al-Dhabyani et al., Data in Brief 2020. Project: {SITE.githubUrl}
      </p>
    </article>
  )
}
