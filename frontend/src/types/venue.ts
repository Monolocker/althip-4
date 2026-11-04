// Other venues (Milestone 22). Mirrors backend/app/models/venue.py.

export type Venue = 'polymarket' | 'kalshi'

// "identical": same payout in every scenario. "comparable": same in the
// normal case, different at the edges, explained by the link's note.
export type MatchLevel = 'identical' | 'comparable'

export interface VenueQuote {
  venue: Venue
  externalId: string
  title: string
  sideLabel: string
  // Dollars per $1 contract for sideLabel; null = no order on that side
  bid: number | null
  ask: number | null
  price: number | null
  status: string
  closesAt: string | null
  rules: string
  fetchedAt: string
}

export interface VenueLink {
  id: number
  marketId: string
  venue: Venue
  externalId: string
  matchLevel: MatchLevel
  note: string
  createdAt: string
}

export interface ElsewhereEntry {
  link: VenueLink
  quote: VenueQuote | null // null = unavailable; see error
  error: string | null
}

