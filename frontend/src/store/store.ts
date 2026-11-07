import { useSyncExternalStore } from 'react'

// The one store primitive for UI state. Small on purpose: get, set (merge), subscribe, and a React hook with a
// selector so components re-render only when the slice they read changes. Hot data (25k ship positions) never
// goes through here; it lives in VesselStore and typed arrays and is drawn straight to the map.
export interface Store<T extends object> {
  get(): T
  set(patch: Partial<T> | ((prev: T) => Partial<T>)): void
  subscribe(listener: (state: T, prev: T) => void): () => void
  use<S>(selector: (state: T) => S): S
}

export function createStore<T extends object>(initial: T): Store<T> {
  let state = initial
  const listeners = new Set<(state: T, prev: T) => void>()
  const store: Store<T> = {
    get: () => state,
    set(patch) {
      const prev = state
      const next = { ...prev, ...(typeof patch === 'function' ? patch(prev) : patch) }
      let changed = false
      for (const k in next) if (next[k] !== prev[k]) { changed = true; break }
      if (!changed) return
      state = next
      for (const l of listeners) l(state, prev)
    },
    subscribe(listener) {
      listeners.add(listener)
      return () => void listeners.delete(listener)
    },
    use(selector) {
      // useSyncExternalStore needs a stable snapshot per state; selectors must return stable refs or primitives.
      return useSyncExternalStore((cb) => store.subscribe(cb), () => selector(state), () => selector(state))
    },
  }
  return store
}
