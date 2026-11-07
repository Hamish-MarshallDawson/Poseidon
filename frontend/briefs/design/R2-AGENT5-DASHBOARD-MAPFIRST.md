# R2 · Agent 5 report: map-first dashboard (round 2b)

Page **"R2 · 5 Dashboard"**: https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=56-2506

This follows Hamish's map-first direction, which overrides the sidebar layout:
- The whole screen is the map.
- The scrub bar floats at the bottom.
- Everything else drops in when you click.
- Ships open in floating windows.

I worked only on my page and created no variables. Every fill, stroke and text colour I drew is bound to DVM Theme or DVM Signals, and every text size and line height I set is bound to DVM Text size.

**Basemap: done.** Every map-first frame (4a–4d, 5, 6, 7a, 7b) now sits on the real **`R2/Basemap/Baltic`** (`70:2`: Natural Earth 10m, 1440 × 900, lon 4–36, lat 54.38–64.46). My drawn land, water, coast, borders and place names are deleted. See "Basemap move" below.

## Frames (all 1440 × 900; new work starts at x = 7000)

| Frame | Light | Dark |
|---|---|---|
| 4 · Map-first, legend open, one ship window | [4a](https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=67-10483) | [4b](https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=67-11383) |
| 4 · Map-first, legend closed, one ship window | [4c](https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=67-12283) | [4d](https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=67-13047) |
| 5 · Compare: 2 windows open + 1 minimised | [5](https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=67-13811) | |
| 6 · Watchlist dropped in | [6](https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=67-14713) | |
| 7 · Replay at 13:05:12Z | [7a](https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=68-16538) | [7b](https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=68-17368) |

- Every frame sets DVM Theme (Light or Dark), DVM Signals = Standard and DVM Text size = Default.
- **The old sidebar layout is retired.** Its 16 frames and titles (grid, 2a–2e, 3a–3b) are in the section [Superseded · sidebar layout](https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=68-18198). They are kept for reference and can be deleted.

## Screen layout (map-first)

