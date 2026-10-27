import type { OrderBook } from '../types/book'
import type { CandleRange, PriceHistory } from '../types/candle'
import type {
  OutcomeMarket,
  OutcomeMarketDetail,
} from '../types/market'

const API_BASE_URL = 'http://127.0.0.1:8000'

async function requestJson<T>(
  path: string,
  label: string,
  signal?: AbortSignal,
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, { signal })

  if (!response.ok) {
    throw new Error(
      `Failed to fetch ${label}: ${response.status} ${response.statusText}`,
    )
  }

  return (await response.json()) as T
}

export async function fetchMarkets(
  signal?: AbortSignal,
): Promise<OutcomeMarket[]> {
  return requestJson<OutcomeMarket[]>('/markets', 'markets', signal)
}

export async function fetchMarketDetail(
  marketId: string,
  signal?: AbortSignal,
): Promise<OutcomeMarketDetail> {
  return requestJson<OutcomeMarketDetail>(
    `/markets/${encodeURIComponent(marketId)}`,
    `market ${marketId}`,
    signal,
  )
}

export async function fetchPriceHistory(
  marketId: string,
  range: CandleRange,
  signal?: AbortSignal,
): Promise<PriceHistory> {
  return requestJson<PriceHistory>(
    `/markets/${encodeURIComponent(marketId)}/candles?range=${range}`,
    `price history for market ${marketId}`,
    signal,
  )
}

export async function fetchOrderBook(
  marketId: string,
  sideIndex: number,
): Promise<OrderBook> {
  return requestJson<OrderBook>(
    `/markets/${encodeURIComponent(marketId)}/book?side=${sideIndex}`,
    `order book for market ${marketId}`,
  )
}