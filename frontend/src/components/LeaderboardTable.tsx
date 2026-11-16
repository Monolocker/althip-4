import { Fragment, useState } from 'react'
import { useLeaderboard } from '../api/queries'
import { WINDOW_LABELS } from '../features/leaderboard/options'
import type { LeaderboardRow, LeaderboardWindow } from '../types/leaderboard'
import { formatUsd, formatVolume } from '../utils/format'
import TraderAddress from './TraderAddress'

function pnlClass(value: number): string {
  if (value > 0) return 'pnl pnl--up'
  if (value < 0) return 'pnl pnl--down'
  return 'pnl'
}

// Where the net PnL came from. Conversions (merges, splits, negations)
// are Hyperliquid's own accounting and can be large, so they are shown
// rather than folded silently into one number.
function RowDetails({ row }: { row: LeaderboardRow }) {
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
        Markets: {row.wins} won · {row.losses} lost · {row.markets - row.wins - row.losses} with nothing
        realized yet
      </p>
    </div>
  )
}

const COLUMNS = 7

interface LeaderboardTableProps {
  timeWindow: LeaderboardWindow
}

// Workspace half of the Leaderboard view (Milestone 23.4, v2 in 26.1).
function LeaderboardTable({ timeWindow }: LeaderboardTableProps) {
  const leaderboard = useLeaderboard(timeWindow)
  // One expanded row at a time, remembered by address, so it stays open
  // when the row moves after a refresh.
  const [expanded, setExpanded] = useState<string | null>(null)

  const title = `Leaderboard · ${WINDOW_LABELS[timeWindow]}`

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
        <p>No traders with complete outcome fills in this window yet.</p>
      </div>
    )
  }

  return (
    <section className="leaderboard">
      <div className="market-detail-header">
        <h2>{title}</h2>
        <p className="detail-note leaderboard-subtitle">
          Top {data.rows.length} of {data.tradersRanked} ranked traders. Realized PnL in USDC after
          fees, HIP-4 outcome markets only. {data.tradersExcluded} traders left out: history incomplete.
        </p>
      </div>

      {/* While a new window loads, the previous table stays on screen,
          dimmed (keepPreviousData), instead of a blank page. */}
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
              <th className="leaderboard-num" aria-sort="descending">
                Net PnL ▾
              </th>
              <th className="leaderboard-num">Volume</th>
              <th className="leaderboard-num">Markets</th>
              <th className="leaderboard-num">W–L</th>
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
                    <td className="leaderboard-num">{row.markets}</td>
                    <td className="leaderboard-num">
                      {row.wins}–{row.losses}
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