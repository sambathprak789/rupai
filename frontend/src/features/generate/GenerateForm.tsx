import type { FormEvent, KeyboardEvent } from 'react'
import { RectangleHorizontal, RectangleVertical, Sparkles, Square, Timer, Zap } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { ASPECTS, NEGATIVE_MAX, PROMPT_MAX, type Aspect, type Mode } from '@/lib/types'

import type { FormValues } from './formValues'

const ASPECT_ICON = { '1:1': Square, '16:9': RectangleHorizontal, '9:16': RectangleVertical } as const

interface Props {
  values: FormValues
  onChange: (values: FormValues) => void
  onSubmit: (values: FormValues) => void
  disabled: boolean
}

export function GenerateForm({ values, onChange, onSubmit, disabled }: Props) {
  const set = <K extends keyof FormValues>(key: K, value: FormValues[K]) => onChange({ ...values, [key]: value })
  const canSubmit = !disabled && values.prompt.trim().length > 0
  const fast = values.mode === 'fast'

  function submit(e?: FormEvent) {
    e?.preventDefault()
    if (canSubmit) onSubmit(values)
  }

  function onPromptKey(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) submit()
  }

  return (
    <form onSubmit={submit} className="grid gap-5">
      <div className="grid gap-2">
        <Label>Mode</Label>
        <ToggleGroup
          type="single"
          value={values.mode}
          onValueChange={(v) => v && set('mode', v as Mode)}
          aria-label="Mode"
        >
          <ToggleGroupItem value="fast">
            <Zap /> Fast
          </ToggleGroupItem>
          <ToggleGroupItem value="quality">
            <Sparkles /> Quality
          </ToggleGroupItem>
        </ToggleGroup>
        <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <Timer className="size-3.5" />
          {fast ? '8 steps, ~3–4 min per image on T4' : '35 steps, 1 image, ~23 min on T4'}
        </p>
      </div>

      <div className="grid gap-2">
        <div className="flex items-baseline justify-between">
          <Label htmlFor="prompt">Prompt</Label>
          <span className="text-xs text-muted-foreground">
            {values.prompt.length}/{PROMPT_MAX}
          </span>
        </div>
        <Textarea
          id="prompt"
          rows={5}
          maxLength={PROMPT_MAX}
          placeholder="A blue ceramic mug on a wooden table, soft morning light…"
          value={values.prompt}
          onChange={(e) => set('prompt', e.target.value)}
          onKeyDown={onPromptKey}
          className="max-h-72"
        />
      </div>

      <div className="grid gap-2">
        <Label htmlFor="negative">Negative prompt</Label>
        <Textarea
          id="negative"
          rows={2}
          maxLength={NEGATIVE_MAX}
          disabled={fast}
          placeholder={fast ? '' : 'blurry, low quality…'}
          value={values.negativePrompt}
          onChange={(e) => set('negativePrompt', e.target.value)}
          className="max-h-40"
        />
        {fast && <p className="text-xs text-muted-foreground">Not used in Fast mode.</p>}
      </div>

      <div className="grid gap-2">
        <Label>Size</Label>
        <ToggleGroup
          type="single"
          value={values.aspect}
          onValueChange={(v) => v && set('aspect', v as Aspect)}
          aria-label="Size"
        >
          {ASPECTS.map((a) => {
            const Icon = ASPECT_ICON[a.value]
            return (
              <ToggleGroupItem key={a.value} value={a.value} title={`${a.label} ${a.size}`}>
                <Icon /> {a.value}
              </ToggleGroupItem>
            )
          })}
        </ToggleGroup>
      </div>

      <Button type="submit" size="lg" disabled={!canSubmit}>
        <Sparkles /> Generate
      </Button>
      <p className="-mt-3 text-center text-xs text-muted-foreground">Ctrl + Enter in the prompt also works</p>
    </form>
  )
}
