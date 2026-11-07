# Timeline agent report (#40, scrub bar, replay, forecast overlay)

PR: see the PR for branch `40-timeline` (title "#40 timeline: …"). Not merged. Built by FrontEndLead's timeline agent (commit `bd75dcf`, rebased onto main), then verified and fixed by Aiden's agent on Linux (2 commits on top).

## What's built

| File | What |
|---|---|
| `src/data/mock.ts` | `createMockAdapter(live, opts)`, `isMock = true`. Session replay: records the feed into `ReplayLog` and answers `{type:'replay'}` like backend PR 45 (status, snapshot on the replay clock, 1 Hz deltas at `speed`, no live deltas while in replay). If the server answers `status.mode === 'replay'` itself, the mock steps aside for good. Synthetic forecast: about 40 Baltic ships seeded by mmsi (p 0.05–0.8, ranks 1..N), watchlist, 3 open gaps (one inside a coverage hole), 2 closed gaps, spoofs, a meeting, outcomes for scores older than 6 h 30 min, a freeze marker at Sat 23:00Z, and coverage spans including the real own_stall 19:39:44–19:50:08Z. **New:** falls back to synthetic ships (below) when no backend says hello within 6 s. |
| `src/data/synthetic.ts` | **New.** A synthetic ship feed for machines without the backend: 25,000 ships (`VITE_MOCK_SHIPS`) in mostly-water boxes worldwide, heavier in the Baltic. Each ship reports every 10 s moving or 60 s at anchor. Positions are a pure function of time, so it backfills the replay log with the last 10 min. It answers `detail` too. |
| `src/data/replayLog.ts` | Columnar ring buffer, one sample per ship per 10 s, 60 min. **Changed:** typed columns at 32 B a sample (t Float64, mmsi Uint32, 5 × Float32). The old version used 7 × Float64 = 56 B, about 500 MB for 25k ships over the hour, not the "60 MB" its comment said; now it's about 290 MB at worst. |
| `src/data/index.ts` | `createAdapter`: `VITE_DATA=live` → backend only; `mock` (default) → mock around live with synthetic fallback; `offline` → synthetic ships at once. Swapping to the backend is this one line. |
| `src/data/live.ts` | Stand-in for the map agent's live adapter (WS + auth + resnapshot on a seq gap, `/history/range`). Take the map agent's file on merge. |
| `src/timeline/ScrubBar.tsx`, `scrubbar.css` | The simplified floating bar: 960 × 48 centred at the bottom at 1440. One track line with ticks per range, playhead (accent in live, ink in replay) moved by rAF with transform only. Also: LIVE dot / REPLAY, play/pause, speed menu 1/10/60/300× (disabled in live), readout `21:21:21Z −1 h 02 min`, range menu 1 h / 6 h / 24 h / Custom (UTC from/to), and Back to live. Markers: gap spans in two lanes, spoof, meeting, freeze, outcome; only watchlisted and windowed ships; merged into a count under 6 px. The 5 px coverage strip sits under the track. `role="slider"` with aria-valuemin/max/now/text. Pointer: click seeks; drag scrubs locally, with a trailing seek after 150 ms rest and a final one on release (one in flight); wheel zooms 15 min–7 d around the cursor; Shift+wheel pans; double-click resets the preset. |
| `src/timeline/replay.ts` | The shown clock (`shownNow()`, `ui.feed.now_ts` at 10 Hz): wall speed in live; `speed` between frames in replay, with a soft rate correction so it never jumps back. Seek queue. `openShip(mmsi)` writes `ui.windows` directly until the windows branch's `openShipWindow` lands. |
| `src/timeline/ReplayChrome.tsx` | 2 px `--dvm-replay-edge` round the screen and the REPLAY tab ("showing Sat 7 Nov 21:21:21Z · not live"), both always mounted and faded/slid in and out. |
| `src/forecast/*` | Probability tags (symbol layer with risk-stripe chip; rank at z<7, rank + % at z7–11, + reason at z≥11; capped 5/10/20; hidden on an open gap or an open window). Ghost regions: dashed edge, fill and hatch pattern, 64-vertex circle growing with `last_sog_kn × t` capped 60 km; grey inside a coverage hole. Also a cross at the last fix and the gap label chip (hover-only at z<7), plus outcome squares after `made_at + 6 h 30`. The Forecast check panel (from the freeze marker) shows top-k hits, the Wilson interval and three baselines. Nothing after the shown time is drawn. |

