import { useState } from "react"
import { useMarketDetail, useMarkets } from "./api/queries"
import ActiveFilters, { type ActiveFilter } from "./components/ActiveFilters"
import ChipFilter from "./components/ChipFilter"
import CloseBucketFilter from "./components/CloseBucketFilter"
import DeployerDirectory from "./components/DeployerDirectory"
import MarketDetail from "./components/MarketDetail"
import MarketList from "./components/MarketList"
import MarketSearch from "./components/MarketSearch"
import MarketSort from "./components/MarketSort"
import SidebarViewSwitch, {
  type SidebarView,
} from "./components/SidebarViewSwitch"
import {
  CLOSE_FILTER_LABELS,
  categoryLabel,
  countByCategory,
  countByVenue,
  countCloseBuckets,
  filterByCategory,
  filterByCloseBucket,
  filterByVenue,
  listCategories,
  listVenues,
  searchMarkets,
  sortEntries,
  venueLabel,
  type CloseFilter,
  type SortMode,
} from "./features/markets/discovery"
import { groupEntries } from "./features/markets/grouping"
import { useNow } from "./hooks/useNow"

// Bucket boundaries are hours and days apart; re-evaluating them once
// a minute is far more precise than they need.
const CLOCK_TICK_MS = 60_000

function App() {
  const [selectedMarketId, setSelectedMarketId] =
    useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState("")
  const [closeFilter, setCloseFilter] = useState<CloseFilter>("all")
  const [sortMode, setSortMode] = useState<SortMode>("default")
  // null = all deployers; "" = markets with no venue.
  const [venueFilter, setVenueFilter] = useState<string | null>(null)
  const [sidebarView, setSidebarView] = useState<SidebarView>("markets")
  // null = all categories.
  const [categoryFilter, setCategoryFilter] = useState<string | null>(null)

  const now = useNow(CLOCK_TICK_MS)
  const marketsQuery = useMarkets()
  const detailQuery = useMarketDetail(selectedMarketId)

  const markets = marketsQuery.data ?? []

  // Discovery pipeline, all derived on every render:
  //   search -> category + deployer + time filters -> group -> sort
  // Faceted counts: each chip group counts the markets that pass every
  // OTHER active filter, so a chip's number is exactly how many markets
  // you would see by clicking it. With three facets, each count set
  // applies the two filters that are not its own.
  const searchedMarkets = searchMarkets(markets, searchQuery)
  const byCategory = filterByCategory(searchedMarkets, categoryFilter)
  const byCategoryVenue = filterByVenue(byCategory, venueFilter)
  const byCategoryTime = filterByCloseBucket(byCategory, closeFilter, now)
  const byVenueTime = filterByCloseBucket(
    filterByVenue(searchedMarkets, venueFilter),
    closeFilter,
    now,
  )

  const categoryCounts = countByCategory(byVenueTime)
  const venueCounts = countByVenue(byCategoryTime)
  const closeCounts = countCloseBuckets(byCategoryVenue, now)
  // Chip order comes from the full list so it doesn't jump around.
  const categories = listCategories(markets)
  const venues = listVenues(markets)

  // Filters work on outcomes; then outcomes of the same question are
  // grouped into one card, and the cards are sorted (Milestone 18.6b).
  const visibleMarkets = filterByCloseBucket(byCategoryVenue, closeFilter, now)
  const entries = sortEntries(
    groupEntries(visibleMarkets, markets),
    sortMode,
    now,
  )

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

  // Every filter currently narrowing the list, each with its own way to
  // undo it (Milestone 20.1d). Built from the same state the chips use,
  // so the two can never disagree. Sort order is not a filter: it never
  // hides a market, so it is not listed and not reset.
  const activeFilters: ActiveFilter[] = []
  if (searchQuery.trim() !== "") {
    activeFilters.push({
      key: "search",
      label: `Search: “${searchQuery.trim()}”`,
      onRemove: () => setSearchQuery(""),
    })
  }
  if (categoryFilter !== null) {
    activeFilters.push({
      key: "category",
      label: `Category: ${categoryLabel(categoryFilter)}`,
      onRemove: () => setCategoryFilter(null),
    })
  }
  if (venueFilter !== null) {
    activeFilters.push({
      key: "deployer",
      label: `Deployer: ${venueLabel(venueFilter)}`,
      onRemove: () => setVenueFilter(null),
    })
  }
  if (closeFilter !== "all") {
    activeFilters.push({
      key: "time",
      label: `Time: ${CLOSE_FILTER_LABELS[closeFilter]}`,
      onRemove: () => setCloseFilter("all"),
    })
  }

  // Four state updates in one click handler are batched by React into a
  // single re-render, so the list never flashes a half-reset state.
  function resetFilters() {
    setSearchQuery("")
    setCategoryFilter(null)
    setVenueFilter(null)
    setCloseFilter("all")
  }
  
  // Decision 1: choosing a deployer reuses the 17.4 deployer filter
  // then shows the market list it now filters 
  function handleSelectVenue(venue: string) {
    setVenueFilter(venue)
    setSidebarView("markets")
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
          <SidebarViewSwitch value={sidebarView} onChange={setSidebarView} />
          
          {sidebarView === "deployers" ? (
            <DeployerDirectory
              activeVenue={venueFilter}
              onSelectVenue={handleSelectVenue}
              />
          ) : marketsQuery.isPending ? (
            <p className="request-status">Loading markets...</p>
          ) : listError !== null ? (
            <div className="request-status request-status--error">
              <strong>Failed to load markets</strong>
              <p>{listError}</p>
            </div>
          ) : (
            <>
              <div className="market-controls">
                <ActiveFilters
                  filters={activeFilters}
                  onResetAll={resetFilters}
                  />
                <MarketSearch
                  value={searchQuery}
                  onChange={setSearchQuery}
                  resultCount={searchedMarkets.length}
                  totalCount={markets.length}
                />
                <ChipFilter
                  label="Category"
                  options={categories}
                  counts={categoryCounts}
                  totalCount={byVenueTime.length}
                  value={categoryFilter}
                  onChange={setCategoryFilter}
                  formatLabel={categoryLabel}
                />
                <ChipFilter
                  label="Deployer"
                  options={venues}
                  counts={venueCounts}
                  totalCount={byCategoryTime.length}
                  value={venueFilter}
                  onChange={setVenueFilter}
                  formatLabel={venueLabel}
                />
                <CloseBucketFilter
                  value={closeFilter}
                  onChange={setCloseFilter}
                  counts={closeCounts}
                />
                <MarketSort value={sortMode} onChange={setSortMode} />
              </div>
              <MarketList
                entries={entries}
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