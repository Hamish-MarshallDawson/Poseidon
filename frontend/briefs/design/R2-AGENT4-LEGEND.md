# Round 2 · Agent 4 report: legend

Page **R2 · 4 Legend**: https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=56-94
I worked only on this page. I created no variables or collections, and I edited nothing on other pages.

## What I made

| Node | Link | What |
|---|---|---|
| Title | https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=56-4599 | Page intro |
| 1 · Legend panel | https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=56-4602 | Compact and full panels in Dark · Standard and Light · Standard, plus compact in Dark · Colour-blind safe with a note on how it adapts |
| 2 · Legend toggle and placement | https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=56-5740 | Toggle closed/open in Dark and Light; two 1440 × 900 dashboard wireframes (Dark with compact open, Light with full open); placement rules |
| 3 · For the dashboard | https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=56-573 | The two component sets for agent 5 |
| **R2/Legend/Panel** (`Variant` = compact / full) | https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=56-574 | compact `56:95`, 480 wide, 3 entries per row, about 610 tall. full `56:301`, 1040 wide, 3 columns, about 640 tall |
| **R2/Legend/Toggle** (`State` = closed / open) | https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=56-3123 | closed `56:3103`, open `56:3113`; 36 px tall |

## Key decisions and why

- **Real symbols.** Every ship glyph is a live instance of round 1's **Ship hull** (`33:108`, mid size) or **Ship marker** (`36:383`, cargo, mid). If agent 2's icons change, the legend updates with them. Other glyphs (lines, hatching, chips) are drawn from the same variables the map uses.
- **Glyphs sit on a small water tile** (`map/water`, 48 × 40), so each symbol is shown against the same background as on the map. The round-1 contrast checks were made on water, so they hold here too.
- **Readability.** Entry names are `size/body` (14 px) Medium or SemiBold. Explanations are `size/body` Regular in `text/secondary`. Group heads are `size/label` uppercase in `text/muted`. All panel text is bound to DVM Text size (size and line height) and every container is auto-layout, so Large and Largest text make the panel grow instead of clipping. Each explanation in the full panel fits on one line at Default size (Track wraps to a second line).
- **Compact vs full.** Compact keeps the essentials in 5 groups: Ships (5 types), State (5), Position (3), Map (4) and Review and time (3), with labels only. Full adds Heading not known, Dimmed, Patchy reception, Track and Focus reason, and gives every entry one line of explanation. I first built compact two entries per row, but it was 786 px tall and didn't fit above the toggle on a 900 px viewport. At three per row it is 610 px.
- **Placement.** The toggle sits at the bottom-left of the map, 16 px from the map's left and bottom edges, just above the replay bar. That corner is free: the status line is at the top-left, and the review list and vessel card are on the right. The panel opens upward with an 8 px gap. "Show all" swaps compact for full in the same corner (1040 px fits the 1080 px map), and "Show less" swaps back. It closes with the toggle or Esc. It is not modal. On the first visit it opens compact, and after that it remembers the viewer's last choice. The toggle uses `aria-expanded` and `aria-controls`; the panel is a region named Legend.
- **Toggle look.** It follows agent 3's lamp-switch idea, not a phone toggle. A square lamp is hollow when closed and lit when open. Open also gets an `accent/subtle` fill and an `accent/default` edge, and the label "Legend" stays the same in both states.
- **Colour-blind mode.** Every swatch is bound to DVM Signals, so switching modes recolours the legend and the map together. No label names a colour, and every state also has its own shape, so the legend reads the same in both modes. The panel footer says: "Shapes carry the meaning; colour repeats it. Colours follow your theme and colour-blind setting."
- **Neutral wording throughout.** I renamed agent 3's focus reason "Also dark" to **"Also no AIS"** in my wording notes. See decisions below.

## Entry list (full name · one-line explanation · compact label)

