import { ApiError } from '../api/markets'
import { useTraderDashboard } from '../api/queries'
import { WINDOWS, WINDOW_LABELS } from '../features/leaderboard/options'
import type { LeaderboardWindow } from '../types/leaderboard'
import { formatMoney, formatTime, formatUsd } from '../utils/format'
import TraderActivity from './TraderActivity'
import TraderAddress from './TraderAddress'
import TraderPnlChart from './TraderPnlChart'

function pnlClass(value: number): string {
  if (value > 0) return 'pnl pnl--up'
  if (value < 0) return 'pnl pnl--down'
  return 'pnl'
}

interface TraderDashboardProps {
  address: string
  timeWindow: LeaderboardWindow
  onWindowChange: (timeWindow: LeaderboardWindow) => void
  onClose: () => void
  onOpenMarket: (marketId: string) => void
}

// One trader's HIP-4 dashboard (Milestone 26.3), opened from the
// leaderboard: Stats | PnL chart | Biggest win + Accuracy, then the
// activity tabs. Window figures come from stored fills; positions and
// orders are live.
function TraderDashboard({ address, timeWindow, onWindowChange, onClose, onOpenMarket }: TraderDashboardProps) {
  const dashboard = useTraderDashboard(address, timeWindow)
  const windowLabel = WINDOW_LABELS[timeWindow]

  const header = (
    <div className="trader-dashboard-header">
      <button type="button" className="trader-back" onClick={onClose}>
        ← Leaderboard
      </button>
      <div className="trader-dashboard-title">
        <h2>Trader</h2>
        <TraderAddress address={address} />
      </div>
      <div className="side-toggle" role="group" aria-label="Window">
        {WINDOWS.map((option) => (
          <button
            key={option}
            type="button"
            className={option === timeWindow ? 'side-toggle-button side-toggle-button--active' : 'side-toggle-button'}
            aria-pressed={option === timeWindow}
            onClick={() => onWindowChange(option)}
          >
            {WINDOW_LABELS[option]}
          </button>
        ))}
      </div>
    </div>
  )

  if (dashboard.isPending) {
    return (
      <section className="trader-dashboard">
        {header}
        <p className="detail-note">Loading this trader…</p>
      </section>
    )
  }
  if (dashboard.isError && dashboard.data === undefined) {
    const notTracked = dashboard.error instanceof ApiError && dashboard.error.status === 404
    return (
      <section className="trader-dashboard">
        {header}
        <p className="detail-note detail-note--error">
          {notTracked ? "This address isn't a trader this app has seen on HIP-4." : dashboard.error.message}
        </p>
      </section>
    )
  }

  const data = dashboard.data
  const { stats, positions, biggestWin } = data
  const historyFrom = formatTime(data.historyFrom)

  return (
    <section className="trader-dashboard">
      {header}

      {!data.complete && (
        <p className="trader-banner">
          This trader's stored fills don't fully cover the {windowLabel} window yet
          {historyFrom !== null ? `; figures start ${historyFrom.utc}` : ''}. They are left out of the{' '}
          {windowLabel} leaderboard until their history catches up.
        </p>
      )}
      {data.liveError !== null && (
        <p className="detail-note detail-note--error">
          Positions and orders unavailable: {data.liveError}
        </p>
      )}

      <div className={dashboard.isPlaceholderData ? 'trader-grid trader-grid--updating' : 'trader-grid'}>
        <div className="trader-card">
          <h3>Stats · {windowLabel}</h3>
          <dl className="trader-stats">
            <dt>PnL</dt>
            <dd
              className={pnlClass(stats.netPnl)}
              title={`Realized, after ${formatMoney(stats.fees)} of fees (before fees: ${formatUsd(stats.grossPnl)})`}
            >
              {formatUsd(stats.netPnl)}
            </dd>
            <dt>Volume</dt>
            <dd>{formatMoney(stats.volume)}</dd>
            <dt>Wins</dt>
            <dd>{stats.wins}</dd>
            <dt>Losses</dt>
            <dd>{stats.losses}</dd>
            <dt>Biggest position</dt>
            <dd
              title={
                positions?.biggest
                  ? `${positions.biggest.title} · ${positions.biggest.sideLabel}`
                  : undefined
              }
            >
              {positions === null ? '—' : formatMoney(positions.biggest?.value ?? 0)}
            </dd>
            <dt>Positions value</dt>
            <dd>
              {positions === null ? '—' : formatMoney(positions.value)}
              {positions !== null && positions.unpriced > 0 && (
                <span className="leaderboard-muted"> + {positions.unpriced} unpriced</span>
              )}
            </dd>
            <dt>Open positions</dt>
            <dd>{positions === null ? '—' : positions.count}</dd>
          </dl>
          <p className="trader-card-note">Realized PnL after fees. Positions are live.</p>
        </div>

        <div className="trader-card trader-card--chart">
          <h3>PnL · {windowLabel}</h3>
          <TraderPnlChart series={data.pnlSeries} timeWindow={timeWindow} />
        </div>

        <div className="trader-side-cards">
          <div className="trader-card">
            <h3>Biggest win · {windowLabel}</h3>
            {biggestWin === null ? (
              <p className="trader-big-number">—</p>
            ) : (
              <>
                <p className="trader-big-number">{formatMoney(biggestWin.netPnl)}</p>
                <button
                  type="button"
                  className="trader-market-link"
                  onClick={() => onOpenMarket(biggestWin.marketId)}
                >
                  {biggestWin.title ?? `Market #${biggestWin.marketId}`} →
                </button>
              </>
            )}
          </div>
          <div className="trader-card">
            <h3>Accuracy rate · {windowLabel}</h3>
            <p className="trader-big-number">
              {stats.accuracy === null ? '—' : `${Math.round(stats.accuracy * 100)}%`}
            </p>
            <p className="trader-card-note">
              {stats.wins} won of {stats.wins + stats.losses} markets with a result
            </p>
          </div>
        </div>
      </div>

      <TraderActivity
        positions={positions}
        orders={data.orders}
        resolved={data.resolved}
        onOpenMarket={onOpenMarket}
      />
    </section>
  )
}

export default TraderDashboard