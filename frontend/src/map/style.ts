import type { Map as MapLibreMap, StyleSpecification } from 'maplibre-gl'
import { basemapStyle, registerBasemap, setBasemapTheme } from '../basemap'

// The one indirection for the basemap: the coastline style (our coast.pmtiles over OpenFreeMap, coloured from the
// tokens). One style serves every theme; recolourBasemap repaints it in place, so a theme swap never reloads tiles.
export const currentTheme = () => document.documentElement.dataset.theme ?? 'dark'

let registered = false
export async function getStyle(): Promise<string | StyleSpecification> {
  if (!registered) { registerBasemap(); registered = true }
  try {
    return await basemapStyle()
  } catch (e) {
    console.warn('[basemap] style build failed, using OpenFreeMap dark as is', e)
    return 'https://tiles.openfreemap.org/styles/dark'
  }
}

export function recolourBasemap(map: MapLibreMap): void {
  try { setBasemapTheme(map) } catch { /* the fallback OpenFreeMap style has none of our layers */ }
}
