import type { OutcomeMarket } from "..types/market"
import MarketCard from "./MarketCard"

interface MarketListProps {
    markets: OutcomeMarket[]
}

function MarketList({ markets }: MarketListProps) {
    return (
      <section className="market-list">
        {markets.map((market) => (
          <MarketCard
            key={market.id}
            market={market}
          />
        ))}
      </section>
    )
  }
  
  export default MarketList