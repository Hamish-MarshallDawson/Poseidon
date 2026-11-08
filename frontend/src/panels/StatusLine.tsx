import { ui } from '../store/ui'
import { yachts } from '../yachts/store'
import { showFilter } from '../show/registry'
import { matchCount, setShow } from '../show/state'
import { HEAT_FADE } from '../map/density'
import { fmtInt, minutes, utcTime } from '../windows/format'

// Minimal status line, top-left (Figma 66:21909). Live: "● LIVE 14:07:12Z · 100 of 2,184 ships in view · …".
// Replay (timeline report): "REPLAY 13:05:12Z −1 h 02 min · …". The counts come from the map (ui.view).
export function StatusLine() {
  const feed = ui.use((s) => s.feed)
  const view = ui.use((s) => s.view)
  const focus = ui.use((s) => s.focusMmsi)
  const related = ui.use((s) => s.focusRelated.length)
  const show = ui.use((s) => s.show)
  const heatLayer = ui.use((s) => s.layers.density && !s.follow)
  yachts.use((s) => s.byMmsi)   // the yachts filter counts from this list
  const replay = feed.mode === 'replay'
  const stalled = feed.sources.some((s) => s.state === 'stall' || s.state === 'down')

  const parts = [
    focus !== null
      ? `Nearby ships · ${related} shown`
      : `${fmtInt(view.shown)} of ${fmtInt(view.inView)} ${replay ? 'then' : 'ships in view'}`,   // replay wording per 68:16538
  ]
  if (focus === null && view.stacked) parts.push(`${fmtInt(view.stacked)} in stacks`)
  if (focus === null && heatLayer && show === 'all' && view.zoom < HEAT_FADE[1]) parts.push(`heat map: ${fmtInt(view.inView)} ships`)
  if (view.noCoverageCells) parts.push(`${fmtInt(view.noCoverageCells)} cells without coverage`)
  if (stalled) parts.push('our feed paused')

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
      <span className="sl-text">
        {utcTime(feed.now_ts)}
        {replay && feed.replay && ` · −${minutes(feed.replay.to_ts - feed.now_ts)}`} · {parts.join(' · ')}{replay && feed.paused && ' · paused'}
      </span>
      {show !== 'all' && (
        <span className="sl-show">
          {showFilter(show).chip(matchCount(show))}
          <button type="button" className="sl-showall" onClick={() => setShow('all')}>Show all</button>
        </span>
      )}
      {feed.isMock && <span className="sl-mock">ILLUSTRATIVE DATA</span>}
    </div>
  )
}
