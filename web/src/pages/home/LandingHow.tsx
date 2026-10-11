import { Link } from 'react-router-dom'
import { goToExplainerStep } from './landingNav'
import { MODEL_STATUS } from '../../lib/constants'

export function LandingHow() {
  return (
    <section id="how" className="landing-section" aria-labelledby="how-heading">
      <div className="landing-partbanner">
        <span className="k">Part 3</span>
        <span className="t" id="how-heading">
          How
        </span>
        <span className="d">Using the detector in your browser</span>
      </div>

      <ol className="landing-steps">
        <li>
          <strong>Start with the tour (recommended).</strong>
          <p>
            Walk through five short scenes on ultrasound, BUSI labels, outlining, data pitfalls,
            and the browser demo.{' '}
            <button
              type="button"
              className="landing-jumplink inline"
              onClick={() => goToExplainerStep()}
            >
              Start the tour
            </button>
          </p>
        </li>
        <li>
          <strong>Open “Try the detector.”</strong>
          <p>
            The model downloads once (~{MODEL_STATUS.sizeHintMb}&nbsp;MB) with a progress bar.
            Later visits load it from your browser cache.
          </p>
        </li>
        <li>
          <strong>Choose an image.</strong>
          <p>
            Pick a gallery sample from the BUSI test set, or upload your own. Breast ultrasound
            frames like BUSI give the most meaningful results.
          </p>
        </li>
        <li>
          <strong>Read the result.</strong>
          <p>
            Look at the lump outline overlay and the harmless vs cancerous score. Fade the overlay
            to compare with the ultrasound. For gallery samples, compare with the known BUSI label.
          </p>
        </li>
        <li>
          <strong>Interpret carefully.</strong>
          <p>
            Visit <Link to="/results">Results</Link> and the{' '}
            <Link to="/model-card">Model card</Link> for accuracy and failure modes. An outline and
            score are not a patient diagnosis.
          </p>
        </li>
      </ol>

      <p className="landing-callout note">
        <strong>Runs in your browser.</strong> The model runs on your device. Uploaded images are
        not sent to a server for analysis.
      </p>

      <div className="landing-actions">
        <Link className="btn" to="/demo">
          Try the detector
        </Link>
        <button type="button" className="btn secondary" onClick={() => goToExplainerStep()}>
          Back to the tour
        </button>
      </div>
    </section>
  )
}
