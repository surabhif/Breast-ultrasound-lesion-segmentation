import { Link } from 'react-router-dom'
import HowBuilt from '../components/HowBuilt'

/**
 * C1 — plain-language BI-RADS ultrasound context.
 * Verified sources are cited; anything uncertain is marked.
 */

const CATEGORIES = [
  {
    code: '0',
    name: 'Incomplete',
    meaning:
      'More imaging or information is needed before a final assessment can be given.',
  },
  {
    code: '1',
    name: 'Negative',
    meaning: 'No finding that warrants a special note; routine follow-up as appropriate.',
  },
  {
    code: '2',
    name: 'Benign',
    meaning:
      'A finding that is confidently benign (for example a simple cyst). Still not “cancer ruled out forever,” but no biopsy for that finding alone.',
  },
  {
    code: '3',
    name: 'Probably benign',
    meaning:
      'Likelihood of malignancy is very low (classically under about 2%). Short-interval follow-up is often recommended instead of immediate biopsy.',
  },
  {
    code: '4',
    name: 'Suspicious',
    meaning:
      'Tissue diagnosis is warranted. Subdivisions 4A / 4B / 4C convey increasing (but still not near-certain) suspicion.',
  },
  {
    code: '5',
    name: 'Highly suggestive of malignancy',
    meaning:
      'Findings with a very high likelihood of cancer (classically ≥95%). Biopsy is appropriate; imaging alone still is not a diagnosis.',
  },
  {
    code: '6',
    name: 'Known biopsy-proven malignancy',
    meaning:
      'Cancer already confirmed by tissue sampling; used while planning or monitoring treatment imaging.',
  },
] as const

const DESCRIPTORS = [
  {
    group: 'Shape',
    items: 'oval, round, irregular',
  },
  {
    group: 'Orientation',
    items: 'parallel (“taller than wide” is more concerning when not parallel)',
  },
  {
    group: 'Margin',
    items: 'circumscribed vs not circumscribed (indistinct, angular, microlobulated, spiculated)',
  },
  {
    group: 'Echo pattern',
    items: 'anechoic, hyperechoic, complex cystic and solid, hypoechoic, isoechoic, heterogeneous',
  },
  {
    group: 'Posterior features',
    items: 'none, enhancement, shadowing, or combined',
  },
] as const

