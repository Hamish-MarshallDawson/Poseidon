// "Live track record": how the running models do on our own graded feed (/lab/metrics).
import { useState } from 'react'
import { fmtDay, fmtHM } from '../../timeline/format'
import { Chart, Diagonal, Legend, Line, Markers, RefLine, extent, type LegendItem, type Tone } from '../charts'
import type { Metrics } from '../types'
import { darkSeries, headline, hLabel, horizonsIn, isBaseline, km, modesIn, pct, pooledBrierSkill, routeView, signedPct, type Mode } from './shape'
import './live.css'

export interface LiveTrackRecordProps {
  metrics: Metrics | null
  /** Model versions running now (from /lab/summary champions); the headline sentence speaks for the first one present. */
  champions?: string[]
}

const TONES: Tone[] = ['accent', 'warn', 'dark', 'bad']
const toneOf = (versions: string[], v: string): Tone => (isBaseline(v) ? 'muted' : TONES[versions.filter((x) => !isBaseline(x)).indexOf(v) % TONES.length])
const when = (t: number) => `${fmtDay(t)} ${fmtHM(t)}`
const span = (ts: number[]): [number, number] => {
  const [a, b] = extent(ts, [0, 1])
  return a === b ? [a - 1_800_000, b + 1_800_000] : [a, b]
}
const targetName = (t: string) => (/^dark_(\d+)h$/.test(t) ? `dark within ${t.slice(5, -1)} h` : t)
const MODE_NAME: Record<Mode, string> = { live: 'Live feed', backtest: 'Backtest replay' }

function Toggle<T extends string | number>({ label, value, options, onChange, name }: { label: string; value: T; options: T[]; onChange: (v: T) => void; name: (v: T) => string }) {
  if (options.length < 2) return null
  return (
    <div className="ll-toggle" role="group" aria-label={label}>
      {options.map((o) => <button key={o} type="button" aria-pressed={o === value} onClick={() => onChange(o)}>{name(o)}</button>)}
    </div>
  )
}

export function LiveTrackRecord({ metrics, champions = [] }: LiveTrackRecordProps) {
  const route = metrics?.route ?? []
  const modes = modesIn([...route, ...(metrics?.godark ?? [])])
  const horizons = horizonsIn(route)
  const [modePick, setMode] = useState<Mode | null>(null)
  const [hPick, setH] = useState<number | null>(null)
  if (!metrics) return <section className="ll-sec"><h3>Live track record</h3><p className="ll-muted">Loading…</p></section>
  const mode = modePick && modes.includes(modePick) ? modePick : modes[0] ?? 'live'
  const horizon = hPick != null && horizons.includes(hPick) ? hPick : horizons.includes(10800) ? 10800 : horizons[0]

  return (
    <section className="ll-sec" aria-labelledby="ll-live">
      <header className="ll-head">
        <h3 id="ll-live">Live track record</h3>
        <Toggle label="Which predictions" value={mode} options={modes} onChange={setMode} name={(m) => MODE_NAME[m]} />
      </header>
      <p className="ll-muted">
        Every prediction is graded once its horizon has passed. {mode === 'live' ? 'Live: predictions made on our own AIS feed as it came in.' : 'Backtest: the same models replayed over past hours of the feed.'} One point per hour; hover a point for its numbers.
      </p>
      <div className="ll-grid2">
        {horizon != null
          ? <RouteBlock metrics={metrics} champions={champions} mode={mode} horizon={horizon} horizons={horizons} setH={setH} />
          : <div className="ll-card"><h4>Where ships went · route</h4><p className="ll-muted">No graded route predictions in this window.</p></div>}
        <DarkBlock metrics={metrics} mode={mode} />
      </div>
    </section>
  )
}

