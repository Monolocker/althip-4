import { skipToken, useQuery } from '@tanstack/react-query'
import { fetchMarketDetail, fetchMarkets } from './markets'

// Query keys are cache addresses. Keeping them in one place means 
// every component asking for the same data shares one cache entry
export const marketKeys = {
    list: ['markets', 'list'] as const, 
    detail: (marketId: string | null ) =>
        ['markets', 'detail', marketId] as const,
}

// Backend snapshots refreshes every 15s, so data younger than 15s
// cannot be improved on, and polling faster would only return copies
const SERVER_CACHE_MS = 15_000
const POLL_MS = 30_000

export function useMarkets() {
    return useQuery({
        queryKey: marketKeys.list,
        queryFn: ({ signal }) => fetchMarkets(signal),
        staleTime: SERVER_CACHE_MS,
        refetchInterval: POLL_MS,
    })
}

export function useMarketDetail(marketId: string | null) {
    return useQuery({
        queryKey: marketKeys.detail(marketId),
        queryFn:
            marketId === null
                ? skipToken
                : ({ signal }) => fetchMarketDetail(marketId, signal),
        staleTime: SERVER_CACHE_MS,
        refetchInterval: POLL_MS,
    })
}

