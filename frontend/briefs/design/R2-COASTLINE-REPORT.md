# Report: R2b coastline agent, real geometry on every map

Figma file `tR0vsJQJlm1lvLKOgUJhOg`. Links use `https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=<id with ->`.

## What I made

My page is [R2 · 6 Basemap (real coastlines)](https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=69-2). It holds:

- **22 basemap components** named `R2/Basemap/<place> [size]`. Names, node ids, bboxes, sizes and sources are in `READY.md`.
  - [Baltic](https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=70-2) `70:2`
  - [Gulf of Finland](https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=73-2) `73:2`
  - [Helsinki approaches](https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=70-25) `70:25`
  - [World](https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=70-35) `70:35`
  - 18 crops for the existing frames.
- **What each component contains:** water, land, a coastline stroke, dotted land borders and a few place labels, with no ships. Every fill and stroke is bound to `map/water`, `map/land`, `map/coast`, `map/border`, `map/label-water` or `map/label-land`. Labels use Libre Caslon Text, italic for water and upright for land.
- **[Showcase · Light and Dark](https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=93-5)**: the main four, each set explicitly to DVM Theme = Light and = Dark, with DVM Signals = Standard.
- **[Build note · custom coastline layer (WANTED)](https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=93-159)**: source, tiling, layering over OpenFreeMap, the ≤ 1 px target, and what to measure. It is set to Dark.
- **Scripts in this folder:**
  - `basemap.py`: clip, Web Mercator, 0.5 px simplification, SVG. It runs a self-check on import.
  - `ships.py`: moves a ship on land to the nearest open water. Lakes count as land, ships stay inside the frame, and there is optional spacing between ships. It also has a self-check.
  - `generalise.py`: makes the deliberately generalised "before" map.
  - `fit_crop.py`: shifts a crop so a ship pile sits on water.
  - `label_spot.py`, `r2s_ships.py`, `batch_ships.py`, `upload.py`, `preview.py`.
  - Raw data is in `data/` and the generated SVGs and previews are in `out/`.

## Data sources and simplification

| Source | Used for | Notes |
|---|---|---|
| Natural Earth **10m** (land, minor islands, lakes, admin-0 land boundary lines; GeoJSON from `nvkelso/natural-earth-vector`) | Baltic, World, North Sea · Bergen, North Sea & Baltic, World 1140, both 300 × 220 Gulf of Finland crops, Gulf of Finland 380 × 280 | Lakes under 8 px² are dropped as specks. World uses 10m; it was not too heavy (22 k vertices, 460 KB SVG). |
| **OSM `natural=coastline`** from Overpass (7 Nov 2026), assembled into land polygons (land on the left of each way) | Helsinki approaches, Helsinki South Harbour 380, Helsinki harbour 1140 | |
| **OSM ocean polygons via OpenFreeMap vector tiles** (planet 2026-11-01, `water` layer with `class=ocean`; land = bbox minus ocean), at the zoom matching each view (z8–z13) | Gulf of Finland, Helsinki offshore, Helsinki archipelago 760 / 372, Tallinn Bay, Tallinn harbour, Fehmarnbelt, Puttgarden, Helsinki approaches 380 | This is the same OSM coastline as the app's own basemap. I used it for two reasons: osmdata.openstreetmap.de did not answer from this machine (connect timeout on ports 80 and 443), and Overpass ran out of capacity halfway through. NE 10m lakes are cut at z ≤ 9 so zooming in from the Baltic stays consistent. |
| Generalised from the OSM coast | `Helsinki archipelago · generalised 760×480` only | Closing of about 18 px, about 7 px simplification, islands under 150 px² dropped. NE 50m was too coarse: it removed the whole archipelago, so no ship could look like it was on land. |

**Every view:**
- clipped to its bbox, with 6 px padding so coast strokes never run along the frame edge;
- projected to Web Mercator in pixels;
- simplified with Douglas–Peucker at **0.5 px**, keeping topology and with no smoothing;
- islands under 1 px² dropped;
- imported as SVG through `upload_assets`. The `use_figma` code limit of 50 KB was too small for real coastlines.

## Frames I replaced

In each frame the drawn land is gone and a basemap instance sits under the ships and overlays. Where the frame already fills `map/water`, I hid the instance's own water.

**Agent 1 · Colour & themes (`39:448`)**
- **Frames:** Map tile in all five specimens: `39:451`, `39:569`, `39:686`, `39:803`, `39:920`. These now use North Sea · Bergen 720 × 420 (`71:26`).
- **Graticule:** moved onto real meridians (0, 3, 6, 9, 12° E) and parallels (59, 60, 61° N). The "4°E" label now reads "3°E".
- **Ships:** five ship dots and the selected ship (with its brackets) moved off Norway.
- **Labels:** Bergen and NORWAY moved to their real places. The instance's duplicate labels are hidden.

