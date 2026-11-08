import type { ReactNode } from 'react'
import { useChart } from './context'
import { pathOf, shapePath, type Shape } from './geom'

// Marks for <Chart>. Every mark takes a `tone` (a design-token colour, see charts.css) and an optional `tip`
// (datum => tooltip content); with a tip, each datum gets a focusable hit target that shows it on hover or focus.

export type Tone = 'accent' | 'ink' | 'muted' | 'good' | 'bad' | 'warn' | 'dark'

const fin = (v: number | null | undefined): v is number => v != null && Number.isFinite(v)

export type XY = { x: number; y: number | null }

function Hits<T>({ data, at, tip, label }: { data: T[]; at: (d: T) => [number, number] | null; tip?: (d: T) => ReactNode; label?: string }) {
  const c = useChart()
  if (!tip) return null
  return (
    <g className="lab-chart__hits">
      {data.map((d, i) => {
        const p = at(d)
        if (!p) return null
        const show = () => c.tip({ x: p[0], y: p[1], content: tip(d) })
        return (
          <circle key={i} cx={p[0]} cy={p[1]} r={8} tabIndex={0} aria-label={label}
            onPointerEnter={show} onFocus={show} onBlur={() => c.tip(null)} />
        )
      })}
    </g>
  )
}

type SeriesProps<T extends XY> = {
  data: T[]
  tone?: Tone
  dashed?: boolean
  /** Draw a dot at each point. */
  dots?: boolean
  tip?: (d: T) => ReactNode
  /** Series name, read out by screen readers on each point. */
  label?: string
}

/** A line through (x, y) points; null y leaves a gap. */
export function Line<T extends XY>({ data, tone = 'accent', dashed, dots, tip, label }: SeriesProps<T>) {
  const { X, Y } = useChart()
  const pts = data.map((d) => ({ px: X(d.x), py: fin(d.y) ? Y(d.y) : null }))
  return (
    <g className={`lab-tone-${tone}`}>
      <path d={pathOf(pts)} className={`lab-chart__line${dashed ? ' dashed' : ''}`} />
      {dots && pts.map((p, i) => p.py != null && <circle key={i} cx={p.px} cy={p.py} r={2.5} className="lab-chart__dot" />)}
      <Hits data={data} at={(d) => (fin(d.y) ? [X(d.x), Y(d.y)] : null)} tip={tip} label={label} />
    </g>
  )
}

/** A step line (value holds until the next point); `until` extends the last value to that x (e.g. now). */
export function Step<T extends XY>({ data, tone = 'accent', dashed, dots, tip, label, until }: SeriesProps<T> & { until?: number }) {
  const { X, Y } = useChart()
  const pts = data.map((d) => ({ px: X(d.x), py: fin(d.y) ? Y(d.y) : null }))
  const last = pts[pts.length - 1]
  if (until != null && last?.py != null) pts.push({ px: X(until), py: last.py })
  return (
    <g className={`lab-tone-${tone}`}>
      <path d={pathOf(pts, true)} className={`lab-chart__line${dashed ? ' dashed' : ''}`} />
      {dots && data.map((d, i) => fin(d.y) && <circle key={i} cx={X(d.x)} cy={Y(d.y)} r={3} className="lab-chart__dot" />)}
      <Hits data={data} at={(d) => (fin(d.y) ? [X(d.x), Y(d.y)] : null)} tip={tip} label={label} />
    </g>
  )
}

export type Interval = { x: number; lo: number | null; hi: number | null }