function RouteBlock({ metrics, champions, mode, horizon, horizons, setH }: { metrics: Metrics; champions: string[]; mode: Mode; horizon: number; horizons: number[]; setH: (h: number) => void }) {
  const v = routeView(metrics.route, horizon, mode)
  const all = v.series.flatMap((s) => s.points)
  const head = headline(v.pooled, champions)
  const x = span(all.map((p) => p.t))
  const errMax = Math.max(1, ...all.flatMap((p) => [p.err ?? 0, p.base ?? 0])) / 1000
  const models = v.series.filter((s) => !isBaseline(s.version))
  const baseSeries = v.series.find((s) => isBaseline(s.version)) ?? models[0]
  const covKeys: LegendItem[] = [...v.series.map((s) => ({ label: s.version, tone: toneOf(v.versions, s.version) })), { label: '80% circle', tone: 'ink' }, { label: '95% circle', tone: 'ink', kind: 'dashed' }]
  const errKeys: LegendItem[] = [...models.map((s) => ({ label: s.version, tone: toneOf(v.versions, s.version) })), { label: 'dead reckoning', tone: 'muted', kind: 'dashed' }]
  return (
    <div className="ll-card">
      <header className="ll-head">
        <h4>Where ships went · route</h4>
        <Toggle label="Prediction horizon" value={horizon} options={horizons} onChange={setH} name={hLabel} />
      </header>
      {!all.length ? <p className="ll-muted">No {mode} route predictions graded at {hLabel(horizon)} in this window.</p> : (
        <>
          {head && (
            <p className="ll-say">
              At {hLabel(horizon)}, <b>{head.version}</b>'s 80% circle held the ship <b>{pct(head.cov80)}</b> of the time (target 80%), its 95% circle <b>{pct(head.cov95)}</b> (target 95%).
              {' '}Median miss <b>{km(head.err)}</b> against <b>{km(head.base)}</b> for dead reckoning: <b>{pct(head.skill)}</b> skill over dead reckoning ({head.n.toLocaleString('en-GB')} graded).
            </p>
          )}
          <h5>Circle coverage against its target</h5>
          <Chart label={`Route circle coverage per hour at ${hLabel(horizon)}`} x={{ type: 'time', domain: x }} y={{ domain: [0, 1], percent: true, ticks: 5 }} height={190}>
            <RefLine y={0.8} label="80% target" />
            <RefLine y={0.95} label="95% target" />
            {v.series.map((s) => (
              <g key={s.version}>
                <Line label={`${s.version}, 80% circle`} tone={toneOf(v.versions, s.version)} dots data={s.points.map((p) => ({ ...p, x: p.t, y: p.cov80 }))}
                  tip={(p) => <><b>{s.version}</b> · {when(p.t)}<br />80% circle held {pct(p.cov80)} (target 80%), {p.n} graded</>} />
                <Line label={`${s.version}, 95% circle`} tone={toneOf(v.versions, s.version)} dashed data={s.points.map((p) => ({ ...p, x: p.t, y: p.cov95 }))}
                  tip={(p) => <><b>{s.version}</b> · {when(p.t)}<br />95% circle held {pct(p.cov95)} (target 95%), {p.n} graded</>} />
              </g>
            ))}
          </Chart>
          <Legend items={covKeys} />
          <h5>Median miss distance against dead reckoning</h5>
          <Chart label={`Route median error per hour at ${hLabel(horizon)}`} x={{ type: 'time', domain: x }} y={{ domain: [0, errMax * 1.05], format: (y) => `${Math.round(y)} km`, ticks: 4 }} height={170}>
            {baseSeries && <Line label="dead reckoning" tone="muted" dashed data={baseSeries.points.map((p) => ({ ...p, x: p.t, y: p.base == null ? null : p.base / 1000 }))}
              tip={(p) => <><b>Dead reckoning</b> · {when(p.t)}<br />median miss {km(p.base)}</>} />}
            {models.map((s) => (
              <Line key={s.version} label={s.version} tone={toneOf(v.versions, s.version)} dots data={s.points.map((p) => ({ ...p, x: p.t, y: p.err == null ? null : p.err / 1000 }))}
                tip={(p) => <><b>{s.version}</b> · {when(p.t)}<br />median miss {km(p.err)} against {km(p.base)} dead reckoning, {p.n} graded</>} />
            ))}
          </Chart>
          <Legend items={errKeys} />
        </>
      )}
    </div>
  )
}

