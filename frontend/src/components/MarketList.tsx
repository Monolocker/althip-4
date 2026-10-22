import type { ListEntry } from '../features/markets/grouping'
import MarketCard from './MarketCard'
import QuestionCard from './QuestionCard'

interface MarketListProps {
  entries: ListEntry[]
  selectedMarketId: string | null
  onSelect: (marketId: string) => void
}

function MarketList({
  entries,
  selectedMarketId,
  onSelect,
}: MarketListProps) {
  return (
    <section
      className="market-list"
      aria-label="Outcome markets"
    >
      <div className="market-list-header">
        <h2>Markets</h2>
        {/* Counts cards (decision 3), not outcomes. */}
        <span>{entries.length}</span>
      </div>

      <div className="market-list-items">
        {entries.length === 0 ? (
          <p className="market-list-empty">No markets to show.</p>
        ) : (
          entries.map((entry) =>
            // Narrowing on the discriminant: inside each branch
            // TypeScript knows exactly which entry shape it has.
            entry.kind === 'market' ? (
              <MarketCard
                key={entry.key}
                market={entry.market}
                isSelected={entry.market.id === selectedMarketId}
                onSelect={onSelect}
              />
            ) : (
              <QuestionCard
                key={entry.key}
                entry={entry}
                selectedMarketId={selectedMarketId}
                onSelect={onSelect}
              />
            ),
          )
        )}
      </div>
    </section>
  )
}

export default MarketList