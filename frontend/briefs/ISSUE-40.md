From Hamish (lead), for **FrontEndLead**, the lead frontend engineer agent on the desktop (Fable 5.1).

The Figma design is approved. Build the real frontend so it **matches the design faithfully**. It must be **functional against the live backend**, **heavily optimised** (a very reactive, responsive interface) and **beautifully animated**: clean, solid, smooth transitions with nothing jittery. Looking at it should be eye candy.

## How to run this

- **You are the lead.** Read everything below, then split the work across **5 Opus 5.5 agents at high effort** in herdr:
  - launch each with `--model claude-opus-5-5 --effort high --permission-mode auto`;
  - give each one tab, and pass `--env HERDR_AGENT_DEPTH=<your depth + 1>`;
  - give each its **own git worktree and branch** off `main`.
  You brief them, review their work, integrate it and merge.
- **Worktrees are mandatory.** Hamish's GitHub agent (the backend owner, herdr pane `w8:p1` on this machine) uses the main checkout at `G:\GitHub\Hedged-Bets-hacktheburgh`, so you and your agents must never switch branches there. Run your own board commands from your own worktree, so your board read-marker is separate from its own.
- **Talk to Hamish's GitHub agent directly through herdr** (`herdr agent prompt w8:p1 ...`) for anything in `backend/`. It owns the backend; Jake's agent owns storage and the model.

## Design source (Figma, final)

File key `tR0vsJQJlm1lvLKOgUJhOg` ("Hacktheburgh"). Load the `figma-design-to-code` skill before `get_design_context`, and use `get_screenshot` to compare.

| Page | Node |
|---|---|
| Agent 1 · Colour & themes (variables: light/dark, high contrast, colour-blind-safe, 3 text sizes) | `39:448` |
| Agent 2 · Ship iconography (silhouettes per type, states, sizes, MapLibre build notes) | `33:2` |
| Agent 3 · Map density & focus (caps, priority, focus mode) | `38:627` |
| R2 · 1 Stacking & overlap (opacity, z-order, halos) | `55:2` |
| R2 · 2 Timeline (simple scrub bar) | `56:1043` |
| R2 · 3 Forecast overlay | `56:2` |
| R2 · 4 Legend | `56:94` |
| R2 · 5 Dashboard (map-first compositions, with and without legend, light and dark, floating ship windows) | `56:2506` |
| R2 · 6 Basemap (real coastlines) and its **build note** | `69:2` |

Turn the Figma variables into design tokens (CSS custom properties) with **one source of truth**, so every theme and accessibility mode follows.

## Product context

- `research/hamish+aiden/hamish-research/dark-vessel-check/REPORT.md`: what the product is.
- `research/hamish+aiden/hamish-research/dark-vessel-check/06-unified-data-model.md`: fields and the WebSocket contract (section 4.3, plus the first `{type: auth, token}` message and `detail` replies).
- `backend/README.md` and `frontend/README.md`.
- Jake's mockups in `research/jake/dark-vessel-monitor/mockups/`.

## Requirements

**Map-first layout:**
- The whole screen is the map, and you interact through the map.
- The scrub bar is visible most of the time.
- Everything else drops in and out depending on what you click:
  - **floating, draggable ship windows**: click a ship and a window opens; click another and a second opens. Several windows at once make ships easy to compare, and each window is visibly linked to its ship on the map.
  - a summonable watchlist;
  - a toggleable legend.

**Functional:**
- Runs end to end against the live backend: the `ws://localhost:8000/ws` WebSocket and Auth0.
- Where a backend feature doesn't exist yet (replay or history for the scrub bar, forecast scores, gaps, outcomes), build the UI against the data contract behind **one data-adapter interface**, with a clearly labelled mock implementation. Swapping to real data later must be one change.
- Ask Hamish's GitHub agent for the history and replay endpoints the scrub bar needs. Ask Jake (board) about scores, gaps and outcomes reads.

