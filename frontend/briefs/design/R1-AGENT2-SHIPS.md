# Agent 2 · Ship iconography: report

File `tR0vsJQJlm1lvLKOgUJhOg`, new page **"Agent 2 · Ship iconography"**: https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=33-2
Nothing outside this page was touched. No variables were created (there were no "DVM" collections when I worked), so all fills are plain; the colour roles are listed below for binding.

## What I made

| Node | Link | What |
|---|---|---|
| Ship hull (component set, 30 variants) | https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=33-108 | Base sprites, one colour, bow up |
| Ship overlay (component set, 6 variants) | https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=33-127 | Selected brackets and sanctioned badge, never rotated |
| Ship marker (component set, 90 variants) | https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=36-383 | Every type × state × size, built from hull and overlay instances |
| Implementation notes | https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=38-255 | Sizes, MapLibre layers, state encoding, colour roles, SDF caveat |
| Sample scenes | https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=38-272 | Busy harbour and open sea at far, mid and near, 1:1 |

## Components and variant properties

- **Ship hull**: `Type` = tanker | cargo | fishing | passenger | inland or other; `Size` = far | mid | near; `Heading` = known | unknown. Export name: `ship-{type}-{size}` and `ship-{type}-{size}-noheading`. One layer named `silhouette`.
- **Ship overlay**: `Overlay` = selected | sanctioned; `Size` = far | mid | near. Export name: `overlay-{overlay}-{size}`.
- **Ship marker**: `Type` (5) × `State` = normal | selected | dark | spoofing | sanctioned | heading unknown × `Size` (3). This is a preview of the stacked sprites for designers; the app exports Hull and Overlay only.

## Silhouettes (plan view from above, bow up = 0°)

Each type has one feature you'd see from above, cut into the hull as holes so it still works as a one-colour sprite:
- **Tanker**: long parallel deck, one pipe run along the centre with a manifold crossbar, accommodation block aft.
- **Cargo**: fine bow, a grid of container bays, a thin bridge bar near the stern.
- **Fishing**: short hull, wheelhouse forward, open working deck aft (U shape), outrigger booms swept back.
- **Passenger**: broad, rounded at both ends, an inset deck ring and rows of lifeboat dots along both sides.
- **Inland or other**: narrow blunt box with one long open hold.

## Sizes per zoom tier

| Tier | Zoom | Hull sprite | No heading | Overlay box | Badge |
|---|---|---|---|---|---|
| far | 0–6 | 8 × 16 px | 8 px ring + dot | 22 px | 5 px |
| mid | 7–10 | 12 × 32 px | 14 px | 40 px | 7 px |
| near | 11+ | 24 × 64 px | 24 px | 76 px | 10 px |

- Far glyphs are separate drawings. Type shows through aspect ratio and bow shape alone.
- Mid keeps one cue per type: pipe and aft block, bay stripes, open deck and booms, deck ring, open hold.
- Near uses `icon-size = clamp(length_m / 150, 0.7, 1.4)`, so 1.0 stands for a 150 m ship.
- **Minimum readable size is 8 × 16 px.** Below that, draw the aggregate view (agent 3) instead of ships.
- Export sprites at @1x and @2x.

## How each state is encoded (shape first, colour second)

| State | Shape (works without colour) | Colour |
|---|---|---|
| normal | solid hull | ink #e6e2d6 |
| selected | four corner brackets (overlay, upright) | ink |
| dark / gone silent | hollow hull (outline only) | magenta #e2487f |
| spoofing | solid hull at the reported position + hollow copy at the implied position (v2's "reported solid, implied outlined") | amber #f2b33d |
| sanctioned | notched diamond badge at the upper right (overlay, upright) | red #e6606a, keyline #07131b |
| heading unknown | ring + a symmetric plan with no bow, never rotated | ink |

- **Brackets for selected, not a halo ring:** a ring already means "meeting" in v2 and "no heading" here.
- **States combine:** for example, sanctioned and dark gives a hollow hull plus the diamond.

## Implementation (MapLibre)

- **Hull layer:** symbol layer with `icon-image` chosen by `type_group` and tier, `icon-rotate = coalesce(heading_deg, cog_deg)` and `icon-rotation-alignment: map`.
  - Treat heading 511 and course 360 as null (AIS "not available").
  - If both are null, use the `-noheading` sprite with a rotation of 0.
- **Hollow states (dark, and the implied copy for spoofing):** reuse the same SDF sprite with an `icon-color` alpha of 0 and `icon-halo-color` / `icon-halo-width` 1.
  - Spoofing draws the sprite twice. The hollow copy goes at the implied position; if there isn't one, it uses a fixed screen offset (10 px at near).
- **Overlay layer:** a second symbol layer with `icon-rotation-alignment: viewport`. Its boxes are square and larger than the hull's diagonal, so they clear the hull at any heading.
- **SDF caveat:** the halo also traces the holes cut into the hull (bays, hold). That's intended: a hollow ship keeps its type. Generate the SDFs with a 3 px buffer.

## Colour roles used (plain fills, to bind to agent 1's DVM variables)

ship/heard #e6e2d6 · ship/dark #e2487f · ship/spoof #f2b33d · ship/sanction #e6606a · ship/keyline #07131b · map/water #0a1822 and #0e2230 · map/land #23221f · map/coast #a9b4b8 · set backgrounds #0e2230 · page background #07131b.

## Known limits

- The open-sea samples are placed at random (seeded), so a few ships overlap, mostly in the near panel. The harbour panels are placed by hand.
- The sanctioned badge sits at the corner of the overlay box, so at far and mid it floats a few px from a narrow hull.
- I checked the sprites only as Figma renders, not as real MapLibre SDF output.
