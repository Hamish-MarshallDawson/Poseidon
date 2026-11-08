import type { LabApi, Loaded } from './api'
import type { LabData, LabEvent, Metrics, Proposal, Run, Summary } from './types'

// What Lab.tsx hands each section (improve/, live/, runs/). Each list is null while loading. `sample` is true when
// any of it is the fixtures sample (offline, mock data, or an endpoint failed); the Lab header says so.
// Sections fetch more themselves through `api` (a run's detail, metrics for other hours), and get the same fallback.
export interface LabSectionProps {
  summary: Summary | null
  runs: Run[] | null
  proposals: Proposal[] | null
  events: LabEvent[] | null
  metrics: Metrics | null
  data: LabData | null
  /** Hours the shared `metrics` cover. */
  hours: number
  api: LabApi
  sample: boolean
  /** Epoch ms of the last load; use it as "now" for time axes so fixtures and live data both line up. */
  now: number
}

export type { Loaded }