/** A shaded interval between lo and hi; `step` holds each interval until the next x (pair it with <Step>). */
export function Band<T extends Interval>({ data, tone = 'accent', step, until, tip, label }: { data: T[]; tone?: Tone; step?: boolean; until?: number; tip?: (d: T) => ReactNode; label?: string }) {
  const { X, Y } = useChart()
  const runs: string[] = []
  let top: [number, number][] = []
  let bot: [number, number][] = []
  const flush = () => {
    if (top.length) runs.push(`M${top.map((p) => p.join(',')).join('L')}L${bot.reverse().map((p) => p.join(',')).join('L')}Z`)
    top = []
    bot = []
  }
  data.forEach((d, i) => {
    if (!fin(d.lo) || !fin(d.hi)) { flush(); return }
    const x0 = X(d.x)
    const next = data[i + 1]
    top.push([x0, Y(d.hi)])
    bot.push([x0, Y(d.lo)])
    if (step) {
      const x1 = next ? X(next.x) : until != null ? X(until) : x0
      top.push([x1, Y(d.hi)])
      bot.push([x1, Y(d.lo)])
    }
  })
  flush()
  return (
    <g className={`lab-tone-${tone}`}>
      {runs.map((d, i) => <path key={i} d={d} className="lab-chart__band" />)}
      <Hits data={data} at={(d) => (fin(d.lo) && fin(d.hi) ? [X(d.x), (Y(d.lo) + Y(d.hi)) / 2] : null)} tip={tip} label={label} />
    </g>
  )
}

export type Marker = { x: number; y?: number | string | null; shape?: Shape; tone?: Tone; size?: number }

/** Point markers. y may be a number, or a category on a band y axis (centred in its band). A marker with no y sits
 * on the event rail along the top of the plot, with a faint rule down. */
export function Markers<T extends Marker>({ data, tone = 'accent', shape = 'circle', size = 4, rule, tip, label }: { data: T[]; tone?: Tone; shape?: Shape; size?: number; rule?: boolean; tip?: (d: T) => ReactNode; label?: string }) {
  const { X, Y, box, yBand } = useChart()
  const placed = (d: T) => typeof d.y === 'string' || fin(d.y)
  const at = (d: T): [number, number] => [X(d.x), typeof d.y === 'string' ? Y(d.y) + yBand / 2 : fin(d.y) ? Y(d.y) : box.top + 6]
  return (
    <g>
      {data.map((d, i) => {
        const [cx, cy] = at(d)
        const s = d.shape ?? shape
        return (
          <g key={i} className={`lab-tone-${d.tone ?? tone}`}>
            {(rule || !placed(d)) && <line x1={cx} x2={cx} y1={cy} y2={box.bottom} className="lab-chart__rule" />}
            <path d={shapePath(s, cx, cy, d.size ?? size)} className={`lab-chart__marker${s === 'cross' ? ' stroke' : ''}`} />
          </g>
        )
      })}
      <Hits data={data} at={at} tip={tip} label={label} />
    </g>
  )
}

export type Bar = { x: number | string; y: number; y0?: number; w?: number; tone?: Tone }

/** Vertical bars from y0 (default 0) to y. On a numeric x axis, `w` is the bar width in x units (e.g. the bucket). */
export function Bars<T extends Bar>({ data, tone = 'accent', tip, label }: { data: T[]; tone?: Tone; tip?: (d: T) => ReactNode; label?: string }) {
  const { X, Y, xBand, xNum } = useChart()
  const geom = (d: T) => {
    let x0: number
    let w: number
    if (xNum) {
      const half = (d.w ?? 0) / 2
      x0 = X(Number(d.x) - half) + 0.5
      w = Math.max(1, X(Number(d.x) + half) - X(Number(d.x) - half) - 1)
      if (!d.w) { x0 = X(d.x) - 2; w = 4 }
    } else {
      x0 = X(d.x)
      w = xBand
    }
    const a = Y(d.y0 ?? 0)
    const b = Y(d.y)
    return { x0, w, top: Math.min(a, b), h: Math.max(1, Math.abs(a - b)) }
  }
  return (
    <g>
      {data.map((d, i) => {
        const g = geom(d)
        return <rect key={i} x={g.x0} y={g.top} width={g.w} height={g.h} className={`lab-chart__bar lab-tone-${d.tone ?? tone}`} />
      })}
      <Hits data={data} at={(d) => { const g = geom(d); return [g.x0 + g.w / 2, g.top] }} tip={tip} label={label} />
    </g>
  )
}

export type Range = { y: string; x0: number; x1: number; tone?: Tone }

/** Horizontal bars from x0 to x1 on a categorical y axis, e.g. each source's history from oldest to newest.
 * `thickness` (px) draws a thin bar centred in the band, e.g. an interval behind a marker. */
