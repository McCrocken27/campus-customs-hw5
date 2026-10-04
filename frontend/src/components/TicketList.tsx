import type { Ticket } from '../api'
import StatusBadge from './StatusBadge'

interface Props {
  tickets: Ticket[]
  selectedId: number | null
  onSelect: (id: number) => void
  onRun: (id: number) => void
  anyRunning: boolean
}

const ICON: Record<string, string> = {
  customer_order: '👕',
  rent_notice: '🏠',
  price_override: '🏷️',
}

export default function TicketList({ tickets, selectedId, onSelect, onRun, anyRunning }: Props) {
  return (
    <aside className="tickets">
      <h2 className="section-title">Ticket desk <span>{tickets.length}</span></h2>
      {tickets.map(t => (
        <div
          key={t.id}
          role="button"
          tabIndex={0}
          className={`ticket-card ${t.id === selectedId ? 'selected' : ''} ${t.resolve_status}`}
          onClick={() => onSelect(t.id)}
          onKeyDown={e => (e.key === 'Enter' || e.key === ' ') && onSelect(t.id)}
        >
          <div className="ticket-top">
            <span className="ticket-icon" aria-hidden>{ICON[t.type] ?? '🎫'}</span>
            <span className="ticket-id">#{t.id}</span>
            <StatusBadge status={t.resolve_status} />
          </div>
          <div className="ticket-subject">{t.subject}</div>
          <div className="ticket-meta">from {t.requester}</div>
          {t.notes && <div className="ticket-notes">“{t.notes}”</div>}
          {t.resolve_status === 'not_run' && (
            <button
              className="run small"
              disabled={anyRunning}
              onClick={e => { e.stopPropagation(); onRun(t.id) }}
            >
              🚀 Send in the team
            </button>
          )}
          {t.pending_approvals > 0 && (
            <div className="needs-you">✋ {t.pending_approvals} waiting on your approval</div>
          )}
        </div>
      ))}
    </aside>
  )
}
