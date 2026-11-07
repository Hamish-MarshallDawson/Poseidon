# Round 2 shared context: Dark Vessel Monitor design (Figma, no code)

You are one of five design sub-agents of "Hamish's GitHub agent" (the master agent). Hamish loved round 1's colours and themes and called the ship iconography fantastic: build on them, don't restyle them.

## The file

- **fileKey `tR0vsJQJlm1lvLKOgUJhOg`** ("Hacktheburgh"; the Figma MCP is logged in as Hamish MD with edit rights). URL form for links: `https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=<id with - instead of :>`.
- Round 1 pages (read only for you): `39:448` "Agent 1 · Colour & themes" (variables, specimens, rationale), `33:2` "Agent 2 · Ship iconography" (components **Ship hull** `33:108`, **Ship overlay** `33:127`, **Ship marker** `36:383`), `38:627` "Agent 3 · Map density & focus" (caps per zoom, slot priority, focus mode, basemap, layers panel), `14:2` "Brand foundations v2 (draft)" (type: Barlow Semi Condensed, IBM Plex Mono, Libre Caslon Text; uncertainty grammar solid / dashed / hatched; the **Evidence strip** component `17:2`).
- Their reports are in this folder: `R1-AGENT1-COLOUR.md`, `R1-AGENT2-SHIPS.md`, `R1-AGENT3-DENSITY.md`. Read the ones your brief names.

## Rules for every round-2 agent

1. Load the **figma-use** skill before any `use_figma` call, and **figma-generate-library** before creating components. Call `create_session` with the file key first and reuse the session id.
2. **Work only in your own new page** (named in your brief). Never edit, move or delete anything on other pages. You may *instance* round-1 components and read anything.
3. **Colours: only the shared variables** from the Colours and themes page: collections **DVM Theme** (modes Light, Dark, Light · High contrast, Dark · High contrast), **DVM Signals** (Standard, Colour-blind safe) and **DVM Text size** (Default, Large, Largest). Bind every fill, stroke and text colour to them. **Do not create or edit variables or collections.** If a role you need is missing, use the closest existing one and list the gap in your report.
4. **Light and dark variants:** show your key frames twice, one with DVM Theme = Light and one with DVM Theme = Dark (both DVM Signals = Standard), by setting explicit variable modes on the frames. Bind text sizes to DVM Text size where you can.
5. **Neutral wording, never an accusation.** Prefer "No AIS received; reception normal nearby" over "went dark", "dark ship", "deliberate" or "hiding". Use "ranked for review", "possible", "likely". Short UI labels may say "No AIS" or "Silent".
6. Avoid the generic AI look (no gradients, glassmorphism, neon, emoji, generic rounded-card dashboards). Readability first.
7. Be economical with `use_figma` calls (batch work per call): five agents share this file and its rate limit.
8. Finish: write `REPORT.md` in your folder (what you made, key decisions and why, node links, decisions for Hamish, gaps in the variables), print a short summary with node links in your tab, then reply with only the report path.

## Data you can rely on

- `DATA.md` in this folder: excerpts from `06-unified-data-model.md` (frozen field names): Vessel/VesselView, **GapEvent** (`start_ts`, `duration_s`, `radius_m` for the "could be anywhere in here" circle, `neighbours_heard`, `coverage_flag`), SpoofEvent, SanctionsMatch, **RiskScore** (`target = dark_6h`, `p`, `made_at`, `horizon_s = 21600`, `features`, `contrib`), **WatchlistEntry** (`rank`, `p`, `decision` inspect / watch / none, `reason_codes`, `evidence`), CoverageCell, **Outcome** (`label` hit or miss, `censored` coverage_gap / own_stall / data_end / already_dark, `lead_s`), the WebSocket messages (including `replay` seek / speed / pause and the `status` message with `mode` live or replay, `speed`, `replay.from_ts / to_ts`), and how consumers use them.
- **Jake's forecast tables** (he owns the data model; append-only, never updated, so the frozen forecast stays checkable): `scores` (hypertable on `made_at`, with `p` and the 6 h horizon), `gaps`, `outcomes` (keyed on `score_id`). Scoring covers ships in the **Baltic box only**. Vessel identity is the **MMSI only**.
- `EVALUATION-PLAN.md`: the honest evaluation: the model is frozen and committed about 23:00 Saturday, scored prospectively about 11:00 Sunday against **three baselines** ("went dark before", "tankers near Russian ports", the cell-hour gap rate), with **Wilson intervals** and a vessel-level bootstrap ("six hits in ten means 31 % to 83 %, and the slide must say so"), and a capture-rate-at-k curve.

## Reference mockups (Jake's, for content not style)

`ref/dark-vessel-monitor-baltic-live-map.png`, `ref/…-natuna-illegal-fishing.png`, `ref/…-hormuz-energy-flows.png`. The Baltic one has a bottom bar (ships tracked, messages per second, counts, a Replay / LIVE toggle and a scrub track 12:00–14:07 with event ticks), a "Likely to go dark · next 6 h" panel (rank, name, type, a bar, %, reason codes, "Backtest top 10: 7 hit · baseline 3"), a vessel card (timer since last AIS, last speed and heading, ships heard nearby, "could be within 16.6 km", sanctions, past gaps, Fly to / Track history / Flag for review) and an events list. Our versions use round 1's look, the neutral wording above, and honest uncertainty.
