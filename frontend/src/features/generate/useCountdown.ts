import { useEffect, useState } from 'react'

/** Re-renders every second while `active`; returns Date.now(). */
export function useNow(active: boolean) {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    if (!active) return
    const id = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(id)
  }, [active])
  return now
}

/** Seconds left: the server's estimate minus the time since it was made. Null when unknown. */
export function remaining(etaS: number | null, updatedAt: string | null, now: number) {
  if (etaS == null || !updatedAt) return null
  return Math.max(0, etaS - (now - new Date(updatedAt).getTime()) / 1000)
}