| Group | Glyph | Full name | Explanation | Compact label | Status |
|---|---|---|---|---|---|
| Ship type | Hull tanker | Tanker | Oil, gas or chemical tanker. | Tanker | final (R1) |
| | Hull cargo | Cargo | Container ship or bulk carrier. | Cargo | final |
| | Hull fishing | Fishing | Fishing vessel. | Fishing | final |
| | Hull passenger | Passenger | Ferry or cruise ship. | Passenger | final |
| | Hull inland | Inland or other | Tug, service craft, inland or unknown type. | Inland, other | final |
| | Hull, heading unknown | Heading not known | No heading sent, so the mark isn't turned. | (full only) | final |
| Position: how sure | Solid ink line | Heard | Solid: from AIS messages we received. | Heard | final |
| | Dashed accent line | Inferred | Dashed: estimated between messages. | Inferred | final |
| | Hatched circle, dashed edge, × at last fix | Could be anywhere in here | Hatched: possible area since the last fix (×). | Could be in here | final |
| Ship state | Marker normal | Normal | AIS heard recently. | Normal | final |
| | Marker selected | Selected | Corner brackets: the ship you opened. | Selected | final |
| | Marker dark (hollow) | No AIS received | Hollow: silent; reception normal nearby. | No AIS received | final |
| | Marker spoofing | Possible spoofing | Solid where it reports, hollow where implied. | Possible spoofing | final |
| | Marker sanctioned | Sanctions match | Diamond: matches a sanctions list entry. | Sanctions match | final |
| | Marker normal at 45 % | Dimmed | Unrelated to the focused ship; click to focus. | (full only) | final (wording from R2 agent 1) |
| Ranked for review | risk/1–4 blocks | Risk 1–4 | Review band: 1 watch, 4 inspect first. | Risk 1–4 | final |
| | R2/Forecast/Probability tag (far in tile, mid beside name; Band 3) | Probability tag | Ranked for review: chance of a silence with reception normal nearby, next 6 h; tags only on the top-ranked watchlist ships. | Chance, next 6 h | final (R2 agent 3) |
| Map | 4 ink tints (5/9/14/22 %) | Ship density | Stronger tint, more ships heard in 10 min. | Ship density | final (R1 agent 3) |
| | "+31" chip | +N more here | Counted but not drawn, to keep the map clear. | +N not drawn | final |
| | R2/Stacking/Stack chip (mid, closed) | Stack of ships | Click: 2–8 fan out; from 9, a list opens. | Stacked ships | final (R2 agent 1) |
| | Hatched grey cell, dashed edge | No receiver here | Nothing heard for 10 min; we can't see here. | No receiver here | final |
| | coverage/degraded cell | Patchy reception | Fewer receivers in range; messages may drop. | (full only) | meaning guessed, see below |
| | Solid line with hour ticks → dashed | Track | Last 6 h, a tick each hour UTC; dashed inferred. | (full only) | final |
| | "Nearby" chip | Focus reason | Why a ship shows in focus mode. | (full only) | final |
| Timeline | Water tile with 2 px ink edge + agent 2's inverted REPLAY chip | Replay | Ink edge on map and bar: showing the past. | Replay | final (R2 agent 2) |

## Placeholders waiting on the other round-2 agents

Each one has a "DRAFT" tag in both variants. Remove the tag and adjust the glyph once the owning agent's report lands.
1. **Forecast probability tag** ("Chance of no AIS, next 6 h"): my guess is a mono "38%" chip with a 3 px bar in the matching `risk/n` colour. Waiting on: the forecast/watchlist agent's tag design, whether it shows % or a band, and its exact label wording.
2. **Stacked-ship count marker** ("Several ships at one spot"): my guess is an ink disc with the count in `bg/app` and an offset ring behind it. Waiting on: the stacking agent's marker and its click behaviour ("spread" or "zoom").
3. **Replay state** ("Replay"): my guess is an accent-outlined "REPLAY" chip. Waiting on: the replay/bottom-bar agent's live/replay indicator and wording.

## Decisions for Hamish

- **"Also dark" → "Also no AIS"** for agent 3's focus reason chip, to keep the wording neutral. Agent 3's page still says "Also dark".
- **Should the legend open by default on the first visit?** I say yes (compact), then remember the viewer's choice.
- **"Patchy reception" (`coverage/degraded`)**: agent 1 drew it, but I found no data rule for it. I guessed "fewer receivers in range; messages may drop". Either confirm a rule (for example, a CoverageCell with a message rate below some threshold) or drop the entry.
- The full variant is 1040 × 640 and covers most of the map while open. That's intended for a reference view, but the alternative is opening it in the right-hand panel instead.

