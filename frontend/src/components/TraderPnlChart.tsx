import { useState, type PointerEvent } from 'react'
import { formatChartTime, linearScale, ticks } from '../features/markets/chart'
import { pnlDomain, stepPath, valueIndexAt, type PnlChartPoint } from '../features/trader/chart'
import type { LeaderboardWindow } from '../types/leaderboard'
import type { PnlPoint } from '../types/trader'
import { formatUsd } from '../utils/format'

// Drawn in this coordinate system; the viewBox scales it to the panel.
const WIDTH = 520
const HEIGHT = 230
const PAD = { left: 8, right: 72, top: 12, bottom: 200 }
const TIME_LABEL_Y = HEIGHT - 8

// Axis labels: compact dollars, so "-$12.4K" fits beside the plot.
const compactUsd = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  notation: 'compact',
  maximumFractionDigits: 1,
  signDisplay: 'exceptZero',
})

interface TraderPnlChartProps {
  series: PnlPoint[]
  timeWindow: LeaderboardWindow
}

// Cumulative realized PnL after fees over the window (Milestone 26.3),
// as a step line: realized PnL moves in jumps, never smoothly.
function TraderPnlChart({ series, timeWindow }: TraderPnlChartProps) {
  const [hoverIndex, setHoverIndex] = useState<number | null>(null)

  const points: PnlChartPoint[] = series.map((point) => ({
    time: Date.parse(point.time),
    value: point.pnl,
  }))
  if (points.length < 2) {
    return <p className="detail-note">No realized PnL in this window.</p>
  }

  const first = points[0]
  const last = points[points.length - 1]
  const xDomain: [number, number] = [first.time, last.time]
  const xRange: [number, number] = [PAD.left, WIDTH - PAD.right]
  const x = linearScale(xDomain, xRange)
  const xToTime = linearScale(xRange, xDomain)
  const yDomain = pnlDomain(points)
  // [bottom, top]: SVG's y axis grows downward.
  const y = linearScale(yDomain, [PAD.bottom, PAD.top])
  // 1-day buckets only need dates on the axis; finer ones need times.
  const interval = timeWindow === 'all' ? '1d' : '1h'

  const hovered = hoverIndex !== null ? (points[hoverIndex] ?? null) : null
  const shown = hovered ?? last

  function handlePointerMove(event: PointerEvent<SVGSVGElement>) {
    const box = event.currentTarget.getBoundingClientRect()
    const chartX = ((event.clientX - box.left) / box.width) * WIDTH
    setHoverIndex(valueIndexAt(points, xToTime(chartX)))
  }

  return (
    <>
      <p className="trader-chart-readout">
        <span className={shown.value > 0 ? 'pnl pnl--up' : shown.value < 0 ? 'pnl pnl--down' : 'pnl'}>
          {formatUsd(shown.value)}
        </span>{' '}
        <span className="leaderboard-muted">{formatChartTime(shown.time, interval)}</span>
      </p>
      <svg
        className="trader-chart"
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        role="img"
        aria-label={`Cumulative realized PnL, latest ${formatUsd(last.value)}`}
        onPointerMove={handlePointerMove}
        onPointerLeave={() => setHoverIndex(null)}
      >
        {ticks(yDomain, 4).map((value) => (
          <g key={value}>
            <line className="price-chart-grid" x1={PAD.left} x2={WIDTH - PAD.right} y1={y(value)} y2={y(value)} />
            <text className="price-chart-label" x={WIDTH - PAD.right + 6} y={y(value)} dominantBaseline="middle">
              {compactUsd.format(value)}
            </text>
          </g>
        ))}
        <line className="trader-chart-zero" x1={PAD.left} x2={WIDTH - PAD.right} y1={y(0)} y2={y(0)} />
        <path className="trader-chart-line" d={stepPath(points, x, y)} />
        {hovered !== null && (
          <circle className="price-chart-dot" cx={x(hovered.time)} cy={y(hovered.value)} r={3.5} />
        )}
        <text className="price-chart-label" x={PAD.left} y={TIME_LABEL_Y}>
          {formatChartTime(first.time, '1d')}
        </text>
        <text className="price-chart-label" x={WIDTH - PAD.right} y={TIME_LABEL_Y} textAnchor="end">
          {formatChartTime(last.time, '1d')}
        </text>
      </svg>
    </>
  )
}

export default TraderPnlChart