export default function BiradsPage() {
  return (
    <article className="panel prose fade-in">
      <header className="page-intro">
        <p className="landing-eyebrow">Clinical context · educational only</p>
        <h1>BI-RADS and this model</h1>
        <p>
          What ultrasound BI-RADS categories and descriptors mean in plain language — and why this
          demo&apos;s score is <strong>not</strong> a BI-RADS assessment.
        </p>
      </header>

      <div className="callout-warn" role="note">
        <strong>Research demo — not for clinical use.</strong> Nothing on this page is medical advice.
        BI-RADS assessments are made by trained clinicians using the full ACR lexicon, clinical
        history, and often multimodality imaging. This model does not output BI-RADS categories.
      </div>

      <h2>What is BI-RADS?</h2>
      <p>
        <strong>BI-RADS</strong> (Breast Imaging Reporting and Data System) is a standardized
        reporting framework from the American College of Radiology (ACR). For ultrasound it covers
        how to describe findings (the lexicon) and how to give a final assessment category that
        ties to recommended next steps.
      </p>
      <p>
        Source (verified): ACR BI-RADS® Atlas, Breast Imaging Reporting and Data System — Ultrasound
        chapter (Mendelson EB, Böhm-Vélez M, Berg WA, et al.; 5th edition, 2013). See also the ACR
        BI-RADS overview at{' '}
        <a
          href="https://www.acr.org/Clinical-Resources/Clinical-Tools-and-Reference/Reporting-and-Data-Systems/BI-RADS"
          target="_blank"
          rel="noreferrer"
        >
          acr.org
        </a>
        .
      </p>

      <h2>Assessment categories (ultrasound)</h2>
      <p>
        These are the familiar final assessment numbers. Exact wording and auditing rules live in
        the Atlas; the table below is a student-level paraphrase.
      </p>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th scope="col">Category</th>
              <th scope="col">Name</th>
              <th scope="col">Plain-language meaning</th>
            </tr>
          </thead>
          <tbody>
            {CATEGORIES.map((c) => (
              <tr key={c.code}>
                <td>
                  <strong>{c.code}</strong>
                </td>
                <td>{c.name}</td>
                <td>{c.meaning}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="muted tiny">
        Likelihood ranges quoted for categories 3 and 5 follow the widely cited BI-RADS guidance
        summarized in peer-reviewed reviews (e.g. Lee et al., Ultrasonography 2017 — PMC5207351).
        Always prefer the current Atlas text for clinical work.
      </p>

      <h2>Mass descriptors radiologists use</h2>
      <p>
        Before (or alongside) the category, ultrasound reports describe how a mass looks. Common
        descriptor groups from the ACR ultrasound lexicon include:
      </p>
      <ul>
        {DESCRIPTORS.map((d) => (
          <li key={d.group}>
            <strong>{d.group}:</strong> {d.items}
          </li>
        ))}
      </ul>
      <p>
        Spiculated or angular margins, irregular shape, and non-parallel orientation are examples of
        features that raise suspicion — but no single descriptor is a diagnosis by itself.
      </p>

      <h2>How this model relates — and does not</h2>
      <ul>
        <li>
          <strong>What the model outputs:</strong> a pixel lesion mask (where it thinks tissue looks
          like a lesion) and a continuous benign-vs-malignant score from an auxiliary head.
        </li>
        <li>
          <strong>What it does not output:</strong> BI-RADS categories 0–6, lexicon descriptors,
          management recommendations, or a radiology report.
        </li>
        <li>
          <strong>Why a score ≠ a BI-RADS category:</strong> BI-RADS combines lexicon features,
          clinical context, and (often) other imaging. A single neural-net probability is a
          different kind of number trained on public research labels — not calibrated to BI-RADS
          likelihood bins, and not reviewed by a radiologist.
        </li>
        <li>
          <strong>Training labels:</strong> BUSI uses folder labels (benign / malignant / normal),
          not BI-RADS assessments. External sets may carry BI-RADS metadata for exploration, but
          this served model was not trained to predict those codes.
        </li>
      </ul>
      <p>
        Try the{' '}
        <Link to="/demo">in-browser demo</Link> to see masks and scores, then read the{' '}
        <Link to="/model-card">model card</Link> for limitations. For size/margin research framing,
        see the <Link to="/surgeons-view">surgeon&apos;s-view</Link> page.
      </p>

      <h2>Unverified / out of scope</h2>
      <ul>
        <li>
          We have <strong>not</strong> independently audited every figure in the commercial ACR
          Atlas PDF; category meanings above are paraphrased from ACR public materials and
          peer-reviewed summaries.
        </li>
        <li>
          ACR BI-RADS® v2025 / forthcoming atlas updates (e.g. new ultrasound non-mass lesion
          language discussed in recent reviews) are <strong>not</strong> fully reflected here —
          treat that as evolving and check the current ACR release for clinical practice.
        </li>
        <li>No clinician reviewed this page (owner decision: no clinician involvement).</li>
      </ul>

      <h2>References</h2>
      <ol className="refs">
        <li>
          Mendelson EB, Böhm-Vélez M, Berg WA, et al. ACR BI-RADS® Ultrasound. In: ACR BI-RADS®
          Atlas, Breast Imaging Reporting and Data System. Reston, VA: American College of
          Radiology; 2013.
        </li>
        <li>
          American College of Radiology. Breast Imaging Reporting &amp; Data System (BI-RADS®).{' '}
          <a
            href="https://www.acr.org/Clinical-Resources/Clinical-Tools-and-Reference/Reporting-and-Data-Systems/BI-RADS"
            target="_blank"
            rel="noreferrer"
          >
            https://www.acr.org/.../BI-RADS
          </a>
        </li>
        <li>
          Lee J, et al. Practical and illustrated summary of updated BI-RADS for ultrasonography.
          Ultrasonography. 2017. PMC5207351.
        </li>
      </ol>

      <HowBuilt className="how-built muted tiny" />
    </article>
  )
}
