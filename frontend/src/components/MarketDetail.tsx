import type {
  OutcomeMarket,
  OutcomeMarketDetail,
} from '../types/market'
import { venueLabel } from '../features/markets/discovery'
import { formatPrice, formatTime, formatVolume } from '../utils/format'
import BookQualityNote from './BookQualityNote'
import OrderBookPanel from './OrderBookPanel'
import TimeValue from './TimeValue'

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
      // the detail response is fresher than the list item:
      // a market can settle between page load and selection
      const status = detail?.status ?? market.status
      const isSettled = status === "settled"

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
          <dd>{status}</dd>
        </div>

        <div>
          <dt>Market ID</dt>
          <dd>{market.id}</dd>
        </div>

        <div>
          <dt>Event</dt>
          <dd>
            <TimeValue value={market.eventAt} />
          </dd>
        </div>

        {market.resolvesBy !== market.eventAt && (
          <div>
            <dt>Resolves by</dt>
            <dd>
              <TimeValue value={market.resolvesBy} />
            </dd>
          </div>
        )}

        <div>
          <dt>24h volume</dt>
          <dd>
            {market.volume24h === null
              ? '—'
              : `${market.volume24h.toLocaleString()} contracts (${formatVolume(market.volume24h)})`}
          </dd>
        </div>

        <div>
          <dt>Venue</dt>
          <dd>{venueLabel(market.venue)}</dd>
        </div>

        <div>
          <dt>Quote token</dt>
          <dd>{market.quoteToken}</dd>
        </div>

        <div>
          <dt>Deployer</dt>
          <dd>{detail === null ? '…' : detail.deployer ?? '—'}</dd>
        </div>
      </dl>

      <section className="detail-section">
        <h3>Outcomes</h3>

        <div
          className={
            market.book?.quality === 'unreliable'
              ? 'detail-outcomes detail-outcomes--unreliable'
              : 'detail-outcomes'
          }
        >
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
        <BookQualityNote book={market.book} />

        {market.book !== null && (
          <p className="detail-note">
            {market.book.source === 'mark'
              ? 'Inferred from the market never having traded; a full order book check is pending.'
              : `Book quality from a background check at ${formatTime(market.book.checkedAt)?.utc ?? 'an unknown time'}, refreshed every few minutes. The live order book below is current.`}
          </p>
        )}
      </section>

      {detailError !== null && (
        <p className="detail-note detail-note--error">
          Could not load additional details: {detailError}
        </p>
      )}

      {detail === null && detailError === null && (
        <p className="detail-note">Loading additional details…</p>
      )}

      {detail !== null &&
        (detail.rules !== null || detail.questionGroup?.rules != null) && (
          <section className="detail-section">
            <h3>Resolution rules</h3>
            <p className="detail-note">
              Rendered from Hyperliquid's validator-approved market template.
            </p>

            {detail.rules !== null && (
              <p className="rules-text">{detail.rules}</p>
            )}

            {detail.questionGroup?.rules != null && (
              <details className="rules-parent" open={detail.rules === null}>
                <summary>
                  Rules for the whole question
                  {detail.questionGroup.title !== null &&
                    `: ${detail.questionGroup.title}`}
                </summary>
                <p className="rules-text">{detail.questionGroup.rules}</p>
              </details>
            )}
          </section>
        )}

      {detail !== null && Object.keys(detail.spec).length > 0 && (
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
              <dd>{detail.questionGroup.title ?? detail.questionGroup.name}</dd>
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

      <OrderBookPanel
        key={market.id}
        marketId={market.id}
        sides={market.sides}
        isSettled={isSettled}
        />
    </section>
  )
}

export default MarketDetail