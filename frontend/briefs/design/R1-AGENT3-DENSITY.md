# Agent 3 report: map density, focus mode and basemap

Page **"Agent 3 · Map density & focus"** in the Hacktheburgh file. It builds on Brand foundations v2 (night): chart water, warm ink, Barlow / Plex Mono / Caslon, and the solid / dashed / hatched uncertainty grammar. Nothing outside this page was touched. No variables were created. No "DVM" collections existed when I worked, so the fills are plain v2 hex values for these roles: water/deep, land/fill, land/coast, grid/line, surface/panel, surface/edge, ink primary/secondary/muted/faint, signal dark-gap magenta, caution amber, inferred pale blue, and risk 1 to 4. The master agent can bind them. Ship marks are instances of one placeholder component (`placeholder/ship-mark`) so they can be swapped for agent 2's silhouettes.

## Links

- Page: https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=38-627
- 1 · Density rules (zoom storyboard, slot priority, aggregate legend, slot behaviour): https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=38-633
- 2 · Focus mode (map + relation rules): https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=39-1276 (map: https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=39-1280)
- 3 · Basemap (before/after, requirement, options, depth layer): https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=41-250
- 4 · Layers & filters (panel + status line variants): https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=41-432
- 5 · Rationale: https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=41-522
- Placeholder parts (ship-mark component): https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=38-628

## Cap per zoom

| Band | Zoom | Icon cap | Ships without a slot become |
|---|---|---|---|
| World | z 0–3 | **100** | ~2° screen bins, summed from the 0.1° `coverage_1m` cells |
| Region | z 4–6 | **100** (same fixed cap) | 0.5° bins |
| Sea area | z 7–9 | **40** | native 0.1° cells (no re-binning) |
| Harbour | z 10+ | **20** | no cells; "+N" chips per berth, anchorage or river reach ("+31 at anchor") |

Why 100 when zoomed out: it matches how deep a reviewer goes into the watchlist. At world zoom one icon covers about 200 km, so extra icons only pile up and make the "game" look.

Cells use 4 monochrome ink tints, with breaks set per band (World 1–49 / 50–249 / 250–999 / 1k+; Region 1–19 / 20–79 / 80–299 / 300+; Sea 1–2 / 3–9 / 10–29 / 30+ ships per cell over the last 10 min). Counts are printed only on the 6 busiest cells in view. A cell is hatched with a dashed edge when no receiver has heard anything there for 10 min. That means "we can't see here", which is different from "ships went dark".

## Slot priority (who wins a slot)

0. Selected or focused ship. Always drawn and never counts against the cap.
1. Watchlist `decision = inspect`, ordered by `risk_rank`.
2. Open gap (`status = gap_open`): a cross at the last position plus the ghost region.
3. Watchlist `decision = watch`, ordered by `risk_rank`.
4. Flagged: `sanctioned = true`, or any `spoof_recent` in the last 24 h.
5. Followed: ships the analyst pinned this session.
6. Large or fast: `length_m ≥ 200` or `sog_kn ≥ 18`, ordered by length.
7. Most recent: `status = active`, newest `last_ts` first.

- Ties go to the ship nearest the view centre.
- Silent or stale ships only get a slot through tiers 0 to 4.
- Two icons are never closer than 1.5 × icon length. The lower-ranked one folds into its cell or chip.
- Hysteresis: a ship keeps its slot for 20 s unless a ship from a higher tier outranks it.
- Slots are recomputed when the map settles (`moveend`), with a 150 ms fade.
- No ship is silently dropped. The status line always says "showing N of M in view".

## Focus mode relation rules

| Reason | Rule | Distance / time | Max shown |
|---|---|---|---|
| Nearby | within the ring around the last fix (or the ghost edge when dark) | **10 nmi (18.5 km)**; 2 nmi when the selected ship is moored or at anchor (`sog_kn < 0.5`) | 8 nearest |
| Possible rendezvous | both ships `sog_kn < 3` and within 0.5 nmi for at least 30 min | **0.5 nmi (926 m), ≥ 30 min, last 24 h** | 3 |
| Also dark | another ship whose gap opened within ±60 min of this one | **30 nmi, ±60 min** | 3 |
| Same flag | same `flag`, inside the current view (lowest weight) | current view | 5 nearest |
| Same owner / operator | same registered owner or operator | any distance | 5. **Needs a data source** (not in the model): Equasis (manual), S&P Sea-web, or OpenSanctions entities. Shown greyed until then |

- At most 1 + 8 + 3 + 3 + 5 = 20 ships, so focus mode stays within the zoomed-in cap.
- Each related ship has a reason chip and a hairline leader line back to the selected ship.
- The heard track is solid warm ink covering the last 6 h, with a UTC tick each hour. The inferred segment is dashed pale blue.
- When the ship goes dark: a magenta cross at the last fix, the ship mark fades to 35 %, and a hatched ghost circle (`radius_m`) is labelled with the time dark and the radius.
- To leave focus: Esc, the "Leave focus" button, or clicking the focused ship again. This returns to the previous view and zoom. Clicking empty water does not leave focus. Clicking a related ship moves focus to it, with a breadcrumb to step back.

