import { useState } from 'react'
import { api, ApiError } from './api'
import { Button, FieldError, Input, Label } from './ui'

export default function Login({ onSuccess }: { onSuccess: (username: string) => void }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const me = await api<{ username: string }>('/api/login', {
        method: 'POST',
        body: JSON.stringify({ username, password }),
      })
      onSuccess(me.username)
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : 'Could not reach the server. Is it running?',
      )
      setBusy(false)
    }
  }

  return (
    <div className="min-h-full grid place-items-center px-6 py-16">
      <div className="w-full max-w-[360px]">
        <div className="mb-8">
          <div className="text-[15px] font-semibold tracking-tight text-ink">Grounded</div>
          <div className="mt-1 text-[13px] text-ink-muted">
            Security questionnaire agent
          </div>
        </div>

        <form
          onSubmit={submit}
          className="bg-surface border border-line rounded-lg p-6 space-y-5"
        >
          <div>
            <Label>Username</Label>
            <Input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              autoFocus
              required
            />
          </div>
          <div>
            <Label>Password</Label>
            <Input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              required
            />
          </div>

          {error && <FieldError>{error}</FieldError>}

          <Button type="submit" className="w-full" disabled={busy || !username || !password}>
            {busy ? 'Signing in…' : 'Sign in'}
          </Button>
        </form>

        <p className="mt-4 text-xs text-ink-faint text-center">
          Answers are grounded in your policy documents. Nothing is guessed.
        </p>
      </div>
    </div>
  )
}
