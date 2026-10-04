import { NavLink } from 'react-router-dom'
import { SITE } from '../lib/constants'

export default function HomePage() {
  return (
    <div className="fade-in home-page">
      <section className="hero panel">
        <p className="hero-kicker">BUSI research demo</p>
        <h1 className="hero-brand">{SITE.title}</h1>
        <p className="hero-lead">
          A U-Net that outlines breast ultrasound lesions in your browser and estimates a
          benign-vs-malignant score — built as a transparent high-school research project on the
          public BUSI dataset.
        </p>
        <div className="hero-actions">
          <NavLink className="btn" to="/demo">
            Try the demo
          </NavLink>
          <NavLink className="btn secondary" to="/results">
            See results
          </NavLink>
        </div>
        <p className="tiny muted" style={{ marginBottom: 0, marginTop: '1rem' }}>
          Research demo, not for clinical use. Model weights run locally via ONNX Runtime Web.
        </p>
      </section>

      <section className="home-grid">
        <article className="panel">
          <h2 className="section-title">What it does</h2>
          <p>
            Upload a breast ultrasound image or pick a BUSI test sample. The model predicts a lesion
            mask (overlay + outline) and a probability that a lesion is malignant rather than
            benign. Normal images were trained with empty masks so the network can also learn “no
            lesion.”
          </p>
        </article>
        <article className="panel">
          <h2 className="section-title">Research angle</h2>
          <p>
            BUSI has no patient IDs, and many frames contain caliper marks or near-duplicates. This
            project measures how those issues can inflate reported scores — and uses grouped splits
            so near-copies never cross train/test.
          </p>
        </article>
        <article className="panel">
          <h2 className="section-title">Learn the method</h2>
          <p>
            Read the plain-language walkthrough in{' '}
            <a href={SITE.githubUrl + '/blob/main/docs/HOW_IT_WORKS.md'}>docs/HOW_IT_WORKS.md</a>,
            then the <NavLink to="/model-card">model card</NavLink> for intended use, metrics, and
            limitations.
          </p>
        </article>
      </section>
    </div>
  )
}
