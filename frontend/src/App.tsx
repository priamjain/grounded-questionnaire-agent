import { useEffect, useState } from 'react'
import { api } from './api'
import Login from './Login'
import Shell from './Shell'

type Auth = { state: 'checking' } | { state: 'out' } | { state: 'in'; username: string }

export default function App() {
  const [auth, setAuth] = useState<Auth>({ state: 'checking' })

  // Session lives in an HttpOnly cookie, so ask the server who we are.
  useEffect(() => {
    api<{ username: string }>('/api/me')
      .then((me) => setAuth({ state: 'in', username: me.username }))
      .catch(() => setAuth({ state: 'out' }))
  }, [])

  if (auth.state === 'checking') {
    return (
      <div className="min-h-full grid place-items-center">
        <div className="h-4 w-32 rounded bg-line animate-pulse" />
      </div>
    )
  }

  if (auth.state === 'out') {
    return <Login onSuccess={(username) => setAuth({ state: 'in', username })} />
  }

  return (
    <Shell
      username={auth.username}
      runs={[]}
      activeRunId={null}
      onSelectRun={() => {}}
      onNewRun={() => {}}
      onLogout={() => setAuth({ state: 'out' })}
    >
      <div className="h-14 border-b border-line bg-surface flex items-center px-6">
        <h1 className="text-[13px] font-semibold text-ink">New run</h1>
      </div>
      <div className="p-6 text-[13px] text-ink-muted">
        Protected shell. The run form lands here next.
      </div>
    </Shell>
  )
}
