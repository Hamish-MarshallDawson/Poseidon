// "Live track record": how the running models do on our own graded feed (/lab/metrics).
import { useState } from 'react'
import { fmtDay, fmtHM } from '../../timeline/format'
import { Plot, Ref, type PlotCtx } from './Plot'
import { darkSeries, headline, hLabel, horizonsIn, isBaseline, km, modesIn, path, pct, pooledBrierSkill, routeView, signedPct } from './shape'
import type { LabMetrics, Mode, Reliability } from './types'
import './live.css'

export interface LiveTrackRecordProps {
  metrics: LabMetrics | null
  /** Model versions running now (from /lab/summary champions); the headline sentence uses the first one present. */
  champions?: string[]
}

const COLORS = ['var(--dvm-accent-default)', 'var(--dvm-ship-class-b)', 'var(--dvm-risk-2)', 'var(--dvm-risk-4)']
const colorOf = (versions: string[], v: string) => (isBaseline(v) ? 'var(--dvm-text-muted)' : COLORS[versions.filter((x) => !isBaseline(x)).indexOf(v) % COLORS.length])
const when = (t: number) => `${fmtDay(t)} ${fmtHM(t)}`

interface Pt { t: number; v: number | null; tip: string }
/** A line with hoverable dots; null values break the line. */
function Series({ c, pts, color, dashed }: { c: PlotCtx; pts: Pt[]; color: string; dashed?: boolean }) {
  const runs: Pt[][] = [[]]
  for (const p of pts) {
    if (p.v == null) runs.push([])
    else runs[runs.length - 1].push(p)
  }
  return (
    <g style={{ color }}>
      {runs.filter((r) => r.length > 1).map((r, i) => <path key={i} className={dashed ? 'll-line dashed' : 'll-line'} d={path(r.map((p) => [c.x(p.t), c.y(p.v as number)]))} />)}
      {pts.filter((p) => p.v != null).map((p) => <circle key={p.t} className="ll-dot" cx={c.x(p.t)} cy={c.y(p.v as number)} r={2.5}><title>{p.tip}</title></circle>)}
    </g>
  )
}

function Keys({ items }: { items: { label: string; color: string; dashed?: boolean }[] }) {
  return (
    <ul className="ll-keys">
      {items.map((k) => <li key={k.label}><i className={k.dashed ? 'dashed' : ''} style={{ color: k.color }} />{k.label}</li>)}
    </ul>
  )
}

function Toggle<T extends string | number>({ label, value, options, onChange, name }: { label: string; value: T; options: T[]; onChange: (v: T) => void; name: (v: T) => string }) {
  if (options.length < 2) return null
  return (
    <div className="ll-toggle" role="group" aria-label={label}>
      {options.map((o) => <button key={o} aria-pressed={o === value} onClick={() => onChange(o)}>{name(o)}</button>)}
    </div>
  )
}

const MODE_NAME: Record<Mode, string> = { live: 'Live feed', backtest: 'Backtest replay' }

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
        Every prediction is graded once its horizon has passed. {mode === 'live' ? 'Live: predictions made on our own AIS feed as it came in.' : 'Backtest: the same models replayed over past hours of the feed.'} One point per hour.
      </p>
      <div className="ll-grid2">
        {horizon != null && <RouteBlock metrics={metrics} champions={champions} mode={mode} horizon={horizon} horizons={horizons} setH={setH} />}
        <DarkBlock metrics={metrics} mode={mode} />
      </div>
    </section>
  )
}

