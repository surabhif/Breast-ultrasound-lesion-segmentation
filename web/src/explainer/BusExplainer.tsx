import { useCallback, useEffect, useId, useState, type KeyboardEvent } from 'react'
import { Link } from 'react-router-dom'
import { EXPLAINER_SOURCES, EXPLAINER_STEPS, type ExplainerStepId } from './steps'
import './explainer.css'

type BusExplainerProps = {
  /** When true, skip a redundant brand hero (landing page already has one). */
  compactIntro?: boolean
}

declare global {
  interface Window {
    __scrollToExplainerStep?: (index: number) => void
  }
}

function VisualPanel({ stepId }: { stepId: ExplainerStepId }) {
  if (stepId === 'ultrasound') {
    return (
      <div className="tour-visual ultrasound" aria-hidden="true">
        <div className="tour-frame">
          <div className="tour-beam" />
          <div className="tour-lesion" />
          <span className="tour-label">B-mode ultrasound</span>
        </div>
      </div>
    )
  }
  if (stepId === 'labels') {
    return (
      <div className="tour-visual labels" aria-hidden="true">
        <div className="tour-tile benign">
          <span>Harmless</span>
        </div>
        <div className="tour-tile malignant">
          <span>Cancerous</span>
        </div>
        <div className="tour-tile normal">
          <span>Normal</span>
        </div>
      </div>
    )
  }
  if (stepId === 'segmentation') {
    return (
      <div className="tour-visual segmentation" aria-hidden="true">
        <div className="tour-frame">
          <div className="tour-beam soft" />
          <div className="tour-mask" />
          <div className="tour-outline" />
          <span className="tour-label">Predicted mask</span>
        </div>
      </div>
    )
  }
  if (stepId === 'pitfalls') {
    return (
      <div className="tour-visual pitfalls" aria-hidden="true">
        <div className="tour-chip">Calipers</div>
        <div className="tour-chip">Near-copies</div>
        <div className="tour-chip">No patient IDs</div>
        <div className="tour-chip accent">Grouped splits</div>
      </div>
    )
  }
  return (
    <div className="tour-visual browser" aria-hidden="true">
      <div className="tour-progress">
        <div className="tour-progress-fill" />
      </div>
      <p className="tour-progress-caption">Model download · runs on your device</p>
      <div className="tour-frame mini">
        <div className="tour-mask" />
      </div>
    </div>
  )
}

export default function BusExplainer({ compactIntro = false }: BusExplainerProps) {
  const labelId = useId()
  const [index, setIndex] = useState(0)
  const step = EXPLAINER_STEPS[index]

  const goTo = useCallback((i: number) => {
    setIndex(Math.max(0, Math.min(EXPLAINER_STEPS.length - 1, i)))
  }, [])

  useEffect(() => {
    window.__scrollToExplainerStep = (i: number) => {
      goTo(i)
      document.getElementById('explainer')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
    return () => {
      delete window.__scrollToExplainerStep
    }
  }, [goTo])

  function onKey(e: KeyboardEvent<HTMLDivElement>) {
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
      e.preventDefault()
      goTo(index + 1)
    } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
      e.preventDefault()
      goTo(index - 1)
    }
  }

  return (
    <section
      className="bus-tour"
      aria-labelledby={labelId}
      tabIndex={0}
      onKeyDown={onKey}
    >
      {!compactIntro && (
        <header className="tour-intro">
          <p className="landing-eyebrow">Interactive explainer</p>
          <h2 id={labelId}>Educational tour</h2>
        </header>
      )}
      {compactIntro && (
        <header className="tour-intro compact">
          <p className="landing-eyebrow">Interactive explainer</p>
          <h2 id={labelId}>Educational tour</h2>
          <p className="muted">
            Five short steps on breast ultrasound, BUSI labels, segmentation, data pitfalls, and
            how this browser demo works.
          </p>
        </header>
      )}

      <div className="tour-stepper" role="tablist" aria-label="Tour steps">
        {EXPLAINER_STEPS.map((s, i) => (
          <button
            key={s.id}
            type="button"
            role="tab"
            aria-selected={i === index}
            className={`tour-step-tab${i === index ? ' active' : ''}`}
            onClick={() => goTo(i)}
          >
            <span className="tour-step-num">{i + 1}</span>
            <span className="tour-step-short">{s.shortTitle}</span>
          </button>
        ))}
      </div>

      <div className="tour-stage panel" role="tabpanel" aria-label={step.title}>
        <div className="tour-copy">
          <p className="tour-kicker">{step.kicker}</p>
          <h3>{step.title}</h3>
          <p>{step.body}</p>
          {step.callouts && (
            <ul className="tour-callouts">
              {step.callouts.map((c) => (
                <li key={c.label}>
                  <strong>{c.label}</strong>
                  <span>{c.detail}</span>
                </li>
              ))}
            </ul>
          )}
          <p className="sr-only">{step.alt}</p>
        </div>
        <VisualPanel stepId={step.id} />
      </div>

      <div className="tour-nav">
        <button
          type="button"
          className="btn secondary"
          onClick={() => goTo(index - 1)}
          disabled={index === 0}
        >
          Previous
        </button>
        <span className="muted tiny">
          Step {index + 1} of {EXPLAINER_STEPS.length}
        </span>
        {index < EXPLAINER_STEPS.length - 1 ? (
          <button type="button" className="btn" onClick={() => goTo(index + 1)}>
            Next
          </button>
        ) : (
          <Link className="btn" to="/demo">
            Try the detector
          </Link>
        )}
      </div>

      <p className="tour-sources muted tiny">
        Sources:{' '}
        {EXPLAINER_SOURCES.map((s, i) => (
          <span key={s.href}>
            {i > 0 ? ' · ' : ''}
            <a href={s.href} target="_blank" rel="noreferrer">
              {s.label}
            </a>
          </span>
        ))}
        . Educational summary only. Not clinical guidance.
      </p>
    </section>
  )
}
