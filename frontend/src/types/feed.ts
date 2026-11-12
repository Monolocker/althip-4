// Unified feed (M24.3)
// Mirrors backend/app/models/feed.py

export type FeedKind = 'news' | 'sports' | 'ticker' | 'trending'

export interface FeedItem {
    kind: FeedKind
    text: string    // full text: the strip shortens it visually
    url: string | null  // external: article or HL trade page
    marketId: string | null // internal: trending items opens domain app market
    source: string | null   // outlet or venue, ex: ESPN
    publishedAt: string | null  
    change24h: number | null    // ticker: fraction, 0.0201 = +2.01%
    probability: number | null  // trending: 0 to 1
}

export interface FeedSourceStatus {
    kind: FeedKind
    ok: boolean // the latest refresh succeeded
    items: number
    fetchedAt: string | null // when the items shown were fetched
    error: string | null
}

export interface Feed {
    generatedAt: string
    items: FeedItem[]
    sources: FeedSourceStatus[]
}