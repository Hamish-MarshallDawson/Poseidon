import type { Status } from './model'

// The status line with its dot: green on target, amber drifting, red off target, grey no data. Same everywhere.
export function StatusLine({ status }: { status: Status }) {
  return (
    <p className={`lab-status lab-status--${status.level}`}>
      <span className="lab-dot" aria-hidden />
      <span>{status.text}</span>
    </p>
  )
}
