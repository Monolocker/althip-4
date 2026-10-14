interface MarketSearchProps {
    value: string
    onChange: (value: string) => void
    resultCount: number
    totalCount: number
  }
  
  // A controlled input: React state (owned by App) is the single source
  // of truth for the text. The input displays `value` and reports every
  // keystroke through `onChange`; it never keeps its own copy.
  function MarketSearch({
    value,
    onChange,
    resultCount,
    totalCount,
  }: MarketSearchProps) {
    const isSearching = value.trim() !== ''
  
    return (
      <div className="market-search">
        <label className="market-search-label" htmlFor="market-search-input">
          Search markets
        </label>
  
        <div className="market-search-field">
          <input
            id="market-search-input"
            className="market-search-input"
            type="text"
            value={value}
            placeholder="BTC, 100000, market id…"
            autoComplete="off"
            spellCheck={false}
            onChange={(event) => onChange(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Escape') {
                onChange('')
              }
            }}
          />
  
          {value !== '' && (
            <button
              className="market-search-clear"
              type="button"
              aria-label="Clear search"
              onClick={() => onChange('')}
            >
              Clear
            </button>
          )}
        </div>
  
        {isSearching && (
          <p className="market-search-count" aria-live="polite">
            {resultCount} of {totalCount} markets match
          </p>
        )}
      </div>
    )
  }
  
  export default MarketSearch