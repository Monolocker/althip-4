import { useState } from 'react'
import { formatProbability } from '../features/markets/pricing'
import type { ResolvedMarket, TraderOrder, TraderPositions } from '../types/trader'
import { formatMoney, formatShortDate, formatTime, formatUsd } from '../utils/format'

type Tab = 'all' | 'open' | 'orders' | 'resolved'

const TABS: { value: Tab; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'open', label: 'Open' },
  { value: 'orders', label: 'Orders' },
  { value: 'resolved', label: 'Resolved' },
]

const RESULT_LABELS: Record<ResolvedMarket['result'], string> = {
  win: 'Won',
  loss: 'Lost',
  even: 'Even',
}

function pnlClass(value: number): string {
  if (value > 0) return 'pnl pnl--up'
  if (value < 0) return 'pnl pnl--down'
  return 'pnl'
}

const shareCount = new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 })

interface MarketLinkProps {
  marketId: string
  title: string | null
  onOpenMarket: (marketId: string) => void
}

// A market name that opens the market in this app. Settled markets open
// too: the market detail shows how they ended (21.2).
function MarketLink({ marketId, title, onOpenMarket }: MarketLinkProps) {
  return (
    <button type="button" className="trader-market-link" onClick={() => onOpenMarket(marketId)}>
      {title ?? `Market #${marketId}`}
    </button>
  )
}

interface TraderActivityProps {
  positions: TraderPositions | null // null: live data unavailable
  orders: TraderOrder[] | null
  resolved: ResolvedMarket[]
  onOpenMarket: (marketId: string) => void
}

