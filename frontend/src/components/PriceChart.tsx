import { useState, type PointerEvent } from 'react'
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
import type { CandleRange, PriceHistory } from '../types/candle'
import { formatPrice } from '../utils/format'

const RANGES: { value: CandleRange; label: string }[] = [
  { value: '1d', label: '1D' },
  { value: '1w', label: '1W' },
  { value: '1m', label: '1M' },
  { value: 'all', label: 'All' },
]

// The chart is drawn in this coordinate system; the viewBox scales it to
// whatever width the panel has. Padding leaves room for axis labels.
const WIDTH = 640
const HEIGHT = 220
const PAD = { top: 12, right: 56, bottom: 26, left: 8 }

interface ChartSvgProps {
  history: PriceHistory
}

function ChartSvg({ history }: ChartSvgProps) {
  const [hoverIndex, setHoverIndex] = useState<number | null>(null)

  const points = toPoints(history.candles)
  const first = points[0]
  const last = points[points.length - 1]

  // Time runs left to right. Price runs bottom to top, so the y range is
  // written [bottom, top]: SVG's y axis grows DOWNWARD.
  const xDomain: [number, number] = [first.time, last.time]
  const xRange: [number, number] = [PAD.left, WIDTH - PAD.right]
  const x = linearScale(xDomain, xRange)
  const xToTime = linearScale(xRange, xDomain)
  const yDomain = valueDomain(points)
  const y = linearScale(yDomain, [HEIGHT - PAD.bottom, PAD.top])

  // A step of up to 1.5 intervals counts as consecutive; anything longer
  // means candles are missing, and the line breaks there.
  const maxStepMs = (INTERVAL_MS[history.interval] ?? Infinity) * 1.5
  const path = linePath(points, x, y, maxStepMs)
  const dots = isolatedIndices(points, maxStepMs)

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
        aria-label={`Price history, ${points.length} points, latest ${formatPrice(last.value)}`}
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
              {formatPrice(value)}
            </text>
          </g>
        ))}

        <text className="price-chart-label" x={PAD.left} y={HEIGHT - 6}>
          {formatChartTime(first.time, history.interval)}
        </text>
        <text
          className="price-chart-label"
          x={WIDTH - PAD.right}
          y={HEIGHT - 6}
          textAnchor="end"
        >
          {formatChartTime(last.time, history.interval)}
        </text>

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

        {hovered !== null && (
          <g>
            <line
              className="price-chart-crosshair"
              x1={x(hovered.time)}
              x2={x(hovered.time)}
              y1={PAD.top}
              y2={HEIGHT - PAD.bottom}
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
        <strong>{formatPrice(shown.value)}</strong> ·{' '}
        {formatChartTime(shown.time, history.interval)} · {shown.trades}{' '}
        {shown.trades === 1 ? 'trade' : 'trades'}
      </p>
    </>
  )
}

interface PriceChartProps {
  marketId: string
  isSettled: boolean
}

// Price history of the market's first side, from Hyperliquid candles
// (Milestone 19). The selected range survives switching markets.
function PriceChart({ marketId, isSettled }: PriceChartProps) {
  const [range, setRange] = useState<CandleRange>('1w')
  const history = usePriceHistory(marketId, range, !isSettled)

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
        Could not load price history: {history.error.message}
      </p>
    )
  } else if (history.data.candles.length === 0) {
    body = <p className="detail-note">No trading history yet.</p>
  } else {
    body = <ChartSvg history={history.data} />
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