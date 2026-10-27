import { useState, type PointerEvent } from 'react'
import { ApiError } from '../api/markets'
import { usePriceHistory } from '../api/queries'
import {
  INTERVAL_MS,
  formatChartTime,
  isolatedIndices,
  linePath,
  linearScale,
  nearestIndex,
  ticks,
  toPoints,
  valueDomain,
} from '../features/markets/chart'
import {
  formatProbability,
  pricesAreProbabilities,
} from '../features/markets/pricing'
import type { CandleRange, PriceHistory } from '../types/candle'
import type { OutcomeMarket } from '../types/market'
import { formatPrice, formatVolume } from '../utils/format'

const RANGES: { value: CandleRange; label: string }[] = [
  { value: '1d', label: '1D' },
  { value: '1w', label: '1W' },
  { value: '1m', label: '1M' },
  { value: 'all', label: 'All' },
]

// The chart is drawn in this coordinate system; the viewBox scales it to
// whatever width the panel has. Two stacked areas share one time axis:
// the price line on top, the volume strip underneath (Milestone 19.3).
const WIDTH = 640
const HEIGHT = 270
const PAD = { left: 8, right: 56 }
const PRICE_AREA = { top: 12, bottom: 186 }
const VOLUME_AREA = { top: 198, bottom: 238 }
const TIME_LABEL_Y = HEIGHT - 8

interface ChartSvgProps {
  history: PriceHistory
  // Shows a value as "21.6%" or "21.6¢" (19.3, decision 1).
  formatValue: (value: number) => string
}

function ChartSvg({ history, formatValue }: ChartSvgProps) {
  const [hoverIndex, setHoverIndex] = useState<number | null>(null)

  const points = toPoints(history.candles)
  const first = points[0]
  const last = points[points.length - 1]

  // Time runs left to right and is shared by both areas. Price and volume
  // run bottom to top, so their ranges are written [bottom, top]: SVG's
  // y axis grows DOWNWARD.
  const xDomain: [number, number] = [first.time, last.time]
  const xRange: [number, number] = [PAD.left, WIDTH - PAD.right]
  const x = linearScale(xDomain, xRange)
  const xToTime = linearScale(xRange, xDomain)
  const yDomain = valueDomain(points)
  const y = linearScale(yDomain, [PRICE_AREA.bottom, PRICE_AREA.top])

  const maxVolume = Math.max(...points.map((point) => point.volume))
  const volumeY = linearScale(
    [0, maxVolume],
    [VOLUME_AREA.bottom, VOLUME_AREA.top],
  )

  // A step of up to 1.5 intervals counts as consecutive; anything longer
  // means candles are missing, and the line breaks there.
  const intervalMs = INTERVAL_MS[history.interval] ?? Infinity
  const maxStepMs = intervalMs * 1.5
  const path = linePath(points, x, y, maxStepMs)
  const dots = isolatedIndices(points, maxStepMs)

  // One interval's width in pixels, 70% of it per bar so neighbours stay
  // apart; a single-candle chart has no width to measure, so it falls
  // back to a 6px interval (a ~4px bar).
  const intervalPx =
    points.length > 1 && Number.isFinite(intervalMs)
      ? x(first.time + intervalMs) - x(first.time)
      : 6
  const barWidth = Math.max(1, intervalPx * 0.7)

  // Hover state can outlive a data change (new range, new market), so an
  // out-of-range index simply means "nothing hovered".
  const hovered = hoverIndex !== null ? (points[hoverIndex] ?? null) : null
  const shown = hovered ?? last

  function handlePointerMove(event: PointerEvent<SVGSVGElement>) {
    // Pointer position in screen pixels -> chart units -> time.
    const box = event.currentTarget.getBoundingClientRect()
    const chartX = ((event.clientX - box.left) / box.width) * WIDTH
    setHoverIndex(nearestIndex(points, xToTime(chartX)))
  }

  return (
    <>
      <svg
        className="price-chart"
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        role="img"
        aria-label={`Price history, ${points.length} points, latest ${formatValue(last.value)}`}
        onPointerMove={handlePointerMove}
        onPointerLeave={() => setHoverIndex(null)}
      >
        {ticks(yDomain, 4).map((value) => (
          <g key={value}>
            <line
              className="price-chart-grid"
              x1={PAD.left}
              x2={WIDTH - PAD.right}
              y1={y(value)}
              y2={y(value)}
            />
            <text
              className="price-chart-label"
              x={WIDTH - PAD.right + 6}
              y={y(value)}
              dominantBaseline="middle"
            >
              {formatValue(value)}
            </text>
          </g>
        ))}

        <path className="price-chart-line" d={path} />

        {dots.map((index) => (
          <circle
            key={points[index].time}
            className="price-chart-dot"
            cx={x(points[index].time)}
            cy={y(points[index].value)}
            r={3}
          />
        ))}

        {/* Volume strip: one bar per candle that had trading volume. An
            interval with no volume has no bar, which is what makes "the
            line was flat because nobody traded" visible. */}
        <line
          className="price-chart-grid"
          x1={PAD.left}
          x2={WIDTH - PAD.right}
          y1={VOLUME_AREA.bottom}
          y2={VOLUME_AREA.bottom}
        />
        {points.map((point, index) =>
          point.volume > 0 ? (
            <rect
              key={point.time}
              className={
                index === hoverIndex
                  ? 'price-chart-volume price-chart-volume--hovered'
                  : 'price-chart-volume'
              }
              x={x(point.time) - barWidth / 2}
              y={volumeY(point.volume)}
              width={barWidth}
              height={VOLUME_AREA.bottom - volumeY(point.volume)}
            />
          ) : null,
        )}
        {maxVolume > 0 && (
          <text
            className="price-chart-label"
            x={WIDTH - PAD.right + 6}
            y={VOLUME_AREA.top}
            dominantBaseline="hanging"
          >
            {`Vol ${formatVolume(maxVolume)}`}
          </text>
        )}

        <text className="price-chart-label" x={PAD.left} y={TIME_LABEL_Y}>
          {formatChartTime(first.time, history.interval)}
        </text>
        <text
          className="price-chart-label"
          x={WIDTH - PAD.right}
          y={TIME_LABEL_Y}
          textAnchor="end"
        >
          {formatChartTime(last.time, history.interval)}
        </text>

        {hovered !== null && (
          <g>
            <line
              className="price-chart-crosshair"
              x1={x(hovered.time)}
              x2={x(hovered.time)}
              y1={PRICE_AREA.top}
              y2={VOLUME_AREA.bottom}
            />
            <circle
              className="price-chart-hover"
              cx={x(hovered.time)}
              cy={y(hovered.value)}
              r={4}
            />
          </g>
        )}
      </svg>

      <p className="price-chart-readout">
        {hovered !== null ? '' : 'Latest: '}
        <strong>{formatValue(shown.value)}</strong> ·{' '}
        {formatChartTime(shown.time, history.interval)} · {shown.trades}{' '}
        {shown.trades === 1 ? 'trade' : 'trades'} · vol{' '}
        {formatVolume(shown.volume)}
      </p>
    </>
  )
}

