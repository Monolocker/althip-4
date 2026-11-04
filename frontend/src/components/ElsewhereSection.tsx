import { useElsewhere } from '../api/queries'
import {
  formatChange,
  formatProbability,
  pricesAreProbabilities,
} from '../features/markets/pricing'
import type { OutcomeMarket } from '../types/market'
import type { ElsewhereEntry, Venue, VenueQuote } from '../types/venue'
import { formatPrice, formatTime } from '../utils/format'

const VENUE_NAMES: Record<Venue, string> = {
  polymarket: 'Polymarket',
  kalshi: 'Kalshi',
}

// A quote's single reference price: the middle of its bid and ask when
// both exist (comparable with our mid), else the venue's own price.
function quoteMid(quote: VenueQuote): number | null {
  if (quote.bid !== null && quote.ask !== null) {
    return (quote.bid + quote.ask) / 2
  }
  return quote.price
}

interface EntryProps {
  entry: ElsewhereEntry
  ourPrice: number | null
  formatValue: (value: number) => string
}

function ElsewhereRow({ entry, ourPrice, formatValue }: EntryProps) {
  const { link, quote, error } = entry
  const theirs = quote !== null ? quoteMid(quote) : null
  const difference = theirs !== null && ourPrice !== null ? theirs - ourPrice : null
  const show = (value: number | null) => (value !== null ? formatValue(value) : '—')

  return (
    <li className="elsewhere-row">
      <div className="elsewhere-header">
        <strong>{VENUE_NAMES[link.venue]}</strong>
        <span className={`match-badge match-badge--${link.matchLevel}`}>
          {link.matchLevel === 'identical' ? 'Identical rules' : 'Comparable'}
        </span>
      </div>

      {quote === null ? (
        <p className="detail-note detail-note--error">
          {error ?? 'No quote available'}
        </p>
      ) : (
        <>
          <p className="elsewhere-title">{quote.title}</p>
          <p className="elsewhere-prices">
            <span>
              There <strong>{show(theirs)}</strong>{' '}
              <span className="elsewhere-muted">
                (bid {show(quote.bid)} / ask {show(quote.ask)})
              </span>
            </span>
            <span>
              Here <strong>{show(ourPrice)}</strong>
            </span>
            {difference !== null && (
              <span className="elsewhere-muted">
                difference {formatChange(difference)}
              </span>
            )}
          </p>
          <p className="elsewhere-muted">
            Quoted {formatTime(quote.fetchedAt)?.utc ?? '—'}
            {quote.closesAt !== null &&
              ` · closes ${formatTime(quote.closesAt)?.utc ?? '—'}`}
          </p>
        </>
      )}

      {link.note !== '' && <p className="elsewhere-note">⚠ {link.note}</p>}
    </li>
  )
}

interface ElsewhereSectionProps {
  market: OutcomeMarket
}

// Confirmed links to the same event on other venues, with live prices
// (Milestone 22.3a). Renders nothing until a link exists: an empty
// section on every market would be noise.
function ElsewhereSection({ market }: ElsewhereSectionProps) {
  const elsewhere = useElsewhere(market.id)

  if (elsewhere.isPending || elsewhere.isError || elsewhere.data.length === 0) {
    return null
  }

  // Same unit rule as the chart (19.3): percent only when this market's
  // prices are probabilities; then the other venues' prices are too.
  const formatValue = pricesAreProbabilities(market)
    ? formatProbability
    : formatPrice

  return (
    <section className="detail-section">
      <h3>Elsewhere</h3>
      <p className="detail-note">
        The same event on other venues, linked by hand after comparing the
        rules. Prices refer to this outcome resolving Yes.
      </p>
      <ul className="elsewhere-list">
        {elsewhere.data.map((entry) => (
          <ElsewhereRow
            key={entry.link.id}
            entry={entry}
            ourPrice={market.sides[0]?.price ?? null}
            formatValue={formatValue}
          />
        ))}
      </ul>
    </section>
  )
}

export default ElsewhereSection