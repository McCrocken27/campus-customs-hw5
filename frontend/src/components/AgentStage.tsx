import type { CSSProperties } from 'react'
import type { Ticket } from '../api'
import { AGENTS, MAX_LOOPS, agentInfo } from '../agents'
import type { RunView } from '../agents'
import StatusBadge from './StatusBadge'

interface Props {
  ticket: Ticket
  run: RunView
  onRun: () => void
  anyRunning: boolean
}

export default function AgentStage({ ticket, run, onRun, anyRunning }: Props) {
  const details = [
    ticket.sku && `SKU ${ticket.sku}`,
    ticket.size && `size ${ticket.size}`,
    ticket.qty !== null && `qty ${ticket.qty}`,
    ticket.lease_id !== null && `lease #${ticket.lease_id}`,
    ticket.invoice_id !== null && `invoice #${ticket.invoice_id}`,
  ].filter(Boolean) as string[]
  const running = ticket.resolve_status === 'running'
  const [boss, ...crew] = AGENTS

  return (
    <section className="panel stage">
      <div className="stage-head">
        <div>
          <div className="eyebrow">Ticket #{ticket.id} · {ticket.type.replace('_', ' ')}</div>
          <h2 className="stage-title">{ticket.subject}</h2>
          <div className="chips">
            <span className="chip">👤 {ticket.requester}</span>
            {details.map(d => <span key={d} className="chip">{d}</span>)}
          </div>
        </div>
        <div className="stage-actions">
          <StatusBadge status={ticket.resolve_status} />
          {!running && (
            <button className="run" onClick={onRun} disabled={anyRunning}>
              {ticket.resolve_status === 'not_run' ? '🚀 Send in the team' : '🔁 Run again'}
            </button>
          )}
        </div>
      </div>

      {ticket.resolve_status === 'resolved' && <div className="stamp">Resolved</div>}

      <div className="chain" aria-live="polite">
        {run.chain.length > 0 ? (
          run.chain.map((name, i) => (
            <span key={i} className="chain-step">
              {i > 0 && <span className="chain-arrow">➜</span>}
              <span className="chain-name">{agentInfo(name).emoji} {name}</span>
            </span>
          ))
        ) : (
          <span className="chain-idle">
            {running ? 'Warming up…' : run.started ? 'Hand-offs finished' : 'Nobody’s on this ticket yet'}
          </span>
        )}
      </div>

      <div className="org">
        <AgentPod name={boss.name} run={run} big />
        <div className="org-lines" aria-hidden>
          {crew.map(a => (
            <span key={a.name} className={`org-line ${run.agents[a.name].status}`} />
          ))}
        </div>
        <div className="crew">
          {crew.map(a => <AgentPod key={a.name} name={a.name} run={run} />)}
        </div>
      </div>

      {ticket.run_error && <div className="run-error">⚠️ {ticket.run_error}</div>}
    </section>
  )
}

function AgentPod({ name, run, big }: { name: string; run: RunView; big?: boolean }) {
  const info = agentInfo(name)
  const view = run.agents[info.name]
  return (
    <div className={`pod ${view.status} ${big ? 'big' : ''}`} style={{ '--agent': info.color } as CSSProperties}>
      <div className="bubble">{view.activity}</div>
      <div className="avatar">
        <span>{info.emoji}</span>
        {view.status === 'idle' && <span className="zzz">z<sup>z</sup></span>}
        {view.status === 'done' && <span className="check">✔</span>}
      </div>
      <div className="pod-name">{info.name}</div>
      <div className="pod-role">{info.role}</div>
      <div className="loops" title={`${view.loops} of ${MAX_LOOPS} loops used`}>
        {Array.from({ length: MAX_LOOPS }, (_, i) => (
          <span key={i} className={i < view.loops ? 'used' : ''} />
        ))}
      </div>
    </div>
  )
}
