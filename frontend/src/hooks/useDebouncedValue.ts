import { useEffect, useState } from 'react'

// The value, but only once it has stopped changing for `delayMs`
// (Milestone 22.4). Typing "1500" would otherwise send four requests
// (1, 15, 150, 1500); debounced, it sends one.
export function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value)

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs)
    // Each new value cancels the previous timer: only the last one fires.
    return () => clearTimeout(timer)
  }, [value, delayMs])

  return debounced
}