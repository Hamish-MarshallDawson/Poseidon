import { ui } from '../store/ui'
import { vessels } from '../store/vessels'
import { showFilter } from './registry'

const KEY = 'poseidon.show'

/** Change the filter: persist it (per viewer) and run the old entry's leave and the new one's enter. */
export function setShow(id: string): void {
  const next = showFilter(id).id, prev = ui.get().show
  if (next === prev) return
  try { localStorage.setItem(KEY, next) } catch { /* private window: the choice just isn't remembered */ }
  ui.set({ show: next })
  showFilter(prev).leave?.()
  showFilter(next).enter?.()
}

/** Start-up: restore the saved choice and run its enter. Unknown or unreadable saved ids mean 'all'. */
export function startShow(): void {
  let id = 'all'
  try { id = showFilter(localStorage.getItem(KEY) ?? 'all').id } catch { /* no storage */ }
  ui.set({ show: id })
  showFilter(id).enter?.()
}

/** Ships known that match the filter (for the status chip). */
export function matchCount(id: string): number {
  const match = showFilter(id).match
  let n = 0
  for (const v of vessels.vessels.values()) if (!match || match(v)) n++
  return n
}
