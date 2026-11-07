# Agent 1 report: colour, themes and accessibility

**Mode limit test: passed.** On 7 Nov 2026 I created a scratch collection and added a second, third and fourth mode with no error, then deleted it. The v2 draft's note ("one mode per collection") is out of date. Everything below uses real Figma variable modes, so no plan change is needed.

## What I made

A page called **Agent 1 · Colour & themes** ([page](https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=39-448)) with:
- Title, [Rationale](https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=40-5), [Structure](https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=40-8), [Cues for agent 2](https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=40-11), [Colour-blind check](https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=40-21) and [Contrast checks](https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=40-14). The contrast numbers are computed inside `use_figma` from the stored variable values.
- [Specimens](https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=39-566): five copies of one specimen, each bound to variables and set to its own mode combination. Each has a map tile (water, land, coastline, dashed national border, grid, water and land labels, coverage cells for "degraded" and "no receiver", and placeholder dots for every ship state), the status line, the ship popup, a legend, the risk ramp and the login screen.
  - [Light · Standard · Default text](https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=39-449)
  - [Dark (dusk) · Standard](https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=39-567)
  - [Dark · Colour-blind safe](https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=39-684)
  - [Dark · High contrast · Colour-blind safe · Large text](https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=39-801)
  - [Light · High contrast · Standard](https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=39-918)
- `palette.py` in this folder is the source of truth for the values and runs the checks: WCAG contrast, plus colour-blind simulation using the Machado 2009 matrices and CIE76 ΔE. `cvd_search.py` is the search I used to pick the colour-blind set.

