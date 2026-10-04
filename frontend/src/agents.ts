// Turns the audit trail into "what is each agent doing right now?" for one ticket run.
import type { AgentName, AuditEvent, EventPart } from './api'

export const MAX_LOOPS = 7

export interface AgentInfo {
  name: AgentName
  emoji: string
  role: string
  color: string
}

export const AGENTS: AgentInfo[] = [
  { name: 'Boss', emoji: '🐶', role: 'Reads the ticket, delegates, makes the call', color: '#00356b' },
  { name: 'Inventory', emoji: '📦', role: 'Stock, low stock, restock vendors', color: '#286dc0' },
  { name: 'Accounting', emoji: '💰', role: 'Cash, invoices, margins, purchase orders', color: '#c9a227' },
  { name: 'Facilities', emoji: '🔧', role: 'Rent, lease, shop upkeep', color: '#4a7ab5' },
  { name: 'Customer Service', emoji: '💌', role: 'Drafts customer messages', color: '#63aaff' },
]

export const agentInfo = (name: string) => AGENTS.find(a => a.name === name) ?? AGENTS[0]

export type AgentStatus = 'idle' | 'working' | 'waiting' | 'done' | 'error'

export interface AgentView {
  status: AgentStatus
  activity: string
  loops: number
  calls: number // how many times this agent was brought in
  tools: string[] // tools used, in order, no repeats
  summaries: string[] // what each run of this agent reported
  drafts: string[]
  error?: string
}

export interface FeedItem {
  index: number
  time: string
  agent: AgentName | 'Human' | 'System'
  text: string
  kind: 'info' | 'tool' | 'delegate' | 'draft' | 'done' | 'error'
}

export interface RunView {
  runId: string | null
  started: boolean
  finished: boolean
  failed: string | null
  chain: AgentName[]
  agents: Record<AgentName, AgentView>
  feed: FeedItem[]
}

const str = (v: unknown) => (v === undefined || v === null ? '' : String(v))
const short = (s: string, n = 90) => (s.length > n ? s.slice(0, n - 1) + '…' : s)

// Friendly words for each tool call.
export function describeTool(tool: string, args: Record<string, unknown> = {}): string {
  const a = (k: string) => str(args[k])
  switch (tool) {
    case 'get_ticket': return `Reading ticket #${a('ticket_id')}`
    case 'list_tickets': return 'Looking over all the tickets'
    case 'get_desk': return "Checking today's date at the desk"
    case 'check_inventory': return `Counting ${a('sku')} size ${a('size')} on the shelf`
    case 'list_inventory': return a('sku') ? `Checking every size of ${a('sku')}` : 'Walking the whole stockroom'
    case 'find_low_stock': return 'Scanning for low stock'
    case 'list_vendors': return 'Flipping through the vendor list'
    case 'get_product_pricing': return `Looking up what ${a('sku')} costs`
    case 'calculate_margin':
      return args.unit_price ? `Crunching margins at $${a('unit_price')} each` : `Crunching margins on ${a('sku')}`
    case 'get_cash_accounts': return 'Peeking at the bank balance'
    case 'list_invoices': return 'Digging through invoices'
    case 'get_invoice': return `Pulling invoice #${a('invoice_id')}`
    case 'list_payments': return 'Checking what has been paid'
    case 'get_lease_details': return `Reading lease #${a('lease_id')}`
    case 'list_leases': return 'Reviewing the leases'
    case 'quote_purchase_order': return `Pricing ${a('qty')} × ${a('sku')} ${a('size')}`
    case 'quote_payment': return `Looking up the ${a('kind')} payment`
    case 'prepare_purchase_order': return `Drafting a purchase order for ${a('qty')} × ${a('sku')} 📝`
    case 'prepare_payment_request': return `Drafting a ${a('kind')} payment for a human to approve 📝`
    case 'draft_customer_message': return 'Writing a note to the customer ✉️'
    case 'delegate': return `Asking ${a('to')}: “${short(a('task'), 70)}”`
    case 'final_result': return 'Writing up the report'
    default: return `Using ${tool}`
  }
}

function emptyAgent(): AgentView {
  return { status: 'idle', activity: 'Napping until needed 💤', loops: 0, calls: 0, tools: [], summaries: [], drafts: [] }
}

function summaryOf(output: Record<string, unknown> | undefined): string {
  if (!output) return ''
  if (typeof output.summary === 'string') return output.summary
  if (typeof output.decision === 'string') return output.decision
  return ''
}

