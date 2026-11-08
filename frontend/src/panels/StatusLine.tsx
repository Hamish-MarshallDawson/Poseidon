import { ui } from '../store/ui'
import { yachts } from '../yachts/store'
import { showFilter } from '../show/registry'
import { matchCount, setShow } from '../show/state'
import { vessels } from '../store/vessels'
import { fmtInt, utcTime } from '../windows/format'

// Status chip, top-left: how many ships we get data from, not how many the map draws.
// Live: "LIVE · 18,432 ships". Replay: "REPLAY · Sat 19:03Z · 9,214 ships". A Show filter replaces the count.
export function StatusLine() {
  const feed = ui.use((s) => s.feed)
  const show = ui.use((s) => s.show)
  ui.use((s) => s.view)   // re-render with each map pass, which follows the data
  yachts.use((s) => s.byMmsi)   // the yachts filter counts from this list
  const replay = feed.mode === 'replay'
  const stalled = feed.sources.some((s) => s.state === 'stall' || s.state === 'down')
  const ships = `${fmtInt(vessels.vessels.size)} ships`
  const day = new Date(feed.now_ts).toUTCString().slice(0, 3)

  const parts = [
    ...(replay ? [`${day} ${utcTime(feed.now_ts)}`] : []),
    show === 'all' ? ships : null,
    replay && feed.paused ? 'paused' : null,
    stalled ? 'our feed paused' : null,
  ].filter(Boolean)

  return (
    <div className={`status-line ${replay ? 'is-replay' : ''}`} role="status" aria-live="off">
      {replay ? (
        <span className="sl-replay">REPLAY</span>
      ) : (
        <>
          <span className={`sl-dot ${feed.connected ? '' : 'off'}`} aria-hidden />
          <span className="sl-mode">{feed.connected ? 'LIVE' : 'NO FEED'}</span>
        </>
      )}
      {parts.length > 0 && <span className="sl-text">· {parts.join(' · ')}</span>}
      {show !== 'all' && (
        <span className="sl-show">
          {parts.length === 0 && '· '}{showFilter(show).chip(matchCount(show))}
          <button type="button" className="sl-showall" onClick={() => setShow('all')}>Show all</button>
        </span>
      )}
      {feed.isMock && <span className="sl-mock">ILLUSTRATIVE DATA</span>}
    </div>
  )
}
