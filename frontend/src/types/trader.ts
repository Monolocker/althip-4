// One trader's HIP-4 dashboard (Milestone 26.2 backend, 26.3 frontend)
// Mirrors backend/app/models/trader.py

import type { LeaderboardWindow } from './leaderboard'

export interface TraderStats {
  netPnl: number // realized, after fees, USDC
  grossPnl: number
  fees: number
  volume: number // Buy / Sell notional
  markets: number
  wins: number // markets with something realized and net PnL above 0
  losses: number
  accuracy: number | null // wins / (wins + losses)
}

export interface BiggestWin {
  marketId: string
  title: string | null
  netPnl: number
}

export interface PnlPoint {
  time: string
  pnl: number // cumulative net realized PnL
}

export interface ResolvedMarket {
  marketId: string
  title: string | null
  netPnl: number
  fees: number
  volume: number
  result: 'win' | 'loss' | 'even'
  settled: boolean // false: closed out by selling or converting
  lastFillAt: string
}

export interface TraderPosition {
  coin: string
  marketId: string
  title: string
  sideLabel: string
  shares: number
  onHold: number // locked by open orders
  entryNotional: number | null // cost basis
  price: number | null
  value: number | null
}

export interface TraderPositions {
  value: number
  unpriced: number
  count: number
  biggest: TraderPosition | null
  items: TraderPosition[]
}

export interface TraderOrder {
  coin: string
  marketId: string
  title: string | null
  sideLabel: string | null
  direction: 'buy' | 'sell'
  price: number
  size: number
  originalSize: number
  placedAt: string
  orderType: string | null
  tif: string | null
  reduceOnly: boolean
}

export interface TraderDashboard {
  address: string
  window: LeaderboardWindow
  windowStart: string | null
  generatedAt: string
  complete: boolean
  historyFrom: string | null
  fillsThrough: string | null
  stats: TraderStats
  biggestWin: BiggestWin | null
  pnlSeries: PnlPoint[]
  resolved: ResolvedMarket[]
  // Live parts: null when Hyperliquid could not be reached (liveError says why)
  positions: TraderPositions | null
  orders: TraderOrder[] | null
  liveError: string | null
}