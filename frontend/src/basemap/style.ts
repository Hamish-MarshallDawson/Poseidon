// The DVM basemap: OpenFreeMap's vector tiles for everything but the coast, our own coast.pmtiles for land, coastline
// and borders (scripts/basemap/), coloured from the map tokens. One style for every theme; setBasemapTheme recolours
// it in place so a theme switch never reloads tiles.
//
// Layering (bottom to top):
//   background            water below z7, land from z7 (OpenFreeMap has no land polygon: its land is the background)
//   ofm-ocean             OpenFreeMap ocean, z7+ only: carries the coast outside our Baltic box
//   coast-mask            our z6 `mask` layer (the Baltic box), overzoomed, painted water: hides OpenFreeMap's ocean
//                         edge inside the box at z7+, so there is never a double coast
//   coast-land            our land (Natural Earth z0-6 world; OSM-derived z7-14 inside the box)
//   ofm-inland            OpenFreeMap lakes, rivers and ponds, drawn on our land
//   roads (z8+), coast-line, border-line (dotted, from our z6 tiles overzoomed)
//   labels                OpenFreeMap names in the design fonts: Caslon italic for water, upright for places
// Depth/bathymetry, landcover, landuse, buildings, aeroways and OpenFreeMap's own boundaries are left out.
import type { LayerSpecification, Map as MapLibreMap, StyleSpecification } from 'maplibre-gl'

const OFM_STYLE = 'https://tiles.openfreemap.org/styles/dark'
const OFM_GLYPHS = 'https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf'
const BASE = `${import.meta.env.BASE_URL}basemap/`
const COAST_URL = `${BASE}coast.pmtiles`
const GLYPHS = `${BASE}fonts/{fontstack}/{range}.pbf`
const SWITCH_Z = 7               // our world land below; OpenFreeMap's coast (outside the box) from here

// Font stacks served from public/basemap/fonts (scripts/basemap/glyphs.py), with OpenFreeMap's Noto as the fallback.
const FONTS = {
  place: ['Libre Caslon Text Regular'], water: ['Libre Caslon Text Italic'], ui: ['Barlow Semi Condensed Medium'],
}
const NOTO = { place: ['Noto Sans Regular'], water: ['Noto Sans Italic'], ui: ['Noto Sans Regular'] }

/** The first label layer: insert ship and overlay layers before it to keep names on top. */
export const BASEMAP_FIRST_LABEL_LAYER = 'label-water-line'

export type BasemapTokens = Record<string, string>

// Every colour in the style, as [layer, paint property, value from tokens]. Used to build the style and to recolour it.
type Paint = [string, string, (t: (n: string) => string) => unknown]
const PAINT: Paint[] = [
  ['background', 'background-color', (t) => ['step', ['zoom'], t('map-water'), SWITCH_Z, t('map-land')]],
  ['ofm-ocean', 'fill-color', (t) => t('map-water')],
  ['coast-mask', 'fill-color', (t) => t('map-water')],
  ['coast-land', 'fill-color', (t) => t('map-land')],
  ['ofm-inland', 'fill-color', (t) => t('map-water')],
  ['ofm-waterway', 'line-color', (t) => t('map-water')],
  ['roads-minor', 'line-color', (t) => t('map-border')],
  ['roads-major', 'line-color', (t) => t('map-border')],
  ['coast-line', 'line-color', (t) => t('map-coast')],
  ['border-line', 'line-color', (t) => t('map-border')],
  ['label-water-line', 'text-color', (t) => t('map-label-water')],
  ['label-water-line', 'text-halo-color', (t) => t('map-water')],
  ['label-water-point', 'text-color', (t) => t('map-label-water')],
  ['label-water-point', 'text-halo-color', (t) => t('map-water')],
  ['label-road', 'text-color', (t) => t('map-label-land')],
  ['label-road', 'text-halo-color', (t) => t('map-land')],
  ['label-place', 'text-color', (t) => t('map-label-land')],
  ['label-place', 'text-halo-color', (t) => t('map-land')],
  ['label-country', 'text-color', (t) => t('map-label-land')],
  ['label-country', 'text-halo-color', (t) => t('map-land')],
]

const lookup = (tokens: BasemapTokens) => (name: string) => tokens[name] ?? tokens[`--dvm-${name}`] ?? '#888888'

/** The current map tokens from the page (needs the tokens stylesheet). */
export function basemapTokens(): BasemapTokens {
  const cs = getComputedStyle(document.documentElement)
  const out: BasemapTokens = {}
  for (const n of ['map-water', 'map-land', 'map-coast', 'map-border', 'map-label-water', 'map-label-land']) out[n] = cs.getPropertyValue(`--dvm-${n}`).trim()
  return out
}

// ---- one-time loads, cached: the OpenFreeMap style JSON, and whether our tiles and fonts are there
let ofm: Promise<StyleSpecification> | null = null
let ours: Promise<{ coast: boolean; fonts: boolean }> | null = null
const exists = (url: string) => fetch(url, { method: 'HEAD' }).then((r) => r.ok && !(r.headers.get('content-type') ?? '').includes('text/html'), () => false)

