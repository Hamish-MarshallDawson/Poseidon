# Agent 3: coastline basemap (PMTiles) over OpenFreeMap

Read `CONTEXT.md` first. Worktree `G:/GitHub/dvm-fe/coast`, branch `40-coastline`, dev port **5176**. You own `frontend/scripts/basemap/` (the build tooling) and `frontend/src/basemap/` (the runtime style builder and PMTiles protocol).

## Design source

- Figma page `69:2` "R2 · 6 Basemap (real coastlines)": the **build note** frame `93:159` is your specification; the showcase `93:5` shows the look in Light and Dark (water `--dvm-map-water`, land `--dvm-map-land` with a 0.75 px `--dvm-map-coast` stroke, dotted land borders in `--dvm-map-border`, Libre Caslon labels italic for water, upright for land). Reports: `design/R2-COASTLINE-REPORT.md`, `design/READY.md` (bboxes), and the basemap requirement in `design/R1-AGENT3-DENSITY.md` (vertex error ≤ 1 px at every zoom 0–14, keep islands ≥ 1 px², borders from the same source, depth removed by default).
- Read the build note in Figma with `get_design_context` on `93:159` and follow it literally where it is more specific than this brief.

## Build

1. **Data.** Reuse what the design agent already downloaded in `G:/GitHub/hedged-bets-agents/figma-r2-coast/data/` (read-only; copy what you need): Natural Earth 10m land, minor islands, lakes and admin-0 boundary lines (GeoJSON), OSM coastline for Helsinki (Overpass JSON), and OpenFreeMap vector tiles (`ofm/`, OSM ocean polygons z8–z13 over the Gulf of Finland). The design agent's `basemap.py` there shows how to assemble OSM coastline into land polygons. Sources, in preference order: OSM land polygons from osmdata.openstreetmap.de (was unreachable from this machine on 7 Nov; try once with a timeout), then a Geofabrik extract, then OpenFreeMap's `water` layer `class=ocean` as land = bbox minus ocean (works to z13), then Natural Earth 10m. **Scope:** world at z0–6 from Natural Earth 10m; the Baltic box (lon 9–31, lat 53.5–66) at z7–14 from OSM-derived geometry. Nothing outside the Baltic above z6 (OpenFreeMap carries on there).
2. **Tiling.** No tippecanoe or WSL on this machine; Java 21 and Python 3.13 are available (`pip install` is fine). Options: Planetiler (Java) with simplification off, or a Python pipeline (`shapely` + `mapbox-vector-tile` + the `pmtiles` writer package). **No line simplification beyond 1 px at each zoom; no tiny-polygon reduction; no smoothing.** Layers: `land` (polygons), `coast` (lines), `border` (admin-0 lines). Output `frontend/public/basemap/coast.pmtiles` (git-ignored; add the ignore) plus `frontend/scripts/basemap/README.md` on how to rebuild (`npm run basemap`). Commit the scripts, never the tiles.
3. **Runtime (`src/basemap/`).** Add the `pmtiles` npm package (justify size) and register its protocol. `basemapStyle(tokens: Record<string,string>): StyleSpecification` returns the OpenFreeMap style of the current theme (fetch the JSON once, cache) with: its ocean/water-outline and land fill hidden where our source covers (below z15 everywhere for world; our coastline source added as `coast` with layers `land-fill`, `coast-line`, `border-line` (dotted: `line-dasharray`), coloured from the tokens; OpenFreeMap's labels kept on top in the token label colours and the three families (Caslon italic for water names); depth/bathymetry removed; graticule optional. If `coast.pmtiles` is missing (HEAD 404), fall back to OpenFreeMap's own coast with a console warning, so teammates without the file still get a map. Also export `BASEMAP_FIRST_LABEL_LAYER` so ships can be inserted below labels if wanted.
4. **Theme switch:** a `setBasemapTheme(map, tokens)` that updates paint properties in place (no `setStyle`) so the map agent's theme crossfade is cheap.
5. **Dev check page:** `?demo=basemap` (one line in `App.tsx`) that mounts a plain map on your style at the Helsinki skerries (`59.98–60.26 N, 24.55–25.45 E`) so the lead can review.

## Measure and report (required), in `briefs/reports/coast.md`

- `coast.pmtiles` size; the largest tile (bytes) and at which z/x/y; tile count per zoom.
- Vertex error check: for three sample tiles at z8, z11 and z14, the max distance between the tiled geometry and the source geometry in px (a script).
- First paint of the basemap at the Baltic view and at the Helsinki skerries (Playwright, headed Edge; tiles served by Vite from `public/`, confirm Range requests work or serve via a tiny static server).
- Pan fps over the Helsinki skerries at z11–13 for 5 s.
- Screenshot comparison against the Figma showcase `93:5` in Light and Dark.

## Acceptance

- Real skerries visible at z12 with no smoothing, islands kept; OpenFreeMap's own ocean coastline hidden (no double coast); dotted borders; labels on top in the design fonts and colours; light and dark follow tokens.
- Missing tiles file degrades gracefully. `npm run build` and `npm run lint` pass. PR open, report written.
