import type { OutcomeMarket, OutcomeSide } from '../../types/market'

// Market-implied probability (Milestone 18.4).
//
// A binary side settles to $1 or $0, so its price in dollars equals the
// probability the market as a whole is implicitly assigning it: 0.638
// means "63.8%". That is a reading of what traders are paying, not a
// forecast of what will happen, and it only exists when:
//   - the payout is binary (a scalar Long token at 0.638 pays out
//     proportionally; the price is not a probability of anything),
//   - the book is not unreliable (the midpoint of a 0.1c / 99.9c book is
//     an artifact, not a market opinion),
//   - there is a price at all.
export function impliedProbability(
  market: OutcomeMarket,
  side: OutcomeSide,
): number | null {
  return pricesAreProbabilities(market) ? side.price : null
}

// Whether this market's prices can be read as probabilities at all
// (binary payout, usable book). Shared by implied probability and by 
// the price chart's axis units (M19.3)
export function pricesAreProbabilities(market: OutcomeMarket): boolean {
  return market.payout === 'binary' && !isPriceUnreliable(market)
}

// One definition of "this market's price means nothing", shared by 
// market cards, detail panel, implied prob, and sorting. No book data
// (null) is NOT unreliable: w/o evidence, price is never greyed
export function isPriceUnreliable(market: OutcomeMarket): boolean {
    return market.book?.quality === 'unreliable'
}


export function formatProbability(probability: number): string {
  return `${(probability * 100).toFixed(1)}%`
}


// --- 24h movers (Milestone 20.2) ------------------------------------

// A market's 24h move counts only when both the move and the market are
// trustworthy: a usable book (so the current price means something) and
// real trading behind it. Decided in 20.2: a lone 43-contract trade in a
// dead market must not top the movers list.
export const MOVER_MIN_VOLUME = 1_000

export function isMoverEligible(market: OutcomeMarket): boolean {
  return (
    market.change24h !== null &&
    !isPriceUnreliable(market) &&
    (market.volume24h ?? 0) >= MOVER_MIN_VOLUME
  )
}

// The 24h change is shown wherever the current price is usable; the
// volume threshold only governs RANKING, not display.
export function visibleChange(market: OutcomeMarket): number | null {
  return isPriceUnreliable(market) ? null : market.change24h
}

// 0.054 -> "+5.4 pts", -0.032 -> "−3.2 pts" (a real minus sign).
export function formatChange(change: number): string {
  const points = change * 100
  const sign = points > 0 ? '+' : points < 0 ? '−' : ''
  return `${sign}${Math.abs(points).toFixed(1)} pts`
}