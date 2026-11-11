import type { LeaderboardSort, LeaderboardWindow } from '../../types/leaderboard'

// Display order of the toggles.
export const WINDOWS: LeaderboardWindow[] = ['24h', '7d', '30d', 'all']
export const SORTS: LeaderboardSort[] = ['pnl', 'volume', 'fills']

// Record<Union, string> makes the compiler insist on a label for every
// member: adding a window to the type without a label is a build error.
export const WINDOW_LABELS: Record<LeaderboardWindow, string> = {
  '24h': '24h',
  '7d': '7d',
  '30d': '30d',
  all: 'All-Time',
}

export const SORT_LABELS: Record<LeaderboardSort, string> = {
  pnl: 'Net PnL',
  volume: 'Volume',
  fills: 'Fills',
}