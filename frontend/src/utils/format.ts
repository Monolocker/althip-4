export function formatPrice(price: number | null): string {
    if (price === null) {
      return "—"
    }
    return `${(price * 100).toFixed(1)}¢`
  }
  
  export function formatCloseTime(closesAt: string | null): string {
    if (closesAt === null) {
      return "No close time"
    }
    const date = new Date(closesAt)
    if (Number.isNaN(date.getTime())) {
      return closesAt
    }
    return date.toLocaleString(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    })
  }