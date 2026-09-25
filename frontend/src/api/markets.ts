import type {
  OutcomeMarket,
  OutcomeMarketDetail,
} from '../types/market'

const API_BASE_URL = 'http://127.0.0.1:8000'

async function requestJson<T>(path: string, label: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`)

  if (!response.ok) {
    throw new Error(
      `Failed to fetch ${label}: ${response.status} ${response.statusText}`,
    )
  }

  return (await response.json()) as T
}

export async function fetchMarkets(): Promise<OutcomeMarket[]> {
  return requestJson<OutcomeMarket[]>('/markets', 'markets')
}

export async function fetchMarketDetail(
  marketId: string,
): Promise<OutcomeMarketDetail> {
  return requestJson<OutcomeMarketDetail>(
    `/markets/${encodeURIComponent(marketId)}`,
    `market ${marketId}`,
  )
}