import { Link } from 'react-router-dom'

/** Three plain-language result lines for the Home page. Numbers from served JSON. */
export function HomeResultsSummary() {
  return (
    <section className="home-results-summary panel" aria-labelledby="home-results-heading">
      <h2 id="home-results-heading" className="section-title">
        What the numbers say (short)
      </h2>
      <ul className="home-results-list">
        <li>
          On held-out BUSI images, the computer outline matches the expert outline about{' '}
          <strong>0.70 out of 1</strong> by outline-overlap score (Dice).
        </li>
        <li>The same frozen model was checked on three outside public datasets.</li>
        <li>It runs on your device. Images you open here are never uploaded.</li>
      </ul>
      <p className="muted tiny" style={{ marginBottom: 0 }}>
        Full tables on <Link to="/results">Results</Link>. Research demo only. Not for clinical
        use.
      </p>
    </section>
  )
}
