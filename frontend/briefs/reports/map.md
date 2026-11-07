# Map core, ships and performance: report (#40, branch `40-map-ships`)

Built on Aiden's Linux desktop (RTX 3080, 60 Hz display, headed Chromium 1243 via Playwright) with **synthetic ships**. There's no backend or Auth0 test user here, so the logged-in path is built and typechecked but not run (see "Not verified"). FrontEndLead should re-measure on the desktop.

## What's built (all in `src/map/` plus `src/data/live.ts`)

| File | What |
|---|---|
| `MapView.tsx` | Full-bleed MapLibre map: mercator, no rotate or pitch, Baltic default frame, worker-URL fix. Uses the `getStyle()` indirection. Sets `mapStore` and bumps `styleVersion` on every style load. Theme change → `setStyle` and our layers re-attach; signal or text change → our layers repaint. Esc handling. Dev switches `?synthetic=N`, `?cap=0`, `?cap=N`. Optional `getToken` prop runs the live adapter until the lead wires `useFeed`. |
| `ships/controller.ts` | Everything ship-shaped: store subscription (O(changed)), slot pass, instance list, cells, dead-cell hatch, stack chips, fan-out, focus geometry, hit-testing, hover and click. |
| `ships/layer.ts` | Custom WebGL2 layer: one instanced draw per world copy. Glide, dead reckoning (stops after 3 s), smoothstep heading the short way round, and opacity fades all run in the vertex shader. The CPU touches the buffer only on change. A fix that only moves a ship patches that ship's instances (`bufferSubData`); a full rebuild happens only when a slot, a look or the selection changes. |
| `ships/state.ts` | Per-ship typed arrays by dense slot (prev/next mercator, velocity, t0/t1, heading, flags). |
| `ships/sprites.ts` + `sprites/*.svg` | Runtime atlas from the Figma hull and overlay SVGs (5 types × 3 tiers × heading known/unknown, plus brackets, sanctioned badge and window letters). Two coverage channels: mark and mark + keyline (1 / 1.5 / 2 px), so a theme change only swaps uniforms. |
| `density.ts` | Caps 100/100/40/20 by band and slot tiers 0–7 (silent or stale only via tiers 0–4). 1.5 × hull separation for routine tiers, 20 s hysteresis, centre-distance ties. Folds 4+ into stack chips, "+N" chips at harbour, and 2° / 0.5° / 0.1° cells with 4 ink tints and counts on the 6 busiest. The sort is a packed native `Float64Array` sort. |
| `stacking.ts` | Z tiers and sort key per R2-AGENT1. Opacity Full 1 / Routine 0.8 / Context `--dvm-focus-dim-opacity` / Trace 0.2. Ring offsets for fan-out. |
| `focus.ts` | Relations (nearby 10 nmi or 2 nmi moored, rendezvous, also silent ±60 min within 30 nmi, same flag in view; caps 8/3/3/5). Heard 6 h track, dashed inferred segment, ghost circle, cross, leaders. |
| `StackList.tsx` | Fallback popover for 9+ ship stacks (`ui.stack`): rows in z-order, hover highlights, click focuses and opens the window. `role="dialog"`, Esc closes. |
| `actions.ts` | `openShipWindow(mmsi, at)` (`nextWindowLetter`, default x/y beside the ship, z on top) and `setFocus`. |
| `style.ts`, `colour.ts` | `getStyle()` (OpenFreeMap by theme; the coastline agent swaps in `basemapStyle(tokens)`), cheap token recolour, CSS colour → RGBA. |
| `synthetic.ts` | Labelled synthetic feed (`isMock: true`), loaded lazily only with `?synthetic=N`. Every second a third of the ships send whole `VesselView` deltas. Includes anchorages, a receiver hole, a watchlist, gaps, spoofs and sanctioned ships. |
| `bench/` | Dev-only page `/src/map/bench/bench.html` (no login, not in the build) and the Playwright runner `bench/run.mjs`. |
| `data/live.ts` | Live adapter: auth as the first message, seq-gap reconnect with 1→15 s backoff, `hello`/`status`/`ping` → status, frames handed over as parsed, subscribe re-sent on reconnect, `historyRange` with Bearer; `timeline`/`scores`/`outcomes` reject. |

Click a ship to open its window: brackets and a letter badge are drawn upright. In focus, clicking a ship moves focus to it, and clicking the focused ship again leaves focus. Click a chip: 2–8 fan out (true positions at Trace, leaders), 9+ open the list. Clicking water or starting a move closes the fan; Esc closes the fan or list, then leaves focus. Hovering a chip shows "12 ships · 7 cargo, 3 tanker…".

## How to run

```
cd frontend && npm run dev -- --port 5175 --strictPort
# no login, synthetic: http://localhost:5175/src/map/bench/bench.html?synthetic=25000   (&cap=0 draws every ship)
# measurements:        node src/map/bench/run.mjs [--channel msedge | --browser /usr/bin/chromium] [--heap]
# real app:            http://localhost:5175/ (login gate, then MapView on the live feed; ?synthetic=25000 works there too)
```

## Measurements (indicative, this machine; 25,000 synthetic ships, ~8,300 changed per 1 s delta, 1440 × 900)

fps from rAF timestamps over a 5 s linear `easeTo`. Pan = 0.6 viewport widths; zoom = +2.5 levels.

