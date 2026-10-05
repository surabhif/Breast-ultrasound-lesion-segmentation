import { goToExplainerStep } from './landingNav'

export function LandingWhy() {
  return (
    <section id="why" className="landing-section" aria-labelledby="why-heading">
      <div className="landing-partbanner">
        <span className="k">Part 1</span>
        <span className="t" id="why-heading">
          Why
        </span>
        <span className="d">The research question behind the app</span>
      </div>

      <div className="landing-block">
        <h2>Why breast ultrasound lesions matter</h2>
        <p className="landing-tldr">
          <b>In short:</b> ultrasound helps describe masses in the breast, and outlining a lesion
          is a common research task — but published scores on public datasets can look better than
          they are when near-duplicates or burned-in calipers leak information.
        </p>
        <p>
          Breast ultrasound is widely used to characterize findings from mammography or physical
          exam, especially in dense breasts. Segmenting a lesion (drawing its outline) and
          estimating whether it looks more benign or malignant are frequent machine-learning
          exercises on public data such as BUSI.
        </p>
        <p>
          <button
            type="button"
            className="landing-jumplink"
            onClick={() => goToExplainerStep('ultrasound')}
          >
            See Step 1 · Ultrasound in the tour →
          </button>
        </p>
      </div>

      <div className="landing-block">
        <h2>What BUSI labels look like</h2>
        <p>
          The Breast Ultrasound Images Dataset (BUSI) labels frames as benign, malignant, or
          normal, with pixel masks for lesions. Normal images have no lesion region.
        </p>
        <div className="landing-sizes">
          <div className="landing-size">
            <span className="dot benign-dot" style={{ width: 18, height: 18 }} aria-hidden="true" />
            <h3>Benign</h3>
            <p>Lesion present; mask outlines the region of interest</p>
          </div>
          <div className="landing-size">
            <span
              className="dot malignant-dot"
              style={{ width: 28, height: 28 }}
              aria-hidden="true"
            />
            <h3>Malignant</h3>
            <p>Lesion present; often more irregular appearance in the dataset</p>
          </div>
          <div className="landing-size">
            <span className="dot normal-dot" style={{ width: 14, height: 14 }} aria-hidden="true" />
            <h3>Normal</h3>
            <p>No lesion; trained here with empty masks</p>
          </div>
        </div>
        <p>
          <button
            type="button"
            className="landing-jumplink"
            onClick={() => goToExplainerStep('labels')}
          >
            See Step 2 · Labels →
          </button>
        </p>
      </div>

      <div className="landing-block">
        <h2>Segmentation vs a simple score</h2>
        <div className="landing-cards two">
          <article className="landing-card">
            <h3>Lesion mask</h3>
            <p>
              A pixel-level outline of where the model thinks the lesion is — shown as an overlay
              with adjustable opacity in the detector.
            </p>
          </article>
          <article className="landing-card">
            <h3>Benign / malignant score</h3>
            <p>
              An auxiliary probability that a lesion is malignant rather than benign. It is less
              meaningful when little or no lesion is detected.
            </p>
          </article>
        </div>
        <p className="landing-callout note">
          This summary is simplified for a general audience. Real imaging decisions depend on many
          factors and are made by clinical teams — never by this demo.
        </p>
        <p>
          <button
            type="button"
            className="landing-jumplink"
            onClick={() => goToExplainerStep('segmentation')}
          >
            See Step 3 · Segmentation →
          </button>
        </p>
      </div>

      <div className="landing-block">
        <h2>Why computer assistance — and why honesty matters</h2>
        <p>
          Researchers study whether models can outline lesions consistently on digitized
          ultrasound. Public benchmarks help students learn the pipeline — but dataset artifacts
          can inflate reported Dice or AUC if near-copies or caliper marks cross the train/test
          boundary.
        </p>
        <p>
          This app is an educational window into that idea: what such a model outputs, how
          metrics are measured on held-out grouped splits, and where the data still misleads.
        </p>
        <p>
          <button
            type="button"
            className="landing-jumplink"
            onClick={() => goToExplainerStep('pitfalls')}
          >
            See Step 4 · Pitfalls →
          </button>
        </p>
      </div>
    </section>
  )
}
