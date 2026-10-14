import type { OutcomeMarket } from '../../types/market'

// Discovery logic: pure functions that take markets in and return
// markets out. No React, no fetching, no state. Every discovery
// feature in Milestone 17 (search, close-time buckets, sort modes)
// lands here as another small function the UI composes.

// Default triage order (moved unchanged from App.tsx): markets with a
// parsed, human-readable question first, then soonest close time.
export function sortMarkets(markets: OutcomeMarket[]): OutcomeMarket[] {
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