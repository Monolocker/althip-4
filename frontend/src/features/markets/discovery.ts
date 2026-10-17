import type { OutcomeMarket } from '../../types/market'

// Discovery logic: pure functions that take markets in and return
// markets out. No React, no fetching, no state. Every discovery
// feature in Milestone 17 (search, time buckets, sort modes) lands
// here as another small function the UI composes.
//
// Pipeline (see App.tsx): search -> deployer + time filters -> sort

// ---------------------------------------------------------------
// Discovery time
// ---------------------------------------------------------------

// The one time discovery features use (decision from Milestone 17.2):
// when the deciding event happens, falling back to the resolution
// deadline for markets that have no scheduled event (tournaments,
// awards, IPOs). Changing this rule changes buckets and sorting
// together, because both go through this function.
function discoveryTime(market: OutcomeMarket): string | null {
  return market.eventAt ?? market.resolvesBy
}

// ---------------------------------------------------------------
// Search
// ---------------------------------------------------------------

// "  BTC   Touch " -> ["btc", "touch"]. An empty or whitespace-only
// query produces no terms, which means "no filter".
function parseSearchTerms(query: string): string[] {
  const trimmed = query.trim().toLowerCase()
  return trimmed === '' ? [] : trimmed.split(/\s+/)
}

// The text a market can be found by. Deliberately limited to what the
// user can see or paste: the displayed question, the market id, and
// the side coins (e.g. "#12100"). The raw spec keys are left out so
// a search never matches on something invisible.
function searchableText(market: OutcomeMarket): string {
  return [
    market.question,
    market.id,
    ...market.sides.map((side) => side.coin),
  ]
    .join(' ')
    .toLowerCase()
}

// Every term must appear somewhere in the market's text (AND match),
// so each extra word narrows the results.
export function searchMarkets(
  markets: OutcomeMarket[],
  query: string,
): OutcomeMarket[] {
  const terms = parseSearchTerms(query)
  if (terms.length === 0) {
    return markets
  }

  return markets.filter((market) => {
    const text = searchableText(market)
    return terms.every((term) => text.includes(term))
  })
}

// ---------------------------------------------------------------
// Time buckets
// ---------------------------------------------------------------

const HOUR_MS = 60 * 60 * 1000
const DAY_MS = 24 * HOUR_MS

// Every market falls into exactly one bucket.
export type CloseBucket =
  | 'awaiting'
  | 'under-24h'
  | '1-7d'
  | 'over-7d'
  | 'undated'

// A filter is either one bucket or no filtering at all.
export type CloseFilter = 'all' | CloseBucket

// Display order of the filter chips.
export const CLOSE_FILTERS: CloseFilter[] = [
  'all',
  'awaiting',
  'under-24h',
  '1-7d',
  'over-7d',
  'undated',
]

// Record<CloseFilter, string> forces a label for every member of the
// union: adding a bucket without a label is a compile error.
export const CLOSE_FILTER_LABELS: Record<CloseFilter, string> = {
  all: 'All',
  awaiting: 'Awaiting result',
  'under-24h': '< 24h',
  '1-7d': '1–7d',
  'over-7d': '> 7d',
  undated: 'No date',
}

// Boundaries: under-24h is (0, 24h); 1-7d is [24h, 7d]; over-7d is
// beyond 7d. "awaiting" means the discovery time has passed but the
// market is still listed as open: the event happened (or the game is
// in progress) and the market has not settled yet.
export function getCloseBucket(
  market: OutcomeMarket,
  now: number,
): CloseBucket {
  const time = discoveryTime(market)
  if (time === null) {
    return 'undated'
  }

  const timeMs = Date.parse(time)
  if (Number.isNaN(timeMs)) {
    return 'undated'
  }

  const remainingMs = timeMs - now
  if (remainingMs <= 0) return 'awaiting'
  if (remainingMs < DAY_MS) return 'under-24h'
  if (remainingMs <= 7 * DAY_MS) return '1-7d'
  return 'over-7d'
}

export function filterByCloseBucket(
  markets: OutcomeMarket[],
  filter: CloseFilter,
  now: number,
): OutcomeMarket[] {
  if (filter === 'all') {
    return markets
  }
  // Narrowing: past this point TypeScript knows `filter` is a
  // CloseBucket, so comparing it to getCloseBucket()'s result is valid.
  return markets.filter((market) => getCloseBucket(market, now) === filter)
}

export function countCloseBuckets(
  markets: OutcomeMarket[],
  now: number,
): Record<CloseFilter, number> {
  const counts: Record<CloseFilter, number> = {
    all: markets.length,
    awaiting: 0,
    'under-24h': 0,
    '1-7d': 0,
    'over-7d': 0,
    undated: 0,
  }

  for (const market of markets) {
    counts[getCloseBucket(market, now)] += 1
  }

  return counts
}

// ---------------------------------------------------------------
// Deployers
// ---------------------------------------------------------------

// Each deployer owns exactly one venue (one entry per venue in
// outcomeMeta.deployers), so filtering by venue is filtering by
// deployer. Unlike time buckets, venues are an OPEN set: new deployers
// can appear at any time, so a venue is a plain string, not a union,
// and the list of venues is derived from the data instead of hard-coded.

