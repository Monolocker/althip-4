import type { OutcomeMarket } from '../types/market'

const API_BASE_URL = 'http://127.0.0.1:8000'

export async function fetchMarkets(): Promise<OutcomeMarket[]> {
  const response = await fetch(`${API_BASE_URL}/markets`)

  if (!response.ok) {
    throw new Error(
      `Failed to fetch markets: ${response.status} ${response.statusText}`,
    )
  }

  const data = (await response.json()) as OutcomeMarket[]

  return data
}