// The honest message for a failed request: a 404 means the history no
// longer exists, anything else is (probably) temporary.
function errorMessage(error: Error): string {
  if (error instanceof ApiError && error.status === 404) {
    return 'Price history is unavailable: this market has settled or is no longer listed.'
  }
  return `Could not load price history right now (${error.message}). It will retry automatically.`
}

interface PriceChartProps {
  market: OutcomeMarket
  isSettled: boolean
}

// Price history of the market's first side, from Hyperliquid candles
// (Milestone 19). The selected range survives switching markets.
function PriceChart({ market, isSettled }: PriceChartProps) {
  const [range, setRange] = useState<CandleRange>('1w')
  const history = usePriceHistory(market.id, range, !isSettled)

  // Same rule as the "Market-implied probability" line (18.4): percent
  // only when this market's prices really are probabilities.
  const formatValue = pricesAreProbabilities(market)
    ? formatProbability
    : formatPrice

  let body
  if (isSettled) {
    body = (
      <p className="detail-note">
        Price history is unavailable for settled markets.
      </p>
    )
  } else if (history.isPending) {
    body = <p className="detail-note">Loading price history…</p>
  } else if (history.isError) {
    body = (
      <p className="detail-note detail-note--error">
        {errorMessage(history.error)}
      </p>
    )
  } else if (history.data.candles.length === 0) {
    body = <p className="detail-note">No trading history yet.</p>
  } else {
    body = <ChartSvg history={history.data} formatValue={formatValue} />
  }

  return (
    <section className="detail-section">
      <div className="section-heading">
        <h3>Price history</h3>

        <div className="side-toggle" role="group" aria-label="Chart range">
          {RANGES.map((option) => (
            <button
              key={option.value}
              type="button"
              className={
                option.value === range
                  ? 'side-toggle-button side-toggle-button--active'
                  : 'side-toggle-button'
              }
              aria-pressed={option.value === range}
              onClick={() => setRange(option.value)}
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>

      {body}
    </section>
  )
}

export default PriceChart