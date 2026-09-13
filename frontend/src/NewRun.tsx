import { useRef, useState } from 'react'
import type { ReactNode } from 'react'
import Papa from 'papaparse'
import { api, ApiError } from './api'
import { Button, FieldError, Input, Textarea } from './ui'

type Csv = { name: string; headers: string[]; rows: string[][] }

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

/** A numbered step with a rail down the left, marked complete once satisfied. */
function Step({
  n,
  title,
  hint,
  done,
  count,
  last = false,
  children,
}: {
  n: number
  title: string
  hint: string
  done: boolean
  count?: string
  last?: boolean
  children: ReactNode
}) {
  return (
    <section className="relative pl-11">
      <div
        className={
          'absolute left-0 top-0 flex h-7 w-7 items-center justify-center rounded-full ' +
          'border text-[12px] font-medium tabular-nums transition-colors ' +
          (done
            ? 'border-accent bg-accent text-white'
            : 'border-line-strong bg-surface text-ink-faint')
        }
      >
        {n}
      </div>
      {!last && (
        <div className="absolute left-[13.5px] top-8 bottom-[-28px] w-px bg-line" />
      )}
      <div className="flex items-baseline justify-between gap-4">
        <h2 className="text-[13px] font-medium text-ink">{title}</h2>
        {count && (
          <span className="shrink-0 text-xs tabular-nums text-ink-faint">{count}</span>
        )}
      </div>
      <p className="mt-0.5 mb-3 text-[13px] text-ink-muted">{hint}</p>
      {children}
    </section>
  )
}

/** Readiness indicator in the action bar. */
function Check({ done, children }: { done: boolean; children: ReactNode }) {
  return (
    <span className="flex items-center gap-1.5">
      <span
        className={'h-1.5 w-1.5 rounded-full ' + (done ? 'bg-accent' : 'bg-line-strong')}
      />
      <span className={done ? 'text-ink' : 'text-ink-faint'}>{children}</span>
    </span>
  )
}

function hostOf(url: string): string | null {
  try {
    const u = new URL(url.trim())
    if (u.protocol !== 'http:' && u.protocol !== 'https:') return null
    return u.hostname.replace(/^www\./, '')
  } catch {
    return null
  }
}

