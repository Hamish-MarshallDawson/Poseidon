import { useMemo } from 'react'
import { ChampionsTab } from './champions/ChampionsTab'
import { DataTab } from './data/DataTab'
import { LiveTab } from './live/LiveTab'
import { OverviewTab } from './OverviewTab'
import { PipelineStrip } from './PipelineStrip'
import { openLab, TABS, type LabModel, type LabTab } from './hash'
import { eventsOf, MODEL_INFO, modelSummary, pipeline, proposalsOf, runsOf } from './model'
import type { TabModel } from './tabs'
import type { LabData, LabEvent, Metrics, Proposal, Run, RunDetail, Summary } from './types'

// A model page (#lab/<model>[/<tab>]): the pipeline strip, then four tabs. Each tab waits for the data it needs.

export interface ModelPageProps {
  target: LabModel
  tab: LabTab
  summary: Summary | null
  runs: Run[] | null
  proposals: Proposal[] | null
  events: LabEvent[] | null
  metrics: Metrics | null
  data: LabData | null
  loadDetail: (id: string) => Promise<RunDetail | null>
}

const TAB_LABEL: Record<LabTab, string> = { overview: 'Overview', champions: 'Champions & challengers', live: 'Live', data: 'Data' }

export function ModelPage({ target, tab, summary, runs, proposals, events, metrics, data, loadDetail }: ModelPageProps) {
  const model: TabModel = useMemo(() => ({ target, ...MODEL_INFO[target], summary: modelSummary(summary, target) }), [target, summary])
  const mRuns = useMemo(() => runsOf(runs, target), [runs, target])
  const mProps = useMemo(() => proposalsOf(proposals, target), [proposals, target])
  const mEvents = useMemo(() => eventsOf(events, target), [events, target])
  const trainingN = data?.training.filter((r) => r.target === target).sort((a, b) => b.created_at - a.created_at)[0]?.n_train ?? null
  const stages = pipeline(model.summary, mRuns, mProps, mEvents, trainingN)
  const ready = (xs: unknown[]) => xs.every((x) => x != null)
  const loading = <p className="lab-muted" role="status">Loading…</p>
  return (
    <div className="lab-model">
      <div className="lab-model__title">
        <h2>{model.name}</h2>
        <p>{model.question}</p>
      </div>
      {summary && runs ? <PipelineStrip stages={stages} /> : null}
      <div className="lab-tabs" role="tablist" aria-label={`${model.name} views`}>
        {TABS.map((t) => (
          <button key={t} type="button" role="tab" id={`lab-tab-${t}`} aria-selected={t === tab} aria-controls="lab-tabpanel"
            className={t === tab ? 'on' : ''} onClick={() => openLab({ model: target, tab: t })}>{TAB_LABEL[t]}</button>
        ))}
      </div>
      <div className="lab-tabpanel" role="tabpanel" id="lab-tabpanel" aria-labelledby={`lab-tab-${tab}`}>
        {tab === 'overview' && (ready([summary, runs, events, metrics]) ? <OverviewTab model={model} runs={mRuns} events={mEvents} metrics={metrics!} /> : loading)}
        {tab === 'champions' && (ready([summary, runs, proposals, events]) ? <ChampionsTab model={model} runs={mRuns} proposals={mProps} events={mEvents} loadDetail={loadDetail} /> : loading)}
        {tab === 'live' && (ready([summary, metrics]) ? <LiveTab model={model} metrics={metrics!} /> : loading)}
        {tab === 'data' && (ready([summary, data]) ? <DataTab model={model} data={data!} /> : loading)}
      </div>
    </div>
  )
}
