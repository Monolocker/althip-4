import type { OutcomeMarket } from '../types/market'

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
      </div>

      <div className="market-card-outcomes">
        {market.outcomes.map((outcome) => (
          <div
            className="market-card-outcome"
            key={outcome.side}
          >
            <span>{outcome.side}</span>
            <strong>{outcome.price}</strong>
          </div>
        ))}
      </div>

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