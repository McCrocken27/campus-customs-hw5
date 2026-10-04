import { useState } from 'react'
import { money } from '../api'
import type { Cash, TicketDetail } from '../api'

interface Props {
  detail: TicketDetail | null
  cash: Cash | null
  onApprove: (kind: 'payment' | 'purchase_order', index: number) => Promise<void>
}

export default function Approvals({ detail, cash, onApprove }: Props) {
  const [busy, setBusy] = useState<string | null>(null)
  const res = detail?.result
  const payments = res?.payment_requests ?? []
  const orders = res?.purchase_orders ?? []
  const messages = res?.customer_messages ?? []

  const click = async (kind: 'payment' | 'purchase_order', i: number) => {
    setBusy(`${kind}-${i}`)
    try { await onApprove(kind, i) } finally { setBusy(null) }
  }

  return (
    <section className="panel approvals">
      <h3 className="section-title">Permission slips</h3>
      {!res && <p className="muted">Nothing to sign yet. Payments and purchases the team drafts land here for you.</p>}
      {res && payments.length + orders.length === 0 && (
        <p className="muted">No payments or purchases needed on this one.</p>
      )}

      {payments.map((p, i) => {
        const done = p.status === 'approved'
        return (
          <div key={`p${i}`} className={`slip ${done ? 'approved' : ''}`}>
            <div className="slip-kind">💸 {p.kind === 'rent' ? 'Rent payment' : `Invoice #${p.ref_id}`}</div>
            <div className="slip-amount">{money(p.amount)}</div>
            <div className="slip-line">to <b>{p.payee}</b>{p.description && <> · {p.description}</>}</div>
            <div className="slip-line">
              due {p.due_date} {p.overdue ? <span className="hot">· {Math.abs(p.days_until_due)} days overdue</span> : <>· in {p.days_until_due} days</>}
            </div>
            <div className="slip-reason">“{p.reason}” — {p.prepared_by}</div>
            {cash && !done && <div className="slip-line muted">Checking after: {money(cash.balance - p.amount)}</div>}
            {done ? (
              <div className="slip-stamp">PAID · {p.approved_by?.replace('human:', '')}</div>
            ) : (
              <button className="approve" disabled={busy !== null} onClick={() => click('payment', i)}>
                {busy === `payment-${i}` ? 'Paying…' : 'Pay it 💸'}
              </button>
            )}
          </div>
        )
      })}

      {orders.map((o, i) => {
        const done = o.status === 'approved'
        return (
          <div key={`o${i}`} className={`slip ${done ? 'approved' : ''}`}>
            <div className="slip-kind">📦 Purchase order</div>
            <div className="slip-amount">{money(o.estimated_total)}</div>
            <div className="slip-line"><b>{o.order_qty} × {o.name}</b> (size {o.size})</div>
            <div className="slip-line">from {o.vendor_name} · arrives {o.expected_arrival} ({o.lead_days} days)</div>
            <div className="slip-reason">“{o.reason}” — {o.prepared_by}</div>
            {cash && !done && <div className="slip-line muted">Checking after: {money(cash.balance - o.estimated_total)}</div>}
            {done ? (
              <div className="slip-stamp">APPROVED · {o.approved_by?.replace('human:', '')}</div>
            ) : (
              <button className="approve" disabled={busy !== null} onClick={() => click('purchase_order', i)}>
                {busy === `purchase_order-${i}` ? 'Approving…' : 'Approve purchase 📦'}
              </button>
            )}
          </div>
        )
      })}

      {messages.map((m, i) => (
        <div key={`m${i}`} className="letter">
          <div className="slip-kind">✉️ Draft for your review · not sent</div>
          <div className="letter-head"><b>To:</b> {m.to}<br /><b>Subject:</b> {m.subject}</div>
          <p className="letter-body">{m.body}</p>
        </div>
      ))}
    </section>
  )
}
