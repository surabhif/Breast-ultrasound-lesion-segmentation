import { Link } from 'react-router-dom'
import { goToExplainerStep } from './landingNav'

export function LandingWhat() {
  return (
    <section id="what" className="landing-section" aria-labelledby="what-heading">
      <div className="landing-partbanner">
        <span className="k">Part 2</span>
        <span className="t" id="what-heading">
          What
        </span>
        <span className="d">What you&apos;ll find in the app</span>
      </div>

      <p className="landing-intro">
        A static website. No account. No install. The model runs on your device. Main areas:
      </p>

      <div className="landing-cards tour">
        <article className="landing-card">
          <span className="landing-card-kicker">On this page</span>
          <h3>Educational tour</h3>
          <p>
            Five short steps on ultrasound, BUSI labels, outlining, data pitfalls, and the browser
            demo.
          </p>
          <button type="button" className="landing-jumplink" onClick={() => goToExplainerStep()}>
            Open the tour →
          </button>
        </article>
        <article className="landing-card">
          <span className="landing-card-kicker">Try it</span>
          <h3>Detector</h3>
          <p>
            Outline a BUSI test sample or your own image. See a mask overlay and a harmless vs
            cancerous score.
          </p>
          <Link className="landing-jumplink" to="/demo">
            Go to Demo →
          </Link>
        </article>
        <article className="landing-card">
          <span className="landing-card-kicker">Evaluation</span>
          <h3>Results</h3>
          <p>
            Outline-overlap scores (Dice), classification numbers, and cleaning experiments from
            the training run.
          </p>
          <Link className="landing-jumplink" to="/results">
            View Results →
          </Link>
        </article>
        <article className="landing-card">
          <span className="landing-card-kicker">Transparency</span>
          <h3>Model card</h3>
          <p>Intended use, training data, and known limits. Educational, not clinical.</p>
          <Link className="landing-jumplink" to="/model-card">
            Read the model card →
          </Link>
        </article>
        <article className="landing-card">
          <span className="landing-card-kicker">Context</span>
          <h3>BI-RADS</h3>
          <p>What ultrasound BI-RADS categories mean, and why a model score is not one.</p>
          <Link className="landing-jumplink" to="/bi-rads">
            BI-RADS context →
          </Link>
        </article>
        <article className="landing-card">
          <span className="landing-card-kicker">Context</span>
          <h3>Surgeon&apos;s view</h3>
          <p>Size and margins as research ideas, not operative planning.</p>
          <Link className="landing-jumplink" to="/surgeons-view">
            Surgeon&apos;s view →
          </Link>
        </article>
        <article className="landing-card">
          <span className="landing-card-kicker">Project</span>
          <h3>About · write-up · video</h3>
          <p>Citation, privacy note, captioned walkthrough, and auto-filled PDF report.</p>
          <Link className="landing-jumplink" to="/about">
            About the project →
          </Link>
        </article>
        <article className="landing-card">
          <span className="landing-card-kicker">Portfolio</span>
          <h3>Related demos</h3>
          <p>Lymph-node metastasis detector and pathology report explainer.</p>
          <Link className="landing-jumplink" to="/portfolio">
            Open portfolio →
          </Link>
        </article>
      </div>

      <div className="landing-block">
        <h2>Tour chapters</h2>
        <div className="landing-cards steps">
          {(
            [
              ['ultrasound', '1', 'Ultrasound', 'Why breast ultrasound shows up in research demos.'],
              ['labels', '2', 'Labels', 'Harmless, cancerous, and normal in BUSI.'],
              ['segmentation', '3', 'Segmentation', 'Mask overlay vs a simple class score.'],
              ['pitfalls', '4', 'Pitfalls', 'Calipers, near-copies, careful splits.'],
              ['browser', '5', 'Browser demo', 'The model runs on your device on test samples.'],
            ] as const
          ).map(([id, num, title, blurb]) => (
            <button
              key={id}
              type="button"
              className="landing-card landing-card-button"
              onClick={() => goToExplainerStep(id)}
            >
              <span className="stepno">{num}</span>
              <h3>{title}</h3>
              <p>{blurb}</p>
            </button>
          ))}
        </div>
      </div>
    </section>
  )
}
