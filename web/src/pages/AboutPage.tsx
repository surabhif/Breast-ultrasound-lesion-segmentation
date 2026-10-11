import { Link } from 'react-router-dom'
import HowBuilt from '../components/HowBuilt'
import { SITE } from '../lib/constants'
import { PLAIN_ABSTRACT } from '../lib/plainAbstract'

const BASE = import.meta.env.BASE_URL

const CITE_APA = `Fadnavis, S. (2026). Breast ultrasound lesion segmentation research demo (Version 1.0.0) [Computer software]. Zenodo. ${SITE.doiUrl}`

const CITE_BIBTEX = `@software{fadnavis_busi_lesion_seg_2026,
  author  = {Fadnavis, Surabhi},
  title   = {Breast Ultrasound Lesion Segmentation Research Demo},
  year    = {2026},
  version = {1.0.0},
  url     = {${SITE.githubUrl}},
  doi     = {${SITE.doi}},
  note    = {Research demo, not for clinical use}
}`

export default function AboutPage() {
  return (
    <article className="panel prose fade-in">
      <header className="page-intro">
        <h1>About</h1>
        <p>Why this project exists, how it was built, and how to cite it.</p>
      </header>

      <h2>Why this project</h2>
      <p>
        Breast ultrasound helps describe masses found on a mammogram or exam, especially in dense
        breasts. Outlining a lump and estimating whether it looks more harmless or cancerous is a
        common research task. Published scores on public datasets can look too good when
        near-identical frames or burned-in measurement marks leak into both training and testing.
        This demo shows that gap in plain view.
      </p>
      <p>
        For lexicon context see <Link to="/bi-rads">BI-RADS</Link>. For size and margin research
        framing see the <Link to="/surgeons-view">surgeon&apos;s-view</Link> page. More projects:{' '}
        <Link to="/portfolio">portfolio</Link>.
      </p>

      <h2>Research demo disclaimer</h2>
      <p>
        <strong>Not for clinical use.</strong> This is an educational high-school research project.
        Do not use it for diagnosis, triage, or screening. Model outputs can be wrong, biased, or
        driven by dataset quirks.
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
          About one minute, with captions. No voiceover. Storyboard:{' '}
          <a href={`${SITE.githubUrl}/blob/main/docs/VIDEO_SCRIPT.md`} target="_blank" rel="noreferrer">
            docs/VIDEO_SCRIPT.md
          </a>
          .
        </figcaption>
      </figure>

      <h2>Research write-up</h2>
      <p>{PLAIN_ABSTRACT}</p>
      <p>
        A site-only research report (not a journal submission). Numbers come from committed results
        JSON:
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
        2020): about 780 PNG ultrasound images labeled harmless, cancerous, or normal, each with an
        expert outline (some lumps have multiple mask files that we merge). BUSI does{' '}
        <em>not</em> provide patient IDs, so true patient-level splits are impossible. We keep
        near-identical photo groups together across splits instead.
      </p>
      <p>
        <strong>Licensing note:</strong> redistribution rights for the full BUSI archive are not
        clearly stated in a machine-readable license. This repository does <em>not</em> commit the
        full dataset. A download script fetches a public Hugging Face mirror. Only a tiny cited
        sample set ships with the web demo.
      </p>

      <h2>What this app does</h2>
      <ul>
        <li>An educational tour on breast ultrasound, BUSI labels, outlining, and data pitfalls.</li>
        <li>
          A browser detector that predicts a lump outline and a harmless vs cancerous score on
          BUSI-style ultrasound images.
        </li>
        <li>
          Results with outline-overlap scores (Dice), ranking metrics, outside checks, cleaning and
          uncertainty experiments.
        </li>
        <li>
          BI-RADS context and surgeon&apos;s-view pages that explain what the model does{' '}
          <em>not</em> claim.
        </li>
        <li>A model card on intended use, data, and limits. Educational, not clinical.</li>
      </ul>

      <h2>Method (short)</h2>
      <ul>
        <li>Network that outlines the lump, plus a second score for harmless vs cancerous</li>
        <li>Normal images trained with empty outlines (“no lump”)</li>
        <li>Careful splits that keep near-identical photos together, plus a held-aside test set</li>
        <li>Automated audit for calipers, burned-in text, and near-copies</li>
        <li>Shrunk model file so inference runs fully in the browser</li>
      </ul>
      <details className="tech-details">
        <summary>Technical details</summary>
        <p>
          Architecture: ResNet-18 U-Net with an auxiliary classification head. Training uses grouped
          stratified 5-fold cross-validation. The browser artifact is an ONNX file run with
          onnxruntime-web.
        </p>
      </details>
      <p>
        For a student-friendly walkthrough of every design choice, see{' '}
        <a href={`${SITE.githubUrl}/blob/main/docs/HOW_IT_WORKS.md`}>docs/HOW_IT_WORKS.md</a>.
      </p>

      <h2 id="cite">How to cite</h2>
      <p>
        Suggested citation (DOI:{' '}
        <a href={SITE.doiUrl} target="_blank" rel="noreferrer">
          {SITE.doi}
        </a>
        ):
      </p>
      <pre className="cite-block" tabIndex={0}>
        {CITE_APA}
      </pre>
      <p>BibTeX:</p>
      <pre className="cite-block" tabIndex={0}>
        {CITE_BIBTEX}
      </pre>
      <p className="muted tiny">
        Machine-readable: <code>CITATION.cff</code> in the repository root. Zenodo version DOI:{' '}
        <a href={SITE.doiUrl} target="_blank" rel="noreferrer">
          {SITE.doiUrl}
        </a>
        .
      </p>
      <p>
        Dataset: Al-Dhabyani W, Gomaa M, Khaled H, Fahmy A. Dataset of breast ultrasound images.
        Data in Brief. 2020;28:104863. https://doi.org/10.1016/j.dib.2019.104863
      </p>

      <h2 id="privacy">Privacy</h2>
      <p>
        This site uses <strong>no analytics and no cookies</strong>. Images you open in the Demo are
        processed <strong>in the browser only</strong>. Nothing you upload is sent to a project
        server.
      </p>

      <h2>Credits</h2>
      <HowBuilt />
      <p className="muted tiny">
        Personal info on this site is limited to name and “high-school senior, Georgia.” No school
        name, photo, email, or personal contact is published.
      </p>
      <p className="muted tiny">MIT license for code. BUSI images remain under their original terms.</p>
    </article>
  )
}
