import { useEffect, useState, type FormEvent, type KeyboardEvent } from 'react'
import {
  ChevronDown,
  CircleStop,
  Dices,
  Images,
  RectangleHorizontal,
  RectangleVertical,
  Sparkles,
  Square,
  Timer,
  X,
  Zap,
} from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Slider } from '@/components/ui/slider'
import { Textarea } from '@/components/ui/textarea'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import {
  ASPECTS,
  FAST_COUNTS,
  FAST_LOCKED,
  NEGATIVE_MAX,
  PROMPT_MAX,
  QUALITY_CFG,
  QUALITY_STEPS,
  type Aspect,
  type Mode,
} from '@/lib/types'

import { parseSeed, randomSeed, type FormValues } from './formValues'

const ASPECT_ICON = { '1:1': Square, '16:9': RectangleHorizontal, '9:16': RectangleVertical } as const

interface Props {
  values: FormValues
  onChange: (values: FormValues) => void
  onSubmit: (values: FormValues) => void
  disabled: boolean
  running: boolean
  onCancel: () => Promise<void>
}

/** Two clicks within 4 s, so a long Quality job is not lost by accident. */
function CancelButton({ onCancel }: { onCancel: () => Promise<void> }) {
  const [armed, setArmed] = useState(false)
  const [busy, setBusy] = useState(false)
  useEffect(() => {
    if (!armed) return
    const id = window.setTimeout(() => setArmed(false), 4000)
    return () => window.clearTimeout(id)
  }, [armed])

  async function click() {
    if (!armed) {
      setArmed(true)
      return
    }
    setBusy(true)
    await onCancel()
    setBusy(false)
    setArmed(false)
  }

  return (
    <Button type="button" variant={armed ? 'destructive' : 'outline'} size="lg" onClick={click} disabled={busy}>
      <CircleStop /> {busy ? 'Cancelling…' : armed ? 'Click again to cancel' : 'Cancel'}
    </Button>
  )
}

export function GenerateForm({ values, onChange, onSubmit, disabled, running, onCancel }: Props) {
  const set = <K extends keyof FormValues>(key: K, value: FormValues[K]) => onChange({ ...values, [key]: value })
  const [advancedOpen, setAdvancedOpen] = useState(false)
  const seedInvalid = Number.isNaN(parseSeed(values.seed))
  const canSubmit = !disabled && values.prompt.trim().length > 0 && !seedInvalid
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
          {fast
            ? `8 steps, ~3–4 min per image on T4${values.count > 1 ? ` (~${values.count * 3}–${values.count * 4} min total)` : ''}`
            : `${values.steps} steps, 1 image, ~${Math.round((values.steps * 38.6 + 45) / 60)} min on T4`}
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

      <div className="grid gap-2">
        <Label>Images</Label>
        {fast ? (
          <ToggleGroup
            type="single"
            value={String(values.count)}
            onValueChange={(v) => v && set('count', Number(v))}
            aria-label="Images"
          >
            {FAST_COUNTS.map((n) => (
              <ToggleGroupItem key={n} value={String(n)}>
                {n}
              </ToggleGroupItem>
            ))}
          </ToggleGroup>
        ) : (
          <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Images className="size-3.5" /> Quality renders 1 image per job.
          </p>
        )}
      </div>

      <Collapsible open={advancedOpen || seedInvalid} onOpenChange={setAdvancedOpen} className="grid gap-4">
        <CollapsibleTrigger asChild>
          <Button type="button" variant="ghost" size="sm" className="justify-between px-2 text-muted-foreground">
            Advanced
            <ChevronDown className={advancedOpen ? 'rotate-180 transition-transform' : 'transition-transform'} />
          </Button>
        </CollapsibleTrigger>
        <CollapsibleContent className="grid gap-5">
          <div className="grid gap-2">
            <Label htmlFor="seed">Seed</Label>
            <div className="flex gap-2">
              <Input
                id="seed"
                inputMode="numeric"
                placeholder="Random"
                value={values.seed}
                onChange={(e) => set('seed', e.target.value)}
                aria-invalid={seedInvalid}
              />
              <Button
                type="button"
                variant="outline"
                size="icon"
                title="Random seed"
                onClick={() => set('seed', randomSeed())}
              >
                <Dices />
              </Button>
              <Button
                type="button"
                variant="outline"
                size="icon"
                title="Clear (random each time)"
                onClick={() => set('seed', '')}
                disabled={!values.seed}
              >
                <X />
              </Button>
            </div>
            <p className={seedInvalid ? 'text-xs text-destructive' : 'text-xs text-muted-foreground'}>
              {seedInvalid ? 'Whole number from 0 to 4294967295.' : 'Empty = a new random seed every time.'}
            </p>
          </div>

          {fast ? (
            <p className="text-xs text-muted-foreground">
              Fast mode is locked to {FAST_LOCKED.steps} steps and CFG {FAST_LOCKED.cfg.toFixed(1)}.
            </p>
          ) : (
            <>
              <div className="grid gap-3">
                <div className="flex items-baseline justify-between">
                  <Label>Steps</Label>
                  <span className="text-sm tabular-nums" data-testid="steps-value">
                    {values.steps}
                  </span>
                </div>
                <Slider
                  aria-label="Steps"
                  min={QUALITY_STEPS.min}
                  max={QUALITY_STEPS.max}
                  step={1}
                  value={[values.steps]}
                  onValueChange={([v]) => set('steps', v)}
                />
              </div>
              <div className="grid gap-3">
                <div className="flex items-baseline justify-between">
                  <Label>CFG</Label>
                  <span className="text-sm tabular-nums" data-testid="cfg-value">
                    {values.cfg.toFixed(1)}
                  </span>
                </div>
                <Slider
                  aria-label="CFG"
                  min={QUALITY_CFG.min}
                  max={QUALITY_CFG.max}
                  step={QUALITY_CFG.step}
                  value={[values.cfg]}
                  onValueChange={([v]) => set('cfg', v)}
                />
              </div>
              <Button
                type="button"
                variant="link"
                size="sm"
                className="h-auto justify-start p-0 text-xs"
                onClick={() => onChange({ ...values, steps: QUALITY_STEPS.default, cfg: QUALITY_CFG.default })}
              >
                Reset to {QUALITY_STEPS.default} steps, CFG {QUALITY_CFG.default.toFixed(1)}
              </Button>
            </>
          )}
        </CollapsibleContent>
      </Collapsible>

      {running ? (
        <CancelButton onCancel={onCancel} />
      ) : (
        <Button type="submit" size="lg" disabled={!canSubmit}>
          <Sparkles /> Generate{fast && values.count > 1 ? ` ${values.count} images` : ''}
        </Button>
      )}
      <p className="-mt-3 text-center text-xs text-muted-foreground">Ctrl + Enter in the prompt also works</p>
    </form>
  )
}