**Agent 2 · Ship iconography (`33:2`)**
- **Frames:** the Harbour far, mid and near scenes, in Dark (`38:274`, `38:467`, `38:574`) and Light · CVD (`47:307`, `47:394`, `47:442`).
- **Basemaps:** Gulf of Finland 380 × 280, Helsinki approaches 380 × 280 and Helsinki South Harbour 380 × 280.
- **Ships:** 40 moved per theme, then a second pass of 17 small corrections, which also took one boat out of Lake Peipus. The selected overlays move with their ships.
- **Open sea scenes:** these have no land and are unchanged.

**Agent 3 · Map density & focus (`38:627`)**
- **World `38:639`:** World 1140 basemap. 57 ships moved.
- **Region `38:969`:** North Sea & Baltic 1140 basemap. 67 ships moved.
- **Sea area `38:1419`:** Gulf of Finland 1140 basemap. 15 ships moved.
- **Harbour `38:1772`:** Helsinki harbour 1140 basemap.
  - 16 ships moved.
  - The "+14 moored" and "+9 inland" cluster rings and their chips moved onto water.
  - "Inner harbour" now reads "South Harbour".
- **Gap ghosts:** in all four storyboards, each moves with its No-AIS ship.
- **Density cells:** these already sit under the land layer, so cells over real land are hidden automatically.
- **Focus `39:1280` (Dark) and `50:1107` (Light · CVD):** Helsinki offshore 1240 × 720, scaled so Vessel A's printed fix (59°57.3′N 24°49.1′E) and the 10 nmi ring are true. Only the "Same owner" ship sat on land (Porkkala). It moved, and its leader line now ends on it in both themes.
- **Basemap before/after `41:255`, `41:297`:**
  - Turku and the Archipelago Sea became **Helsinki** and the Gulf of Finland, because that is where I had full-detail data.
  - Five ships moved, in identical positions in both panes. Three sit in real skerry channels that the generalised "before" draws as land, so the existing "on land?" chips stay true.
- **Depth off/on `41:396`, `41:408`:** Helsinki archipelago 372 × 232.

**R2 · 1 Stacking & overlap (`55:2`)**
- **Frames:** all 24 before/after scenes in `56:6364` (Dark) and `56:6973` (Light).
- **Crowded anchorage:**
  - Far: Gulf of Finland 300 × 220, at z6 scale.
  - Mid: Tallinn Bay.
  - Near: Tallinn harbour.
  - Label "Roads" now reads Gulf of Finland / Tallinn roads.
- **Busy strait:**
  - Far: Gulf of Finland · east.
  - Mid: Fehmarnbelt.
  - Near: Puttgarden.
  - Label "Sound" now reads Gulf of Finland / Fehmarnbelt.
- **Ships:** each crop was shifted (`fit_crop.py`) so the ship piles sit on real water untouched, which keeps the stacking demo intact. Only the far strait needed nudges: 8 ships of a few px, the same in before, after and both themes.

I did not touch `14:2` or any other page.

## What I could not do, or did only partly

- **Depth contours (`41:408`) are still Agent 3's illustrative contours.** They don't follow the real seabed around the real islands. Real contours need a bathymetry source, such as Traficom depth areas or EMODnet.
- **Agent 3's graticules are not georeferenced.** I left them as they were; only Agent 1's tile now has a real graticule.
- **World and Region storyboards:** relocated ships hug the nearest real coast, and the density cells were not re-binned to real traffic. Counts and caps are unchanged, so the storyboard's point holds.
- **Agent 3's captions are not mine and I didn't edit them.** The before/after header says "same zoom (z6)" and "Natural-Earth-style … islands under ~1 km dropped". The new crops are about z10, and the generalised pane is made from OSM as described above.
- **Label font sizes are fixed** (15 / 12 / 11 / 9–11 px) and not bound to DVM Text size.
- **No Playwright cross-check against the running map.** The previews (`out/preview/*.png`) and the Figma screenshots were the visual checks.

## Decisions for Hamish

1. **Coastline source for the build.**
   - The note asks for osmdata.openstreetmap.de land polygons.
   - That server was unreachable from this machine. If it is the same at build time, OpenFreeMap's tiled OSM ocean polygons gave correct results down to z13.
   - Planetiler from a Geofabrik Baltic extract also works.
2. **Lakes at low zoom.** The Baltic and Gulf of Finland views show Natural Earth lakes, so Finland's lake district is busy. Keep them, or hide lakes below z8?
3. **Places changed for honesty and data.**
   - Agent 3's before/after moved from Turku to Helsinki.
   - In R2 · 1, the "Busy strait" far tier is the Gulf of Finland, and mid and near are Fehmarnbelt. The Fehmarnbelt can't be drawn as a 250 px lane at far zoom without ships on land.
   - Say if you'd rather have one place across all tiers.
4. **The depth layer:** keep it as an illustrative frame, or source real contours?
5. **Baltic framing:** at 1440 × 900 I could not fit lon 9–31 and lat 53.5–66 together. I chose lon 4–36, lat 54.4–64.5, which crops the top of the Bothnian Bay. A taller crop is one line in `basemap.py`.

## Gaps in the variables

None needed. All map colours use the existing `map/*` roles. Captions on my page use `text/primary` and `text/secondary`, and backgrounds use `bg/app` and `bg/panel`.
