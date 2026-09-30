import { useEffect, useState } from 'react'
import { subscribeToOrderBook, type SocketStatus } from '../api/hlSocket'
import { fetchOrderBook } from '../api/markets'
import type { BookLevel, OrderBook } from '../types/book'
import type { OutcomeSide } from '../types/market'
import { formatPrice } from '../utils/format'

interface BookSideTableProps {
  title: string
  levels: BookLevel[]
}

function BookSideTable({ title, levels }: BookSideTableProps) {
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
            </tr>
          </thead>
          <tbody>
            {levels.map((level) => (
              <tr key={level.price}>
                <td>{formatPrice(level.price)}</td>
                <td>{level.size.toLocaleString()}</td>
                <td>{level.orders}</td>
              </tr>
            ))}
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

interface OrderBookPanelProps {
  marketId: string
  sides: OutcomeSide[]
  isSettled: boolean
}

function OrderBookPanel({ marketId, sides, isSettled }: OrderBookPanelProps) {
  const [sideIndex, setSideIndex] = useState(0)
  const [book, setBook] = useState<OrderBook | null>(null)
  const [bookSource, setBookSource] = useState<BookSource | null>(null)
  const [socketStatus, setSocketStatus] = useState<SocketStatus | 'idle'>('idle')
  const [reconnectAttempt, setReconnectAttempt] = useState(0)
  const [snapshotError, setSnapshotError] = useState<string | null>(null)

  const activeSide = sides[sideIndex] ?? null
  const activeCoin = activeSide?.coin ?? null
  const isReconnecting = socketStatus === 'reconnecting'

  // Source 1: HTTP snapshot via our backend. Fast first paint, and the
  // fallback if the socket cannot connect. Never overwrites a live book.
  useEffect(() => {
    setBook(null)
    setBookSource(null)
    setSnapshotError(null)

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
    setSocketStatus('idle')
    setReconnectAttempt(0)

    if (isSettled || activeCoin === null) {
      return
    }

    const unsubscribe = subscribeToOrderBook(activeCoin, sideIndex, {
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
  }, [activeCoin, sideIndex, isSettled])

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

      {!isSettled && (
        <LiveBadge
          socketStatus={socketStatus}
          attempt={reconnectAttempt}
          bookSource={bookSource}
          updatedAt={book?.fetchedAt ?? null}
        />
      )}

      {isSettled ? (
        <p className="detail-note">Settled markets have no order book.</p>
      ) : book === null ? (
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
              <dd>{formatPrice(book.bestBid)}</dd>
            </div>
            <div>
              <dt>Best ask</dt>
              <dd>{formatPrice(book.bestAsk)}</dd>
            </div>
            <div>
              <dt>Spread</dt>
              <dd>{formatPrice(book.spread)}</dd>
            </div>
          </dl>

          <div className="order-book">
            <BookSideTable
              title={`Bids (buy ${activeSide?.label ?? 'side'})`}
              levels={book.bids}
            />
            <BookSideTable
              title={`Asks (sell ${activeSide?.label ?? 'side'})`}
              levels={book.asks}
            />
          </div>
        </div>
      )}
    </section>
  )
}

export default OrderBookPanel