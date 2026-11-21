import { useCallback, useEffect, useMemo, useState } from 'react'
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
 * All jobs of this Colab session, the one being shown, and live updates over WebSocket /api/ws
 * (job state, a preview after every step, warm-up status). Falls back to polling while the socket is down.
 * `onAuthLost` runs when the server closes the socket with 4401/4429.
 */
export function useGenerate(onAuthLost: () => void) {
  const [jobsById, setJobsById] = useState<Record<string, Job>>({})
  const [currentId, setCurrentId] = useState<string | null>(null)
  const [preview, setPreview] = useState<(Preview & { jobId: string }) | null>(null)
  const [warming, setWarming] = useState(false)
  const [connected, setConnected] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [failedShown] = useState(() => new Set<string>())

  const job = currentId ? (jobsById[currentId] ?? null) : null
  const running = !!job && !isFinished(job.status)

  const acceptJob = useCallback(
    (next: Job) => {
      setJobsById((all) => ({ ...all, [next.id]: next }))
      // Follow the shown job, or switch to a newer one that is running (e.g. started in another tab)
      setCurrentId((cur) => (cur === null || cur === next.id || !isFinished(next.status) ? next.id : cur))
      if (next.status === 'failed' && !failedShown.has(next.id)) {
        failedShown.add(next.id)
        toast.error(next.error ?? 'Generation failed')
      }
    },
    [failedShown],
  )

  // After a reload: the whole session history, newest job shown
  useEffect(() => {
    api
      .listJobs()
      .then((jobs) => {
        setJobsById((all) => Object.fromEntries([...jobs.map((j) => [j.id, j] as const), ...Object.entries(all)]))
        if (jobs.length > 0) setCurrentId((cur) => cur ?? jobs[0].id)
      })
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
        if (ev.type === 'status') setWarming(ev.warming)
        // Count down from the moment we received the estimate, so a wrong PC clock does not matter
        else if (ev.type === 'job')
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
        if (e instanceof ApiError && e.status === 404) setCurrentId(null)
        else setJobsById((all) => ({ ...all })) // try again on the next tick
      }
    }, FALLBACK_POLL_MS)
    return () => window.clearTimeout(timer)
  }, [connected, job, acceptJob])

  const generate = useCallback(
    async (body: JobCreate) => {
      setSubmitting(true)
      try {
        setPreview(null)
        const created = await api.createJob(body)
        acceptJob(created)
        setCurrentId(created.id)
      } catch (e) {
        const msg = e instanceof ApiError ? e.message : 'Could not start the job'
        toast.error(e instanceof ApiError && e.status === 409 ? 'A job is already running' : msg)
      } finally {
        setSubmitting(false)
      }
    },
    [acceptJob],
  )

  const cancel = useCallback(async () => {
    if (!job) return
    try {
      acceptJob(await api.cancelJob(job.id))
    } catch (e) {
      if (e instanceof ApiError && e.status === 409)
        acceptJob(await api.getJob(job.id)) // it just finished
      else toast.error(e instanceof ApiError ? e.message : 'Could not cancel')
    }
  }, [job, acceptJob])

  /** Newest first */
  const jobs = useMemo(() => Object.values(jobsById).sort((a, b) => b.createdAt.localeCompare(a.createdAt)), [jobsById])

  const currentPreview = preview && job && preview.jobId === job.id ? preview : null
  return { job, jobs, preview: currentPreview, running, warming, submitting, connected, generate, cancel }
}