| Element | Where | Component |
|---|---|---|
| Map | full bleed, 1440 × 900, on `R2/Basemap/Baltic` | `R2/Dashboard/Map · Baltic full screen` ([66:14309](https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=66-14309)) |
| Status line (minimal) | top-left, 16 px inset | in `R2/Dashboard/Map controls · live` ([66:21908](https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=66-21908)): "● LIVE 14:07:12Z · 100 of 2,184 ships in view · 375 in stacks, 1,709 in cells · 3 cells without coverage" plus the "Illustrative data" tag |
| Watchlist summon chip, Layers button | top-right | `R2/Dashboard/Watchlist chip` ([66:21907](https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=66-21907)), State closed / open |
| Zoom, scale | right edge | in Map controls |
| Scrub bar | floating, centred at the bottom: x 240, y 836, 960 × 48 | `R2/Timeline/Bar` (agent 2's simplified bar, updated in place). State live, or replay in 7a/7b |
| Legend toggle | bottom-left, centred on the bar's row | `R2/Legend/Toggle` |
| Legend overlay | above the toggle, 8 px gap | `R2/Legend/Panel` compact (now about 480 × 330) |
| Minimised windows | pills above the legend toggle, along the bottom-left edge | Ship window State=minimised |
| Watchlist drop-in | below the chip, top-right, 360 × 666 (no scrolling needed now) | `R2/Forecast/Watchlist panel` |
| Ship windows | default: the free side nearest the ship, with no ship under it | `R2/Dashboard/Ship window` |

Only the status line, the top-right buttons, the legend toggle and the scrub bar are on screen all the time. Everything else appears on demand.

## The ship window ([component set 66:21898](https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=66-21898))

- **Chrome (title bar):**
  - a 6-dot drag handle;
  - the **ID badge** (`R2/Dashboard/Ship ID badge`, [66:21744](https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=66-21744)): a letter on `ship/selected` with `text/on-accent`;
  - name (SemiBold) and type;
  - minimise (–) and close (×).
- **Component properties:** `Name` and `Type`. The badge has its own `ID` property.
- **Body:** an `R2/Forecast/Ship card` instance (agent 3, now 320 wide). The window hugs the card, so it is 322 × 495. Set the card's `State` (No AIS or Active) on the nested instance.

| Variant | Node | Look |
|---|---|---|
| open | [66:21746](https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=66-21746) | `bg/panel`, 1 px `border/default`, title bar `bg/raised` |
| dragging | [66:21812](https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=66-21812) | Lifted: 2 px `border/strong` and an `accent/subtle` title bar. No shadow variable exists, so I used no shadow |
| minimised | [66:21878](https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=66-21878) | 173 × 38 pill: handle, badge, name, restore (▢), close. It docks along the bottom-left edge above the legend toggle |
| closed | [66:21896](https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=66-21896) | Nothing drawn. The ship's highlight and badge are removed from the map |

### How a window is tied to its ship

- **Always on:** the ship gets two marks on the map, and they stay until the window is closed (minimised windows keep them):
  - the **selected corner brackets** (upright Ship overlay, `ship/selected`);
  - the same **letter badge** as the window, placed up and to the left of the hull.
- **Only for the front window** (the one clicked last), and for any window while the pointer is over it: a **1 px leader line** in `ship/selected`, from the nearest window edge to the ship, ending in a 5 px dot at the window.
- **Why:** with two or three windows open, several leaders cross each other and cross the ships between them. They quickly become the noisiest thing on the map. Letters scale to many windows, still work when a window is minimised, and read without colour. The single leader answers "which ship is this?" for the window you are using now.
- **Frames:** frame 5 shows this. A (front) has a leader; B and C (minimised) have letters and brackets only.

### Several windows

- **Stacking:** the last clicked window is on top.
- **Limit:** at most 4 open at once. Opening a 5th minimises the oldest, so it moves to a pill instead of vanishing.
- **Where a new window opens:** on the side of the ship with more free map, never over the ship itself, and offset 24 px from the window before it so title bars never hide each other.
- **Comparing:** drag windows side by side. Frame 5 shows NORDIC HAVEN (B, Active) and AURORA BAY (A, No AIS) open, with KESTREL (C) minimised.

## The map ([66:14309](https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=66-14309))

- **Extent and zoom:** the Baltic at about z5, on `R2/Basemap/Baltic`: lon 4–36, lat 54.38–64.46, Web Mercator.
- **Layers, from bottom to top:**
  1. `R2/Basemap/Baltic`, with its labels hidden;
  2. density cells, coverage holes and the graticule;
  3. a second `R2/Basemap/Baltic` with its water hidden. It redraws the real land, the dotted borders and the labels over the cells, so cells never tint land;
  4. "Overlay": cell counts, extra port labels, ghosts, stacks, ships and tags.
- **Ships:** 100 Ship marker icons, the cap for z4–6, in slot-priority order. Every ship is counted once: 375 in 5 stack chips plus 1,709 in 0.5° cells, so 100 + 375 + 1,709 = 2,184. The status line says the same.
- **Stacking (agent 1):** keyline on every hull and overlay; routine ships at 80 %; `R2/Stacking/Stack chip` at five anchorages.
- **Forecast (agent 3):**
  - **Probability tags:** `R2/Forecast/Probability tag`, far zoom, rank only, on ranks 01, 02, 04 and 05.
  - **Open gaps:** AURORA BAY (rank 03), Vessel C and Vessel G get `R2/Forecast/Ghost region` instead of a tag. Each ghost is sized from `radius_m` at map scale, with its 40 px inner hull hidden at this zoom.
  - **Gap labels:** `R2/Forecast/Gap label` on each gap. When a ship's window is open, its gap label is hidden, because the window already says the same thing.
  - **No receiver:** `R2/Forecast/Coverage hole` on the 3 cells with no receiver.
- **Replay (7a/7b):**
  - 2 px ink edge around the screen, and a REPLAY tab I drew myself, because agent 2's tab node no longer exists.
  - Agent 2's replay status line. `R2/Timeline/Bar` with State=replay.
  - Nothing after 13:05:12Z is drawn: AURORA BAY and Vessel G are heard (no ghost); Vessel C's ghost shows as of 13:05, at 1 h 08 min.
  - Window A shows the card in State=Active, "as of 13:05Z".

## Which slots use which agents' components

| Agent | Component | Used in |
|---|---|---|
| R1 · 2 | Ship marker `36:383`, Ship overlay `33:127` | every map; window highlights |
| R2 · 1 | Stack chip `55:50`, keyline and opacity rules | map |
| R2 · 2 | Timeline/Bar `56:2502` (live, replay); replay status line `57:6232` (copied) | every frame |
| R2 · 3 | Probability tag `56:56`, Ghost region `56:76`, Gap label `56:93`, Coverage hole `56:77`, Watchlist panel `56:4359`, Ship card `56:4598` | map, window body, watchlist drop-in |
| R2 · 4 | Legend/Toggle `56:3123`, Legend/Panel `56:574` (compact) | every frame |
| R2 · 5 (mine) | Ship window, Ship ID badge, Watchlist chip, Map controls, Map · Baltic full screen | |
| Coastline agent | `R2/Basemap/Baltic` `70:2` | the map component (two instances), so every map-first frame |

## Basemap move

- **Frames moved** (all eight map-first frames, through the one map component): 4a, 4b, 4c, 4d, 5, 6, 7a and 7b, in Light and Dark. The basemap follows each frame's DVM Theme mode.
- **Ships re-placed from lon/lat** with the basemap's formula. Each position was tested against the real land path (12,994 edges, even-odd).
  - Every generated ship that fell on land was rejected and redrawn in water, so **0 of 100 icons sit on land**.
  - Of the named ships, only U1 (St Petersburg anchorage, heading unknown) had to move: 6 px into water.
  - The lanes and scene are the same as before (Skagerrak and Kattegat → Öresund and Great Belt → Bornholm → east of Gotland → Gulf of Finland → Primorsk, Ust-Luga and St Petersburg, plus the Bothnian Sea, Riga, Klaipėda, Gdańsk, Stockholm–Turku and Helsinki–Tallinn).
- **Southern edge:** the basemap stops at 54.38°N, so the German and Polish coast south of that is off-map. Gdańsk roads is still in view.
- **Place labels are now the basemap's own real labels:**
  - water names: Baltic Sea, Gulf of Bothnia, Gulf of Riga;
  - countries: Finland, Sweden, Estonia, Latvia, Russia, Norway;
  - cities: Helsinki, Tallinn, Stockholm, St Petersburg, Riga.

  I hid its "Gulf of Finland" label with an override, because it sat on the ranked ships. I added mono labels for the real ports the scene uses: Primorsk, Ust-Luga, Klaipėda, Copenhagen and Gothenburg. My invented labels are gone.
- **Window links moved with the ships:** AURORA BAY (A) is now at (1008, 438), NORDIC HAVEN (B) at (655, 723) and KESTREL (C) at (945, 451). Window A moved to (1102, 330), right of its ship, with a horizontal leader.
- **Replay overrides re-applied:** A and G heard, their ghosts and labels hidden, and C's ghost redrawn for 13:05Z at 23 km.
- **Not moved:** the 8 superseded sidebar frames in the "Superseded" section (map 1080 × 768, old component `56:2507`) still use my drawn coast. **Question:** no basemap is 1080 × 768. Should I ask the coastline agent for one, or just delete the superseded frames?

## Decisions for Hamish

0. **The Gulf of Finland is crowded at overview zoom.** Four ranked ships, three stacks and AURORA BAY's window share the eastern gulf, and window A covers the Primorsk, Ust-Luga and St Petersburg stacks. Should opening a ship window also fly the map to the Gulf of Finland (`R2/Basemap/Gulf of Finland`, z7, cap 40), where the windows would fit over land?

1. **Leader lines:** one line for the front window only (my choice), or one for every open window?
2. **Window limit:** 4 open, with the oldest minimised when a 5th opens. Is that enough for comparing?
3. **Where windows open:** beside the ship, as drawn, or always in one place (for example top-right) so the eye knows where to look?
4. **Gap labels at overview zoom:** the 280 px labels are heavy at z5. Show them only on hover, or for the selected ship (whose window then replaces them)?
5. **The watchlist chip** shows "Ranked for review · next 6 h · 5". Should it also flag a change (for example "1 new") so people know when to open it?

## Inconsistencies between agents (unchanged)

- **AURORA BAY's last AIS time:** agent 3's card says 13:15:04Z, but its 00:47:12 timer at 14:07:12Z means 13:20Z, which agent 2 also uses. The live windows show agent 3's text as it is.
- **Agent 2's "Map in replay" REPLAY tab** (`57:6229`) has been removed from its page; I drew an equivalent.

## Gaps in the variables

- **No shadow or elevation role.** The dragging state uses a stronger border instead. A `shadow/lift` effect colour would let floating windows lift properly.
- **Paint opacity is lost when a colour is bound,** so I used node opacity for cells and hatches.
- **No replay role.** I used `text/primary` for the edge and the inverted tab.
- **No feed-health roles.**

## Known limits

- I screenshotted 4b, 5, 7a, and 5 and 7b again after the basemap move. The other frames share their components, so I checked them only through their structure.
- The parts from the sidebar layout (old map `56:2507`, top bar, placeholders) are still on the page below the Superseded section. Only the superseded frames use them.
