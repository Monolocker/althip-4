import type { Lookalike } from '../../types/market'
import { venueLabel } from './discovery'

// Wording for lookalike warnings (Milestone 20.3). Pure functions, so
// the card and the detail panel describe a lookalike the same way.

// "listingDeadline" -> "listing deadline", "priceDescription" ->
// "price description". Spec keys are camelCase; a regex inserts a space
// before each capital letter, then everything is lower-cased.
export function humanizeSpecKey(key: string): string {
  return key.replace(/([A-Z])/g, ' $1').toLowerCase().trim()
}

// "⚠ Same title on txyz, skew — different listing deadline"
export function lookalikeSummary(lookalikes: Lookalike[]): string {
  const venues = [...new Set(lookalikes.map((l) => venueLabel(l.venue)))]
  const keys = [
    ...new Set(lookalikes.flatMap((l) => l.differences.map((d) => d.key))),
  ].map(humanizeSpecKey)
  return `Same title on ${venues.join(', ')} — different ${keys.join(', ')}`
}