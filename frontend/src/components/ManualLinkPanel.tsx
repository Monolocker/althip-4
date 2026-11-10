import { useState } from 'react'
import { useVenueLookup } from '../api/queries'
import { formatProbability } from '../features/markets/pricing'
import { VENUE_NAMES } from '../features/markets/venues'
import type { Venue, VenueQuote } from '../types/venue'
import { formatTime } from '../utils/format'
import LinkConfirmForm from './LinkConfirmForm'

const VENUES: Venue[] = ['polymarket', 'kalshi']

const HINTS: Record<Venue, string> = {
  polymarket: 'Paste a polymarket.com link, a market id, or a few words',
  kalshi: 'Paste a kalshi.com link or a ticker (e.g. KXFED-26DEC)',
}

const showPrice = (value: number | null) =>
  value !== null ? formatProbability(value) : '—'

interface ManualLinkPanelProps {
  marketId: string
  outcomeLabel: string
  linkedVenues: Venue[]
  onClose: () => void
}

// Manual linking (Milestone 22.5): for markets the suggestions do not
// cover. The person pastes the other venue's market, the app shows what
// it found WITH its rules, and the same confirm form saves one link for
// this one outcome.
function ManualLinkPanel({ marketId, outcomeLabel, linkedVenues, onClose }: ManualLinkPanelProps) {
  const [venue, setVenue] = useState<Venue>('polymarket')
  const [text, setText] = useState('')
  // What was last looked up; null until "Look up" is pressed.
  const [reference, setReference] = useState<string | null>(null)
  const [chosen, setChosen] = useState<VenueQuote | null>(null)
  const lookup = useVenueLookup(venue, reference)
  const name = VENUE_NAMES[venue]

  function chooseVenue(next: Venue) {
    setVenue(next)
    setReference(null)
    setChosen(null)
  }

  function lookUp() {
    setChosen(null)
    setReference(text.trim() === '' ? null : text.trim())
  }

  let results = null
  if (linkedVenues.includes(venue)) {
    results = (
      <p className="suggestion-linked">
        ✓ Already linked on {name}. To change it, remove the {name} link above first.
      </p>
    )
  } else if (reference !== null && lookup.isPending) {
    results = <p className="detail-note">Looking up on {name}…</p>
  } else if (lookup.isError) {
    results = (
      <p className="detail-note detail-note--error">Lookup failed: {lookup.error.message}</p>
    )
  } else if (lookup.data !== undefined && lookup.data.length === 0) {
    results = <p className="detail-note">Nothing found on {name} for that reference.</p>
  } else if (lookup.data !== undefined) {
    results = (
      <ul className="lookup-results">
        {lookup.data.map((quote) => (
          <li key={quote.externalId}>
            <label className={chosen?.externalId === quote.externalId ? 'lookup-result lookup-result--chosen' : 'lookup-result'}>
              <input
                type="radio"
                name="lookup-result"
                checked={chosen?.externalId === quote.externalId}
                onChange={() => setChosen(quote)}
              />
              <span>
                <strong>{quote.title}</strong>
                <span className="elsewhere-muted">
                  {' '}
                  · {quote.sideLabel} bid {showPrice(quote.bid)} / ask {showPrice(quote.ask)} ·{' '}
                  {quote.status}
                  {quote.closesAt !== null && ` · closes ${formatTime(quote.closesAt)?.utc}`}
                </span>
              </span>
            </label>
          </li>
        ))}
      </ul>
    )
  }

  return (
    <div className="suggestions-panel">
      <div className="elsewhere-header">
        <strong>Link "{outcomeLabel}" manually</strong>
        <button type="button" className="side-toggle-button" onClick={onClose}>
          Close
        </button>
      </div>

      <div className="lookup-controls">
        <div className="side-toggle" role="group" aria-label="Venue">
          {VENUES.map((option) => (
            <button
              key={option}
              type="button"
              className={
                option === venue
                  ? 'side-toggle-button side-toggle-button--active'
                  : 'side-toggle-button'
              }
              aria-pressed={option === venue}
              onClick={() => chooseVenue(option)}
            >
              {VENUE_NAMES[option]}
            </button>
          ))}
        </div>
        <input
          type="text"
          className="lookup-input"
          value={text}
          placeholder={HINTS[venue]}
          aria-label={`${name} market reference`}
          onChange={(event) => setText(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter') lookUp()
          }}
        />
        <button type="button" className="side-toggle-button" onClick={lookUp}>
          Look up
        </button>
      </div>

      {results}

      {chosen !== null && !linkedVenues.includes(venue) && (
        <div className="suggestion">
          <p className="detail-note">
            Linking <strong>{outcomeLabel}</strong> (this outcome resolving Yes) to{' '}
            <strong>{chosen.title}</strong> ({chosen.sideLabel}) on {name}. Make sure
            both describe the SAME outcome.
          </p>
          <details className="suggestion-rules" open>
            <summary>{name}'s rules</summary>
            <p>{chosen.rules || 'No rules text was returned for this market.'}</p>
          </details>
          {/* key: a different chosen market gets a fresh form (level, note). */}
          <LinkConfirmForm
            key={chosen.externalId}
            venue={venue}
            links={[{ marketId, externalId: chosen.externalId }]}
          />
        </div>
      )}
    </div>
  )
}

export default ManualLinkPanel