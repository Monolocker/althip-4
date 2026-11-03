// Price history. Mirrors backend/app/models/candle.py

export type CandleRange = '1d' | '1w' | '1m' | 'all'

// "hyperliquid": Hyperliquid's own candles (live markets).
// "recorded": this app's 5-minute recordings, used once Hyperliquid has
// deleted a settled market's candles (Milestone 21.3).
export type HistorySource = 'hyperliquid' | 'recorded'

export interface Candle {
    time: string    // interval start, ISO UTC
    open: number
    high: number
    low: number
    close: number
    // null = unknown (recorded history keeps no per-interval volume)
    volume: number | null
    // Can be 0: HL records some intervals w/o trades. null = unknown.
    trades: number | null
}

export interface PriceHistory {
    marketId: string
    coin: string
    range: CandleRange
    interval: string    // e.g. "1h"
    candles: Candle[]
    fetchedAt: string
    source: HistorySource
}