// A tiny champion sparkline (inline SVG, no axes): the primary held-out number per champion over time.
export function Sparkline({ points, label, width = 120, height = 32 }: { points: { t: number; v: number }[]; label: string; width?: number; height?: number }) {
  if (points.length === 0) return <span className="lab-spark lab-spark--empty" aria-hidden />
  const xs = points.map((p) => p.t), ys = points.map((p) => p.v)
  const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys)
  const sx = (t: number) => (x1 === x0 ? width / 2 : 3 + ((t - x0) / (x1 - x0)) * (width - 6))
  const sy = (v: number) => (y1 === y0 ? height / 2 : height - 3 - ((v - y0) / (y1 - y0)) * (height - 6))
  const d = points.map((p, i) => `${i ? 'L' : 'M'}${sx(p.t).toFixed(1)},${sy(p.v).toFixed(1)}`).join('')
  const last = points[points.length - 1]
  return (
    <svg className="lab-spark" width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" aria-label={label}>
      {points.length > 1 && <path d={d} fill="none" stroke="currentColor" strokeWidth={1.5} />}
      <circle cx={sx(last.t)} cy={sy(last.v)} r={3} fill="currentColor" />
    </svg>
  )
}
