interface ChipFilterProps {
    // Group label shown above the chips, e.g. "Deployer".
    label: string
    // Values in display order (derived from the data: an open set).
    options: string[]
    counts: Map<string, number>
    // Count for the "All" chip: markets passing every OTHER filter.
    totalCount: number
    // null = "All", i.e. no filter on this facet.
    value: string | null
    onChange: (value: string | null) => void
    // How a value is shown, e.g. "" -> "Hyperliquid", "sports" -> "Sports".
    formatLabel: (value: string) => string
  }
  
  // A chip row for any open-set facet (Milestone 20.1c). Deployer and
  // Category were two copies of the same component; with a third chip
  // group the shared shape was clear, so it was extracted ("rule of
  // three", 17.4). The Time chips stay separate: a closed, ordered set.
  function ChipFilter({
    label,
    options,
    counts,
    totalCount,
    value,
    onChange,
    formatLabel,
  }: ChipFilterProps) {
    return (
      <div
        className="filter-chips"
        role="group"
        aria-label={`Filter by ${label.toLowerCase()}`}
      >
        <span className="filter-chips-label">{label}</span>
  
        <button
          type="button"
          className={value === null ? 'filter-chip filter-chip--active' : 'filter-chip'}
          aria-pressed={value === null}
          onClick={() => onChange(null)}
        >
          All
          <span className="filter-chip-count">{totalCount}</span>
        </button>
  
        {options.map((option) => {
          const isActive = option === value
          const count = counts.get(option) ?? 0
  
          return (
            <button
              key={option}
              type="button"
              className={isActive ? 'filter-chip filter-chip--active' : 'filter-chip'}
              aria-pressed={isActive}
              disabled={count === 0 && !isActive}
              onClick={() => onChange(option)}
            >
              {formatLabel(option)}
              <span className="filter-chip-count">{count}</span>
            </button>
          )
        })}
      </div>
    )
  }
  
  export default ChipFilter