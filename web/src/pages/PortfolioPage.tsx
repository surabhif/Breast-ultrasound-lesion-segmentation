import HowBuilt from '../components/HowBuilt'

type ProjectCard = {
  title: string
  blurb: string
  repoUrl: string
  liveUrl?: string
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
      'In-browser U-Net on BUSI with external BUS-BRA / BrEaST checks, caliper audits, and honest limitations.',
    repoUrl: 'https://github.com/surabhif/Breast-ultrasound-lesion-segmentation',
    liveUrl: 'https://surabhif.github.io/Breast-ultrasound-lesion-segmentation/',
    metric: {
      label: 'Served INT8 test Dice (BUSI)',
      value: '0.697',
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
      label: 'Test ROC-AUC (published subset run)',
      value: '0.910',
      source: 'web/public/results/metrics.json (sibling repo)',
    },
  },
  {
    title: 'Pathology report explainer',
    blurb:
      'Grounded plain-language explanations of de-identified TCGA pathology reports with quote-level citations.',
    repoUrl: 'https://github.com/surabhif/Pathology-report-explainer',
    liveUrl: 'https://pathology-report-explainer.vercel.app',
    // No static published metrics JSON verified → metric omitted on purpose.
  },
]

export default function PortfolioPage() {
  return (
    <article className="panel prose fade-in portfolio-page">
      <header className="page-intro">
        <p className="landing-eyebrow">Student portfolio</p>
        <h1>Surabhi Fadnavis: student research in oncology AI</h1>
        <p>
          High-school senior, Georgia. Three related research demos — each educational, each
          explicitly <strong>not for clinical use</strong>.
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
            </p>
          </section>
        ))}
      </div>

      <h2>How I work</h2>
      <ul>
        <li>Publish numbers from committed JSON — never invent headline metrics.</li>
        <li>Lead with limitations: leakage, calipers, domain shift, and what the model cannot do.</li>
        <li>Keep disclaimers visible; research demos stay research demos.</li>
        <li>Prefer open licenses and clear dataset attribution (CC BY externals; BUSI citation).</li>
        <li>No clinician involvement on this breast-ultrasound project (owner decision).</li>
      </ul>

      <HowBuilt id="how-built" className="how-built" />
    </article>
  )
}
