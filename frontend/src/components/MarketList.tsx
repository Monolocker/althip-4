import type { OutcomeMarket } from '../types/market'
import MarketCard from './MarketCard'

interface MarketListProps {
  markets: OutcomeMarket[]
  selectedMarketId: string | null
  onSelect: (marketId: string) => void
}

function MarketList({
  markets,
  selectedMarketId,
  onSelect,
}: MarketListProps) {
  return (
    <section
      className="market-list"
      aria-label="Outcome markets"
    >
      <div className="market-list-header">
        <h2>Markets</h2>
        <span>{markets.length}</span>
      </div>

      <div className="market-list-items">
        {markets.map((market) => (
          <MarketCard
            key={market.id}
            market={market}
            isSelected={market.id === selectedMarketId}
            onSelect={onSelect}
          />
        ))}
      </div>
    </section>
  )
}

export default MarketList