import type { OutcomeMarket } from '../../types/market'
import { isPriceUnreliable } from './pricing'

// Grouping (Milestone 18.6b): the market list shows ENTRIES, where an
// entry is either one standalone market or one multi-outcome question
// holding its outcomes. Filtering still happens on individual outcomes
// (so the 17.4 facet counts are unchanged); grouping happens after.

export interface MarketEntry {
  kind: 'market'
  key: string
  market: OutcomeMarket
}

export interface QuestionEntry {
  kind: 'question'
  // Prefixed so a question key can never equal a market id in React.
  key: string
  id: string
  title: string
  // Visible named outcomes, usable prices first, highest price first.
  named: OutcomeMarket[]
  // The visible fallback outcome, if it passed the filters.
  fallback: OutcomeMarket | null
  // Named outcomes in the WHOLE question, for "1 of 3 outcomes match".
  totalNamed: number
}

// A discriminated union: the `kind` field tells TypeScript (and us)
// which of the two shapes an entry has.
export type ListEntry = MarketEntry | QuestionEntry

export function entryMembers(entry: ListEntry): OutcomeMarket[] {
  if (entry.kind === 'market') {
    return [entry.market]
  }
  // Narrowing: here TypeScript knows `entry` is a QuestionEntry.
  return entry.fallback !== null ? [...entry.named, entry.fallback] : entry.named
}

function countNamedByQuestion(markets: OutcomeMarket[]): Map<string, number> {
  const counts = new Map<string, number>()
  for (const market of markets) {
    if (market.parent?.role === 'named') {
      const id = market.parent.id
      counts.set(id, (counts.get(id) ?? 0) + 1)
    }
  }
  return counts
}

// Rows inside a question card: usable prices first, then by price,
// highest first, so the market's favourite leads.
function compareRows(a: OutcomeMarket, b: OutcomeMarket): number {
  const aRank = isPriceUnreliable(a) ? 1 : 0
  const bRank = isPriceUnreliable(b) ? 1 : 0
  if (aRank !== bRank) {
    return aRank - bRank
  }
  return (b.sides[0]?.price ?? -1) - (a.sides[0]?.price ?? -1)
}

// `visible` is the filtered outcomes; `all` is every outcome, used only
// to know how many named outcomes each question has in total.
export function groupEntries(
  visible: OutcomeMarket[],
  all: OutcomeMarket[],
): ListEntry[] {
  const totals = countNamedByQuestion(all)
  const entries: ListEntry[] = []
  const questions = new Map<string, QuestionEntry>()

  for (const market of visible) {
    const parent = market.parent
    if (parent === null) {
      entries.push({ kind: 'market', key: market.id, market })
      continue
    }

    let entry = questions.get(parent.id)
    if (entry === undefined) {
      entry = {
        kind: 'question',
        key: `q:${parent.id}`,
        id: parent.id,
        title: parent.title ?? `Question ${parent.id}`,
        named: [],
        fallback: null,
        totalNamed: totals.get(parent.id) ?? 0,
      }
      questions.set(parent.id, entry)
      entries.push(entry)
    }

    if (parent.role === 'fallback') {
      entry.fallback = market
    } else {
      entry.named.push(market)
    }
  }

  // These arrays were created above, so sorting them in place is safe:
  // nothing else holds a reference to them yet.
  for (const entry of questions.values()) {
    entry.named.sort(compareRows)
  }
  return entries
}