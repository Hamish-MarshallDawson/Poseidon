# Round 2 · Agent 3 report: forecast overlay

Everything is on the new page **R2 · 3 Forecast overlay** ([page](https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=56-2)) in the Hacktheburgh file. I changed nothing on any other page. I created no variables or collections. Every fill, stroke and text colour is bound to DVM Theme or DVM Signals. Every text node I made has its font size and line height bound to DVM Text size. All forecast and outcome numbers are illustrative. The Wilson intervals are computed correctly from those illustrative counts.

## What I made

| Frame | Link | Contents |
|---|---|---|
| Read me | [59:402](https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=59-402) | Four principles: what p means, a ranking not a verdict, silent is not guilty, honest scoring |
| 1 · Probabilities on ships | [58:3638](https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=58-3638) | Rules column, plus a mid-zoom map sample: [Dark](https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=58-3677) and [Light](https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=58-9107). The map has tags, a selected ship, an open-gap ghost, and a ship lost in a coverage hole |
| 2 · Could be anywhere in here | [Dark 59:418](https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=59-418) · [Light 59:3301](https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=59-3301) | The ghost growing at 10 min, 47 min and 2 h. A comparison of three cases: No AIS with reception normal, No AIS inside a coverage hole, and a coverage hole with no ship. Plus a note on `own_stall` |
| 3 · Watchlist and ship card | [59:659](https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=59-659) | The 360 px right column, plus the No AIS and Active ship cards, in Dark and Light |
| 4 · Sunday morning | [59:1144](https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=59-1144) | The forecast vs outcome card in Dark and Light, and the watchlist footer in its Running and Scored states |
| 5 · Components | [56:3](https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=56-3) | The main components for agent 5 |

## Components (for agent 5)

Each component's description carries its rules.

