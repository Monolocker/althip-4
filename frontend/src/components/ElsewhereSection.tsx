import { useState } from 'react'
import { useDeleteLink, useElsewhere } from '../api/queries'
import {
  formatChange,
  formatProbability,
  pricesAreProbabilities,
} from '../features/markets/pricing'
import { VENUE_NAMES } from '../features/markets/venues'
import type { OutcomeMarket } from '../types/market'
import type { ElsewhereEntry, VenueQuote } from '../types/venue'
import { formatPrice, formatTime } from '../utils/format'
import ManualLinkPanel from './ManualLinkPanel'
import SuggestionsPanel from './SuggestionsPanel'

// A quote's single reference price: the middle of its bid and ask when
// both exist (comparable with our mid), else the venue's own price.
function quoteMid(quote: VenueQuote): number | null {
  if (quote.bid !== null && quote.ask !== null) {
    return (quote.bid + quote.ask) / 2
  }
  return quote.price
}

// Suggestions cover Hyperliquid's football match questions only
// (22.2, decision 3): "Competition: Team A v Team B". Every other
// market is linked by hand (22.5).
function canSuggest(market: OutcomeMarket): boolean {
  return (
    market.parent !== null &&
    market.category === 'sports' &&
    (market.parent.title ?? '').includes(' v ')
  )
}

interface EntryProps {
  entry: ElsewhereEntry
  ourPrice: number | null
  formatValue: (value: number) => string
}

function ElsewhereRow({ entry, ourPrice, formatValue }: EntryProps) {
  const { link, quote, error } = entry
  const remove = useDeleteLink()
  const theirs = quote !== null ? quoteMid(quote) : null
  const difference = theirs !== null && ourPrice !== null ? theirs - ourPrice : null
  const show = (value: number | null) => (value !== null ? formatValue(value) : '—')

  function handleRemove() {
    // window.confirm: a deliberate second step before deleting data
    // that a person curated by hand.
    if (window.confirm(`Remove the ${VENUE_NAMES[link.venue]} link for this outcome?`)) {
      remove.mutate(link.id)
    }
  }

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

      <div className="elsewhere-actions">
        {remove.isError && (
          <span className="detail-note--error">{remove.error.message}</span>
        )}
        <button
          type="button"
          className="elsewhere-remove"
          disabled={remove.isPending}
          onClick={handleRemove}
        >
          {remove.isPending ? 'Removing…' : 'Remove link'}
        </button>
      </div>
    </li>
  )
}

// Which linking panel is open under the list, if any.
type OpenPanel = 'none' | 'suggestions' | 'manual'

interface ElsewhereSectionProps {
  market: OutcomeMarket
}

// Confirmed links to the same event on other venues, with live prices
// (22.3a), plus two ways to create them: suggestions for football
// matches (22.3b) and manual linking for everything else (22.5).
function ElsewhereSection({ market }: ElsewhereSectionProps) {
  const elsewhere = useElsewhere(market.id)
  const [panel, setPanel] = useState<OpenPanel>('none')
  const entries = elsewhere.data ?? []
  const isOpen = market.status === 'open'

  // A settled market cannot gain links; show the section only if it
  // already has some.
  if (!isOpen && entries.length === 0) {
    return null
  }

  // Same unit rule as the chart (19.3): percent only when this market's
  // prices are probabilities; then the other venues' prices are too.
  const formatValue = pricesAreProbabilities(market)
    ? formatProbability
    : formatPrice
  const linkedVenues = entries.map((entry) => entry.link.venue)

  return (
    <section className="detail-section">
      <div className="section-heading">
        <h3>Elsewhere</h3>
        {isOpen && panel === 'none' && (
          <div className="side-toggle">
            {canSuggest(market) && (
              <button
                type="button"
                className="side-toggle-button"
                onClick={() => setPanel('suggestions')}
              >
                Find on other venues
              </button>
            )}
            <button
              type="button"
              className="side-toggle-button"
              onClick={() => setPanel('manual')}
            >
              Link manually
            </button>
          </div>
        )}
      </div>

      {entries.length > 0 ? (
        <>
          <p className="detail-note">
            The same event on other venues, linked by hand after comparing
            the rules. Prices refer to this outcome resolving Yes.
          </p>
          <ul className="elsewhere-list">
            {entries.map((entry) => (
              <ElsewhereRow
                key={entry.link.id}
                entry={entry}
                ourPrice={market.sides[0]?.price ?? null}
                formatValue={formatValue}
              />
            ))}
          </ul>
        </>
      ) : (
        <p className="detail-note">No linked markets on other venues yet.</p>
      )}

      {panel === 'suggestions' && market.parent !== null && (
        <SuggestionsPanel
          questionId={market.parent.id}
          linkedVenues={linkedVenues}
          onClose={() => setPanel('none')}
        />
      )}
      {panel === 'manual' && (
        <ManualLinkPanel
          marketId={market.id}
          outcomeLabel={market.parent?.outcomeLabel ?? market.question}
          linkedVenues={linkedVenues}
          onClose={() => setPanel('none')}
        />
      )}
    </section>
  )
}

export default ElsewhereSection