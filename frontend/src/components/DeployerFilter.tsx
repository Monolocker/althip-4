import { venueLabel } from '../features/markets/discovery'

interface DeployerFilterProps {
  venues: string[]
  counts: Map<string, number>
  totalCount: number
  value: string | null
  onChange: (venue: string | null) => void
}

// Chips for "All deployers" plus one per venue. The same controlled
// pattern as CloseBucketFilter; the options come from data instead of
// a fixed list, so a newly launched deployer appears automatically.
function DeployerFilter({
  venues,
  counts,
  totalCount,
  value,
  onChange,
}: DeployerFilterProps) {
  return (
    <div className="filter-chips" role="group" aria-label="Filter by deployer">
      <span className="filter-chips-label">Deployer</span>

      <button
        type="button"
        className={
          value === null ? 'filter-chip filter-chip--active' : 'filter-chip'
        }
        aria-pressed={value === null}
        onClick={() => onChange(null)}
      >
        All
        <span className="filter-chip-count">{totalCount}</span>
      </button>

      {venues.map((venue) => {
        const isActive = venue === value
        const count = counts.get(venue) ?? 0

        return (
          <button
            key={venue}
            type="button"
            className={
              isActive ? 'filter-chip filter-chip--active' : 'filter-chip'
            }
            aria-pressed={isActive}
            disabled={count === 0 && !isActive}
            onClick={() => onChange(venue)}
          >
            {venueLabel(venue)}
            <span className="filter-chip-count">{count}</span>
          </button>
        )
      })}
    </div>
  )
}

export default DeployerFilter