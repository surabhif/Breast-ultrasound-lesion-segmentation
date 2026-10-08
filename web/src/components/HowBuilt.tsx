/** Shared §8.5 honesty credit — keep wording consistent across the site. */

export const HOW_BUILT_STATEMENT =
  'Project by Surabhi Fadnavis. The code, analysis, text, and video were produced with AI tools (Cursor).'

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
