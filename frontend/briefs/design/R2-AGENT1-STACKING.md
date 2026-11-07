# R2 · Agent 1: stacking clarity: report

New page **"R2 · 1 Stacking & overlap"**, `55:2`, in file `tR0vsJQJlm1lvLKOgUJhOg`: https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=55-2
Nothing outside this page was touched. No variables or collections were created or edited. Every fill, stroke, text colour and keyline effect colour is bound to DVM Theme or DVM Signals. Text sizes are bound to DVM Text size. Section frames are set explicitly to DVM Theme = Dark (or Light), DVM Signals = Standard and DVM Text size = Default.

## Node links

| Section | Node | Link |
|---|---|---|
| Header | `56:625` | https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=56-625 |
| 1 · Z-order | `56:628` | https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=56-628 |
| 2 · Opacity steps (with a focus-mode example) | `56:684` | https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=56-684 |
| 3 · Separation & stacks | `56:832` | https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=56-832 |
| 4 · Before / after · Dark | `56:6364` | https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=56-6364 |
| 4 · Before / after · Light | `56:6973` | https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=56-6973 |
| 5 · MapLibre notes | `56:1028` | https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=56-1028 |
| 6 · For the dashboard | `55:3` | https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=55-3 |

## 1. Z-order (higher = drawn on top)

| Tier | Ship | Order within the tier |
|---|---|---|
| 0 | Selected or focused ship; hovered ship | always on top, in its own layer |
| 1 | Related to the focused ship (focus mode only) | nearby, possible rendezvous, also silent, same flag |
| 2 | Watchlist `decision = inspect` | `risk_rank` 1 first |
| 3 | Open gap, No AIS (`status = gap_open`) | longest gap first |
| 4 | Watchlist `decision = watch` | `risk_rank` 1 first |
| 5 | Flagged: `sanctioned`, or `spoof_recent` in the last 24 h | then recency |
| 6 | Followed (pinned this session) | then recency |
| 7 | Large or fast: `length_m ≥ 200` or `sog_kn ≥ 18` | longest first |
| 8 | Everyone else | newest `last_ts` first |

```
sort_key = (8 − tier) × 1 000 000 + order_in_tier × 1 000 + recency
order_in_tier = 999 − min(risk_rank, 999)   tiers 2, 4
              = min(gap_minutes, 999)        tier 3
              = min(length_m, 999)           tier 7
              = 0                            other tiers
recency       = 999 − min(minutes since last_ts, 999)
```

- The highest key is 8,999,999, which float32 holds exactly.
- **How ties break:** equal keys keep source order. Send the GeoJSON sorted by MMSI ascending, and never rely on tile order.
- A ship that matches several tiers takes the highest one.
- **Tier 0 is not in the key.** The selected, focused or hovered ship is drawn in a separate layer on top. Sort keys can't read feature-state, and this way changing the selection doesn't need a data reload.

## 2. Opacity steps

| Step | Opacity | Who | Labels and heading line |
|---|---|---|---|
| Full | **100 %** | Selected or focused ship and its related ships; tiers 2–5 (inspect, No AIS, watch, flagged) in normal view | Label shown at mid and near. Heading line shown |
| Routine | **80 %** | All other ships in normal view (tiers 6–8) | Label only at near, and only when it fits (`text-optional`). Heading line at 80 % |
| Context | **45 % Dark · 40 % Light · 35 % high contrast** (= DVM Theme `focus/dim-opacity`) | Unrelated ships while a ship is focused | No label, no heading line. Still clickable: a click moves focus to that ship |
| Trace | **20 %** | True-position hulls behind an open fan-out | No label, no heading line, not clickable |

- Colour never changes with the step. A dimmed No AIS ship stays magenta and hollow.
- Text is never dimmed: a label either shows at full contrast or is hidden.

## 3. Halo (keyline) spec and stacks

**Keyline**

- Colour: DVM Theme `bg/app`, so it follows Light, Dark and high contrast.
- Width: far **1 px**, mid **1.5 px**, near **2 px** at 1×. Double these for @2x sprites.
- Blur: 0, so it's a crisp edge, not a glow.
- Applies to hulls in every state (solid and hollow), to overlays, and to stack chips.
- Ships are never nudged off their true position.
- In Figma the keyline is 8 zero-blur drop shadows bound to `bg/app`. That is a stand-in for drawing only.

**Stacks**

- 1 ship: drawn normally.
- 2–3 overlapping ships, or any number at Full strength: keyline and z-order only. Every ship stays visible and clickable.
- **4 or more overlapping routine ships (tiers 6–8)** fold into one **stack chip** at their centre: a stack glyph and a count.
  - "Overlapping" means centres closer than one hull length: far 16 px, mid 32 px, near 64 px × `icon-size`.
  - Ships at Full strength (tiers 0–5) never fold. They are drawn on top of the chip, so a stack can never hide a ship that matters.
  - This is the same fold as agent 3's "+N" chips: agent 3's 1.5 × icon-length spacing rule decides who becomes an icon, and this chip is how the folded ones look on the map.
