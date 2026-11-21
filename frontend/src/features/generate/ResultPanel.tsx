import { useEffect, useState } from 'react'
import { Download, ImageIcon, Loader2 } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import type { GeneratedImage, Job } from '@/lib/types'
import { isFinished } from '@/lib/types'
import { formatDuration } from '@/lib/utils'

function useElapsed(since: string | null, active: boolean) {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    if (!active) return
    const id = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(id)
  }, [active])
  return since ? (now - new Date(since).getTime()) / 1000 : 0
}

function ImageCard({ image }: { image: GeneratedImage }) {
  return (
    <figure className="overflow-hidden rounded-xl border bg-card">
      <img
        src={image.url}
        alt={`Generated image, seed ${image.seed}`}
        width={image.width}
        height={image.height}
        className="h-auto w-full bg-muted"
        style={{ aspectRatio: `${image.width} / ${image.height}` }}
      />
      <figcaption className="flex items-center justify-between gap-2 p-3">
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Badge variant={image.mode === 'quality' ? 'default' : 'secondary'} className="capitalize">
            {image.mode}
          </Badge>
          seed {image.seed}
        </div>
        <Button asChild size="sm" variant="secondary">
          <a href={image.url} download={image.filename}>
            <Download /> Download
          </a>
        </Button>
      </figcaption>
    </figure>
  )
}

export function ResultPanel({ job }: { job: Job | null }) {
  const running = !!job && !isFinished(job.status)
  const elapsed = useElapsed(job?.createdAt ?? null, running)

  if (!job) {
    return (
      <div className="flex min-h-80 flex-col items-center justify-center gap-3 rounded-xl border border-dashed text-muted-foreground">
        <ImageIcon className="size-10" />
        <p className="text-sm">Your images will appear here.</p>
      </div>
    )
  }

  const { progress } = job
  return (
    <section className="grid gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="line-clamp-2 max-w-prose text-sm text-muted-foreground">{job.prompt}</p>
        {running && (
          <span className="flex items-center gap-2 text-sm" role="status">
            <Loader2 className="size-4 animate-spin text-primary" />
            {job.status === 'queued' || progress.step === 0
              ? 'Starting…'
              : `Image ${progress.imageIndex + 1}/${job.count} · step ${progress.step}/${progress.totalSteps}`}
            <span className="text-muted-foreground tabular-nums">{formatDuration(elapsed)}</span>
          </span>
        )}
        {job.status === 'failed' && <span className="text-sm text-destructive">{job.error}</span>}
        {job.status === 'cancelled' && <span className="text-sm text-muted-foreground">Cancelled</span>}
      </div>

      <div className={job.count > 1 ? 'grid gap-4 sm:grid-cols-2' : 'grid max-w-4xl gap-4'}>
        {job.images.map((img) => (
          <ImageCard key={img.id} image={img} />
        ))}
        {running &&
          Array.from({ length: job.count - job.images.length }, (_, i) => (
            <div
              key={`pending-${i}`}
              className="animate-pulse rounded-xl border bg-card"
              style={{ aspectRatio: `${job.width} / ${job.height}` }}
            />
          ))}
      </div>
    </section>
  )
}
