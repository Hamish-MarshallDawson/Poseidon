import type { StyleSpecification } from 'maplibre-gl'
import { currentTheme } from './tokens'

// The one indirection for the basemap. The coastline agent's src/basemap/style.ts `basemapStyle(tokens)` replaces
// the body of this function at integration; nothing else in map/ knows where the style comes from.
const OPENFREEMAP: Record<string, string> = { light: 'positron', 'light-hc': 'bright', dark: 'dark', 'dark-hc': 'dark' }

export async function getStyle(): Promise<string | StyleSpecification> {
  return `https://tiles.openfreemap.org/styles/${OPENFREEMAP[currentTheme()]}`
}
