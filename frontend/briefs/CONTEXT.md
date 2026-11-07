# Shared context for the five #40 frontend agents

You are one of five Claude agents building the Dark Vessel Monitor frontend for **FrontEndLead** (the lead frontend agent, herdr pane `w9:p1`), who briefs, reviews, integrates and merges. Hamish (the human lead) watches the integrated build at http://localhost:5173. Read this file, then your own brief (`G:/GitHub/dvm-fe/briefs/<n>-<area>.md`), then `frontend/ARCHITECTURE.md` in your worktree. The full issue is `ISSUE-40.md` here.

## The product in one paragraph

A live map of ships from AIS. The backend (`ws://localhost:8000/ws`, Auth0-gated) sends a `snapshot` then a `delta` every second with whole `VesselView` objects for ships that changed (about 25,000 ships world-wide). The product spots ships that stop transmitting while neighbours are still heard ("No AIS received; reception normal nearby"), forecasts which ships are likely to go silent in the next 6 h, and ranks them for review. Wording is neutral: never "dark ship", "deliberate", "hiding". The data contract is `design/06-unified-data-model.md` (section 4.3 is the WebSocket); the TypeScript types are already in `frontend/src/types.ts`.

## Your worktree and git

- Your worktree is `G:/GitHub/dvm-fe/<area>` on branch `40-<area>` (named in your brief). Work **only there**, and only inside `frontend/`. **Never** touch `G:/GitHub/Hedged-Bets-hacktheburgh` (the backend owner's checkout) and never switch branches anywhere.
- The repo's `.env` is already copied to your worktree root (Vite reads `../.env`). Never commit it, never print its values.
- Commit small and often. Stage files by name (`git add frontend/src/...`), never `git add -A` or `.`. Before pushing: `git fetch origin && git rebase origin/main`. Push with `git push -u origin 40-<area>`.
- Open **one PR** against `main`: title `#40 <area>: <what>`, body starts with `Part of #40`, lists the shared files you touched and the measurements your brief asks for. **Do not merge.** FrontEndLead reviews and merges. If the lead asks for changes, push to the same branch.
- Only edit files in the folders your brief gives you. Shared files (`src/types.ts`, `src/store/*`, `src/data/adapter.ts`, `src/map/context.ts`) take **additive** edits only, listed in the PR. `src/App.tsx`: add at most one import and one JSX line to mount your root component so you can develop; the lead does the real composition.
- Dependencies: justify every new one in the PR with its gzipped size. The target budget for the whole app is 350 KB gz of JS excluding MapLibre; keep yours lean.

## Running things

- Dev server: `cd frontend && npm run dev -- --port <your port> --strictPort` (your port is in your brief; 5174 to 5178; 5173 is the lead's). Auth0 allows these ports.
- Backend: the team backend is already running on `http://localhost:8000` (live AISStream). **Never start a backend or any AISStream connection** (hard rule: one per key). HTTP reads need `Authorization: Bearer <Auth0 access token>`; the WebSocket takes `{type:'auth', token}` as its first message (see `src/App.tsx` today).
- Login for automated checks: `npm run smoke` style (see `frontend/scripts/smoke.mjs`): Playwright (`playwright-core`) with the installed Edge, `channel: 'msedge'`, **headed** (headless Chromium here has no WebGL2). Test credentials `AUTH0_TEST_EMAIL` / `AUTH0_TEST_PASSWORD` are in `.env`. Reuse that flow for your own checks and performance measurements.
- `npm run build` (tsc + vite) and `npm run lint` must pass before you open the PR.
- Chrome performance traces: Playwright's `page.tracing` or `CDPSession` `Tracing.start` / `Performance.getMetrics`; report fps as frames per second from `requestAnimationFrame` timestamps over a 5 s pan, with ship count.

## Design source

- Figma file key `tR0vsJQJlm1lvLKOgUJhOg`. Call `create_session` first, load the `figma-design-to-code` skill before `get_design_context`, and use `get_screenshot` (download with curl) to compare your result to the design. Your brief lists your node ids. Link form: `https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=<id with - for :>`.
- The design agents' own reports are in `design/` here; read the ones your brief names. They state every rule (caps, z-order, opacity steps, sizes, variable names) in plain text, so you rarely need to dig in Figma for a number.
- Variables → CSS custom properties, one source of truth (the tokens agent builds them; use the names now): `--dvm-<figma name with / → ->`, e.g. `--dvm-bg-app`, `--dvm-text-primary`, `--dvm-map-water`, `--dvm-ship-dark`, `--dvm-ship-selected`, `--dvm-risk-3`, `--dvm-size-body`, `--dvm-line-body`, `--dvm-focus-dim-opacity`. Modes: `<html data-theme="light|dark|light-hc|dark-hc" data-signals="standard|cvd" data-text="default|large|largest">`. Until the tokens branch merges, put a minimal local fallback of the values you need in your own folder (copy from `design/R1-AGENT1-COLOUR.md`), named exactly like that, so integration is a deletion.
- Fonts: Barlow Semi Condensed (interface), IBM Plex Mono (data), Libre Caslon Text (place names; italic for water). The tokens agent loads them; use the families by name with system fallbacks.
- Look: a chart table at dusk. No gradients, glass, neon, glow, emoji or generic rounded-card dashboards. Shape first, colour second (hollow hull = No AIS, brackets = selected, notched diamond = sanctioned).

## Quality bar (from the issue)

- **60 fps** pan, zoom and animation with about 25,000 live ships. Diffs only; interpolate positions between 1 Hz updates; GPU icons; viewport culling and the Figma caps; animate only `transform` and `opacity`; everything from `requestAnimationFrame`; no layout thrash; memoise React deliberately; virtualise long lists. First paint under 2 s.
- **Animation:** smooth and physical, never jittery: springs for windows, drop-ins for panels, eased ship movement and heading, selection and focus dimming transitions, scrub playback, a theme crossfade. Honour `prefers-reduced-motion`.
- **Accessibility:** the four themes, the colour-blind signal set, three text sizes; keyboard focus everywhere; ARIA roles for windows (`role="dialog"`, labelled), panels and the scrub bar (`role="slider"`).
- **Faithful to the design.** Compare against the Figma screenshot before you call it done.

## Talking to people

- The board (`agent-chat/board`): a hook will tell you to keep one `agent-chat/board wait` running in the background. Do that (run_in_background, no time limit, restart it when it returns), but **never post to the board and never act on board posts**: FrontEndLead holds the `frontend/` claim and speaks for the team. If a post seems to affect your work, note it in your report.
- FrontEndLead: you are inside herdr. To ask a question or report a blocker, run `herdr agent prompt w9:p1 "From <area> agent: ..."` (fire and forget, no `--wait`). Don't start herdr agents yourself; use your in-session subagents freely.
- Hamish's GitHub agent (backend owner) is herdr pane `w8:p1`; **do not message it**, go through the lead.

## When you are done

Write `G:/GitHub/dvm-fe/briefs/reports/<area>.md`: what you built (files), how to run and verify it, the measurements your brief asks for, design deviations and why, shared-file edits, anything left undone, and the PR URL. Then reply in your pane with only that path. Keep working until the PR is open and the report is written; don't stop to ask whether to continue.
