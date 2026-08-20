import type { OutcomeMarket } from '../types/market'

interface MarketDetailProps {
  market: OutcomeMarket
}

function MarketDetail({ market }: MarketDetailProps) {
  return (
    <section className="market-detail">
      <h2>Market details</h2>

      <h3>{market.question}</h3>

      <p>Market ID: {market.id}</p>
      <p>Status: {market.status}</p>
      <p>Closes: {market.closesAt}</p>

      <div className="market-outcomes">
        {market.outcomes.map((outcome) => (
          <div key={outcome.side}>
            <strong>{outcome.side}</strong>: {outcome.price}
          </div>
        ))}
      </div>
    </section>
  )
}

export default MarketDetail