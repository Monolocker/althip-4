// Trader leaderboard (Milestone 23.4)
// Mirrors backend/app/models/leaderboard.py

export type LeaderboardWindow = '24h' | '7d' | '30d' | 'all'
export type LeaderboardSort = 'pnl' | 'volume' | 'fills'
// "full": every fill inside the window is stored. "partial": this
// trader's stored history starts after the window does (or is not
// verified yet: coverageFrom null).
export type Coverage = 'full' | 'partial'

export interface LeaderboardRow {
  address: string
  netPnl: number // grossPnl - fees, USDC
  grossPnl: number
  tradingPnl: number // Buy / Sell fills
  settlementPnl: number // Settlement fills
  conversionPnl: number // merges, splits, negations
  fees: number
  volume: number // USDC notional of Buy / Sell fills only
  fills: number
  markets: number // distinct outcomes
  settlementsWon: number
  settlementsLost: number
  settlementsFractional: number
  coverage: Coverage
  coverageFrom: string | null // null: completeness not known yet
  fillsThrough: string
  behind: boolean // trades seen that are not fetched yet
}

export interface Leaderboard {
  window: LeaderboardWindow
  sort: LeaderboardSort
  windowStart: string | null
  trackingSince: string | null
  generatedAt: string
  tradersKnown: number
  tradersPending: number
  tradersRanked: number
  rows: LeaderboardRow[] // best first, the first `limit` only
}