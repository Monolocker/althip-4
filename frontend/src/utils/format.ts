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

export function formatDateTime(value: string | null): string {
  if (value === null) {
    return "—"
  }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }
  return date.toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  })
}