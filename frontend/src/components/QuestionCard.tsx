import type { QuestionEntry } from '../features/markets/grouping'
import { entryMembers } from '../features/markets/grouping'
import { venueLabel } from '../features/markets/discovery'
import {
  formatProbability,
  impliedProbability,
  isPriceUnreliable,
} from '../features/markets/pricing'
import type { OutcomeMarket } from '../types/market'
import { formatPrice, formatTime, formatVolume } from '../utils/format'

interface QuestionCardProps {
  entry: QuestionEntry
  selectedMarketId: string | null
  onSelect: (marketId: string) => void
}

// The probability for one named outcome's Yes side, or null when its
// price is not a probability (unreliable book, scalar payout, no price).
function rowProbability(market: OutcomeMarket): number | null {
  const yes = market.sides[0]
  return yes === undefined ? null : impliedProbability(market, yes)
}

// One multi-outcome question as a single card (Milestone 18.6b). Each
// row is one outcome; clicking it opens that outcome's detail panel.
function QuestionCard({ entry, selectedMarketId, onSelect }: QuestionCardProps) {
  const members = entryMembers(entry)
  const first = members[0]
  const time = formatTime(first.eventAt ?? first.resolvesBy)
  const containsSelected = members.some((m) => m.id === selectedMarketId)
  const showsAllNamed = entry.named.length === entry.totalNamed

  // Decision 5, refined by the 18.6a data: show the sum only when every
  // listed outcome has a usable price AND the whole question is visible.
  // It is "listed" outcomes: a tournament's fallback also covers every
  // unlisted participant, so listed outcomes need not reach 100%.
  const probabilities = entry.named.map(rowProbability)
  const sum =
    showsAllNamed &&
    probabilities.length > 0 &&
    probabilities.every((p) => p !== null)
      ? probabilities.reduce<number>((total, p) => total + (p ?? 0), 0)
      : null

  const volumes = members
    .map((m) => m.volume24h)
    .filter((v): v is number => v !== null)
  const volume =
    volumes.length > 0 ? volumes.reduce((total, v) => total + v, 0) : null

  return (
    <article
      className={
        containsSelected ? 'question-card question-card--selected' : 'question-card'
      }
    >
      <div className="question-card-header">
        <span className="market-status">
          Question · {entry.totalNamed} outcomes
        </span>
        <h3>{entry.title}</h3>
        <p className="question-card-meta">
          {time?.utc ?? 'No date'} · {venueLabel(first.venue)}
        </p>
      </div>

      {!showsAllNamed && (
        <p className="question-card-match">
          {entry.named.length} of {entry.totalNamed} outcomes match
        </p>
      )}

      <ul className="question-card-rows">
        {entry.named.map((market) => {
          const probability = rowProbability(market)
          const selected = market.id === selectedMarketId
          const unreliable = isPriceUnreliable(market)
          const classes = ['question-row']
          if (unreliable) classes.push('question-row--unreliable')
          if (selected) classes.push('question-row--selected')

          return (
            <li key={market.id}>
              <button
                type="button"
                className={classes.join(' ')}
                aria-pressed={selected}
                onClick={() => onSelect(market.id)}
              >
                <span className="question-row-label">
                  {market.parent?.outcomeLabel ?? market.question}
                </span>
                <strong>
                  {probability !== null
                    ? formatProbability(probability)
                    : formatPrice(market.sides[0]?.price ?? null)}
                </strong>
              </button>
            </li>
          )
        })}
      </ul>

      {sum !== null && (
        <p className="question-card-sum">
          Listed outcomes sum to {formatProbability(sum)} · the fallback
          covers everything else
        </p>
      )}

      {entry.fallback !== null && (
        <button
          type="button"
          className={
            entry.fallback.id === selectedMarketId
              ? 'question-card-fallback question-card-fallback--selected'
              : 'question-card-fallback'
          }
          aria-pressed={entry.fallback.id === selectedMarketId}
          onClick={() => {
            if (entry.fallback !== null) onSelect(entry.fallback.id)
          }}
        >
          Fallback {formatPrice(entry.fallback.sides[0]?.price ?? null)}
          {isPriceUnreliable(entry.fallback) && ' · no reliable price'}
        </button>
      )}

      <p className="market-card-volume">24h vol {formatVolume(volume)}</p>
    </article>
  )
}

export default QuestionCard