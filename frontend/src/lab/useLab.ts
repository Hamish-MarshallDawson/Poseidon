import { useCallback, useEffect, useRef, useState } from 'react'
import { lab } from './api'
import type { LabSectionProps } from './sections'

// Loads every Lab endpoint once on open and every minute after; each falls back to the fixtures on its own.

export const HOURS = 24
const REFRESH_MS = 60_000

type State = Omit<LabSectionProps, 'api' | 'hours'> & { errors: string[] }

const EMPTY: State = { summary: null, runs: null, proposals: null, events: null, metrics: null, data: null, sample: false, now: Date.now(), errors: [] }

export function useLab(): State & { reload: () => void } {
  const [s, setS] = useState<State>(EMPTY)
  const alive = useRef(true)
  const load = useCallback(async () => {
    const [summary, runs, proposals, events, metrics, data] = await Promise.all([
      lab.summary(), lab.runs(), lab.proposals(), lab.events(), lab.metrics(HOURS), lab.data(),
    ])
    if (!alive.current) return
    const all = [summary, runs, proposals, events, metrics, data]
    setS({
      summary: summary.value, runs: runs.value, proposals: proposals.value, events: events.value, metrics: metrics.value, data: data.value,
      sample: all.some((r) => r.sample),
      // On the sample, "now" is when the fixtures were written, so their 24 h windows still line up.
      now: summary.sample ? summary.value.generated_at : Date.now(),
      errors: all.flatMap((r) => (r.error ? [r.error] : [])),
    })
  }, [])
  useEffect(() => {
    alive.current = true
    void load()
    const id = window.setInterval(() => void load(), REFRESH_MS)
    return () => { alive.current = false; window.clearInterval(id) }
  }, [load])
  return { ...s, reload: () => void load() }
}
