import { useEffect, useState } from "react"
import { fetchMarkets } from "./api/markets"
import MarketDetail from "./components/MarketDetail"
import MarketList from "./components/MarketList"
import type { OutcomeMarket } from "./types/market"

function App() {
  const [markets, setMarkets] = useState<OutcomeMarket[]>([])
  const [selectedMarketId, setSelectedMarketId] =
    useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const selectedMarket =
    markets.find(
      (market) => market.id === selectedMarketId,
    ) ?? null

  useEffect(() => {
    let ignore = false

    async function loadMarkets() {
      try {
        const fetchedMarkets = await fetchMarkets()

        if (!ignore) {
          setMarkets(fetchedMarkets)
        }
      } catch (caughtError) {
        if (!ignore) {
          const message = 
            caughtError instanceof Error
              ? caughtError.message
              : "An unknown error occurred"

              setError(message)
        }
      } finally {
        if(!ignore) {
          setIsLoading(false)
        }
      }
    }

    loadMarkets()

    return () => {
      ignore = true
    }
  }, [])

  function handleSelectMarket(marketId: string) {
    setSelectedMarketId(marketId)
  }

  let workspaceTitle = "Select a market"
  let workspaceMessage = 
    "Choose a market from the list to inspect its details"

  if (isLoading) {
    workspaceTitle = "Loading markets"
    workspaceMessage = "Waiting for market data from the API"
  } else if (error) {
    workspaceTitle = "Markets unavailable"
    workspaceMessage = error
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
          {isLoading ? (
            <p className="request-status">Loading markets...</p>
          ) : error ? (
            <div className="request-status request-status--error">
              <strong>Failed to load markets</strong>
              <p>{error}</p>
            </div>
          ) : (
            <MarketList
              markets={markets}
              selectedMarketId={selectedMarketId}
              onSelect={handleSelectMarket}
            />
          )}
        </aside>

        <section className="market-workspace">
          {selectedMarket ? (
            <MarketDetail market={selectedMarket} />
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