function RouteBlock({ metrics, champions, mode, horizon, horizons, setH }: { metrics: LabMetrics; champions: string[]; mode: Mode; horizon: number; horizons: number[]; setH: (h: number) => void }) {
  const v = routeView(metrics.route, horizon, mode)
  const all = v.series.flatMap((s) => s.points)
  const head = headline(v.pooled, champions)
  const t0 = Math.min(...all.map((p) => p.t)), t1 = Math.max(...all.map((p) => p.t))
  const errMax = Math.max(1, ...all.flatMap((p) => [p.err ?? 0, p.base ?? 0])) / 1000
  const models = v.series.filter((s) => !isBaseline(s.version))
  const baseSeries = v.series.find((s) => isBaseline(s.version)) ?? models[0]
  return (
    <div className="ll-card">
      <header className="ll-head">
        <h4>Where ships went · route</h4>
        <Toggle label="Prediction horizon" value={horizon} options={horizons} onChange={setH} name={(h) => hLabel(h)} />
      </header>
      {!all.length ? <p className="ll-muted">No graded route predictions at {hLabel(horizon)} in this window.</p> : (
        <>
          {head && (
            <p className="ll-say">
              At {hLabel(horizon)}, <b>{head.version}</b>'s 80% circle held the ship <b>{pct(head.cov80)}</b> of the time (target 80%), the 95% circle <b>{pct(head.cov95)}</b> (target 95%).
              {' '}Median miss <b>{km(head.err)}</b> against <b>{km(head.base)}</b> for dead reckoning: <b>{pct(head.skill)}</b> skill over dead reckoning ({head.n.toLocaleString('en-GB')} graded).
            </p>
          )}
          <h5>Circle coverage against its target</h5>
          <Plot label={`Route circle coverage per hour at ${hLabel(horizon)}`} x={[t0, t1]} y={[0, 1]} time yTick={(y) => pct(y)}>
            {(c) => (
              <>
                <Ref c={c} v={0.8} label="80% target" />
                <Ref c={c} v={0.95} label="95% target" />
                {v.series.map((s) => (
                  <g key={s.version}>
                    <Series c={c} color={colorOf(v.versions, s.version)} pts={s.points.map((p) => ({ t: p.t, v: p.cov80, tip: `${s.version} ${when(p.t)}: 80% circle held ${pct(p.cov80)} (n ${p.n})` }))} />
                    <Series c={c} dashed color={colorOf(v.versions, s.version)} pts={s.points.map((p) => ({ t: p.t, v: p.cov95, tip: `${s.version} ${when(p.t)}: 95% circle held ${pct(p.cov95)} (n ${p.n})` }))} />
                  </g>
                ))}
              </>
            )}
          </Plot>
          <Keys items={[...v.series.map((s) => ({ label: s.version, color: colorOf(v.versions, s.version) })), { label: 'solid 80% · dashed 95%', color: 'var(--dvm-text-muted)', dashed: true }]} />
          <h5>Median miss distance against dead reckoning</h5>
          <Plot label={`Route median error per hour at ${hLabel(horizon)}`} x={[t0, t1]} y={[0, errMax]} time yTick={(y) => `${y} km`}>
            {(c) => (
              <>
                {baseSeries && <Series c={c} dashed color="var(--dvm-text-muted)" pts={baseSeries.points.map((p) => ({ t: p.t, v: p.base == null ? null : p.base / 1000, tip: `Dead reckoning ${when(p.t)}: median miss ${km(p.base)}` }))} />}
                {models.map((s) => (
                  <Series key={s.version} c={c} color={colorOf(v.versions, s.version)} pts={s.points.map((p) => ({ t: p.t, v: p.err == null ? null : p.err / 1000, tip: `${s.version} ${when(p.t)}: median miss ${km(p.err)} vs ${km(p.base)} dead reckoning (n ${p.n})` }))} />
                ))}
              </>
            )}
          </Plot>
          <Keys items={[...models.map((s) => ({ label: s.version, color: colorOf(v.versions, s.version) })), { label: 'dead reckoning', color: 'var(--dvm-text-muted)', dashed: true }]} />
        </>
      )}
    </div>
  )
}

function DarkBlock({ metrics, mode }: { metrics: LabMetrics; mode: Mode }) {
  const series = darkSeries(metrics.godark, mode)
  const pts = series.flatMap((s) => s.points)
  const keys = series.map((s) => s.key)
  const col = (k: string) => COLORS[keys.indexOf(k) % COLORS.length]
  const lo = Math.min(-0.1, ...pts.map((p) => p.brier_skill)), hi = Math.max(0.1, ...pts.map((p) => p.brier_skill))
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
          <p className="ll-muted">Dots on the diagonal are calibrated; below it the model over-warns. Dot size is the number of predictions in the bin.</p>
        </>
      )}
      <h5>Brier skill over the base rate (above 0 beats always guessing the average)</h5>
      {!pts.length ? <p className="ll-muted">No graded go-dark predictions from a model in this window.</p> : (
        <>
          <p className="ll-say">
            {series.map((s, i) => <span key={s.key}>{i > 0 && '; '}{targetName(s.target)} <b>{signedPct(pooledBrierSkill(s))}</b></span>)} over the window.
          </p>
          <Plot label="Go-dark Brier skill per hour" x={[Math.min(...pts.map((p) => p.t)), Math.max(...pts.map((p) => p.t))]} y={[lo, hi]} time yTick={(y) => signedPct(y)}>
            {(c) => (
              <>
                <Ref c={c} v={0} label="no skill" />
                {series.map((s) => <Series key={s.key} c={c} color={col(s.key)} pts={s.points.map((p) => ({ t: p.t, v: p.brier_skill, tip: `${s.key} ${when(p.t)}: Brier skill ${signedPct(p.brier_skill)} (${p.positives} of ${p.n} went dark)` }))} />)}
              </>
            )}
          </Plot>
          <Keys items={series.map((s) => ({ label: `${targetName(s.target)} · ${s.version}`, color: col(s.key) }))} />
        </>
      )}
    </div>
  )
}

const targetName = (t: string) => (/^dark_(\d+)h$/.test(t) ? `dark within ${t.slice(5, -1)} h` : t)

function ReliabilityPlot({ r }: { r: Reliability }) {
  const max = Math.min(1, Math.max(0.05, ...r.bins.flatMap((b) => [b.p_mean, b.hit_rate])) * 1.1)
  const nMax = Math.max(1, ...r.bins.map((b) => b.n))
  return (
    <figure>
      <figcaption>{targetName(r.target)}</figcaption>
      <Plot label={`Reliability, ${targetName(r.target)}`} x={[0, max]} y={[0, max]} height={200} xTick={(v) => pct(v)} yTick={(v) => pct(v)}>
        {(c) => (
          <>
            <line className="ll-diag" x1={c.x(0)} y1={c.y(0)} x2={c.x(max)} y2={c.y(max)} />
            {r.bins.map((b) => (
              <circle key={b.p_mean} className="ll-bin" cx={c.x(b.p_mean)} cy={c.y(b.hit_rate)} r={2 + 7 * Math.sqrt(b.n / nMax)}>
                <title>{`Predicted ${pct(b.p_mean, 1)}, went dark ${pct(b.hit_rate, 1)} (${b.n.toLocaleString('en-GB')} predictions)`}</title>
              </circle>
            ))}
          </>
        )}
      </Plot>
      <p className="ll-axis">x: predicted p · y: share that went dark</p>
    </figure>
  )
}