export default function NewRun({ onStarted }: { onStarted: (runId: string) => void }) {
  const [urls, setUrls] = useState<string[]>([''])
  const [bulk, setBulk] = useState('')
  const [bulkOpen, setBulkOpen] = useState(false)
  const [csv, setCsv] = useState<Csv | null>(null)
  const [csvError, setCsvError] = useState<string | null>(null)
  const [column, setColumn] = useState(0)
  const [email, setEmail] = useState('')
  const [dragging, setDragging] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const fileInput = useRef<HTMLInputElement>(null)

  const cleanUrls = urls.map((u) => u.trim()).filter(Boolean)
  const invalidCount = cleanUrls.filter((u) => !hostOf(u)).length
  const hosts = new Set(cleanUrls.map(hostOf).filter(Boolean) as string[])
  const questions = csv
    ? csv.rows.map((r) => (r[column] ?? '').trim()).filter(Boolean)
    : []
  const emailValid = EMAIL_RE.test(email.trim())
  const ready = cleanUrls.length > 0 && questions.length > 0 && emailValid

  function splitUrls(value: string): string[] {
    return value
      .split(/[\n,\s]+/)
      .map((p) => p.trim())
      .filter(Boolean)
  }

  /** Pasting several lines into one row splits into one row per line. */
  function setUrlAt(index: number, value: string) {
    const parts = value.split(/[\n,]+/).map((p) => p.trim())
    setUrls((prev) => {
      const next = [...prev]
      if (parts.length > 1) next.splice(index, 1, ...parts.filter(Boolean))
      else next[index] = value
      return next.length ? next : ['']
    })
  }

  function addBulk() {
    const parts = splitUrls(bulk)
    if (!parts.length) return
    setUrls((prev) => {
      const kept = prev.filter((u) => u.trim())
      const merged = [...kept, ...parts]
      return merged.filter((u, i) => merged.indexOf(u) === i)
    })
    setBulk('')
    setBulkOpen(false)
  }

  function parseFile(file: File) {
    setCsvError(null)
    if (!/\.csv$/i.test(file.name)) {
      setCsvError('That is not a .csv file.')
      return
    }
    Papa.parse<string[]>(file, {
      skipEmptyLines: true,
      complete: (result) => {
        const all = result.data.filter((r) => r.some((c) => (c ?? '').trim()))
        if (all.length < 2) {
          setCsvError('The file needs a header row and at least one question.')
          return
        }
        const [headers, ...rows] = all
        // Default to the column whose header looks like the question column.
        const guess = headers.findIndex((h) => /question|query|item|ask/i.test(h ?? ''))
        setColumn(guess >= 0 ? guess : 0)
        setCsv({ name: file.name, headers, rows })
      },
      error: () => setCsvError('Could not read that file.'),
    })
  }

  async function submit() {
    setSubmitting(true)
    setError(null)
    try {
      const { run_id } = await api<{ run_id: string }>('/api/runs', {
        method: 'POST',
        body: JSON.stringify({
          source_urls: cleanUrls,
          questions,
          email: email.trim(),
        }),
      })
      onStarted(run_id)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not start the run.')
      setSubmitting(false)
    }
  }

  return (
    <div className="max-w-3xl px-6 py-8">
      <div className="mb-8">
        <h1 className="text-[15px] font-medium text-ink">New run</h1>
        <p className="mt-1 text-[13px] text-ink-muted">
          Every answer is checked against a literal quote from your sources. Anything
          that cannot be grounded is escalated, not guessed.
        </p>
      </div>

      <div className="space-y-7 pb-24">
        <Step
          n={1}
          title="Policy sources"
          hint="URLs of the documents answers must be grounded in."
          done={cleanUrls.length > 0 && invalidCount === 0}
          count={
            cleanUrls.length
              ? `${cleanUrls.length} source${cleanUrls.length === 1 ? '' : 's'} · ${hosts.size} host${hosts.size === 1 ? '' : 's'}`
              : undefined
          }
        >
          <div className="space-y-2">
            {urls.map((url, i) => {
              const trimmed = url.trim()
              const host = hostOf(url)
              const bad = trimmed !== '' && !host
              return (
                <div key={i}>
                  <div className="flex gap-2">
                    <Input
                      value={url}
                      onChange={(e) => setUrlAt(i, e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' && i === urls.length - 1 && trimmed) {
                          setUrls((prev) => [...prev, ''])
                        }
                      }}
                      placeholder="https://handbook.example.com/security/access-control"
                      spellCheck={false}
                      className={bad ? 'border-bad focus:border-bad' : ''}
                    />
                    <Button
                      variant="secondary"
                      className="w-9 px-0 shrink-0"
                      aria-label="Remove source"
                      disabled={urls.length === 1 && !urls[0]}
                      onClick={() =>
                        setUrls((prev) => {
                          const next = prev.filter((_, j) => j !== i)
                          return next.length ? next : ['']
                        })
                      }
                    >
                      &minus;
                    </Button>
                  </div>
                  {bad && (
                    <p className="mt-1 text-xs text-bad">Not a valid http or https URL.</p>
                  )}
                  {host && (
                    <p className="mt-1 font-mono text-[11px] text-ink-faint">{host}</p>
                  )}
                </div>
              )
            })}
          </div>

          <div className="mt-2 flex items-center gap-1">
            <Button
              variant="ghost"
              className="px-2"
              onClick={() => setUrls((prev) => [...prev, ''])}
            >
              + Add source
            </Button>
            <Button variant="ghost" className="px-2" onClick={() => setBulkOpen((v) => !v)}>
              {bulkOpen ? 'Hide list paste' : 'Paste a list'}
            </Button>
          </div>

          {bulkOpen && (
            <div className="mt-3 rounded-lg border border-line bg-canvas p-3">
              <Textarea
                value={bulk}
                onChange={(e) => setBulk(e.target.value)}
                onPaste={(e) => {
                  // A paste into an empty box is almost always the whole list.
                  const text = e.clipboardData.getData('text')
                  if (bulk.trim() || splitUrls(text).length < 2) return
                  e.preventDefault()
                  setBulk(text)
                }}
                rows={3}
                autoFocus
                spellCheck={false}
                placeholder="Separated by commas, spaces or newlines"
              />
              <div className="mt-2 flex items-center gap-3">
                <Button
                  variant="secondary"
                  disabled={!splitUrls(bulk).length}
                  onClick={addBulk}
                >
                  Add to sources
                </Button>
                {bulk.trim() && (
                  <span className="text-xs tabular-nums text-ink-faint">
                    {splitUrls(bulk).length} link{splitUrls(bulk).length === 1 ? '' : 's'}{' '}
                    detected
                  </span>
                )}
              </div>
            </div>
          )}
        </Step>

        <Step
          n={2}
          title="Questions"
          hint="A CSV with a header row and one question per row."
          done={questions.length > 0}
          count={csv ? `${questions.length} questions` : undefined}
        >
          {!csv ? (
            <div
              onDragOver={(e) => {
                e.preventDefault()
                setDragging(true)
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={(e) => {
                e.preventDefault()
                setDragging(false)
                const file = e.dataTransfer.files[0]
                if (file) parseFile(file)
              }}
              className={
                'rounded-lg border border-dashed px-6 py-8 text-center transition-colors ' +
                (dragging ? 'border-accent bg-accent-faint' : 'border-line-strong bg-surface')
              }
            >
              <p className="text-[13px] text-ink">
                Drop a CSV here, or{' '}
                <button
                  className="font-medium text-accent hover:underline"
                  onClick={() => fileInput.current?.click()}
                >
                  choose a file
                </button>
              </p>
              <p className="mt-1 text-xs text-ink-faint">No file selected</p>
            </div>
          ) : (
            <div className="overflow-hidden rounded-lg border border-line bg-surface">
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-4 py-3">
                <div className="min-w-0">
                  <div className="truncate font-mono text-[12px] text-ink">{csv.name}</div>
                  <div className="mt-0.5 text-xs tabular-nums text-ink-faint">
                    {csv.rows.length} rows &middot; {csv.headers.length} columns &middot;{' '}
                    {questions.length} usable
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <label className="flex items-center gap-2 text-[13px] text-ink-muted">
                    Question column
                    <select
                      value={column}
                      onChange={(e) => setColumn(Number(e.target.value))}
                      className="h-8 rounded-md border border-line-strong bg-surface px-2 text-[13px]"
                    >
                      {csv.headers.map((h, i) => (
                        <option key={i} value={i}>
                          {h?.trim() || `Column ${i + 1}`}
                        </option>
                      ))}
                    </select>
                  </label>
                  <Button variant="secondary" onClick={() => fileInput.current?.click()}>
                    Replace
                  </Button>
                </div>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-[13px]">
                  <thead>
                    <tr className="border-b border-line">
                      {csv.headers.map((h, i) => (
                        <th
                          key={i}
                          className={
                            'whitespace-nowrap px-4 py-2 text-left font-medium ' +
                            (i === column ? 'text-accent' : 'text-ink-muted')
                          }
                        >
                          {h?.trim() || `Column ${i + 1}`}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {csv.rows.slice(0, 5).map((row, r) => (
                      <tr key={r} className="border-b border-line last:border-0">
                        {csv.headers.map((_, c) => (
                          <td
                            key={c}
                            className={
                              'max-w-[320px] truncate px-4 py-2 align-top ' +
                              (c === column ? 'text-ink' : 'text-ink-faint')
                            }
                          >
                            {row[c]}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {csv.rows.length > 5 && (
                <div className="border-t border-line px-4 py-2 text-xs tabular-nums text-ink-faint">
                  Showing 5 of {csv.rows.length} rows
                </div>
              )}
            </div>
          )}

          <input
            ref={fileInput}
            type="file"
            accept=".csv,text/csv"
            hidden
            onChange={(e) => {
              const file = e.target.files?.[0]
              if (file) parseFile(file)
              e.target.value = ''
            }}
          />

          {csvError && (
            <div className="mt-3">
              <FieldError>{csvError}</FieldError>
            </div>
          )}
        </Step>

        <Step
          n={3}
          title="Send results to"
          hint="The finished table is emailed here. You can also resend it later."
          done={emailValid}
          last
        >
          <div className="max-w-sm">
            <Input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="security@vendor.com"
              className={
                email.trim() !== '' && !emailValid ? 'border-bad focus:border-bad' : ''
              }
            />
            {email.trim() !== '' && !emailValid && (
              <p className="mt-1 text-xs text-bad">Enter a valid email address.</p>
            )}
          </div>
        </Step>

        {error && <FieldError>{error}</FieldError>}
      </div>

      <div className="sticky bottom-0 -mx-6 border-t border-line bg-surface px-6 py-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-4 text-[13px]">
            <Check done={cleanUrls.length > 0 && invalidCount === 0}>
              {cleanUrls.length
                ? `${cleanUrls.length} source${cleanUrls.length === 1 ? '' : 's'}`
                : 'Sources'}
            </Check>
            <Check done={questions.length > 0}>
              {questions.length ? `${questions.length} questions` : 'Questions'}
            </Check>
            <Check done={emailValid}>{emailValid ? email.trim() : 'Recipient'}</Check>
            {invalidCount > 0 && (
              <span className="text-[13px] text-bad">
                {invalidCount} invalid URL{invalidCount === 1 ? '' : 's'}
              </span>
            )}
          </div>
          <Button disabled={!ready || submitting} onClick={submit}>
            {submitting ? 'Starting…' : 'Run questionnaire'}
          </Button>
        </div>
      </div>
    </div>
  )
}
