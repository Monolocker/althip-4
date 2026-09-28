import { useEffect, useState } from 'react'
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

interface OrderBookPanelProps {
  marketId: string
  sides: OutcomeSide[]
  isSettled: boolean
}

function OrderBookPanel({ marketId, sides, isSettled }: OrderBookPanelProps) {
  const [sideIndex, setSideIndex] = useState(0)
  const [book, setBook] = useState<OrderBook | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setBook(null)
    setError(null)

    if (isSettled) {
      return
    }

    let ignore = false

    async function loadBook() {
      try {
        const fetchedBook = await fetchOrderBook(marketId, sideIndex)

        if (!ignore) {
          setBook(fetchedBook)
        }
      } catch (caughtError) {
        if (!ignore) {
          setError(
            caughtError instanceof Error
              ? caughtError.message
              : 'An unknown error occurred',
          )
        }
      }
    }

    loadBook()

    return () => {
      ignore = true
    }
  }, [marketId, sideIndex, isSettled])

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

      {isSettled ? (
        <p className="detail-note">Settled markets have no order book.</p>
      ) : error !== null ? (
        <p className="detail-note detail-note--error">
          Could not load order book: {error}
        </p>
      ) : book === null ? (
        <p className="detail-note">Loading order book…</p>
      ) : (
        <>
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
        </>
      )}
    </section>
  )
}

export default OrderBookPanel