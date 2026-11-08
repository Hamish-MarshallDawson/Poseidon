import { memo } from 'react'
import { ui } from '../store/ui'
import { vessels } from '../store/vessels'
import { Button } from '../ui'
import { details } from './detail'
import { useGap, useNow, useVessel, useWatchlist } from './hooks'
import { DECISION_LABEL, TYPE_LABEL, fmtMmsi, hms, utcTime } from './format'
import type { VesselView } from '../types'
import { runBriefing } from '../briefing/store'
import { fmtEta, matchDestination, usePortInfo } from '../ports'
import type { Departure, PortIndex } from '../ports'
import { toggleReview, useInReview } from '../review/store'

// Body of a ship window: R2/Forecast/Ship card (Figma 56:4598), states No AIS and Active.
// Fields come from the live VesselView, its open GapEvent, the risk fields, and the `detail` reply.

const WEEK = 7 * 24 * 3600 * 1000

// shortcut: confidence is guessed from message age until the backend sends one; replace with the server's value.
function confidence(ageMs: number): { label: 'High' | 'Medium' | 'Low'; pips: number } {
  return ageMs < 10 * 60e3 ? { label: 'High', pips: 3 } : ageMs < 60 * 60e3 ? { label: 'Medium', pips: 2 } : { label: 'Low', pips: 1 }
}

export function EvidenceStrip({ ts, now, src = 'AISSTREAM' }: { ts: number; now: number; src?: string }) {
  const c = confidence(now - ts)
  return (
    <span className="ev">
      <span className="ev-src">{src}</span>
      <span className="ev-div" />
      <span className="ev-pips" aria-hidden>
        {[0, 1, 2].map((i) => <i key={i} className={i < c.pips ? 'on' : ''} />)}
      </span>
      <span className="ev-conf">{c.label}</span>
      <span className="ev-ts">{utcTime(ts, false)}</span>
    </span>
  )
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
  return [TYPE_LABEL[v.type_group], `MMSI ${fmtMmsi(v.mmsi)}`, flag && `${flag} flag`, length && `${Math.round(length)} m`]
    .filter(Boolean).join(' · ')
}

const portName = (p: { name: string; cc: string }) => `${p.name}, ${p.cc}`

// "From <port> → To <port>": the destination is what the ship reports; the departure is inferred from its 24 h track.
export function Route({ v, destination, eta, ports, departure }: {
  v: VesselView; destination?: string; eta?: string; ports: PortIndex | null; departure: Departure
}) {
  const raw = destination?.trim()
  const hit = raw && ports ? matchDestination(raw, ports, [v.lat, v.lon]) : null
  const etaText = eta ? fmtEta(eta) : null
  const to = !raw ? <><b>To:</b> not reported</>
    : <><b>To</b> {hit ? portName(hit.port) : `"${raw}"`} (reported){etaText && ` · ETA ${etaText}`}</>
  const from = departure === 'loading' ? <><b>From:</b> checking track…</>
    : departure === 'error' ? <><b>Departure:</b> track unavailable</>
    : departure ? <><b>From</b> {portName(departure.port)} (left {utcTime(departure.leftTs, false)}) <small>inferred from track</small></>
    : <><b>Departure</b> not seen in the last 24 h</>
  return (
    <p className="sc-route">
      <span className="sc-leg">{from}</span>
      <span className="sc-leg"><span className="sc-arrow" aria-hidden>→ </span>{to}</span>
    </p>
  )
}

