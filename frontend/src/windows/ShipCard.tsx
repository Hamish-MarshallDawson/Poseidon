import { memo } from 'react'
import { ui } from '../store/ui'
import { vessels } from '../store/vessels'
import { Button } from '../ui'
import { details } from './detail'
import { useGap, useNow, useVessel, useWatchlist } from './hooks'
import { DECISION_LABEL, TYPE_LABEL, fmtMmsi, hms, utcTime } from './format'
import { raisedBy } from '../forecast/labels'
import type { VesselView } from '../types'
import { runBriefing } from '../briefing/store'
import { fmtEta, matchDestination, usePortInfo } from '../ports'
import type { Departure, PortIndex } from '../ports'
import { yachts } from '../yachts/store'
import { YachtSection } from '../yachts/Yachts'
import { toggleReview, useInReview } from '../review/store'
import { ShipHistory } from './ShipHistory'
import { ShipPresence } from '../collab/presence/SharedList'

// Body of a ship window: R2/Forecast/Ship card (Figma 56:4598), states No AIS and Active.
// Fields come from the live VesselView, its open GapEvent, the risk fields, and the `detail` reply.

const WEEK = 7 * 24 * 3600 * 1000

// shortcut: confidence is guessed from message age until the backend sends one; replace with the server's value.
function confidence(ageMs: number): { label: 'High' | 'Medium' | 'Low'; pips: number } {
  return ageMs < 10 * 60e3 ? { label: 'High', pips: 3 } : ageMs < 60 * 60e3 ? { label: 'Medium', pips: 2 } : { label: 'Low', pips: 1 }
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="sc-field">
      <span className="sc-label">{label}</span>
      <span className="sc-value">{value}</span>
    </div>
  )
}

function subline(v: VesselView, flag: string | null | undefined, length: number | null | undefined): string {
  return [TYPE_LABEL[v.type_group], v.cls && `Class ${v.cls}`, `MMSI ${fmtMmsi(v.mmsi)}`, flag && `${flag} flag`, length && `${Math.round(length)} m`]
    .filter(Boolean).join(' · ')
}

const portName = (p: { name: string; cc: string }) => `${p.name}, ${p.cc}`

// One line: "From <port> (left 14:00Z) → To <port> (reported) · ETA …". The departure is inferred from the 24 h track and
// the destination is what the ship reports; a half that is unknown is left out, and so is the whole line when both are.
export function Route({ v, destination, eta, ports, departure }: {
  v: VesselView; destination?: string; eta?: string; ports: PortIndex | null; departure: Departure
}) {
  const raw = destination?.trim()
  const hit = raw && ports ? matchDestination(raw, ports, [v.lat, v.lon]) : null
  const etaText = eta ? fmtEta(eta) : null
  const from = departure && departure !== 'loading' && departure !== 'error' ? <><b>From</b> {portName(departure.port)} (left {utcTime(departure.leftTs, false)})</> : null
  const to = raw ? <><b>To</b> {hit ? portName(hit.port) : `"${raw}"`} (reported){etaText && ` · ETA ${etaText}`}</> : null
  if (!from && !to) return null
  return <p className="sc-route">{from}{from && to && <span aria-hidden> → </span>}{to}</p>
}

