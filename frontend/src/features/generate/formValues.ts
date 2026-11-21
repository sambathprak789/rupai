import { QUALITY_CFG, QUALITY_STEPS, SEED_MAX, type Aspect, type Mode } from '@/lib/types'

export interface FormValues {
  mode: Mode
  prompt: string
  negativePrompt: string
  aspect: Aspect
  /** Empty = random seed for each job */
  seed: string
  /** Quality mode only (Fast is locked to 8 steps, CFG 1) */
  steps: number
  cfg: number
}

export const DEFAULT_FORM: FormValues = {
  mode: 'fast',
  prompt: '',
  negativePrompt: '',
  aspect: '1:1',
  seed: '',
  steps: QUALITY_STEPS.default,
  cfg: QUALITY_CFG.default,
}

/** Whole number 0..2^32-1, or null when empty. NaN when invalid. */
export function parseSeed(seed: string): number | null {
  const s = seed.trim()
  if (s === '') return null
  if (!/^\d+$/.test(s)) return Number.NaN
  const n = Number(s)
  return n <= SEED_MAX ? n : Number.NaN
}

export function randomSeed(): string {
  const buf = new Uint32Array(1)
  crypto.getRandomValues(buf)
  return String(buf[0])
}