export const ShipCard = memo(function ShipCard({ mmsi, onFocus }: { mmsi: number; onFocus: () => void }) {
  const v = useVessel(mmsi)
  const gap = useGap(v?.open_gap_id)
  const now = useNow()
  const replay = ui.use((s) => s.feed.mode === 'replay')
  const detail = details.use((s) => s.byMmsi[mmsi])
  const entry = useWatchlist()?.entries.find((e) => e.mmsi === mmsi)
  const inReview = useInReview(mmsi)
  const { ports, departure } = usePortInfo(mmsi)
  if (!v) return <div className="sc"><p className="sc-sub">This ship is no longer in the feed.</p></div>

  const noAis = v.status === 'gap_open' || v.status === 'silent'
  const statics = detail?.statics[0]
  const pastGaps = detail ? detail.gaps.filter((g) => g.start_ts > now - WEEK && g.id !== v.open_gap_id).length : null
  const score = detail?.score
  const rank = v.risk_rank ?? score?.rank ?? null
  const decision = entry ? DECISION_LABEL[entry.decision] : ''
  const p = v.risk_p !== null ? `${Math.round(v.risk_p * 100)} %` : null

  return (
    <div className={`sc ${noAis ? 'is-noais' : ''}`}>
      <div className="sc-head">
        <h3 className="sc-name">{v.name ?? `MMSI ${fmtMmsi(v.mmsi)}`}</h3>
        <span className={`sc-chip ${noAis ? 'noais' : ''}`}>{noAis ? 'No AIS' : 'AIS heard'}{replay && ` · as of ${utcTime(now, false)}`}</span>
      </div>
      <p className="sc-sub">{subline(v, statics?.flag_iso2 ?? v.flag, statics?.length_m ?? v.length_m)}</p>
      <Route v={v} destination={statics?.destination} eta={statics?.eta_utc} ports={ports} departure={departure} />
      <div className="sc-timer">
        <span className="sc-clock">{hms(now - v.last_ts)}</span>
        <span className="sc-caption">since last AIS ({utcTime(v.last_ts)}){replay && ` · shown time ${utcTime(now)}`}</span>
      </div>
      <div className="sc-grid">
        <Field label="Last speed" value={v.sog_kn !== null ? `${v.sog_kn.toFixed(1)} kn` : '—'} />
        <Field label={noAis ? 'Last heading' : 'Heading'} value={(v.heading_deg ?? v.cog_deg) !== null ? `${String(Math.round((v.heading_deg ?? v.cog_deg)!)).padStart(3, '0')}°` : 'Not known'} />
        <Field label="Ships heard nearby" value={gap ? `${gap.neighbours_heard} within 20 km` : '—'} />
        <Field label="Could be within" value={gap?.radius_m ? `${(gap.radius_m / 1000).toFixed(1)} km` : noAis ? '—' : 'Position current'} />
        <Field label="Sanctions" value={v.sanctioned ? 'List match' : 'No match'} />
        <Field label="Past silent gaps" value={pastGaps === null ? '—' : `${pastGaps} in 7 days`} />
      </div>
      <div className="sc-forecast">
        {noAis ? (
          <>
            <b>Forecast before the silence</b>
            <span>
              {p ? `${p}${rank ? ` · rank ${rank}` : ''}${score ? ` · made ${utcTime(score.made_at, false)}` : ''}. ` : 'No forecast was made before this silence. '}
              This silence is the event it ranked; it is scored only if it began after a frozen forecast.
            </span>
          </>
        ) : (
          <>
            <b>Forecast · next 6 h</b>
            <span>{p ? `${p} chance of a silence with reception normal nearby${rank ? ` · rank ${rank}` : ''}${decision ? ` · ${decision}` : ''}` : 'Not ranked: no forecast for this ship yet.'}</span>
          </>
        )}
      </div>
      <EvidenceStrip ts={v.last_ts} now={now} />
      <div className="sc-actions">
        <Button onClick={onFocus}>Track history</Button>
        <Button onClick={() => runBriefing([mmsi])}>Brief me</Button>
        <Button variant={inReview ? 'outline' : 'filled'} aria-pressed={inReview} onClick={() => toggleReview(mmsi)}>
          {inReview ? 'In review' : 'Add to review'}
        </Button>
      </div>
      <span className="sc-caption sc-track">{trackCaption(vessels.trails.get(mmsi))}</span>
    </div>
  )
})

// What the Track history path shows: how far back the oldest point is.
function trackCaption(trail: [number, number, number][] | undefined): string {
  if (!trail || trail.length < 2) return 'No track yet'
  const min = Math.round((trail[trail.length - 1][0] - trail[0][0]) / 60000)
  return `Track: last ${min < 60 ? `${Math.max(1, min)} min` : min >= 23 * 60 ? '24 h' : `${Math.round(min / 60)} h`}`
}
