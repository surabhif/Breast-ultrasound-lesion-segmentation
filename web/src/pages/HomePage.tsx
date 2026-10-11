import { lazy, Suspense, useEffect } from 'react'
import { Link } from 'react-router-dom'
import HowBuilt from '../components/HowBuilt'
import { LandingHero } from './home/LandingHero'
import { LandingWhy } from './home/LandingWhy'
import { LandingWhat } from './home/LandingWhat'
import { LandingHow } from './home/LandingHow'
import { applyLandingHash } from './home/landingNav'

const BusExplainer = lazy(() => import('../explainer/BusExplainer'))
const BASE = import.meta.env.BASE_URL

export default function HomePage() {
  useEffect(() => {
    applyLandingHash(window.location.hash)
    const onHash = () => applyLandingHash(window.location.hash)
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  return (
    <div className="home fade-in landing-home">
      <LandingHero />
      <LandingWhy />
      <LandingWhat />
      <LandingHow />

      <section id="walkthrough" className="landing-section" aria-labelledby="walkthrough-heading">
        <div className="landing-partbanner">
          <span className="k">Watch</span>
          <span className="t" id="walkthrough-heading">
            Site walkthrough
          </span>
          <span className="d">About one minute, with captions. No voiceover.</span>
        </div>
        <figure className="walkthrough-embed panel">
          <video
            controls
            playsInline
            preload="metadata"
            poster={`${BASE}video/walkthrough-poster.jpg`}
            aria-label="Captioned walkthrough of the research demo site"
          >
            <source src={`${BASE}video/walkthrough.mp4`} type="video/mp4" />
            <track
              kind="captions"
              srcLang="en"
              label="English"
              src={`${BASE}video/walkthrough.vtt`}
              default
            />
          </video>
          <figcaption className="muted tiny">
            Research demo only. Not for clinical use.{' '}
            <a href={`${BASE}report.pdf`} target="_blank" rel="noreferrer">
              Research write-up (PDF)
            </a>
            {' · '}
            <Link to="/about">About &amp; cite</Link>
          </figcaption>
        </figure>
        <HowBuilt className="how-built muted tiny" />
      </section>

      <section id="explainer" className="landing-explainer" aria-label="Interactive educational tour">
        <Suspense
          fallback={
            <div className="panel landing-explainer-fallback">
              <p className="landing-eyebrow">Interactive explainer</p>
              <h2>Loading the tour…</h2>
              <div className="landing-actions">
                <Link className="btn" to="/demo">
                  Try the detector
                </Link>
              </div>
            </div>
          }
        >
          <BusExplainer compactIntro />
        </Suspense>
      </section>
    </div>
  )
}
