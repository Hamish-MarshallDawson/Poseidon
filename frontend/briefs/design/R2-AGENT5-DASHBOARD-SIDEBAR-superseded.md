# R2 · Agent 5 report: full dashboard compositions

Page **"R2 · 5 Dashboard"**: https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=56-2506
I worked only on this page. I created no variables. Every fill, stroke and text colour is bound to DVM Theme or DVM Signals, and every text size and line height is bound to DVM Text size.

## Status of the round-2 components

**In:** R2 · 1 stacking, R2 · 4 legend and R2 · 2 timeline.
**Still waiting:** R2 · 3 forecast and watchlist.

Each slot that is still waiting is a local component with a dashed "placeholder · R2 · n" tag. Swapping in the real part is one edit, and every composition updates with it.

| Slot | Now | Final when |
|---|---|---|
| Top status | **final** (`R2/Dashboard/Top bar`) | n/a |
| Map, basemap and ships | **final**: real Ship marker instances with the **R2 · 1 stacking rules applied** (see "Stacking on the map" below) | n/a |
| Map chrome (status line, Layers button, zoom, scale) | **final** | n/a |
| Layers pop-over | **final** (round-1 agent 3 panel, copied) | n/a |
| Legend | **final**: `R2/Legend/Toggle` State=open plus `R2/Legend/Panel` Variant=compact in 2a and 2b; Toggle State=closed in 2c, 2d and 2e. Agent 4's placement: 16 px from the map's left and bottom edges, panel opens upward with an 8 px gap | n/a |
| Selected ship card | **final** | could take `R2/Forecast/...` if R2 · 3 makes a card part |
| Watchlist | placeholder | `R2/Forecast/...` (R2 · 3) lands |
| Rank tags on the map ("01"–"05") | placeholder | `R2/Forecast/...` map overlay (R2 · 3) lands |
| Timeline | **final**: `R2/Timeline/Bar` (`56:2502`), 1440 × 88. State=live, Range=6 h in 2a–2e; State=replay, Range=6 h in 3a and 3b | n/a |
| Replay frames (one per theme) | **final** (3a, 3b), except for the forecast placeholders inside them | n/a |

These parts are no longer used: the legend placeholders (`56:9263`, `56:9333`) and the timeline placeholder (`56:9230`). They stay on the page as parts, and can be deleted.

## Timeline and replay (R2 · 2)

- **The bar is 88 px tall** instead of the 112 I had reserved. I gave the extra 24 px to the map (now 1080 × 768) and to the selected ship card (now 364 tall). The legend moved down by 24 px with its toggle.
- **The clock now matches agent 2's example:** Sun 8 Nov 14:07:12Z.
- **Replay frames 3a (Light) and 3b (Dark) show 13:05:12Z, 1 h 02 min behind live.** They are copies of 2c and 2d (legend closed), with agent 2's "Map in replay" treatment (`57:6177`, `57:6362`):
  - **Bar:** State=replay, so it shows the REPLAY chip, "Back to live" and the ink playhead.
  - **Map edge and tab:** a 2 px `text/primary` edge around the map, and agent 2's REPLAY tab ("showing Sun 8 Nov 13:05:12Z · not live"). I moved the tab off-centre, to the right of the status line, so it isn't covered. Agent 2 centres it.
  - **Status line, replay form:** agent 2's component reads "REPLAY 13:05:12Z · −1 h 02 min · 100 of 2,141 then · raw log · paused". It replaces my live status line.
  - **"As of" popup:** agent 2's popup, filled in for Vessel A. It shows last heard 13:04:51Z (21 s before the shown time) and forecast 71 % (rank 1). Its blue live-now footer reads "no AIS received since 13:20Z (47 min); reception normal nearby".
  - **Top bar:** an inverted ink REPLAY pill. Stats read "In view then 2,141", "Source raw log" and "No AIS then 1", and the clock shows 13:05:12Z.
  - **Card:** an "AS OF 13:05Z" tag, with last heard 13:04:51Z instead of the No AIS timer. Its live-now line matches the popup.
  - **Watchlist subtitle:** "as of 13:05:12Z".
- **Nothing after the shown time is drawn.** Vessel A (silent from 13:20Z) and Vessel G (silent from 13:42Z) are back to normal hulls, and their gap circles and chips are hidden. Vessel C's gap is redrawn smaller, at 1 h 08 min as of 13:05Z. Figma won't move a layer inside an instance, so the smaller circle is drawn on the frame, without the hatch.

