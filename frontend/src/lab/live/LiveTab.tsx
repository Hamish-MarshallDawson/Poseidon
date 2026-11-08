// Live tab of a model page: 2 big tiles (accuracy, calibration gauge), a 24 h trend, details behind a toggle.
import { useState } from 'react'
import { fmtDay, fmtHM } from '../../timeline/format'
import { Chart, Legend, Line, extent } from '../charts'
import type { Metrics } from '../types'
import { LiveTrackRecord } from './LiveTrackRecord'
import { LEVEL_NAME, championOf, livePlain, targetOf, type Level, type ModelRef, type Tile } from './plain'
import './live.css'

export interface LiveTabProps {
  /** The model this page is for: 'route' | 'godark' | 'fishing', or its /lab/summary entry. */
  model: ModelRef
  metrics: Metrics | null
}

const when = (t: number) => `${fmtDay(t)} ${fmtHM(t)}`
const pct = (x: number | null) => (x == null ? '–' : x < 0.1 ? `${(x * 100).toFixed(1)}%` : `${Math.round(x * 100)}%`)

export function StatusDot({ level }: { level: Level }) {
  return <span className={`ll-dot ll-dot--${level}`} role="img" aria-label={LEVEL_NAME[level]} />
}

function Gauge({ g }: { g: NonNullable<Tile['gauge']> }) {
  const at = (v: number) => `${Math.max(0, Math.min(100, (v / g.max) * 100))}%`
  return (
    <div className="ll-gauge" aria-hidden>
      <div className="ll-gauge__fill" style={{ width: at(g.value) }} />
      <div className="ll-gauge__target" style={{ left: at(g.target) }} />
    </div>
  )
}

function BigTile({ tile }: { tile: Tile }) {
  return (
    <div className={`ll-tile ll-tile--${tile.level}`}>
      <div className="ll-tile__title"><StatusDot level={tile.level} />{tile.title}</div>
      <div className="ll-tile__value">{tile.value}</div>
      {tile.gauge && <Gauge g={tile.gauge} />}
      <div className="ll-tile__caption">{tile.caption}</div>
    </div>
  )
}

export function LiveTab({ model, metrics }: LiveTabProps) {
  const [details, setDetails] = useState(false)
  if (!metrics) return <p className="ll-muted" role="status">Loading…</p>
  const hrs = (metrics as Metrics & { hours?: number }).hours ?? 24
  const p = livePlain(metrics, model)
  const pts = p.trend.points
  const xs = extent(pts.map((q) => q.t), [0, 1])
  const x: [number, number] = xs[0] === xs[1] ? [xs[0] - 1_800_000, xs[1] + 1_800_000] : xs
  const yMax = Math.max(p.trend.kind === 'km' ? 1 : 0.01, ...pts.flatMap((q) => [q.y ?? 0, q.ref ?? 0])) * 1.1
  const fmt = (y: number | null) => (y == null ? '–' : p.trend.kind === 'km' ? `${y.toFixed(1)} km` : pct(y))
  const source = p.mode === 'backtest' ? 'Replayed past hours (no live grades yet)' : p.mode === 'live' ? 'Our live feed' : null
  return (
    <section className="ll-sec" aria-label="Live results">
      <p className="ll-muted">
        {source ? <>{source} · last {hrs} h · {p.n.toLocaleString('en-GB')} graded{p.version ? <> · {p.version}</> : null}</> : 'No graded predictions for this model yet.'}
      </p>
      <div className="ll-tiles">{p.tiles.map((t) => <BigTile key={t.title} tile={t} />)}</div>
      {pts.length > 0 && (
        <div className="ll-card">
          <h4>Last {hrs} hours, hour by hour</h4>
          <Chart label={`${p.trend.label} per hour`} x={{ type: 'time', domain: x }}
            y={{ domain: [0, yMax], format: (y) => fmt(y), ticks: 4 }} height={170}>
            <Line label={p.trend.refLabel} tone="muted" dashed data={pts.map((q) => ({ ...q, x: q.t, y: q.ref }))}
              tip={(q) => <>{when(q.t)}<br />{p.trend.refLabel}: {fmt(q.ref)}</>} />
            <Line label={p.trend.label} tone="accent" dots data={pts.map((q) => ({ ...q, x: q.t }))}
              tip={(q) => <>{when(q.t)}<br /><b>{p.trend.label}: {fmt(q.y)}</b> · {p.trend.refLabel}: {fmt(q.ref)}<br />{q.n.toLocaleString('en-GB')} graded</>} />
          </Chart>
          <Legend items={[{ label: p.trend.label, tone: 'accent' }, { label: p.trend.refLabel, tone: 'muted', kind: 'dashed' }]} />
        </div>
      )}
      {targetOf(model) !== 'fishing' && (
        <>
          <button type="button" className="ll-more" aria-expanded={details} onClick={() => setDetails((d) => !d)}>
            {details ? 'Hide details' : 'Show details'}
          </button>
          {details && <LiveTrackRecord metrics={metrics} champions={championOf(model)} only={targetOf(model) === 'route' ? 'route' : 'godark'} />}
        </>
      )}
    </section>
  )
}