export const ShipCard = memo(function ShipCard({ mmsi }: { mmsi: number }) {
  const v = useVessel(mmsi)
  const gap = useGap(v?.open_gap_id)
  const now = useNow()
  const replay = ui.use((s) => s.feed.mode === 'replay')
  const detail = details.use((s) => s.byMmsi[mmsi])
  const entry = useWatchlist()?.entries.find((e) => e.mmsi === mmsi)
  const inReview = useInReview(mmsi)
  const yachtSanctioned = yachts.use((s) => !!s.byMmsi.get(mmsi)?.sanctioned)
  const { ports, departure } = usePortInfo(mmsi)
  if (!v) return <div className="sc"><p className="sc-sub">This ship is no longer in the feed.</p></div>

  const noAis = v.status === 'gap_open' || v.status === 'silent'
  const statics = detail?.statics[0]
  const pastGaps = detail ? detail.gaps.filter((g) => g.start_ts > now - WEEK && g.id !== v.open_gap_id).length : null
  const score = detail?.score
  const rank = v.risk_rank ?? score?.rank ?? null
  const decision = entry ? DECISION_LABEL[entry.decision] : ''
  const pv = v.risk_p ?? (score?.target === 'dark_6h' ? score.p : null)
  const p = pv !== null ? `${Math.round(pv * 100)} %` : null
  const raised = raisedBy(score?.contrib)

  return (
    <div className={`sc ${noAis ? 'is-noais' : ''}`}>
      {noAis && <span className="sc-chip noais">No AIS</span>}
      <p className="sc-sub">{subline(v, statics?.flag_iso2 ?? v.flag, statics?.length_m ?? v.length_m)}</p>
      <ShipPresence mmsi={mmsi} />
      <Route v={v} destination={statics?.destination} eta={statics?.eta_utc} ports={ports} departure={departure} />
      <ShipHistory mmsi={mmsi} now={now} />
      <div className="sc-timer">
        <span className="sc-clock">{hms(now - v.last_ts)}</span>
        <span className="sc-caption">since last AIS {utcTime(v.last_ts, false)} · AISStream, {confidence(now - v.last_ts).label.toLowerCase()}{replay && ` · shown time ${utcTime(now, false)}`}</span>
      </div>
      <div className="sc-grid">
        <Field label="Last speed" value={v.sog_kn !== null ? `${v.sog_kn.toFixed(1)} kn` : '—'} />
        <Field label={noAis ? 'Last heading' : 'Heading'} value={(v.heading_deg ?? v.cog_deg) !== null ? `${String(Math.round((v.heading_deg ?? v.cog_deg)!)).padStart(3, '0')}°` : 'Not known'} />
        {gap && <Field label="Ships heard nearby" value={`${gap.neighbours_heard} within 20 km`} />}
        {gap?.radius_m ? <Field label="Could be within" value={`${(gap.radius_m / 1000).toFixed(1)} km`} /> : null}
        {v.sanctioned && !yachtSanctioned && <Field label="Sanctions" value="List match" />}
        {pastGaps ? <Field label="Past silent gaps" value={`${pastGaps} in 7 days`} /> : null}
      </div>
      <YachtSection mmsi={mmsi} />
      {p && (
        <p className="sc-note">
          <b>{noAis ? 'Forecast before the silence' : 'Chance of going dark, next 6 h:'}</b>{' '}
          {p}{rank ? ` · rank ${rank}` : ''}
          {noAis ? (score ? ` · made ${utcTime(score.made_at, false)}` : '') : decision ? ` · ${decision}` : ''}
          {raised.length > 0 && <> · raised by {raised.join(', ')}</>}
          {score?.model_version && <span className="sc-model"> · {score.model_version}</span>}
        </p>
      )}
      <div className="sc-actions">
        <Button onClick={() => runBriefing([mmsi])}>Brief me</Button>
        <Button variant={inReview ? 'outline' : 'filled'} aria-pressed={inReview} onClick={() => toggleReview(mmsi)}>
          {inReview ? 'In review' : 'Add to review'}
        </Button>
      </div>
      <span className="sc-caption sc-track">{trackCaption(vessels.trails.get(mmsi))}</span>
    </div>
  )
})

// What the always-on past track shows: how far back the oldest point is.
function trackCaption(trail: [number, number, number][] | undefined): string {
  if (!trail || trail.length < 2) return 'No track yet'
  const min = Math.round((trail[trail.length - 1][0] - trail[0][0]) / 60000)
  return `Track: last ${min < 60 ? `${Math.max(1, min)} min` : min >= 23 * 60 ? '24 h' : `${Math.round(min / 60)} h`}`
}
