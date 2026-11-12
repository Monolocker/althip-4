import type { CSSProperties } from 'react'
import { useFeed } from '../api/queries'
import type { FeedItem, FeedSourceStatus } from '../types/feed'
import { formatTime } from '../utils/format'

// Scroll speed: each item gets about this long on screen. The duration
// grows with the number of items, so the speed stays the same.
const SECONDS_PER_ITEM = 2.5

const signedPercent = new Intl.NumberFormat('en-US', {
  style: 'percent',
  signDisplay: 'exceptZero',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})
const wholePercent = new Intl.NumberFormat('en-US', { style: 'percent', maximumFractionDigits: 0 })

// One line per source for the label's tooltip: what worked, and how old
// the items still being shown are when a refresh failed.
function sourceSummary(sources: FeedSourceStatus[]): string {
  return sources
    .map((source) => {
      const fetched = formatTime(source.fetchedAt)?.utc ?? 'never'
      return source.ok
        ? `${source.kind}: ${source.items} items, fetched ${fetched}`
        : `${source.kind}: refresh failed (${source.error ?? 'unknown error'}), showing items from ${fetched}`
    })
    .join('\n')
}

interface FeedEntryProps {
  item: FeedItem
  // The second, duplicate copy of the row exists only to make the loop
  // seamless: keyboard and screen-reader users skip it.
  duplicate: boolean
  onSelectMarket: (marketId: string) => void
}

function FeedEntry({ item, duplicate, onSelectMarket }: FeedEntryProps) {
  const tabIndex = duplicate ? -1 : undefined
  const marketId = item.marketId

  // Trending: one of our markets, opened inside the app.
  if (item.kind === 'trending' && marketId !== null) {
    return (
      <button
        type="button"
        className="feed-item feed-item--trending"
        tabIndex={tabIndex}
        title={item.text}
        onClick={() => onSelectMarket(marketId)}
      >
        {item.probability !== null && (
          <span className="feed-value">{wholePercent.format(item.probability)}</span>
        )}
        <span className="feed-text">{item.text}</span>
      </button>
    )
  }

  if (item.url === null) {
    return null
  }

  // Headline only (decision 4); the tooltip names the outlet, so the
  // click's destination is never a surprise.
  const published = formatTime(item.publishedAt)?.utc
  const title = [item.text, item.source, published].filter(Boolean).join(' · ')
  const change = item.change24h
  return (
    <a
      className={`feed-item feed-item--${item.kind}`}
      href={item.url}
      target="_blank"
      rel="noopener noreferrer"
      tabIndex={tabIndex}
      title={title}
    >
      <span className="feed-text">{item.text}</span>
      {item.kind === 'ticker' && (
        <span
          className={
            change === null
              ? 'feed-value'
              : change > 0
                ? 'feed-value feed-change--up'
                : change < 0
                  ? 'feed-value feed-change--down'
                  : 'feed-value'
          }
        >
          {change === null ? '—' : signedPercent.format(change)}
        </span>
      )}
    </a>
  )
}

interface FeedRowProps {
  items: FeedItem[]
  duplicate: boolean
  onSelectMarket: (marketId: string) => void
}

function FeedRow({ items, duplicate, onSelectMarket }: FeedRowProps) {
  return (
    <ul className="feed-row" aria-hidden={duplicate || undefined}>
      {items.map((item, index) => (
        <li key={`${item.kind}-${item.url ?? item.marketId ?? ''}-${index}`}>
          <FeedEntry item={item} duplicate={duplicate} onSelectMarket={onSelectMarket} />
        </li>
      ))}
    </ul>
  )
}

interface FeedTickerProps {
  onSelectMarket: (marketId: string) => void
}

// The scrolling strip under the header (Milestone 24.3). The row is
// rendered twice and the track slides left by exactly one copy (-50%),
// so the end of the first copy meets the start of the second without a
// visible jump. Hovering or focusing the strip pauses it, which is what
// makes an item clickable.
function FeedTicker({ onSelectMarket }: FeedTickerProps) {
  const feed = useFeed()
  const data = feed.data
  // Nothing yet, or every source empty: no strip rather than an empty box.
  if (data === undefined || data.items.length === 0) {
    return null
  }

  const failing = data.sources.filter((source) => !source.ok).length
  const trackStyle = {
    '--feed-duration': `${data.items.length * SECONDS_PER_ITEM}s`,
  } as CSSProperties

  return (
    <section className="feed-strip" aria-label="News and market feed">
      <span className="feed-label" title={sourceSummary(data.sources)}>
        Feed{failing > 0 && <span className="feed-warning"> ⚠ {failing}</span>}
      </span>
      <div className="feed-viewport">
        <div className="feed-track" style={trackStyle}>
          <FeedRow items={data.items} duplicate={false} onSelectMarket={onSelectMarket} />
          <FeedRow items={data.items} duplicate onSelectMarket={onSelectMarket} />
        </div>
      </div>
    </section>
  )
}

export default FeedTicker