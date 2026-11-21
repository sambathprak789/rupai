import { useCallback, useEffect, useRef, useState } from 'react'
import { toast } from 'sonner'

import { api, ApiError } from '@/lib/api'
import { isFinished, type Job, type JobCreate } from '@/lib/types'

const POLL_MS = 1000

/** Creates a job and polls it until it finishes. M5 swaps polling for WebSocket progress. */
export function useGenerate() {
  const [job, setJob] = useState<Job | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const pollId = useRef<string | null>(null)

  const running = !!job && !isFinished(job.status)

  // After a reload: show the newest job, keep polling if it still runs
  useEffect(() => {
    api
      .listJobs()
      .then((jobs) => {
        if (jobs.length > 0) setJob((current) => current ?? jobs[0])
      })
      .catch(() => {})
  }, [])

  useEffect(() => {
    if (!job || isFinished(job.status)) return
    pollId.current = job.id
    const timer = window.setTimeout(async () => {
      try {
        const next = await api.getJob(job.id)
        if (pollId.current !== next.id) return
        setJob(next)
        if (next.status === 'failed') toast.error(next.error ?? 'Generation failed')
      } catch (e) {
        // keep the last state; the session hook shows the offline screen if needed
        if (e instanceof ApiError && e.status === 404) setJob(null)
        else setJob((j) => (j ? { ...j } : j)) // schedule another poll
      }
    }, POLL_MS)
    return () => window.clearTimeout(timer)
  }, [job])

  const generate = useCallback(async (body: JobCreate) => {
    setSubmitting(true)
    try {
      setJob(await api.createJob(body))
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : 'Could not start the job'
      toast.error(e instanceof ApiError && e.status === 409 ? 'A job is already running' : msg)
    } finally {
      setSubmitting(false)
    }
  }, [])

  return { job, running, submitting, generate }
}
