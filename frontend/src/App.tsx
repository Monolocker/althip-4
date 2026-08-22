import { useState } from 'react'
import MarketDetail from './components/MarketDetail'
import MarketList from './components/MarketList'
import { fakeMarkets } from './data/fakeMarkets'

function App() {
  const [selectedMarketId, setSelectedMarketId] =
    useState<string | null>(null)

  const selectedMarket =
    fakeMarkets.find(
      (market) => market.id === selectedMarketId,
    ) ?? null

  function handleSelectMarket(marketId: string) {
    setSelectedMarketId(marketId)
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
          <MarketList
            markets={fakeMarkets}
            selectedMarketId={selectedMarketId}
            onSelect={handleSelectMarket}
          />
        </aside>

        <section className="market-workspace">
          {selectedMarket ? (
            <MarketDetail market={selectedMarket} />
          ) : (
            <div className="market-detail-empty">
              <h2>Select a market</h2>
              <p>
                Choose a market from the list to inspect its
                details.
              </p>
            </div>
          )}
        </section>
      </div>
    </main>
  )
}

export default App