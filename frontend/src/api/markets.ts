import type { OrderBook } from '../types/book'
import type { CandleRange, PriceHistory } from '../types/candle'
import type { DeployerStats } from '../types/deployer'
import type {
  OutcomeMarket,
  OutcomeMarketDetail,
} from '../types/market'

const API_BASE_URL = 'http://127.0.0.1:8000'

// An HTTP error from our backend that keeps its status code, so callers
// can tell "this doesn't exist" (404) from "try again later" (502)
// (Milestone 19.3). It extends Error, so existing code that only reads
// `.message` keeps working unchanged.
export class ApiError extends Error {
  readonly status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function requestJson<T>(
  path: string,
  label: string,
  signal?: AbortSignal,
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, { signal })

  if (!response.ok) {
    throw new ApiError(
      `Failed to fetch ${label}: ${response.status} ${response.statusText}`,
      response.status,
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

export async function fetchDeployers(
  signal?: AbortSignal,
): Promise<DeployerStats[]> {
  return requestJson<DeployerStats[]>('/deployers', 'deployers', signal)
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