export interface ActiveFilter {
    key: string
    label: string
    onRemove: () => void
  }
  
  interface ActiveFiltersProps {
    filters: ActiveFilter[]
    onResetAll: () => void
  }
  
  // The filters currently narrowing the list, each removable on its own,
  // plus one "Reset all" (Milestone 20.1d). Renders nothing when no filter
  // is active, so it only takes space when there is something to undo.
  function ActiveFilters({ filters, onResetAll }: ActiveFiltersProps) {
    if (filters.length === 0) {
      return null
    }
  
    return (
      <div className="active-filters" role="group" aria-label="Active filters">
        <span className="filter-chips-label">
          {filters.length === 1 ? '1 active filter' : `${filters.length} active filters`}
        </span>
  
        {filters.map((filter) => (
          <button
            key={filter.key}
            type="button"
            className="active-filter"
            aria-label={`Remove filter: ${filter.label}`}
            onClick={filter.onRemove}
          >
            {filter.label}
            <span className="active-filter-remove" aria-hidden="true">
              ×
            </span>
          </button>
        ))}
  
        <button
          type="button"
          className="active-filters-reset"
          onClick={onResetAll}
        >
          Reset all
        </button>
      </div>
    )
  }
  
  export default ActiveFilters