// Trader leaderboard (Milestone 23.4, v2 in 26.1)
// Mirrors backend/app/models/leaderboard.py

export type LeaderboardWindow = '24h' | '7d' | '30d' | 'all'

// Only traders whose stored fills are complete for the window get a
// row, so rows carry no coverage flags.
export interface LeaderboardRow {
  address: string
  netPnl: number // grossPnl - fees, USDC: the ranking measure
  grossPnl: number
  tradingPnl: number // Buy / Sell fills
  settlementPnl: number // Settlement fills
  conversionPnl: number // merges, splits, negations
  fees: number
  volume: number // USDC notional of Buy / Sell fills only
  markets: number // distinct outcomes
  // Per market: a market with something realized in the window is a
  // win if its net PnL is above 0, a loss if below.
  wins: number
  losses: number
}

export interface Leaderboard {
  window: LeaderboardWindow
  windowStart: string | null // null for All-Time: each trader's own history
  generatedAt: string
  tradersKnown: number
  tradersPending: number
  tradersRanked: number
  tradersExcluded: number // history does not cover this window yet
  rows: LeaderboardRow[] // best first, the first `limit` only
}