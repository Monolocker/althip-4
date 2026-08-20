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
    <main>
      <h1>Hyperliquid Outcomes</h1>
      <p>Read-only outcome market terminal</p>

      <MarketList
        markets={fakeMarkets}
        selectedMarketId={selectedMarketId}
        onSelect={handleSelectMarket}
      />

      {selectedMarket ? (
        <MarketDetail market={selectedMarket} />
      ) : (
        <p className="market-detail-empty">
          Select a market to view its details.
        </p>
      )}
    </main>
  )
}

export default App