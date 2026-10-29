import { formatChange } from '../features/markets/pricing'

interface ChangeBadgeProps {
  change: number // price units; 0.054 = +5.4 pts
}

// "+5.4 pts" coloured by direction (Milestone 20.2). The sign is in the
// text too, so the colour is never the only cue.
function ChangeBadge({ change }: ChangeBadgeProps) {
  const tone = change > 0 ? 'up' : change < 0 ? 'down' : 'flat'
  return (
    <span className={`change-badge change-badge--${tone}`}>
      {formatChange(change)}
    </span>
  )
}

export default ChangeBadge