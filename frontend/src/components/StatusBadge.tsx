import type { ResolveStatus } from '../api'

const LABELS: Record<ResolveStatus, string> = {
  not_run: 'Not started',
  running: 'Agents working',
  failed: 'Hit a snag',
  awaiting_approval: 'Needs you',
  resolved: 'Resolved',
}

export default function StatusBadge({ status }: { status: ResolveStatus }) {
  return (
    <span className={`badge ${status}`}>
      {status === 'running' && <span className="spinner" aria-hidden />}
      {status === 'resolved' && '✔ '}
      {LABELS[status] ?? status}
    </span>
  )
}
