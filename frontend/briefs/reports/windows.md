# Windows agent report (#40: ship windows, legend, watchlist, status line, motion)

Branch `40-windows`, rebased on main `6fdb7bf`. PR: https://github.com/Hamish-MarshallDawson/Hedged-Bets-hacktheburgh/pull/55. Not merged.
Built on Aiden's Linux desktop (handover from FrontEndLead's paused windows agent). The WIP commit `cd6cdeb` (now `91252eb` after
the rebase) was reviewed, tested in a real browser and fixed. The two new commits come after it.

## What is there

| Path | What |
|---|---|
| `src/motion/index.ts` | Hand-rolled springs on one shared rAF loop: `SpringStyle`, `useSpring`, `usePresence` (mount/unmount with an exit animation), `useDrag` (pointer capture, one callback per frame, no inertia), `onFrame`, `reducedMotion()`. Writes only `transform: translate3d() scale()` and `opacity`. Fixed 1/240 s substeps keep stiff springs stable. |
| `src/windows/open.ts` | The canonical `openShipWindow(mmsi, at?)`, plus `closeShipWindow`, `bringToFront`, `setMinimised`, `moveShipWindow`, `clampWindows`, `shipScreenPoint`. `ui.windows` stays the single source of truth for the map's brackets and badges. |
| `src/windows/place.ts` (+ `place.check.ts`) | Pure geometry: placement on the freer side of the ship, the 24 px cascade, viewport clamp, pill dock slots, nearest-edge for the leader. `node src/windows/place.check.ts` checks it, and also the Wilson interval and risk bands. |
| `src/windows/ShipWindow.tsx` | `WindowLayer` and each window: chrome (6-dot handle, letter badge, name and type, minimise, close), lifted drag state, a 173 × 38 pill, grow-from-ship open and shrink-to-ship close, `role="dialog"` with `aria-labelledby`, non-modal. |
| `src/windows/ShipCard.tsx` | Window body (Ship card `56:4598`, No AIS / Active): timer, fields, forecast box (neutral wording), evidence strip, "AS OF" chip in replay, Track history (sets focus) and Add to review. |
| `src/windows/Leader.tsx`, `leaderBus.ts` | One `<svg>` with two leader groups: the front window, and the hovered window. Each is a 1 px `ship/selected` line from the nearest window edge with a 5 px dot. Updated by attribute transforms in the map's `render` event and on window springs. Layout reads are cached outside the loop. |
| `src/windows/detail.ts`, `hooks.ts`, `format.ts` | `detail` request/reply store; per-ship `useVessel` (re-renders only when that ship changes); wording and number formats. |
| `src/panels/StatusLine.tsx` | "● LIVE 14:07:12Z · N of M ships in view · stacks, cells · cells without coverage", the replay form, NO FEED, "our feed paused", ILLUSTRATIVE DATA tag. |
| `src/panels/MapControls.tsx` | Top-right watchlist chip, Layers button with the pop-over (ships "Showing N of M" bar and `src/ui` `Switch` rows bound to `ui.layers`), Log out. Zoom +/− on the right edge, scale bar bottom-right. |
| `src/panels/Legend.tsx` (+ `glyphs/`) | Toggle bottom-left with `aria-expanded`; compact panel opens upward with an 8 px gap. The Figma glyphs are CSS masks painted with signal tokens, so they follow theme and CVD. |
| `src/panels/Watchlist.tsx` | Chip ("Ranked for review · next 6 h · N") and a 360-wide drop-in. Virtualised rows with a fixed height per kind (normal, No AIS). Row click flies the map and opens the window beside the ship; row hover/focus sets `ui.hoverMmsi`. Honest footer: "Prospective test running" until results exist, then hits of n with the Wilson range and the baseline overlap. |
| `src/panels/FocusBar.tsx` | "FOCUS · name · type · MMSI", reason chips counted from `ui.focusRelated`, a breadcrumb when focus moves ship to ship, and "Leave focus [Esc]". Double-clicking a window title, or Track history, sets `ui.focusMmsi`. |
| `src/windows/WindowsRoot.tsx` | One mount for all of the above: `<WindowsRoot onLogout={...} />`. Esc closes the innermost thing: the window holding focus, then layers, watchlist, legend, focus, then the front window. |
| `src/windows/demo/` | **New:** `?demo=windows` harness (lazy chunk, no login, no backend). Seeded illustrative Baltic ships moving at 1 Hz, three open gaps, a ranked watchlist of 40, canned `detail` replies, a circle layer and stand-in brackets and letter badges. Query options: `&ships=25000`, `&replay=1`, `&blank=1` (no basemap tiles). |

