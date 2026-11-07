// Token strings (#rgb, #rrggbb, #rrggbbaa, rgb(), rgba()) to 0..1 RGBA for WebGL uniforms.
export function rgba(css: string, fallback: [number, number, number, number] = [1, 0, 1, 1]): [number, number, number, number] {
  const s = css.trim()
  let m = /^#([0-9a-f]{3,8})$/i.exec(s)
  if (m) {
    let h = m[1]
    if (h.length <= 4) h = [...h].map((c) => c + c).join('')
    const n = (i: number) => parseInt(h.slice(i, i + 2), 16) / 255
    return [n(0), n(2), n(4), h.length >= 8 ? n(6) : 1]
  }
  m = /^rgba?\(([^)]+)\)$/i.exec(s)
  if (m) {
    const p = m[1].split(/[\s,/]+/).filter(Boolean).map((x) => (x.endsWith('%') ? parseFloat(x) / 100 : parseFloat(x)))
    if (p.length >= 3 && p.every(Number.isFinite)) return [p[0] / 255, p[1] / 255, p[2] / 255, p[3] ?? 1]
  }
  return fallback
}
