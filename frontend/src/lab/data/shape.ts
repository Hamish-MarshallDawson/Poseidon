// Data tab counters (pure; tested in shape.test.ts).
import type { LabData, Target } from '../types'
import { outcomeSeries, sourceSpans } from '../live/shape'

export interface DataCounters { graded: number | null; training: number | null; oldest: number | null; depth: string | null }

/** "3.2 years", "45 days", "6 hours" from a span in ms. */
export function depthLabel(ms: number): string {
  const d = ms / 86_400_000
  if (d >= 365) return `${(d / 365.25).toFixed(1)} years`
  if (d >= 2) return `${Math.round(d)} days`
  return `${Math.max(1, Math.round(ms / 3_600_000))} hours`
}

export function dataCounters(data: LabData, target: Target, now = Date.now()): DataCounters {
  const outs = outcomeSeries(data.outcomes)
  const graded = outs.length ? outs.reduce((a, s) => a + (s.points.at(-1)?.cumulative ?? 0), 0) : null
  const runs = data.training.filter((t) => t.n_train != null && t.target === target).sort((a, b) => b.created_at - a.created_at)
  const spans = sourceSpans(data.sources)
  const oldest = spans.length ? spans[0].oldest : null
  return { graded, training: runs[0]?.n_train ?? null, oldest, depth: oldest == null ? null : depthLabel(now - oldest) }
}
