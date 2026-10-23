import { useEffect, useState, type CSSProperties } from 'react'
import { subscribeToOrderBook, type SocketStatus } from '../api/hlSocket'
import { fetchOrderBook } from '../api/markets'
import type { BookLevel, OrderBook } from '../types/book'
import type { OutcomeSide } from '../types/market'
import { formatPrecisePrice } from '../utils/format'

// Running total of size from the best price outward: how many contracts
// you could trade by sweeping the book down to (and including) each level.
function cumulativeSizes(levels: BookLevel[]): number[] {
  const totals: number[] = []
  let running = 0
  for (const level of levels) {
    running += level.size
    totals.push(running)
  }
  return totals
}

const sizeFormat = new Intl.NumberFormat(undefined, {
  maximumFractionDigits: 2,
})

interface BookSideTableProps {
  title: string
  levels: BookLevel[]
  side: 'bid' | 'ask'
  // Largest cumulative size on EITHER side, so both tables share one
  // scale and an imbalance (1k bid vs 16k ask) is visible at a glance.
  maxTotal: number
}

function BookSideTable({ title, levels, side, maxTotal }: BookSideTableProps) {
  const totals = cumulativeSizes(levels)

  return (
    <div className="book-side">
      <h4>{title}</h4>

      {levels.length === 0 ? (
        <p className="detail-note">No resting orders.</p>
      ) : (
        <table className="book-table">
          <thead>
            <tr>
              <th>Price</th>
              <th>Size</th>
              <th>Orders</th>
              <th>Total</th>
            </tr>
          </thead>
          <tbody>
            {levels.map((level, index) => {
              const total = totals[index]
              const depth = maxTotal > 0 ? (total / maxTotal) * 100 : 0
              // A CSS custom property set from data: the stylesheet draws
              // the bar, React only supplies how long it is.
              const style = { '--depth': `${depth}%` } as CSSProperties

              return (
                <tr key={level.price}>
                  <td>{formatPrecisePrice(level.price)}</td>
                  <td>{sizeFormat.format(level.size)}</td>
                  <td>{level.orders}</td>
                  <td
                    className={`depth-cell depth-cell--${side}`}
                    style={style}
                  >
                    {sizeFormat.format(total)}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      )}
    </div>
  )
}

type BookSource = 'snapshot' | 'live'

interface LiveBadgeProps {
  socketStatus: SocketStatus | 'idle'
  attempt: number
  bookSource: BookSource | null
  updatedAt: string | null
}

function LiveBadge({ socketStatus, attempt, bookSource, updatedAt }: LiveBadgeProps) {
  let label = 'Idle'
  let tone = 'idle'

  if (socketStatus === 'connecting') {
    label = 'Connecting'
    tone = 'pending'
  } else if (socketStatus === 'open') {
    label = bookSource === 'live' ? 'Live' : 'Connected'
    tone = bookSource === 'live' ? 'live' : 'pending'
  } else if (socketStatus === 'reconnecting') {
    label =
      bookSource !== null
        ? `Reconnecting (attempt ${attempt}) — showing last data`
        : `Reconnecting (attempt ${attempt})`
    tone = 'down'
  }

  const updatedTime =
    updatedAt !== null ? new Date(updatedAt).toLocaleTimeString() : null

  return (
    <div className="live-badge">
      <span className={`live-dot live-dot--${tone}`} aria-hidden="true" />
      <span>{label}</span>
      {updatedTime !== null && (
        <span className="live-updated">· updated {updatedTime}</span>
      )}
    </div>
  )
}

interface OrderBookBodyProps {
  marketId: string
  sideIndex: number
  side: OutcomeSide | null
  isSettled: boolean
}

// Everything that belongs to ONE (market, side) book: its data, its
// socket and its status. The parent renders it with a `key` made from the
// side, so switching sides mounts a brand-new OrderBookBody whose state
// starts empty, instead of an effect resetting old state (the source of
// the two set-state-in-effect lint warnings, Milestone 18.7).
function OrderBookBody({ marketId, sideIndex, side, isSettled }: OrderBookBodyProps) {
  const [book, setBook] = useState<OrderBook | null>(null)
  const [bookSource, setBookSource] = useState<BookSource | null>(null)
  const [socketStatus, setSocketStatus] = useState<SocketStatus | 'idle'>('idle')
  const [reconnectAttempt, setReconnectAttempt] = useState(0)
  const [snapshotError, setSnapshotError] = useState<string | null>(null)

  const coin = side?.coin ?? null
  const isReconnecting = socketStatus === 'reconnecting'

  // Source 1: HTTP snapshot via our backend. Fast first paint, and the
  // fallback if the socket cannot connect. Never overwrites a live book.
  useEffect(() => {
    if (isSettled) {
      return
    }

    let ignore = false

    async function loadSnapshot() {
      try {
        const snapshot = await fetchOrderBook(marketId, sideIndex)

        if (!ignore) {
          setBook((current) => current ?? snapshot)
          setBookSource((current) => current ?? 'snapshot')
        }
      } catch (caughtError) {
        if (!ignore) {
          setSnapshotError(
            caughtError instanceof Error
              ? caughtError.message
              : 'An unknown error occurred',
          )
        }
      }
    }

    loadSnapshot()

    return () => {
      ignore = true
    }
  }, [marketId, sideIndex, isSettled])

  // Source 2: live snapshots over WebSocket. The adapter handles
  // reconnection and guarantees no callbacks after unsubscribe.
  useEffect(() => {
    if (isSettled || coin === null) {
      return
    }

    const unsubscribe = subscribeToOrderBook(coin, sideIndex, {
      onBook: (liveBook) => {
        setBook(liveBook)
        setBookSource('live')
      },
      onStatus: (status, attempt) => {
        setSocketStatus(status)
        setReconnectAttempt(attempt)
      },
    })

    return unsubscribe
  }, [coin, sideIndex, isSettled])

  if (isSettled) {
    return <p className="detail-note">Settled markets have no order book.</p>
  }

  const bidTotals = cumulativeSizes(book?.bids ?? [])
  const askTotals = cumulativeSizes(book?.asks ?? [])
  const maxTotal = Math.max(bidTotals.at(-1) ?? 0, askTotals.at(-1) ?? 0)

  return (
    <>
      <LiveBadge
        socketStatus={socketStatus}
        attempt={reconnectAttempt}
        bookSource={bookSource}
        updatedAt={book?.fetchedAt ?? null}
      />

      {book === null ? (
        snapshotError !== null ? (
          <p className="detail-note detail-note--error">
            Could not load order book: {snapshotError}
          </p>
        ) : (
          <p className="detail-note">Loading order book…</p>
        )
      ) : (
        <div
          className={
            isReconnecting
              ? 'order-book-body order-book-body--stale'
              : 'order-book-body'
          }
        >
          <dl className="market-metadata book-summary">
            <div>
              <dt>Best bid</dt>
              <dd>{formatPrecisePrice(book.bestBid)}</dd>
            </div>
            <div>
              <dt>Best ask</dt>
              <dd>{formatPrecisePrice(book.bestAsk)}</dd>
            </div>
            <div>
              <dt>Spread</dt>
              <dd>{formatPrecisePrice(book.spread)}</dd>
            </div>
          </dl>

          <div className="order-book">
            <BookSideTable
              title={`Bids (buy ${side?.label ?? 'side'})`}
              levels={book.bids}
              side="bid"
              maxTotal={maxTotal}
            />
            <BookSideTable
              title={`Asks (sell ${side?.label ?? 'side'})`}
              levels={book.asks}
              side="ask"
              maxTotal={maxTotal}
            />
          </div>
        </div>
      )}
    </>
  )
}

interface OrderBookPanelProps {
  marketId: string
  sides: OutcomeSide[]
  isSettled: boolean
}

function OrderBookPanel({ marketId, sides, isSettled }: OrderBookPanelProps) {
  const [sideIndex, setSideIndex] = useState(0)
  const activeSide = sides[sideIndex] ?? null

  return (
    <section className="detail-section">
      <div className="section-heading">
        <h3>Order book</h3>

        <div className="side-toggle" role="group" aria-label="Book side">
          {sides.map((side) => (
            <button
              key={side.coin}
              type="button"
              className={
                side.index === sideIndex
                  ? 'side-toggle-button side-toggle-button--active'
                  : 'side-toggle-button'
              }
              aria-pressed={side.index === sideIndex}
              onClick={() => setSideIndex(side.index)}
            >
              {side.label}
            </button>
          ))}
        </div>
      </div>

      {/* MarketDetail already keys this whole panel by market id; this key
          adds the side and settled state, so each book gets fresh state. */}
      <OrderBookBody
        key={`${sideIndex}:${isSettled}`}
        marketId={marketId}
        sideIndex={sideIndex}
        side={activeSide}
        isSettled={isSettled}
      />
    </section>
  )
}

export default OrderBookPanel