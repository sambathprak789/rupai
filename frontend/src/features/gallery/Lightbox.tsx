import { ArrowRight } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog'

import { ImageActions, type ImageActionHandlers } from './ImageActions'
import type { ImageIndex } from './imageIndex'

interface Props extends ImageActionHandlers {
  imageId: string | null
  index: ImageIndex
  onSelect: (imageId: string | null) => void
}

export function Lightbox({ imageId, index, onSelect, onReuse, onRenderQuality, busy }: Props) {
  const image = imageId ? index.imageById.get(imageId) : undefined
  const job = image ? index.jobById.get(image.jobId) : undefined
  const source = job?.sourceImageId ? index.imageById.get(job.sourceImageId) : undefined
  const qualityVersion = image ? index.qualityOf.get(image.id) : undefined

  return (
    <Dialog open={!!image} onOpenChange={(open) => !open && onSelect(null)}>
      <DialogContent className="max-w-5xl pt-12 sm:pt-6">
        {image && job && (
          <>
            <img
              src={image.url}
              alt={`Generated image, seed ${image.seed}`}
              className="mx-auto max-h-[70svh] w-auto rounded-lg bg-muted object-contain"
              style={{ aspectRatio: `${image.width} / ${image.height}` }}
            />
            <div className="grid gap-2">
              <DialogTitle>{job.prompt}</DialogTitle>
              <DialogDescription asChild>
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant={image.mode === 'quality' ? 'default' : 'secondary'} className="capitalize">
                    {image.mode}
                  </Badge>
                  <span>
                    {image.width}×{image.height} · seed {image.seed} · {job.steps} steps · CFG {job.cfg.toFixed(1)}
                  </span>
                  {job.mode === 'quality' && job.negativePrompt.trim() && <span>· negative: {job.negativePrompt}</span>}
                </div>
              </DialogDescription>
              {(source || qualityVersion) && (
                <div className="flex flex-wrap gap-2">
                  {source && (
                    <Button size="sm" variant="link" className="h-auto p-0" onClick={() => onSelect(source.id)}>
                      Made from Fast image (seed {source.seed}) <ArrowRight />
                    </Button>
                  )}
                  {qualityVersion && (
                    <Button size="sm" variant="link" className="h-auto p-0" onClick={() => onSelect(qualityVersion.id)}>
                      See the Quality version <ArrowRight />
                    </Button>
                  )}
                </div>
              )}
            </div>
            <ImageActions
              image={image}
              busy={busy}
              onReuse={(img) => {
                onReuse(img)
                onSelect(null)
              }}
              onRenderQuality={(img) => {
                onRenderQuality(img)
                onSelect(null)
              }}
            />
          </>
        )}
      </DialogContent>
    </Dialog>
  )
}
