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
