import HowBuilt from '../components/HowBuilt'
import { SITE } from '../lib/constants'

type ProjectCard = {
  title: string
  blurb: string
  repoUrl: string
  liveUrl?: string
  doiUrl?: string
  /** Verified published metric only — omit rather than invent. */
  metric?: { label: string; value: string; source: string }
}

/**
 * Sibling URLs verified HTTP 200 on 2026-10-08 before linking.
 * Pathology GitHub Pages 404 — use Vercel homepage from the repo instead.
 * Pathology has no static published metrics JSON in-repo → no invented headline metric.
 */
const PROJECTS: ProjectCard[] = [
  {
    title: 'Breast ultrasound lesion segmentation',
    blurb:
      'Browser demo that outlines lumps on BUSI, with outside checks on BUS-BRA, BrEaST, and BUS-UCLM, plus caliper audits and clear limits.',
    repoUrl: 'https://github.com/surabhif/Breast-ultrasound-lesion-segmentation',
    liveUrl: 'https://surabhif.github.io/Breast-ultrasound-lesion-segmentation/',
    doiUrl: SITE.doiUrl,
    metric: {
      label: 'Browser-model test Dice (BUSI)',
      value: '0.697 out of 1',
      source: 'results/served_int8_test.json',
    },
  },
  {
    title: 'Lymph-node metastasis detector',
    blurb:
      'PatchCamelyon (PCam) research demo: highlight tumor-suspicious patches in lymph-node tissue images.',
    repoUrl: 'https://github.com/surabhif/Lymph-node-metastasis-detector',
    liveUrl: 'https://surabhif.github.io/Lymph-node-metastasis-detector/',
    metric: {
      label: 'Test ranking score (published subset run)',
      value: '0.910 out of 1',
      source: 'web/public/results/metrics.json (sibling repo)',
    },
  },
  {
    title: 'Pathology report explainer',
    blurb:
      'Plain-language explanations of de-identified TCGA pathology reports with quote-level citations.',
    repoUrl: 'https://github.com/surabhif/Pathology-report-explainer',
    liveUrl: 'https://pathology-report-explainer.vercel.app',
  },
]

export default function PortfolioPage() {
  return (
    <article className="panel prose fade-in portfolio-page">
      <header className="page-intro">
        <p className="landing-eyebrow">Student portfolio</p>
        <h1>Surabhi Fadnavis · oncology AI research demos</h1>
        <p>
          High-school senior, Georgia. Three related research demos. Each is educational. Each is{' '}
          <strong>not for clinical use</strong>.
        </p>
      </header>

      <div className="portfolio-grid" role="list">
        {PROJECTS.map((p) => (
          <section className="portfolio-card" role="listitem" key={p.repoUrl}>
            <h2>{p.title}</h2>
            <p>{p.blurb}</p>
            {p.metric && (
              <p className="portfolio-metric">
                <span className="portfolio-metric-label">{p.metric.label}</span>
                <strong>{p.metric.value}</strong>
                <span className="muted tiny">Source: {p.metric.source}</span>
              </p>
            )}
            <p className="portfolio-links">
              <a href={p.repoUrl} target="_blank" rel="noreferrer">
                GitHub
              </a>
              {p.liveUrl && (
                <>
                  {' · '}
                  <a href={p.liveUrl} target="_blank" rel="noreferrer">
                    Live demo
                  </a>
                </>
              )}
              {p.doiUrl && (
                <>
                  {' · '}
                  <a href={p.doiUrl} target="_blank" rel="noreferrer">
                    DOI
                  </a>
                </>
              )}
            </p>
          </section>
        ))}
      </div>

      <h2>How I work</h2>
      <ul>
        <li>Publish numbers from committed JSON. Never invent headline metrics.</li>
        <li>Lead with limits: near-copies, calipers, domain shift, and what the model cannot do.</li>
        <li>Keep disclaimers visible. Research demos stay research demos.</li>
        <li>Prefer open licenses and clear dataset attribution (CC BY outside sets; BUSI citation).</li>
      </ul>

      <HowBuilt id="how-built" className="how-built" />
    </article>
  )
}
