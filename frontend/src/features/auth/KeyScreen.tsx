import { useState, type FormEvent } from 'react'
import { KeyRound } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

export function KeyScreen({ error, onSubmit }: { error?: string; onSubmit: (key: string) => Promise<void> }) {
  const [key, setKey] = useState('')
  const [busy, setBusy] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!key.trim()) return
    setBusy(true)
    await onSubmit(key)
    setBusy(false)
  }

  return (
    <div className="flex min-h-svh items-center justify-center p-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <KeyRound className="size-5 text-primary" /> RupAI
          </CardTitle>
          <CardDescription>Enter the access key. The notebook prints it with the URL.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="grid gap-3">
            <Label htmlFor="key">Access key</Label>
            <Input
              id="key"
              type="password"
              autoComplete="current-password"
              autoFocus
              value={key}
              onChange={(e) => setKey(e.target.value)}
              aria-invalid={!!error}
            />
            {error && <p className="text-sm text-destructive">{error}</p>}
            <Button type="submit" disabled={busy || !key.trim()}>
              {busy ? 'Checking…' : 'Continue'}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
