# Agent 2: map core, ships and performance

Read `CONTEXT.md` first. Worktree `G:/GitHub/dvm-fe/map`, branch `40-map-ships`, dev port **5175**. You own `frontend/src/map/` (except `context.ts`, which you may extend additively) and `frontend/src/data/live.ts`. This is the hardest and most important branch: **60 fps with 25,000 live ships** is a hard requirement.

## Design source

- Ship iconography page `33:2`: components Ship hull `33:108` (5 types × 3 sizes × heading known/unknown), Ship overlay `33:127` (selected brackets, sanctioned badge), Ship marker `36:383`, implementation notes `38:255`, sample scenes `38:272`. Report: `design/R1-AGENT2-SHIPS.md` (sizes per zoom tier, state encodings, MapLibre notes).
- Density and focus page `38:627`: density rules `38:633`, focus mode `39:1276` (map `39:1280`), layers panel `41:432`. Report: `design/R1-AGENT3-DENSITY.md` (caps 100/100/40/20 per band, slot priority tiers 0–7, hysteresis, focus relation rules, "showing N of M in view").
- Stacking page `55:2`: z-order `56:628`, opacity steps `56:684`, separation and stacks `56:832`, MapLibre notes `56:1028`, components `55:3`. Report: `design/R2-AGENT1-STACKING.md` (sort key formula, opacity steps Full 100 / Routine 80 / Context dim-opacity / Trace 20, keyline spec, stack chips with fan-out and list, clustering notes).
- Export the hull and overlay SVGs from Figma (`get_design_context` on `33:108` and `33:127` gives asset URLs; download them into `src/map/sprites/`). Every type × size × heading variant, exactly as drawn.

## Build

1. **`src/map/MapView.tsx`**: the full-bleed MapLibre map (mercator, keep the existing worker-URL fix). Style: for now the OpenFreeMap style URL per theme (`https://tiles.openfreemap.org/styles/{dark|bright|positron}`) recoloured to the tokens where cheap; the coastline agent delivers `src/basemap/style.ts` with `basemapStyle(tokens)`; design your code so swapping the style builder is one import (call a `getStyle()` indirection). Set `mapStore.set({ map })` once the style is loaded and bump `styleVersion` on every `setStyle`. Default view: the Baltic (the dashboard's frame: lon 4–36, lat 54.4–64.5 at 1440×900), not the world.
2. **`src/data/live.ts`**: `createLiveAdapter(opts): DataAdapter` implementing `data/adapter.ts`: WebSocket with the auth first message, seq-gap reconnect with backoff (port the logic from today's `App.tsx`), `send()` for detail/replay/subscribe, status handling (`hello`, `status`, `ping` → `ui.feed`), frames → `vessels.applyFrame`. `historyRange()` = `GET {httpBase}/history/range` with Bearer; `timeline/scores/outcomes` reject with `new Error('not implemented by backend')` (the timeline agent wraps you with a mock). Parse cheaply: deltas are whole objects, so just `JSON.parse` and hand over; no per-vessel allocation beyond the parsed objects.
3. **Ship rendering, the hot path (`src/map/ships/`)**: measure, then choose between a MapLibre symbol layer with SDF icons (`icon-rotate`, `icon-rotation-alignment: map`, `icon-allow-overlap`, `symbol-sort-key`) and a custom WebGL layer (`map.addLayer({type:'custom', render})`) drawing instanced quads from typed arrays. Requirements either way:
   - Per-ship state in typed arrays indexed by a dense slot (`Float32Array` lon/lat prev/next, heading prev/next, t0/t1, flags), updated O(changed) from `vessels.subscribe`.
   - **Interpolation**: between 1 Hz updates, ease position from the previous to the new fix over ~1 s, and ease heading the short way round; stop extrapolating after 3 s. Driven by one `requestAnimationFrame` loop that only runs while something moves or the map moves.
   - **Sprites** built at runtime on a canvas from the exported SVG paths, per theme (keyline baked in: `--dvm-ship-keyline` stroke 1/1.5/2 px per tier under the fill), registered with `map.addImage(..., {sdf:false})` or as a texture atlas for the custom layer; rebuilt on `onTokensChange`. Hollow (No AIS) and solid states; the implied-position hollow copy for spoofing; the no-heading ring variant; overlays (brackets, sanctioned badge) upright in a second layer (`icon-rotation-alignment: viewport`).
   - **Density caps and slots** (`src/map/density.ts`): per zoom band, the icon cap and slot priority tiers from the density report, 1.5 × icon-length separation, 20 s hysteresis, recompute on `moveend` with a 150 ms fade; ships without a slot go to **aggregate cells** (2° / 0.5° / 0.1° ink-tinted cells with counts on the 6 busiest, hatched "no receiver" cells from `vessels.coverage` state `dead`) or "+N" chips at harbour zoom. Write `ui.view` counts every recompute ("showing N of M in view").
   - **Stacking** (`src/map/stacking.ts`): sort key per the stacking report; opacity steps via feature-state or a per-slot attribute (Full / Routine 0.8 / Context `--dvm-focus-dim-opacity` / Trace 0.2); stack chips for 4+ overlapping routine ships (`cluster: true` source or your own screen-space grid), fan-out ring for 2–8 on click, list for 9+ (emit `ui` events the windows agent can render; a minimal fallback popover is fine).
   - **Selection and windows**: for every `ui.windows` entry draw the upright brackets and the letter badge beside the hull (overlay layer); hover highlight; a click on a ship calls `openShipWindow(mmsi)`: implement it as `ui.set` adding a window with `nextWindowLetter` and sensible default x/y (the windows agent refines placement). Click on a stack chip: fan-out.
   - **Focus mode** (`src/map/focus.ts`): when `ui.focusMmsi` is set, compute the related ships per the density report's relation table (nearby 10 nmi / 2 nmi when moored, possible rendezvous, also silent ±60 min within 30 nmi, same flag in view; cap 8/3/3/5), write `ui.focusRelated`, dim everything else to Context (animated over 200 ms), draw hairline leaders from related ships to the focused one and the heard track (`vessels.trails`, solid, last 6 h) plus a dashed inferred segment when the ship is silent. Esc or clicking the focused ship again leaves focus; the windows agent renders the "Leave focus" button and reason chips.
4. **Viewport culling**: only ships in the padded viewport get slots and draw calls; the rest cost nothing per frame.
5. **Status**: write `ui.feed` from status messages (connected, mode, speed, paused, now_ts, replay range, sources, stats) and `ui.view` from the slot pass.
6. Keep the existing `App.tsx` login gate working; mount `MapView` where `LiveMap` was (replace `LiveMap`, `popup.ts` and `vessels.ts` at the old paths; delete what you superseded).

## Measure and report (required)

Use Playwright with headed Edge and the smoke login. Report, in `briefs/reports/map.md`:
- fps during a 5 s programmatic pan and a zoom-in, at the world view and at the Baltic view, with the live ship count (~25k expected world-wide; if the live count is lower, add a `?synthetic=25000` dev switch that adds synthetic moving ships so the number is honest; label it).
- Time from navigation to first map paint and to the first ship frame.
- JS heap after 2 minutes (no growth per delta).
- The symbol-layer vs custom-layer decision with numbers.
- Bundle size added (gz).

## Acceptance

- 60 fps (≥ 58 average, no frame > 50 ms) pan/zoom with 25k ships on this desktop; icons rotate with heading and glide between updates; states and sizes match the Figma scenes (screenshot comparison at far/mid/near); caps and cells behave per the density report; focus dims smoothly.
- `npm run build` and `npm run lint` pass. PR open, report written.
