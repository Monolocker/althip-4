import type { LeaderboardWindow } from '../../types/leaderboard'
import { WINDOWS } from '../leaderboard/options'

// The trader dashboard lives in the URL (decision, 26.3): ?trader=0x…&window=30d.
// No router library: the History API (pushState / popstate) is enough
// for one optional view, so a link can be shared and Back works.

export interface TraderLocation {
  address: string
  window: LeaderboardWindow
}

const ADDRESS = /^0x[0-9a-fA-F]{40}$/

function isWindow(value: string | null): value is LeaderboardWindow {
  return value !== null && (WINDOWS as string[]).includes(value)
}

// What the current URL asks for; null when it names no (valid) trader.
export function readTraderLocation(search: string = window.location.search): TraderLocation | null {
  const params = new URLSearchParams(search)
  const address = params.get('trader')
  if (address === null || !ADDRESS.test(address)) {
    return null
  }
  const timeWindow = params.get('window')
  return { address: address.toLowerCase(), window: isWindow(timeWindow) ? timeWindow : '30d' }
}

// The URL for a trader's dashboard, or the plain app URL for null.
export function traderHref(location: TraderLocation | null): string {
  if (location === null) {
    return window.location.pathname
  }
  const params = new URLSearchParams({ trader: location.address, window: location.window })
  return `${window.location.pathname}?${params.toString()}`
}