## Stacking on the map (R2 · 1 rules)

- **Keyline:** every hull and overlay instance has agent 1's far keyline: 1 px, 8 zero-blur shadows bound to `bg/app`.
- **Opacity steps:** full strength (100 %) for tiers 0–5, which is 21 nodes: the selected ship, ranks 01–05, open gaps, spoofing, sanctioned and their overlays. **Routine 80 %** for the other 86. There is no focus in these frames, so no ship is at Context or Trace.
- **Stack chips:** `R2/Stacking/Stack chip` (far, closed) at the five crowded anchorages:
  - St Petersburg 10
  - Ust-Luga 18
  - Primorsk 14
  - Gdańsk roads 9
  - Copenhagen roads 7
- **The fold is consistent.** The chip ships are taken out of their 0.5° cell counts (the St Petersburg cell is now empty and removed). 100 icons + 58 in stacks + 2,026 in cells = 2,184, which matches the status line. The layers pop-over now says "2,084 more: 2,026 in density cells, 58 in stack chips".
- **Draw order:** the chips sit below the ship layer, so a full-strength ship is never hidden by a chip (agent 1's rule).
- **Not shown:** the fan-out and the stack list. They only appear after a click, so they don't belong in a resting map view. A focus-mode frame could show them later.

## Frames

- [1 · Grid & slots](https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=57-255), with the [grid notes](https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=57-292) beside it
- [2a · with legend · Light](https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=57-293)
- [2b · with legend · Dark](https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=57-1130)
- [2c · legend closed · Light](https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=57-1967)
- [2d · legend closed · Dark](https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=57-2744)
- [2e · Layers pop-over open · Light](https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=57-3521) (extra)
- [3a · Replay at 13:05:12Z · Light](https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=59-12861)
- [3b · Replay at 13:05:12Z · Dark](https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=59-13885)

Each composition sets DVM Theme (Light or Dark), DVM Signals = Standard and DVM Text size = Default explicitly on the frame.

The parts (local components, below the compositions at y ≥ 4000) are: [Map](https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=56-2507), [Top bar](https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=56-9080), [Watchlist (placeholder)](https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=56-9112), [Selected ship card](https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=56-9192), [Timeline (placeholder)](https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=56-9230), [Legend (placeholder)](https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=56-9263), [Legend toggle (placeholder)](https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=56-9333), [Map chrome](https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=56-9334) and [Layers pop-over](https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=56-9422).

## Grid and slot sizes (1440 × 900)

| Slot | x, y | Size | Notes |
|---|---|---|---|
| Top status | 0, 0 | 1440 × 44 | Mode (LIVE / REPLAY), ships tracked, in view, messages per second, No AIS now, possible spoofing, on sanctions list, feed sources, an "Illustrative data" tag, UTC clock |
| Map | 0, 44 | 1080 × 768 | Nothing docks over it |
| Watchlist | 1080, 44 | 360 × 404 | 5 rows plus a footer with the honest check |
| Selected ship card | 1080, 448 | 360 × 364 | |
| Timeline (R2/Timeline/Bar) | 0, 812 | 1440 × 88 | Full width, always visible; its tooltips overflow upward onto the map |
| Status line and Layers button | 12, 56 | floating | |
| Layers pop-over | 12, 56 | 340 × 705 | Covers the status line, which it repeats |
| Legend (R2/Legend/Panel, compact) | 16, 142 | 480 × 610 | Opens upward from its toggle with an 8 px gap |
| Legend toggle (R2/Legend/Toggle) | 16, 760 | ~110 × 36 | |
| Zoom | top right of the map | | |
| Scale bar | bottom right of the map | | |

**Reasoning.** The reading order is:
1. Is the feed live? (top bar). If a source is down, everything else is suspect.
2. Where is something happening? (map)
3. What should I review first? (watchlist)
4. Why this ship? (card)
5. When did it happen? (timeline)

Layout choices:
- The ranked list and the card sit in a fixed right column, so they never cover ships.
- The timeline runs full width, which gives agent 2's track room for 6 h at the default range.
- The only things that float on the map are the legend and the layers pop-over, and both use the **west edge** (Denmark, Kattegat, south Sweden, west of 15°E). That is outside the scoring box (19–31°E, 54–61°N), so a pop-over can never hide a ranked ship.

## The map

- **Baltic at about z5** (agent 3's Region band, cap 100).
- **Ships:** exactly **100 Ship marker instances** (far size) out of 2,184 in view. Slot priority is followed:
  - the selected ship;
  - watchlist ranks 01–05;
  - 3 open gaps;
  - 2 possible spoofing;
  - 6 sanctioned;
  - 2 with heading unknown;
  - then large ships;
  - then the rest.
- **Spacing and density cells:** icons are never closer than 24 px (1.5 × icon length). The other 2,084 ships are counted in 0.5° cells, masked to the water, using agent 3's 4 ink tints. Counts are printed on the 6 busiest cells.
- **Traffic:** ships are placed along real shipping lanes (Skaw → Öresund and Great Belt → Bornholm → east of Gotland → Gulf of Finland → Primorsk, Ust-Luga and St Petersburg, plus Gdańsk, Klaipėda, Riga, Stockholm–Turku and Helsinki–Tallinn) and at anchorages. The positions are seeded, so a rebuild reproduces them.
- **No-receiver cells:** 3 cells are hatched with a dashed edge, in neutral grey and never magenta.
- **Open gaps:** each has a dashed, hatched "could be anywhere in here" circle sized from `radius_m`, and a neutral chip such as "No AIS 47 min · within 16.6 km".
- **Basemap:** Mercator, with a hand-simplified coastline, 9 islands, dash-dot borders, Caslon water and land names, mono city names, and a graticule.

## Key decisions and why

- **Overlays stay upright.** For selected and sanctioned ships I rotate the Ship marker (`State=normal` or `dark`) to its heading, and add an **upright Ship overlay** (`33:127`) instance on top. This follows agent 2's rule that brackets and badges never rotate. Agent 3 had rotated the whole marker.
- **The selected ship (Vessel A) has three states at once:** No AIS, sanctioned and rank 01. So the card shows a hollow hull with brackets and a badge together, which tests that the encodings combine.
- **Neutral wording throughout:** "No AIS received for", "Reception normal nearby: 14 ships heard within 20 km (16 before)", "Ranked for review", "Possible spoofing".
- **The watchlist footer states the honest number.** It shows the prospective check with its Wilson interval ("top 10 → 6 had a gap (95 % CI 31–83 %)") and the three baselines from EVALUATION-PLAN.md, not a bare "7 hit".
- **The layers pop-over is agent 3's own panel, copied.** Only its numbers changed (100 of 2,184, cap 100). It is the same height as the map, so it opens at the status line instead of below the button.

## Decisions for Hamish

1. **Timeline width:** keep it full width (my choice, for a longer scrub track), or only under the map (which gives the right column the full 856 px height)?
2. **Default zoom:** should the dashboard open on the whole Baltic (z5, 100 icons plus cells, as drawn), or on the Gulf of Finland (z7, cap 40), where most ranked ships are?
3. **The compact legend is large.** At 480 × 610 it reaches 19°E, so it now covers Gotland, the rank-05 ship (Vessel K) and part of the open gap east of Gotland. My grid note that the pop-overs stay west of 15°E no longer holds while the legend is open. Options:
   - a narrower compact variant (2 per row, about 300 wide) that fits west of 15°E;
   - opening the legend in the right column instead;
   - accepting it, because the legend is closed by default after the first visit.
4. **"Illustrative data" tag:** keep it in the top bar for the demo?
5. **Hamish's input needed:** the watchlist numbers and names are placeholders ("Vessel A", made-up MMSIs). They need real values on demo day.

## Gaps in the variables

- **Paint opacity is lost when a colour is bound.** Agent 3 hit this too: binding a variable to a paint resets the paint's opacity, so I used node opacity for the density cells, hatches and graticule. A translucent role (for example `bg/panel-overlay` at 92 %) would let chips over the map be see-through.
- **No role marks replay mode.** The replay frames will need one. Until there is a variable, I plan to use `border/strong` plus text.
- **No feed-health roles** (up, degraded, down). The source lamps use `text/secondary`.
- **No role for text on the signal colours.** Tags use a signal-coloured border with `text/primary` text instead.

## Known limits

- The coastline is hand-simplified, so it is not chart accurate.
- The Gulf of Finland label sits close to the Primorsk label.
- I added the stack chip counts by hand at the anchorages. They are not the output of a real clusterer.
- I checked the layers pop-over frame (2e) only through its structure, not with a screenshot.
