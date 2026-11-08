import { championRun, championSeries, godarkLive, heldOut, modelView, routeLive } from './model'
import { Sparkline } from './Sparkline'
import { StatusLine } from './Status'
import { day, proposerLabel, when } from './format'
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
      <figure className="lab-ov__chart">
        <Sparkline points={series} width={640} height={120} label={`${model.name} champion over time`} />
        <figcaption className="lab-muted">{series.length ? `Each point is a champion, ${day(series[0].t)} to ${day(series[series.length - 1].t)}: higher is better.` : 'No champion history recorded yet.'}</figcaption>
      </figure>
    </div>
  )
}

function keyNumbers(target: string, m: NonNullable<OverviewTabProps['model']['summary']>, champ: ReturnType<typeof championRun>, metrics: OverviewTabProps['metrics']) {
  const pct = (x: number | null | undefined) => (x == null ? '–' : `${Math.round(x * 100)}%`)
  const graded = { label: 'graded live, 24 h', value: m.live ? m.live.n.toLocaleString('en-GB') : '–' }
  if (target === 'route') {
    const r = routeLive(metrics, m.champion.version)
    return [
      { label: 'typical miss after 3 h', value: r.errM == null ? '–' : `${(r.errM / 1000).toFixed(1)} km` },
      { label: 'circle held the ship · target 80%', value: pct(r.cov80) },
      graded,
    ]
  }
  if (target === 'godark') {
    const g = godarkLive(metrics, m.champion.version)
    return [
      { label: 'more likely to go dark when flagged', value: g.lift == null ? '–' : `${g.lift.toFixed(1)}×` },
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
