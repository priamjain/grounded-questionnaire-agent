/** Shared primitives. Subtle 1px borders, no heavy shadows, 8px grid. */
import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode } from 'react'

export function Button({
  variant = 'primary',
  className = '',
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'primary' | 'secondary' | 'ghost'
}) {
  const base =
    'inline-flex items-center justify-center gap-2 h-9 px-4 text-[13px] font-medium ' +
    'rounded-md transition-colors disabled:opacity-40 disabled:cursor-not-allowed'
  const variants = {
    primary: 'bg-accent text-white hover:bg-accent-hover disabled:hover:bg-accent',
    secondary:
      'bg-surface text-ink border border-line-strong hover:bg-canvas disabled:hover:bg-surface',
    ghost: 'text-ink-muted hover:text-ink hover:bg-canvas',
  }
  return <button className={`${base} ${variants[variant]} ${className}`} {...props} />
}

export function Input({ className = '', ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={
        'h-9 w-full px-3 text-[13px] bg-surface text-ink rounded-md border border-line-strong ' +
        'placeholder:text-ink-faint focus:border-accent focus:outline-none ' +
        `focus:ring-2 focus:ring-accent/15 ${className}`
      }
      {...props}
    />
  )
}

export function Label({ children, hint }: { children: ReactNode; hint?: string }) {
  return (
    <div className="flex items-baseline justify-between mb-2">
      <label className="text-[13px] font-medium text-ink">{children}</label>
      {hint && <span className="text-xs text-ink-faint">{hint}</span>}
    </div>
  )
}

export function FieldError({ children }: { children: ReactNode }) {
  return (
    <div
      role="alert"
      className="flex items-start gap-2 px-3 py-2 text-[13px] rounded-md border border-bad/25 bg-bad-faint text-bad"
    >
      {children}
    </div>
  )
}

const PILL: Record<string, string> = {
  ANSWERED: 'border-ok/25 bg-ok-faint text-ok',
  ESCALATE: 'border-warn/25 bg-warn-faint text-warn',
  BLOCKED: 'border-bad/25 bg-bad-faint text-bad',
}

export function StatusPill({ status }: { status: string }) {
  return (
    <span
      className={
        'inline-flex items-center h-5 px-2 rounded border text-[11px] font-medium ' +
        `tracking-wide whitespace-nowrap ${PILL[status] ?? 'border-line bg-canvas text-ink-muted'}`
      }
    >
      {status}
    </span>
  )
}

export function Toast({ message, onDismiss }: { message: string; onDismiss: () => void }) {
  return (
    <div
      role="status"
      className="fixed bottom-6 right-6 z-50 flex items-center gap-3 pl-4 pr-2 py-3
                 bg-ink text-white text-[13px] rounded-md"
    >
      <span>{message}</span>
      <button
        onClick={onDismiss}
        className="h-6 px-2 rounded text-white/60 hover:text-white hover:bg-white/10"
      >
        Dismiss
      </button>
    </div>
  )
}

/** Shimmering placeholder row, used while the run is still in flight. */
export function SkeletonRow() {
  return (
    <tr className="border-b border-line">
      {[40, 20, 70, 60, 24].map((w, i) => (
        <td key={i} className="px-4 py-3 align-top">
          <div
            className="h-3 rounded bg-line relative overflow-hidden"
            style={{ width: `${w}%` }}
          >
            <div
              className="absolute inset-0 -translate-x-full bg-gradient-to-r
                         from-transparent via-white/70 to-transparent"
              style={{ animation: 'shimmer 1.4s infinite' }}
            />
          </div>
        </td>
      ))}
    </tr>
  )
}
