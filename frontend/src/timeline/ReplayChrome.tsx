import { ui } from '../store/ui'
import { fmtDay, fmtTime } from './format'
import './scrubbar.css'

// In replay: a 2 px --dvm-replay-edge round the screen and the REPLAY tab at the top centre. Both stay mounted and fade
// or slide, so entering and leaving replay animate both ways.
export function ReplayChrome() {
  const replay = ui.use((s) => s.feed.mode === 'replay')
  const t = ui.use((s) => Math.floor((s.time.dragT ?? s.feed.now_ts) / 1000) * 1000)
  return (
    <>
      <div className={`tl-edge${replay ? ' on' : ''}`} aria-hidden />
      <div className={`tl-tab${replay ? ' on' : ''}`} role="status" aria-hidden={!replay}>
        <b>REPLAY</b>showing {fmtDay(t)} {fmtTime(t)} · not live
      </div>
    </>
  )
}
