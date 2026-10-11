import HowBuilt from '../components/HowBuilt'
import { MODEL_STATUS, SITE } from '../lib/constants'

export default function ModelCardPage() {
  return (
    <article className="panel prose fade-in">
      <header className="page-intro">
        <h1>Model card</h1>
        <p>
          Plain documentation for the breast ultrasound outlining model served on this site.
          Research demo. Not for clinical use.
        </p>
      </header>

      <h2>Model details</h2>
      <ul>
        <li>
          <strong>Version:</strong> <code>v{MODEL_STATUS.version}</code>
        </li>
        <li>
          <strong>What it does:</strong> draws a lump outline and estimates whether a detected lump
          looks harmless or cancerous
        </li>
        <li>
          <strong>Input:</strong> color ultrasound resized to 160×160
        </li>
        <li>
          <strong>Outputs:</strong> an outline map and a cancerous-lump score
        </li>
        <li>
          <strong>Cleanup after prediction:</strong> keep outline pixels above 0.4, then drop tiny
          blobs under 40 pixels
        </li>
        <li>
          <strong>Download size:</strong> about {MODEL_STATUS.sizeHintMb} MB
        </li>
      </ul>
      <details className="tech-details">
        <summary>Technical details</summary>
        <ul>
          <li>
            Architecture: U-Net with ResNet-18 ImageNet encoder and an auxiliary classification head
            ({MODEL_STATUS.label})
          </li>
          <li>
            Artifact: <code>models/v{MODEL_STATUS.version}/busi_unet.onnx</code>, selected by{' '}
            <code>models/current.json</code>
          </li>
          <li>Training stack: PyTorch → ONNX → onnxruntime-web (WASM), dynamic INT8 weights</li>
          <li>
            Output tensors: <code>seg_mask</code>, <code>cls_prob</code>
          </li>
        </ul>
      </details>

      <h2 id="current-model">Current served model</h2>
      <p>
        The live site serves model version <strong>v{MODEL_STATUS.version}</strong>. The browser
        cache key includes the version so an update is not blocked by an old download. The Results
        page shows both the training checkpoint scores and the browser-model scores on the same
        test set.
      </p>

      <h2>Intended use</h2>
      <ul>
        <li>Education and research demonstration of ultrasound lump outlining</li>
        <li>Practice talking about data leakage, calibration, and dataset quirks</li>
        <li>
          <strong>Not</strong> for diagnosis, screening, triage, or any clinical decision
        </li>
      </ul>

      <h2>Training data</h2>
      <p>
        BUSI (Al-Dhabyani et al., 2020): harmless (benign), cancerous (malignant), and normal (no
        lump) breast ultrasound PNGs with outlines. Multi-mask lumps are merged. Near-identical
        photos are grouped together. An automated check flags likely caliper marks and burned-in
        text.
      </p>

      <h2>Splits</h2>
      <p>
        About 15% of images are held aside for testing. The rest use 5-fold cross-validation,
        stratified by label. Near-identical photo groups never cross splits.{' '}
        <strong>True patient-level splits are not possible</strong> because BUSI publishes no
        patient IDs.
      </p>

      <h2>Metrics</h2>
      <p>
        Primary: outline-overlap score (Dice) and intersection-over-union (IoU) per image, overall
        and by label. Dice is high when the computer outline matches the expert outline. On images
        that contain a lump, we also report a lump-only Dice that skips normals. Classification:
        how well the score ranks cancerous above harmless, plus sensitivity and specificity at
        threshold 0.5.
      </p>
      <p>
        <strong>Training checkpoint:</strong> test Dice 0.686 out of 1, lump-only Dice 0.751, ranking
        score 0.939.
        <br />
        <strong>Browser model (v{MODEL_STATUS.version}):</strong> test Dice 0.697 out of 1, lump-only
        Dice 0.764, ranking score 0.931. See the Results page for confidence intervals.
      </p>
      <details className="tech-details">
        <summary>Technical details</summary>
        <p>
          FP32 training checkpoint vs served INT8 ONNX on the same grouped test set. Calibration is
          summarized with expected calibration error (ECE). Sources:{' '}
          <code>results/full_run.json</code>, <code>results/served_int8_test.json</code>.
        </p>
      </details>

      <h2 id="phase-2">Later experiments</h2>
      <p>
        A later multi-dataset retrain and a caliper-erase retrain are compared on the Results page.
        A retrained version did better on some outside images but not consistently, so the site
        still serves v{MODEL_STATUS.version}. An offline flip-based uncertainty check is available
        in the Demo.
      </p>

      <h2 id="limitations">Limitations</h2>
      <ul>
        <li>
          Domain shift: on outside sets, outline scores stay nearer the home score (BUS-BRA ≈ 0.714,
          BrEaST ≈ 0.627, BUS-UCLM lump-only ≈ 0.679) while telling harmless from cancerous drops
          (ranking scores ≈ 0.638 / 0.721 / 0.780 vs ≈ 0.931 at home). BUS-UCLM overall Dice ≈ 0.386
          is dragged down by 320/413 false outlines on normal (no lump) images.
        </li>
        <li>No patient IDs → residual risk from near-identical photos</li>
        <li>Caliper and on-screen text may still act as shortcuts</li>
        <li>160×160 resolution for CPU and browser speed; fine detail is lost</li>
        <li>The class score is poorly defined for normal (no lump) images</li>
        <li>Small test set → wide confidence intervals</li>
        <li>
          <strong>Known weakness:</strong> on the test set, both the training checkpoint and the
          browser model draw a non-empty outline on <strong>12 of 19</strong> normal (no lump)
          images. Do not treat a predicted outline on a normal (no lump) frame as evidence of
          disease.
        </li>
      </ul>

      <h2 id="phase-3">Clinical context pages</h2>
      <p>
        Educational BI-RADS and surgeon&apos;s-view pages explain what the model does <em>not</em>{' '}
        claim. A site-only research PDF auto-fills numbers from results JSON. Served model remains{' '}
        <strong>v{MODEL_STATUS.version}</strong>.
      </p>

      <h2>Ethical considerations</h2>
      <p>
        Wrong outlines or scores could cause harm if misused clinically. Always show the research
        disclaimer. Do not upload identifiable patient studies to public demos. Prefer
        on-device inference so images need not leave the device. This site uses no analytics or
        cookies.
      </p>

      <h2>Citation</h2>
      <p>
        Al-Dhabyani et al., Data in Brief 2020. Project: {SITE.githubUrl}. See About → How to cite
        and <code>CITATION.cff</code> (DOI:{' '}
        <a href={SITE.doiUrl} target="_blank" rel="noreferrer">
          {SITE.doi}
        </a>
        ).
      </p>

      <h2 id="how-built">How this was built</h2>
      <HowBuilt />
      <p className="muted tiny">High-school research project. Not for clinical use.</p>
    </article>
  )
}