## Fixes made to the WIP (found by review and browser testing)

1. **Restoring a pill with 4 windows open left 5 open.** `openShipWindow` applied the 4-open limit only to new windows. Restoring now minimises the oldest window too (verified: `A B(min) C D E` → restore B → `A B C(min) D E`).
2. **Every legend glyph was a solid block.** Vite inlines small SVGs as `data:` URIs, and the unquoted `url(data:…)` is invalid CSS, so the browser dropped `mask-image`. The URL is now quoted (before/after: `legend-3x.webp`).
3. **Closing windows were still clickable and focusable** during the exit animation. They are now `inert`.
4. **Reduced motion ignored the Display menu.** `reducedMotion()` now reads `themeStore.reducedMotion`, which resolves the user's pick over the media query.
5. **Watchlist virtualisation could overlap rows.** The "No AIS …" note could wrap to a different number of lines, and a row whose ship had left the feed lost its evidence strip. Both now have fixed slots, and the heights are measured again when the text-size mode changes.
6. **Pill was 175 px wide** (the border was outside the width); it is now 173 × 38, with an ellipsis on long names.
7. **Tokens and components:** `tokens-fallback.css` is deleted (every `--dvm-*` name used exists in `src/tokens/tokens.css`), the local font redefinitions are gone, and the local `.btn`, layer-switch and `kbd` stand-ins are replaced by `src/ui` `Button`, `Switch` and `Kbd`.
8. Lint: 3 `react(refs)` warnings are gone (`usePresence` is destructured).

## How to run and verify

```
cd frontend && npm ci
npm run dev -- --port 5177 --strictPort
open http://localhost:5177/?demo=windows            # click ships; Legend bottom-left; chips top-right; Display bottom-right
open http://localhost:5177/?demo=windows&ships=25000
open http://localhost:5177/?demo=windows&replay=1   # REPLAY status line and AS OF chip
node src/windows/place.check.ts                     # geometry, Wilson, risk bands
npm run build && npm run lint                       # both pass, 0 warnings
```

## Acceptance, item by item

