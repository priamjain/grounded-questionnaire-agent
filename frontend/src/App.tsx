import { useCallback, useEffect, useState } from 'react'
import { api } from './api'
import Login from './Login'
import NewRun from './NewRun'
import RunView from './RunView'
import Shell, { type RunSummary } from './Shell'

type Auth = { state: 'checking' } | { state: 'out' } | { state: 'in'; username: string }

export default function App() {
  const [auth, setAuth] = useState<Auth>({ state: 'checking' })
  const [runs, setRuns] = useState<RunSummary[]>([])
  const [activeRunId, setActiveRunId] = useState<string | null>(null)

  // Session lives in an HttpOnly cookie, so ask the server who we are.
  useEffect(() => {
    api<{ username: string }>('/api/me')
      .then((me) => setAuth({ state: 'in', username: me.username }))
      .catch(() => setAuth({ state: 'out' }))
  }, [])

  const refreshRuns = useCallback(() => {
    api<{ runs: RunSummary[] }>('/api/runs')
      .then((r) => setRuns(r.runs))
      .catch(() => {})
  }, [])

  useEffect(() => {
    if (auth.state === 'in') refreshRuns()
  }, [auth.state, refreshRuns])

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
      runs={runs}
      activeRunId={activeRunId}
      onSelectRun={setActiveRunId}
      onNewRun={() => setActiveRunId(null)}
      onLogout={() => {
        setAuth({ state: 'out' })
        setRuns([])
        setActiveRunId(null)
      }}
    >
      {activeRunId ? (
        <RunView key={activeRunId} runId={activeRunId} />
      ) : (
        <>
          <div className="h-14 border-b border-line bg-surface flex items-center px-6">
            <h1 className="text-[13px] font-semibold text-ink">New run</h1>
          </div>
          <NewRun
            onStarted={(runId) => {
              setActiveRunId(runId)
              refreshRuns()
            }}
          />
        </>
      )}
    </Shell>
  )
}
