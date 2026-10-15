export function formatPrice(price: number | null): string {
  if (price === null) {
    return "—"
  }
  return `${(price * 100).toFixed(1)}¢`
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