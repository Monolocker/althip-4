import {
    CLOSE_FILTERS,
    CLOSE_FILTER_LABELS,
    type CloseFilter,
  } from '../features/markets/discovery'
  
  interface CloseBucketFilterProps {
    value: CloseFilter
    onChange: (filter: CloseFilter) => void
    counts: Record<CloseFilter, number>
  }
  
  function CloseBucketFilter({
    value,
    onChange,
    counts,
  }: CloseBucketFilterProps) {
    return (
      <div
        className="filter-chips"
        role="group"
        aria-label="Filter by time until the market's event"
      >
        <span className="filter-chips-label">Time</span>
  
        {CLOSE_FILTERS.map((filter) => {
          const isActive = filter === value
          const count = counts[filter]
  
          return (
            <button
              key={filter}
              type="button"
              className={
                isActive ? 'filter-chip filter-chip--active' : 'filter-chip'
              }
              aria-pressed={isActive}
              // An empty bucket can't be selected, unless it is already
              // the active one (it emptied after being chosen), so the
              // user can always see and leave the current state.
              disabled={count === 0 && !isActive}
              onClick={() => onChange(filter)}
            >
              {CLOSE_FILTER_LABELS[filter]}
              <span className="filter-chip-count">{count}</span>
            </button>
          )
        })}
      </div>
    )
  }
  
  export default CloseBucketFilter