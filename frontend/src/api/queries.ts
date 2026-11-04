import { 
    skipToken,
    useMutation,
    useQuery,
    useQueryClient, 
} from '@tanstack/react-query'
import type { CandleRange } from '../types/candle'
import {
    ApiError,
    fetchDeployers,
    createLinks,
    deleteLink,
    fetchElsewhere,
    fetchSuggestions,
    fetchMarketDetail,
    fetchMarkets,
    fetchPriceHistory,
} from './markets'

// Query keys are cache addresses. Keeping them in one place means 
// every component asking for the same data shares one cache entry
export const marketKeys = {
    list: ['markets', 'list'] as const, 
    detail: (marketId: string | null ) =>
        ['markets', 'detail', marketId] as const,
    // One cache entry per (market, range): switching back to a range
    // you already viewed is instant.
    priceHistory: (marketId: string | null, range: CandleRange) =>
        ['markets', 'priceHistory', marketId, range] as const,
    deployers: ['deployers'] as const,
    elsewhere: (marketId: string | null) => 
        ['markets', 'elsewhere', marketId] as const,
    suggestions: (questionId: string | null) =>
        ['markets', 'suggestions', questionId] as const,
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


// The backend caches candles for 1 to 10 minutes depending on the range,
// so refreshing faster than once a minute would only return copies.
const PRICE_HISTORY_MS = 60_000

export function usePriceHistory(
    marketId: string | null,
    range: CandleRange,
    enabled: boolean,
) {
    return useQuery({
        queryKey: marketKeys.priceHistory(marketId, range),
        queryFn:
            marketId === null || !enabled
                ? skipToken
                : ({ signal }) => fetchPriceHistory(marketId, range, signal),
        staleTime: PRICE_HISTORY_MS,
        refetchInterval: PRICE_HISTORY_MS,
        // Retrying a 404 cannot help: the market's history is gone
        // (settled). Anything else (502, network) gets the usual 3 tries.
        retry: (failureCount, error) =>
            !(error instanceof ApiError && error.status === 404) &&
            failureCount < 3,
    })
}


// Deployer stats are summarized from the same 15s backend snapshot as the
// market list, so they share its freshness and polling. The query only
// runs while the Deployers view is on screen (its component is mounted).
export function useDeployers() {
    return useQuery({
        queryKey: marketKeys.deployers,
        queryFn: ({ signal }) => fetchDeployers(signal),
        staleTime: SERVER_CACHE_MS,
        refetchInterval: POLL_MS,
    })
}


// Linked markets on other venues (Milestone 22.3). The backend caches
// each external quote for 30 s (decision 5), so polling faster would
// only return copies.
const ELSEWHERE_MS = 30_000

export function useElsewhere(marketId: string | null) {
    return useQuery({
        queryKey: marketKeys.elsewhere(marketId),
        queryFn:
            marketId === null
                ? skipToken
                : ({ signal }) => fetchElsewhere(marketId, signal),
        staleTime: ELSEWHERE_MS,
        refetchInterval: ELSEWHERE_MS,
    })
}


// Suggestions are searched on demand (22.3b): `enabled` stays false until
// the person clicks "Find on other venues", because each search costs
// requests to two other venues.
export function useSuggestions(questionId: string | null, enabled: boolean) {
    return useQuery({
        queryKey: marketKeys.suggestions(questionId),
        queryFn:
            questionId === null || !enabled
                ? skipToken
                : ({ signal }) => fetchSuggestions(questionId, signal),
        staleTime: 60_000,
        // A failed search is shown with a "try again" button rather than
        // retried silently three times.
        retry: false,
    })
}

// After a write, every "elsewhere" list may be out of date: one
// confirmation links several outcomes at once. Invalidating by the key
// PREFIX ['markets', 'elsewhere'] marks all of them stale, and the ones
// on screen refetch immediately.
function useInvalidateElsewhere() {
    const queryClient = useQueryClient()
    return () =>
        queryClient.invalidateQueries({ queryKey: ['markets', 'elsewhere'] })
}

export function useCreateLinks() {
    const invalidate = useInvalidateElsewhere()
    return useMutation({
        mutationFn: createLinks,
        onSuccess: invalidate,
    })
}

export function useDeleteLink() {
    const invalidate = useInvalidateElsewhere()
    return useMutation({
        mutationFn: deleteLink,
        onSuccess: invalidate,
    })
}