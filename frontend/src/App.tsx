import { useState } from "react"
import { useMarketDetail, useMarkets } from "./api/queries"
import MarketDetail from "./components/MarketDetail"
import MarketList from "./components/MarketList"
import type { OutcomeMarket } from "./types/market"

function sortMarkets(markets: OutcomeMarket[]): OutcomeMarket[] {
  return [...markets].sort((a, b) => {
    const aParsed = a.question !== a.description
    const bParsed = b.question !== b.description
    if (aParsed !== bParsed) {
      return aParsed ? -1 : 1
    }

    if (a.closesAt !== null && b.closesAt !== null) {
      return a.closesAt.localeCompare(b.closesAt)
    }
    if (a.closesAt !== null) return -1
    if (b.closesAt !== null) return 1
    return 0
  })
}

function App() {
  const [selectedMarketId, setSelectedMarketId] =
    useState<string | null>(null)

  const marketsQuery = useMarkets()
  const detailQuery = useMarketDetail(selectedMarketId)

  const markets = marketsQuery.data ?? []
  const displayMarkets = sortMarkets(markets)

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
            <MarketList
              markets={displayMarkets}
              selectedMarketId={selectedMarketId}
              onSelect={handleSelectMarket}
            />
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