function loadOfm(): Promise<StyleSpecification> {
  ofm ??= fetch(OFM_STYLE).then((r) => { if (!r.ok) throw new Error(`OpenFreeMap style ${r.status}`); return r.json() })
  ofm.catch(() => { ofm = null })
  return ofm
}
function loadOurs() {
  ours ??= Promise.all([exists(COAST_URL), exists(GLYPHS.replace('{fontstack}', encodeURIComponent(FONTS.place[0])).replace('{range}', '0-255'))])
    .then(([coast, fonts]) => {
      if (!coast) console.warn(`[basemap] ${COAST_URL} not found: using OpenFreeMap's own coastline. Build it with npm run basemap.`)
      if (!fonts) console.warn('[basemap] map label fonts not found: using Noto Sans from OpenFreeMap.')
      return { coast, fonts }
    })
  return ours
}

const label = (l: LayerSpecification) => l.type === 'symbol'
// Filter helpers build plain arrays; MapLibre's expression types are too narrow for composed arrays, hence `never`.
const geomIs = (...types: string[]) => ['match', ['geometry-type'], types, true, false] as never
const latinName = ['coalesce', ['get', 'name_en'], ['get', 'name:latin'], ['get', 'name']]   // English first, like the design labels

/**
 * The basemap style for the given tokens (from basemapTokens()). Fetches the OpenFreeMap style once. If coast.pmtiles
 * is missing, falls back to OpenFreeMap's own coast (with a console warning) so the map still works.
 */
