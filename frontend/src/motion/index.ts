import { themeStore } from '../theme/theme'
import { useCallback, useLayoutEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from 'react'

// The shared animation system: hand-rolled springs on one requestAnimationFrame loop. Only transform
// (translate3d + scale) and opacity are ever written, so every animation stays on the compositor.
// Chosen over the `motion` library (about 30 KB gz for motion/react) because we need four primitives, not a framework.

export interface SpringConfig { stiffness: number; damping: number }
export const springs = {
  window: { stiffness: 420, damping: 34 },   // open, close, minimise, restore: quick, one soft overshoot
  drop: { stiffness: 520, damping: 42 },     // panels dropping in: no overshoot
  settle: { stiffness: 700, damping: 40 },   // the lift and settle around a drag
} satisfies Record<string, SpringConfig>

// Reduced motion: every spring jumps straight to its target. The theme store resolves the user's Display-menu pick
// over the system prefers-reduced-motion setting, so both turn it on.
export function reducedMotion(): boolean {
  return themeStore.get().reducedMotion
}

// One rAF loop for every spring, drag and overlay. A tick returns true to keep running.
type Tick = (now: number, dt: number) => boolean
const ticks = new Set<Tick>()
let raf = 0
let last = 0
function loop(now: number) {
  const dt = Math.min(0.064, Math.max(0, (now - last) / 1000))
  last = now
  for (const t of ticks) if (!t(now, dt)) ticks.delete(t)
  raf = ticks.size ? requestAnimationFrame(loop) : 0
}
export function onFrame(tick: Tick): () => void {
  ticks.add(tick)
  if (!raf) {
    last = performance.now()
    raf = requestAnimationFrame(loop)
  }
  return () => void ticks.delete(tick)
}

export interface Pose { x: number; y: number; scale: number; opacity: number }
const KEYS = ['x', 'y', 'scale', 'opacity'] as const
const REST: Pose = { x: 0.05, y: 0.05, scale: 0.0005, opacity: 0.002 }   // per key: close enough to stop
const STEP = 1 / 240                                                   // fixed substep keeps stiff springs stable

// Animates one element's pose. Writes `transform` and `opacity` inline, nothing else.
export class SpringStyle {
  pos: Pose
  target: Pose
  private vel: Pose = { x: 0, y: 0, scale: 0, opacity: 0 }
  private el: HTMLElement | SVGElement | null = null
  private running = false
  private onRest: (() => void) | null = null
  onChange: (() => void) | null = null      // called after every write (the leader lines follow windows with it)
  config: SpringConfig

  constructor(initial: Partial<Pose>, config: SpringConfig = springs.window) {
    this.pos = { x: 0, y: 0, scale: 1, opacity: 1, ...initial }
    this.target = { ...this.pos }
    this.config = config
  }

  attach = (el: HTMLElement | SVGElement | null) => {
    this.el = el
    if (el) this.write()
  }

  // Spring towards `target`. `onRest` runs once when it settles (or at once with reduced motion).
  to(target: Partial<Pose>, opts: { config?: SpringConfig; onRest?: () => void } = {}) {
    Object.assign(this.target, target)
    if (opts.config) this.config = opts.config
    this.onRest = opts.onRest ?? null
    if (reducedMotion()) return this.jump(this.target)
    if (!this.running) {
      this.running = true
      onFrame(this.step)
    }
  }

  // Set keys immediately with no velocity (drag follows the pointer 1:1). Other keys keep animating.
  jump(values: Partial<Pose>) {
    for (const k of KEYS) {
      const v = values[k]
      if (v === undefined) continue
      this.pos[k] = v
      this.target[k] = v
      this.vel[k] = 0
    }
    this.write()
    if (!this.running) this.finish()
  }

  private finish() {
    const done = this.onRest
    this.onRest = null
    done?.()
  }

  private step = (_now: number, dt: number): boolean => {
    const { stiffness, damping } = this.config
    for (let t = 0; t < dt; t += STEP) {
      const h = Math.min(STEP, dt - t)
      for (const k of KEYS) {
        const a = -stiffness * (this.pos[k] - this.target[k]) - damping * this.vel[k]
        this.vel[k] += a * h
        this.pos[k] += this.vel[k] * h
      }
    }
    let resting = true
    for (const k of KEYS) {
      if (Math.abs(this.pos[k] - this.target[k]) > REST[k] || Math.abs(this.vel[k]) > REST[k] * 10) resting = false
    }
    if (resting) {
      Object.assign(this.pos, this.target)
      this.vel = { x: 0, y: 0, scale: 0, opacity: 0 }
    }
    this.write()
    if (resting) {
      this.running = false
      this.finish()
    }
    return !resting
  }

  write() {
    const { x, y, scale, opacity } = this.pos
    if (this.el) {
      this.el.style.transform = `translate3d(${x}px, ${y}px, 0) scale(${scale})`
      this.el.style.opacity = String(Math.min(1, Math.max(0, opacity)))
    }
    this.onChange?.()
  }
}

// A spring owned by a component. Pass `ref` to the element; the controller is stable for the component's life.
export function useSpring(initial: Partial<Pose>, config?: SpringConfig): SpringStyle {
  const [spring] = useState(() => new SpringStyle(initial, config))
  return spring
}

// Mount/unmount with an animation: mounted while shown or while the exit animation runs.
// `hidden` is the pose it enters from and leaves to; the shown pose is the identity.
export function usePresence(show: boolean, hidden: Partial<Pose>, config: SpringConfig = springs.drop) {
  const [mounted, setMounted] = useState(show)
  const spring = useSpring({ x: 0, y: 0, scale: 1, opacity: 0, ...hidden }, config)
  const [hiddenPose] = useState(hidden)   // fixed for the component's life
  if (show && !mounted) setMounted(true)
  useLayoutEffect(() => {
    if (show && mounted) spring.to({ x: 0, y: 0, scale: 1, opacity: 1 })
    else if (!show && mounted) spring.to({ opacity: 0, ...hiddenPose }, { onRest: () => setMounted(false) })
  }, [show, mounted, spring, hiddenPose])
  return { mounted, attach: spring.attach }
}

// Pointer-captured drag, batched to one callback per frame. No inertia: the caller springs to rest on end.
// onStart returns false to refuse (e.g. the press landed on a button).
export interface DragHandlers {
  onStart?(e: ReactPointerEvent): boolean | void
  onMove(dx: number, dy: number): void
  onEnd?(dx: number, dy: number): void
}
export function useDrag(handlers: DragHandlers) {
  const ref = useRef(handlers)
  useLayoutEffect(() => { ref.current = handlers })
  return useCallback((e: ReactPointerEvent) => {
    if (e.button !== 0 || ref.current.onStart?.(e) === false) return
    const el = e.currentTarget as Element
    const id = e.pointerId
    el.setPointerCapture(id)
    const x0 = e.clientX
    const y0 = e.clientY
    let dx = 0
    let dy = 0
    let pending = false
    let ended = false
    const move = (ev: PointerEvent) => {
      if (ev.pointerId !== id) return
      dx = ev.clientX - x0
      dy = ev.clientY - y0
      if (pending) return
      pending = true
      onFrame(() => {
        pending = false
        if (!ended) ref.current.onMove(dx, dy)
        return false
      })
    }
    const end = (ev: PointerEvent) => {
      if (ev.pointerId !== id) return
      ended = true
      el.removeEventListener('pointermove', move as EventListener)
      el.removeEventListener('pointerup', end as EventListener)
      el.removeEventListener('pointercancel', end as EventListener)
      ref.current.onMove(dx, dy)
      ref.current.onEnd?.(dx, dy)
    }
    el.addEventListener('pointermove', move as EventListener)
    el.addEventListener('pointerup', end as EventListener)
    el.addEventListener('pointercancel', end as EventListener)
  }, [])
}
