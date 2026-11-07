// Basemap runtime: PMTiles protocol + the DVM style builder (style.ts). Map code calls registerBasemap() once before
// creating a map, then `style: await basemapStyle()`, and setBasemapTheme(map) on a theme change.
import { addProtocol } from 'maplibre-gl'
import { Protocol } from 'pmtiles'

let registered = false
/** Registers the pmtiles:// protocol with MapLibre (idempotent). */
export function registerBasemap(): void {
  if (registered) return
  registered = true
  addProtocol('pmtiles', new Protocol({ metadata: true }).tile)
}

export { BASEMAP_FIRST_LABEL_LAYER, basemapStyle, basemapTokens, setBasemapTheme, type BasemapTokens } from './style'