## Gaps in the variables

- **`focus/dim-opacity` can't be bound to opacity as stored.** It holds 0.40–0.45, but Figma reads an opacity binding as a percent, so the dimmed ship rendered at 0.45 %. I set that glyph to a plain 45 % instead. Fix: store the values as 40 / 45 / 35 / 35 (percent), or keep the fraction for code and add a percent twin.
- **No role for density tints.** I followed agent 3: `text/primary` at a node opacity of 5 / 9 / 14 / 22 %. Paint opacity on a bound paint didn't show in my renders (the cells came out solid), so I used node opacity. `density/1–4` variables would make this robust.
- **No role for hatching lines.** I used `text/muted` at 40 % on "no receiver" and `ship/ghost-edge` at 45 % on the gap circle.
- **No role for the inferred line.** I used `accent/default`, as agent 3 did. A `track/inferred` role would stop it changing if the accent changes.
- **Glyph text isn't bound to DVM Text size.** The "+31", "Nearby", "38%", "REPLAY" and "5" text inside the 48 × 40 tiles are fixed at 10–12 px, so the tiles stay map-sized. All other text is bound.
- **The page background is hard-coded** to the dusk `bg/app` hex (`#15232d`), because Figma page backgrounds can't take variables. Every frame is bound.

## Follow-up: stacking agent landed (R2 · Agent 1)

- **Stack entry is final.** The drawn guess is replaced, in both Panel variants, by an instance of **R2/Stacking/Stack chip** (`55:50`, `Size=mid, State=closed`, 45 × 20, centred in the 48 × 40 water tile). New instances: `58:1741`, `58:1748`.
  - Full: **"Stack of ships"**, with "Click: 2–8 fan out; from 9, a list opens."
  - Compact: the label stays "Stacked ships".
  - The DRAFT tag is removed from both variants.
- **Dimmed wording now matches agent 1's Context step:** "Unrelated to the focused ship; click to focus." It was "Not related to the ship in focus." The glyph stays at 45 %, agent 1's Dark value. Their Light value is 40 % and high contrast is 35 %. I can't bind this per theme because of the `focus/dim-opacity` scale gap, which agent 1 reports too.
- **Still DRAFT:** "Chance of no AIS, next 6 h" (forecast tag) and "Replay". They are waiting on their agents' reports.
- **Every instance updated:** sections 1 and 2 and the dashboard set all use the component, so they all changed. Nothing outside page `56:94` was touched.
- **Not covered:** agent 1's Routine (80 %) and Trace (20 %) emphasis steps and the fan-out leaders have no legend entries. Add them if Hamish wants every map state explained. I'd skip Trace: it only shows while a fan-out is open.

## Follow-up: timeline agent landed (R2 · Agent 2)

- **The Replay entry is final, and its DRAFT tag is gone.**
  - The glyph is now a water tile with a 2 px `text/primary` inner edge, the same as agent 2's map edge.
  - Next to the name sits agent 2's real inverted ink **REPLAY chip**.
  - Wording: "Ink edge on map and bar: showing the past."
  - In compact, the REPLAY chip replaces the DRAFT tag under the "Replay" label.
- **New "Timeline (bar under the map)" group, in the full variant only.** It is a full-width row of 3 columns under the main columns. It replaces my old "Time" group.
  - **Shown time:** agent 2's "AS OF 13:05:12Z" chip. "Popups and lists show values as of that time."
  - **No AIS received (span):** a closed span over an open, dashed one. "Start to end; dashed edge while still silent."
  - **Possible spoofing (triangle):** "Position looked false at this time."
  - **Meeting (ring):** "Two ships alongside each other."
  - **Forecast frozen (line and flag):** "Committed Sat 23:00Z; never changed after."
  - **Outcome: hit, miss, censored (filled, hollow and dashed squares):** "Filled hit, hollow miss, dashed can't tell."
  - **Coverage strip (under track):** four segments. "Solid: logged. Dotted: weak reception. Hatched: our feed stalled. Dashed: not in our log." This is the only entry that runs past one line; four states don't fit in one.
