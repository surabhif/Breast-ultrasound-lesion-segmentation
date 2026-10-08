import { Link } from 'react-router-dom'
import HowBuilt from '../components/HowBuilt'
import { SITE } from '../lib/constants'

const BASE = import.meta.env.BASE_URL

const CITE_APA = `Fadnavis, S. (2026). Breast ultrasound lesion segmentation research demo (Version 1.0.0) [Computer software]. GitHub. ${SITE.githubUrl}`

const CITE_BIBTEX = `@software{fadnavis_busi_lesion_seg_2026,
  author  = {Fadnavis, Surabhi},
  title   = {Breast Ultrasound Lesion Segmentation Research Demo},
  year    = {2026},
  version = {1.0.0},
  url     = {${SITE.githubUrl}},
  note    = {Research demo, not for clinical use}
}`

export default function AboutPage() {
  return (
    <article className="panel prose fade-in">
      <header className="page-intro">
        <h1>About</h1>
        <p>Clinical motivation, dataset citation, method overview, privacy, and credits.</p>
      </header>

      <h2>Clinical motivation</h2>
      <p>
        Breast ultrasound is widely used to characterize masses found on mammography or physical
        exam, especially in dense breasts. Segmenting a lesion and estimating whether it looks more
        benign or malignant is a common research task — but published scores on public datasets can
        look better than they are when near-duplicate frames or burned-in caliper marks leak
        information. This demo explores that gap transparently.
      </p>
      <p>
        For lexicon context see <Link to="/bi-rads">BI-RADS</Link>; for size/margin research framing
        see the <Link to="/surgeons-view">surgeon&apos;s-view</Link> page. More projects:{' '}
        <Link to="/portfolio">portfolio</Link>.
      </p>

      <h2>Research demo disclaimer</h2>
      <p>
        <strong>Not for clinical use.</strong> This is an educational high-school research project.
        It must not be used for diagnosis, triage, or screening. Model outputs can be wrong, biased,
        or driven by dataset artifacts. No clinician was involved in reviewing this site.
      </p>

      <h2>Walkthrough video</h2>
      <figure className="walkthrough-embed">
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
          60–90s captioned walkthrough (no voiceover). Storyboard:{' '}
          <a href={`${SITE.githubUrl}/blob/main/docs/VIDEO_SCRIPT.md`} target="_blank" rel="noreferrer">
            docs/VIDEO_SCRIPT.md
          </a>
          .
        </figcaption>
      </figure>

      <h2>Research write-up</h2>
      <p>
        A site-only research report (not a journal submission) with numbers filled from committed
        results JSON:
      </p>
      <p className="report-link-row">
        <a className="btn" href={`${BASE}report.pdf`} target="_blank" rel="noreferrer">
          Open report.pdf
        </a>
        <Link className="btn secondary" to="/results">
          See Results
        </Link>
      </p>

      <h2>Dataset: BUSI</h2>
      <p>
        We use the Breast Ultrasound Images Dataset (BUSI) from Al-Dhabyani et al. (Data in Brief,
        2020): roughly 780 PNG ultrasound images labeled benign, malignant, or normal, each with a
        ground-truth mask (some lesions have multiple mask files that we merge). BUSI does{' '}
        <em>not</em> provide patient IDs, so true patient-level splits are impossible. We instead
        keep perceptual-hash near-duplicate groups together across splits.
      </p>
      <p>
        <strong>Licensing note:</strong> redistribution rights for the full BUSI archive are not
        clearly stated in a machine-readable license. This repository does <em>not</em> commit the
        full dataset; a download script fetches a public Hugging Face mirror. Only a tiny cited
        sample set ships with the web demo.
      </p>

      <h2>What this app does</h2>
      <ul>
        <li>
          An educational tour on breast ultrasound, BUSI labels, segmentation, and data pitfalls.
        </li>
        <li>
          An in-browser detector that predicts a lesion mask overlay and a benign-vs-malignant
          score on BUSI-style ultrasound images.
        </li>
        <li>
          Results with Dice, IoU, classification metrics, external validation, cleaning and
          uncertainty experiments.
        </li>
        <li>
          BI-RADS context and surgeon&apos;s-view pages that explain what the model does{' '}
          <em>not</em> claim.
        </li>
        <li>
          A model card documenting intended use, data, and limitations — educational, not clinical.
        </li>
      </ul>

      <h2>Method (short)</h2>
      <ul>
        <li>U-Net segmentation with an auxiliary benign-vs-malignant head</li>
        <li>Normal images trained with empty masks (“no lesion”)</li>
        <li>Grouped stratified 5-fold CV + held-out test</li>
        <li>Automated audit for calipers / burned-in text and near-duplicates</li>
        <li>Exported ONNX model for fully in-browser inference</li>
      </ul>
      <p>
        For a student-friendly walkthrough of every design choice, see{' '}
        <a href={`${SITE.githubUrl}/blob/main/docs/HOW_IT_WORKS.md`}>docs/HOW_IT_WORKS.md</a>.
      </p>

      <h2 id="cite">How to cite</h2>
      <p>Suggested citation (no DOI yet):</p>
      <pre className="cite-block" tabIndex={0}>
        {CITE_APA}
      </pre>
      <p>BibTeX:</p>
      <pre className="cite-block" tabIndex={0}>
        {CITE_BIBTEX}
      </pre>
      <p className="muted tiny">
        Machine-readable: <code>CITATION.cff</code> in the repository root.{' '}
        <strong>TODO (owner):</strong> mint a Zenodo DOI when ready — requires the owner&apos;s
        Zenodo login; agents cannot complete that step.
      </p>
      <p>
        Dataset: Al-Dhabyani W, Gomaa M, Khaled H, Fahmy A. Dataset of breast ultrasound images.
        Data in Brief. 2020;28:104863. https://doi.org/10.1016/j.dib.2019.104863
      </p>

      <h2 id="privacy">Privacy</h2>
      <p>
        This site uses <strong>no analytics and no cookies</strong>. Images you open in the Demo are
        processed <strong>in the browser only</strong> (ONNX Runtime Web / WASM). Nothing you upload
        is sent to a project server.
      </p>

      <h2>Credits</h2>
      <HowBuilt />
      <p className="muted tiny">
        Personal info on this site is limited to name and “high-school senior, Georgia.” No school
        name, photo, email, or personal contact is published (D7).
      </p>
      <p className="muted tiny">MIT license for code. BUSI images remain under their original terms.</p>
    </article>
  )
}
