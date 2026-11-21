import { useCallback, useMemo, useState } from 'react'
import { Loader2 } from 'lucide-react'
import { toast } from 'sonner'

import { Badge } from '@/components/ui/badge'
import { Toaster } from '@/components/ui/sonner'
import { KeyScreen } from '@/features/auth/KeyScreen'
import { useSession } from '@/features/auth/useSession'
import { DEFAULT_FORM, parseSeed, type FormValues } from '@/features/generate/formValues'
import { GenerateForm } from '@/features/generate/GenerateForm'
import { ResultPanel } from '@/features/generate/ResultPanel'
import { useGenerate } from '@/features/generate/useGenerate'
import { Gallery } from '@/features/gallery/Gallery'
import { buildIndex } from '@/features/gallery/imageIndex'
import { Lightbox } from '@/features/gallery/Lightbox'
import { StatusScreen } from '@/features/status/StatusScreen'
import type { GeneratedImage, Health } from '@/lib/types'

function Workspace({ health, onAuthLost }: { health: Health; onAuthLost: () => void }) {
  const [form, setForm] = useState<FormValues>(DEFAULT_FORM)
  const [openImageId, setOpenImageId] = useState<string | null>(null)
  const { job, jobs, preview, running, warming, submitting, generate, cancel } = useGenerate(onAuthLost)
  const index = useMemo(() => buildIndex(jobs), [jobs])
  const busy = running || submitting

  /** Reuse (spec Flow 4): this image's prompt, mode, size, seed and settings go back into the form */
  function reuse(image: GeneratedImage) {
    const src = index.jobById.get(image.jobId)
    if (!src) return
    setForm((f) => ({
      ...f,
      mode: src.mode,
      prompt: src.prompt,
      negativePrompt: src.negativePrompt.trim() ? src.negativePrompt : '',
      aspect: src.aspect,
      seed: String(image.seed),
      count: 1,
      ...(src.mode === 'quality' ? { steps: src.steps, cfg: src.cfg } : {}),
    }))
    window.scrollTo({ top: 0, behavior: 'smooth' })
    toast.success('Settings loaded into the form')
  }

  /** Render in Quality (spec Flow 3): same prompt, seed and size; Quality mode; starts right away */
  function renderInQuality(image: GeneratedImage) {
    const src = index.jobById.get(image.jobId)
    if (!src) return
    setForm((f) => ({
      ...f,
      mode: 'quality',
      prompt: src.prompt,
      aspect: src.aspect,
      seed: String(image.seed),
      count: 1,
    }))
    void generate({
      mode: 'quality',
      prompt: src.prompt,
      negativePrompt: form.negativePrompt || src.negativePrompt,
      aspect: src.aspect,
      baseSeed: image.seed,
      steps: form.steps,
      cfg: form.cfg,
      count: 1,
      sourceImageId: image.id,
    })
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const actions = { onReuse: reuse, onRenderQuality: renderInQuality, busy }

  function onSubmit(v: FormValues) {
    const quality = v.mode === 'quality'
    void generate({
      mode: v.mode,
      prompt: v.prompt,
      negativePrompt: quality ? v.negativePrompt : undefined,
      aspect: v.aspect,
      baseSeed: parseSeed(v.seed) ?? undefined,
      steps: quality ? v.steps : undefined,
      cfg: quality ? v.cfg : undefined,
      count: quality ? 1 : v.count,
    })
  }

  return (
    <div className="min-h-svh">
      <header className="sticky top-0 z-10 flex h-14 items-center justify-between border-b bg-background/80 px-4 backdrop-blur md:px-6">
        <span className="text-lg font-semibold tracking-tight">
          Rup<span className="text-primary">AI</span>
        </span>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          {(warming || health.warming) && (
            <Badge variant="outline" className="gap-1.5" role="status">
              <Loader2 className="animate-spin" /> Warming up…
            </Badge>
          )}
          {health.mock && <Badge variant="outline">Mock</Badge>}
          <span className="hidden sm:inline">{health.modelQuant}</span>
          {health.vramTotalGb && (
            <span className="hidden sm:inline">
              · VRAM {health.vramFreeGb}/{health.vramTotalGb} GB free
            </span>
          )}
          <span className="size-2 rounded-full bg-emerald-500" aria-label="Backend online" />
        </div>
      </header>

      <div className="mx-auto flex max-w-[1600px] flex-col gap-6 p-4 md:flex-row md:items-start md:p-6">
        <aside className="w-full shrink-0 rounded-xl border bg-card p-5 md:sticky md:top-20 md:w-[360px]">
          <GenerateForm
            values={form}
            onChange={setForm}
            onSubmit={onSubmit}
            disabled={busy}
            running={running}
            onCancel={cancel}
          />
        </aside>
        <main className="grid min-w-0 flex-1 gap-8">
          <ResultPanel job={job} preview={preview} onOpen={setOpenImageId} actions={actions} />
          <Gallery index={index} hideJobId={job?.id ?? null} onOpen={setOpenImageId} />
        </main>
      </div>
      <Lightbox imageId={openImageId} index={index} onSelect={setOpenImageId} {...actions} />
    </div>
  )
}

export default function App() {
  const { state, submitKey, refresh } = useSession()
  const onAuthLost = useCallback(() => void refresh(), [refresh])

  let content
  switch (state.kind) {
    case 'ready':
      content = <Workspace health={state.health} onAuthLost={onAuthLost} />
      break
    case 'need-key':
      content = <KeyScreen error={state.error} onSubmit={submitKey} />
      break
    case 'connecting':
    case 'backend-offline':
    case 'blocked':
      content = <StatusScreen variant={state.kind} onRetry={() => void refresh()} />
      break
    case 'comfy-offline':
      content = <StatusScreen variant="comfy-offline" onRetry={() => void refresh()} />
      break
  }

  return (
    <>
      {content}
      <Toaster />
    </>
  )
}
