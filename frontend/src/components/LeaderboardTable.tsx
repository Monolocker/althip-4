import { Fragment, useState } from 'react'
import { useLeaderboard } from '../api/queries'
import { SORT_LABELS, WINDOW_LABELS } from '../features/leaderboard/options'
import type { LeaderboardRow, LeaderboardSort, LeaderboardWindow } from '../types/leaderboard'
import { formatShortDate, formatTime, formatUsd, formatVolume } from '../utils/format'
import TraderAddress from './TraderAddress'

function pnlClass(value: number): string {
  if (value > 0) return 'pnl pnl--up'
  if (value < 0) return 'pnl pnl--down'
  return 'pnl'
}

// What this trader's history covers, shown only when it needs attention.
function HistoryBadges({ row }: { row: LeaderboardRow }) {
  const through = formatTime(row.fillsThrough)?.utc ?? row.fillsThrough
  return (
    <span className="history-badges">
      {row.coverage === 'full' ? (
        <span className="leaderboard-muted">full</span>
      ) : row.coverageFrom === null ? (
        <span
          className="history-badge history-badge--checking"
          title="This trader's history is being re-fetched: completeness is not known yet."
        >
          checking
        </span>
      ) : (
        <span
          className="history-badge history-badge--partial"
          title={`Fills are complete only from ${formatTime(row.coverageFrom)?.utc}, after this window starts.`}
        >
          from {formatShortDate(row.coverageFrom)}
        </span>
      )}
      {row.behind && (
        <span
          className="history-badge history-badge--behind"
          title={`Trades seen that are not fetched yet. Fills as of ${through}.`}
        >
          catching up
        </span>
      )}
    </span>
  )
}

// Where the net PnL came from. Conversions (merges, splits, negations)
// are Hyperliquid's own accounting and can be large, so they are shown
// rather than folded silently into one number.
function RowDetails({ row }: { row: LeaderboardRow }) {
  const coverageFrom = formatTime(row.coverageFrom)
  const through = formatTime(row.fillsThrough)
  return (
    <div className="leaderboard-details">
      <p>
        Trading <span className={pnlClass(row.tradingPnl)}>{formatUsd(row.tradingPnl)}</span>
        {' · '}Settlements <span className={pnlClass(row.settlementPnl)}>{formatUsd(row.settlementPnl)}</span>
        {' · '}Conversions <span className={pnlClass(row.conversionPnl)}>{formatUsd(row.conversionPnl)}</span>
        {' · '}Fees <span className="pnl pnl--down">{formatUsd(-row.fees)}</span>
        {' = '}
        <strong className={pnlClass(row.netPnl)}>{formatUsd(row.netPnl)}</strong>
      </p>
      <p>
        Settlements: {row.settlementsWon} won · {row.settlementsLost} lost
        {row.settlementsFractional > 0 && ` · ${row.settlementsFractional} fractional`}
      </p>
      <p>
        History complete from {coverageFrom?.utc ?? 'not verified yet'} · fills fetched through{' '}
        {through?.utc ?? '—'}
      </p>
    </div>
  )
}

// Header cell of a column the leaderboard can be ranked by.
function RankHeader({ label, active }: { label: string; active: boolean }) {
  return (
    <th className="leaderboard-num" aria-sort={active ? 'descending' : undefined}>
      {label}
      {active && ' ▾'}
    </th>
  )
}

const COLUMNS = 9

interface LeaderboardTableProps {
  timeWindow: LeaderboardWindow
  sort: LeaderboardSort
}

// Workspace half of the Leaderboard view (Milestone 23.4).
function LeaderboardTable({ timeWindow, sort }: LeaderboardTableProps) {
  const leaderboard = useLeaderboard(timeWindow, sort)
  // One expanded row at a time, remembered by address, so it stays open
  // when the row moves after a refresh.
  const [expanded, setExpanded] = useState<string | null>(null)

  const title = `Leaderboard · ${WINDOW_LABELS[timeWindow]} · by ${SORT_LABELS[sort]}`

  if (leaderboard.isPending) {
    return (
      <div className="market-detail-empty">
        <h2>{title}</h2>
        <p>Loading the leaderboard…</p>
      </div>
    )
  }
  if (leaderboard.isError && leaderboard.data === undefined) {
    return (
      <div className="market-detail-empty">
        <h2>{title}</h2>
        <p className="detail-note--error">{leaderboard.error.message}</p>
      </div>
    )
  }

  const data = leaderboard.data
  if (data.rows.length === 0) {
    return (
      <div className="market-detail-empty">
        <h2>{title}</h2>
        <p>No traders with outcome fills in this window yet.</p>
      </div>
    )
  }

  return (
    <section className="leaderboard">
      <div className="market-detail-header">
        <h2>{title}</h2>
        <p className="detail-note leaderboard-subtitle">
          Top {data.rows.length} of {data.tradersRanked} ranked traders. Realized PnL in USDC, net of
          fees, outcome markets only.
        </p>
      </div>

      {/* While a new window or ranking loads, the previous table stays
          on screen, dimmed (keepPreviousData), instead of a blank page. */}
      <div
        className={
          leaderboard.isPlaceholderData ? 'leaderboard-table leaderboard-table--updating' : 'leaderboard-table'
        }
      >
        <table>
          <thead>
            <tr>
              <th className="leaderboard-num">#</th>
              <th>Trader</th>
              <RankHeader label="Net PnL" active={sort === 'pnl'} />
              <RankHeader label="Volume" active={sort === 'volume'} />
              <RankHeader label="Fills" active={sort === 'fills'} />
              <th className="leaderboard-num">Markets</th>
              <th className="leaderboard-num">Settled W–L</th>
              <th>History</th>
              <th>
                <span className="visually-hidden">Details</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {data.rows.map((row, index) => {
              const isOpen = expanded === row.address
              return (
                <Fragment key={row.address}>
                  <tr className={isOpen ? 'leaderboard-row leaderboard-row--open' : 'leaderboard-row'}>
                    <td className="leaderboard-num">{index + 1}</td>
                    <td>
                      <TraderAddress address={row.address} />
                    </td>
                    <td className="leaderboard-num">
                      <span className={pnlClass(row.netPnl)}>{formatUsd(row.netPnl)}</span>
                    </td>
                    <td className="leaderboard-num">${formatVolume(row.volume)}</td>
                    <td className="leaderboard-num">{row.fills.toLocaleString('en-US')}</td>
                    <td className="leaderboard-num">{row.markets}</td>
                    <td className="leaderboard-num">
                      {row.settlementsWon}–{row.settlementsLost}
                    </td>
                    <td>
                      <HistoryBadges row={row} />
                    </td>
                    <td>
                      <button
                        type="button"
                        className="trader-address-button"
                        aria-expanded={isOpen}
                        onClick={() => setExpanded(isOpen ? null : row.address)}
                      >
                        {isOpen ? 'Hide' : 'Details'}
                      </button>
                    </td>
                  </tr>
                  {isOpen && (
                    <tr className="leaderboard-detail-row">
                      <td colSpan={COLUMNS}>
                        <RowDetails row={row} />
                      </td>
                    </tr>
                  )}
                </Fragment>
              )
            })}
          </tbody>
        </table>
      </div>
    </section>
  )
}

export default LeaderboardTable