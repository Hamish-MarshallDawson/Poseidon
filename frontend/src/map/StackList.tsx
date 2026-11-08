import { useEffect, useRef } from 'react'
import { ui } from '../store/ui'
import { vessels } from '../store/vessels'
import { openShipWindow } from './actions'

// Minimal fallback for the stack list (a chip of 9+ ships): rows in z-order, anchored to the chip. Hovering a row
// highlights that ship on the map; clicking a row opens its window. The windows agent may replace it
// by rendering `ui.stack` itself.
const MAX_ROWS = 200

export function StackList() {
  const stack = ui.use((s) => s.stack)
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => { if (stack) ref.current?.focus() }, [stack])
  if (!stack) return null
  const rows = stack.mmsis.slice(0, MAX_ROWS)
  const x = Math.min(stack.x + 16, window.innerWidth - 296), y = Math.max(8, Math.min(stack.y - 20, window.innerHeight - 340))
  return (
    <div ref={ref} className="dvm-stack" role="dialog" aria-label={`${stack.mmsis.length} ships at this spot`} tabIndex={-1}
      style={{ transform: `translate(${x}px, ${y}px)` }} onMouseLeave={() => ui.set({ hoverMmsi: null })}>
      <div className="dvm-stack__head">{stack.mmsis.length.toLocaleString('en-GB')} ships here</div>
      <ul className="dvm-stack__list">
        {rows.map((m) => {
          const v = vessels.vessels.get(m)
          return (
            <li key={m}>
              <button type="button" onMouseEnter={() => ui.set({ hoverMmsi: m })} onFocus={() => ui.set({ hoverMmsi: m })}
                onClick={() => { ui.set({ stack: null }); openShipWindow(m) }}>
                <span className="dvm-stack__name">{v?.name ?? 'Unnamed'}</span>
                <span className="dvm-stack__meta">{v?.type_group ?? ''} · {m}</span>
              </button>
            </li>
          )
        })}
      </ul>
      {stack.mmsis.length > MAX_ROWS && <div className="dvm-stack__more">and {stack.mmsis.length - MAX_ROWS} more; zoom in to separate them</div>}
    </div>
  )
}
