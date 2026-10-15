import { useEffect, useState } from 'react'

// The current time as React state, refreshed every `intervalMs`.
// Components derive time-dependent values from this instead of calling
// Date.now() during render, which would make rendering impure and
// would never update as time passes.
export function useNow(intervalMs: number): number {
  // Lazy initializer: the function runs once, on the first render only.
  const [now, setNow] = useState(() => Date.now())

  useEffect(() => {
    const timerId = window.setInterval(() => {
      setNow(Date.now())
    }, intervalMs)

    // Cleanup: stop the timer when the component unmounts or the
    // interval changes, so no orphaned timers keep calling setNow.
    return () => window.clearInterval(timerId)
  }, [intervalMs])

  return now
}