export type Status = 'ANSWERED' | 'ESCALATE' | 'BLOCKED'

export type Row = {
  key: string
  question: string
  status: Status
  answer: string
  source_quote: string
  source_url: string
  confidence: number
  reason: string
}

export type Stats = { answered: number; escalated: number; blocked: number }

export type Run = {
  run_id: string
  created_at: string
  email: string
  source_urls: string[]
  questions: string[]
  status: 'running' | 'done' | 'error'
  rows: Row[]
  error: string
  email_sent_at: string
  stats: Stats
}
