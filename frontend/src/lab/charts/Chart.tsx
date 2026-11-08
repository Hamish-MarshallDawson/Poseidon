import { useEffect, useLayoutEffect, useMemo, useRef, useState, type ReactNode, type RefObject } from 'react'
import { Ctx, useChart, type Axis, type CatAxis, type ChartCtx, type NumAxis, type Tip } from './context'
import { placeTip } from './geom'
import { band, linear, niceTicks, numLabel, timeLabel, timeTicks, type BandScale, type Scale } from './scale'
import './charts.css'

// <Chart> lays out a responsive inline-SVG plot: it measures its width, builds the x and y scales, draws the axes and
// gridlines, and hands the scales to its children (Line, Step, Band, Markers, Bars, Ranges, RefLine) through context.
// Tooltips: a mark calls ctx.tip(...) on hover/focus and the chart shows one tooltip box at that point.

const isBand = (a: Axis): a is CatAxis => a.type === 'band'

export type ChartProps = {
  /** Accessible name, e.g. "Route skill over dead reckoning, by day". */
  label: string
  x: Axis
  y: Axis
  height?: number
  /** Fixed width; omit to fill the container. */
  width?: number
  margin?: Partial<{ top: number; right: number; bottom: number; left: number }>
  children?: ReactNode
  className?: string
}

export function Chart({ label, x, y, height = 180, width: fixed, margin, children, className }: ChartProps) {
  const wrap = useRef<HTMLDivElement>(null)
  const [measured, setMeasured] = useState(fixed ?? 560)
  const [tip, setTip] = useState<Tip>(null)
  useEffect(() => {
    if (fixed != null || !wrap.current || typeof ResizeObserver === 'undefined') return
    const el = wrap.current
    const ro = new ResizeObserver(() => setMeasured(Math.max(160, Math.round(el.clientWidth))))
    ro.observe(el)
    setMeasured(Math.max(160, Math.round(el.clientWidth)))
    return () => ro.disconnect()
  }, [fixed])
  const width = fixed ?? measured

  const leftDefault = isBand(y) ? Math.min(140, 8 + 6.5 * Math.max(...y.domain.map((k) => (y.format ? y.format(k) : k).length), 3)) : 44
  const m = { top: 10, right: 12, bottom: x.label ? 36 : 22, left: (y.label ? 14 : 0) + leftDefault, ...margin }
  const box = { left: m.left, top: m.top, right: width - m.right, bottom: height - m.bottom, width: Math.max(1, width - m.left - m.right), height: Math.max(1, height - m.top - m.bottom) }

  const ctx = useMemo<ChartCtx>(() => {
    const xs = isBand(x) ? band(x.domain, [box.left, box.right]) : linear(x.domain, [box.left, box.right])
    const ys = isBand(y) ? band(y.domain, [box.top, box.bottom]) : linear(y.domain, [box.bottom, box.top])
    return {
      X: (v) => (isBand(x) ? (xs as BandScale)(String(v)) : (xs as Scale)(Number(v))),
      Y: (v) => (isBand(y) ? (ys as BandScale)(String(v)) : (ys as Scale)(Number(v))),
      xBand: isBand(x) ? (xs as BandScale).bandwidth : 0,
      yBand: isBand(y) ? (ys as BandScale).bandwidth : 0,
      xNum: isBand(x) ? null : (xs as Scale),
      yNum: isBand(y) ? null : (ys as Scale),
      box,
      tip: setTip,
    }
    // box is derived from width/height/margins, all in the deps through these primitives
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [x, y, box.left, box.right, box.top, box.bottom])

  return (
    <div ref={wrap} className={`lab-chart ${className ?? ''}`} onPointerLeave={() => setTip(null)}>
      <svg width={width} height={height} role="img" aria-label={label} viewBox={`0 0 ${width} ${height}`}>
        <Ctx.Provider value={ctx}>
          <AxisX axis={x} />
          <AxisY axis={y} />
          <g className="lab-chart__marks">{children}</g>
        </Ctx.Provider>
      </svg>
      {tip && <TipBox tip={tip} wrap={wrap} />}
    </div>
  )
}

function numTicks(a: NumAxis, px: number): { v: number; s: string }[] {
  const count = a.ticks ?? Math.max(2, Math.min(8, Math.floor(px / 90)))
  if (a.type === 'time') {
    const t = timeTicks(a.domain, count)
    const spacing = t.length > 1 ? t[1] - t[0] : a.domain[1] - a.domain[0]
    return t.map((v) => ({ v, s: a.format ? a.format(v) : timeLabel(v, spacing) }))
  }
  return niceTicks(a.domain, count).map((v) => ({ v, s: a.format ? a.format(v) : numLabel(v, a.percent) }))
}

function AxisX({ axis }: { axis: Axis }) {
  const { X, box, xBand } = useChart()
  const ticks = isBand(axis)
    ? axis.domain.map((k) => ({ p: X(k) + xBand / 2, s: axis.format ? axis.format(k) : k }))
    : numTicks(axis, box.width).map((t) => ({ p: X(t.v), s: t.s }))
  return (
    <g className="lab-chart__axis" aria-hidden>
      <line x1={box.left} x2={box.right} y1={box.bottom} y2={box.bottom} className="lab-chart__base" />
      {ticks.map((t, i) => (
        <g key={i}>
          {!isBand(axis) && !axis.noGrid && <line x1={t.p} x2={t.p} y1={box.top} y2={box.bottom} className="lab-chart__grid" />}
          <text x={t.p} y={box.bottom + 14} textAnchor="middle">{t.s}</text>
        </g>
      ))}
      {axis.label && <text x={(box.left + box.right) / 2} y={box.bottom + 30} textAnchor="middle" className="lab-chart__label">{axis.label}</text>}
    </g>
  )
}

function AxisY({ axis }: { axis: Axis }) {
  const { Y, box, yBand } = useChart()
  const ticks = isBand(axis)
    ? axis.domain.map((k) => ({ p: Y(k) + yBand / 2, s: axis.format ? axis.format(k) : k }))
    : numTicks(axis, box.height * 1.6).map((t) => ({ p: Y(t.v), s: t.s }))
  return (
    <g className="lab-chart__axis" aria-hidden>
      {ticks.map((t, i) => (
        <g key={i}>
          {!isBand(axis) && !axis.noGrid && <line x1={box.left} x2={box.right} y1={t.p} y2={t.p} className="lab-chart__grid" />}
          <text x={box.left - 6} y={t.p} dy="0.32em" textAnchor="end">{t.s}</text>
        </g>
      ))}
      {axis.label && (
        <text transform={`translate(10 ${(box.top + box.bottom) / 2}) rotate(-90)`} textAnchor="middle" className="lab-chart__label">{axis.label}</text>
      )}
    </g>
  )
}

function TipBox({ tip, wrap }: { tip: NonNullable<Tip>; wrap: RefObject<HTMLDivElement | null> }) {
  const ref = useRef<HTMLDivElement>(null)
  const [pos, setPos] = useState<{ left: number; top: number } | null>(null)
  useLayoutEffect(() => {
    const el = ref.current
    const host = wrap.current
    if (!el || !host) return
    const o = host.getBoundingClientRect()
    setPos(placeTip(tip, { w: el.offsetWidth, h: el.offsetHeight }, { left: o.left, top: o.top }, { w: document.documentElement.clientWidth }))
  }, [tip, wrap])
  return (
    <div ref={ref} className="lab-chart__tip" role="status" style={pos ? { left: pos.left, top: pos.top } : { left: tip.x, top: tip.y, visibility: 'hidden' }}>
      {tip.content}
    </div>
  )
}
