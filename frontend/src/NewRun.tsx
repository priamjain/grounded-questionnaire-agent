import { useRef, useState } from 'react'
import Papa from 'papaparse'
import { api, ApiError } from './api'
import { Button, FieldError, Input, Label, Textarea } from './ui'

type Csv = { name: string; headers: string[]; rows: string[][] }

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

export default function NewRun({ onStarted }: { onStarted: (runId: string) => void }) {
  const [urls, setUrls] = useState<string[]>([''])
  const [bulk, setBulk] = useState('')
  const [csv, setCsv] = useState<Csv | null>(null)
  const [csvError, setCsvError] = useState<string | null>(null)
  const [column, setColumn] = useState(0)
  const [email, setEmail] = useState('')
  const [dragging, setDragging] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const fileInput = useRef<HTMLInputElement>(null)

  const cleanUrls = urls.map((u) => u.trim()).filter(Boolean)
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
    <div className="max-w-3xl px-6 py-8 space-y-8">
      {/* Policy sources */}
      <section>
        <Label hint="Paste multiple lines to add several at once">Policy sources</Label>
        <p className="-mt-1 mb-3 text-[13px] text-ink-muted">
          Public URLs of the documents answers must be grounded in.
        </p>
        <div className="space-y-2">
          {urls.map((url, i) => (
            <div key={i} className="flex gap-2">
              <Input
                value={url}
                onChange={(e) => setUrlAt(i, e.target.value)}
                placeholder="https://handbook.example.com/security/access-control"
                spellCheck={false}
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
          ))}
        </div>
        <Button
          variant="ghost"
          className="mt-2 px-2"
          onClick={() => setUrls((prev) => [...prev, ''])}
        >
          + Add source
        </Button>

        <div className="mt-5 pt-5 border-t border-line">
          <Label hint="Separated by commas, spaces or newlines">Or paste a list</Label>
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
            spellCheck={false}
            placeholder="https://example.com/a, https://example.com/b"
          />
          <div className="mt-2 flex items-center gap-3">
            <Button variant="secondary" disabled={!splitUrls(bulk).length} onClick={addBulk}>
              Add to sources
            </Button>
            {bulk.trim() && (
              <span className="text-xs text-ink-faint">
                {splitUrls(bulk).length} link{splitUrls(bulk).length === 1 ? '' : 's'} detected
              </span>
            )}
          </div>
        </div>
      </section>

      {/* Questions CSV */}
      <section>
        <Label hint="CSV with a header row, one question per row">Questions</Label>
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
            'mt-1 rounded-lg border border-dashed px-6 py-8 text-center transition-colors ' +
            (dragging ? 'border-accent bg-accent-faint' : 'border-line-strong bg-surface')
          }
        >
          <p className="text-[13px] text-ink">
            Drop a CSV here, or{' '}
            <button
              className="text-accent font-medium hover:underline"
              onClick={() => fileInput.current?.click()}
            >
              choose a file
            </button>
          </p>
          <p className="mt-1 text-xs text-ink-faint">
            {csv ? `${csv.name} — ${csv.rows.length} rows` : 'No file selected'}
          </p>
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
        </div>

        {csvError && <div className="mt-3">
          <FieldError>{csvError}</FieldError>
        </div>}

        {csv && (
          <div className="mt-4 border border-line rounded-lg overflow-hidden bg-surface">
            <div className="flex items-center justify-between gap-4 px-4 py-3 border-b border-line">
              <span className="text-[13px] font-medium text-ink">
                Preview — first {Math.min(5, csv.rows.length)} of {csv.rows.length}
              </span>
              <label className="flex items-center gap-2 text-[13px] text-ink-muted">
                Question column
                <select
                  value={column}
                  onChange={(e) => setColumn(Number(e.target.value))}
                  className="h-8 px-2 text-[13px] bg-surface border border-line-strong rounded-md"
                >
                  {csv.headers.map((h, i) => (
                    <option key={i} value={i}>
                      {h?.trim() || `Column ${i + 1}`}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-[13px]">
                <thead>
                  <tr className="border-b border-line">
                    {csv.headers.map((h, i) => (
                      <th
                        key={i}
                        className={
                          'text-left font-medium px-4 py-2 whitespace-nowrap ' +
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
                            'px-4 py-2 align-top max-w-[320px] truncate ' +
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
          </div>
        )}
      </section>

      {/* Recipient */}
      <section className="max-w-sm">
        <Label>Send results to</Label>
        <Input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="security@vendor.com"
        />
        {email.trim() !== '' && !emailValid && (
          <p className="mt-2 text-xs text-bad">Enter a valid email address.</p>
        )}
      </section>

      {error && <FieldError>{error}</FieldError>}

      <div className="flex items-center gap-4 pt-2 border-t border-line">
        <Button className="mt-6" disabled={!ready || submitting} onClick={submit}>
          {submitting ? 'Starting…' : 'Run'}
        </Button>
        <p className="mt-6 text-[13px] text-ink-muted">
          {ready
            ? `${questions.length} questions against ${cleanUrls.length} source${
                cleanUrls.length === 1 ? '' : 's'
              }`
            : 'Add sources, questions, and a recipient to run.'}
        </p>
      </div>
    </div>
  )
}
