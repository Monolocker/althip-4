import type { BookLevel, OrderBook } from '../types/book'

const HYPERLIQUID_WS_URL = 'wss://api.hyperliquid.xyz/ws'

// l2Book pushes a full snapshot about every 5s, so 15s of silence
// means the connection is dead even if the browser still reports as open
const STALE_AFTER_MS = 15_000
const WATCHDOG_INTERVAL_MS = 2_500

// HL closes connections that go 60s w/o traffic.
// Pinging keeps quiet connections alive
// Does not detect dead ones
const PING_INTERVAL_MS = 20_000

const RECONNECT_BASE_MS = 1_000
const RECONNECT_MAX_MS = 30_000

export type SocketStatus = "connecting" | "open" | "reconnecting"

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
    onStatus: (status: SocketStatus, attempt: number) => void
  }
  
  /**
   * Keep a live subscription to one coin's book, connect, subscribe,
   * watch for silence, and reconnect w/ backoff until disposed
   * 
   * Contract: no handler is ever called after the returned function runs 
   */
  export function subscribeToOrderBook(
    coin: string,
    sideIndex: number,
    handlers: OrderBookHandlers,
  ): () => void {
    const subscription = { type: "l2Book", coin }

    // The one socket we actually care about
    // Events from any other socket are ignored
    let socket: WebSocket | null = null
    let disposed = false
    let attempt = 0
    let lastMessageAt = 0
    let reconnectTimer: number | undefined
    let pingTimer: number | undefined
    let watchdogTimer: number | undefined

    function report(status: SocketStatus) {
      if (!disposed) {
        handlers.onStatus(status, attempt)
      }
    }

    function stopTimers() {
      window.clearTimeout(reconnectTimer)
      window.clearInterval(pingTimer)
      window.clearInterval(watchdogTimer)
    }

    function retire(target: WebSocket) {
      if (target.readyState === WebSocket.OPEN) {
        target.close(1000, "client closing")
      } else if (target.readyState === WebSocket.CONNECTING) {
        // Closing mid-handshake makes the browser log a warning
        // let handshake finish, then close cleanly
        target.addEventListener("open", () => target.close(1000, "client closing"))
      }
    }

    function scheduleReconnect() {
      if (disposed) return
      stopTimers()
  
      // Retire the current socket without waiting for its close event;
      // on a dead network that event can take minutes to arrive.
      if (socket !== null) {
        retire(socket)
        socket = null
      }
  
      attempt += 1
      const backoff = Math.min(
        RECONNECT_BASE_MS * 2 ** (attempt - 1),
        RECONNECT_MAX_MS,
      )
      const delay = backoff / 2 + Math.random() * (backoff / 2)
  
      report('reconnecting')
      reconnectTimer = window.setTimeout(connect, delay)
    }
  
    function connect() {
      if (disposed) return
      stopTimers()
  
      const current = new WebSocket(HYPERLIQUID_WS_URL)
      socket = current
      lastMessageAt = Date.now()
      report(attempt === 0 ? 'connecting' : 'reconnecting')
  
      // Started at connect, not at open, so a handshake that hangs
      // forever is caught the same way as a connection that goes silent.
      watchdogTimer = window.setInterval(() => {
        if (Date.now() - lastMessageAt > STALE_AFTER_MS) {
          scheduleReconnect()
        }
      }, WATCHDOG_INTERVAL_MS)
  
      current.addEventListener('open', () => {
        if (current !== socket) return
        current.send(JSON.stringify({ method: 'subscribe', subscription }))
        lastMessageAt = Date.now()
        report('open')
  
        pingTimer = window.setInterval(() => {
          if (current.readyState === WebSocket.OPEN) {
            current.send(JSON.stringify({ method: 'ping' }))
          }
        }, PING_INTERVAL_MS)
      })
  
      current.addEventListener('message', (event: MessageEvent<string>) => {
        if (current !== socket) return
        // Any traffic at all (book, pong, subscription ack) proves liveness.
        lastMessageAt = Date.now()
  
        let parsed: unknown
        try {
          parsed = JSON.parse(event.data)
        } catch {
          return
        }
  
        if (isL2BookMessage(parsed) && parsed.data.coin === coin) {
          // Data is flowing again: the next failure starts backoff fresh.
          if (attempt !== 0) {
            attempt = 0
            report('open')
          }
          handlers.onBook(normalizeL2Book(parsed.data, sideIndex))
        }
      })
  
      // The browser always fires close after error, so close alone
      // decides when to reconnect.
      current.addEventListener('close', () => {
        if (current !== socket) return
        scheduleReconnect()
      })
    }
  
    // When the browser regains network while we are waiting out a
    // backoff delay, skip the rest of the wait.
    function handleOnline() {
      if (disposed || socket !== null) return
      connect()
    }
  
    window.addEventListener('online', handleOnline)
    connect()
  
    return () => {
      disposed = true
      stopTimers()
      window.removeEventListener('online', handleOnline)
  
      const current = socket
      socket = null
      if (current !== null) {
        if (current.readyState === WebSocket.OPEN) {
          current.send(JSON.stringify({ method: 'unsubscribe', subscription }))
        }
        retire(current)
      }
    }
  
  }