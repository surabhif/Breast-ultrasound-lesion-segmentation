/** Shared §8.5 honesty credit — keep wording consistent across the site. */

export const HOW_BUILT_STATEMENT =
  'How this was built: The code, analysis scripts, and most site and report text were produced with AI coding tools (Cursor). Surabhi Fadnavis owns the research questions, interpretation, presentation choices, and final review. This is a high-school research project — not clinician-reviewed and not for clinical use.'

type Props = {
  as?: 'p' | 'div'
  className?: string
  id?: string
}

export default function HowBuilt({ as = 'p', className = 'how-built', id }: Props) {
  const Tag = as
  return (
    <Tag className={className} id={id}>
      {HOW_BUILT_STATEMENT}
    </Tag>
  )
}
