// Pure SVG path builders for the marks.

export type Shape = 'circle' | 'square' | 'diamond' | 'triangle' | 'cross'

/** Path through the points; nulls break the line. `step` draws step-after (value holds until the next point). */
export function pathOf(pts: { px: number; py: number | null }[], step = false): string {
  let d = ''
  let pen = false
  for (const p of pts) {
    if (p.py == null) { pen = false; continue }
    if (!pen) d += `M${p.px},${p.py}`
    else if (step) d += `H${p.px}V${p.py}`
    else d += `L${p.px},${p.py}`
    pen = true
  }
  return d
}

export function shapePath(shape: Shape, cx: number, cy: number, r: number): string {
  switch (shape) {
    case 'square': return `M${cx - r},${cy - r}h${2 * r}v${2 * r}h${-2 * r}Z`
    case 'diamond': return `M${cx},${cy - r * 1.3}L${cx + r * 1.3},${cy}L${cx},${cy + r * 1.3}L${cx - r * 1.3},${cy}Z`
    case 'triangle': return `M${cx},${cy - r * 1.2}L${cx + r * 1.15},${cy + r * 0.8}L${cx - r * 1.15},${cy + r * 0.8}Z`
    case 'cross': return `M${cx - r},${cy - r}L${cx + r},${cy + r}M${cx + r},${cy - r}L${cx - r},${cy + r}`
    default: return `M${cx - r},${cy}a${r},${r} 0 1,0 ${2 * r},0a${r},${r} 0 1,0 ${-2 * r},0`
  }
}

