import type { BookLevel, OrderBook } from '../types/book'

const HYPERLIQUID_WS_URL = 'wss://api.hyperliquid.xyz/ws'

export type SocketStatus = "connecting" | "open" | "closed" | "error"

// Raw HL shapes. Never leaves this module
interface RawLevel {
    px: string
    sz: string
    n: number
}

interface RawL2Book {
    coin: string
    time: number
    levels: [RawLevel[], RawLevel[]]
}

interface L2BookMessage {
    channel: 'l2Book'
    data: RawL2Book
}

function isL2BookMessage(value: unknown): value is L2BookMessage {
    if (typeof value !== 'object' || value === null) {
        return false
    }
    const candidate = value as { channel?: unknown; data?: unknown }
    if (candidate.channel !== 'l2Book') {
        return false
    }
    const data = candidate.data as {coin?: unknown; levels?: unknown} | undefined
    return (
        data !== undefined &&
        typeof data.coin === 'string' &&
        Array.isArray(data.levels) && 
        data.levels.length === 2
    )
}

function parseLevels(raw: RawLevel[]): BookLevel[] {
    const levels: BookLevel[] = []
    for (const level of raw) {
      const price = Number(level.px)
      const size = Number(level.sz)
      if (Number.isFinite(price) && Number.isFinite(size)) {
        levels.push({ price, size, orders: level.n })
      }
    }
    return levels
  }
  
  export function normalizeL2Book(raw: RawL2Book, sideIndex: number): OrderBook {
    const bids = parseLevels(raw.levels[0]).sort((a, b) => b.price - a.price)
    const asks = parseLevels(raw.levels[1]).sort((a, b) => a.price - b.price)
  
    const bestBid = bids.length > 0 ? bids[0].price : null
    const bestAsk = asks.length > 0 ? asks[0].price : null
    const spread =
      bestBid !== null && bestAsk !== null
        ? Math.round((bestAsk - bestBid) * 1e6) / 1e6
        : null
  
    return {
      coin: raw.coin,
      sideIndex,
      fetchedAt: new Date(raw.time).toISOString(),
      bids,
      asks,
      bestBid,
      bestAsk,
      spread,
    }
  }
  
  interface OrderBookHandlers {
    onBook: (book: OrderBook) => void
    onStatus: (status: SocketStatus, detail?: string) => void
  }
  
  /**
   * Open a connection, subscribe to one coin's book, and deliver parsed
   * updates. Returns a function that unsubscribes and closes the socket.
   */
  export function subscribeToOrderBook(
    coin: string,
    sideIndex: number,
    handlers: OrderBookHandlers,
  ): () => void {
    const socket = new WebSocket(HYPERLIQUID_WS_URL)
    const subscription = { type: 'l2Book', coin }
  
    handlers.onStatus('connecting')
  
    socket.addEventListener('open', () => {
      socket.send(JSON.stringify({ method: 'subscribe', subscription }))
      handlers.onStatus('open')
    })
  
    socket.addEventListener('message', (event: MessageEvent<string>) => {
      let parsed: unknown
      try {
        parsed = JSON.parse(event.data)
      } catch {
        return
      }
  
      if (isL2BookMessage(parsed) && parsed.data.coin === coin) {
        handlers.onBook(normalizeL2Book(parsed.data, sideIndex))
      }
    })
  
    socket.addEventListener('close', (event: CloseEvent) => {
      handlers.onStatus('closed', `code ${event.code}`)
    })
  
    socket.addEventListener('error', () => {
        handlers.onStatus('error')
    })
  
    return () => {
      if (socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({ method: 'unsubscribe', subscription }))
      }
      socket.close()
    }
  }