import { useEffect } from 'react'
import type { Map as MapLibreMap } from 'maplibre-gl'
import { createStore } from '../store/store'

// The live MapLibre instance, for layers owned by other folders (forecast overlay, window leader lines).
// map/MapView sets it once the style has loaded and clears it on unmount.
export const mapStore = createStore<{ map: MapLibreMap | null; styleVersion: number }>({ map: null, styleVersion: 0 })

export function useMapInstance(): MapLibreMap | null {
  return mapStore.use((s) => s.map)
}

// Runs `setup(map)` when the map is ready and again after every style swap (theme change rebuilds the style),
// calling the returned cleanup first. Add sources and layers inside setup; remove them in the cleanup.
export function useMapLayer(setup: (map: MapLibreMap) => void | (() => void), deps: unknown[] = []): void {
  const map = mapStore.use((s) => s.map)
  const styleVersion = mapStore.use((s) => s.styleVersion)
  useEffect(() => {
    if (!map) return
    const cleanup = setup(map)
    return () => { if (cleanup) cleanup() }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map, styleVersion, ...deps])
}