- Hover: the chip border turns accent, and a tooltip says "12 ships · 7 cargo, 3 tanker, 2 other".
- Click with 2–8 ships: the stack **fans out** onto a ring, radius 78 px at mid. The highest z-order goes at 12 o'clock, then clockwise. Hairline leaders run back to the shared true position, and the true positions stay visible at Trace 20 %.
- Click with 9 or more ships: a **stack list** opens, anchored to the chip and sorted in z-order. Hovering a row highlights that ship; clicking a row focuses it.
- To close: Esc, a click on water, or a click on the chip. Zooming in past the fold distance dissolves the stack by itself.

## 4. Before / after

The scenes use real **Ship marker** (`36:383`) instances at far, mid and near, 1:1, in a crowded anchorage and a busy strait, in Dark and Light. Each caption counts what is drawn:

| Scene | Before | After |
|---|---|---|
| Anchorage, far | 34 ships drawn as 34 icons | 4 icons + 1 chip (30) |
| Anchorage, mid | 15 icons | 4 icons + 1 chip (11) |
| Anchorage, near | 8 icons | 3 icons + 1 chip (5) |
| Strait, far | 30 icons | 15 icons + 3 chips (5, 6, 4) |
| Strait, mid | 13 icons | 8 icons + 1 chip (5) |
| Strait, near | 7 icons | 7 icons, separated by keyline only |

## 5. MapLibre (summary; the full notes are in frame `56:1028`)

- **Hull layer:** `icon-allow-overlap: true`, `icon-ignore-placement: true`, `symbol-sort-key = sort_key`. With overlap allowed, a higher key draws on top.
- **Selected and hover:** a second symbol layer on top, filtered by id.
- **Opacity:** `icon-opacity` and `text-opacity` come from feature-state `emphasis`. `text-opacity` is 0 at Context and Trace.
- **Keyline: bake it into the sprite.** `icon-halo-color` / `icon-halo-width` on SDF sprites do draw an outline. But as far as I know MapLibre draws all halos of a layer before all icon fills, so a halo never cuts into the ship underneath. The hollow No AIS state also already uses the halo as its outline. So:
  - Build the sprites at runtime on a canvas from agent 2's SVG paths, with a `bg/app` stroke under the fill.
  - Make one sprite set per theme with `map.addImage`, and rebuild it when the theme changes.
  - Use `icon-halo` only as a fallback. **Check the halo pass order on a real build.**
- **Stack chip:**
  - A separate GeoJSON source for routine ships (tiers 6–8, not in focus), with:
    - `cluster: true`
    - `clusterMaxZoom: 18` and source `maxzoom: 18`, so stacks persist when overzoomed
    - `clusterRadius` = hull length in px (16 / 32 / 64)
    - `clusterMinPoints: 4`
    - `clusterProperties` with per-type counts for the tooltip
  - Clusters draw as the chip (icon plus `point_count`). Tiers 0–5 come from an unclustered source drawn above.
  - `getClusterLeaves(id, 50)` gives the ships for the fan-out or the list.
- **Fan-out:** a temporary GeoJSON source with ring positions computed in screen space (`map.unproject`), and the leaders as a line layer. It closes on `movestart`.

## 6. Components for agent 5 (in frame `55:3`)

| Component | Node | Properties |
|---|---|---|
| **R2/Stacking/Stack chip** | `55:50` | `Size` far / mid / near × `State` closed / open. Text layer `count`; near also has `unit` ("ships") |
| **R2/Stacking/Ship emphasis** | `55:68` | `Emphasis` full / routine / context / trace. Contains an exposed Ship marker instance `ship` with the mid keyline |
| **R2/Stacking/Fan-out** | `55:69` | 6 mid ships on a ring with leaders and a shared true-position dot |
| **R2/Stacking/Stack list** | `55:100` | List popover for 9 or more ships, rows in z-order. The far Ship marker instance in each row is swappable |

Instance them inside a frame that has the DVM modes set; they take Light or Dark from their parent.

## Decisions for Hamish

1. **Which ships never fold into a stack:** I chose all of tiers 0–5 (everything shown at Full strength, including watch and flagged ships), not just inspect and No AIS. It is safer, but it allows more overlap in busy places.
2. **Routine ships at 80 % in normal view:** this calms crowds, but it means ordinary ships are never shown at full strength. The alternative is 100 % and relying on the keyline alone.
3. **Fan-out up to 8 ships, list from 9:** say if you'd rather always use the list (simpler to build).
4. **Bake the keyline into the sprites** rather than relying on `icon-halo`. This costs a small runtime sprite build per theme.

## Gaps in the variables

- **`focus/dim-opacity` can't be bound to layer opacity.** It holds 0.45 / 0.40 / 0.35, but Figma's opacity binding expects 0–100, so binding it gives 0.45 %. I set Context to a literal 0.45 in the components and scenes. Fix: a second variable that holds 45 / 40 / 35, or change the scale of the existing one if nothing else depends on it.
- **No opacity variables for Routine (0.8) or Trace (0.2).** They are literals for now.
- **No keyline role:** I used `bg/app`, as round 1 did for the badge. A `ship/keyline` alias (= `bg/app`) would make the intent clear.

## Known limits

- The before/after scenes are seeded and generated, with simple single-link folding. In the far strait panel, two neighbouring chips sit close together. A real clusterer (supercluster) would merge them.
- As in agent 3's scenes, the whole marker is rotated, so the selected brackets in the focus example rotate with the hull. In the app they stay upright, per agent 2.
- The MapLibre details (halo pass order, `clusterMinPoints`, overzoomed clustering) are from memory and are not tested on a real build.
