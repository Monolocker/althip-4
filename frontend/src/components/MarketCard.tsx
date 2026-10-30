import type { OutcomeMarket } from '../types/market'
import { formatPrice, formatTime, formatVolume } from '../utils/format'
import { venueLabel } from '../features/markets/discovery'
import { lookalikeSummary } from '../features/markets/lookalikes'
import BookQualityNote from './BookQualityNote'
import { isPriceUnreliable, visibleChange } from '../features/markets/pricing'
import ChangeBadge from './ChangeBadge'

interface MarketCardProps {
  market: OutcomeMarket
  isSelected: boolean
  onSelect: (marketId: string) => void
}

function MarketCard({
  market,
  isSelected,
  onSelect,
}: MarketCardProps) {
  // Milestone 18.3: an unreliable book makes both sides' prices
  // meaningless (the two sides share one merged book).
  const unreliable = isPriceUnreliable(market)
  const change = visibleChange(market)
  const time = formatTime(market.eventAt ?? market.resolvesBy)

  return (
    <article
      className={
        isSelected
          ? 'market-card market-card--selected'
          : 'market-card'
      }
    >
      <div className="market-card-header">
        <span className="market-status">
          {market.status}
        </span>

        <h3>{market.question}</h3>
        <p className="question-card-meta">
          {time?.utc ?? 'No date'} · {venueLabel(market.venue)}
        </p>
        {market.lookalikes.length > 0 && (
          <p className="lookalike-warning">
            ⚠ {lookalikeSummary(market.lookalikes)}
          </p>
        )}
      </div>

      <div
        className={
          unreliable
            ? 'market-card-outcomes market-card-outcomes--unreliable'
            : 'market-card-outcomes'
        }
      >
        {market.sides.map((side) => (
          <div
            className="market-card-outcome"
            key={side.coin}
          >
            <span>{side.label}</span>
            <strong>{formatPrice(side.price)}</strong>
          </div>
        ))}
      </div>

      <BookQualityNote book={market.book} />

      <p className="market-card-volume">
        24h vol {formatVolume(market.volume24h)}
        {change !== null && (
          <>
            {' . '}
            <ChangeBadge change={change} /> 24h
          </>
        )}
      </p>

      <button
        className="market-select-button"
        type="button"
        aria-pressed={isSelected}
        onClick={() => onSelect(market.id)}
      >
        {isSelected ? 'Selected' : 'View details'}
      </button>
    </article>
  )
}

export default MarketCard