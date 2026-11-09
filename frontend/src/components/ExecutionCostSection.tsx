import { useState } from 'react'
import { useExecution } from '../api/queries'
import { pricesAreProbabilities } from '../features/markets/pricing'
import { useDebouncedValue } from '../hooks/useDebouncedValue'
import type { ExecutionVenue, VenueCost } from '../types/execution'
import type { OutcomeMarket } from '../types/market'
import { formatTime } from '../utils/format'

const VENUE_NAMES: Record<ExecutionVenue, string> = {
  hyperliquid: 'Hyperliquid',
  polymarket: 'Polymarket',
  kalshi: 'Kalshi',
}

const QUICK_SIZES = [100, 500, 1000]

const dollars = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  minimumFractionDigits: 2,
})

// Costs differ by fractions of a point, so two decimals, not one:
// 26.96% vs 27.35% is the whole story here.
function precise(value: number | null, asPercent: boolean): string {
  if (value === null) return '—'
  return asPercent ? `${(value * 100).toFixed(2)}%` : `${(value * 100).toFixed(2)}¢`
}

// The cheapest COMPLETE fill: a row that cannot fill the whole size is
// not comparable, however good its partial price looks.
function cheapestVenue(venues: VenueCost[]): ExecutionVenue | null {
  const complete = venues.filter(
    (v) => v.error === null && v.unfilled === 0 && v.breakEven !== null,
  )
  if (complete.length < 2) return null
  return complete.reduce((best, v) => ((v.breakEven ?? 1) < (best.breakEven ?? 1) ? v : best)).venue
}

interface ExecutionCostSectionProps {
  market: OutcomeMarket
}

// "Cost to buy" (Milestone 22.4): walking each venue's book for a given
// size and adding its fees, for Hyperliquid and every confirmed link.
function ExecutionCostSection({ market }: ExecutionCostSectionProps) {
  const [sizeText, setSizeText] = useState('500')
  const debouncedText = useDebouncedValue(sizeText, 400)
  const parsed = Number(debouncedText)
  const size = Number.isFinite(parsed) && parsed > 0 && parsed <= 1_000_000 ? parsed : null
  const execution = useExecution(market.id, size)
  const asPercent = pricesAreProbabilities(market)

  let body
  if (size === null) {
    body = <p className="detail-note">Enter a number of contracts between 1 and 1,000,000.</p>
  } else if (execution.isPending) {
    body = <p className="detail-note">Walking the order books…</p>
  } else if (execution.isError) {
    body = (
      <p className="detail-note detail-note--error">
        Could not estimate costs: {execution.error.message}
      </p>
    )
  } else {
    const estimate = execution.data
    const cheapest = cheapestVenue(estimate.venues)
    body = (
      <>
        <div className={execution.isPlaceholderData ? 'cost-table cost-table--updating' : 'cost-table'}>
          <table>
            <thead>
              <tr>
                <th>Venue</th>
                <th>Avg fill</th>
                <th>Slippage</th>
                <th>Fees</th>
                <th>Cost / contract</th>
                {asPercent && <th>Break-even</th>}
              </tr>
            </thead>
            <tbody>
              {estimate.venues.map((v) => (
                <CostRow
                  key={`${v.venue}-${v.externalId ?? ''}`}
                  cost={v}
                  asPercent={asPercent}
                  isCheapest={v.venue === cheapest}
                  size={estimate.size}
                />
              ))}
            </tbody>
          </table>
        </div>
        <ul className="cost-notes">
          {estimate.settlesAt !== null && (
            <li>Capital is held until settlement: {formatTime(estimate.settlesAt)?.utc}.</li>
          )}
          {estimate.assumptions.map((assumption) => (
            <li key={assumption}>{assumption}</li>
          ))}
          {asPercent && (
            <li>
              Break-even: the probability at which buying here exactly pays off, after fees
              charged now and at settlement. Lower is cheaper.
            </li>
          )}
        </ul>
      </>
    )
  }

  return (
    <section className="detail-section">
      <div className="section-heading">
        <h3>Cost to buy</h3>
        <div className="cost-size">
          {QUICK_SIZES.map((quick) => (
            <button
              key={quick}
              type="button"
              className={
                sizeText === String(quick)
                  ? 'side-toggle-button side-toggle-button--active'
                  : 'side-toggle-button'
              }
              onClick={() => setSizeText(String(quick))}
            >
              {quick.toLocaleString()}
            </button>
          ))}
          <label className="cost-size-input">
            <input
              type="number"
              min={1}
              step={1}
              value={sizeText}
              onChange={(event) => setSizeText(event.target.value)}
              aria-label="Contracts to buy"
            />
            contracts
          </label>
        </div>
      </div>
      {body}
    </section>
  )
}

interface CostRowProps {
  cost: VenueCost
  asPercent: boolean
  isCheapest: boolean
  size: number
}

function CostRow({ cost, asPercent, isCheapest, size }: CostRowProps) {
  const name = VENUE_NAMES[cost.venue]
  const columns = asPercent ? 6 : 5

  if (cost.error !== null) {
    return (
      <tr>
        <td>{name}</td>
        <td colSpan={columns - 1} className="detail-note--error">
          {cost.error}
        </td>
      </tr>
    )
  }

  const fees =
    cost.feeIfWins > 0
      ? `${dollars.format(cost.feeNow)} now · ${dollars.format(cost.feeIfWins)} if it wins`
      : `${dollars.format(cost.feeNow)} now`

  return (
    <>
      <tr className={isCheapest ? 'cost-row--cheapest' : undefined}>
        <td>
          <strong>{name}</strong>
          {cost.matchLevel !== null && (
            <span className={`match-badge match-badge--${cost.matchLevel}`}>
              {cost.matchLevel === 'identical' ? 'Identical' : 'Comparable'}
            </span>
          )}
          {isCheapest && <span className="cost-cheapest">Cheapest</span>}
        </td>
        <td>{precise(cost.averagePrice, asPercent)}</td>
        <td>{cost.slippage !== null ? `${(cost.slippage * 100).toFixed(2)} pts` : '—'}</td>
        <td title={cost.feeBasis}>{fees}</td>
        <td>{precise(cost.costPerContract, asPercent)}</td>
        {asPercent && <td><strong>{precise(cost.breakEven, asPercent)}</strong></td>}
      </tr>
      <tr className="cost-detail-row">
        <td colSpan={columns}>
          <span>{cost.feeBasis}</span>
          {cost.unfilled > 0 && (
            <span> · filled {cost.filled.toLocaleString()} of {size.toLocaleString()}</span>
          )}
          {cost.bookTime !== null && (
            <span> · book {formatTime(cost.bookTime)?.utc}</span>
          )}
          {cost.warnings.map((warning) => (
            <span key={warning} className="cost-warning">⚠ {warning}</span>
          ))}
        </td>
      </tr>
    </>
  )
}

export default ExecutionCostSection