import { useLeaderboard } from '../api/queries'
import { WINDOWS, WINDOW_LABELS } from '../features/leaderboard/options'
import type { LeaderboardWindow } from '../types/leaderboard'
import { formatTime } from '../utils/format'

interface LeaderboardPanelProps {
  timeWindow: LeaderboardWindow
  onWindowChange: (timeWindow: LeaderboardWindow) => void
}

// Sidebar half of the Leaderboard view (Milestone 23.4, v2 in 26.1):
// the window toggle, and what the numbers do and do not cover. It calls
// the same hook with the same key as the table, so both share ONE
// request.
function LeaderboardPanel({ timeWindow, onWindowChange }: LeaderboardPanelProps) {
  const leaderboard = useLeaderboard(timeWindow)
  const data = leaderboard.data

  const start = formatTime(data?.windowStart ?? null)
  const updated = formatTime(data?.generatedAt ?? null)

  return (
    <section className="leaderboard-panel" aria-label="Leaderboard">
      <div className="market-list-header">
        <h2>Leaderboard</h2>
        {data !== undefined && <span>{data.tradersRanked}</span>}
      </div>

      <div className="leaderboard-group">
        <span className="leaderboard-group-label">Window</span>
        <div className="side-toggle" role="group" aria-label="Window">
          {WINDOWS.map((option) => (
            <button
              key={option}
              type="button"
              className={
                option === timeWindow ? 'side-toggle-button side-toggle-button--active' : 'side-toggle-button'
              }
              aria-pressed={option === timeWindow}
              onClick={() => onWindowChange(option)}
            >
              {WINDOW_LABELS[option]}
            </button>
          ))}
        </div>
      </div>

      {data !== undefined && (
        <dl className="leaderboard-summary">
          <dt>Window starts</dt>
          <dd>
            {timeWindow === 'all' ? (
              <span className="leaderboard-muted">each trader's full tracked history</span>
            ) : (
              start?.utc ?? '—'
            )}
          </dd>
          <dt>Ranked</dt>
          <dd>{data.tradersRanked} traders with fills in this window</dd>
          <dt>Left out</dt>
          <dd>{data.tradersExcluded} whose history doesn't cover this window yet</dd>
          <dt>Discovered</dt>
          <dd>{data.tradersKnown} traders seen on the trade stream</dd>
          <dt>Updated</dt>
          <dd>{updated?.utc ?? '—'}</dd>
        </dl>
      )}

      <ul className="leaderboard-notes">
        <li>HIP-4 outcome markets only: perp and spot fills are never stored.</li>
        <li>Ranked by realized PnL after fees. Open positions are not included.</li>
        <li>Wins and losses count markets: a market is a win if its net PnL in the window is above 0.</li>
        <li>Only traders this app has seen trading, and whose history is complete, are ranked.</li>
      </ul>
    </section>
  )
}

export default LeaderboardPanel