// Price history. Mirrors backend/app/models/candle.py

export type CandleRange = '1d' | '1w' | '1m' | 'all'

export interface Candle {
    time: string    // interval start, ISO UTC
    open: number
    high: number
    low: number
    close: number
    volume: number
    // Can be 0: HL records some intervals w/o trades
    trades: number
}

export interface PriceHistory {
    marketId: string
    coin: string
    range: CandleRange
    interval: string    // e.g. "1h"
    candles: Candle[]
    fetchedAt: string
}