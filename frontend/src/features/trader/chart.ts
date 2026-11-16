// Chart math for the trader PnL chart (Milestone 26.3). Pure functions,
// like features/markets/chart.ts, whose linearScale and ticks it reuses.

export interface PnlChartPoint {
    time: number // ms since epoch
    value: number // cumulative net PnL, USDC
  }
  
  // The value range to draw: always including 0 (so the zero line is on
  // screen and gains read as above it), padded by 10% so the line never
  // touches the edges. A flat series at 0 still gets a visible range.
  export function pnlDomain(points: PnlChartPoint[]): [number, number] {
    const values = points.map((point) => point.value)
    const min = Math.min(0, ...values)
    const max = Math.max(0, ...values)
    const pad = Math.max((max - min) * 0.1, 1)
    return [min - pad, max + pad]
  }
  
  // A step path: realized PnL changes in jumps (a settlement, a sale), so
  // the line stays flat until the next point, then moves straight up or
  // down. "H" draws horizontally to an x, "V" vertically to a y.
  export function stepPath(
    points: PnlChartPoint[],
    x: (time: number) => number,
    y: (value: number) => number,
  ): string {
    return points
      .map((point, index) =>
        index === 0
          ? `M${x(point.time).toFixed(1)},${y(point.value).toFixed(1)}`
          : `H${x(point.time).toFixed(1)} V${y(point.value).toFixed(1)}`,
      )
      .join(' ')
  }
  
  // Index of the last point at or before `time`: on a step chart that is
  // the value in force at that moment.
  export function valueIndexAt(points: PnlChartPoint[], time: number): number | null {
    let found: number | null = null
    points.forEach((point, index) => {
      if (point.time <= time) {
        found = index
      }
    })
    return found
  }