import { useLeaderboard } from '../api/queries'
import { SORTS, SORT_LABELS, WINDOWS, WINDOW_LABELS } from '../features/leaderboard/options'
import type { LeaderboardSort, LeaderboardWindow } from '../types/leaderboard'
import { formatTime } from '../utils/format'

interface ToggleGroupProps<T extends string> {
  label: string
  options: T[]
  labels: Record<T, string>
  value: T
  onChange: (value: T) => void
}

// A generic toggle row: T is the union of allowed values ('24h' | ...),
// so onChange can only ever receive one of them.
function ToggleGroup<T extends string>({ label, options, labels, value, onChange }: ToggleGroupProps<T>) {
  return (
    <div className="leaderboard-group">
      <span className="leaderboard-group-label">{label}</span>
      <div className="side-toggle" role="group" aria-label={label}>
        {options.map((option) => (
          <button
            key={option}
            type="button"
            className={
              option === value ? 'side-toggle-button side-toggle-button--active' : 'side-toggle-button'
            }
            aria-pressed={option === value}
            onClick={() => onChange(option)}
          >
            {labels[option]}
          </button>
        ))}
      </div>
    </div>
  )
}

interface LeaderboardPanelProps {
  timeWindow: LeaderboardWindow
  sort: LeaderboardSort
  onWindowChange: (timeWindow: LeaderboardWindow) => void
  onSortChange: (sort: LeaderboardSort) => void
}

// Sidebar half of the Leaderboard view (Milestone 23.4): the controls,
// and what the numbers do and do not cover. It calls the same hook with
// the same key as the table, so both share ONE request.
function LeaderboardPanel({ timeWindow, sort, onWindowChange, onSortChange }: LeaderboardPanelProps) {
  const leaderboard = useLeaderboard(timeWindow, sort)
  const data = leaderboard.data

  const shown = data?.rows ?? []
  const full = shown.filter((row) => row.coverage === 'full').length
  const behind = shown.filter((row) => row.behind).length
  const start = formatTime(data?.windowStart ?? null)
  const since = formatTime(data?.trackingSince ?? null)
  const updated = formatTime(data?.generatedAt ?? null)

  return (
    <section className="leaderboard-panel" aria-label="Leaderboard">
      <div className="market-list-header">
        <h2>Leaderboard</h2>
        {data !== undefined && <span>{data.tradersRanked}</span>}
      </div>

      <ToggleGroup
        label="Window"
        options={WINDOWS}
        labels={WINDOW_LABELS}
        value={timeWindow}
        onChange={onWindowChange}
      />
      <ToggleGroup label="Rank by" options={SORTS} labels={SORT_LABELS} value={sort} onChange={onSortChange} />

      {data !== undefined && (
        <dl className="leaderboard-summary">
          <dt>Window starts</dt>
          <dd>
            {start?.utc ?? '—'}
            {timeWindow === 'all' && <span className="leaderboard-muted"> (since tracking began)</span>}
          </dd>
          <dt>Full history</dt>
          <dd>
            {full} of {shown.length} shown
          </dd>
          <dt>Catching up</dt>
          <dd>{behind} with recent trades not fetched yet</dd>
          <dt>Traders</dt>
          <dd>
            {data.tradersKnown} discovered, {data.tradersPending} awaiting first fetch
          </dd>
          <dt>Tracking since</dt>
          <dd>{since?.utc ?? '—'}</dd>
          <dt>Updated</dt>
          <dd>{updated?.utc ?? '—'}</dd>
        </dl>
      )}

      <ul className="leaderboard-notes">
        <li>Outcome markets only: perp and spot fills are never stored.</li>
        <li>Realized PnL net of fees. Open positions are not included.</li>
        <li>Only traders this app has seen trading are ranked.</li>
      </ul>
    </section>
  )
}

export default LeaderboardPanel