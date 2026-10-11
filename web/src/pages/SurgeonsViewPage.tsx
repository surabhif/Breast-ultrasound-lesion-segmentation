import { Link } from 'react-router-dom'
import HowBuilt from '../components/HowBuilt'
import measurement from '../data/measurement_agreement.json'

const BASE = import.meta.env.BASE_URL

const BREAST_EXAMPLES = [
  {
    id: 'breast_00',
    img: 'samples/external/breast_00_benign.png',
    mask: 'samples/external/breast_00_benign_mask.png',
    label: 'BrEaST example · harmless (CC BY)',
  },
  {
    id: 'breast_03',
    img: 'samples/external/breast_03_malignant.png',
    mask: 'samples/external/breast_03_malignant_mask.png',
    label: 'BrEaST example · cancerous (CC BY)',
  },
] as const

const BUSI_SILHOUETTES = [
  {
    id: 'busi_benign',
    src: 'results/mistakes_silhouettes/benign__benign_100.png',
    label: 'BUSI outline-only silhouette (no ultrasound pixels)',
  },
  {
    id: 'busi_mal',
    src: 'results/mistakes_silhouettes/malignant__malignant_102.png',
    label: 'BUSI outline-only silhouette (no ultrasound pixels)',
  },
] as const

const diamCorr = Number(measurement.longest_diameter_mm.pearson_proxy_for_icc).toFixed(2)
const t1t2 = (Number(measurement.longest_diameter_mm.t1_t2_20mm_discordance_rate) * 100).toFixed(0)
const nMeas = measurement.n

export default function SurgeonsViewPage() {
  return (
    <article className="panel prose fade-in">
      <header className="page-intro">
        <p className="landing-eyebrow">Surgeon&apos;s-view · research framing</p>
        <h1>Lump size, margins, and what models can tell you</h1>
        <p>
          Why surgeons care about size and margins, and why this demo&apos;s pixel measurements are
          research illustrations, not operative planning.
        </p>
      </header>

      <div className="callout-warn" role="note">
        <strong>Not for clinical use.</strong> Imaging size is not pathologic T-stage. Model
        outlines are not surgical margins. Do not use anything here for biopsy decisions,
        lumpectomy planning, or counseling patients.
      </div>

      <h2>Why surgeons care about size</h2>
      <p>
        In breast cancer care, tumor size helps place a case in the AJCC TNM framework. It also
        shapes talks about breast-conserving surgery versus mastectomy, oncoplastic options, and
        adjuvant therapy. Pathologic size on the excised specimen, not a single ultrasound
        diameter, is what ultimately defines pathologic T category in standard staging.
      </p>
      <p className="muted tiny">
        Source (verified): AJCC Cancer Staging Manual principles for breast cancer T category
        (pathologic tumor size). This page does not reproduce AJCC tables.
      </p>

      <h2>Why margins matter</h2>
      <p>
        For invasive breast cancer treated with breast-conserving surgery, a widely cited consensus
        (SSO–ASTRO) supports &quot;no ink on tumor&quot; as an adequate margin in appropriately
        selected patients receiving whole-breast irradiation. That means the inked specimen edge
        should not touch invasive cancer. DCIS has related but distinct guidance. Those rules apply
        to <em>surgical specimens</em>, not to an AI overlay on a resized ultrasound PNG.
      </p>
      <p className="muted tiny">
        Source (verified): Moran MS, et al. Society of Surgical Oncology–American Society for
        Radiation Oncology consensus guideline on margins for breast-conserving surgery. Ann Surg
        Oncol / Int J Radiat Oncol Biol Phys, 2014 (and later updates). Check current society
        guidance for practice.
      </p>

      <h2>What this model measures</h2>
      <p>
        On the <Link to="/demo">Demo</Link>, after an outline is predicted, the app computes
        research-only geometry on the <strong>160×160</strong> mask:
      </p>
      <ul>
        <li>Area (pixels; mm² only when spacing is known)</li>
        <li>Longest diameter and a perpendicular width</li>
        <li>Optional depth/width from the bounding box</li>
      </ul>
      <p>
        Physical spacing is available only for curated <strong>BrEaST</strong> samples (spacing
        metadata scaled to 160²). BUSI demo images stay in pixels. Offline, we also compared model
        vs expert outline diameters on BrEaST ({nMeas} images): Pearson correlation for longest
        diameter in mm ≈ <strong>{diamCorr}</strong>. Model and expert disagreed on a ≥20 mm
        threshold in about <strong>{t1t2}%</strong> of cases. That is exploratory, not a staging
        claim. Numbers come from committed measurement results.
      </p>

      <h2>What it cannot tell you</h2>
      <ul>
        <li>Pathologic tumor size or AJCC T category</li>
        <li>Distance to a surgical margin or &quot;ink on tumor&quot;</li>
        <li>Whether a lump is resectable with cosmesis goals</li>
        <li>Nodal status, biology, or treatment response</li>
        <li>A BI-RADS assessment (see <Link to="/bi-rads">BI-RADS context</Link>)</li>
      </ul>

      <h2>Examples (licensing-aware)</h2>
      <p>
        Full ultrasound pixels on new pages use CC BY outside imagery. BUSI rows use outline-only
        silhouettes.
      </p>

      <div className="example-grid" role="list">
        {BREAST_EXAMPLES.map((ex) => (
          <figure className="example-card" role="listitem" key={ex.id}>
            <div className="example-pair">
              <img src={`${BASE}${ex.img}`} alt={`Ultrasound: ${ex.label}`} width={240} height={240} />
              <img
                src={`${BASE}${ex.mask}`}
                alt={`Expert mask silhouette for ${ex.label}`}
                width={240}
                height={240}
              />
            </div>
            <figcaption className="muted tiny">{ex.label} · image + expert mask</figcaption>
          </figure>
        ))}
        {BUSI_SILHOUETTES.map((ex) => (
          <figure className="example-card" role="listitem" key={ex.id}>
            <div className="example-pair example-pair-single">
              <img src={`${BASE}${ex.src}`} alt={ex.label} width={240} height={240} />
            </div>
            <figcaption className="muted tiny">{ex.label}</figcaption>
          </figure>
        ))}
      </div>
      <p className="muted tiny">
        Attribution: Pawłowska et al. 2024, BrEaST / TCIA, CC BY 4.0. BUSI silhouettes omit source
        pixels (Al-Dhabyani et al. 2020).
      </p>

      <h2>Try it</h2>
      <p>
        Open the Demo, pick a BrEaST sample, run the model, and toggle measurement overlays. Treat
        every millimeter as a research illustration. Then read the{' '}
        <Link to="/results">Results</Link> measurement notes and the{' '}
        <a href={`${BASE}report.pdf`} target="_blank" rel="noreferrer">
          research write-up PDF
        </a>
        .
      </p>

      <HowBuilt className="how-built muted tiny" />
    </article>
  )
}