export function Ranges<T extends Range>({ data, tone = 'accent', thickness, tip, label }: { data: T[]; tone?: Tone; thickness?: number; tip?: (d: T) => ReactNode; label?: string }) {
  const { X, Y, yBand } = useChart()
  const h = thickness != null ? Math.min(thickness, yBand) : yBand
  const off = (yBand - h) / 2
  return (
    <g>
      {data.map((d, i) => (
        <rect key={i} x={X(d.x0)} y={Y(d.y) + off} width={Math.max(2, X(d.x1) - X(d.x0))} height={h} rx={thickness != null ? h / 2 : 0} className={`lab-chart__bar lab-tone-${d.tone ?? tone}${thickness != null ? ' soft' : ''}`} />
      ))}
      <Hits data={data} at={(d) => [(X(d.x0) + X(d.x1)) / 2, Y(d.y) + yBand / 2]} tip={tip} label={label} />
    </g>
  )
}

/** A reference line: horizontal at `y` (e.g. the nominal 80%, or zero skill) or vertical at `x` (e.g. a deploy). */
export function RefLine({ y, x, label, tone = 'muted', solid }: { y?: number; x?: number; label?: string; tone?: Tone; solid?: boolean }) {
  const { X, Y, box } = useChart()
  if (y != null) {
    const py = Y(y)
    return (
      <g className={`lab-tone-${tone}`}>
        <line x1={box.left} x2={box.right} y1={py} y2={py} className={`lab-chart__ref${solid ? '' : ' dashed'}`} />
        {label && <text x={box.right - 4} y={py - 4} textAnchor="end" className="lab-chart__reflabel">{label}</text>}
      </g>
    )
  }
  if (x != null) {
    const px = X(x)
    return (
      <g className={`lab-tone-${tone}`}>
        <line x1={px} x2={px} y1={box.top} y2={box.bottom} className={`lab-chart__ref${solid ? '' : ' dashed'}`} />
        {label && (px > box.right - 60
          ? <text x={px - 4} y={box.top + 10} textAnchor="end" className="lab-chart__reflabel">{label}</text>
          : <text x={px + 4} y={box.top + 10} className="lab-chart__reflabel">{label}</text>)}
      </g>
    )
  }
  return null
}

/** The y = x diagonal, for reliability diagrams (predicted against observed). */
export function Diagonal({ tone = 'muted', label }: { tone?: Tone; label?: string }) {
  const { X, Y, xNum, yNum } = useChart()
  if (!xNum || !yNum) return null
  const lo = Math.max(xNum.domain[0], yNum.domain[0])
  const hi = Math.min(xNum.domain[1], yNum.domain[1])
  return (
    <g className={`lab-tone-${tone}`}>
      <line x1={X(lo)} y1={Y(lo)} x2={X(hi)} y2={Y(hi)} className="lab-chart__ref dashed" />
      {label && <text x={X(hi) - 4} y={Y(hi) + 12} textAnchor="end" className="lab-chart__reflabel">{label}</text>}
    </g>
  )
}

export type LegendItem = { label: ReactNode; tone?: Tone; kind?: 'line' | 'dashed' | 'band' | 'bar' | Shape }

/** HTML legend row for a chart; every series is named in words, not colour alone. */
export function Legend({ items }: { items: LegendItem[] }) {
  return (
    <ul className="lab-legend">
      {items.map((it, i) => {
        const kind = it.kind ?? 'line'
        return (
          <li key={i}>
            <svg width={18} height={10} aria-hidden className={`lab-tone-${it.tone ?? 'accent'}`}>
              {kind === 'line' || kind === 'dashed' ? <line x1={1} x2={17} y1={5} y2={5} className={`lab-chart__line${kind === 'dashed' ? ' dashed' : ''}`} />
                : kind === 'band' ? <rect x={1} y={1} width={16} height={8} className="lab-chart__band" />
                : kind === 'bar' ? <rect x={4} y={1} width={10} height={8} className="lab-chart__bar" />
                : <path d={shapePath(kind, 9, 5, 3.5)} className={`lab-chart__marker${kind === 'cross' ? ' stroke' : ''}`} />}
            </svg>
            {it.label}
          </li>
        )
      })}
    </ul>
  )
}
