import { fakeMarkets } from "./data/fakeMarkets"

function App() {
  return (
    <main>
      <h1>Hyperliquid Outcomes</h1>
      <p>Read-only outcome market terminal</p>
      <p>Loaded {fakeMarkets.length} fake outcome markets.</p>
    </main>
  )
}

export default App