**Performance (a hard requirement):**
- **60 fps** pan, zoom and animation with about 25,000 live ships.
- Don't resend or re-parse the full ship set every second:
  - apply diffs, and interpolate positions between updates;
  - draw ship icons on the GPU (MapLibre symbol layer with SDF icons and heading rotation, or deck.gl `IconLayer`; measure and choose);
  - cull to the viewport, and apply the Figma caps and priority rules.
- Animate only `transform` and `opacity`, drive everything from `requestAnimationFrame`, and avoid layout thrash.
- Memoise React deliberately and virtualise long lists.
- First paint within 2 s on the desktop.
- Measure with Playwright and Chrome performance traces, set a bundle-size budget, and report the numbers.

**Animations:**
- Smooth, physical and never jittery:
  - windows opening, closing and dragging (springs);
  - legend and watchlist drop-ins;
  - ship movement interpolation and heading easing;
  - selection and focus transitions (dimming the others);
  - scrub playback;
  - a crossfade when the theme switches.
- Honour `prefers-reduced-motion`.
- Justify any animation dependency (for example Motion) and keep the bundle lean.

**Coastlines:** implement the **page `69:2` build note**:
- a custom high-detail coastline PMTiles file layered under OpenFreeMap labels;
- OpenFreeMap's own ocean coastline hidden;
- dotted land borders;
- no smoothing beyond 1 px.
Measure its targets: file size, largest tile, first paint, and pan fps over the Helsinki skerries.

**Accessibility:** use the Figma themes, high-contrast and colour-blind modes and text sizes. Add keyboard focus, and ARIA for windows and panels.

## Suggested split (change it if you have a better one)

1. **Design system and theming:** tokens from the Figma variables, base components, and the theme switch with its crossfade.
2. **Map core and ships:** MapLibre setup, ship silhouettes per type and state, stacking, opacity and z-order, density caps and aggregate cells, position interpolation, and render performance.
3. **Coastline basemap:** build the PMTiles file to the build note, layer it over OpenFreeMap, and measure accuracy and performance.
4. **Interaction layer:** the multi floating ship windows linked to the map, focus mode, the legend toggle, the watchlist drop-in, and the shared animation system.
5. **Timeline and forecast:** the simple scrub bar (one line; drag; play/pause; speed; time readout; variable range), replay mode, and the forecast overlay (probability on ships, ghost circles, frozen forecast against outcome) behind the data adapter.

## Live preview for Hamish (required)

- Keep the integrated build **running on the desktop at http://localhost:5173**, updated as you integrate, so Hamish can watch it come together. Reply with the link as soon as it's up.
  - 5173 is Hamish's main Auth0 callback.
  - Ask Hamish's GitHub agent through herdr to stop its current dev server (Ctrl+C) before you take the port over, then serve from your integration worktree.
- Sub-agents preview on ports **5174 to 5178**. Auth0 already allows 5173 to 5179 for callbacks, logouts and web origins.
  - The WebSocket isn't limited by CORS.
  - Only plain HTTP calls such as `/coverage` need CORS, so ask Hamish's GitHub agent to add those ports to `FRONTEND_ORIGINS` in the desktop's root `.env` and restart the backend cleanly.
- The smoke-test login uses `AUTH0_TEST_EMAIL` and `AUTH0_TEST_PASSWORD` from the root `.env`.

## Hard rules

- **Never** start a second backend or any AISStream connection (`backend/dvm/limits.py`: one per key; Ctrl+C only).
- **Never** commit keys.
- Follow `agent-chat/AGENTS.md`:
  - **claim `frontend/` on the board before editing**, labelling your posts with `BOARD_AS="Hamish's frontend lead"`;
  - stage files by name, rebase before push, keep PRs small, and merge your own PRs when `npm run smoke` and the build pass.
- **Talk to Hamish** through Hamish's laptop agent, which reads your herdr screen. End each reply with a status line (done / next / blockers), and include the preview link.

