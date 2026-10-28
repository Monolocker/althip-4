import { useDeployers } from '../api/queries'
import { venueLabel } from '../features/markets/discovery'
import type { DeployerStats, QualityCounts } from '../types/deployer'
import { formatTime, formatVolume } from '../utils/format'

// "0x0c46eb73fae2816f219fcf11f50d6d3c59b5819e" -> "0x0c46…819e"
function shortAddress(address: string): string {
  return `${address.slice(0, 6)}…${address.slice(-4)}`
}

const QUALITY_SEGMENTS: { key: keyof QualityCounts; label: string }[] = [
  { key: 'tight', label: 'tight' },
  { key: 'wide', label: 'wide' },
  { key: 'unreliable', label: 'unreliable' },
  { key: 'unknown', label: 'unchecked' },
]

// One horizontal bar split into the 18.3 book-quality classes, each
// segment as wide as its share of the deployer's markets.
function QualityBar({ quality, total }: { quality: QualityCounts; total: number }) {
  if (total === 0) {
    return null
  }
  return (
    <span className="quality-bar" aria-hidden="true">
      {QUALITY_SEGMENTS.map(({ key }) =>
        quality[key] > 0 ? (
          <span
            key={key}
            className={`quality-bar-segment quality-bar-segment--${key}`}
            style={{ width: `${(quality[key] / total) * 100}%` }}
          />
        ) : null,
      )}
    </span>
  )
}

interface DeployerCardProps {
  stats: DeployerStats
  isActive: boolean
  onSelect: (venue: string) => void
}

function DeployerCard({ stats, isActive, onSelect }: DeployerCardProps) {
  const label = venueLabel(stats.venue)
  const legend = QUALITY_SEGMENTS.filter(({ key }) => stats.bookQuality[key] > 0)
    .map(({ key, label: name }) => `${stats.bookQuality[key]} ${name}`)
    .join(' · ')
  // Largest categories first; three is enough for a card.
  const categories = Object.entries(stats.categories)
    .sort(([, a], [, b]) => b - a)
    .slice(0, 3)
  const nextEvent = formatTime(stats.nextEventAt)

  return (
    // The whole card is one button: clicking it shows this deployer's
    // markets (decision 1). Inside a button only inline elements are
    // valid HTML, so the layout uses spans styled as blocks.
    <button
      type="button"
      className={isActive ? 'deployer-card deployer-card--active' : 'deployer-card'}
      aria-pressed={isActive}
      aria-label={`Show ${label} markets`}
      onClick={() => onSelect(stats.venue)}
    >
      <span className="deployer-card-header">
        <strong>{label}</strong>
        <span className="deployer-card-address">
          {stats.address !== null ? shortAddress(stats.address) : 'protocol'}
        </span>
      </span>

      <span className="deployer-card-line">
        {stats.marketCount} markets · {stats.questionCount} questions · 24h vol{' '}
        {formatVolume(stats.volume24h)}
      </span>

      <QualityBar quality={stats.bookQuality} total={stats.marketCount} />
      {legend !== '' && <span className="deployer-card-muted">{legend}</span>}

      {categories.length > 0 && (
        <span className="deployer-card-categories">
          {categories.map(([name, count]) => (
            <span key={name} className="deployer-card-category">
              {name} {count}
            </span>
          ))}
        </span>
      )}

      <span className="deployer-card-muted">
        Next event: {nextEvent?.utc ?? '—'}
      </span>
      {stats.topMarketQuestion !== null && (
        <span className="deployer-card-top">Top: {stats.topMarketQuestion}</span>
      )}
    </button>
  )
}

interface DeployerDirectoryProps {
  activeVenue: string | null
  onSelectVenue: (venue: string) => void
}

// Every deployer, busiest first, summarized by the backend (20.1a).
function DeployerDirectory({ activeVenue, onSelectVenue }: DeployerDirectoryProps) {
  const deployers = useDeployers()

  if (deployers.isPending) {
    return <p className="request-status">Loading deployers…</p>
  }
  if (deployers.isError) {
    return (
      <p className="detail-note detail-note--error">
        Could not load deployers: {deployers.error.message}
      </p>
    )
  }

  return (
    <section className="deployer-directory" aria-label="Deployers">
      <div className="market-list-header">
        <h2>Deployers</h2>
        <span>{deployers.data.length}</span>
      </div>

      <div className="market-list-items">
        {deployers.data.map((stats) => (
          <DeployerCard
            key={stats.venue === '' ? '(hyperliquid)' : stats.venue}
            stats={stats}
            isActive={stats.venue === activeVenue}
            onSelect={onSelectVenue}
          />
        ))}
      </div>
    </section>
  )
}

export default DeployerDirectory