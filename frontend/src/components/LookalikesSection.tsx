import { venueLabel } from '../features/markets/discovery'
import { humanizeSpecKey } from '../features/markets/lookalikes'
import type { Lookalike } from '../types/market'

interface LookalikesSectionProps {
  lookalikes: Lookalike[]
  onSelectMarket: (marketId: string) => void
}

// "Similar markets, different rules" (Milestone 20.3, decision 2). Each
// lookalike is shown as a comparison: what the OTHER market says, next
// to what THIS market says, for every field that differs.
function LookalikesSection({ lookalikes, onSelectMarket }: LookalikesSectionProps) {
  if (lookalikes.length === 0) {
    return null
  }

  return (
    <section className="detail-section lookalikes">
      <h3>Similar markets, different rules</h3>
      <p className="detail-note">
        These markets share this title but settle on different terms, so
        their prices are not directly comparable.
      </p>

      <ul className="lookalike-list">
        {lookalikes.map((lookalike) => (
          <li key={lookalike.marketId} className="lookalike">
            <div className="lookalike-header">
              <strong>
                {venueLabel(lookalike.venue)} · market {lookalike.marketId}
              </strong>
              <button
                type="button"
                className="side-toggle-button"
                onClick={() => onSelectMarket(lookalike.marketId)}
              >
                Open
              </button>
            </div>
            {lookalike.differences.map((difference) => (
              <p key={difference.key} className="lookalike-difference">
                <span className="lookalike-key">
                  {humanizeSpecKey(difference.key)}:
                </span>{' '}
                {difference.otherValue}
                <span className="time-local">
                  this market: {difference.thisValue}
                </span>
              </p>
            ))}
          </li>
        ))}
      </ul>
    </section>
  )
}

export default LookalikesSection