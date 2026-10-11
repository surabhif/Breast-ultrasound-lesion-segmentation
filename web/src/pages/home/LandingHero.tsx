import { Link } from 'react-router-dom'
import { goToExplainerStep } from './landingNav'
import { SITE } from '../../lib/constants'

export function LandingHero() {
  return (
    <header className="landing-hero">
      <p className="landing-eyebrow">Educational research demo</p>
      <h1 className="landing-title">{SITE.title}</h1>
      <p className="landing-byline">
        A research project by <strong>Surabhi Fadnavis</strong>
      </p>
      <p className="landing-lede">
        This site asks a simple research question about public breast ultrasound. Can a small
        program outline a lump in your browser? Do the published scores still hold when images
        share near-copies or burned-in measurement marks? Take a short tour, then try a demo that
        draws an outline and estimates whether a lump looks harmless or cancerous.
      </p>
      <div className="landing-actions">
        <a
          className="btn"
          href="#explainer"
          onClick={(e) => {
            e.preventDefault()
            goToExplainerStep()
          }}
        >
          Start the tour
        </a>
        <Link className="btn secondary" to="/demo">
          Try the detector
        </Link>
      </div>
      <nav className="landing-wwh" aria-label="Guide sections">
        <a href="#why">
          <b>Why</b>
          <span>Why outlining lumps on ultrasound matters for research.</span>
        </a>
        <a href="#what">
          <b>What</b>
          <span>Tour, detector, results, and model notes.</span>
        </a>
        <a href="#how">
          <b>How</b>
          <span>How to run the detector in your browser.</span>
        </a>
      </nav>
      <p className="landing-disclaimer" role="note">
        <strong>Educational only. Not for clinical use.</strong> Built on a public research
        dataset. Not a diagnostic tool. Never use it for anyone&apos;s health decisions.
      </p>
    </header>
  )
}
