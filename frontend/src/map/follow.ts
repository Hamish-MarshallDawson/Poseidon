import { useEffect } from 'react'
import type { GeoJSONSource, Map as MapLibreMap } from 'maplibre-gl'
import { getTrack } from '../data/track'
import { ui } from '../store/ui'
import { readToken } from '../theme/tokens'
import { shownNow } from '../timeline/replay'
import { useMapLayer } from './context'

// Follow selected (replay): only the open windows' ships are drawn (controller.ts reads ui.follow), cells and chips are
// hidden, and each followed ship's past track over the replay range is drawn here: solid up to the replay head, faint
// after it. The head split is refreshed at 4 Hz, not per frame. Drawing goes through drawFollowTracks only, so it can
// be pointed at the shared track renderer once that lands.

type Track = [number, number, number][]   // [ts, lon, lat], oldest first
const SRC = 'dvm-follow-tracks', PAST = 'dvm-follow-past', FUTURE = 'dvm-follow-future'
const HOLE_MS = 5 * 60_000                // a longer silence breaks the line
const HEAD_HZ = 4

/** Turn follow on when replay starts with windows open; off on live or when the last window closes. */
function useFollowState() {
  useEffect(() => ui.subscribe((s, p) => {
    const want = s.follow
    let next = want
    if (s.feed.mode === 'live' || s.windows.length === 0) next = false
    else if (p.feed.mode === 'live' || p.windows.length === 0) next = true      // entering replay, or the first window opens in replay
    if (next !== want) ui.set({ follow: next })
  }), [])
}

function lines(t: Track, head: number): { past: number[][][]; future: number[][][] } {
  const past: number[][][] = [], future: number[][][] = []
  let cur: number[][] = [], curFuture = false, prev = 0
  const flush = () => { if (cur.length > 1) (curFuture ? future : past).push(cur); cur = [] }
  for (const [ts, lon, lat] of t) {
    const f = ts > head
    if (cur.length && (ts - prev > HOLE_MS)) flush()
    if (f !== curFuture) { const last = cur[cur.length - 1]; flush(); curFuture = f; if (last) cur.push(last) }
    cur.push([lon, lat]); prev = ts
  }
  flush()
  return { past, future }
}

export function drawFollowTracks(map: MapLibreMap, tracks: Map<number, Track>, headTs: number): void {
  const past: GeoJSON.Feature[] = [], future: GeoJSON.Feature[] = []
  for (const t of tracks.values()) {
    const l = lines(t, headTs)
    for (const c of l.past) past.push({ type: 'Feature', properties: { k: 'past' }, geometry: { type: 'LineString', coordinates: c } })
    for (const c of l.future) future.push({ type: 'Feature', properties: { k: 'future' }, geometry: { type: 'LineString', coordinates: c } })
  }
  map.getSource<GeoJSONSource>(SRC)?.setData({ type: 'FeatureCollection', features: [...past, ...future] })
}

export function FollowTracks() {
  useFollowState()
  useMapLayer((map) => {
    const accent = readToken('accent-default') || '#86c9e8'
    map.addSource(SRC, { type: 'geojson', data: { type: 'FeatureCollection', features: [] } })
    const before = map.getLayer('dvm-ships') ? 'dvm-ships' : undefined
    const layout = { 'line-cap': 'round', 'line-join': 'round' } as const
    map.addLayer({ id: FUTURE, type: 'line', source: SRC, filter: ['==', ['get', 'k'], 'future'], layout, paint: { 'line-color': accent, 'line-width': 2, 'line-opacity': 0.3 } }, before)
    map.addLayer({ id: PAST, type: 'line', source: SRC, filter: ['==', ['get', 'k'], 'past'], layout, paint: { 'line-color': accent, 'line-width': 2.5 } }, before)

    const tracks = new Map<number, Track>()
    let timer: number | undefined
    let gen = 0
    const range = () => ui.get().feed.replay
    const redraw = () => drawFollowTracks(map, tracks, ui.get().time.dragT ?? shownNow())
    const sync = () => {
      const s = ui.get()
      const mine = ++gen
      window.clearInterval(timer)
      tracks.clear()
      if (!s.follow) { redraw(); return }
      for (const w of s.windows) {
        getTrack(w.mmsi, 24).then((t) => {
          if (mine !== gen) return
          const r = range()
          tracks.set(w.mmsi, r ? t.filter(([ts]) => ts >= r.from_ts && ts <= r.to_ts) : t)
          redraw()
        }, () => {})
      }
      timer = window.setInterval(redraw, 1000 / HEAD_HZ)
    }
    sync()
    const off = ui.subscribe((s, p) => { if (s.follow !== p.follow || (s.follow && s.windows !== p.windows)) sync() })
    return () => {
      off(); window.clearInterval(timer); gen++
      for (const id of [PAST, FUTURE]) if (map.getLayer(id)) map.removeLayer(id)
      if (map.getSource(SRC)) map.removeSource(SRC)
    }
  })
  return null
}
