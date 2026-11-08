import { memo, useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { ui, type ShipWindow } from '../store/ui'
import { springs, useDrag, useSpring } from '../motion'
import { bringToFront, closeShipWindow, moveShipWindow, openOrigins, setMinimised, shipScreenPoint } from './open'
import { clampToViewport, dockSlot } from './place'
import { ShipCard } from './ShipCard'
import { useVessel } from './hooks'
import { TYPE_LABEL, fmtMmsi } from './format'
import { scheduleLeader, windowGeom } from './leaderBus'
import dragHandle from './assets/drag-handle.svg'

// R2/Dashboard/Ship window (Figma 66:21898): open, dragging (lifted), minimised (pill), closed (gone).
// Position, scale and opacity are springs on transform/opacity; nothing animates top/left/width/height.

const ShipWindowView = memo(function ShipWindowView({ w, slot, exiting, onExited }: {
  w: ShipWindow; slot: number | null; exiting: boolean; onExited: (mmsi: number) => void
}) {
  const v = useVessel(w.mmsi)
  const name = v?.name ?? `MMSI ${fmtMmsi(w.mmsi)}`
  const elRef = useRef<HTMLElement>(null)
  const origin = openOrigins.get(w.mmsi)
  const spring = useSpring({ x: w.x, y: w.y, scale: origin ? 0.2 : 0.96, opacity: 0 }, springs.window)
  const [vh, setVh] = useState(innerHeight)
  const target = slot !== null ? dockSlot(slot, vh) : { x: w.x, y: w.y }
  const titleId = `sw-title-${w.mmsi}`

  // Grow from the ship on open; follow store moves (restore, minimise, resize clamp) with the spring.
  useLayoutEffect(() => {
    const el = elRef.current!
    if (exiting) {
      const ship = shipScreenPoint(w.mmsi)
      if (ship && slot === null) el.style.transformOrigin = `${ship.x - spring.pos.x}px ${ship.y - spring.pos.y}px`
      spring.to({ scale: 0.2, opacity: 0 }, { config: springs.window, onRest: () => onExited(w.mmsi) })
      return
    }
    el.style.transformOrigin = origin && slot === null ? `${origin.x - w.x}px ${origin.y - w.y}px` : '0 0'
    openOrigins.delete(w.mmsi)
    spring.to({ ...target, scale: 1, opacity: 1 }, { config: springs.window })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [target.x, target.y, exiting])

  // Register for the leader lines: the spring for position, the element size from a ResizeObserver.
  useEffect(() => {
    const el = elRef.current!
    const geom = { spring, w: el.offsetWidth, h: el.offsetHeight }
    windowGeom.set(w.mmsi, geom)
    spring.onChange = scheduleLeader
    const ro = new ResizeObserver(() => {
      geom.w = el.offsetWidth; geom.h = el.offsetHeight; scheduleLeader()
      const sc = el.querySelector('.sc')
      el.classList.toggle('sw-scroll', !!sc && sc.scrollHeight > sc.clientHeight + 1)
      // A card that grew (more rows) must not reach into the scrub bar band: slide it up.
      const cur = ui.get().windows.find((x) => x.mmsi === w.mmsi)
      if (!cur || cur.minimised) return
      const p = clampToViewport(cur, innerWidth, innerHeight, geom.w, geom.h)
      if (p.y !== cur.y) moveShipWindow(w.mmsi, cur.x, p.y)
    })
    ro.observe(el)
    const onResize = () => setVh(innerHeight)
    addEventListener('resize', onResize)
    return () => {
      ro.disconnect()
      removeEventListener('resize', onResize)
      if (windowGeom.get(w.mmsi) === geom) windowGeom.delete(w.mmsi)
      spring.onChange = null
      scheduleLeader()
    }
  }, [spring, w.mmsi])

  const start = useRef({ x: 0, y: 0 })
  const onDragStart = useDrag({
    onStart(e) {
      if ((e.target as Element).closest('button') || slot !== null) return false
      const el = elRef.current!
      start.current = { x: spring.pos.x, y: spring.pos.y }
      el.dataset.lifted = 'true'
      spring.to({ scale: 1.01 }, { config: springs.settle })
    },
    onMove(dx, dy) {
      const el = elRef.current!
      spring.jump(clampToViewport({ x: start.current.x + dx, y: start.current.y + dy }, innerWidth, innerHeight, el.offsetWidth, el.offsetHeight))
    },
    onEnd() {
      delete elRef.current!.dataset.lifted
      spring.to({ scale: 1 }, { config: springs.settle })
      moveShipWindow(w.mmsi, spring.pos.x, spring.pos.y)
    },
  })

  const hover = (on: boolean) => ui.set((s) => ({ hoverMmsi: on ? w.mmsi : s.hoverMmsi === w.mmsi ? null : s.hoverMmsi }))
  const focus = () => ui.set({ focusMmsi: w.mmsi })

  return (
    <section
      ref={(el) => { elRef.current = el; spring.attach(el) }}
      className={`sw ${slot !== null ? 'sw-pill' : ''}`}
      role="dialog"
      aria-modal="false"
      aria-labelledby={titleId}
      data-mmsi={w.mmsi}
      inert={exiting || undefined}
      style={{ zIndex: w.z }}
      onPointerDownCapture={() => bringToFront(w.mmsi)}
      onFocusCapture={() => bringToFront(w.mmsi)}
      onPointerEnter={() => hover(true)}
      onPointerLeave={() => hover(false)}
    >
      <header className="sw-bar" onPointerDown={onDragStart} onDoubleClick={slot === null ? focus : undefined}
        title={slot === null ? 'Drag to move · double-click to focus' : undefined}>
        <img className="sw-handle" src={dragHandle} width={8} height={14} alt="" />
        <span className="badge" aria-label={`Window ${w.letter}`}>{w.letter}</span>
        {slot !== null ? (
          <button type="button" className="sw-pillname" id={titleId} onClick={() => setMinimised(w.mmsi, false)}>{name}</button>
        ) : (
          <span className="sw-title">
            <span className="sw-name" id={titleId}>{name}</span>
            {v && <span className="sw-type">{TYPE_LABEL[v.type_group]}</span>}
          </span>
        )}
        {slot !== null ? (
          <button type="button" className="sw-btn" aria-label={`Restore ${name}`} onClick={() => setMinimised(w.mmsi, false)}>▢</button>
        ) : (
          <button type="button" className="sw-btn" aria-label={`Minimise ${name}`} onClick={() => setMinimised(w.mmsi, true)}>–</button>
        )}
        <button type="button" className="sw-btn" aria-label={`Close ${name}`} onClick={() => closeShipWindow(w.mmsi)}>×</button>
      </header>
      {slot === null && <ShipCard mmsi={w.mmsi} onFocus={focus} />}
    </section>
  )
})

// Renders ui.windows, plus closed windows until their exit animation ends.
export function WindowLayer() {
  const windows = ui.use((s) => s.windows)
  // Derived during render (not in an effect) so a closed window is never unmounted for a frame.
  const [state, setState] = useState({ prev: windows, exiting: [] as ShipWindow[] })
  let exiting = state.exiting
  if (state.prev !== windows) {
    const gone = state.prev.filter((p) => !windows.some((w) => w.mmsi === p.mmsi))
    exiting = [...exiting.filter((e) => !windows.some((w) => w.mmsi === e.mmsi)), ...gone]
    setState({ prev: windows, exiting })
  }
  const onExited = useCallback((mmsi: number) => setState((s) => ({ ...s, exiting: s.exiting.filter((e) => e.mmsi !== mmsi) })), [])

  // Same key for a window while it exits, so the instance (and its spring) carries the close animation.
  const all = [...windows, ...exiting.filter((e) => !windows.some((w) => w.mmsi === e.mmsi))]
  let slot = 0
  const slots = new Map(all.filter((w) => w.minimised).map((w) => [w.mmsi, slot++]))
  return (
    <div className="sw-layer">
      {all.map((w) => (
        <ShipWindowView key={w.mmsi} w={w} slot={slots.get(w.mmsi) ?? null} exiting={!windows.includes(w)} onExited={onExited} />
      ))}
    </div>
  )
}
