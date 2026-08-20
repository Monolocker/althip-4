import type { OutcomeMarket } from "../types/market"

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
        <h2>{market.question}</h2>
  
        <p>Status: {market.status}</p>
        <p>Closes: {market.closesAt}</p>
  
        <div className="market-outcomes">
          {market.outcomes.map((outcome) => (
            <div key={outcome.side}>
              <strong>{outcome.side}</strong>: {outcome.price}
            </div>
          ))}
        </div>
  
        <button
          type="button"
          onClick={() => onSelect(market.id)}
        >
          {isSelected ? 'Selected' : 'View details'}
        </button>
      </article>
    )
  }
  
  export default MarketCard
