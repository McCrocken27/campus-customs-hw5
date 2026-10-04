import type { CSSProperties } from 'react'
import type { TicketDetail } from '../api'
import { AGENTS, describeTool } from '../agents'
import type { RunView } from '../agents'

export default function Summaries({ run, detail }: { run: RunView; detail: TicketDetail | null }) {
  const decision = detail?.result?.decision
  return (
    <section className="panel summaries">
      <h3 className="section-title">Who did what</h3>

      {decision && (
        <div className="verdict">
          <div className="verdict-label">🐶 The Boss’s call</div>
          <p className="verdict-text">{decision.decision}</p>
          {decision.next_steps.length > 0 && (
            <ol className="steps">
              {decision.next_steps.map((s, i) => <li key={i}>{s}</li>)}
            </ol>
          )}
          {decision.missing_data.length > 0 && (
            <p className="muted small">Not in the database: {decision.missing_data.join('; ')}</p>
          )}
        </div>
      )}

      <div className="summary-grid">
        {AGENTS.map(a => {
          const v = run.agents[a.name]
          const involved = v.calls > 0
          return (
            <div key={a.name} className={`summary ${involved ? '' : 'benched'}`} style={{ '--agent': a.color } as CSSProperties}>
              <div className="summary-head">
                <span className="summary-emoji">{a.emoji}</span>
                <b>{a.name}</b>
                {involved && <span className="summary-stats">{v.loops}/7 loops · {v.tools.length} tools</span>}
              </div>
              {!involved ? (
                <p className="muted">{run.started ? 'Sat this one out 💤' : 'Waiting for a run'}</p>
              ) : (
                <>
                  {v.summaries.length > 0
                    ? v.summaries.map((s, i) => <p key={i} className="summary-text">{s}</p>)
                    : <p className="muted">{v.status === 'error' ? v.error : 'Still working…'}</p>}
                  {v.drafts.length > 0 && (
                    <ul className="drafts">{v.drafts.map((d, i) => <li key={i}>📝 {d}</li>)}</ul>
                  )}
                  {v.tools.length > 0 && (
                    <div className="tools">
                      {v.tools.map(t => (
                        <span key={t} className="tool" title={describeTool(t)}>{t}</span>
                      ))}
                    </div>
                  )}
                </>
              )}
            </div>
          )
        })}
      </div>
    </section>
  )
}
