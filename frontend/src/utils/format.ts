export function formatPrice(price: number | null): string {
  if (price === null) {
    return "—"
  }
  return `${(price * 100).toFixed(1)}¢`
}

// 21876 -> "21.9K", 1250000 -> "1.3M". Compact on purpose: volume is
// for comparing markets at a glance, not for accounting.
const compactNumber = new Intl.NumberFormat(undefined, {
  notation: "compact",
  maximumFractionDigits: 1,
})

export function formatVolume(volume: number | null): string {
  if (volume === null) {
    return "—"
  }
  return compactNumber.format(volume)
}

// Milestone 18.2: UTC is the primary time everywhere, because titles and
// resolution rules are rendered in UTC by the backend from Hyperliquid's
// templates. Local time is a secondary reading.

// Fixed "en-US" + timeZone "UTC" so the output matches the backend's
// strftime("%b %d, %Y %H:%M UTC") exactly, whatever the viewer's locale.
const utcFormatter = new Intl.DateTimeFormat("en-US", {
  timeZone: "UTC",
  year: "numeric",
  month: "short",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
})

// The viewer's own locale and time zone, with the zone named
// ("Oct 18, 8:00 AM CDT") so it is never mistaken for UTC.
const localFormatter = new Intl.DateTimeFormat(undefined, {
  month: "short",
  day: "numeric",
  hour: "numeric",
  minute: "2-digit",
  timeZoneName: "short",
})

export interface DisplayTime {
  utc: string
  local: string | null
}

export function formatTime(value: string | null): DisplayTime | null {
  if (value === null) {
    return null
  }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    // Unparseable: show the raw value rather than hide it.
    return { utc: value, local: null }
  }

  // formatToParts returns labeled pieces ({type: "month", value: "Oct"},
  // ...), so we can assemble our exact layout instead of accepting the
  // formatter's punctuation.
  const parts = Object.fromEntries(
    utcFormatter.formatToParts(date).map((part) => [part.type, part.value]),
  )
  return {
    utc: `${parts.month} ${parts.day}, ${parts.year} ${parts.hour}:${parts.minute} UTC`,
    local: localFormatter.format(date),
  }
}