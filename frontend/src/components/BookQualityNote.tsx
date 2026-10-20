import type { BookSummary } from '../types/market'
import { formatPrecisePrice } from '../utils/format'

interface BookQualityNoteProps {
  book: BookSummary | null
}

// Why an unreliable price is unreliable, in words a trader can act on.
function describeUnreliable(book: BookSummary): string {
  if (book.source === 'mark') {
    return 'Never traded: no reliable price'
  }
  if (book.bid === null && book.ask === null) {
    return 'Empty order book: no reliable price'
  }
  if (book.bid === null || book.ask === null) {
    return 'One-sided order book: no reliable price'
  }
  return `Very wide book (${formatPrecisePrice(book.bid)} bid / ${formatPrecisePrice(book.ask)} ask): no reliable price`
}

// Renders nothing for tight books (or no data): a normal market needs no
// caption. Wide books get a spread hint; unreliable books get a warning.
function BookQualityNote({ book }: BookQualityNoteProps) {
  if (book === null || book.quality === 'tight') {
    return null
  }

  if (book.quality === 'wide') {
    return (
      <p className="book-note book-note--wide">
        Wide spread: {formatPrecisePrice(book.spread)}
      </p>
    )
  }

  return (
    <p className="book-note book-note--unreliable" role="note">
      ⚠ {describeUnreliable(book)}
    </p>
  )
}

export default BookQualityNote