import { useCallback, useEffect, useRef, useState } from 'react'

import { api, ApiError } from '@/lib/api'
import type { Health } from '@/lib/types'

const KEY_STORAGE = 'rupai.key'
const HEALTH_POLL_MS = 10_000
const OFFLINE_RETRY_MS = 4_000

export type SessionState =
  | { kind: 'connecting' }
  | { kind: 'need-key'; error?: string }
  | { kind: 'blocked' }
  | { kind: 'backend-offline' }
  | { kind: 'comfy-offline'; health: Health }
  | { kind: 'ready'; health: Health }

function readStoredKey(): string | null {
  try {
    return localStorage.getItem(KEY_STORAGE)
  } catch {
    return null
  }
}

function storeKey(key: string | null) {
  try {
    if (key) localStorage.setItem(KEY_STORAGE, key)
    else localStorage.removeItem(KEY_STORAGE)
  } catch {
    // storage unavailable (private mode): the cookie still works for this tab
  }
}

/** Takes `?key=` from the address bar and removes it right away (spec Item 6.3). */
function takeUrlKey(): string | null {
  const url = new URL(window.location.href)
  const key = url.searchParams.get('key')
  if (key) {
    url.searchParams.delete('key')
    window.history.replaceState(null, '', url.pathname + url.search + url.hash)
  }
  return key
}

/**
 * Auth + backend health (spec 3.1 status screen, 6.1 access key).
 * Order: ?key= in URL -> session cookie -> key saved in localStorage -> ask the user.
 */
export function useSession() {
  const [state, setState] = useState<SessionState>({ kind: 'connecting' })
  const urlKey = useRef<string | null>(null)
  const started = useRef(false)

  const loginWith = useCallback(async (key: string): Promise<boolean> => {
    try {
      await api.login(key)
      storeKey(key)
      return true
    } catch (e) {
      if (e instanceof ApiError && e.status === 429) setState({ kind: 'blocked' })
      else if (e instanceof ApiError && e.status === 401) {
        storeKey(null)
        setState({ kind: 'need-key', error: 'Wrong key' })
      } else setState({ kind: 'backend-offline' })
      return false
    }
  }, [])

  const refresh = useCallback(async () => {
    // At most one re-login with the saved key per check (cookie missing or expired)
    for (let attempt = 0; attempt < 2; attempt++) {
      try {
        const health = await api.health()
        setState(health.status === 'ready' ? { kind: 'ready', health } : { kind: 'comfy-offline', health })
        return
      } catch (e) {
        if (!(e instanceof ApiError) || e.status === 0) {
          setState({ kind: 'backend-offline' })
          return
        }
        if (e.status === 429) {
          setState({ kind: 'blocked' })
          return
        }
        if (e.status !== 401) return
        const saved = attempt === 0 ? readStoredKey() : null
        if (saved && (await loginWith(saved))) continue
        setState((s) => (s.kind === 'need-key' ? s : { kind: 'need-key' }))
        return
      }
    }
  }, [loginWith])

  // First load
  useEffect(() => {
    if (started.current) return // StrictMode runs effects twice in dev
    started.current = true
    urlKey.current = takeUrlKey()
    void (async () => {
      if (urlKey.current && !(await loginWith(urlKey.current))) return
      await refresh()
    })()
  }, [loginWith, refresh])

  // Keep checking: fast retry while offline, slow poll while ready
  useEffect(() => {
    const ms =
      state.kind === 'backend-offline' || state.kind === 'comfy-offline'
        ? OFFLINE_RETRY_MS
        : state.kind === 'ready'
          ? HEALTH_POLL_MS
          : null
    if (ms === null) return
    const id = window.setTimeout(() => void refresh(), ms)
    return () => window.clearTimeout(id)
  }, [state, refresh])

  const submitKey = useCallback(
    async (key: string) => {
      if (await loginWith(key.trim())) await refresh()
    },
    [loginWith, refresh],
  )

  return { state, submitKey, refresh }
}
