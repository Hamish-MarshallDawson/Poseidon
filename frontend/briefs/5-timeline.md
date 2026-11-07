# Agent 5: timeline (scrub bar, replay) and forecast overlay

Read `CONTEXT.md` first. Worktree `G:/GitHub/dvm-fe/timeline`, branch `40-timeline`, dev port **5178**. You own `frontend/src/timeline/`, `frontend/src/forecast/`, `frontend/src/data/mock.ts` and `frontend/src/data/index.ts`.

## Design source

- Timeline page `56:1043`: **component `R2/Timeline/Bar` `56:2502`** (States live / replay / hover / dragging / playing × Range 1 h / 6 h / 24 h), bar Light `56:7582` / Dark `56:8331`, map in replay `57:6177` / `57:6362`, developer notes `58:3411`. Report: `design/R2-AGENT2-TIMELINE.md` (anatomy, markers, coverage strip, speeds 1/10/60/300×, steps, keys, message mapping, replay edge and tab, "as of" wording). The dashboard uses the **simplified floating bar**: centred at the bottom, 960 × 48 at 1440 wide (`design/R2-AGENT5-DASHBOARD-MAPFIRST.md`, frames `68:16538` / `68:17368` for replay). Hamish's requirement: "a simple scrub bar: one line; drag; play/pause; speed; time readout; variable range".
- Forecast page `56:2`: probabilities on ships `58:3638` (map Dark `58:3677` / Light `58:9107`), "could be anywhere in here" `59:418` / `59:3301`, components Probability tag `56:56`, Ghost region `56:76`, Coverage hole `56:77`, Gap label `56:93`. Report: `design/R2-AGENT3-FORECAST.md` (what p means, tag rules per zoom, ghost growth from `radius_m`, frozen forecast against outcome, neutral wording).

## Backend status (from the backend owner, 7 Nov 20:38)

Replay and history are being built on a backend branch now: client `{type:'replay', action: seek|play|pause|speed|live, t?, speed?}`; server answers `status` (`mode`, `speed`, `paused`, `replay.{from_ts,to_ts}`), then a `snapshot` whose `now_ts` is the replay clock, then 1 Hz `delta`s on the replay clock; live deltas stop while in replay. `GET /history/range` → `{from_ts, to_ts}` (positions start about 16:51Z today). Scores, gaps, outcomes and the watchlist will arrive over the same `/ws` from Jake's detector later; today `gaps`, `spoofs` are empty, `watchlist` empty, `risk_p` null. **Build against the contract and run on the mock until the lead tells you the backend branch is live.**

## Build

1. **`src/data/mock.ts`**: `createMockAdapter(live: DataAdapter): DataAdapter` with `isMock = true`. It passes the live feed through and adds what the backend lacks, clearly labelled:
   - **Session replay**: record every live frame into a ring buffer (last 60 min, compacted to one position per ship per 10 s) so `replay seek/play/pause/speed/live` work client-side; emit `status` and synthetic `snapshot`/`delta` frames with `now_ts` on the replay clock, exactly like the server will. When the real backend answers `replay`, the mock steps aside (detect `status.mode === 'replay'` from the server).
   - **Forecast**: `scores()` returns deterministic synthetic `RiskScore` rows for ~40 Baltic ships (seeded by mmsi, p in 0.05–0.8, ranks 1..N) and `watchlist` entries from them; `outcomes()` for scores older than 6 h; `timeline()` builds `TimelineEvent`s from `vessels.gaps`, `vessels.spoofs`, synthetic outcomes, a `freeze` marker at Sat 23:00Z and `coverage` spans (own_stall 19:39:44–19:50:08Z today is real). Set `ui.feed.isMock` so the UI shows the "Illustrative data" tag.
   - **`src/data/index.ts`**: `createAdapter(opts)` picks live or mock-wrapped live by `VITE_DATA` (`mock` default until the backend lands; `live` otherwise) and exports the singleton.
