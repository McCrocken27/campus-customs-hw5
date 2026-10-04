import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api } from './api'
import type { AuditEvent, Cash, Ticket, TicketDetail } from './api'
import { buildRun, latestRunId } from './agents'
import Header from './components/Header'
import TicketList from './components/TicketList'
import AgentStage from './components/AgentStage'
import ActivityFeed from './components/ActivityFeed'
import Approvals from './components/Approvals'
import Summaries from './components/Summaries'
import Confetti from './components/Confetti'
import ScoreTicker from './components/ScoreTicker'
import { PeekingBulldog, RivalryRow } from './components/Mascots'

const NAME_KEY = 'cc-human-on-duty'

export default function App() {
  const [tickets, setTickets] = useState<Ticket[]>([])
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [detail, setDetail] = useState<TicketDetail | null>(null)
  const [events, setEvents] = useState<AuditEvent[]>([])
  const [cash, setCash] = useState<Cash | null>(null)
  const [online, setOnline] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [human, setHuman] = useState(() => localStorage.getItem(NAME_KEY) ?? 'Joey')
  const [confettiKey, setConfettiKey] = useState(0)
  const lastIndex = useRef(-1)
  const prevStatus = useRef<Record<number, string>>({})

  useEffect(() => localStorage.setItem(NAME_KEY, human), [human])

  const anyRunning = tickets.some(t => t.resolve_status === 'running')

  const loadTickets = useCallback(async () => {
    try {
      const list = await api.tickets()
      setTickets(list)
      setOnline(true)
      // celebrate when a ticket goes from running to finished
      for (const t of list) {
        const before = prevStatus.current[t.id]
        if (before === 'running' && t.resolve_status !== 'running') setConfettiKey(k => k + 1)
        prevStatus.current[t.id] = t.resolve_status
      }
      setSelectedId(id => id ?? list[0]?.id ?? null)
    } catch {
      setOnline(false)
    }
  }, [])

  const loadCash = useCallback(async () => {
    try { setCash(await api.cash()) } catch { /* shown as offline by loadTickets */ }
  }, [])

  const loadEvents = useCallback(async () => {
    try {
      const { events: fresh, last_index } = await api.events(lastIndex.current)
      if (fresh.length) {
        lastIndex.current = Math.max(lastIndex.current, last_index)
        // Polls can overlap, so merge by index: each event appears once, in order.
        setEvents(prev => {
          const byIndex = new Map(prev.map(e => [e.index, e]))
          let added = false
          for (const e of fresh) if (!byIndex.has(e.index)) { byIndex.set(e.index, e); added = true }
          return added ? [...byIndex.values()].sort((a, b) => a.index - b.index) : prev
        })
      }
    } catch { /* offline */ }
  }, [])

  const loadDetail = useCallback(async (id: number) => {
    try { setDetail(await api.ticket(id)) } catch { /* offline */ }
  }, [])

  // Poll: faster while the team is working.
  useEffect(() => {
    loadTickets(); loadCash(); loadEvents()
    const fast = anyRunning ? 1500 : 5000
    const t1 = setInterval(loadTickets, fast)
    const t2 = setInterval(loadEvents, anyRunning ? 1200 : 5000)
    const t3 = setInterval(loadCash, 6000)
    return () => { clearInterval(t1); clearInterval(t2); clearInterval(t3) }
  }, [anyRunning, loadTickets, loadCash, loadEvents])

  const selected = tickets.find(t => t.id === selectedId) ?? null

  // Reload the selected ticket's detail whenever its status changes.
  useEffect(() => {
    if (selectedId !== null) loadDetail(selectedId)
  }, [selectedId, selected?.resolve_status, selected?.approved_drafts, loadDetail])

  const run = useMemo(() => {
    if (selectedId === null || selected?.resolve_status === 'not_run') return buildRun([], null)
    return buildRun(events, latestRunId(events, selectedId))
  }, [events, selectedId, selected?.resolve_status])

  const flash = (msg: string) => { setError(msg); setTimeout(() => setError(null), 6000) }

  async function startRun(id: number) {
    if (!human.trim()) return flash('Type your name first — agents only run when a human asks.')
    try {
      await api.run(id, human.trim())
      setSelectedId(id)
      await loadTickets()
      await loadEvents()
    } catch (e) { flash((e as Error).message) }
  }

  async function approve(kind: 'payment' | 'purchase_order', index: number) {
    if (!human.trim()) return flash('Type your name first so we know who approved it.')
    if (selectedId === null) return
    try {
      await api.approve(selectedId, kind, index, human.trim())
      setConfettiKey(k => k + 1)
      await Promise.all([loadTickets(), loadCash(), loadDetail(selectedId)])
    } catch (e) { flash((e as Error).message) }
  }

  async function reset() {
    if (!window.confirm('Reset the database to its original values? Payments and team results will be wiped (the audit trail is kept).')) return
    try {
      await api.reset(human.trim() || 'unknown')
      prevStatus.current = {}
      await Promise.all([loadTickets(), loadCash(), loadEvents()])
      if (selectedId !== null) await loadDetail(selectedId)
    } catch (e) { flash((e as Error).message) }
  }

  return (
    <div className="app">
      <Confetti burst={confettiKey} />
      <Header human={human} onHuman={setHuman} cash={cash} online={online} onReset={reset} busy={anyRunning} />
      <ScoreTicker />
      {error && <div className="toast" role="alert">{error}</div>}
      {!online && (
        <div className="offline">
          The backend isn’t answering at http://localhost:8000. Start it from <code>hw5/backend</code> with{' '}
          <code>uvicorn main:app --reload --port 8000</code>.
        </div>
      )}
      <div className="layout">
        <TicketList
          tickets={tickets}
          selectedId={selectedId}
          onSelect={setSelectedId}
          onRun={startRun}
          anyRunning={anyRunning}
        />
        <main className="stage-col">
          {selected ? (
            <>
              <AgentStage ticket={selected} run={run} onRun={() => startRun(selected.id)} anyRunning={anyRunning} />
              <div className="two-col">
                <ActivityFeed feed={run.feed} running={selected.resolve_status === 'running'} />
                <Approvals detail={detail} onApprove={approve} cash={cash} />
              </div>
              <Summaries run={run} detail={detail} />
            </>
          ) : (
            <div className="panel empty">Loading tickets…</div>
          )}
        </main>
      </div>
      <RivalryRow />
      <PeekingBulldog />
      <footer>Boola Boola! 🐶 Campus Customs HQ · every number comes from the campus-customs MCP server · nothing is paid or sent without a human</footer>
    </div>
  )
}
