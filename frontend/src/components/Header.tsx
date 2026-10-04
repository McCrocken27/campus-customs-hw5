import { useEffect, useRef, useState } from 'react'
import { money } from '../api'
import type { Cash } from '../api'

interface Props {
  human: string
  onHuman: (name: string) => void
  cash: Cash | null
  online: boolean
  busy: boolean
  onReset: () => void
}

// Rolls the balance up or down to its new value.
function useTween(target: number | null, ms = 900) {
  const [shown, setShown] = useState(target ?? 0)
  const from = useRef(target ?? 0)
  useEffect(() => {
    if (target === null) return
    const start = performance.now()
    const begin = from.current
    let raf = 0
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / ms)
      const eased = 1 - Math.pow(1 - t, 3)
      setShown(begin + (target - begin) * eased)
      if (t < 1) raf = requestAnimationFrame(tick)
      else from.current = target
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [target, ms])
  return shown
}

export default function Header({ human, onHuman, cash, online, busy, onReset }: Props) {
  const shown = useTween(cash?.balance ?? null)
  return (
    <header className="header">
      <div className="brand">
        <div className="logo" aria-hidden>Y</div>
        <div>
          <h1>Campus Customs <span>HQ</span> 🐶</h1>
          <p className="tagline">
            <span className={`dot ${online ? 'on' : 'off'}`} /> {online ? 'Agent team on call' : 'Backend offline'}
            {cash && <> · desk date {cash.as_of}</>}
          </p>
        </div>
      </div>

      <label className="human">
        <span>Human on duty</span>
        <input value={human} onChange={e => onHuman(e.target.value)} placeholder="Your name" maxLength={40} />
      </label>

      <div className="bank" title="Checking balance from cash_accounts">
        <div className="piggy" aria-hidden>🐷</div>
        <div>
          <div className="bank-label">Checking</div>
          <div className="bank-amount">{cash ? money(shown) : '—'}</div>
        </div>
      </div>

      <button className="ghost" onClick={onReset} disabled={busy || !online} title="Restore the database to its original values">
        ↺ Fresh run
      </button>
    </header>
  )
}
