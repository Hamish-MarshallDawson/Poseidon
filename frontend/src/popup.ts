import type { VesselView } from './types'

// Fields the server's `detail` reply adds (06 section 4.3: statics[0] is the vessel's current identity).
export interface StaticDetail { ship_type?: number | null; destination?: string | null; callsign?: string | null }

const dash = (x: string | number | null | undefined) => (x === null || x === undefined || x === '' ? '–' : String(x))

// Built with textContent, never innerHTML: names and destinations are untrusted AIS text.
export function popupContent(v: VesselView, s: StaticDetail | undefined, now = Date.now()): HTMLElement {
  const type = s?.ship_type != null ? `${v.type_group} (${s.ship_type})` : v.type_group
  const ago = Math.max(0, Math.round((now - v.last_ts) / 1000))
  const rows: [string, string][] = [
    ['MMSI', String(v.mmsi)],
    ['IMO', dash(v.imo)],
    ['Ship type', type],
    ['Speed', v.sog_kn != null ? `${v.sog_kn.toFixed(1)} kn` : '–'],
    ['Course', v.cog_deg != null ? `${Math.round(v.cog_deg)}°` : '–'],
    ['Destination', s ? dash(s.destination) : '…'],
    ['Last seen', `${new Date(v.last_ts).toISOString().slice(11, 19)} UTC (${ago} s ago)`],
  ]
  const el = document.createElement('div')
  el.className = 'ship-popup'
  const title = document.createElement('strong')
  title.textContent = v.name ?? 'Unknown name'
  const dl = document.createElement('dl')
  for (const [k, val] of rows) {
    const dt = document.createElement('dt')
    const dd = document.createElement('dd')
    dt.textContent = k
    dd.textContent = val
    dl.append(dt, dd)
  }
  el.append(title, dl)
  return el
}
