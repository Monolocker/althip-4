import { useState } from "react"
import { useMarketDetail, useMarkets } from "./api/queries"
import MarketDetail from "./components/MarketDetail"
import MarketList from "./components/MarketList"
import MarketSearch from "./components/MarketSearch"
import { searchMarkets, sortMarkets } from "./features/markets/discovery"

function App() {
  const [selectedMarketId, setSelectedMarketId] =
    useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState("")

  const marketsQuery = useMarkets()
  const detailQuery = useMarketDetail(selectedMarketId)

  const markets = marketsQuery.data ?? []

  // Derived, not stored: the visible list is recomputed from the
  // server data and the query on every render, so it can never drift
  // out of sync with either of them.
  const visibleMarkets = sortMarkets(searchMarkets(markets, searchQuery))

  // Errors only matter when there is no data to show. A failed
  // background refetch keeps the last good data on screen.
  const listError =
    marketsQuery.data === undefined && marketsQuery.error !== null
      ? marketsQuery.error.message
      : null

  const detail = detailQuery.data ?? null
  const detailError =
    detail === null && detailQuery.error !== null
      ? detailQuery.error.message
      : null

  // A market can settle and drop out of the refreshed list while it is
  // selected. The detail response is an OutcomeMarket too, so it keeps
  // the panel populated.
  // Looked up in the full list, not visibleMarkets: narrowing the
  // search must not close the market currently being inspected.
  const selectedMarket =
    markets.find((market) => market.id === selectedMarketId) ?? detail

  function handleSelectMarket(marketId: string) {
    setSelectedMarketId(marketId)
  }

  let workspaceTitle = "Select a market"
  let workspaceMessage =
    "Choose a market from the list to inspect its details"

  if (marketsQuery.isPending) {
    workspaceTitle = "Loading markets"
    workspaceMessage = "Waiting for market data from the API"
  } else if (listError !== null) {
    workspaceTitle = "Markets unavailable"
    workspaceMessage = listError
  }

  return (
    <main className="app-shell">
      <header className="app-header">
        <div>
          <h1>Hyperliquid Outcomes</h1>
          <p>Read-only outcome market terminal</p>
        </div>
      </header>

      <div className="terminal-layout">
        <aside className="market-sidebar">
          {marketsQuery.isPending ? (
            <p className="request-status">Loading markets...</p>
          ) : listError !== null ? (
            <div className="request-status request-status--error">
              <strong>Failed to load markets</strong>
              <p>{listError}</p>
            </div>
          ) : (
            <>
              <MarketSearch
                value={searchQuery}
                onChange={setSearchQuery}
                resultCount={visibleMarkets.length}
                totalCount={markets.length}
              />
              <MarketList
                markets={visibleMarkets}
                selectedMarketId={selectedMarketId}
                onSelect={handleSelectMarket}
              />
            </>
          )}
        </aside>

        <section className="market-workspace">
          {selectedMarket !== null ? (
            <MarketDetail
              market={selectedMarket}
              detail={detail}
              detailError={detailError}
            />
          ) : (
            <div className="market-detail-empty">
              <h2>{workspaceTitle}</h2>
              <p>{workspaceMessage}</p>
            </div>
          )}
        </section>
      </div>
    </main>
  )
}

export default App