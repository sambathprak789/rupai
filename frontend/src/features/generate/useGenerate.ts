import { useCallback, useEffect, useRef, useState } from 'react'
import { toast } from 'sonner'

import { api, ApiError } from '@/lib/api'
import { isFinished, type Job, type JobCreate, type Preview, type StreamEvent } from '@/lib/types'

const FALLBACK_POLL_MS = 2000
const RECONNECT_MAX_MS = 10_000

function streamUrl() {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${proto}//${window.location.host}/api/ws`
}

/**
 * Creates jobs and follows them live over WebSocket /api/ws (job state + a preview after every step).
 * Falls back to polling while the socket is down. `onAuthLost` runs when the server closes with 4401.
 */
export function useGenerate(onAuthLost: () => void) {
  const [job, setJob] = useState<Job | null>(null)
  const [preview, setPreview] = useState<(Preview & { jobId: string }) | null>(null)
  const [connected, setConnected] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const lastFailedId = useRef<string | null>(null)

  const running = !!job && !isFinished(job.status)

  const acceptJob = useCallback((next: Job) => {
    // Follow the current job, or switch to a newer one that is running
    setJob((prev) => (!prev || prev.id === next.id || !isFinished(next.status) ? next : prev))
    if (next.status === 'failed' && lastFailedId.current !== next.id) {
      lastFailedId.current = next.id
      toast.error(next.error ?? 'Generation failed')
    }
  }, [])

  // After a reload: show the newest job
  useEffect(() => {
    api
      .listJobs()
      .then((jobs) => jobs.length > 0 && setJob((current) => current ?? jobs[0]))
      .catch(() => {})
  }, [])

  // Live stream with reconnect
  useEffect(() => {
    let ws: WebSocket | null = null
    let retryTimer: number | undefined
    let delay = 1000
    let stopped = false

    const connect = () => {
      ws = new WebSocket(streamUrl())
      ws.onopen = () => {
        delay = 1000
        setConnected(true)
      }
      ws.onmessage = (msg) => {
        const ev = JSON.parse(msg.data) as StreamEvent
        // Count down from the moment we received the estimate, so a wrong PC clock does not matter
        if (ev.type === 'job')
          acceptJob({ ...ev.job, progress: { ...ev.job.progress, updatedAt: new Date().toISOString() } })
        else setPreview({ jobId: ev.jobId, imageIndex: ev.imageIndex, step: ev.step, dataUrl: ev.dataUrl })
      }
      ws.onclose = (e) => {
        setConnected(false)
        if (stopped) return
        if (e.code === 4401 || e.code === 4429) {
          onAuthLost()
          return
        }
        retryTimer = window.setTimeout(connect, delay)
        delay = Math.min(delay * 2, RECONNECT_MAX_MS)
      }
    }
    connect()
    return () => {
      stopped = true
      window.clearTimeout(retryTimer)
      ws?.close()
    }
  }, [acceptJob, onAuthLost])

  // Fallback: poll while the socket is down and a job runs
  useEffect(() => {
    if (connected || !job || isFinished(job.status)) return
    const timer = window.setTimeout(async () => {
      try {
        acceptJob(await api.getJob(job.id))
      } catch (e) {
        if (e instanceof ApiError && e.status === 404) setJob(null)
        else setJob((j) => (j ? { ...j } : j)) // try again on the next tick
      }
    }, FALLBACK_POLL_MS)
    return () => window.clearTimeout(timer)
  }, [connected, job, acceptJob])

  const generate = useCallback(
    async (body: JobCreate) => {
      setSubmitting(true)
      try {
        setPreview(null)
        acceptJob(await api.createJob(body))
      } catch (e) {
        const msg = e instanceof ApiError ? e.message : 'Could not start the job'
        toast.error(e instanceof ApiError && e.status === 409 ? 'A job is already running' : msg)
      } finally {
        setSubmitting(false)
      }
    },
    [acceptJob],
  )

  const currentPreview = preview && job && preview.jobId === job.id ? preview : null
  return { job, preview: currentPreview, running, submitting, connected, generate }
}
