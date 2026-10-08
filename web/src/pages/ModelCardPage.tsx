import { MODEL_STATUS, SITE } from '../lib/constants'

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
          <strong>Version:</strong> <code>v{MODEL_STATUS.version}</code> (semantic model tag{' '}
          <code>model-v{MODEL_STATUS.version}</code>)
        </li>
        <li>
          <strong>Architecture:</strong> U-Net with ResNet-18 ImageNet encoder and an auxiliary
          benign-vs-malignant classification head
        </li>
        <li>
          <strong>Input:</strong> RGB ultrasound resized to 160×160, ImageNet normalized
        </li>
        <li>
          <strong>Outputs:</strong> lesion probability map (<code>seg_mask</code>) and P(malignant)
          (<code>cls_prob</code>)
        </li>
        <li>
          <strong>Post-processing:</strong> soft mask threshold 0.4, then drop 4-connected
          components smaller than 40 px (same as the Python metrics pipeline)
        </li>
        <li>
          <strong>Served artifact:</strong>{' '}
          <code>models/v{MODEL_STATUS.version}/busi_unet.onnx</code> ({MODEL_STATUS.label}, ~
          {MODEL_STATUS.sizeHintMb} MB after INT8 quantization). Pointer:{' '}
          <code>models/current.json</code> (versioned Cache API key)
        </li>
        <li>
          <strong>Framework:</strong> PyTorch training → ONNX → onnxruntime-web (WASM)
        </li>
      </ul>

      <h2 id="current-model">Current served model</h2>
      <p>
        The GitHub Pages build serves the versioned ONNX under <code>web/public/models/v1.0.0/</code>
        , selected by <code>models/current.json</code>. The browser cache key includes the version
        and sha8 so a new model cannot be shadowed by a stale cached copy. Metrics on the Results
        page include both the FP32 training checkpoint and the <strong>served INT8</strong> scores
        on the same held-out test set.
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
        sensitivity/specificity at threshold 0.5, confusion matrix, reliability diagram / ECE.
      </p>
      <p>
        <strong>FP32 (training checkpoint, torchvision/PIL resize):</strong> test Dice 0.686, lesion
        Dice 0.751, AUC 0.939.
        <br />
        <strong>INT8 (served ONNX, v{MODEL_STATUS.version}, shared bilinear):</strong> test Dice
        0.697, lesion Dice 0.764, AUC 0.931. Overall Dice is slightly higher than the FP32 training
        number under the browser-matched preprocess; AUC is ~0.008 lower. See the Results page and{' '}
        <code>results/served_int8_test.json</code>.
      </p>

      <h2 id="limitations">Limitations</h2>
      <ul>
        <li>Single public dataset; scanner / population shift is untested (see pre-registered
          external validation protocol — evaluation not run yet)</li>
        <li>No patient IDs → residual leakage risk beyond near-duplicate hashing</li>
        <li>Caliper and HUD artifacts may still act as shortcuts</li>
        <li>160² resolution for CPU/browser practicality — fine detail is lost</li>
        <li>Classification head is auxiliary and poorly defined for “normal” images</li>
        <li>Small test set → wide confidence intervals</li>
        <li>
          <strong>Known weakness — normal-image false positives:</strong> on the held-out test set,
          both the FP32 checkpoint and the served INT8 model produce a non-empty lesion mask on{' '}
          <strong>12 of 19</strong> normal images. Empty-mask Dice on normals is therefore low. Do
          not treat a predicted outline on a “normal” frame as evidence of disease.
        </li>
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
