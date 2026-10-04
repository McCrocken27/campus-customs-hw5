import { useEffect, useRef } from 'react'
import { agentInfo } from '../agents'
import type { FeedItem } from '../agents'

const ICON: Record<string, string> = { Human: '🙋', System: '🎬' }

export default function ActivityFeed({ feed, running }: { feed: FeedItem[]; running: boolean }) {
  const box = useRef<HTMLOListElement>(null)
  useEffect(() => {
    box.current?.scrollTo({ top: box.current.scrollHeight, behavior: 'smooth' })
  }, [feed.length])

  return (
    <section className="panel feed">
      <h3 className="section-title">Live feed {running && <span className="live">● LIVE</span>}</h3>
      {feed.length === 0 ? (
        <p className="muted">When the team starts, every step shows up here.</p>
      ) : (
        <ol ref={box}>
          {feed.map(item => (
            <li key={item.index + item.text} className={`feed-item kind-${item.kind}`}>
              <span className="feed-icon">{ICON[item.agent] ?? agentInfo(item.agent).emoji}</span>
              <div>
                <div className="feed-who">
                  {item.agent}
                  <time>{new Date(item.time).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit', second: '2-digit' })}</time>
                </div>
                <div className="feed-text">{item.text}</div>
              </div>
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}
