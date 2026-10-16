import { SITE } from '../lib/constants'

type Props = {
  className?: string
}

/** LinkedIn profile link whose visible text is the author name. */
export default function SurabhiNameLink({ className = 'linkedin-name' }: Props) {
  return (
    <a
      href={SITE.linkedinUrl}
      target="_blank"
      rel="noopener noreferrer"
      aria-label="Surabhi Fadnavis on LinkedIn"
      className={className}
    >
      Surabhi Fadnavis
    </a>
  )
}
