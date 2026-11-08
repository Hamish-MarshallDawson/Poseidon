import { useEffect, useState } from 'react'
import { getTrack } from '../data/track'
import { buildIndex, inferDeparture } from './match'
import type { PortIndex, PortRow, Port } from './match'

export { fmtEta, matchDestination, nearestPort } from './match'
export type { Port, PortIndex }

// The port list (public/ports/ports.json, ~250 KB) is fetched the first time a ship window needs it.
let index: Promise<PortIndex> | undefined
export function loadPorts(): Promise<PortIndex> {
  index ??= fetch(`${import.meta.env.BASE_URL}ports/ports.json`)
    .then((r) => { if (!r.ok) throw new Error(`ports ${r.status}`); return r.json() as Promise<PortRow[]> })
    .then(buildIndex)
  index.catch(() => { index = undefined })
  return index
}

export type Departure = 'loading' | 'error' | { port: Port; leftTs: number } | null

// Ports plus the inferred departure for one open ship window. `ports` is null until loaded or if it failed.
export function usePortInfo(mmsi: number): { ports: PortIndex | null; departure: Departure } {
  const [ports, setPorts] = useState<PortIndex | null>(null)
  const [res, setRes] = useState<{ mmsi: number; d: Departure }>({ mmsi, d: 'loading' })
  useEffect(() => {
    let live = true
    loadPorts().then((idx) => {
      if (!live) return
      setPorts(idx)
      return getTrack(mmsi, 24).then((t) => live && setRes({ mmsi, d: inferDeparture(t, idx) }))
    }).catch(() => live && setRes({ mmsi, d: 'error' }))
    return () => { live = false }
  }, [mmsi])
  return { ports, departure: res.mmsi === mmsi ? res.d : 'loading' }
}
