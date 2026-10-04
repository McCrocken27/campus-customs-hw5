// Talks to the Q7 FastAPI backend.
export const API_BASE = 'http://localhost:8000'

export type AgentName = 'Boss' | 'Inventory' | 'Accounting' | 'Facilities' | 'Customer Service'

export type ResolveStatus =
  | 'not_run'
  | 'running'
  | 'failed'
  | 'awaiting_approval'
  | 'resolved'

export interface Ticket {
  id: number
  type: string
  requester: string
  subject: string
  sku: string | null
  size: string | null
  qty: number | null
  lease_id: number | null
  invoice_id: number | null
  status: string
  notes: string | null
  created_at: string
  resolve_status: ResolveStatus
  run_id: string | null
  run_error: string | null
  recommended_status: string | null
  decision: string | null
  pending_approvals: number
  approved_drafts: number
  customer_messages: number
}

export interface PurchaseOrderDraft {
  ticket_id: number
  prepared_by: AgentName
  sku: string
  name: string
  size: string
  order_qty: number
  vendor_id: number
  vendor_name: string
  lead_days: number
  expected_arrival: string
  unit_cost: number
  estimated_total: number
  cash_after_order: number
  cash_after_order_and_open_invoices: number
  reason: string
  status: 'pending_human_approval' | 'approved'
  approved_by: string | null
  payment_id: number | null
}

export interface PaymentRequestDraft {
  ticket_id: number
  prepared_by: AgentName
  kind: 'rent' | 'invoice'
  ref_id: number
  payee: string
  description: string | null
  amount: number
  due_date: string
  days_until_due: number
  overdue: boolean
  cash_after_payment: number
  reason: string
  status: 'pending_human_approval' | 'approved'
  approved_by: string | null
  payment_id: number | null
}

export interface CustomerMessageDraft {
  ticket_id: number
  prepared_by: AgentName
  to: string
  subject: string
  body: string
  status: string
}

export interface BossDecision {
  ticket_id: number
  decision: string
  reasoning: string
  recommended_status: string
  next_steps: string[]
  missing_data: string[]
}

export interface TicketResolution {
  ticket: Record<string, unknown>
  decision: BossDecision
  purchase_orders: PurchaseOrderDraft[]
  payment_requests: PaymentRequestDraft[]
  customer_messages: CustomerMessageDraft[]
  delegations: { from_agent: AgentName; to_agent: AgentName; task: string; depth: number; error: string | null }[]
  model_requests: number
  tool_calls: number
}

export interface TicketDetail extends Ticket {
  result: TicketResolution | null
}

export interface EventPart {
  type: 'user_prompt' | 'tool_result' | 'retry' | 'tool_call' | 'text'
  tool?: string
  args?: Record<string, unknown>
  content?: unknown
}

export interface AuditEvent {
  index: number
  timestamp: string
  event: string
  run_id: string | null
  ticket_id: number | null
  agent?: AgentName
  chain?: AgentName[]
  step?: number
  node?: string
  loop?: number
  parts?: EventPart[]
  prompt?: string
  output?: Record<string, unknown>
  error?: string
  draft_type?: string
  draft?: Record<string, unknown>
  requested_by?: string
  approved_by?: string
}

export interface Cash {
  account: string
  balance: number
  as_of: string
}

export interface Scoreboard {
  results: {
    date: string
    sport: string
    opponent: string
    home: boolean
    outcome: 'W' | 'L' | 'T'
    yale_score: number
    opponent_score: number
  }[]
  upcoming: { date: string; time: string | null; sport: string; opponent: string; home: boolean }[]
  updated_at: string | null
  source: string
  available: boolean
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(API_BASE + path, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
  })
  const body = await res.json().catch(() => ({}))
  if (!res.ok) {
    const detail = (body as { detail?: unknown }).detail
    throw new Error(typeof detail === 'string' ? detail : `Request failed (${res.status})`)
  }
  return body as T
}

export const api = {
  tickets: () => call<{ tickets: Ticket[] }>('/api/tickets').then(r => r.tickets),
  ticket: (id: number) => call<TicketDetail>(`/api/tickets/${id}`),
  run: (id: number, requestedBy: string) =>
    call<{ run_id: string }>(`/api/tickets/${id}/run`, {
      method: 'POST',
      body: JSON.stringify({ requested_by: requestedBy }),
    }),
  events: (after: number) =>
    call<{ events: AuditEvent[]; last_index: number }>(`/api/events?after=${after}`),
  approve: (id: number, kind: 'payment' | 'purchase_order', index: number, approvedBy: string) =>
    call<Record<string, unknown>>(`/api/tickets/${id}/approve`, {
      method: 'POST',
      body: JSON.stringify({ kind, index, approved_by: approvedBy }),
    }),
  cash: () => call<Cash>('/api/cash'),
  scores: () => call<Scoreboard>('/api/scores'),
  reset: (requestedBy: string) =>
    call<{ reset: boolean }>('/api/reset', {
      method: 'POST',
      body: JSON.stringify({ requested_by: requestedBy, confirm: true }),
    }),
}

export const money = (n: number) =>
  n.toLocaleString('en-US', { style: 'currency', currency: 'USD' })
