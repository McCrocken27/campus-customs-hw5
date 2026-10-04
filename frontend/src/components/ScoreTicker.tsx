import { useEffect, useState } from 'react'
import { api } from '../api'
import type { Scoreboard } from '../api'

const shortDate = (iso: string) => {
  const [, m, d] = iso.split('-')
  return `${Number(m)}/${Number(d)}`
}

const shortTime = (hhmm: string | null) => {
  if (!hhmm) return ''
  const [h, m] = hhmm.split(':').map(Number)
  return ` ${((h + 11) % 12) + 1}${m ? `:${String(m).padStart(2, '0')}` : ''}${h < 12 ? 'am' : 'pm'}`
}

// A scrolling scoreboard of real Yale Athletics results, like the ticker on a sports
// broadcast (ported from the HW4 site). Hovering pauses it. Scores come from
// yalebulldogs.com through the backend's /api/scores route.
export default function ScoreTicker() {
  const [board, setBoard] = useState<Scoreboard | null>(null)

  useEffect(() => {
    const load = () =>
      api.scores()
        .then(setBoard)
        .catch(() => setBoard({ results: [], upcoming: [], updated_at: null, source: 'https://yalebulldogs.com', available: false }))
    load()
    const t = setInterval(load, 15 * 60 * 1000)
    return () => clearInterval(t)
  }, [])

  if (!board) return <div className="ticker ticker--loading" aria-hidden="true" />

  const items = [
    ...board.results.map(g => (
      <span key={`r-${g.date}-${g.sport}-${g.opponent}`} className="ticker-item">
        <span className={`ticker-badge ticker-badge--${g.outcome}`}>{g.outcome}</span>
        <strong>{g.sport}</strong>
        <span className="ticker-score">{g.yale_score}–{g.opponent_score}</span>
        <span className="ticker-opp">{g.home ? 'vs' : 'at'} {g.opponent} · {shortDate(g.date)}</span>
      </span>
    )),
    ...board.upcoming.map(g => (
      <span key={`u-${g.date}-${g.sport}-${g.opponent}`} className="ticker-item">
        <span className="ticker-badge ticker-badge--next">Next</span>
        <strong>{g.sport}</strong>
        <span className="ticker-opp">
          {g.home ? 'vs' : 'at'} {g.opponent} · {shortDate(g.date)}{shortTime(g.time)}
        </span>
      </span>
    )),
  ]

  return (
    <section className="ticker" aria-label="Yale Athletics scores">
      <div className="ticker-label">
        <span className="ticker-live" aria-hidden="true" />
        🐶 Yale Scores
      </div>
      <div className="ticker-window">
        {items.length === 0 ? (
          <span className="ticker-item ticker-empty">Scores are unavailable right now.</span>
        ) : (
          // The list is repeated twice so the scroll loops without a gap.
          <div className="ticker-track" style={{ animationDuration: `${Math.max(items.length * 5, 30)}s` }}>
            <div className="ticker-set">{items}</div>
            <div className="ticker-set" aria-hidden="true">{items}</div>
          </div>
        )}
      </div>
      <a className="ticker-link" href={board.source} target="_blank" rel="noopener noreferrer">
        Full schedule ↗
      </a>
    </section>
  )
}
