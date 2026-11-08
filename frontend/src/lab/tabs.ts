import type { LabModel } from './hash'
import type { LabData, LabEvent, Metrics, ModelSummary, Proposal, Run, RunDetail } from './types'

// The props each model-page tab gets (Lab.tsx mounts them in its slots). Every list is already filtered to the page's
// model and is never null: the model page shows "Loading…" until the data a tab needs has arrived. `summary` is null
// when /lab/summary has no row for the model (nothing trained or graded yet): show an honest empty state.
// Slots: champions/ChampionsTab.tsx (lab2-champions), live/LiveTab.tsx and data/DataTab.tsx (lab2-live),
// OverviewTab.tsx (lab2-nav). Replace the stubs in place; keep the export names and these props.
// Escape: Lab.tsx returns home on Escape unless the event is defaultPrevented, so a side panel that closes on Escape
// should call e.preventDefault() (listen on window in the capture phase, or on the panel).

export interface TabModel {
  /** 'route' | 'godark' | 'fishing' */
  target: LabModel
  /** "Route", "Go-dark", "Fishing" */
  name: string
  /** The plain question the model answers: "Where is a silent ship now?" */
  question: string
  summary: ModelSummary | null
}

export interface ChampionsTabProps {
  model: TabModel
  /** This model's runs, newest first. */
  runs: Run[]
  proposals: Proposal[]
  events: LabEvent[]
  /** GET /lab/runs/{id}: the run side panel's detail (null when unknown). */
  loadDetail: (runId: string) => Promise<RunDetail | null>
}

/** `metrics` is the full /lab/metrics response (last 24 h, hourly); filter rows by model.target yourself
 *  (route rows for route; godark rows whose target starts with dark_ for godark; fishing has none yet). */
export interface LiveTabProps { model: TabModel; metrics: Metrics }

/** `data` is the full /lab/data response; training/holdouts rows carry a target. */
export interface DataTabProps { model: TabModel; data: LabData }

export interface OverviewTabProps { model: TabModel; runs: Run[]; events: LabEvent[]; metrics: Metrics }
