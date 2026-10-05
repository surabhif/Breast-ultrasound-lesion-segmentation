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
        A static website: no account, no installation, and no server running the model. Main areas:
      </p>

      <div className="landing-cards tour">
        <article className="landing-card">
          <span className="landing-card-kicker">On this page</span>
          <h3>Educational tour</h3>
          <p>
            Five interactive steps covering ultrasound, BUSI labels, segmentation, data pitfalls,
            and in-browser inference.
          </p>
          <button type="button" className="landing-jumplink" onClick={() => goToExplainerStep()}>
            Open the tour →
          </button>
        </article>
        <article className="landing-card">
          <span className="landing-card-kicker">Try it</span>
          <h3>Detector</h3>
          <p>
            Segment a BUSI test sample or upload an image; see a mask overlay and a
            benign-vs-malignant score.
          </p>
          <Link className="landing-jumplink" to="/demo">
            Go to Demo →
          </Link>
        </article>
        <article className="landing-card">
          <span className="landing-card-kicker">Evaluation</span>
          <h3>Results</h3>
          <p>Dice, IoU, classification AUC, and the cleaning experiment from the training run.</p>
          <Link className="landing-jumplink" to="/results">
            View Results →
          </Link>
        </article>
        <article className="landing-card">
          <span className="landing-card-kicker">Transparency</span>
          <h3>Model card</h3>
          <p>Intended use, training data, and known limitations — educational, not clinical.</p>
          <Link className="landing-jumplink" to="/model-card">
            Read the model card →
          </Link>
        </article>
        <article className="landing-card">
          <span className="landing-card-kicker">Project</span>
          <h3>About</h3>
          <p>Background on the project and its educational purpose.</p>
          <Link className="landing-jumplink" to="/about">
            About the project →
          </Link>
        </article>
      </div>

      <div className="landing-block">
        <h2>Tour chapters</h2>
        <div className="landing-cards steps">
          {(
            [
              ['ultrasound', '1', 'Ultrasound', 'Why breast ultrasound is used in research demos.'],
              ['labels', '2', 'Labels', 'Benign, malignant, and normal in BUSI.'],
              ['segmentation', '3', 'Segmentation', 'Mask overlay vs a simple class score.'],
              ['pitfalls', '4', 'Pitfalls', 'Calipers, near-duplicates, grouped splits.'],
              ['browser', '5', 'Browser demo', 'ONNX in your browser on held-out samples.'],
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