2. **Scrub bar (`src/timeline/ScrubBar.tsx`)**, faithful to the simplified bar: one track line with ticks per range (1 h / 6 h / 24 h presets + custom from/to), the playhead (accent in live, ink in replay), LIVE dot / inverted REPLAY chip, play/pause, speed menu (1/10/60/300×, disabled in live), time readout `13:05:12Z −1 h 02 min`, "Back to live [L]", range selector, event markers (gap spans in `--dvm-ship-dark` with ghost fill, spoof triangles, meeting rings, freeze flag, outcome squares; merge markers closer than 6 px into a count; only watchlisted and selected ships) and the 5 px coverage strip below the track. Hover tooltip with the time. `role="slider"` with `aria-valuenow/min/max/text`, keyboard: Space play/pause, arrows step (per range), Shift+arrows big step, L live, Home/End. Pointer: click seeks, drag scrubs with a local playhead and a trailing `seek` after 150 ms rest + final on release (one request in flight), wheel zooms the range around the cursor (15 min to 7 d), Shift+wheel pans, double-click resets the preset. `cursor: ew-resize` on the track.
3. **Replay controller (`src/timeline/replay.ts`)**: owns the shown clock: in live, `now_ts` advances with wall time from the last frame; in replay playing, it advances at `speed` between server frames (interpolated), so the readout and the map agent's interpolation share one clock (`ui.feed.now_ts`). Entering replay: 2 px `--dvm-replay-edge` edge around the screen and the REPLAY tab (top centre: "showing Sun 8 Nov 13:05:12Z · not live"), both animated in. Pausing in live seeks to the latest `now_ts` and enters replay. Clicking a marker seeks to its start and opens that ship's window (`openShipWindow`).
4. **Forecast overlay (`src/forecast/`)**, map layers via `useMapLayer` from `src/map/context.ts`:
   - **Probability tags** on ranked ships: per the forecast report's zoom rules (rank only at far: "01"–"05"; rank + % at mid; full tag at near), a symbol layer with a text halo in `--dvm-bg-panel`, positioned up-right of the hull; hidden when that ship has an open window.
   - **Ghost regions** for open gaps (`vessels.gaps`, state open): a dashed `--dvm-ship-ghost-edge` circle filled `--dvm-ship-ghost-fill`, hatched where unknown (a pattern image), radius `radius_m` (or `last_sog_kn` m/s × `duration_s`, capped) **growing smoothly** in real time (recompute the GeoJSON circle every rAF only while visible; 64 vertices); a magenta cross at the last fix; the gap label chip "No AIS 47 min · within 16.6 km" (hidden when its window is open; hover-only at far zoom per the dashboard's open decision 4: implement hover-only at z < 7).
   - **Coverage holes**: handled by the map agent's cells; you only add the neutral "No receiver here since 13:51Z" label on hover.
   - **Frozen forecast vs outcome** view: when the shown time is after a score's `made_at + horizon`, draw the outcome mark (hit filled / miss hollow / censored dashed square) at the ship; a small "Forecast check" panel (summon from the scrub bar's freeze marker) with the honest numbers: top-k hit count, Wilson interval, the three baselines (wording from the forecast report).
   - Replay rule: **nothing after the shown time is drawn** (filter gaps/scores by `ui.feed.now_ts`).
5. Mount `ScrubBar`, the replay chrome and `ForecastOverlay` in `App.tsx` (one import + one line each at most; keep the login gate).

## Measure and report (required), in `briefs/reports/timeline.md`

- fps during a 5 s scrub drag and during 60× playback with the live ship count (Playwright + headed Edge).
- Seek latency on the mock (pointer-up to the frame shown).
- Screenshots of the bar in live, replay and dragging next to `56:8331` / `56:7582`, and of the replay map edge next to `68:17368`.
- Added bundle size (gz).

## Acceptance

- Scrub bar matches the simplified design; drag, play/pause, speed, range and readout work on the mock; markers and coverage strip render; keyboard and ARIA complete; replay chrome in and out smoothly; forecast tags and growing ghosts on the map; the mock is labelled and swapping to the backend is one change in `data/index.ts`. `npm run build` and `npm run lint` pass. PR open, report written.