| Name | Node | Variants / size |
|---|---|---|
| `R2/Forecast/Probability tag` | [56:56](https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=56-56) | Zoom = far / mid / near × Band = 1–4. Text properties: Rank, Chance, Reason |
| `R2/Forecast/Ghost region` | [56:76](https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=56-76) | Kind = No AIS / Coverage hole. Resize the instance (don't rescale it): the circle scales, while the hatch spacing, hull and cross stay fixed |
| `R2/Forecast/Gap label` | [56:93](https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=56-93) | Kind = No AIS / Coverage hole. 280 wide. Change the texts headline, context and detail |
| `R2/Forecast/Coverage hole` | [56:77](https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=56-77) | A dead CoverageCell: grey, square, hatched. Resizable |
| `R2/Forecast/Watchlist row` | [56:4339](https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=56-4339) | Kind = Inspect / Watch / No AIS now. 360 wide |
| `R2/Forecast/Watchlist panel` | [56:4359](https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=56-4359) | 360 wide, for the right-hand column of the 1440 px dashboard: a header, five rows and the test summary |
| `R2/Forecast/Test summary` | [56:4358](https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=56-4358) | State = Running / Scored. This is the watchlist footer; it replaces "Backtest top 10: 7 hit · baseline 3" |
| `R2/Forecast/Ship card` | [56:4598](https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=56-4598) | State = No AIS / Active. 360 wide |
| `R2/Forecast/Forecast vs outcome` | [57:4547](https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=57-4547) | 1080 wide |

Ships on the map are agent 2's **Ship marker** (`36:383`). The **Evidence strip** (`17:2`) is instanced in every watchlist row and ship card.

## Which ships get a probability (the top-k rule)

- **Who:** only watchlist entries with `decision` Inspect or Watch and `p` ≥ 0.10. Every other ship shows no number.
- **Cap per zoom:**
  - far (z 0–6): top 5, rank only
  - mid (z 7–10): top 10, rank and %
  - near (z 11+): top 20 in view, rank, % and the first reason
- **Slots:** tags use round 1's slot tiers 1 (Inspect) and 3 (Watch), so they count against the icon cap.
- **Selected ship:** always shows its tag, in the near style.
- **Ship with an open gap:** no tag. The ghost region and gap label replace it, because the ship is already silent and a new score would be censored as `already_dark`.
- **Treatment:** a small chip with a hairline leader, anchored 10 px up and to the right of the hull. The rank comes first, in mono semibold, and the % second. I used a chip rather than a ring, because round 1 already uses a ring for "meeting" and "heading unknown".
- **Colour:** the chip's 3 px stripe uses the round 1 risk ramp, binned by p: `risk/1` 10–24 %, `risk/2` 25–49 %, `risk/3` 50–74 %, `risk/4` 75 % and up. The hull is never recoloured, and the rank number carries the meaning without colour.

## Wording used

- **Panel title:** "Ranked for review · next 6 h"
- **Panel explainer:** "Chance a ship goes silent with reception normal nearby, within 6 h. Behaviour only: list matches show as reasons, never as inputs."
- **Tag tooltip:** "Ranked 3 for review · 61 % chance of a silence with reception normal nearby in the next 6 h"
- **Gap label:** "No AIS received for 47 min; reception normal nearby (14 ships heard within 20 km)" / "Could be within 16.6 km · last 11.4 kn, 074°"
- **Coverage-hole label:** "No AIS for 50 min; coverage hole here (0 ships heard within 20 km). Not counted as a silence."
- **Outcomes:** "Went silent" (hit), "Stayed heard" (miss), "Not scored" (censored)
- **Ship card action:** "Add to review" instead of "Flag for review"
- **Short labels:** "No AIS" and "AIS heard"

### Reason codes in plain words

| Code | Wording |
|---|---|
| `OPEN_GAP` | No AIS now, reception normal nearby |
| `RECENT_GAP` | Silent gap in the last 24 h |
| `SPOOF_CIRCLING` | Circling while reporting at anchor |
| `SANCTIONED` | On EU sanctions list |
| `DRAUGHT_JUMP` | Draught up 3.1 m |
| `FLAG_MISMATCH` | Flag does not match MMSI country |
| `BLANK_DESTINATION` | No destination |
| `LOITERING` | Loitering |

## Key decisions

- **Ghost region:** uses the v2 grammar of a hatched fill with a dashed edge. It has a cross at `last_lat/lon`, a hollow hull, and a dashed line along the last course.
  - Diameter = 2 × `radius_m` at map scale. The section 2 note says the radius is capped at 60 km; that cap is my placeholder until Jake sets the real one.
  - Magenta (`ship/dark`, `ship/ghost-*`) appears only when `coverage_flag = deliberate_candidate`.
  - A ship whose gap began inside a coverage hole (`coverage_gap`) gets the same geometry in grey (`text/muted`, `coverage/dead`).
  - A dead cell with no ship is a square grey cell with no cross and no circle.
  - `own_stall`: no ghost is drawn, and the status line says the feed paused.
- **Sunday card:** shows the commit, model version, freeze time and scoring time.
  - **All ten** top-10 rows stay visible, and hits, misses and "not scored" rows carry the same visual weight. Shape tells them apart, not colour: filled square = hit, hollow square = miss, hatched square = not scored.
  - Headline: 6 of 9 (35–88 %). The p values predicted 4.6 of 9, and median warning was 3 h 05 min.
  - The censored row is explained, and the "counted as a miss" figure is given: 6 of 10, 31–83 %.
  - Model, with-list ablation and the **three baselines** each have Wilson ranges, drawn as dot-and-bar intervals.
  - A plain sentence says the ranges overlap.
  - A capture-rate-at-k chart has a bootstrap band, direct labels and a k = 10 marker.
  - A list shows the silences the top 10 missed.
- **Panel order is by p**, as the data model says, and sanctions show only as reasons.

## Decisions for Hamish

1. **Censored forecasts.** At the moment they are left out of the headline rate, shown as "Not scored" rows, and the counted-as-miss figure sits next to the headline. The alternative is to count them as misses in the headline (the most conservative choice).
2. **Ships already silent on the watchlist.** At the moment the row stays, greyed: "61 % was the forecast before the silence". The alternative is to drop them and show them only in an events list.
3. **Ranking key.** The data model sorts by `p`. The evaluation plan ranks by `p × importance` (sanctions, tanker, draught jump, blank destination). Jake should pick one. If it's the product, the panel needs a second number or a note.
4. **Per-ship interval on p.** I didn't show one: it isn't in the data model, and it would clutter the list. Calibration appears on the Sunday card ("predicted 4.6 of 9") instead.
5. **Panel height.** The five rows with Evidence strips come to about 985 px, so the panel scrolls on a 900 px viewport. The other option is to show the Evidence strip only on the selected row.
6. **Colour-blind set.** `risk/4` is close to the spoofing yellow (agent 1 flagged this). Tags only colour a 3 px chip stripe, never a hull, so I think this is acceptable.

## Gaps in the variables

- **The Evidence strip main component (`17:2`) is still bound to `DVM Chart v2 · Night (superseded)`,** so it stays dark in Light mode. I rebound my instances' overrides to DVM Theme: panel → `bg/raised`, edge → `border/subtle`, texts → `text/*`, empty pips → `border/default`. Agent 1 or the master should rebind the main component; after that, these overrides can be cleared.
  - The strip's internal text sizes aren't bound to DVM Text size.
- **No "heard / confidence" colour** (v2 verdigris). The filled pips use `text/secondary`.
- **No chart-series or outcome roles.** The model line uses `accent/default` with `accent/subtle` for the band. Baselines use `text/secondary` and `text/muted` with dash patterns, and outcomes are ink plus shape. If charts multiply, add `chart/series-1…n` and `chart/band`.
- **No live / status-OK colour** for "AIS heard". It uses neutral `border/default`.

## Not checked

- I didn't run a contrast check on the new combinations (for example `ship/dark` text on `bg/panel` in the "No AIS" chip and the pink timer). These are agent 1's roles on agent 1's surfaces, but the specific pairs are unverified.
- The bootstrap figures (0.52, 0.34–0.69) and the capture curves are invented placeholders.
- Agent 2's map markers are rotated as whole instances, so selected brackets rotate with the hull; in the app they must stay upright.

## Contrast check

I computed each ratio in `use_figma` from the stored variable values. Aliases are resolved, and alpha colours are blended over their real backdrop. Every pair was checked in all 4 DVM Theme modes × both DVM Signals modes. The targets are 4.5:1 for text and 3:1 for marks.

**Passed as built (lowest ratio and where):**

| Pair | Lowest ratio |
|---|---|
| `text/primary` / `secondary` / `muted` on `bg/panel`, `bg/raised`, `bg/app` | `text/muted` on `bg/raised`: 4.94 (Dark) |
| `ship/dark` text on `bg/panel` (No AIS chip, timer) | 4.64 (Dark · CVD) |
| `text/on-accent` on `accent/default` (Add to review) | 6.93 |
| `risk/1–4` tag stripe on `bg/panel` | 4.48 (`risk/1`, Light · CVD) |
| Gap-label stripes (`ship/dark`, `text/muted`) on `bg/panel` | 4.64 |
| `ship/dark` cross on the ghost fill over water | 3.24 (Dark · CVD) |
| Coverage-hole edge (`text/muted`) on water | 4.71 |
| Coverage-hole cross on the dead cell over water | 3.50 |
| Map leaders (`text/muted`) on water | 4.71 |
| Outcome markers (hit fill, miss outline, hatched censored) on `bg/panel` | 8.23 |
| Chart model line (`accent/default`) on `bg/panel` | 6.53 |
| Chart model line on the bootstrap band | 5.45 |
| Chart baselines (`text/secondary` / `text/muted`) on `bg/panel` | 5.69 |
| Wilson interval bars on `bg/panel` | 8.23 |
| Inspect chip edge (`border/strong`) on `bg/panel` | 6.14 |

**Failed, and fixed with an existing role:**

| Pair | Before | Fix | After |
|---|---|---|---|
| Chance bar fill on its `border/subtle` track | 1.56 (Dark · HC) | The track is now a 1 px `text/muted` rule with no fill, so the bar reads against `bg/panel` | bar fill on panel ≥ 4.48; track rule on panel 5.69 |
| Greyed bar (`text/muted`) on the track | 2.46 | Same fix | 5.69 on panel |
| Probability-tag chip edge (`border/default`) on water | 1.68 (Light) | Edge changed to `text/muted` | 4.12 on water-alt, 4.71 on water |
| Ghost edge (`ship/ghost-edge`, i.e. `ship/dark` at 75 %) on water | 2.78 on water, 2.42 on water-alt (Dark · CVD) | Edge and last-course line changed to full `ship/dark` | 3.85 on water, 3.23 on water-alt |
| Button and Watch-chip edges (`border/default`) on `bg/panel` | 2.03 | Changed to `text/muted` | 5.69 |
| Empty Evidence-strip pip (`border/subtle` outline) on `bg/raised` | under 1.9 | Outline changed to `text/muted` (an override on my instances only) | 4.94 |

**Left as they are (texture or decoration; the edges carry the boundary):**
- Ghost hatch: 1.30.
- Coverage-hole hatch: 1.32.
- Dead-cell fill against water: 1.28.
- Chart gridlines (`border/subtle`): 1.37.

The edge, cross and label of each region pass. Only the fill inside is low-contrast, on purpose.

**Note for agent 1:** `ship/ghost-edge` (75 % alpha) fails 3:1 on water in Dark (2.78 Standard / CVD, 2.42 on water-alt). Anyone else who draws a ghost edge with it should use `ship/dark` instead, or the variable needs a higher alpha.
