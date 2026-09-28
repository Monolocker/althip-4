export interface BookLevel {
    price: number
    size: number
    orders: number
}

export interface OrderBook {
    coin: string
    sideIndex: number
    fetchedAt: string
    bids: BookLevel[]
    asks: BookLevel[]
    bestBid: number | null
    bestAsk: number | null
    spread: number | null
}