| Scenario | Pan fps / worst frame | Zoom fps / worst frame | Drawn |
|---|---|---|---|
| Custom layer, caps (product path), Baltic z5 | **60 / 22 ms** | **60 / 22 ms** | 100 of 12,118 in view |
| Custom layer, caps, world z1.6 | **60 / 22 ms** | **60 / 22 ms** | 100 of 25,000 |
| Custom layer, `cap=0`, Baltic | 60 / 22 ms | 60 / 28 ms | 12,118 |
| Custom layer, `cap=0`, world | 60 / 22 ms | 60 / 33 ms | 25,000 |
| Symbol layer + `setData` per frame, Baltic | 10.7 / 150 ms | 22 / 211 ms | 25,000 |
| Symbol layer + `setData` per frame, world | 3.1 / 773 ms | 5.1 / 389 ms | 25,000 |

- **Decision: custom layer.** Interpolation forces a symbol layer to `setData` every frame (GeoJSON serialisation and worker re-tiling of 25k points). Measured at 3–22 fps against 60 fps for the custom layer, even with all 25k ships drawn. The comparison is the bench's `?renderer=symbol`.
- **Main-thread costs per event** (product path, world): slot pass median 11 ms / max 17 ms (on `moveend` and at most every 2 s with new data); rebuild 0.6 ms; per-delta store and patch work ≈ 4–5 ms for 8.3k changed ships. With `cap=0` a full rebuild of 25k instances is about 30 ms, but it only runs when the drawn set changes.
- **First paint:** map `load` (all tiles) 680–830 ms after navigation; first frame with ships 400–550 ms (marks `dvm:map-load` and `dvm:first-ship-frame`). Measured on the bench page; the login redirect is not included.
- **JS heap after GC:** 22 MB at 15 s, 23 MB at 120 s, panning every 4 s. Flat apart from about 1 MB of warm-up.
- **Bundle:** +18 KB gz over `main` (map code plus inlined SVG sprites; no new dependencies). `synthetic.ts` is a separate 2 KB gz lazy chunk.
- Correctness check of the patch path: after deltas, 123 drawn instances (91 moving) all matched the CPU motion state, with 3 full rebuilds in 3.5 s.

## Acceptance

- 60 fps, ≥ 58 average, no frame > 50 ms, with 25k ships: **verified here**, on synthetic data. Worst frame is 22 ms on the product path and 33 ms with every ship drawn. Indicative only; the lead re-measures on the desktop with Edge and live data.
- Icons rotate with heading and glide between updates: **verified** (shader glide, patch-path check, screenshots at near and mid).
- States and sizes match the Figma scenes: **partial**. The sprites are the Figma exports and the sizes follow R1-AGENT2, but I didn't compare screenshots against Figma (Figma tools not authenticated in this session). Seen in screenshots: solid, hollow No AIS (holes traced), spoof plus offset hollow copy, sanctioned badge, brackets plus letter, no-heading ring.
- Caps and cells behave per the density report: **verified** for caps, cells, labels, hatch, chips, "+N", list, fan-out and `ui.view` counts.
- Focus dims smoothly: **verified** (200 ms to Context; leaders drawn).
- `npm run build` and `npm run lint`: **pass**.

## Design deviations and choices

- `silent` (not yet a gap) is drawn hollow in muted ink. Magenta hollow is reserved for `gap_open`.
- Spoof's hollow copy uses a fixed screen offset (5 / 7 / 10 px), because the data has no implied position.
- Cells count current positions, not "last 10 min".
- Hysteresis lets holders win inside their own tier; a higher tier still takes the slot.
- A fold of 1–3 ships at harbour zoom still gets a "+N" chip, so no ship is silently dropped. Nearby bins merge within 96 px.
- Fan radius 52 / 78 / 110 px for far / mid / near (spec gives 78 at mid only).
- `maxZoom` is 15: float32 mercator precision in the vertex buffer stays sub-pixel up to there.
- Leaving focus doesn't restore the previous view, because the map never moves on focus. The breadcrumb, "Leave focus" button and reason chips are the windows agent's.

## Shared-file edits

- `src/store/ui.ts`: additive `stack: { mmsis; x; y } | null` (the stack list for 9+ chips; the windows agent can render it instead of `StackList`).
- `src/App.tsx`: one import (`MapView`) and one JSX line (`<MapView getToken=… /><ThemeMenu />`) in place of `<LiveMap>`. Swapping the element left `LiveMap` unused, which fails `tsc` (`noUnusedLocals`), so the dead `LiveMap` function, its imports, `src/popup.ts` and `src/vessels.ts` are deleted, as the brief asks. Side effect: the old status line and logout link are gone until the lead composes the windows agent's status line. `index.css` still has the old `.map` and `.status` rules (lead's file).
- Removed `src/map/tokens.ts` (WIP stand-in) in favour of `src/theme/tokens.ts` from PR 47.

## Integration notes for the lead

- `origin/40-timeline` has its own `src/data/live.ts`; this branch's version is the brief owner's. Keep this one and its `createLiveAdapter(opts)` signature matches `data/index.ts`.
- Once `useFeed` is mounted, drop MapView's `getToken` prop so the feed isn't started twice.
- The coastline style: put `basemapStyle(tokens)` in `getStyle()`. Our cell labels and chips use the glyph font `Noto Sans Regular`, so the new style's glyphs need it or the font name must change.

## Not verified

- The logged-in path, the live WebSocket and `historyRange` (no backend or test user here): typechecked only.
- Edge, and the desktop's numbers.
- Figma screenshot comparison.
- Reduced motion beyond code review (glides and fades become instant when `themeStore.reducedMotion` is set).

Board posts during this work (Mano's #52 briefing claim and merge, the 40-windows note) don't affect the map.

PR: https://github.com/Hamish-MarshallDawson/Hedged-Bets-hacktheburgh/pull/57
