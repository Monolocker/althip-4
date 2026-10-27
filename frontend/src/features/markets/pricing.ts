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