/** The latest run for a ticket, unless the database was reset after it. */
export function latestRunId(events: AuditEvent[], ticketId: number): string | null {
  let runId: string | null = null
  for (const e of events) {
    if (e.event === 'ticket_run_start' && e.ticket_id === ticketId) runId = e.run_id
    if (e.event === 'database_reset') runId = null
  }
  return runId
}

export function buildRun(events: AuditEvent[], runId: string | null): RunView {
  const agents = Object.fromEntries(AGENTS.map(a => [a.name, emptyAgent()])) as Record<AgentName, AgentView>
  const view: RunView = { runId, started: false, finished: false, failed: null, chain: [], agents, feed: [] }
  if (!runId) return view

  const push = (e: AuditEvent, agent: FeedItem['agent'], text: string, kind: FeedItem['kind']) =>
    view.feed.push({ index: e.index, time: e.timestamp, agent, text, kind })

  for (const e of events) {
    if (e.run_id !== runId) continue
    const ag = e.agent ? agents[e.agent] : undefined

    switch (e.event) {
      case 'ticket_run_start':
        view.started = true
        push(e, 'Human', `${str(e.requested_by).replace('human:', '')} sent the team in 🚀`, 'info')
        break
      case 'agent_start':
        if (!ag || !e.agent) break
        ag.status = 'working'
        ag.calls += 1
        ag.activity = 'Getting the brief…'
        view.chain = e.chain ?? [e.agent]
        if (e.agent !== 'Boss') {
          const from = e.chain && e.chain.length > 1 ? e.chain[e.chain.length - 2] : 'Boss'
          if (agents[from]) {
            agents[from].status = 'waiting'
            agents[from].activity = `Waiting on ${e.agent}…`
          }
        }
        push(e, e.agent, e.agent === 'Boss' ? 'Clocked in and picked up the ticket' : 'Jumped in', 'info')
        break
      case 'loop_step':
        if (!ag || !e.agent) break
        if (e.node === 'model_request') {
          ag.loops = Math.max(ag.loops, e.loop ?? ag.loops + 1)
          if (ag.status !== 'waiting') ag.activity = 'Thinking… 🤔'
        } else if (e.node === 'model_response') {
          for (const p of (e.parts ?? []) as EventPart[]) {
            if (p.type === 'tool_call' && p.tool) {
              const text = describeTool(p.tool, p.args)
              ag.activity = text
              if (p.tool !== 'final_result' && !ag.tools.includes(p.tool)) ag.tools.push(p.tool)
              push(e, e.agent, text, p.tool === 'delegate' ? 'delegate' : 'tool')
            } else if (p.type === 'text' && typeof p.content === 'string' && p.content.trim()) {
              ag.activity = 'Writing…'
            }
          }
        }
        break
      case 'draft_saved': {
        if (!ag || !e.agent) break
        const d = e.draft ?? {}
        const label =
          e.draft_type === 'purchase_order' ? `Purchase order: ${str(d.order_qty)} × ${str(d.sku)} ${str(d.size)}`
          : e.draft_type === 'payment_request' ? `Payment: $${Number(d.amount).toLocaleString()} to ${str(d.payee)}`
          : `Message to ${str(d.to)}`
        ag.drafts.push(label)
        push(e, e.agent, `Saved a draft for human approval — ${label}`, 'draft')
        break
      }
      case 'agent_end': {
        if (!ag || !e.agent) break
        ag.status = 'done'
        const s = summaryOf(e.output)
        if (s) ag.summaries.push(s)
        ag.activity = 'Done ✔'
        view.chain = (e.chain ?? []).slice(0, -1)
        // whoever was waiting on this agent is back to work
        const parent = e.chain && e.chain.length > 1 ? e.chain[e.chain.length - 2] : null
        if (parent && agents[parent]?.status === 'waiting') {
          agents[parent].status = 'working'
          agents[parent].activity = `Reading ${e.agent}'s report`
        }
        push(e, e.agent, s ? `Finished: ${short(s, 140)}` : 'Finished', 'done')
        break
      }
      case 'agent_error':
      case 'agent_refused':
        if (!ag || !e.agent) break
        ag.status = 'error'
        ag.error = e.error
        ag.activity = 'Hit a snag ⚠️'
        push(e, e.agent, e.error ?? 'Error', 'error')
        break
      case 'ticket_run_end':
        view.finished = true
        view.chain = []
        push(e, 'System', 'The team wrapped up this ticket 🎉', 'done')
        break
      case 'ticket_run_error':
        view.finished = true
        view.failed = e.error ?? 'The run failed'
        view.chain = []
        push(e, 'System', view.failed, 'error')
        break
    }
  }
  return view
}
