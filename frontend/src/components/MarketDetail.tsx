import type {
  OutcomeMarket,
  OutcomeMarketDetail,
} from '../types/market'
import { formatCloseTime, formatPrice } from '../utils/format'

interface MarketDetailProps {
  market: OutcomeMarket
  detail: OutcomeMarketDetail | null
  detailError: string | null
}

function MarketDetail({ market, detail, detailError }: MarketDetailProps) {
  const settlement = detail?.settlement ?? null
  const winningSide =
    settlement !== null && settlement.winningSideIndex !== null
      ? market.sides[settlement.winningSideIndex] ?? null
      : null

  return (
    <section className="market-detail">
      <header className="market-detail-header">
        <p className="section-label">Market details</p>
        <h2>{market.question}</h2>
      </header>

      {settlement !== null && (
        <div className="settlement-banner">
          <strong>Settled</strong>
          <span>
            {winningSide !== null
              ? `${winningSide.label} won`
              : `Settle fraction: ${settlement.settleFraction ?? 'unknown'}`}
          </span>
        </div>
      )}

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
          <dd>{market.venue || '—'}</dd>
        </div>

        <div>
          <dt>Quote token</dt>
          <dd>{market.quoteToken}</dd>
        </div>

        <div>
          <dt>Deployer</dt>
          <dd>{detail?.deployer ?? '…'}</dd>
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

      {detailError !== null && (
        <p className="detail-note detail-note--error">
          Could not load additional details: {detailError}
        </p>
      )}

      {detail === null && detailError === null && (
        <p className="detail-note">Loading additional details…</p>
      )}

      {detail !== null && (
        <section className="detail-section">
          <h3>Market spec</h3>

          <dl className="market-metadata">
            {Object.entries(detail.spec).map(([key, value]) => (
              <div key={key}>
                <dt>{key}</dt>
                <dd>{value}</dd>
              </div>
            ))}
          </dl>

          <p className="market-spec">{market.description}</p>
        </section>
      )}

      {detail !== null && detail.questionGroup !== null && (
        <section className="detail-section">
          <h3>Part of a question</h3>

          <dl className="market-metadata">
            <div>
              <dt>Question</dt>
              <dd>{detail.questionGroup.name}</dd>
            </div>

            <div>
              <dt>Role</dt>
              <dd>
                {detail.questionGroup.isFallback
                  ? 'Fallback outcome'
                  : 'Named outcome'}
              </dd>
            </div>

            <div>
              <dt>Other outcomes</dt>
              <dd>{detail.questionGroup.siblingIds.length}</dd>
            </div>
          </dl>

          <p className="market-spec">{detail.questionGroup.description}</p>
        </section>
      )}

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