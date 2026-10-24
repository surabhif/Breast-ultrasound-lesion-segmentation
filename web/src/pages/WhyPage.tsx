import { Link } from 'react-router-dom'
import HowBuilt from '../components/HowBuilt'
import SurabhiNameLink from '../components/SurabhiNameLink'

/**
 * DRAFT page for Surabhi to review and edit.
 * Editor prompts live only in docs/WHY_PAGE_NOTES.md — never on this page.
 */
export default function WhyPage() {
  return (
    <article className="panel prose fade-in">
      <header className="page-intro">
        <p className="landing-eyebrow">Personal note · draft</p>
        <h1>Why I built this</h1>
        <p>
          A short first-person note from <SurabhiNameLink /> about this research demo.
        </p>
      </header>

      <p>
        I am a high-school senior in Georgia. I want to study surgical oncology. I built this
        project to practice a real imaging research question on public breast ultrasound: can a
        small program outline a lump in the browser, and do the published scores stay honest when
        near-copies or measurement marks leak across splits?
      </p>
      <p>
        Surgery and imaging both ask careful questions about what is on the screen and what it
        might mean. This demo is not surgery training. It is a student research site that shows
        outlines, scores, and limits in plain view.
      </p>
      <p>
        I used AI tools to help write code, analysis text, and the walkthrough video. The research
        questions, reading of the numbers, and presentation choices are mine to own and revise.
      </p>
      <p>
        <strong>Educational only. Not for clinical use.</strong> Do not use this site for
        diagnosis or care decisions.
      </p>

      <p>
        More context: <Link to="/about">About</Link> · <Link to="/portfolio">Portfolio</Link> ·{' '}
        <Link to="/results">Results</Link>
      </p>

      <HowBuilt />
    </article>
  )
}
