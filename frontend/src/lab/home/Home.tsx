import { MODELS, openLab, type LabModel } from '../hash'
import { championSeries, MODEL_INFO, modelSummary, modelView, runsOf, type RichSummary } from '../model'
import { Sparkline } from '../Sparkline'
import { StatusLine } from '../Status'
import { count } from '../format'
import type { Metrics, Proposal, Run, Summary } from '../types'

// The Lab home (#lab): a slim totals strip, then one card per model. A card opens its model page.

export interface HomeProps { summary: Summary | null; runs: Run[] | null; proposals: Proposal[] | null; metrics: Metrics | null }

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
  const series = championSeries(runs, m?.offline.primary_h)
  const total = m?.runs_total ?? runs.length
  const gem = m?.runs_gemini ?? runs.filter((r) => r.proposer === 'gemini').length
  return (
    <button type="button" className="lab-home-card" onClick={() => openLab({ model: target })} aria-label={`${info.name}: ${info.question} Open details`}>
      <span className="lab-home-card__name">{info.name}</span>
      <span className="lab-home-card__q">{info.question}</span>
      <span className="lab-home-card__head">{v.headline.text}</span>
      {v.sub && <span className="lab-home-card__sub">{v.sub}</span>}
      <StatusLine status={v.status} />
      <span className="lab-home-card__foot">
        <Sparkline points={series} label={`${info.name} champions over time`} />
        <span>{total} runs · {gem} by Gemini</span>
      </span>
      <span className="lab-home-card__enter"><span>Explore {info.name.toLowerCase()}</span><span aria-hidden="true">→</span></span>
    </button>
  )
}
