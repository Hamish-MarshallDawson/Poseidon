import { useEffect } from 'react'
import { Marker, type Map as MapLibreMap } from 'maplibre-gl'
import { ui } from '../../store/ui'
import { vessels } from '../../store/vessels'
import { mapStore } from '../../map/context'
import { reducedMotion } from '../../motion'
import { openShipWindow } from '../../windows/open'
import { collab, sendPresence, useInSession } from './core'
import { presenceUi, followUser } from './state'
import { Avatar } from './Avatar'
import { fanOffsets, initials, ringIndex, safePicture, shouldSend, viewersByShip, type Bbox, type PresenceOut, type PresenceUser } from './logic'
import './presence.css'

// What I tell the others: the ship I am viewing (the front window), the ships of Follow selected, the map view.
function currentPresence(): PresenceOut {
  const s = ui.get()
  const map = mapStore.get().map
  const front = s.windows.find((w) => w.mmsi === s.frontMmsi && !w.minimised) ?? null
  const b = map?.getBounds()
  const bbox: Bbox | null = b ? [b.getWest(), b.getSouth(), b.getEast(), b.getNorth()].map((n) => Math.round(n * 1000) / 1000) as Bbox : null
  return {
    viewing: front?.mmsi ?? null,
    following: s.follow ? s.windows.map((w) => w.mmsi).slice(0, 100) : [],
    bbox,
    private: presenceUi.get().private,
  }
}

/** Sends `presence` at most every 2 s on change and at least every 8 s while in a session. */
function usePresenceOut(active: boolean) {
  useEffect(() => {
    if (!active) return
    let last: PresenceOut | null = null
    let lastAt = 0
    const tick = () => {
      const next = currentPresence()
      const now = Date.now()
      if (!shouldSend(last, lastAt, next, now)) return
      last = next; lastAt = now
      sendPresence(next)
    }
    tick()
    const id = window.setInterval(tick, 500)
    return () => window.clearInterval(id)
  }, [active])
}

// Teammates' avatars pinned to the ship they view. A handful of DOM markers (one per teammate) beside the GPU ship
// layer: the 25k ships are never touched. Positions follow the ship's last fix once a second; several people on one
// ship fan out on a small arc.
function useMapAvatars(map: MapLibreMap | null, active: boolean) {
  useEffect(() => {
    if (!map || !active) return
    const marks = new Map<string, { marker: Marker; el: HTMLElement; sig: string }>()
    const draw = () => {
      const { presence, meId } = collab.get()
      const seen = new Set<string>()
      for (const [mmsi, group] of viewersByShip(presence, meId)) {
        const v = vessels.vessels.get(mmsi)
        if (!v) continue
        const offs = fanOffsets(group.length)
        group.forEach((u: PresenceUser, i) => {
          seen.add(u.id)
          let m = marks.get(u.id)
          const sig = `${u.name}|${u.picture}`
          if (!m || m.sig !== sig) {
            m?.marker.remove()
            const el = document.createElement('div')
            el.className = 'pr-pin'
            el.dataset.user = u.id
            const marker = new Marker({ element: el, offset: [offs[i].x, offs[i].y] }).setLngLat([v.lon, v.lat]).addTo(map)
            m = { marker, el, sig }
            marks.set(u.id, m)
            m.el.appendChild(avatarEl(u))
          }
          m.marker.setOffset([offs[i].x, offs[i].y]).setLngLat([v.lon, v.lat])
        })
      }
      for (const [id, m] of marks) if (!seen.has(id)) { m.marker.remove(); marks.delete(id) }
    }
    draw()
    const id = window.setInterval(draw, 1000)
    const off = collab.subscribe((s, p) => { if (s.presence !== p.presence) draw() })
    return () => { window.clearInterval(id); off(); for (const m of marks.values()) m.marker.remove() }
  }, [map, active])
}

// The pin is a plain element (not React) because MapLibre owns it; text goes in via textContent only.
function avatarEl(u: PresenceUser): HTMLElement {
  const wrap = document.createElement('span')
  wrap.className = 'pr-av ring pr-pin-av'
  wrap.dataset.ring = String(ringIndex(u.id))
  wrap.title = u.name ?? 'Member'
  const b = document.createElement('b')
  b.textContent = initials(u.name)
  wrap.appendChild(b)
  const src = safePicture(u.picture)
  if (src) {
    const img = document.createElement('img')
    img.src = src; img.alt = ''; img.referrerPolicy = 'no-referrer'
    img.onerror = () => img.remove()
    wrap.appendChild(img)
  }
  return wrap
}

// Following a teammate's view: the map jumps to their view when it changes; touching the map yourself stops it.
function useFollowView(map: MapLibreMap | null) {
  const target = presenceUi.use((s) => s.followUser)
  useEffect(() => {
    if (!map || !target) return
    const stop = (e: { originalEvent?: unknown }) => { if (e.originalEvent) followUser(null) }
    map.on('dragstart', stop); map.on('wheel', stop); map.on('dblclick', stop)
    let lastView: number | null | undefined
    const go = () => {
      const u = collab.get().presence.find((p) => p.id === target)
      if (!u) return
      if (u.bbox) map.fitBounds([[u.bbox[0], u.bbox[1]], [u.bbox[2], u.bbox[3]]], { duration: reducedMotion() ? 0 : 600, essential: true })
      if (u.viewing != null && u.viewing !== lastView) openShipWindow(u.viewing)
      lastView = u.viewing
    }
    go()
    const off = collab.subscribe((s, p) => { if (s.presence !== p.presence) go() })
    return () => { off(); map.off('dragstart', stop); map.off('wheel', stop); map.off('dblclick', stop) }
  }, [map, target])
}

/** "Following Aiden's view · Stop", above the scrub bar. */
export function FollowBar() {
  const target = presenceUi.use((s) => s.followUser)
  const u = collab.use((s) => s.presence.find((p) => p.id === target) ?? null)
  const m = collab.use((s) => s.members.find((x) => x.id === target) ?? null)
  if (!target) return null
  const name = (u?.name ?? m?.name ?? 'a teammate').split(/\s+/)[0]
  return (
    <div className="pr-follow panel" data-zone role="status">
      {m && <Avatar id={m.id} name={m.name} picture={m.picture} size={20} />}
      <span>Following {name}’s view{!u && ' (not online)'}</span>
      <button type="button" className="dvm-btn dvm-btn--outline btn-small" onClick={() => followUser(null)}>Stop</button>
    </div>
  )
}

/** Mount once in the logged-in root. Renders nothing outside a session. */
export function Presence() {
  const inSession = useInSession()
  const map = mapStore.use((s) => s.map)
  const priv = presenceUi.use((s) => s.private)
  usePresenceOut(inSession)
  useMapAvatars(map, inSession)
  useFollowView(inSession ? map : null)
  // Switching private on or off should reach the others at once, not on the next 2 s tick (the throttle still applies).
  useEffect(() => { if (inSession) sendPresence(currentPresence()) }, [priv, inSession])
  useEffect(() => { if (!inSession) followUser(null) }, [inSession])
  return inSession ? <FollowBar /> : null
}
