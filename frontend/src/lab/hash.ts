import { useSyncExternalStore } from 'react'

// The Lab is open while the URL hash starts with #lab. Routes: #lab (home), #lab/<model> (a model page, Overview tab),
// #lab/<model>/<tab>. No router: the hash is the state, so Back and links work.

export const MODELS = ['route', 'godark', 'fishing'] as const
export type LabModel = (typeof MODELS)[number]
export const TABS = ['overview', 'champions', 'live', 'data'] as const
export type LabTab = (typeof TABS)[number]

export interface LabRoute { model: LabModel | null; tab: LabTab }

const HASH = '#lab'
const subscribe = (fn: () => void) => { window.addEventListener('hashchange', fn); return () => window.removeEventListener('hashchange', fn) }
const isOpen = () => location.hash === HASH || location.hash.startsWith(`${HASH}/`)

export function parseRoute(hash: string): LabRoute {
  const [, m, t] = hash.replace(/^#/, '').split('/')
  const model = (MODELS as readonly string[]).includes(m) ? (m as LabModel) : null
  const tab = model && (TABS as readonly string[]).includes(t) ? (t as LabTab) : 'overview'
  return { model, tab }
}

export function routeHash({ model, tab }: Partial<LabRoute>): string {
  if (!model) return HASH
  return tab && tab !== 'overview' ? `${HASH}/${model}/${tab}` : `${HASH}/${model}`
}

export function openLab(route: Partial<LabRoute> = {}) {
  const h = routeHash(route)
  if (location.hash !== h) location.hash = h
}

export function closeLab() {
  if (!isOpen()) return
  history.replaceState(history.state, '', location.pathname + location.search)
  window.dispatchEvent(new HashChangeEvent('hashchange'))
}

export function useLabOpen(): boolean {
  return useSyncExternalStore(subscribe, isOpen, () => false)
}

const currentHash = () => location.hash
export function useLabRoute(): LabRoute {
  const h = useSyncExternalStore(subscribe, currentHash, () => HASH)
  return parseRoute(h)
}
