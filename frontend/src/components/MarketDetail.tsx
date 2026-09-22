import type { OutcomeMarket } from '../types/market'
import { formatCloseTime, formatPrice } from '../utils/format'

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
          <dd>{formatCloseTime(market.closesAt)}</dd>
        </div>

        <div>
          <dt>Venue</dt>
          <dd>{market.venue || "—"}</dd>
        </div>

        <div>
          <dt>Quote token</dt>
          <dd>{market.quoteToken}</dd>
        </div>
      </dl>

      <section className="detail-section">
        <h3>Outcomes</h3>

        <div className="detail-outcomes">
          {market.sides.map((side) => (
            <article
              className="detail-outcome-card"
              key={side.coin}
            >
              <span>{side.label}</span>
              <strong>{formatPrice(side.price)}</strong>
              <small>{side.coin}</small>
            </article>
          ))}
        </div>
      </section>

      <section className="detail-section">
        <h3>Market spec</h3>
        <p className="market-spec">{market.description}</p>
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