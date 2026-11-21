// Mirrors backend/app/models.py (camelCase JSON)

export type Mode = 'fast' | 'quality'
export type Aspect = '1:1' | '16:9' | '9:16'
export type JobStatus = 'queued' | 'running' | 'done' | 'cancelled' | 'failed'

export interface Progress {
  imageIndex: number
  step: number
  totalSteps: number
  // countdown: start from *EtaS at updatedAt and count down locally
  secondsPerStep: number | null
  imageEtaS: number | null
  jobEtaS: number | null
  updatedAt: string | null
}

/** WebSocket /api/ws events */
export type StreamEvent =
  | { type: 'status'; warming: boolean }
  | { type: 'job'; job: Job }
  | { type: 'preview'; jobId: string; imageIndex: number; step: number; dataUrl: string }

export interface Preview {
  imageIndex: number
  step: number
  dataUrl: string
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
  warming: boolean
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

export const SEED_MAX = 2 ** 32 - 1
export const QUALITY_STEPS = { min: 10, max: 60, default: 35 }
export const QUALITY_CFG = { min: 1, max: 10, step: 0.5, default: 5 }
export const FAST_LOCKED = { steps: 8, cfg: 1 }
export const FAST_COUNTS = [1, 2, 3, 4] as const

export const PROMPT_MAX = 2000
export const NEGATIVE_MAX = 1000

export function isFinished(status: JobStatus) {
  return status === 'done' || status === 'failed' || status === 'cancelled'
}