- **Glyphs are agent 2's own nodes, copied, not drawn by me.** I instanced `R2/Timeline/Bar` (`State=replay, Range=24 h`, `56:1500`) on my page, detached that copy, took its gap, spoofing, meeting, frozen, outcome and coverage nodes, and deleted the rest. I copied the AS OF chip from `57:6400`. Their bindings came with them.
  - These are copies, not instances, so they won't follow later edits on agent 2's page. Making them components there would fix that.
  - Timeline glyphs sit on `bg/panel` tiles (the bar's surface) rather than water, so they read as bar symbols, not map symbols.
- **Size problem: the full variant is now 1040 × 870.**
  - With a 56 px top bar and agent 2's 88 px timeline bar, the map in a 900 px window is about 756 px tall.
  - So the full legend must be capped at the map height and scroll its body, with the header (Show less) staying put. I added this to the placement note in section 2.
  - The Light wireframe now shows the full panel capped and clipped (`56:6090`). That wireframe still uses my older 56 px placeholder bar, not agent 2's bar.
- **Wording to align: agent 2 says "Meeting"; agent 3 says "Possible rendezvous".** I kept agent 2's word on the timeline. Hamish should pick one.
- **Still DRAFT:** "Chance of no AIS, next 6 h" (forecast tag) only.
- **Section positions:** sections 2 and 3 were moved down so nothing overlaps. Nothing outside page `56:94` was edited. The temporary detached copy and the AS OF clone were removed; the AS OF clone only passed through agent 2's frame inside a single script.

## Follow-up: forecast agent landed (R2 · Agent 3)

- **Forecast tag is final. No DRAFT tags remain on the page.**
  - Full: the entry is now **"Probability tag"**, using the requested wording: "Ranked for review: chance of a silence with reception normal nearby, next 6 h; tags only on the top-ranked watchlist ships." It runs to 3 lines; this is the one entry I let run long, because the wording was asked for word for word.
  - The glyph is real instances of **R2/Forecast/Probability tag** (`56:56`, Band = 3, matching agent 3's 61 % example):
    - The `Zoom=mid` tag (57 × 18) is too wide for a 48 px tile, so it sits beside the name (full) or under the label (compact).
    - The tile holds the `Zoom=far` tag (rank only), so the legend also shows how the tag looks zoomed out.
  - Compact keeps the label "Chance, next 6 h".
- **Silence vs coverage hole, now clearly two entries.** Both use agent 3's **R2/Forecast/Ghost region** (`56:76`), resized to 38 px, not rescaled:
  - **Could be anywhere in here:** `Kind=No AIS`, magenta. "Silent, reception normal; area since last fix." This replaces my drawn ghost in both variants.
  - **No AIS in a coverage hole (new, full only):** `Kind=Coverage hole`, grey. "Grey: we can't hear there; not counted." It sits right under the magenta one, so the two read as a pair.
  - **"No receiver here"** stays as a separate entry: a dead cell with no ship, matching agent 3's `R2/Forecast/Coverage hole` (`56:77`). I kept my drawn tile, which has the same grammar (grey, hatched, dashed edge, no cross).
  - At 38 px, the ghost region's fixed-size hull and course line crowd the circle. It is legible, but busier than the other tiles. A small "legend" variant from agent 3 would fix this.
- **Wording choice: "Possible rendezvous" on the map, "Meeting" only on the timeline.** The glyphs differ: a reason chip on the map, a 9 px ring on the timeline.
  - Focus reason now reads "Why shown: Nearby, Possible rendezvous, …".
  - The timeline entry reads "Ships alongside; map: Possible rendezvous." so the two terms are linked.
- **Size:** the full variant is now 1040 × 920. The placement note in section 2 is updated, and it still says to cap the panel at map height and scroll it. Sections were re-stacked so nothing overlaps.
- **Not checked:** I haven't checked the contrast of agent 3's grey ghost on `map/water` in the Light and high-contrast themes. Nothing outside page `56:94` was edited.