## Fixes made in this pass

1. **The mock showed no ships without the backend.** It only wrapped the live WebSocket. It now falls back to `data/synthetic.ts` (see above), so `VITE_DATA=mock` works on any machine, as the lead's 21:07 board note assumed.
2. **Replay log memory** about halved (see above).
3. **Real tokens:** `timeline/tokens-fallback.css` deleted; everything resolves from `src/tokens/tokens.css` (PR 47). Every token name used was checked against it.
4. **Theme changes reached no map layer:** forecast paint colours and canvas images were read once. It now uses `readToken` and rebuilds its layers and images on `onTokensChange` (verified dark → light and light → dark).
5. **Gap labels showed at far zoom:** MapLibre writes an inline `opacity` on the marker element, which beat `.hidden`. The label is now a child of the marker element.
6. **Probability tag chips** rendered as blank boxes with the text below them: `icon-offset`/`icon-anchor` fought `icon-text-fit`. Removed them, and added `text-max-width` so the tag stays on one line.
7. **You couldn't drag from much of the track:** gap spans cover the line, and an open gap runs to now, so pointerdown on one was swallowed as a marker click. A drag may now start on a gap span (moving scrubs; a still press is that gap's click). Point markers keep their own click.
8. **Arrow, Home and End keys were global:** pressing them with the map focused panned the map *and* seeked. They now act only when the slider has focus. Space and L stay global (not inside inputs, buttons, menus or dialogs).
9. **Ghost growth cost about 10 fps:** `setData` ran every rAF even for sub-pixel growth. It now updates only when a visible radius grows by half a pixel at the current zoom, or the visible set changes. At 1× that's about once every few seconds at z12; at 300× it's every frame. Idle fps at the same view went from 49 to 56 (60 with the overlay off).
10. Markers now reload 300 ms after a snapshot (first data, seek, back to live), not only on the 15 s poll.

## How to run and verify

```
cd frontend && npm ci
npm run dev -- --port 5178 --strictPort       # VITE_DATA=mock in ../.env; no backend needed (falls back after 6 s)
node src/timeline/selfcheck.ts                # ReplayLog and Wilson unit checks
npm run build && npm run lint
```