// The backend sends "" for markets with no venue (Hyperliquid's
// "Recurring" markets). "" is a real value meaning "no venue"; it is
// different from the filter value null, which means "all deployers".
export function venueLabel(venue: string): string {
    return venue === '' ? 'Hyperliquid' : venue
  }
  
  export function countByVenue(markets: OutcomeMarket[]): Map<string, number> {
    const counts = new Map<string, number>()
    for (const market of markets) {
      counts.set(market.venue, (counts.get(market.venue) ?? 0) + 1)
    }
    return counts
  }
  
  // Every venue present in the data, largest first (ties by name). Taken
  // from the full market list so the chip order stays put while other
  // filters change the counts.
  export function listVenues(markets: OutcomeMarket[]): string[] {
    return [...countByVenue(markets).entries()]
      .sort(([aVenue, aCount], [bVenue, bCount]) =>
        bCount !== aCount ? bCount - aCount : aVenue.localeCompare(bVenue),
      )
      .map(([venue]) => venue)
  }
  
  // null means "no deployer filter".
  export function filterByVenue(
    markets: OutcomeMarket[],
    venue: string | null,
  ): OutcomeMarket[] {
    if (venue === null) {
      return markets
    }
    return markets.filter((market) => market.venue === venue)
  }

// ---------------------------------------------------------------
// Sorting
// ---------------------------------------------------------------

export type SortMode = 'default' | 'trending' | 'soonest' | 'newest'

// Display order of the sort options.
export const SORT_MODES: SortMode[] = ['default', 'trending', 'soonest', 'newest']

export const SORT_MODE_LABELS: Record<SortMode, string> = {
  default: 'Recommended',
  trending: 'Trending (24h volume)',
  soonest: 'Happening soonest',
  newest: 'Newest',
}

// Type predicate: when this returns true, TypeScript narrows `value`
// from string to SortMode in the caller. This is how untyped input
// (a <select>'s value is always a plain string) becomes a typed value
// without lying to the compiler with `as SortMode`.
export function isSortMode(value: string): value is SortMode {
  return (SORT_MODES as readonly string[]).includes(value)
}

// Earliest first; markets without a time go last.
function compareTimes(a: string | null, b: string | null): number {
  if (a !== null && b !== null) return a.localeCompare(b)
  if (a !== null) return -1
  if (b !== null) return 1
  return 0
}

// Recommended: markets with a parsed, human-readable question first,
// then soonest discovery time. (Unchanged triage order from 17.2.)
function compareDefault(a: OutcomeMarket, b: OutcomeMarket): number {
  const aParsed = a.question !== a.description
  const bParsed = b.question !== b.description
  if (aParsed !== bParsed) {
    return aParsed ? -1 : 1
  }
  return compareTimes(discoveryTime(a), discoveryTime(b))
}

// Tiers for "happening soonest": upcoming events, then events that
// already happened but have not settled, then undated markets.
function soonestTier(market: OutcomeMarket, now: number): number {
  const bucket = getCloseBucket(market, now)
  if (bucket === 'awaiting') return 1
  if (bucket === 'undated') return 2
  return 0
}

// Happening soonest: ignores question quality entirely. Within the
// upcoming tier the nearest event comes first; within the awaiting
// tier the most recently passed event comes first.
function compareSoonest(
  a: OutcomeMarket,
  b: OutcomeMarket,
  now: number,
): number {
  const tierDiff = soonestTier(a, now) - soonestTier(b, now)
  if (tierDiff !== 0) {
    return tierDiff
  }

  const timeOrder = compareTimes(discoveryTime(a), discoveryTime(b))
  return soonestTier(a, now) === 1 ? -timeOrder : timeOrder
}

// Newest: highest outcome id first. ASSUMPTION: Hyperliquid assigns
// outcome ids in increasing order as markets are created. Observed in
// live data (e.g. later recurring BTC markets have higher ids), but
// not stated in the official docs.
function compareNewest(a: OutcomeMarket, b: OutcomeMarket): number {
  return Number(b.id) - Number(a.id)
}

// Trending (decision from Milestone 17.5): highest 24h volume first.
// Unknown volume (null) sorts after every known volume, including 0:
// "no trades" is information, "no data" is not.
function compareTrending(a: OutcomeMarket, b: OutcomeMarket): number {
    if (a.volume24h !== null && b.volume24h !== null) {
      return b.volume24h - a.volume24h
    }
    if (a.volume24h !== null) return -1
    if (b.volume24h !== null) return 1
    return 0
  }


export function sortMarkets(
  markets: OutcomeMarket[],
  mode: SortMode,
  now: number,
): OutcomeMarket[] {
  // Copy first: Array.prototype.sort mutates in place, and `markets`
  // may be TanStack Query's cached array, which must never be mutated.
  const sorted = [...markets]

  switch (mode) {
    case 'default':
        return sorted.sort(compareDefault)
    case 'trending':
        return sorted.sort(compareTrending)
    case 'soonest':
        return sorted.sort((a, b) => compareSoonest(a, b, now))
    case 'newest':
        return sorted.sort(compareNewest)
  }
}