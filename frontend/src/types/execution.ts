// Execution Costs (M22.4). Mirrors backend/app/models/costs.py
import type { MatchLevel } from './venue'

export type ExecutionVenue = 'hyperliquid' | 'polymarket' | 'kalshi'

export interface VenueCost { 
    venue: ExecutionVenue
    externalId: string | null   // null for HL
    title: string
    matchLevel: MatchLevel | null
    filled: number
    unfilled: number
    bestAsk: number | null
    mid: number | null
    averagePrice: number | null
    slippage: number | null     // averagePrice - bestAsk
    feeNow: number  // $ paid when buying
    feeIfWins: number // $ taken at settlement if it wins (Hyperliquid)
    costPerContract: number | null
    breakEven: number | null    // probability at which buying here breaks even
    feeBasis: string
    warnings: string[]
    bookTime: string | null
    error: string | null
}

export interface ExecutionEstimate {
    marketId: string
    size: number
    settlesAt: string | null
    assumptions: string[]
    venues: VenueCost[]
}