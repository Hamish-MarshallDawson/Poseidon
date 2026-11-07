import { useEffect, useRef } from 'react'
import { ui } from '../store/ui'
import { vessels } from '../store/vessels'
import { useMapInstance } from '../map/context'
import { scheduleLeader, setLeaderDraw, windowGeom } from './leaderBus'
import { nearestEdge } from './place'

// Leader lines: one <svg> for all. A 1 px ship/selected line from the nearest edge of the front window (and the
// hovered window) to its ship, ending in a 5 px dot at the window. Updated with transform attributes only:
// synchronously inside the map's own render frame while it moves, otherwise on the shared rAF loop.

export function LeaderLines() {
  const map = useMapInstance()
  const front = ui.use((s) => s.frontMmsi)
  const hover = ui.use((s) => s.hoverMmsi)
  const windows = ui.use((s) => s.windows)
  const svgRef = useRef<SVGSVGElement>(null)

  useEffect(() => {
    const groups = Array.from(svgRef.current!.querySelectorAll<SVGGElement>('g'))
    const targets = [front, hover !== front ? hover : null].map((m) => windows.find((w) => w.mmsi === m && !w.minimised)?.mmsi ?? null)
    let box = map?.getContainer().getBoundingClientRect()     // cached: no layout reads inside the frame loop
    const draw = () => {
      targets.forEach((mmsi, i) => {
        const g = groups[i]
        const geom = mmsi !== null ? windowGeom.get(mmsi) : undefined
        const v = mmsi !== null ? vessels.vessels.get(mmsi) : undefined
        if (!map || !box || !geom || !v || geom.spring.pos.opacity < 0.6) return void g.setAttribute('visibility', 'hidden')
        const p = map.project([v.lon, v.lat])
        const ship = { x: p.x + box.left, y: p.y + box.top }
        const { x, y } = geom.spring.pos
        const edge = nearestEdge(ship, { x, y, w: geom.w, h: geom.h })
        if (!edge) return void g.setAttribute('visibility', 'hidden')
        const dx = ship.x - edge.x
        const dy = ship.y - edge.y
        g.setAttribute('visibility', 'visible')
        g.setAttribute('transform', `translate(${edge.x} ${edge.y})`)
        g.firstElementChild!.setAttribute('transform', `rotate(${(Math.atan2(dy, dx) * 180) / Math.PI}) scale(${Math.hypot(dx, dy)} 1)`)
      })
    }
    setLeaderDraw(draw)
    draw()
    const onRender = () => draw()
    map?.on('render', onRender)
    const unsub = vessels.subscribe((changed) => { if (targets.some((t) => t !== null && changed.includes(t))) scheduleLeader() })
    const onResize = () => { box = map?.getContainer().getBoundingClientRect(); scheduleLeader() }
    addEventListener('resize', onResize)
    return () => {
      map?.off('render', onRender)
      unsub()
      removeEventListener('resize', onResize)
      setLeaderDraw(null)
    }
  }, [map, front, hover, windows])

  return (
    <svg ref={svgRef} className="leader" aria-hidden width="100%" height="100%">
      {[0, 1].map((i) => (
        <g key={i} visibility="hidden">
          <line x1={0} y1={0} x2={1} y2={0} vectorEffect="non-scaling-stroke" />
          <circle r={2.5} />
        </g>
      ))}
    </svg>
  )
}
