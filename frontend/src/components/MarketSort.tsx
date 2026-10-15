import {
    SORT_MODES,
    SORT_MODE_LABELS,
    isSortMode,
    type SortMode,
  } from '../features/markets/discovery'
  
  interface MarketSortProps {
    value: SortMode
    onChange: (mode: SortMode) => void
  }
  
  // A controlled <select>: the same pattern as MarketSearch's input.
  // App owns the sort mode; this component displays it and reports
  // changes.
  function MarketSort({ value, onChange }: MarketSortProps) {
    return (
      <div className="market-sort">
        <label className="market-sort-label" htmlFor="market-sort-select">
          Sort
        </label>
        <select
          id="market-sort-select"
          className="market-sort-select"
          value={value}
          onChange={(event) => {
            const next = event.target.value
            // event.target.value is a plain string. The type predicate
            // narrows it to SortMode before it reaches typed state.
            if (isSortMode(next)) {
              onChange(next)
            }
          }}
        >
          {SORT_MODES.map((mode) => (
            <option key={mode} value={mode}>
              {SORT_MODE_LABELS[mode]}
            </option>
          ))}
        </select>
      </div>
    )
  }
  
  export default MarketSort