## Basemap requirement

- Coastlines, islands and borders must be drawn with a vertex error of **at most 1 screen px at every zoom 0–14**. No smoothing.
- Keep every island of at least 1 px².
- Borders come from the same detailed source as the coastline.
- Use at least Natural Earth 10 m at z 0–3 and OSM land polygons from z 4.
- The before/after frame shows why this matters: with a generalised coast, ships in real channels in the skerries appear to sail over land, which looks like an `on_land` spoof.
- **Depth is removed from the default style.** An optional "Depth" layer stays off by default and shows contours only (10 / 20 / 50 / 200 m), with no tints.

Options:

- **A (recommended):** keep OpenFreeMap for labels and add our own coastline and border layer on top. Source: OSM land polygons from osmdata.openstreetmap.de. Tile them with `tippecanoe --no-line-simplification --no-tiny-polygon-reduction` into a static PMTiles file, and hide OpenFreeMap's own water outline below z 6.
- **B:** self-host the whole basemap with Planetiler, using lower simplification settings.
- **C (stopgap):** Natural Earth 10 m for z 0–5. It is still generalised.

Measure tile size and first paint before the demo.

## Layers & filters panel

The panel opens with the cap stated in words ("Showing 20 of 1,240 ships in view", a thin proportion bar, and "1,220 more counted in density cells and +N chips").

- **Map switches:** Density view (on), Coverage gaps (on), Inland vessels (off), Labels (on), Depth (off).
- **Focus reasons switches:** Nearby, Possible rendezvous, Also dark, Same flag (all on); Same owner (n/a, needs data).

The switches are square indicator lamps with the state written as text, not phone toggles.

## Notes and risks

- Map geometry is illustrative: generated coastlines, not real Finland. The numbers in the rules are design proposals and need checking against live data (especially the cell breaks and the 0.5 nmi / 30 min rendezvous rule).
- In the Figma basemap options box, the `--` in the tippecanoe flags renders as a dash in Barlow. This report has the exact flags.

## Follow-up: shared variables and real ship icons

- **Bound:** 1,254 plain fills and strokes on my page now use DVM Theme or DVM Signals variables.
  - Water → `map/water` / `map/water-alt`
  - Land, coast, grid → `map/land`, `map/coast`, `map/grid`
  - Dash-dot national border → `map/border`
  - Section backgrounds → `bg/app`; panels and chips → `bg/panel`
  - Edges → `border/default`
  - Ink → `text/primary` / `text/secondary` / `text/muted`
  - Water and land names → `map/label-water` / `map/label-land`
  - Old amber caption text and the pale-blue inferred line and contours → `accent/default`; the "on land?" chips → `ship/spoof`
  - Magenta → `ship/dark`, with `ship/ghost-fill` and `ship/ghost-edge` for ghost regions
  - "No receiver" hatch → `coverage/dead`
  - Density cells → `text/primary` at low opacity
- **Modes:** the five section frames are set explicitly to DVM Theme = Dark (dusk) and DVM Signals = Standard.
- **Ships:**
  - All 266 `placeholder/ship-mark` instances were swapped for agent 2's **Ship marker** (`36:383`), keeping each one's position and rotation. The placeholder component and its parts frame were deleted.
  - Sizes: far for World, Region and the basemap frames; mid for Sea area and focus; near for Harbour.
  - States in the storyboards: 171 normal at far, 11 sanctioned and 20 spoofing at far, plus mid and near ones. The selected ships (Sea area, and Vessel A in focus) are `selected`.
  - 20 `dark` markers were added at the gap positions, including the "Also dark" fishing boat in focus.
  - Types are a seeded mix per scene: more inland in Region, more passenger and inland in Harbour.
  - The whole marker is rotated, so the selected brackets and the sanctioned badge rotate with the hull. In the app they must stay upright, as agent 2 specifies.
- **Layout change:** agent 2's smallest marker is 16 px long, about three times my placeholder. So the storyboard is now a 2 × 2 grid of 1140 × 774 panels, about 80 % of a 1440 × 980 viewport. The caps (100 / 100 / 40 / 20) are now drawn at the real icon size, and they still read calmly.
- **Opacity changes:**
  - Binding reset every paint's opacity, so I restored them by rule: chips at 92 %, range ring 30 %, leaders 18 %, graticule 50 %, contours 45 %, ghost edge 45–50 %.
  - The cell tints are lowered for the brighter dusk water: **5 / 9 / 14 / 22 %** (was 5 / 10 / 17 / 27 %). The ships now stay clearly on top.
  - The "no receiver" hatch uses `coverage/dead` at its built-in 24 %.
  - 49 stray black fills that the SVG import left on open line paths were removed; they would have shown in light mode.
- **Light proof:** "2b · Focus mode · Light · Colour-blind safe" is a clone of the focus map with only the modes changed. It sits to the right of section 2: https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=50-1104 (map: https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=50-1107). Text sizes are not bound to DVM Text size.
