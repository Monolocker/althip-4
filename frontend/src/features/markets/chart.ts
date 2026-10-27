import type { Candle } from '../../types/candle'

// Chart math for the hand-built SVG price chart (Milestone 19.2). Pure
// functions only: no React, no DOM, so each piece can be reasoned about
// (and tested) on its own.

export interface ChartPoint {
  time: number // ms since epoch, start of the candle
  value: number // close price, 0..1
  trades: number
}

// Hyperliquid interval -> its length, used to recognise missing candles.
export const INTERVAL_MS: Record<string, number> = {
  '15m': 15 * 60_000,
  '1h': 60 * 60_000,
  '4h': 4 * 60 * 60_000,
  '1d': 24 * 60 * 60_000,
}

export function toPoints(candles: Candle[]): ChartPoint[] {
  return candles.map((candle) => ({
    time: Date.parse(candle.time),
    value: candle.close,
    trades: candle.trades,
  }))
}

// A linear scale maps a value from one interval onto another: from time to
// x pixels, or from price to y pixels. Swapping domain and range gives the
// inverse (pixels back to time), which is how hovering finds a candle.
export function linearScale(
  domain: [number, number],
  range: [number, number],
): (value: number) => number {
  const [d0, d1] = domain
  const [r0, r1] = range
  const span = d1 - d0
  return (value) =>
    span === 0 ? (r0 + r1) / 2 : r0 + ((value - d0) / span) * (r1 - r0)
}

// The price range to draw: the data's min..max, padded by 10% (at least
// 1 cent) so the line never touches the edges, and clamped to 0..1
// because an outcome price cannot leave that range.
export function valueDomain(points: ChartPoint[]): [number, number] {
  const values = points.map((point) => point.value)
  const min = Math.min(...values)
  const max = Math.max(...values)
  const pad = Math.max((max - min) * 0.1, 0.01)
  return [Math.max(0, min - pad), Math.min(1, max + pad)]
}

// Evenly spaced values from min to max inclusive, for gridlines.
export function ticks(domain: [number, number], count: number): number[] {
  const [min, max] = domain
  if (count < 2) return [min]
  const step = (max - min) / (count - 1)
  return Array.from({ length: count }, (_, index) => min + step * index)
}

// True when a point starts a new line segment: the first point, or the
// first point after missing candles.
function startsSegment(points: ChartPoint[], index: number, maxStepMs: number): boolean {
  return index === 0 || points[index].time - points[index - 1].time > maxStepMs
}

// The SVG path for the price line. "M x,y" moves the pen without drawing;
// "L x,y" draws a line to the point. Starting a new "M" after a gap means
// missing candles show as a break in the line, instead of a straight line
// that pretends we know what happened in between.
export function linePath(
  points: ChartPoint[],
  x: (time: number) => number,
  y: (value: number) => number,
  maxStepMs: number,
): string {
  return points
    .map((point, index) => {
      const command = startsSegment(points, index, maxStepMs) ? 'M' : 'L'
      return `${command}${x(point.time).toFixed(1)},${y(point.value).toFixed(1)}`
    })
    .join(' ')
}

// Points with a gap on both sides form a segment of length one, which a
// line cannot show; the chart draws a dot for each of these instead.
export function isolatedIndices(points: ChartPoint[], maxStepMs: number): number[] {
  return points.flatMap((_, index) => {
    const gapBefore = startsSegment(points, index, maxStepMs)
    const gapAfter =
      index === points.length - 1 || startsSegment(points, index + 1, maxStepMs)
    return gapBefore && gapAfter ? [index] : []
  })
}

// Index of the point closest in time (a linear scan: at most ~365 points).
export function nearestIndex(points: ChartPoint[], time: number): number | null {
  let best: number | null = null
  let bestDistance = Infinity
  points.forEach((point, index) => {
    const distance = Math.abs(point.time - time)
    if (distance < bestDistance) {
      best = index
      bestDistance = distance
    }
  })
  return best
}

const axisDay = new Intl.DateTimeFormat('en-US', {
  timeZone: 'UTC',
  month: 'short',
  day: 'numeric',
})
const axisDayTime = new Intl.DateTimeFormat('en-US', {
  timeZone: 'UTC',
  month: 'short',
  day: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  hourCycle: 'h23',
})

// Axis and readout labels, in UTC like every other market time (18.2).
// Daily candles only need the date; finer ones need the time too.
export function formatChartTime(time: number, interval: string): string {
  const formatter = interval === '1d' ? axisDay : axisDayTime
  return `${formatter.format(time)} UTC`
}