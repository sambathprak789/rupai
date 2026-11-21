import { Sparkles } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import type { GeneratedImage } from '@/lib/types'

import type { ImageIndex } from './imageIndex'

interface Props {
  index: ImageIndex
  /** Images of the job shown above (not repeated here) */
  hideJobId: string | null
  onOpen: (imageId: string) => void
}

function Thumb({ image, hasQuality, onOpen }: { image: GeneratedImage; hasQuality: boolean; onOpen: () => void }) {
  return (
    <button
      type="button"
      onClick={onOpen}
      className="group relative cursor-pointer overflow-hidden rounded-lg border bg-muted text-left outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
      style={{ aspectRatio: `${image.width} / ${image.height}` }}
      aria-label={`Open ${image.mode} image, seed ${image.seed}`}
    >
      <img
        src={image.url}
        alt=""
        loading="lazy"
        className="size-full object-cover transition-transform group-hover:scale-[1.02]"
      />
      <div className="absolute inset-x-0 bottom-0 flex items-center gap-1 bg-gradient-to-t from-black/70 to-transparent p-2">
        <Badge variant={image.mode === 'quality' ? 'default' : 'secondary'} className="capitalize">
          {image.mode}
        </Badge>
        {hasQuality && (
          <Badge variant="outline" className="border-primary/60 bg-black/40" title="Has a Quality version">
            <Sparkles /> HQ
          </Badge>
        )}
      </div>
    </button>
  )
}

export function Gallery({ index, hideJobId, onOpen }: Props) {
  const images = index.all.filter((img) => img.jobId !== hideJobId)
  if (images.length === 0) return null
  return (
    <section className="grid gap-3" aria-label="Session history">
      <h2 className="text-sm font-medium text-muted-foreground">
        Earlier in this session ({images.length}) · images disappear when the Colab session ends
      </h2>
      <div className="grid grid-cols-2 items-start gap-3 sm:grid-cols-3 xl:grid-cols-4">
        {images.map((img) => (
          <Thumb key={img.id} image={img} hasQuality={index.qualityOf.has(img.id)} onOpen={() => onOpen(img.id)} />
        ))}
      </div>
    </section>
  )
}
