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
        <h2>Why breast ultrasound lumps matter</h2>
        <p className="landing-tldr">
          Ultrasound helps describe masses in the breast. Drawing an outline around a lump is a
          common research task. Public dataset scores can look too good when near-identical photos
          or measurement marks leak into both training and testing.
        </p>
        <p>
          Doctors often use breast ultrasound after a mammogram or exam, especially in dense
          breasts. Researchers use public image sets such as BUSI to practice outlining a lump and
          estimating whether it looks more harmless (benign) or cancerous (malignant).
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
          The Breast Ultrasound Images Dataset (BUSI) labels frames as harmless, cancerous, or
          normal. Lesion images include a pixel outline of the lump. Normal images have no lump.
        </p>
        <div className="landing-sizes">
          <div className="landing-size">
            <span className="dot benign-dot" style={{ width: 18, height: 18 }} aria-hidden="true" />
            <h3>Harmless (benign)</h3>
            <p>A lump is present. The mask outlines that region.</p>
          </div>
          <div className="landing-size">
            <span
              className="dot malignant-dot"
              style={{ width: 28, height: 28 }}
              aria-hidden="true"
            />
            <h3>Cancerous (malignant)</h3>
            <p>A lump is present. Edges often look more irregular in this set.</p>
          </div>
          <div className="landing-size">
            <span className="dot normal-dot" style={{ width: 14, height: 14 }} aria-hidden="true" />
            <h3>Normal</h3>
            <p>No lump. Training uses an empty outline.</p>
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
        <h2>Outline vs a simple score</h2>
        <div className="landing-cards two">
          <article className="landing-card">
            <h3>Lump outline</h3>
            <p>
              A pixel map of where the program thinks the lump is. The detector shows it as a
              colored overlay you can fade.
            </p>
          </article>
          <article className="landing-card">
            <h3>Harmless vs cancerous score</h3>
            <p>
              A second number estimates whether a detected lump looks cancerous. It means less when
              little or no lump is found.
            </p>
          </article>
        </div>
        <p className="landing-callout note">
          This summary is simplified for a general audience. Real imaging decisions belong to
          clinical teams, not this demo.
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
        <h2>Why computers, and why careful scores</h2>
        <p>
          Researchers ask whether programs can outline lumps on digitized ultrasound. Public
          benchmarks help students learn, but dataset quirks can inflate outline-overlap scores
          (Dice) or ranking scores if near-copies or caliper marks cross the train/test line.
        </p>
        <p>
          This app shows what such a program outputs, how scores are measured on careful splits,
          and where the data can still mislead.
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
