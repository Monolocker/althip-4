import type { OutcomeMarket } from "../types/market"

interface MarketCardProps {
    market: OutcomeMarket
}

function MarketCard ({ market }: MarketCardProps) {
    return (
        <article className="market-card">
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
            </article>
    )
}

export default MarketCard