export async function basemapStyle(tokens: BasemapTokens = basemapTokens()): Promise<StyleSpecification> {
  const [base, have] = await Promise.all([loadOfm(), loadOurs()])
  const fonts = have.fonts ? FONTS : NOTO
  const src = 'openmaptiles'
  const byId = new Map(base.layers.map((l) => [l.id, l]))
  const keep = (id: string) => byId.get(id) as (LayerSpecification & { source: string; 'source-layer': string; filter?: unknown }) | undefined

  const layers: LayerSpecification[] = [{ id: 'background', type: 'background', paint: {} }]
  const water = ['all', geomIs('Polygon', 'MultiPolygon'), ['!=', ['get', 'brunnel'], 'tunnel']] as never
  if (have.coast) {
    layers.push(
      { id: 'ofm-ocean', type: 'fill', source: src, 'source-layer': 'water', minzoom: SWITCH_Z, filter: ['all', water, ['==', ['get', 'class'], 'ocean']] as never, paint: { 'fill-antialias': true } },
      { id: 'coast-mask', type: 'fill', source: 'coast6', 'source-layer': 'mask', minzoom: SWITCH_Z, paint: { 'fill-antialias': false } },
      { id: 'coast-land', type: 'fill', source: 'coast', 'source-layer': 'land', paint: { 'fill-antialias': false } },
      { id: 'ofm-inland', type: 'fill', source: src, 'source-layer': 'water', filter: ['all', water, ['!=', ['get', 'class'], 'ocean']] as never, paint: { 'fill-antialias': true } },
    )
  } else {
    // No coast file: OpenFreeMap's water on a land background at every zoom.
    layers.push({ id: 'ofm-inland', type: 'fill', source: src, 'source-layer': 'water', filter: water, paint: { 'fill-antialias': false } })
  }
  const ww = keep('waterway')
  if (ww) layers.push({ id: 'ofm-waterway', type: 'line', source: src, 'source-layer': 'waterway', minzoom: 8, filter: ww.filter as never, paint: { 'line-width': ['interpolate', ['linear'], ['zoom'], 8, 0.5, 14, 2] } })
  const road = (cls: string[]) => ['all', geomIs('LineString', 'MultiLineString'), ['match', ['get', 'class'], cls, true, false], ['!=', ['get', 'brunnel'], 'tunnel']]
  layers.push(
    { id: 'roads-minor', type: 'line', source: src, 'source-layer': 'transportation', minzoom: 12, filter: road(['minor', 'service', 'tertiary']) as never,
      layout: { 'line-cap': 'round', 'line-join': 'round' }, paint: { 'line-opacity': 0.35, 'line-width': ['interpolate', ['linear'], ['zoom'], 12, 0.5, 16, 2] } },
    { id: 'roads-major', type: 'line', source: src, 'source-layer': 'transportation', minzoom: 8, filter: road(['motorway', 'trunk', 'primary', 'secondary']) as never,
      layout: { 'line-cap': 'round', 'line-join': 'round' }, paint: { 'line-opacity': 0.45, 'line-width': ['interpolate', ['linear'], ['zoom'], 8, 0.4, 16, 3] } },
  )
  if (have.coast) {
    layers.push(
      { id: 'coast-line', type: 'line', source: 'coast', 'source-layer': 'coast', layout: { 'line-join': 'round' }, paint: { 'line-width': 0.75 } },
      { id: 'border-line', type: 'line', source: 'coast6', 'source-layer': 'border', layout: { 'line-join': 'round' },
        paint: { 'line-width': ['interpolate', ['linear'], ['zoom'], 2, 0.6, 10, 1.2], 'line-dasharray': [1, 2.5] } },
    )
  } else {
    layers.push({ id: 'border-line', type: 'line', source: src, 'source-layer': 'boundary', filter: ['all', ['==', ['get', 'admin_level'], 2], ['!=', ['get', 'maritime'], 1]],
      layout: { 'line-join': 'round' }, paint: { 'line-width': ['interpolate', ['linear'], ['zoom'], 2, 0.6, 10, 1.2], 'line-dasharray': [1, 2.5] } })
  }

  // (Our tiles are clipped exactly at tile edges, so their fills skip antialiasing to avoid hairline seams; the 0.75 px
  // coast stroke draws the edge. OpenFreeMap's tiles carry a buffer, so theirs antialias.)
  // Labels: OpenFreeMap's names and filters, our fonts, colours and Latin names only (the design labels are Latin).
  const halo = { 'text-halo-width': 1.2, 'text-halo-blur': 0 }
  const wn = keep('water_name')
  if (wn) {
    layers.push(
      { id: 'label-water-line', type: 'symbol', source: src, 'source-layer': 'water_name', filter: wn.filter as never,
        layout: { 'symbol-placement': 'line', 'symbol-spacing': 500, 'text-field': latinName as never, 'text-font': fonts.water, 'text-size': 12, 'text-rotation-alignment': 'map', 'text-letter-spacing': 0.05 }, paint: halo },
      { id: 'label-water-point', type: 'symbol', source: src, 'source-layer': 'water_name', filter: geomIs('Point', 'MultiPoint') as never,
        layout: { 'text-field': latinName as never, 'text-font': fonts.water, 'text-size': ['interpolate', ['linear'], ['zoom'], 2, 11, 6, 14, 10, 15], 'text-max-width': 6, 'text-letter-spacing': 0.08 }, paint: halo },
    )
  }
  layers.push({ id: 'label-road', type: 'symbol', source: src, 'source-layer': 'transportation_name', minzoom: 13, filter: geomIs('LineString', 'MultiLineString') as never,
    layout: { 'symbol-placement': 'line', 'text-field': latinName as never, 'text-font': fonts.ui, 'text-size': 11, 'text-rotation-alignment': 'map' }, paint: halo })
  const places = base.layers.filter((l) => label(l) && l.id.startsWith('place_') && !l.id.startsWith('place_country'))
  const placeFilter = ['any', ...places.map((l) => (l as { filter?: unknown }).filter ?? true)]
  layers.push({ id: 'label-place', type: 'symbol', source: src, 'source-layer': 'place', filter: ['all', geomIs('Point', 'MultiPoint'), placeFilter] as never,
    layout: { 'text-field': latinName as never, 'text-font': fonts.place, 'text-max-width': 8,
      'text-size': ['interpolate', ['linear'], ['zoom'], 4, ['match', ['get', 'class'], 'city', 12, 'town', 11, 10], 12, ['match', ['get', 'class'], 'city', 16, 'town', 13, 12]],
      'symbol-sort-key': ['get', 'rank'] }, paint: halo })
  layers.push({ id: 'label-country', type: 'symbol', source: src, 'source-layer': 'place', maxzoom: 9, filter: ['all', geomIs('Point', 'MultiPoint'), ['==', ['get', 'class'], 'country']] as never,
    layout: { 'text-field': ['upcase', latinName] as never, 'text-font': fonts.place, 'text-size': ['interpolate', ['linear'], ['zoom'], 2, 10, 6, 13], 'text-letter-spacing': 0.15, 'text-max-width': 8 }, paint: halo })

  const style: StyleSpecification = {
    version: 8,
    name: 'dvm-basemap',
    glyphs: have.fonts ? new URL(GLYPHS, location.href).href.replace('%7Bfontstack%7D', '{fontstack}').replace('%7Brange%7D', '{range}') : OFM_GLYPHS,
    sources: {
      openmaptiles: base.sources.openmaptiles,
      ...(have.coast ? {
        coast: { type: 'vector', url: `pmtiles://${new URL(COAST_URL, location.href).href}`, maxzoom: 14 },          // attribution comes from the file's metadata
        // Same file read at z0-6 only, so borders and the box mask overzoom from z6 everywhere.
        coast6: { type: 'vector', url: `pmtiles://${new URL(COAST_URL, location.href).href}`, maxzoom: 6 },
      } : {}),
    } as StyleSpecification['sources'],
    layers,
  }
  applyPaint(style.layers, tokens)
  return style
}

function applyPaint(layers: LayerSpecification[], tokens: BasemapTokens) {
  const t = lookup(tokens)
  const byId = new Map(layers.map((l) => [l.id, l as LayerSpecification & { paint?: Record<string, unknown> }]))
  for (const [id, prop, v] of PAINT) { const l = byId.get(id); if (l) (l.paint ??= {})[prop] = v(t) }
}

/** Recolours the basemap in place for new tokens (no setStyle, no tile reload). */
export function setBasemapTheme(map: MapLibreMap, tokens: BasemapTokens = basemapTokens()): void {
  const t = lookup(tokens)
  for (const [id, prop, v] of PAINT) if (map.getLayer(id)) map.setPaintProperty(id, prop as never, v(t) as never)
}
