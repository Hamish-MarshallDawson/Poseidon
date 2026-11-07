import { useEffect } from 'react'
import type { ServerMsg } from '../types'
import { ui } from '../store/ui'
import { vessels } from '../store/vessels'
import type { AdapterOptions, DataAdapter } from './adapter'
import { createLiveAdapter } from './live'
import { createMockAdapter } from './mock'

// Picks the data source. VITE_DATA=live uses the backend alone; anything else (default `mock`) wraps the live feed with
// the labelled mock (session replay + synthetic forecast). Switching to the real backend is this one choice.
const DATA = import.meta.env.VITE_DATA ?? 'mock'

export function createAdapter(opts: AdapterOptions): DataAdapter {
  const live = createLiveAdapter(opts)
  return DATA === 'live' ? live : createMockAdapter(live)
}

// The singleton the UI talks to (send replay/detail, read scores and timeline). Null until useFeed has mounted.
export let adapter: DataAdapter | null = null

type Detail = Extract<ServerMsg, { type: 'detail' }>
const detailListeners = new Set<(d: Detail) => void>()
export function onDetail(cb: (d: Detail) => void): () => void {
  detailListeners.add(cb)
  return () => void detailListeners.delete(cb)
}

// Starts the feed once (call it from the logged-in root) and wires it to the stores.
export function useFeed(getToken: () => Promise<string | undefined>): void {
  useEffect(() => {
    const a = createAdapter({
      wsUrl: import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws',
      httpBase: import.meta.env.VITE_API_URL || 'http://localhost:8000',
      getToken,
    })
    adapter = a
    a.start({
      onFrame: (f) => vessels.applyFrame(f),
      onStatus: (s) => ui.set({ feed: { ...s, isMock: a.isMock } }),
      onDetail: (d) => detailListeners.forEach((l) => l(d)),
    })
    return () => { a.stop(); if (adapter === a) adapter = null }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
}
