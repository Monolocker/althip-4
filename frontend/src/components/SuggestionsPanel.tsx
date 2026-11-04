import { useState } from 'react'
import { useCreateLinks, useSuggestions } from '../api/queries'
import { formatProbability } from '../features/markets/pricing'
import type { MatchLevel, Suggestion, Venue } from '../types/venue'

const VENUE_NAMES: Record<Venue, string> = {
  polymarket: 'Polymarket',
  kalshi: 'Kalshi',
}

const showPrice = (value: number | null) =>
  value !== null ? formatProbability(value) : '—'

interface SuggestionCardProps {
  suggestion: Suggestion
}

// One venue's candidate match, with everything needed to judge it:
// the outcome pairs, their prices, and the venue's full rules. Nothing
// is saved until the person picks a level (and, for "comparable",
// writes down how the rules differ) and confirms.
function SuggestionCard({ suggestion }: SuggestionCardProps) {
  const [level, setLevel] = useState<MatchLevel>('comparable')
  const [note, setNote] = useState('')
  const create = useCreateLinks()
  const venue = VENUE_NAMES[suggestion.venue]
  // Decision 2 (22.2), checked here for a clear message; the backend
  // and the database enforce it too.
  const needsNote = level === 'comparable' && note.trim() === ''

  if (create.isSuccess) {
    return (
      <div className="suggestion suggestion--done">
        ✓ Linked {create.data.length} outcomes on {venue}.
      </div>
    )
  }

  function confirm() {
    create.mutate({
      venue: suggestion.venue,
      matchLevel: level,
      note: note.trim(),
      links: suggestion.pairs.map((pair) => ({
        marketId: pair.marketId,
        externalId: pair.quote.externalId,
      })),
    })
  }

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

      <fieldset className="suggestion-level">
        <legend>How do the rules compare?</legend>
        <label>
          <input
            type="radio"
            name={`level-${suggestion.venue}`}
            checked={level === 'comparable'}
            onChange={() => setLevel('comparable')}
          />{' '}
          Comparable: same in the normal case, different at the edges
        </label>
        <label>
          <input
            type="radio"
            name={`level-${suggestion.venue}`}
            checked={level === 'identical'}
            onChange={() => setLevel('identical')}
          />{' '}
          Identical: same payout in every scenario
        </label>
      </fieldset>

      <label className="suggestion-note">
        Note{' '}
        {level === 'comparable' ? '(required: how do the rules differ?)' : '(optional)'}
        <textarea
          value={note}
          onChange={(event) => setNote(event.target.value)}
          rows={2}
          placeholder="e.g. Cancelled match: Hyperliquid's Draw resolves Yes; this venue resolves No."
        />
      </label>

      {create.isError && (
        <p className="detail-note detail-note--error">{create.error.message}</p>
      )}

      <button
        type="button"
        className="suggestion-confirm"
        disabled={needsNote || create.isPending}
        onClick={confirm}
      >
        {create.isPending
          ? 'Confirming…'
          : `Confirm ${suggestion.pairs.length} links on ${venue}`}
      </button>
    </div>
  )
}

interface SuggestionsPanelProps {
  questionId: string
  onClose: () => void
}

// "Find on other venues" (Milestone 22.3b): candidate matches for this
// football question, searched once on demand.
function SuggestionsPanel({ questionId, onClose }: SuggestionsPanelProps) {
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
      <SuggestionCard key={suggestion.venue} suggestion={suggestion} />
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