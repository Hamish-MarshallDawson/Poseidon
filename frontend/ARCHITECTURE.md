# Frontend architecture (issue #40)

Map-first: the whole screen is the map; everything else drops in on click. Five areas, one folder each, so two agents never edit the same file. Shared contracts live in `src/types.ts`, `src/store/`, `src/data/adapter.ts` and `src/map/context.ts`. Changes to shared files must be additive and listed in the PR.

## Folders and owners

| Folder | Owner | What |
|---|---|---|
| `src/tokens/`, `src/theme/`, `src/ui/` | tokens agent | CSS custom properties from the Figma variables, theme store and switch (crossfade), fonts, base components |
| `src/map/`, `src/data/live.ts` | map agent | MapLibre map, ship sprites and layers, interpolation, density caps, stacking, focus dimming, live WebSocket adapter |
| `src/basemap/`, `scripts/basemap/` | coastline agent | PMTiles coastline build, style builder over OpenFreeMap |
| `src/windows/`, `src/panels/`, `src/motion/` | windows agent | floating ship windows, legend, watchlist, status line, map controls, focus UI, shared springs |
| `src/timeline/`, `src/forecast/`, `src/data/mock.ts`, `src/data/index.ts` | timeline agent | scrub bar, replay controller, forecast overlay, mock adapter |
| `src/App.tsx`, `src/main.tsx` | lead | composition; agents add one import and one JSX line for their root component |

## Data flow

```
DataAdapter (data/) ──frames──▶ VesselStore (store/vessels.ts) ──subscribe──▶ map/ (typed arrays, rAF interpolation, GPU layers)
                   ──status──▶ ui.feed                                        ▲
React UI (windows/, timeline/, panels/) ◀── ui store (store/ui.ts) ───────────┘  (selection, focus, windows, time)
```

- Ship positions never pass through React. `VesselStore.applyFrame` is O(changed); the map keeps per-ship interpolation state and redraws from `requestAnimationFrame`.
- `ui` is a tiny external store (`store/store.ts`, `useSyncExternalStore`) for selection, windows, focus, drop-ins, feed state and the shown time. Components select slices.
- `mapStore` / `useMapLayer` (`map/context.ts`) give other folders the MapLibre instance to add their own sources and layers (forecast ghosts, probability tags, leader lines).

## Tokens

CSS custom properties on `<html>`, one source of truth generated from the Figma variables. Name = Figma name with `/` → `-`, prefixed `--dvm-`: `--dvm-bg-app`, `--dvm-ship-dark`, `--dvm-size-body`, `--dvm-line-body`, `--dvm-focus-dim-opacity`. Modes are attributes: `data-theme="light|dark|light-hc|dark-hc"`, `data-signals="standard|cvd"`, `data-text="default|large|largest"`. `src/theme/tokens.ts` exports `readToken(name)` and `onTokensChange(cb)` so MapLibre paint (which needs real colours) follows the theme.

## Rules that keep it at 60 fps

- Diffs only: never re-send or re-parse the whole ship set. One `setData`/buffer update per frame at most, culled to the viewport, within the Figma caps.
- Animate only `transform` and `opacity`; drive from `requestAnimationFrame`; no layout reads in the loop.
- React: memoise deliberately, virtualise long lists, never render per ship.
- Honour `prefers-reduced-motion`.
