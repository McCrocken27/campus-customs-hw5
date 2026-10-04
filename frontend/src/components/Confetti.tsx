import { useEffect, useState } from 'react'
import type { CSSProperties } from 'react'

const PIECES = ['🎉', '💙', '✨', '🐾', '🐶', '🏆', '💸']

// A quick burst of confetti whenever `burst` changes (not on first render).
export default function Confetti({ burst }: { burst: number }) {
  const [bits, setBits] = useState<{ id: number; left: number; delay: number; char: string; drift: number }[]>([])
  useEffect(() => {
    if (burst === 0) return
    setBits(Array.from({ length: 40 }, (_, i) => ({
      id: burst * 100 + i,
      left: Math.random() * 100,
      delay: Math.random() * 0.5,
      drift: (Math.random() - 0.5) * 200,
      char: PIECES[i % PIECES.length],
    })))
    const t = setTimeout(() => setBits([]), 3200)
    return () => clearTimeout(t)
  }, [burst])

  return (
    <div className="confetti" aria-hidden>
      {bits.map(b => (
        <span
          key={b.id}
          style={{ left: `${b.left}%`, animationDelay: `${b.delay}s`, '--drift': `${b.drift}px` } as CSSProperties}
        >
          {b.char}
        </span>
      ))}
    </div>
  )
}
