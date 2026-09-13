/** Persistent left sidebar: past runs, and logout pinned to the bottom. */
import type { ReactNode } from 'react'
import { api } from './api'
import { Button } from './ui'

export type RunSummary = { run_id: string; created_at: string; total: number }

export default function Shell({
  username,
  runs,
  activeRunId,
  onSelectRun,
  onNewRun,
  onLogout,
  children,
}: {
  username: string
  runs: RunSummary[]
  activeRunId: string | null
  onSelectRun: (id: string) => void
  onNewRun: () => void
  onLogout: () => void
  children: ReactNode
}) {
  async function logout() {
    await api('/api/logout', { method: 'POST' }).catch(() => {})
    onLogout()
  }

  return (
    <div className="min-h-full flex">
      <aside className="w-60 shrink-0 border-r border-line bg-surface flex flex-col">
        <div className="h-14 px-4 flex items-center border-b border-line">
          <span className="text-[13px] font-semibold tracking-tight text-ink">Grounded</span>
        </div>

        <div className="p-3">
          <Button variant="secondary" className="w-full" onClick={onNewRun}>
            New run
          </Button>
        </div>

        <div className="px-3 pb-2">
          <div className="px-2 text-[11px] font-medium uppercase tracking-wider text-ink-faint">
            History
          </div>
        </div>

        <nav className="flex-1 overflow-y-auto px-2 pb-2 space-y-0.5">
          {runs.length === 0 && (
            <p className="px-2 py-2 text-[13px] text-ink-faint leading-relaxed">
              No runs yet. Start one to see it here.
            </p>
          )}
          {runs.map((r) => (
            <button
              key={r.run_id}
              onClick={() => onSelectRun(r.run_id)}
              className={
                'w-full text-left px-2 py-2 rounded-md transition-colors ' +
                (r.run_id === activeRunId
                  ? 'bg-accent-faint text-accent'
                  : 'text-ink-muted hover:bg-canvas hover:text-ink')
              }
            >
              <div className="text-[13px] font-medium truncate">{formatDate(r.created_at)}</div>
              <div className="text-xs text-ink-faint">{r.total} questions</div>
            </button>
          ))}
        </nav>

        <div className="border-t border-line p-3 flex items-center justify-between gap-2">
          <span className="text-xs text-ink-muted truncate" title={username}>
            {username}
          </span>
          <Button variant="ghost" className="h-8 px-2" onClick={logout}>
            Log out
          </Button>
        </div>
      </aside>

      <main className="flex-1 min-w-0">{children}</main>
    </div>
  )
}

export function formatDate(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}