| Item | State | Evidence |
|---|---|---|
| Windows open, drag, minimise, restore and close with springs; several at once | **Verified** | Playwright on `?demo=windows`. Open grows from the ship (per-frame trace: scale 0.2 → 1, `transform-origin` at the ship). Drag sets `data-lifted` and moves by the pointer delta. Minimise docks a 173 × 38 pill at x 16 above the legend toggle. Restore and close work; no console errors. |
| Max 4 open, 5th minimises the oldest; front window = last clicked | **Verified** | `A B C D` + E → `A B(min) C D E`; `ui.frontMmsi` follows clicks. Restore obeys the limit (fix 1). |
| Placement beside the ship, never over it, 24 px cascade, kept in the viewport | **Verified** | `place.check.ts`; screenshots. A resize clamps windows. |
| Leader line and letter tied to the ship | **Verified (leader), partial (letter)** | The front window's leader is visible; hovering a back window shows a second one. The letters come from `ui.windows[].letter`, and the map's badge must read the same field. The real map marks are the map agent's; the harness draws stand-ins. |
| `role="dialog"`, labelled, non-modal; Esc closes the front window; Tab order | **Verified** | 2 dialogs found by role. Tab moves from Minimise to Close. Esc with focus in a window closes that window; Esc on the map closes the front window. |
| Legend drops in and out; toggle `aria-expanded` | **Verified** | `legend-wrap` springs translateY + opacity; Esc closes it. |
| Watchlist drops in; virtualised; row click opens and flies; hover sets `hoverMmsi` | **Verified** | 40 rows, 5 rendered at a time; a row click opened window A and flew the map. |
| Status line live; Layers pop-over switches bound to `ui.layers` | **Verified** | Clock ticks at 1 Hz; Depth switch flips `ui.layers.depth`. |
| Focus UI | **Verified** | A title double-click sets `focusMmsi`; the focus bar shows; Leave focus / Esc clears it. The reason chips need `ui.focusRelated` from the map (0 shown in the harness). |
| Reduced motion honoured | **Verified** | With system `reduce`, 40 ms after open the window is at `scale(1)`, `opacity: 1`; the legend too. With the Display-menu pick on a full-motion system, the same. With full motion, a window is mid-spring at 40 ms. |
| Replay "AS OF" | **Verified** | `&replay=1`: "REPLAY 21:24:26Z −1 h 02 min · …" and "AS OF 21:24:26Z" on the card. |
| Build and lint | **Verified** | `npm run build` passes; `npm run lint` passes with 0 warnings. |
| Compared with Figma | **Not done** | The Figma MCP isn't authenticated on this machine. Built from the written specs in `design/R2-AGENT5-DASHBOARD-MAPFIRST.md`, `R2-AGENT4-LEGEND.md`, `R2-AGENT3-FORECAST.md` and `R1-AGENT3-DENSITY.md`. FrontEndLead: please put the screenshots below next to `67:11383`, `67:13811` and `67:14713`. |
| Real login and backend path | **Not verified** | No Auth0 test user and no backend here. `WindowsRoot` isn't mounted in the logged-in app yet; that is the lead's composition step (see "Integration" below). |

## Measurements

Headed Chromium 1243 on an RTX 3080 (ANGLE / OpenGL), on a 60 Hz monitor, so 60 fps is the vsync ceiling. The viewport was 1440 × 900 and the map was OpenFreeMap dark at z5 over the Baltic. fps comes from `requestAnimationFrame` timestamps. These numbers come from Aiden's desktop and are only indicative; FrontEndLead re-measures.

| Scenario (5 s) | 2,000 ships | 25,000 ships |
|---|---|---|
| Pan, no window (baseline) | 60.6 fps, p95 22 ms | 60.8 fps, p95 22 ms |
| **Dragging a window** over the live map | **60.8 fps**, p95 22 ms, max 22 ms | **63.7 fps**, p95 17 ms, max 33 ms |
| **Opening then closing 4 windows** in a row (350 ms apart) | **131 fps** (unsynced rAF), p95 17 ms, max 28 ms | **152 fps**, p95 17 ms, max 39 ms |
| Pan with one window and its leader line | 59.8 fps, p95 22 ms, max 56 ms | 59.6 fps, p95 22 ms, max 72 ms |

- The overlay costs nothing measurable against the baseline. The single 56–72 ms frames during the pan come from the harness's own 1 Hz GeoJSON `setData` of every ship, not from the windows (the real map agent uses typed arrays).
- Headless SwiftShader numbers (12–50 fps) only measure software GL, and I don't use them.
- **Bundle:** no new dependency. The motion decision is hand-rolled springs instead of `motion/react` (about 30 KB gz), because only four primitives are needed. The lazy chunk holding windows + panels + motion + the demo harness is **16.7 KB gz JS + 3.4 KB gz CSS**. That is an upper bound, since the harness is about 12 KB of source inside it. Once the lead mounts `WindowsRoot` in the main app it moves to the main chunk.

