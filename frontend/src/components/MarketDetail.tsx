import type { OutcomeMarket } from '../types/market'

interface MarketDetailProps {
  market: OutcomeMarket
}

function MarketDetail({ market }: MarketDetailProps) {
  return (
    <section className="market-detail">
      <header className="market-detail-header">
        <p className="section-label">Market details</p>
        <h2>{market.question}</h2>
      </header>

      <dl className="market-metadata">
        <div>
          <dt>Status</dt>
          <dd>{market.status}</dd>
        </div>

        <div>
          <dt>Market ID</dt>
          <dd>{market.id}</dd>
        </div>

        <div>
          <dt>Closes</dt>
          <dd>{market.closesAt}</dd>
        </div>
      </dl>

      <section className="detail-section">
        <h3>Outcomes</h3>

        <div className="detail-outcomes">
          {market.outcomes.map((outcome) => (
            <article
              className="detail-outcome-card"
              key={outcome.side}
            >
              <span>{outcome.side}</span>
              <strong>{outcome.price}</strong>
            </article>
          ))}
        </div>
      </section>

      <section className="detail-section">
        <div className="section-heading">
          <h3>Order book</h3>
          <span>Placeholder</span>
        </div>

        <div className="order-book-placeholder">
          <div>
            <h4>Bids</h4>
            <p>No live order book data yet.</p>
          </div>

          <div>
            <h4>Asks</h4>
            <p>No live order book data yet.</p>
          </div>
        </div>
      </section>
    </section>
  )
}

export default MarketDetail