## Key decisions and why
- **The idea is a chart table at dusk.** It draws on paper charts and the IHO S-52 day, dusk and night palettes, which bridge crews switch for the light they work in. From them we keep only the grammar: buff for land, blue for water, magenta for important things. Dark mode is dusk, not night: water is `#1f3b4b` (v2 used `#0a1822`) and text is warm ink `#eee9dc`. That makes it clearly brighter and calmer, but still a dark theme. Light mode is the paper chart.
- **Ships are drawn in ink by default.** Only states that need a human get colour: magenta for gone dark (v2's signal), amber for spoofing, vermilion for sanctioned, and sounding blue corner brackets for the selected ship. Port red and starboard green are kept out of every signal. There are no gradients, glow, glass or neon cyan, and the `#22d3ee` dots are retired.
- **"No receiver" uses neutral grey, never magenta**, so missing coverage never looks like a dark ship.
- **Three independent switches (4 × 2 × 3 = 24 combinations), and every combination is valid:**
  - High contrast sits in the theme collection because it changes every surface and the basemap.
  - The signal colours alias hidden `signal-std/*` and `signal-cvd/*` variables in DVM Theme, so they adapt to the background automatically.
  - There is one colour-blind-safe set that covers protanopia, deuteranopia and tritanopia together, so users get a single toggle and never have to name their type.
- **Existing collections:**
  - `Primitives v2` was renamed to `DVM Primitives v2` and `Layout v2` to `DVM Layout v2`. Their values are unchanged.
  - `Chart v2` was renamed to `DVM Chart v2 · Night (superseded)`. I kept it so the v2 draft still renders; new work should bind to DVM Theme.
  - The v1 collections (`Primitives`, `Color`, `Layout`) are untouched. They belong to the v1 draft page and can be retired with it.
- The DVM Theme values are raw hex values for each mode rather than aliases to primitives. With four modes and almost no values shared between them, a primitive layer would have doubled the variable count for no gain.

## Collections and modes
| Collection | Modes | Variables |
|---|---|---|
| DVM Theme | Light, Dark, Light · High contrast, Dark · High contrast | 48: 25 colour roles, `focus/dim-opacity`, and 22 hidden `signal-std/*` / `signal-cvd/*` |
| DVM Signals | Standard, Colour-blind safe | 11: `ship/normal, selected, dark, ghost-fill, ghost-edge, spoof, sanctioned` and `risk/1-4` (aliases into DVM Theme) |
| DVM Text size | Default, Large, Largest | 14: `size/*` and `line/*` for caption, label, data, body, heading, title, display |

Every variable has explicit scopes and WEB code syntax `var(--dvm-<name>)`.

## DVM Theme
| Variable | Light | Dark | Light · HC | Dark · HC |
|---|---|---|---|---|
| `bg/app` | #f3efe4 | #15232d | #ffffff | #0c171e |
| `bg/panel` | #fbf8f1 | #1c2d38 | #ffffff | #0f1c24 |
| `bg/raised` | #ffffff | #253a47 | #ffffff | #152530 |
| `border/subtle` | #ddd6c5 | #30485a | #8c8578 | #6c8494 |
| `border/default` | #b9b09b | #4a6474 | #4a4740 | #a9bcc6 |
| `border/strong` | #5a5f5c | #9fb4bf | #000000 | #ffffff |
| `text/primary` | #1d2529 | #eee9dc | #000000 | #ffffff |
| `text/secondary` | #424b4f | #cbc5b6 | #1d2529 | #ece7da |
| `text/muted` | #5d6466 | #a5a99f | #33393c | #d2cdbf |
| `text/on-accent` | #ffffff | #10202a | #ffffff | #000000 |
| `accent/default` | #1c5f86 | #86c9e8 | #0b4468 | #a6dbf3 |
| `accent/subtle` | #1c5f86 @ 10 % | #86c9e8 @ 16 % | #0b4468 @ 14 % | #a6dbf3 @ 20 % |
| `map/water` | #d6e6ec | #1f3b4b | #e4f1f6 | #132b38 |
| `map/water-alt` | #c4dbe4 | #26475a | #cfe4ed | #1a3646 |
| `map/land` | #efe4c6 | #3b3a32 | #f3e2b2 | #3e3c32 |
| `map/coast` | #3f4b4f | #c3cccb | #000000 | #f2f2ec |
| `map/border` | #7a6f5a | #b0a58a | #4f4535 | #d8cca8 |
| `map/label-water` | #2f5468 | #a9c6d4 | #0f3448 | #cfe5ef |
| `map/label-land` | #5a5140 | #cfc6ae | #2f281b | #ece2c6 |
| `map/grid` | #b5cad3 | #2f4b5b | #93b0bd | #3a5a6b |
| `focus/veil` | #f3efe4 @ 62 % | #15232d @ 62 % | #ffffff @ 72 % | #0c171e @ 72 % |
| `focus/dim-ship` | #7b8387 | #8d969a | #5d6466 | #a3abaf |
| `coverage/ok` | #2e8a6f @ 10 % | #4fbf9f @ 12 % | #1c6b55 @ 14 % | #5fd3b0 @ 16 % |
| `coverage/degraded` | #b07a12 @ 16 % | #e0b65a @ 18 % | #8a5c00 @ 22 % | #f0c45e @ 24 % |
| `coverage/dead` | #6b7275 @ 22 % | #8d969a @ 24 % | #3d4346 @ 30 % | #a3abaf @ 30 % |
| `focus/dim-opacity` | 0.40 | 0.45 | 0.35 | 0.35 |

`ship/ghost-fill` and `ship/ghost-edge` use the `dark` colour at 14 % and 75 % opacity.

## DVM Signals: resolved values (Standard / Colour-blind safe)
| Signal | Light | Dark | Light · HC | Dark · HC |
|---|---|---|---|---|
| `ship/normal` | #1d2529 / #1d2529 | #eee9dc / #eee9dc | #000000 / #000000 | #ffffff / #ffffff |
| `ship/selected` | #1c5f86 / #0c63e1 | #86c9e8 / #95cee9 | #0b4468 / #0f3f6a | #a6dbf3 / #39c1f9 |
| `ship/dark` | #b3266b / #522a03 | #f26aa0 / #c98269 | #8f0f4e / #4e2b02 | #ff7fb0 / #f59453 |
| `ship/spoof` | #9a6400 / #807a03 | #f2b33d / #beaf3a | #6e4700 / #7c7d18 | #ffc24d / #e5cd11 |
| `ship/sanctioned` | #c2331c / #c64b8a | #ff7650 / #ff5aa8 | #9a2010 / #d209d0 | #ff8a63 / #fb4c95 |
| `risk/1` | #83702a / #5f7686 | #e5d38c / #7d9bb3 | #6b5a14 / #4b6170 | #f0e0a0 / #93b2c8 |
| `risk/2` | #a2630a / #7a6430 | #f2a640 / #a9a98a | #8a5200 / #6e5a24 | #ffb54d / #c4c09a |
| `risk/3` | #c2492b / #83420f | #ee7458 / #e0a95a | #9a2f14 / #73380a | #ff8a6a / #f0b860 |
| `risk/4` | #a8195e / #4f1e08 | #f0609e / #ffc36b | #7c0a43 / #3d1504 | #ff74ae / #ffd27a |

## DVM Text size (size / line height, px)
| Role | Default | Large | Largest |
|---|---|---|---|
| caption | 10 / 14 | 12 / 16 | 14 / 20 |
| label | 12 / 16 | 14 / 18 | 17 / 22 |
| data | 12 / 16 | 14 / 20 | 17 / 24 |
| body | 14 / 20 | 17 / 24 | 20 / 28 |
| heading | 15 / 20 | 18 / 24 | 22 / 28 |
| title | 18 / 24 | 22 / 28 | 26 / 32 |
| display | 32 / 38 | 38 / 44 | 44 / 52 |

## Contrast results
I ran the checks in `use_figma` against the stored values; they match `palette.py`. **0 failures** across all four theme modes.
- **Text (target 4.5:1):** checked text primary, secondary and muted on the app, panel and raised surfaces, accent on panel, on-accent text on accent, and map labels on water and on land. The lowest is **4.94**, for Dark `text/muted` on `bg/raised`.
- **Non-text (target 3:1):** checked coastline on water and land, border on land, the strong border, and every ship state and risk step (both signal sets) against water, water-alt and land, plus the sanctioned badge against its keyline. The lowest is **3.06**.
- **Colour-blind (worst pairwise ΔE among normal, selected, dark, spoof and sanctioned, target 20 or more):**

| Set | normal vision | protan | deutan | tritan |
|---|---|---|---|---|
| Light cvd | 39.1 | 31.1 | 34.6 | 33.7 |
| Dark cvd | 31.0 | 25.7 | 23.6 | 26.1 |
| Light HC cvd | 38.9 | 33.3 | 31.9 | 33.9 |
| Dark HC cvd | 49.5 | 30.7 | 27.9 | 29.5 |
| Light std | 34.0 | 9.5 | 3.3 | 19.6 |
| Dark std | 34.9 | 23.4 | 18.1 | 8.4 |

The Standard set is not colour-blind safe on purpose (that is what the toggle is for). The colour-blind risk ramp rises steadily in lightness in every theme, so it reads as a ramp without hue.

## Final non-colour encodings (agent 2's, also on the page)
- Normal: a solid silhouette.
- Selected: four upright corner brackets in ship/selected.
- Dark: a hollow hull, plus the v2 cross and uncertainty circle.
- Gap ghost: a dashed circle, hatched where unknown.
- Spoofing: a solid hull at the reported position and a hollow copy at the implied position.
- Sanctioned: a notched diamond badge at the upper right, with a bg/app keyline.
- Heading unknown: a ring and a bow-less plan, never rotated.
- Risk: a number in the chip, and a heavier ring on the map.
- Dimmed: low opacity, with no heading line and no label.

## Open points for Hamish
- In the Standard set, colour-blind users can't tell spoofing amber from sanctioned vermilion. The colour-blind toggle and the shape cues cover this. Decide whether the colour-blind set should be the default.
- In the colour-blind set the top risk step is a pale yellow-orange, close to the spoofing yellow. They appear in different places (chips versus map marks), but don't recolour hulls by risk on the map.
- The v1 collections are still in the file, unrenamed.

## Follow-up: agent 2's icons bound to DVM variables

**What I bound.** On "Agent 2 · Ship iconography" ([page](https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=33-2)), every visible solid fill and stroke now points to a DVM variable: 0 left unbound. I bound the main components first (Ship hull `33:108`, Ship overlay `33:127`), then the instance overrides that were still unbound in Ship marker `36:383` and in the Sample scenes `38:272` (for example the amber spoof hulls). Instances now follow the variables.

| Agent 2 colour | Now bound to |
|---|---|
| ship/heard `#e6e2d6` (hulls, strokes) | DVM Signals `ship/normal` |
| the same ink inside the "Overlay=selected" brackets | `ship/selected` |
| `#e2487f` hollow strokes | `ship/dark` |
| `#f2b33d` fills and strokes | `ship/spoof` |
| `#e6606a` badge | `ship/sanctioned` |
| `#07131b` badge keyline | DVM Theme **`bg/app`** |
| `#0e2230` set backgrounds | `map/water` |
| `#0e2230` harbour scenes | `map/water-alt` |
| `#0a1822` open-sea scenes | `map/water` |
| `#23221f` land / `#a9b4b8` coast | `map/land` / `map/coast` |
| `#07131b` notes and scenes frames | `bg/app` |
| `#24394a` frame edges | `border/subtle` |
| `#e6e2d6`, `#b5b2a6`, `#858a86` text | `text/primary`, `text/secondary`, `text/muted` |

**Keyline choice: `bg/app`.** The keyline works like a cartographic halo: it has to separate the red badge from the ink hull under it, in both themes. `bg/app` is always the opposite of the ink: 13.2–13.6:1 against the hull. Against the badge it is 3.8–6.1:1, and it nearly disappears on water, so the badge reads as cut out of the map.

**Modes.**
- The page and its top-level frames and sets are set explicitly to Dark (dusk) · Standard.
- Page backgrounds can't take variables in Figma, so the page background is set to the dusk `bg/app` hex, `#15232d`.
- I added one copy of the scene frames, "Sample scenes · zoom tiers · Light · Colour-blind safe" ([47:305](https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=47-305)), placed to the right of the original. It renders correctly: black ink hulls on pale water, buff land, and the colour-blind state colours.

**The file now agrees with itself.**
- My cues frame is renamed "Final encodings (agent 2, bound to DVM Signals)" ([40:11](https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=40-11)) and describes agent 2's encodings: brackets for selected, hollow hull for dark, solid plus hollow copy for spoofing, notched diamond for sanctioned, and a ring with a bow-less plan for heading unknown.
- In all five specimens, the selected ring is now four corner brackets, the dark dot is hollow, and the sanctioned dot is an ink dot with a notched diamond badge.
- The legends and the rationale line about the ring are updated to match.

**Contrast re-check (3:1 non-text).** I ran it again in `use_figma` and `palette.py`, adding `map/water-alt` (which the harbour scenes use) and the badge against its keyline. Two problems turned up:
- Dark · Colour-blind safe `ship/sanctioned` on water-alt was 2.79:1. I changed `#f63997` to `#ff5aa8`, which gives 3.42:1. The worst colour-blind separation is still ΔE 23.6, above the target of 20.
- Light · Standard `risk/1` and `risk/2` on water-alt were 2.90:1 and 2.82:1. I changed them from `#8f7b2e` and `#b0700c` to `#83702a` and `#a2630a`, which gives 3.38:1 for both.

After the fixes there are **0 failures** in all modes; the lowest non-text ratio is 3.06 and the lowest text ratio is 4.94. The contrast card ([40:14](https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=40-14)) and the tables above show the new values.
