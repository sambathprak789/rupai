import { CloudOff, Loader2, ServerCrash, ShieldAlert } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

type Variant = 'connecting' | 'backend-offline' | 'comfy-offline' | 'blocked'

const COPY: Record<Variant, { title: string; body: string; icon: typeof Loader2 }> = {
  connecting: { title: 'Connecting…', body: 'Checking the backend on Colab.', icon: Loader2 },
  'backend-offline': {
    title: 'Backend offline',
    body: 'The Colab session may have stopped or the tunnel URL changed. Run the notebook again and open the new URL. Retrying every few seconds…',
    icon: CloudOff,
  },
  'comfy-offline': {
    title: 'Model engine not ready',
    body: 'ComfyUI is starting or has crashed. Run the "Show logs" cell in the notebook if this does not clear. Retrying…',
    icon: ServerCrash,
  },
  blocked: {
    title: 'Too many wrong keys',
    body: 'This network is blocked for 15 minutes. Wait, then reload the page.',
    icon: ShieldAlert,
  },
}

export function StatusScreen({ variant, onRetry }: { variant: Variant; onRetry?: () => void }) {
  const { title, body, icon: Icon } = COPY[variant]
  return (
    <div className="flex min-h-svh items-center justify-center p-4">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Icon className={variant === 'connecting' ? 'size-5 animate-spin text-primary' : 'size-5 text-primary'} />
            {title}
          </CardTitle>
          <CardDescription>{body}</CardDescription>
        </CardHeader>
        {onRetry && variant !== 'connecting' && variant !== 'blocked' && (
          <CardContent>
            <Button variant="secondary" onClick={onRetry}>
              Retry now
            </Button>
          </CardContent>
        )}
      </Card>
    </div>
  )
}
