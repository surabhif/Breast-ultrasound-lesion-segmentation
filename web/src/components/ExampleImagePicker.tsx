import { getExampleStripSamples, EXAMPLE_STRIP_DISCLAIMER, type ExampleSample } from '../lib/exampleSamples'
import { classLabelDisplay } from '../lib/sampleMeta'

type Props = {
  selectedId: string | null
  disabled?: boolean
  onPick: (sample: ExampleSample) => void
}

/** Horizontal strip of six BUSI sample scans. One click runs the model. */
export default function ExampleImagePicker({ selectedId, disabled, onPick }: Props) {
  const samples = getExampleStripSamples()
  const base = import.meta.env.BASE_URL

  return (
    <div className="example-picker" data-testid="example-image-picker">
      <h2 className="section-title">Example scans</h2>
      <p className="muted" style={{ marginTop: 0 }}>
        Six public BUSI samples (2 normal, 2 benign, 2 malignant). Tap one to run the model.
      </p>
      <p className="muted tiny">{EXAMPLE_STRIP_DISCLAIMER}</p>
      <div
        className="example-picker-strip"
        role="listbox"
        aria-label="Example ultrasound scans"
      >
        {samples.map((sample) => {
          const selected = selectedId === sample.id
          return (
            <button
              key={sample.id}
              type="button"
              role="option"
              className={`example-picker-item${selected ? ' selected' : ''}`}
              aria-selected={selected}
              aria-label={`Run model on ${classLabelDisplay(sample.label)} sample ${sample.id}`}
              disabled={disabled}
              onClick={() => onPick(sample)}
            >
              <img
                src={`${base}${sample.src}`}
                alt=""
                width={96}
                height={96}
                loading="lazy"
              />
              <span className={`badge ${sample.label}`}>{classLabelDisplay(sample.label)}</span>
            </button>
          )
        })}
      </div>
    </div>
  )
}