There's no Auth0 test user on this machine, so the app's login gate couldn't be passed. Browser checks used a Playwright-only harness instead: an HTML page routed by Playwright that loads an untracked `dev-harness.tsx`, a copy of App's `LiveMap` (same map, ship layer, `useFeed`, ThemeMenu, ForecastOverlay, ReplayChrome, ScrubBar) without the gate. Nothing that skips auth is committed. The harness and scripts live outside the repo; to reuse them, copy `dev-harness.tsx` into `src/timeline/` and run them (ask Aiden's agent for them). Browser: Playwright-core 1.55 driving `/usr/bin/chromium` headless with `--use-gl=angle --use-angle=swiftshader` (software WebGL2). Viewport 1440 × 900.

## Measurements (Linux laptop, software WebGL: indicative only; FrontEndLead re-measures)

| What | Result |
|---|---|
| Ships | 24,998 synthetic (25,000 requested; 2 mmsi hash collisions), about 2,500 reports/s |
| fps, 5 s scrub drag (200 pointer moves, 6 seeks sent: trailing + final, one in flight) | 52.8 dark / 53.8 light (p95 frame 33 ms) |
| fps, 60× playback, 5 s | 52.8 dark / 54.8 light (p95 33 ms). Clock advanced 316 s in 5.3 s wall |
| Idle fps, same view (overlay on / off) | 55.8 / 60 |
| Seek latency on the mock, pointer-up → snapshot applied → next 2 frames painted | 26–51 ms, typically about 40 ms (6 samples across two runs; one outlier 95 ms) |
| JS heap after load with 10 min backfill | about 119 MB |
| Added bundle (vs main `6fdb7bf`) | JS +19.4 KB gz (428.2 → 447.5 KB, including mock + synthetic feed, which a live-only build could drop); CSS +2.1 KB gz. No new dependencies. |

## Acceptance, item by item

| Item | Status |
|---|---|
| Scrub bar matches the simplified design | **Partial.** Matches the written spec (x 240, 960 × 48 at 1440, anatomy, marker shapes and colours, coverage strip, wording). The Figma MCP isn't authenticated here, so it wasn't compared against `56:8331` / `56:7582` / `68:17368` visually. Screenshots are in `reports/timeline/` for the lead to compare. |
| Drag, play/pause, speed, range, readout work on the mock | **Verified** in the browser: pause in live → replay paused; 60× via menu → playing; range menu → 1 h; wheel zoom → 22 min; double-click → back to 1 h; drag and click seek; L → live. |
| Markers and coverage strip render | **Verified:** 5 gap spans, 9 point markers or counts, coverage strip. A gap click seeks and opens that ship's window. The freeze marker (Sat 23:00Z) isn't in range yet tonight, so the Forecast check panel wasn't opened in the browser. |
| Keyboard and ARIA complete | **Verified:** role, aria-valuemin/max/now/text, tabindex. Space pauses; ← steps 60 s in 1 h; Shift+← steps the big step, clamped at the log start (10 min of log here); Home → oldest stored time; ← with the map focused doesn't seek; L → live. Menus: arrow keys and Esc. |
| Replay chrome in and out smoothly | **Verified** on (edge `.on`, tab opacity 1) and off after L. Transitions are CSS opacity/transform; smoothness was only eyeballed in screenshots. |
| Forecast tags and growing ghosts on the map | **Verified:** tags render (e.g. "01  80 %  Silent gap in the last 24 h" at z11.5); the ghost radius grows (checked on source data over 6 s at z12); gap labels are hidden at z<7 and shown at z8.5. |
| Mock labelled; backend swap is one change in `data/index.ts` | **Verified:** "Illustrative data" in the status line; `VITE_DATA` choice in `data/index.ts`. |
| `npm run build` and `npm run lint` pass | **Verified** (lint: 0 warnings). |
| PR open, report written | This file; PR opened right after. |

## Shared files touched

- `src/App.tsx`: more than one import and one line. The original commit moved the WebSocket code out of `LiveMap` into `data/live.ts` + `data/index.ts` (`useFeed`), added the "Illustrative data" tag and mounted three components. During the rebase it was merged with main's ThemeMenu/tokens changes, keeping both. The lead does the real composition.
- `src/data/live.ts`: a stand-in; the map agent's version wins.
- None of `types.ts`, `store/*`, `data/adapter.ts`, `map/context.ts` were edited in this pass.

## Not done, risks, notes

- Figma visual comparison (not authenticated); fps numbers are from software WebGL, not headed Edge.
- Tag text uses the basemap glyphs (`Noto Sans Regular`), not Barlow: MapLibre symbol text needs the font in the style's glyph server.
- The fallback decides once: if the desktop backend takes over 6 s to say hello (e.g. a slow Auth0 token), the session stays on synthetic ships, logs `[mock] no backend answered…` to the console and shows "Illustrative data". Set `VITE_DATA=live` to rule it out.
- The forecast layers rebuild on a theme change via `onTokensChange`. If the map agent also swaps the style on a theme change, `useMapLayer` reruns on `styleVersion` as well, so there may be two quick rebuilds. That's harmless, but setup assumes the style is loaded when it runs.
- Double-clicking the track also seeks (its two clicks), then resets the range preset.
- Outcome markers (top 10 per hour, same resolve time) show as count chips ("10") every hour in 6 h / 24 h; that follows the merge rule, but it's busy.
- Board 21:18: the project is now named POSEIDON. No UI string in this branch uses the old name.
