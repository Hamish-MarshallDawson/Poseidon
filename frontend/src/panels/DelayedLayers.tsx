import { useEffect, useState } from 'react'
import { adapter } from '../data/index'
import { DELAYED, delayed, setDelayed, type DelayedKey } from '../map/delayed'
import { Switch } from '../ui'

// The three delayed-data layer rows for the Display panel's Layers section: a switch with its label, and the age of
// that source's newest data from GET /sources (plus a note when the 5,000-row cap is hit).
const KEYS = Object.keys(DELAYED) as DelayedKey[]

const age = (s: number) => (s < 3600 ? `${Math.max(1, Math.round(s / 60))} min old` : s < 48 * 3600 ? `${Math.round(s / 3600)} h old` : `${Math.round(s / 86_400)} d old`)

function useAges(): Record<string, number | null> {
  const [ages, setAges] = useState<Record<string, number | null>>({})
  useEffect(() => {
    let live = true
    const load = () => adapter?.sources?.().then((r) => live && setAges(Object.fromEntries(r.sources.map((s) => [s.src, s.age_s]))), () => {})
    void load()
    const id = window.setInterval(load, 5 * 60_000)
    return () => { live = false; window.clearInterval(id) }
  }, [])
  return ages
}

export function DelayedLayers() {
  const on = delayed.use((s) => s.on)
  const notes = delayed.use((s) => s.notes)
  const ages = useAges()
  return (
    <>
      {KEYS.map((k) => {
        const a = ages[DELAYED[k].src]
        const hint = [a != null && age(a), on[k] && notes[k]].filter(Boolean).join(' · ')
        return <Switch key={k} checked={on[k]} label={DELAYED[k].label} hint={hint || undefined} onChange={(v) => setDelayed(k, v)} />
      })}
    </>
  )
}
