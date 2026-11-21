import type { Health, Job, JobCreate } from './types'

/** HTTP error from the backend. `status` 0 = network error (backend or tunnel down). */
export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(path, {
      credentials: 'same-origin',
      ...init,
      headers: { 'Content-Type': 'application/json', ...init?.headers },
    })
  } catch {
    throw new ApiError(0, 'Backend is not reachable')
  }
  // Cloudflare returns 502/530 when the Colab side is gone
  if (res.status === 502 || res.status === 503 || res.status === 530) {
    throw new ApiError(0, 'Backend is not reachable')
  }
  if (!res.ok) {
    throw new ApiError(res.status, await errorMessage(res))
  }
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

async function errorMessage(res: Response): Promise<string> {
  try {
    const body = await res.json()
    if (typeof body.detail === 'string') return body.detail
    if (Array.isArray(body.detail) && body.detail.length > 0) {
      // FastAPI 422: [{ loc, msg }]
      return body.detail.map((d: { msg?: string }) => d.msg?.replace(/^Value error, /, '')).join('; ')
    }
  } catch {
    // not JSON
  }
  return `Request failed (${res.status})`
}

export const api = {
  login: (key: string) => request<void>('/api/auth', { method: 'POST', body: JSON.stringify({ key }) }),
  health: () => request<Health>('/api/health'),
  listJobs: () => request<Job[]>('/api/jobs'),
  getJob: (id: string) => request<Job>(`/api/jobs/${encodeURIComponent(id)}`),
  createJob: (body: JobCreate) => request<Job>('/api/jobs', { method: 'POST', body: JSON.stringify(body) }),
  cancelJob: (id: string) => request<Job>(`/api/jobs/${encodeURIComponent(id)}/cancel`, { method: 'POST' }),
}
