import type { OutcomeMarket } from "../types/market"
import MarketCard from "./MarketCard"

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
      <section className="market-list">
        {markets.map((market) => (
          <MarketCard
            key={market.id}
            market={market}
            isSelected={market.id === selectedMarketId}
            onSelect={onSelect}
          />
        ))}
      </section>
    )
  }
  
  export default MarketList