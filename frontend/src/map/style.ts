import type { Map as MapLibreMap, StyleSpecification } from 'maplibre-gl'
import { readToken } from '../theme/tokens'

// The one indirection for the basemap. At integration the body of getStyle() becomes the coastline agent's
// `basemapStyle(tokens)` from src/basemap/style.ts; nothing else in map/ knows where the style comes from.
const OPENFREEMAP: Record<string, string> = { light: 'positron', 'light-hc': 'bright', dark: 'dark', 'dark-hc': 'dark' }

export const currentTheme = () => document.documentElement.dataset.theme ?? 'dark'

export async function getStyle(): Promise<string | StyleSpecification> {
  return `https://tiles.openfreemap.org/styles/${OPENFREEMAP[currentTheme()] ?? 'dark'}`
}

// Cheap recolour of the stand-in style to the tokens (background = land, water fills = water). The coastline
// style is built from tokens already, so this becomes a no-op there.
export function recolourBasemap(map: MapLibreMap): void {
  const land = readToken('map-land'), water = readToken('map-water')
  for (const l of map.getStyle().layers ?? []) {
    try {
      if (l.type === 'background' && land) map.setPaintProperty(l.id, 'background-color', land)
      else if (l.type === 'fill' && /^water/.test(l.id) && water) map.setPaintProperty(l.id, 'fill-color', water)
    } catch { /* a layer the style builder already themed */ }
  }
}
