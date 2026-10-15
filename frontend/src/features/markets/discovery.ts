import type { OutcomeMarket } from '../../types/market'

// Discovery logic: pure functions that take markets in and return
// markets out. No React, no fetching, no state. Every discovery
// feature in Milestone 17 (search, time buckets, sort modes) lands
// here as another small function the UI composes.

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

// Default triage order: markets with a parsed, human-readable
// question first, then soonest discovery time.
export function sortMarkets(markets: OutcomeMarket[]): OutcomeMarket[] {
  return [...markets].sort((a, b) => {
    const aParsed = a.question !== a.description
    const bParsed = b.question !== b.description
    if (aParsed !== bParsed) {
      return aParsed ? -1 : 1
    }

    const aTime = discoveryTime(a)
    const bTime = discoveryTime(b)
    if (aTime !== null && bTime !== null) {
      return aTime.localeCompare(bTime)
    }
    if (aTime !== null) return -1
    if (bTime !== null) return 1
    return 0
  })
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