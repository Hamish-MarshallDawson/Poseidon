import { useSyncExternalStore } from 'react'

// The Lab is open while the URL hash is #lab.

const HASH = '#lab'
const subscribe = (fn: () => void) => { window.addEventListener('hashchange', fn); return () => window.removeEventListener('hashchange', fn) }
const isOpen = () => location.hash === HASH

export function openLab() { if (!isOpen()) location.hash = HASH }

export function closeLab() {
  if (!isOpen()) return
  history.replaceState(history.state, '', location.pathname + location.search)
  window.dispatchEvent(new HashChangeEvent('hashchange'))
}

export function useLabOpen(): boolean {
  return useSyncExternalStore(subscribe, isOpen, () => false)
}
