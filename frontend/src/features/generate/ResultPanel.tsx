import { Download, ImageIcon, Loader2 } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import type { GeneratedImage, Job, Preview } from '@/lib/types'
import { isFinished } from '@/lib/types'
import { formatDuration } from '@/lib/utils'

import { remaining, useNow } from './useCountdown'

// Size a card so the whole image plus its caption fits on screen (header, paddings and caption ≈ 12rem)
function fitWidth(width: number, height: number) {
  return { width: `min(100%, calc((100svh - 12rem) * ${width / height}))` }
}

function timeLeft(seconds: number | null) {
  if (seconds == null) return null
  return seconds < 1 ? 'almost done…' : `≈ ${formatDuration(seconds)} left`
}

function ImageCard({ image }: { image: GeneratedImage }) {
  return (
    <figure
      className="flex flex-col overflow-hidden rounded-xl border bg-card"
      style={fitWidth(image.width, image.height)}
    >
      <img
        src={image.url}
        alt={`Generated image, seed ${image.seed}`}
        width={image.width}
        height={image.height}
        className="h-auto w-full bg-muted"
        style={{ aspectRatio: `${image.width} / ${image.height}` }}
      />
      <figcaption className="flex items-center justify-between gap-2 border-t p-3">
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

/** The image being rendered: live preview, step, progress bar and countdown. */
function ActiveCard({ job, preview, now }: { job: Job; preview: Preview | null; now: number }) {
  const { progress } = job
  const started = progress.step > 0
  const left = remaining(progress.imageEtaS, progress.updatedAt, now)
  const pct = progress.totalSteps ? (progress.step / progress.totalSteps) * 100 : 0
  const showPreview = preview && preview.imageIndex === progress.imageIndex

  return (
    <figure
      className="flex flex-col overflow-hidden rounded-xl border bg-card"
      style={fitWidth(job.width, job.height)}
      aria-busy="true"
    >
      <div className="relative w-full overflow-hidden bg-muted" style={{ aspectRatio: `${job.width} / ${job.height}` }}>
        {showPreview ? (
          <img
            src={preview.dataUrl}
            alt={`Preview at step ${preview.step}`}
            className="absolute inset-0 size-full object-cover"
            data-testid="live-preview"
          />
        ) : (
          <div className="absolute inset-0 flex animate-pulse items-center justify-center text-sm text-muted-foreground">
            {started ? 'Waiting for preview…' : 'Starting… (loading the model can take a minute)'}
          </div>
        )}
      </div>
      <figcaption className="grid gap-2 border-t p-3" role="status">
        <div className="flex items-center justify-between gap-2 text-sm">
          <span className="flex items-center gap-2">
            <Loader2 className="size-4 animate-spin text-primary" />
            Image {progress.imageIndex + 1}/{job.count}
            {started && (
              <span className="text-muted-foreground">
                · step {progress.step}/{progress.totalSteps}
              </span>
            )}
          </span>
          <span className="text-muted-foreground tabular-nums" data-testid="image-countdown">
            {timeLeft(left)}
          </span>
        </div>
        <Progress value={pct} aria-label="Image progress" />
      </figcaption>
    </figure>
  )
}

export function ResultPanel({ job, preview }: { job: Job | null; preview: Preview | null }) {
  const running = !!job && !isFinished(job.status)
  const now = useNow(running)

  if (!job) {
    return (
      <div className="flex min-h-80 flex-col items-center justify-center gap-3 rounded-xl border border-dashed text-muted-foreground">
        <ImageIcon className="size-10" />
        <p className="text-sm">Your images will appear here.</p>
      </div>
    )
  }

  const jobLeft = running ? remaining(job.progress.jobEtaS, job.progress.updatedAt, now) : null
  const waiting = running ? job.count - job.images.length - 1 : 0

  return (
    <section className="grid gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="line-clamp-2 max-w-prose text-sm text-muted-foreground">{job.prompt}</p>
        {running && jobLeft != null && (
          <span className="text-sm tabular-nums" data-testid="job-countdown">
            Job {timeLeft(jobLeft)}
          </span>
        )}
        {job.status === 'failed' && <span className="text-sm text-destructive">{job.error}</span>}
        {job.status === 'cancelled' && <span className="text-sm text-muted-foreground">Cancelled</span>}
      </div>

      <div className={job.count > 1 ? 'grid items-start gap-4 sm:grid-cols-2' : 'flex flex-col items-start gap-4'}>
        {job.images.map((img) => (
          <ImageCard key={img.id} image={img} />
        ))}
        {running && <ActiveCard job={job} preview={preview} now={now} />}
        {Array.from({ length: Math.max(0, waiting) }, (_, i) => (
          <div
            key={`waiting-${i}`}
            className="flex items-center justify-center rounded-xl border border-dashed bg-card/50 text-sm text-muted-foreground"
            style={{ ...fitWidth(job.width, job.height), aspectRatio: `${job.width} / ${job.height}` }}
          >
            Waiting
          </div>
        ))}
      </div>
    </section>
  )
}
