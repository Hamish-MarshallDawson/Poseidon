import { MODELS, openLab, type LabModel } from '../hash'
import { championSeries, MODEL_INFO, modelSummary, modelView, runsOf, type RichSummary } from '../model'
import { Sparkline } from '../Sparkline'
import { count } from '../format'
import type { Metrics, Proposal, Run, Summary } from '../types'

// The Lab home (#lab): three full-width sections, one per model: what it predicts, then how well it does, as numbers.

export interface HomeProps { summary: Summary | null; runs: Run[] | null; proposals: Proposal[] | null; metrics: Metrics | null }

type Level = 'ok' | 'warn' | 'bad' | 'none'
interface Stat { value: string; label: string; level?: Level }

const pct = (x: number | null | undefined) => (x == null ? null : `${Math.round(x * 100)}%`)
const pct1 = (x: number | null | undefined) => (x == null ? null : `${(x * 100).toFixed(x < 0.1 ? 1 : 0)}%`)

/** The numbers each section leads with: how well the model does, from the live ledger (or the frozen test). */
export function statsFor(target: LabModel, m: RichSummary | null): Stat[] {
  if (!m) return []
  const live = m.live
  const lvl = (m.status?.level ?? 'none') as Level
  const out: Stat[] = []
  if (target === 'route') {
    if (m.headline?.value != null) out.push({ value: `${m.headline.value} km`, label: 'typical miss after 3 h' })
    if (live?.calibration?.value != null) out.push({ value: pct(live.calibration.value)!, label: `inside the 80% circle · target 80%`, level: lvl })
    if (live?.primary?.value != null) out.push({ value: `${live.primary.value > 0 ? '+' : ''}${pct(live.primary.value)}`, label: 'closer than a straight line' })
  } else if (target === 'godark') {
    if (m.headline?.value != null) out.push({ value: `${m.headline.value}×`, label: 'flagged ships go dark more often' })
    if (live?.calibration?.value != null) out.push({ value: `${pct1(live.calibration.value)} / ${pct1(live.calibration.nominal)}`, label: 'predicted / actual', level: lvl })
  } else {
    if (m.headline?.value != null) out.push({ value: `${m.headline.value} in 10`, label: 'ranked correctly on held-out weeks' })
    if (m.offline?.skill != null) out.push({ value: `+${pct(m.offline.skill)}`, label: 'better than gear and flag alone' })
  }
  if (live?.n) out.push({ value: count(live.n), label: 'graded in the last 24 h' })
  return out
}

export function Home({ summary, runs, proposals, metrics }: HomeProps) {
  if (!summary) return <p className="lab-muted" role="status">Loading the models…</p>
  const t = summary.totals
  const gemini = (proposals ?? []).filter((p) => p.proposer === 'gemini').length
  return (
    <>
      <dl className="lab-strip-totals" aria-label="Totals">
        <div><dd>{count(t.runs)}</dd><dt>training runs</dt></div>
        <div><dd>{count(proposals ? gemini : t.proposals)}</dd><dt>Gemini proposals</dt></div>
        <div><dd>{t.graded_outcomes_estimated ? '~' : ''}{count(t.graded_outcomes)}</dd><dt>graded predictions <span>+{count(t.graded_last_hour)} last hour</span></dt></div>
      </dl>
      <div className="lab-home-cards">
        {MODELS.map((m) => <HomeCard key={m} target={m} m={modelSummary(summary, m)} runs={runsOf(runs, m)} metrics={metrics} />)}
      </div>
    </>
  )
}

function HomeCard({ target, m, runs, metrics }: { target: LabModel; m: RichSummary | null; runs: Run[]; metrics: Metrics | null }) {
  const info = MODEL_INFO[target]
  const v = modelView(target, m, runs, metrics)
  const stats = statsFor(target, m)
  const series = championSeries(runs, m?.offline.primary_h)
  const total = m?.runs_total ?? runs.length
  const gem = m?.runs_gemini ?? runs.filter((r) => r.proposer === 'gemini').length
  return (
    <button type="button" className="lab-home-card" onClick={() => openLab({ model: target })} aria-label={`${info.question}. Open ${info.name}`}>
      <span className="lab-home-card__name">{info.name}</span>
      <span className="lab-home-card__q">{info.question}</span>
      <span className="lab-home-card__stats">
        {stats.length ? stats.map((s) => (
          <span key={s.label} className={`lab-home-stat${s.level ? ` lab-home-stat--${s.level}` : ''}`}>
            <span className="lab-home-stat__v">{s.value}</span>
            <span className="lab-home-stat__l">{s.label}</span>
          </span>
        )) : <span className="lab-home-stat"><span className="lab-home-stat__l">{v.status.text}</span></span>}
      </span>
      {m?.status?.level === 'none' && <span className="lab-home-card__note">{v.status.text}</span>}
      <span className="lab-home-card__foot">
        <Sparkline points={series} label={`${info.name} champions over time`} />
        <span>{total} runs · {gem} by Gemini</span>
      </span>
      <span className="lab-home-card__enter"><span>Open {info.name.toLowerCase()}</span><span aria-hidden="true">→</span></span>
    </button>
  )
}
