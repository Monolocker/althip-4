import { useSuggestions } from '../api/queries'
import { formatProbability } from '../features/markets/pricing'
import { VENUE_NAMES } from '../features/markets/venues'
import type { Suggestion, Venue } from '../types/venue'
import LinkConfirmForm from './LinkConfirmForm'

const showPrice = (value: number | null) =>
  value !== null ? formatProbability(value) : '—'

interface SuggestionCardProps {
  suggestion: Suggestion
  alreadyLinked: boolean
}

// One venue's candidate match, with everything needed to judge it:
// the outcome pairs, their prices, and the venue's full rules. Nothing
// is saved until the person confirms in LinkConfirmForm.
function SuggestionCard({ suggestion, alreadyLinked }: SuggestionCardProps) {
  const venue = VENUE_NAMES[suggestion.venue]

  return (
    <div className="suggestion">
      <div className="elsewhere-header">
        <strong>{venue}</strong>
        <span className="elsewhere-muted">{suggestion.eventTitle}</span>
      </div>

      <table className="suggestion-pairs">
        <thead>
          <tr>
            <th>Here</th>
            <th>{venue} market</th>
            <th>Bid / ask</th>
          </tr>
        </thead>
        <tbody>
          {suggestion.pairs.map((pair) => (
            <tr key={pair.marketId}>
              <td>{pair.outcomeLabel}</td>
              <td>{pair.quote.title}</td>
              <td>
                {showPrice(pair.quote.bid)} / {showPrice(pair.quote.ask)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {alreadyLinked ? (
        // 22.5: no confirm form for a venue this outcome is already
        // linked to; confirming again could only be refused (409).
        <p className="suggestion-linked">
          ✓ Already linked on {venue}. To change it, remove the {venue} link
          above first.
        </p>
      ) : (
        <>
          {suggestion.unmatched.length > 0 && (
            <p className="elsewhere-muted">
              Not linked (no equivalent on {venue}): {suggestion.unmatched.join(', ')}
            </p>
          )}

          <details className="suggestion-rules">
            <summary>{venue}'s rules</summary>
            <p>{suggestion.rules}</p>
          </details>
          <p className="detail-note">
            Compare them with this market's resolution rules below before
            confirming: especially what happens if the match is postponed or
            cancelled.
          </p>

          <LinkConfirmForm
            venue={suggestion.venue}
            links={suggestion.pairs.map((pair) => ({
              marketId: pair.marketId,
              externalId: pair.quote.externalId,
            }))}
          />
        </>
      )}
    </div>
  )
}

interface SuggestionsPanelProps {
  questionId: string
  // Venues this outcome already has a confirmed link to.
  linkedVenues: Venue[]
  onClose: () => void
}

// "Find on other venues" (Milestone 22.3b): candidate matches for this
// football question, searched once on demand.
function SuggestionsPanel({ questionId, linkedVenues, onClose }: SuggestionsPanelProps) {
  const suggestions = useSuggestions(questionId, true)

  let body
  if (suggestions.isPending) {
    body = (
      <p className="detail-note">
        Searching Polymarket and Kalshi… (the first search can take several
        seconds while Kalshi's series list loads)
      </p>
    )
  } else if (suggestions.isError) {
    body = (
      <p className="detail-note detail-note--error">
        Search failed: {suggestions.error.message}{' '}
        <button type="button" className="side-toggle-button" onClick={() => suggestions.refetch()}>
          Try again
        </button>
      </p>
    )
  } else if (suggestions.data.length === 0) {
    body = <p className="detail-note">No matching event found on Polymarket or Kalshi.</p>
  } else {
    body = suggestions.data.map((suggestion) => (
      <SuggestionCard
        key={suggestion.venue}
        suggestion={suggestion}
        alreadyLinked={linkedVenues.includes(suggestion.venue)}
      />
    ))
  }

  return (
    <div className="suggestions-panel">
      <div className="elsewhere-header">
        <strong>Suggested matches</strong>
        <button type="button" className="side-toggle-button" onClick={onClose}>
          Close
        </button>
      </div>
      {body}
    </div>
  )
}

export default SuggestionsPanel