import { useState } from 'react'
import { championRun, championSeries, godarkLive, heldOut, modelView, routeLive, type RichSummary } from './model'
import { Chart, Legend, Markers, RefLine, Step, extent, pad, timeFull } from './charts'
import { StatusLine } from './Status'
import { day, horizon, proposerLabel, when } from './format'
import type { OverviewTabProps } from './tabs'

// Overview tab: the champion, three key numbers, and the champion's held-out number over time.
export function OverviewTab({ model, runs, metrics }: OverviewTabProps) {
  const m = model.summary
  if (!m) return <p className="lab-empty">No {model.name.toLowerCase()} model trained yet. Runs appear here once the first one is judged.</p>
  const v = modelView(model.target, m, runs, metrics)
  const champ = championRun(m, runs)
  const series = championSeries(runs, m.offline.primary_h)
  return (
    <div className="lab-ov">
      <section className="lab-ov__hero">
        <p className="lab-ov__head">{v.headline.text}</p>
        {v.sub && <p className="lab-ov__sub">{v.sub}</p>}
        <StatusLine status={v.status} />
        <p className="lab-muted">Champion <code>{m.champion.version}</code> · since {m.champion.since ? when(m.champion.since) : 'unknown'} · {proposerLabel(m.champion.proposer)}</p>
      </section>
      <dl className="lab-ov__nums">{keyNumbers(model.target, m, champ, metrics).map((k) => (
        <div key={k.label}><dd>{k.value}</dd><dt>{k.label}</dt></div>
      ))}</dl>
      <ChampionChart target={model.target} name={model.name} series={series} metrics={metrics} champion={m.champion.version} h={m.offline.primary_h}
        sameStat={!!m.live?.offline && m.live.statistic === m.offline.statistic && m.live.horizon_s === m.offline.primary_h} />
    </div>
  )
}

function keyNumbers(target: string, m: NonNullable<OverviewTabProps['model']['summary']>, champ: ReturnType<typeof championRun>, metrics: OverviewTabProps['metrics']) {
  const pct = (x: number | null | undefined) => (x == null ? '–' : x > 0 && x < 0.1 ? `${(x * 100).toFixed(1)}%` : `${Math.round(x * 100)}%`)
  const hv = (unit: string) => (m as RichSummary).headline?.unit === unit ? (m as RichSummary).headline?.value ?? null : null
  const graded = { label: 'graded live, 24 h', value: m.live ? m.live.n.toLocaleString('en-GB') : '–' }
  if (target === 'route') {
    const r = routeLive(metrics, m.champion.version)
    return [
      { label: 'typical miss after 3 h', value: hv('km') != null ? `${hv('km')} km` : r.errM == null ? '–' : `${r.errM >= 10_000 ? Math.round(r.errM / 1000) : (r.errM / 1000).toFixed(1)} km` },
      { label: 'circle held the ship · target 80%', value: pct(r.cov80) },
      graded,
    ]
  }
  if (target === 'godark') {
    const g = godarkLive(metrics, m.champion.version)
    return [
      { label: 'more likely to go dark when flagged', value: hv('×') != null ? `${hv('×')}×` : g.lift == null ? '–' : `${g.lift.toFixed(1)}×` },
      { label: 'says vs actual', value: g.said == null || g.actual == null ? '–' : `${pct(g.said)} / ${pct(g.actual)}` },
      graded,
    ]
  }
  const ho = heldOut(champ, m.offline.primary_h)
  return [
    { label: ho.recall != null ? 'fishing weeks spotted' : 'ranked correctly', value: ho.recall != null ? `${Math.round(ho.recall * 10)} in 10` : ho.aucPr != null ? `${Math.round(ho.aucPr * 10)} in 10` : '–' },
    { label: 'held-out weeks tested', value: ho.n == null ? '–' : ho.n.toLocaleString('en-GB') },
    graded,
  ]
}

const VS: Record<string, string> = { route: 'a straight-line guess', godark: 'guessing the average rate', fishing: 'the usual rate for that kind of boat' }

/** The champion's held-out number over time as steps (higher is better), with the live hourly figure as dots when the
 *  live figure is the same measure at the same horizon (route); never two measures on one axis. */
function ChampionChart({ target, name, series, metrics, champion, h, sameStat }: { target: string; name: string; series: { t: number; v: number }[]; metrics: OverviewTabProps['metrics']; champion: string; h: number; sameStat: boolean }) {
  const [now] = useState(() => Date.now())
  if (!series.length) return <p className="lab-empty">No champion history recorded yet.</p>
  const live = sameStat && target === 'route'
    ? metrics.route.filter((r) => r.horizon_s === h && (r.mode ?? 'live') === 'live' && r.n > 0 && (r.model_version === champion || champion.replace(/-cal\d+$/, '') === r.model_version)
        && r.median_err_m != null && r.baseline_median_err_m)
        .map((r) => ({ x: r.t, y: 1 - r.median_err_m! / r.baseline_median_err_m!, n: r.n }))
    : []
  const xs = [...series.map((p) => p.t), ...live.map((p) => p.x), now]
  const xd = pad(extent(xs), 0.04)
  const yd = pad(extent([0, ...series.map((p) => p.v), ...live.map((p) => p.y)]), 0.1)
  const vs = VS[target] ?? 'the simple guess'
  return (
    <figure className="lab-ov__chart">
      <Chart label={`${name}: how much better than ${vs} each champion was, over time`} height={220}
        x={{ type: 'time', domain: xd }} y={{ domain: yd, percent: true, ticks: 4 }}>
        <RefLine y={0} label="no better than the simple guess" />
        <Step data={series.map((p) => ({ x: p.t, y: p.v }))} until={now} tone="ink" dots label="champion on the frozen test"
          tip={(d) => <><b>{Math.round((d.y ?? 0) * 100)}% better</b> than {vs} at {horizon(h)} · {timeFull(d.x)}</>} />
        {live.length > 0 && <Markers data={live.map((p) => ({ ...p, tone: 'accent' as const }))} size={3} label="live hour"
          tip={(d) => <><b>Live: {Math.round(d.y * 100)}% better</b> than {vs} · {d.n} ships · {timeFull(d.x)}</>} />}
      </Chart>
      <figcaption>
        <Legend items={[
          { label: 'champion on the frozen test', tone: 'ink', kind: 'line' },
          ...(live.length ? [{ label: 'live, each hour', tone: 'accent' as const, kind: 'circle' as const }] : []),
        ]} />
        <span className="lab-muted">% better than {vs} at {horizon(h)}; higher is better. {day(series[0].t)} to now.</span>
      </figcaption>
    </figure>
  )
}
