import { useEffect, useMemo, useState } from 'react'
import { api, ApiError } from './api'
import type { Row, Run, Status } from './types'
import { Button, FieldError, SkeletonRow, StatusPill, Toast } from './ui'

const FILTERS: (Status | 'ALL')[] = ['ALL', 'ANSWERED', 'ESCALATE', 'BLOCKED']

export default function RunView({ runId }: { runId: string }) {
  const [run, setRun] = useState<Run | null>(null)
  const [rows, setRows] = useState<Row[]>([])
  const [live, setLive] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [filter, setFilter] = useState<Status | 'ALL'>('ALL')
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const [sending, setSending] = useState(false)
  const [toast, setToast] = useState<string | null>(null)

  // Load the snapshot first so a reload of a finished run renders instantly.
  useEffect(() => {
    let cancelled = false
    setRun(null)
    setRows([])
    setLoadError(null)
    setExpanded(new Set())
    api<Run>(`/api/runs/${runId}`)
      .then((r) => {
        if (cancelled) return
        setRun(r)
        setRows(r.rows)
        setLive(r.status === 'running')
      })
      .catch((err) =>
        setLoadError(err instanceof ApiError ? err.message : 'Could not load this run.'),
      )
    return () => {
      cancelled = true
    }
  }, [runId])

  // Then follow the stream. Rows are keyed, so replayed ones are not duplicated.
  useEffect(() => {
    if (!run || run.status !== 'running') return
    const source = new EventSource(`/api/runs/${runId}/stream`)
    source.onmessage = (event) => {
      const data = JSON.parse(event.data)
      if (data.type === 'row') {
        setRows((prev) =>
          prev.some((r) => r.key === data.row.key) ? prev : [...prev, data.row],
        )
      } else if (data.type === 'done') {
        setLive(false)
        setRun((prev) =>
          prev ? { ...prev, status: data.status, error: data.error } : prev,
        )
        source.close()
      }
    }
    source.onerror = () => {
      setLive(false)
      source.close()
    }
    return () => source.close()
  }, [runId, run?.status])

  const stats = useMemo(
    () => ({
      total: run?.questions.length ?? 0,
      answered: rows.filter((r) => r.status === 'ANSWERED').length,
      escalated: rows.filter((r) => r.status === 'ESCALATE').length,
      blocked: rows.filter((r) => r.status === 'BLOCKED').length,
    }),
    [rows, run],
  )

  const visible = filter === 'ALL' ? rows : rows.filter((r) => r.status === filter)
  const pending = Math.max(0, stats.total - rows.length)

  async function sendEmail() {
    setSending(true)
    try {
      const res = await api<{ already_sent: boolean }>(`/api/runs/${runId}/email`, {
        method: 'POST',
      })
      setToast(
        res.already_sent
          ? `Already sent to ${run?.email}.`
          : `Results sent to ${run?.email}.`,
      )
    } catch (err) {
      setToast(err instanceof ApiError ? `Send failed: ${err.message}` : 'Send failed.')
    }
    setSending(false)
  }

  if (loadError) {
    return (
      <div className="p-6 max-w-lg">
        <FieldError>{loadError}</FieldError>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full">
      <header className="h-14 shrink-0 border-b border-line bg-surface flex items-center justify-between px-6 gap-4">
        <div className="flex items-center gap-3 min-w-0">
          <h1 className="text-[13px] font-semibold text-ink">Run {runId}</h1>
          {live && (
            <span className="flex items-center gap-1.5 text-xs text-ink-muted">
              <span className="h-1.5 w-1.5 rounded-full bg-accent animate-pulse" />
              Running
            </span>
          )}
          {run?.status === 'error' && (
            <span className="text-xs text-bad">Failed — {run.error}</span>
          )}
        </div>
        <Button
          variant="secondary"
          disabled={sending || live || !run || rows.length === 0}
          onClick={sendEmail}
        >
          {sending ? 'Sending…' : 'Send email'}
        </Button>
      </header>

      <div className="px-6 pt-6">
        <div className="grid grid-cols-4 gap-3">
          <Tile label="Total" value={stats.total} />
          <Tile label="Answered" value={stats.answered} tone="ok" />
          <Tile label="Escalated" value={stats.escalated} tone="warn" />
          <Tile label="Blocked" value={stats.blocked} tone="bad" />
        </div>

        <div className="flex items-center gap-2 mt-6">
          {FILTERS.map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={
                'h-7 px-3 rounded-full border text-[12px] font-medium transition-colors ' +
                (filter === f
                  ? 'border-accent bg-accent-faint text-accent'
                  : 'border-line-strong bg-surface text-ink-muted hover:text-ink')
              }
            >
              {f === 'ALL' ? 'All' : f}
              {f !== 'ALL' && (
                <span className="ml-1.5 text-ink-faint">
                  {f === 'ANSWERED'
                    ? stats.answered
                    : f === 'ESCALATE'
                      ? stats.escalated
                      : stats.blocked}
                </span>
              )}
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 overflow-auto px-6 py-4">
        <div className="border border-line rounded-lg bg-surface overflow-hidden">
          <table className="w-full text-[13px] table-fixed">
            <thead className="sticky top-0 z-10 bg-canvas">
              <tr className="border-b border-line text-left text-ink-muted">
                <th className="font-medium px-4 py-2.5 w-[26%]">Question</th>
                <th className="font-medium px-4 py-2.5 w-[110px]">Status</th>
                <th className="font-medium px-4 py-2.5">Answer</th>
                <th className="font-medium px-4 py-2.5 w-[26%]">Source quote</th>
                <th className="font-medium px-4 py-2.5 w-[100px]">Confidence</th>
              </tr>
            </thead>
            <tbody>
              {visible.map((row) => {
                const open = expanded.has(row.key)
                return (
                  <tr key={row.key} className="border-b border-line last:border-0 align-top">
                    <td className="px-4 py-3 text-ink">{row.question}</td>
                    <td className="px-4 py-3">
                      <StatusPill status={row.status} />
                    </td>
                    <td className="px-4 py-3 text-ink-muted">
                      {row.answer || (
                        <span className="text-ink-faint italic">{row.reason || '—'}</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      {row.source_quote ? (
                        <button
                          onClick={() =>
                            setExpanded((prev) => {
                              const next = new Set(prev)
                              next.has(row.key) ? next.delete(row.key) : next.add(row.key)
                              return next
                            })
                          }
                          className="text-left w-full group"
                        >
                          <span
                            className={
                              'block text-ink-muted font-mono text-[12px] leading-relaxed ' +
                              (open ? '' : 'line-clamp-2')
                            }
                          >
                            “{row.source_quote}”
                          </span>
                          <span className="text-[11px] text-accent group-hover:underline">
                            {open ? 'Collapse' : 'Expand'}
                          </span>
                        </button>
                      ) : (
                        <span className="text-ink-faint">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-ink-muted tabular-nums">
                      {row.status === 'BLOCKED' ? '—' : row.confidence.toFixed(2)}
                    </td>
                  </tr>
                )
              })}

              {live &&
                filter === 'ALL' &&
                Array.from({ length: Math.min(pending, 4) }).map((_, i) => (
                  <SkeletonRow key={`skeleton-${i}`} />
                ))}

              {!live && visible.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-10 text-center text-ink-faint">
                    {rows.length === 0
                      ? 'No results in this run.'
                      : `No ${filter.toLowerCase()} rows.`}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {toast && <Toast message={toast} onDismiss={() => setToast(null)} />}
    </div>
  )
}

function Tile({
  label,
  value,
  tone,
}: {
  label: string
  value: number
  tone?: 'ok' | 'warn' | 'bad'
}) {
  const color =
    tone === 'ok'
      ? 'text-ok'
      : tone === 'warn'
        ? 'text-warn'
        : tone === 'bad'
          ? 'text-bad'
          : 'text-ink'
  return (
    <div className="border border-line rounded-lg bg-surface px-4 py-3">
      <div className="text-[11px] font-medium uppercase tracking-wider text-ink-faint">
        {label}
      </div>
      <div className={`mt-1 text-2xl font-semibold tabular-nums ${color}`}>{value}</div>
    </div>
  )
}