## Screenshots (illustrative data, `?demo=windows`, 1440 × 900)

| Figma frame | Dark | Light |
|---|---|---|
| `67:11383` / `67:10483`: legend open + one window (No AIS) | `windows/frame4-dark.webp` | `windows/frame4-light.webp` |
| `67:13811`: two windows + one minimised | `windows/frame5-dark.webp` | `windows/frame5-light.webp` |
| `67:14713`: watchlist dropped in | `windows/frame6-dark.webp` | `windows/frame6-light.webp` |
| Legend glyphs at 3× | `windows/legend-3x.webp` | |

The harness ships are circles in rough water boxes, and the brackets and badges are stand-ins. Judge the overlay, not the map.

## Design deviations and notes

- **Leader lines:** only the front window and the hovered one have a leader, as the dashboard report proposes (decision 1 there is still open for Hamish).
- **Cascade:** windows opened for nearby ships cascade 24 px and can overlap a lot (see frame 5). That follows the spec; side-by-side comparison is done by dragging, as in the Figma frame.
- **Confidence pips** on the evidence strip are estimated from message age until the backend sends a confidence (marked `shortcut:` in `ShipCard.tsx`).
- **Prospective test footer** shows the "running" state; the scored state (`TestSummary result`) needs outcome data from the timeline adapter.
- **Add to review** is local state only; there is no backend endpoint for it.
- **ThemeMenu collides** with the top-right chips in the composed app (both fixed top-right at 16 px). The harness moves it bottom-right; the lead should choose its final place.
- **Project rename:** the board says the project is now POSEIDON (PR 51). None of my UI strings name the product, so nothing changes here.

## Integration (for the lead)

- Mount `<WindowsRoot onLogout={...} />` once over the map.
- Wire `detail`: `bindDetailSender((m) => adapter.send(m))` once the adapter starts, and route `FeedHandlers.onDetail` to `receiveDetail`. Timeline's `data/index.ts` exposes `onDetail(cb)`, so `onDetail(receiveDetail)` works.
- The map agent should call `openShipWindow(mmsi)` on ship click, draw brackets and letter badges from `ui.windows`, and fill `ui.view` and `ui.focusRelated`.
- Delete the `?demo=windows` line in `App.tsx` and `src/windows/demo/` whenever you like; nothing else imports them.

## Shared files touched

- `src/App.tsx`: one lazy import and one line for `?demo=windows` (the same pattern as `?demo=tokens`).
- No changes to `src/types.ts`, `src/store/*`, `src/data/adapter.ts` or `src/map/context.ts`.

## PR

https://github.com/Hamish-MarshallDawson/Hedged-Bets-hacktheburgh/pull/55

## Handover (22:00, back to FrontEndLead)

- **Done:** every build item 1–8 in `4-windows.md` is implemented and browser-tested (see "Acceptance"). PR 55 is open and not merged. Nothing is half-done; no work in progress is uncommitted.
- **Verified:** `npm run build` and `npm run lint` pass (0 warnings); `node src/windows/place.check.ts` passes; Playwright flows on `?demo=windows` with no console errors; fps in headed Chromium on a GPU (table above).
- **Left against the acceptance list:** (1) the Figma visual comparison (the screenshots are in `reports/windows/`); (2) mount `<WindowsRoot>` in the logged-in app and wire `detail` (see "Integration"); (3) the map agent draws brackets and letter badges from `ui.windows` and calls `openShipWindow`; (4) re-measure fps on the desktop with the real map layer.
- **Known problems:** ThemeMenu and the top-right chips overlap when both are mounted; confidence pips are estimated from message age; Add to review is local state only; the branch holds merge commits (the force-push was refused), so squash on merge.
- **To resume:** `cd frontend && npm ci && npm run dev -- --port 5177 --strictPort`, then open `/?demo=windows`. Review PR 55, then do the integration steps above.
