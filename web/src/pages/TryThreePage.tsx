import { Link } from 'react-router-dom'
import samplesManifest from '../data/samples.json'
import GlossaryTerm from '../components/GlossaryTerm'
import HowBuilt from '../components/HowBuilt'
import { classLabelDisplay } from '../lib/sampleMeta'

type Sample = (typeof samplesManifest.samples)[number]

type TourCase = {
  sampleId: string
  stepLabel: string
  whatHappened: string
  gotRight: string
  gotWrong: string
}

/** On /try, benign is labeled “benign (not cancer)” rather than “harmless”. */
function tryLabelDisplay(label: string): string {
  if (label === 'benign') return 'benign (not cancer)'
  return classLabelDisplay(label)
}

const TOUR: TourCase[] = [
  {
    sampleId: 'busi-test-01',
    stepLabel: 'Case 1 · Benign (not cancer) lump',
    whatHappened:
      'A BUSI test image labeled benign (not cancer). The expert drew a lump outline. The browser model is asked to outline the lump and give a benign-vs-cancerous score.',
    gotRight:
      'The predicted outline overlaps the expert outline a lot (Dice about 0.94 out of 1). The class score is very low, so the display leans benign (not cancer) — matching the known label.',
    gotWrong:
      'Nothing major on this sample. Still research only: a good match on one image is not a diagnosis, and other benign lumps can be harder.',
  },
  {
    sampleId: 'busi-test-03',
    stepLabel: 'Case 2 · Cancerous lump',
    whatHappened:
      'A BUSI test image labeled cancerous (malignant). The expert outlined the lump. The model predicts an outline and a class score.',
    gotRight:
      'Outline overlap is high (Dice about 0.90 out of 1). The class score is near 1, so the display leans cancerous — matching the known label.',
    gotWrong:
      'The outline is not perfect pixel-for-pixel. Real lumps have fuzzy edges, so small mismatches are common even when the overall shape looks right.',
  },
  {
    sampleId: 'busi-test-04',
    stepLabel: 'Case 3 · Normal (no lump)',
    whatHappened:
      'A BUSI test image labeled normal (no lump). The expert outline is empty. The model should ideally draw nothing.',
    gotRight:
      'The known label is clear: there is no lump to outline. Comparing against an empty expert mask makes mistakes easy to see.',
    gotWrong:
      'The model still drew a non-empty outline (Dice near 0 when the expert is empty). The high “cancerous” score is not meaningful here — normal (no lump) is not the same as benign (not cancer). False outlines on normal scans are a known weak spot.',
  },
]

function findSample(id: string): Sample | undefined {
  return samplesManifest.samples.find((s) => s.id === id)
}

export default function TryThreePage() {
  const base = import.meta.env.BASE_URL

  return (
    <div className="fade-in try-three">
      <header className="page-intro">
        <p className="eyebrow">Guided tour</p>
        <h1>Try 3 cases</h1>
        <p>
          Three public BUSI test samples — one benign (not cancer) lump, one cancerous lump, and one{' '}
          <GlossaryTerm term="ultrasound">ultrasound</GlossaryTerm> with no lump. Each card says
          what the model got right and wrong using the saved browser-model scores. Research demo
          only. Not for clinical use.
        </p>
        <p className="muted tiny">
          Tip: tap underlined glossary words (like{' '}
          <GlossaryTerm term="dice">Dice</GlossaryTerm>) for a short definition.
        </p>
      </header>

      <ol className="try-three-list">
        {TOUR.map((item, index) => {
          const sample = findSample(item.sampleId)
          if (!sample) return null
          const dice = sample.reported_dice_int8
          const cls = sample.reported_cls_prob_int8
          return (
            <li key={sample.id} className="panel try-three-card">
              <div className="try-three-card-head">
                <span className="try-three-step">{index + 1} / 3</span>
                <h2 className="section-title">{item.stepLabel}</h2>
              </div>
              <div className="try-three-grid">
                <figure className="try-three-figure">
                  <img
                    src={`${base}${sample.src}`}
                    alt={`BUSI sample ${sample.id}: ${tryLabelDisplay(sample.label)} ultrasound`}
                    width={320}
                    height={320}
                    loading={index === 0 ? 'eager' : 'lazy'}
                  />
                  <figcaption className="muted tiny">
                    Known label: {tryLabelDisplay(sample.label)}. Public BUSI test sample.
                  </figcaption>
                </figure>
                <div className="try-three-copy">
                  <p>{item.whatHappened}</p>
                  <p>
                    <strong>Saved scores:</strong> outline-overlap (
                    <GlossaryTerm term="dice">Dice</GlossaryTerm>){' '}
                    {dice != null ? dice.toFixed(2) : '—'} out of 1 · class score{' '}
                    {cls != null ? `${(cls * 100).toFixed(1)}%` : '—'} toward cancerous
                  </p>
                  <p>
                    <strong>Got right:</strong> {item.gotRight}
                  </p>
                  <p>
                    <strong>Got wrong / watch out:</strong> {item.gotWrong}
                  </p>
                  <div className="landing-actions">
                    <Link className="btn" to={`/demo?sample=${sample.id}`}>
                      Open in Demo
                    </Link>
                  </div>
                </div>
              </div>
            </li>
          )
        })}
      </ol>

      <section className="panel" style={{ marginTop: '1rem' }}>
        <h2 className="section-title">Words used on this site</h2>
        <p className="muted tiny" style={{ marginBottom: '0.75rem' }}>
          Hover or tap a word anywhere it appears underlined. Full list:
        </p>
        <ul className="try-three-glossary-list">
          <li>
            <GlossaryTerm term="dice" /> — outline-overlap score
          </li>
          <li>
            <GlossaryTerm term="auc" /> — ranking score for benign (not cancer) vs cancerous
          </li>
          <li>
            <GlossaryTerm term="birads" /> — radiology reporting scale (not model output)
          </li>
          <li>
            <GlossaryTerm term="lesion" /> — lump / mass on the image
          </li>
          <li>
            <GlossaryTerm term="margin" /> — edge of a lump
          </li>
          <li>
            <GlossaryTerm term="ultrasound" /> — sound-wave imaging
          </li>
          <li>
            <GlossaryTerm term="outline" /> — pixel mask around a lump
          </li>
          <li>
            <GlossaryTerm term="threshold" /> — cut-off for display
          </li>
        </ul>
        <div className="landing-actions" style={{ marginTop: '1rem' }}>
          <Link className="btn secondary" to="/demo">
            Full Demo
          </Link>
          <Link className="btn secondary" to="/results">
            Results
          </Link>
        </div>
      </section>

      <HowBuilt className="how-built muted tiny" />
    </div>
  )
}
