// Mirrors backend/app/models.py (camelCase JSON)

export type Mode = 'fast' | 'quality'
export type Aspect = '1:1' | '16:9' | '9:16'
export type JobStatus = 'queued' | 'running' | 'done' | 'cancelled' | 'failed'

export interface Progress {
  imageIndex: number
  step: number
  totalSteps: number
}

export interface GeneratedImage {
  id: string
  jobId: string
  index: number
  seed: number
  mode: Mode
  filename: string
  url: string
  width: number
  height: number
  createdAt: string
}

export interface Job {
  id: string
  mode: Mode
  prompt: string
  negativePrompt: string
  aspect: Aspect
  width: number
  height: number
  steps: number
  cfg: number
  baseSeed: number
  count: number
  sourceImageId: string | null
  status: JobStatus
  progress: Progress
  error: string | null
  createdAt: string
  finishedAt: string | null
  images: GeneratedImage[]
}

export interface JobCreate {
  mode: Mode
  prompt: string
  negativePrompt?: string
  aspect: Aspect
  steps?: number
  cfg?: number
  baseSeed?: number
  count?: number
  sourceImageId?: string
}

export interface Health {
  status: 'ready' | 'offline'
  mock: boolean
  comfy: 'ready' | 'offline'
  modelQuant: string
  busy: boolean
  vramTotalGb: number | null
  vramFreeGb: number | null
  ramTotalGb: number | null
  ramUsedGb: number | null
}

export const ASPECTS: { value: Aspect; label: string; size: string }[] = [
  { value: '1:1', label: 'Square', size: '1024×1024' },
  { value: '16:9', label: 'Landscape', size: '1344×768' },
  { value: '9:16', label: 'Portrait', size: '768×1344' },
]

export const PROMPT_MAX = 2000
export const NEGATIVE_MAX = 1000

export function isFinished(status: JobStatus) {
  return status === 'done' || status === 'failed' || status === 'cancelled'
}