// The tabs under the chart (Milestone 26.3). Open and Orders are live;
// Resolved covers the chosen window; All = Open + Resolved (decision).
function TraderActivity({ positions, orders, resolved, onOpenMarket }: TraderActivityProps) {
  const [tab, setTab] = useState<Tab>('all')
  const unavailable = <p className="detail-note">Live data is unavailable right now.</p>

  const counts: Record<Tab, number | null> = {
    all: positions === null ? null : positions.count + resolved.length,
    open: positions?.count ?? null,
    orders: orders?.length ?? null,
    resolved: resolved.length,
  }

  function openTable() {
    if (positions === null) return unavailable
    if (positions.items.length === 0) return <p className="detail-note">No open positions.</p>
    return (
      <table>
        <thead>
          <tr>
            <th>Market</th>
            <th>Side</th>
            <th className="leaderboard-num">Shares</th>
            <th className="leaderboard-num">Price</th>
            <th className="leaderboard-num">Value</th>
            <th className="leaderboard-num">Cost</th>
            <th className="leaderboard-num">On hold</th>
          </tr>
        </thead>
        <tbody>
          {positions.items.map((item) => (
            <tr key={item.coin}>
              <td className="trader-market-cell">
                <MarketLink marketId={item.marketId} title={item.title} onOpenMarket={onOpenMarket} />
              </td>
              <td>{item.sideLabel}</td>
              <td className="leaderboard-num">{shareCount.format(item.shares)}</td>
              <td className="leaderboard-num">{item.price === null ? '—' : formatProbability(item.price)}</td>
              <td className="leaderboard-num">{item.value === null ? 'unpriced' : formatMoney(item.value)}</td>
              <td className="leaderboard-num">
                {item.entryNotional === null ? '—' : formatMoney(item.entryNotional)}
              </td>
              <td className="leaderboard-num">{item.onHold > 0 ? shareCount.format(item.onHold) : '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    )
  }

  function ordersTable() {
    if (orders === null) return unavailable
    if (orders.length === 0) return <p className="detail-note">No open orders.</p>
    return (
      <table>
        <thead>
          <tr>
            <th>Market</th>
            <th>Side</th>
            <th>Order</th>
            <th className="leaderboard-num">Price</th>
            <th className="leaderboard-num">Size</th>
            <th>Placed</th>
          </tr>
        </thead>
        <tbody>
          {orders.map((order) => (
            <tr key={`${order.coin}-${order.placedAt}-${order.price}`}>
              <td className="trader-market-cell">
                <MarketLink marketId={order.marketId} title={order.title} onOpenMarket={onOpenMarket} />
              </td>
              <td>{order.sideLabel ?? '—'}</td>
              <td>
                {order.direction === 'buy' ? 'Buy' : 'Sell'}
                {order.tif === 'Alo' && <span className="leaderboard-muted"> · post only</span>}
                {order.reduceOnly && <span className="leaderboard-muted"> · reduce only</span>}
              </td>
              <td className="leaderboard-num">{formatProbability(order.price)}</td>
              <td className="leaderboard-num">
                {shareCount.format(order.size)}
                {order.size !== order.originalSize && (
                  <span className="leaderboard-muted"> of {shareCount.format(order.originalSize)}</span>
                )}
              </td>
              <td title={formatTime(order.placedAt)?.utc}>{formatTime(order.placedAt)?.utc ?? '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    )
  }

  function resolvedRows(items: ResolvedMarket[]) {
    return items.map((item) => (
      <tr key={`resolved-${item.marketId}`}>
        <td className="trader-market-cell">
          <MarketLink marketId={item.marketId} title={item.title} onOpenMarket={onOpenMarket} />
        </td>
        <td>
          {RESULT_LABELS[item.result]}
          <span className="leaderboard-muted"> · {item.settled ? 'settled' : 'sold'}</span>
        </td>
        <td className="leaderboard-num">
          <span className={pnlClass(item.netPnl)}>{formatUsd(item.netPnl)}</span>
        </td>
        <td className="leaderboard-num">{formatMoney(item.volume)}</td>
        <td title={formatTime(item.lastFillAt)?.utc}>{formatShortDate(item.lastFillAt)}</td>
      </tr>
    ))
  }

  function resolvedTable() {
    if (resolved.length === 0) {
      return <p className="detail-note">No market with realized PnL in this window.</p>
    }
    return (
      <table>
        <thead>
          <tr>
            <th>Market</th>
            <th>Result</th>
            <th className="leaderboard-num">Net PnL</th>
            <th className="leaderboard-num">Volume</th>
            <th>Last fill</th>
          </tr>
        </thead>
        <tbody>{resolvedRows(resolved)}</tbody>
      </table>
    )
  }

  // Open positions first (they are "now"), then the window's resolved
  // markets, newest first.
  function allTable() {
    const open = positions?.items ?? []
    if (open.length === 0 && resolved.length === 0) {
      return positions === null ? unavailable : <p className="detail-note">Nothing in this window.</p>
    }
    return (
      <>
        {positions === null && unavailable}
        <table>
          <thead>
            <tr>
              <th>Market</th>
              <th>Status</th>
              <th className="leaderboard-num">PnL / value</th>
              <th className="leaderboard-num">Volume</th>
              <th>When</th>
            </tr>
          </thead>
          <tbody>
            {open.map((item) => (
              <tr key={`open-${item.coin}`}>
                <td className="trader-market-cell">
                  <MarketLink marketId={item.marketId} title={item.title} onOpenMarket={onOpenMarket} />
                </td>
                <td>
                  Open<span className="leaderboard-muted"> · {item.sideLabel}</span>
                </td>
                <td className="leaderboard-num">{item.value === null ? 'unpriced' : formatMoney(item.value)}</td>
                <td className="leaderboard-num">—</td>
                <td>now</td>
              </tr>
            ))}
            {resolvedRows(resolved)}
          </tbody>
        </table>
      </>
    )
  }

  const body =
    tab === 'open' ? openTable() : tab === 'orders' ? ordersTable() : tab === 'resolved' ? resolvedTable() : allTable()

  return (
    <section className="trader-activity">
      <div className="side-toggle" role="tablist" aria-label="Trader activity">
        {TABS.map((item) => (
          <button
            key={item.value}
            type="button"
            role="tab"
            aria-selected={tab === item.value}
            className={tab === item.value ? 'side-toggle-button side-toggle-button--active' : 'side-toggle-button'}
            onClick={() => setTab(item.value)}
          >
            {item.label}
            {counts[item.value] !== null && <span className="trader-tab-count"> {counts[item.value]}</span>}
          </button>
        ))}
      </div>
      <div className="leaderboard-table trader-activity-table">{body}</div>
    </section>
  )
}

export default TraderActivity