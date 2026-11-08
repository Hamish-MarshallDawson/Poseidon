// Minimal inline-SVG plot used by the live section until lab/charts lands (then swapped for <Chart>, <Line>, <RefLine>…).
import { useLayoutEffect, useRef, useState, type ReactNode } from 'react'

export interface Scale { (v: number): number; ticks: number[] }
export interface PlotCtx { x: Scale; y: Scale; w: number; h: number }
const PLOT_W = 560

const PAD = { l: 44, r: 10, t: 8, b: 22 }

function niceTicks(lo: number, hi: number, n: number): number[] {
  if (!(hi > lo)) return [lo]
  const raw = (hi - lo) / n, mag = 10 ** Math.floor(Math.log10(raw)), f = raw / mag
  const step = (f < 1.5 ? 1 : f < 3 ? 2 : f < 7 ? 5 : 10) * mag
  const out: number[] = []
  for (let v = Math.ceil(lo / step) * step; v <= hi + step * 1e-9; v += step) out.push(+v.toPrecision(12))
  return out
}

function scale(d0: number, d1: number, r0: number, r1: number, ticks: number[]): Scale {
  const k = d1 === d0 ? 0 : (r1 - r0) / (d1 - d0)
  const s = ((v: number) => r0 + (v - d0) * k) as Scale
  s.ticks = ticks
  return s
}

const HOUR = 3_600_000, DAY = 24 * HOUR
/** Time ticks at whole hours (or days / years for long spans). */
function timeTicks(lo: number, hi: number): number[] {
  const span = hi - lo
  const step = [HOUR, 3 * HOUR, 6 * HOUR, 12 * HOUR, DAY, 7 * DAY, 30 * DAY, 365 * DAY].find((s) => span / s <= 6) ?? 365 * DAY
  if (step === 365 * DAY) {
    const out: number[] = []
    for (let y = new Date(lo).getUTCFullYear() + 1; Date.UTC(y, 0, 1) <= hi; y += Math.max(1, Math.ceil(span / (365 * DAY) / 6))) out.push(Date.UTC(y, 0, 1))
    return out
  }
  const out: number[] = []
  for (let t = Math.ceil(lo / step) * step; t <= hi; t += step) out.push(t)
  return out
}

function fmtTick(t: number, span: number): string {
  const d = new Date(t)
  if (span > 2 * 365 * DAY) return String(d.getUTCFullYear())
  if (span > 3 * DAY) return d.toISOString().slice(5, 10)
  return d.toISOString().slice(11, 16)
}

export interface PlotProps {
  x: [number, number]; y: [number, number]; width?: number; height?: number; time?: boolean
  xTick?: (v: number) => string; yTick?: (v: number) => string
  label: string; children: (c: PlotCtx) => ReactNode
}

/** An x/y frame with gridlines and tick labels; children draw in data space through the scales. */
export function Plot({ x, y, width, height = 170, time, xTick, yTick, label, children }: PlotProps) {
  // Draw at the container's own width so tick text stays at its real size on a phone.
  const box = useRef<HTMLDivElement>(null)
  const [measured, setMeasured] = useState(0)
  useLayoutEffect(() => {
    const el = box.current
    if (!el || typeof ResizeObserver === 'undefined') return
    const ro = new ResizeObserver(([e]) => setMeasured(Math.round(e.contentRect.width)))
    ro.observe(el)
    return () => ro.disconnect()
  }, [])
  const W = Math.max(200, width ?? (measured || PLOT_W)), h = height, iw = W - PAD.l - PAD.r, ih = h - PAD.t - PAD.b
  const [x0, x1] = x[0] === x[1] ? [x[0] - HOUR, x[1] + HOUR] : x
  const xs = scale(x0, x1, PAD.l, PAD.l + iw, time ? timeTicks(x0, x1) : niceTicks(x0, x1, 5))
  const yt0 = niceTicks(y[0], y[1], 4)
  const step = yt0.length > 1 ? yt0[1] - yt0[0] : 0
  // Extend the y range to whole ticks so the top and bottom lines are labelled.
  const yLo = step && yt0[0] > y[0] ? +(yt0[0] - step).toPrecision(12) : y[0], yHi = step && yt0[yt0.length - 1] < y[1] ? +(yt0[yt0.length - 1] + step).toPrecision(12) : y[1]
  const ys = scale(yLo, yHi, PAD.t + ih, PAD.t, [...(yLo < yt0[0] ? [yLo] : []), ...yt0, ...(yHi > yt0[yt0.length - 1] ? [yHi] : [])])
  const xt = xTick ?? (time ? (v: number) => fmtTick(v, x1 - x0) : String)
  const yt = yTick ?? String
  return (
    <div ref={box} className="ll-plot-box">
    <svg className="ll-plot" viewBox={`0 0 ${W} ${h}`} role="img" aria-label={label}>
      {ys.ticks.map((v) => (
        <g key={`y${v}`}>
          <line className="ll-grid" x1={PAD.l} x2={PAD.l + iw} y1={ys(v)} y2={ys(v)} />
          <text className="ll-tick" x={PAD.l - 4} y={ys(v)} dy="0.32em" textAnchor="end">{yt(v)}</text>
        </g>
      ))}
      {xs.ticks.map((v) => <text key={`x${v}`} className="ll-tick" x={xs(v)} y={h - 6} textAnchor="middle">{xt(v)}</text>)}
      {children({ x: xs, y: ys, w: W, h })}
    </svg>
    </div>
  )
}

/** Horizontal reference line across the frame with a short label at the right. */
export function Ref({ c, v, label }: { c: PlotCtx; v: number; label?: string }) {
  return (
    <g className="ll-ref">
      <line x1={PAD.l} x2={c.w - PAD.r} y1={c.y(v)} y2={c.y(v)} />
      {label && <text x={c.w - PAD.r - 2} y={c.y(v)} dy="-0.35em" textAnchor="end">{label}</text>}
    </g>
  )
}
