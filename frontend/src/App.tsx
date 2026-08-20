import MarketList from './components/MarketList'
import { fakeMarkets } from './data/fakeMarkets'

function App() {
  return (
    <main>
      <h1>Hyperliquid Outcomes</h1>
      <p>Read-only outcome market terminal</p>

      <MarketList markets={fakeMarkets} />
    </main>
  )
}

export default App