import type { Aspect, Mode } from '@/lib/types'

export interface FormValues {
  mode: Mode
  prompt: string
  negativePrompt: string
  aspect: Aspect
}

export const DEFAULT_FORM: FormValues = { mode: 'fast', prompt: '', negativePrompt: '', aspect: '1:1' }
