import type { OrderBook } from '../types/book'
import type { CandleRange, PriceHistory } from '../types/candle'
import type { DeployerStats } from '../types/deployer'
import type { Leaderboard, LeaderboardSort, LeaderboardWindow } from '../types/leaderboard'
import type { ExecutionEstimate } from '../types/execution'
import type {
  OutcomeMarket,
  OutcomeMarketDetail,
} from '../types/market'
import type { 
  ElsewhereEntry,
  LinkGroupCreate,
  Suggestion,
  VenueLink,
  Venue, 
  VenueQuote,
} from '../types/venue'

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

// Writes (Milestone 22.3b): POST and DELETE with a JSON body. Errors
// carry the backend's own explanation ("detail"), e.g. why a link was
// refused, so the form can show it instead of a bare status code.
async function sendJson<T>(
  path: string,
  label: string,
  method: 'POST' | 'DELETE',
  body?: unknown,
): Promise<T | null> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers: body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })

  if (!response.ok) {
    let detail = response.statusText
    try {
      const data: unknown = await response.json()
      if (typeof data === 'object' && data !== null && 'detail' in data) {
        detail = String((data as { detail: unknown }).detail)
      }
    } catch {
      // No JSON body: keep the status text.
    }
    throw new ApiError(`Could not ${label}: ${detail}`, response.status)
  }

  // 204 No Content has no body to parse.
  return response.status === 204 ? null : ((await response.json()) as T)
}

export async function fetchSuggestions(
  questionId: string,
  signal?: AbortSignal,
): Promise<Suggestion[]> {
  return requestJson<Suggestion[]>(
    `/questions/${encodeURIComponent(questionId)}/suggestions`,
    `suggestions for question ${questionId}`,
    signal,
  )
}

// The other venue's market(s) for a pasted link, id, ticker or words
// (Milestone 22.5, manual linking).
export async function fetchVenueLookup(
  venue: Venue,
  reference: string,
  signal?: AbortSignal,
): Promise<VenueQuote[]> {
  return requestJson<VenueQuote[]>(
    `/venues/${venue}/lookup?ref=${encodeURIComponent(reference)}`,
    `${venue} market lookup`,
    signal,
  )
}

export async function createLinks(group: LinkGroupCreate): Promise<VenueLink[]> {
  return (await sendJson<VenueLink[]>('/links', 'confirm the links', 'POST', group)) ?? []
}

export async function deleteLink(linkId: number): Promise<void> {
  await sendJson<null>(`/links/${linkId}`, 'remove the link', 'DELETE')
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

export async function fetchExecution(
  marketId: string,
  size: number,
  signal?: AbortSignal,
): Promise<ExecutionEstimate> {
  return requestJson<ExecutionEstimate>(
    `/markets/${encodeURIComponent(marketId)}/execution?size=${size}`,
    `execution costs for market ${marketId}`,
    signal,
  )
}

export async function fetchElsewhere(
  marketId: string,
  signal?: AbortSignal,
): Promise<ElsewhereEntry[]> {
  return requestJson<ElsewhereEntry[]>(
    `/markets/${encodeURIComponent(marketId)}/elsewhere`,
    `other venues for market ${marketId}`,
    signal,
  )
}

export async function fetchDeployers(
  signal?: AbortSignal,
): Promise<DeployerStats[]> {
  return requestJson<DeployerStats[]>('/deployers', 'deployers', signal)
}

// Trader leaderboard (Milestone 23.4).
export async function fetchLeaderboard(
  timeWindow: LeaderboardWindow,
  sort: LeaderboardSort,
  limit: number,
  signal?: AbortSignal,
): Promise<Leaderboard> {
  return requestJson<Leaderboard>(
    `/leaderboard?window=${timeWindow}&sort=${sort}&limit=${limit}`,
    'leaderboard',
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