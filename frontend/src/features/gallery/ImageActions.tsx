import { Download, RotateCcw, Sparkles } from 'lucide-react'

import { Button } from '@/components/ui/button'
import type { GeneratedImage } from '@/lib/types'

export interface ImageActionHandlers {
  onReuse: (image: GeneratedImage) => void
  onRenderQuality: (image: GeneratedImage) => void
  /** A job is running: Render in Quality would get a 409 */
  busy: boolean
}

export function ImageActions({
  image,
  onReuse,
  onRenderQuality,
  busy,
  compact = false,
}: ImageActionHandlers & { image: GeneratedImage; compact?: boolean }) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <Button size="sm" variant="ghost" onClick={() => onReuse(image)} title="Put this image's settings in the form">
        <RotateCcw /> {!compact && 'Reuse'}
      </Button>
      {image.mode === 'fast' && (
        <Button
          size="sm"
          variant="ghost"
          onClick={() => onRenderQuality(image)}
          disabled={busy}
          title={busy ? 'Wait for the running job to finish' : 'Same prompt, seed and size in Quality mode'}
        >
          <Sparkles /> {compact ? 'Quality' : 'Render in Quality'}
        </Button>
      )}
      <Button asChild size="sm" variant="secondary">
        <a href={image.url} download={image.filename}>
          <Download /> {!compact && 'Download'}
        </a>
      </Button>
    </div>
  )
}
