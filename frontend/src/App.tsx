import { useState } from 'react'

import { Badge } from '@/components/ui/badge'
import { Toaster } from '@/components/ui/sonner'
import { KeyScreen } from '@/features/auth/KeyScreen'
import { useSession } from '@/features/auth/useSession'
import { DEFAULT_FORM, type FormValues } from '@/features/generate/formValues'
import { GenerateForm } from '@/features/generate/GenerateForm'
import { ResultPanel } from '@/features/generate/ResultPanel'
import { useGenerate } from '@/features/generate/useGenerate'
import { StatusScreen } from '@/features/status/StatusScreen'
import type { Health } from '@/lib/types'

function Workspace({ health }: { health: Health }) {
  const [form, setForm] = useState<FormValues>(DEFAULT_FORM)
  const { job, running, submitting, generate } = useGenerate()

  function onSubmit(v: FormValues) {
    void generate({
      mode: v.mode,
      prompt: v.prompt,
      negativePrompt: v.mode === 'quality' ? v.negativePrompt : undefined,
      aspect: v.aspect,
      count: 1,
    })
  }

  return (
    <div className="min-h-svh">
      <header className="sticky top-0 z-10 flex h-14 items-center justify-between border-b bg-background/80 px-4 backdrop-blur md:px-6">
        <span className="text-lg font-semibold tracking-tight">
          Rup<span className="text-primary">AI</span>
        </span>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
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
          <GenerateForm values={form} onChange={setForm} onSubmit={onSubmit} disabled={running || submitting} />
        </aside>
        <main className="min-w-0 flex-1">
          <ResultPanel job={job} />
        </main>
      </div>
    </div>
  )
}

export default function App() {
  const { state, submitKey, refresh } = useSession()

  let content
  switch (state.kind) {
    case 'ready':
      content = <Workspace health={state.health} />
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