function DarkBlock({ metrics, mode }: { metrics: Metrics; mode: Mode }) {
  const series = darkSeries(metrics.godark, mode)
  const pts = series.flatMap((s) => s.points)
  const tone = (i: number) => TONES[i % TONES.length]
  const [lo, hi] = extent([-0.1, 0.1, ...pts.map((p) => p.brier_skill)])
  return (
    <div className="ll-card">
      <h4>Who went dark · go-dark risk</h4>
      {metrics.lift.length > 0 && (
        <ul className="ll-lift">
          {metrics.lift.map((l) => (
            <li key={l.target}>
              <b>{targetName(l.target)}</b>: the top {pct(l.top_share)} by risk went dark <b>{pct(l.top_hit_rate, 1)}</b> of the time, against <b>{pct(l.all_hit_rate, 1)}</b> for all ships
              {l.all_hit_rate > 0 && <> ({(l.top_hit_rate / l.all_hit_rate).toFixed(1)}× lift)</>}.
            </li>
          ))}
        </ul>
      )}
      {metrics.reliability.length > 0 && (
        <>
          <h5>Does p mean what it says? Predicted against observed</h5>
          <div className="ll-rel">{metrics.reliability.map((r) => <ReliabilityPlot key={r.target} r={r} />)}</div>
          <p className="ll-muted">On the diagonal a prediction of p comes true p of the time; below it the model over-warns. Dot size is the number of predictions in the bin.</p>
        </>
      )}
      <h5>Brier skill over the base rate (above 0 beats always guessing the average)</h5>
      {!pts.length ? <p className="ll-muted">No {mode} go-dark predictions from a model graded in this window.</p> : (
        <>
          <p className="ll-say">
            Over the window: {series.map((s, i) => <span key={s.key}>{i > 0 && '; '}{targetName(s.target)} <b>{signedPct(pooledBrierSkill(s))}</b></span>)}.
          </p>
          <Chart label="Go-dark Brier skill per hour" x={{ type: 'time', domain: span(pts.map((p) => p.t)) }} y={{ domain: [lo * 1.1, hi * 1.1], format: signedPct, ticks: 4 }} height={170}>
            <RefLine y={0} label="no skill" solid />
            {series.map((s, i) => (
              <Line key={s.key} label={s.key} tone={tone(i)} dots data={s.points.map((p) => ({ ...p, x: p.t, y: p.brier_skill }))}
                tip={(p) => <><b>{targetName(s.target)}</b> · {s.version}<br />{when(p.t)}: Brier skill {signedPct(p.brier_skill)} ({p.positives} of {p.n} went dark)</>} />
            ))}
          </Chart>
          <Legend items={series.map((s, i) => ({ label: `${targetName(s.target)} · ${s.version}`, tone: tone(i) }))} />
        </>
      )}
    </div>
  )
}

function ReliabilityPlot({ r }: { r: Metrics['reliability'][number] }) {
  const max = Math.min(1, Math.max(0.05, ...r.bins.flatMap((b) => [b.p_mean, b.hit_rate])) * 1.1)
  const nMax = Math.max(1, ...r.bins.map((b) => b.n))
  return (
    <figure>
      <figcaption>{targetName(r.target)}</figcaption>
      <Chart label={`Reliability, ${targetName(r.target)}`} x={{ domain: [0, max], percent: true, label: 'predicted p', ticks: 4 }} y={{ domain: [0, max], percent: true, label: 'went dark', ticks: 4 }} height={210}>
        <Diagonal label="calibrated" />
        <Markers data={r.bins.map((b) => ({ ...b, x: b.p_mean, y: b.hit_rate, size: 2.5 + 7 * Math.sqrt(b.n / nMax) }))} label="reliability bin"
          tip={(b) => <>Predicted {pct(b.p_mean, 1)}, went dark {pct(b.hit_rate, 1)}<br />{b.n.toLocaleString('en-GB')} predictions</>} />
      </Chart>
    </figure>
  )
}
