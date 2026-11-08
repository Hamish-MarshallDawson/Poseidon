import { adapter } from './index'

type Track = [number, number, number][]   // [ts, lon, lat], oldest first

// The one way the UI reads a ship's past track (GET /track, up to 24 h). Cached per ship and span for a minute, and
// concurrent callers share one request. Rejects when there is no feed or the backend has no track.
const TTL_MS = 60_000
const cache = new Map<string, { at: number; p: Promise<Track> }>()

export function getTrack(mmsi: number, hours = 24): Promise<Track> {
  if (!adapter) return Promise.reject(new Error('no feed'))
  const key = `${mmsi}:${hours}`
  const hit = cache.get(key)
  if (hit && Date.now() - hit.at < TTL_MS) return hit.p
  const p = adapter.track(mmsi, hours)
  cache.set(key, { at: Date.now(), p })
  p.catch(() => { if (cache.get(key)?.p === p) cache.delete(key) })
  return p
}
