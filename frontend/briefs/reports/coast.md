# Coast agent handover report (#40, coastline basemap): WIP

Branch `40-coastline`. **No PR yet.** This is a handover at 22:00 to FrontEndLead. It started from FrontEndLead's WIP `7274306`; Aiden's agent finished the data run and built the runtime on Linux.

## Done

| File | What |
|---|---|
| `scripts/basemap/fetch_ofm.py` | (from the WIP) Quadtree fetch of OpenFreeMap `water` class=ocean, z10 to z14 over the Baltic box, into `.cache/ofm.sqlite` (resumable). **Changed:** 16 workers by default (`BASEMAP_WORKERS`). Ran to completion here: z14 has 79,672 tiles (53,781 mixed), about 1 GB downloaded, a 515 MB cache, 0 errors. osmdata.openstreetmap.de didn't connect from this machine either. |
| `scripts/basemap/build.py` | (from the WIP) Builds `public/basemap/coast.pmtiles` (git-ignored). **Fixed:** (1) land vanished at z7–9 (and in any tile where MVT quantisation made a polygon invalid): the encoder's make_valid dropped whole features. Now `shapely.set_precision` snaps to the grid itself. (2) Islands of at least 1 px² were lost when simplification shrank them below the prune threshold. Now it prunes by area before simplifying, and afterwards drops only slivers under 0.05 px². 14 workers by default. Build time is about 1.5 min. |
| `scripts/basemap/verify.py` | **New.** Vertex error check (tiled vs unsimplified source, px at the tile's zoom, raw and "as rendered" after a 0.1 px closing) and `--stats` (count and bytes per zoom, largest tile). |
| `scripts/basemap/glyphs.py` | **New.** MapLibre SDF glyph PBFs for Libre Caslon Text Regular/Italic and Barlow Semi Condensed Medium (OFL, google/fonts), in the fontnik parameters. Output is `public/basemap/fonts/` (948 KB, **committed**, so labels work without a rebuild). |
| `scripts/basemap/run.mjs`, `requirements.txt` | `npm run basemap [fetch\|build\|glyphs\|all]`: makes `scripts/basemap/.venv` (uv or venv) and runs the steps. `.venv/` is git-ignored. |
| `src/basemap/style.ts`, `index.ts` | `registerBasemap()` (pmtiles protocol). `basemapStyle(tokens?)`: **async** (it fetches the OpenFreeMap style once and HEAD-checks the tiles and fonts); the brief said sync. `setBasemapTheme(map, tokens?)` uses setPaintProperty only. Also `basemapTokens()` and `BASEMAP_FIRST_LABEL_LAYER`. Layering is documented at the top of `style.ts`: water background below z7 with our NE land; from z7, a land background with OFM ocean, our z6 `mask` repainting water inside the box and our OSM land over it (no double coast); OFM lakes and rivers on top; a 0.75 px coast; dotted NE borders overzoomed from z6; labels in Caslon (italic for water) and Barlow, English names first. Depth, landcover, landuse, buildings and OFM boundaries are dropped. If `coast.pmtiles` is missing, it falls back to OFM's coast with a console warning; missing fonts fall back to Noto. |
| `src/basemap/BasemapDemo.tsx`, `demo.css`, `src/App.tsx` (+1 lazy import, +1 line) | `?demo=basemap` (no login): skerries / Baltic / World buttons, a zoom readout, the Display menu, `&view=baltic\|world`, and a URL hash. |
| `package.json` | the `basemap` script (`pmtiles` ^4.5.0 was already added by the WIP). |

## Measurements (Linux laptop, headless Chromium + SwiftShader software WebGL: indicative only)

- `coast.pmtiles`: 91.4 MB; 1,179,024 tiles; 80,534 distinct blobs (all-land tiles are deduplicated). Per zoom: z0 1, z1 4, z2 16, z3 61, z4 205, z5 677, z6 2265, z7 90, z8 306, z9 1092, z10 3960, z11 14,747, z12 56,932, z13 222,836, z14 875,832. Largest tile: **161,509 B at 4/8/4**, the world tile holding the Baltic, which is heavy.
- Vertex error, tiled → source, as rendered: 8/145/74 **0.44 px**; 11/1165/593 **0.44 px**; 11/1164/593 0.22; 12/2330/1187 0.13; 13/4664/2372 0.21; 14/9331/4745 **0.02 px**. All are ≤ 1 px. Raw values reach 4.6 px at z8 only because of sub-pixel seams between pieces simplified in neighbouring child tiles: they share an edge to about 0.06 px and draw solid. Islands ≥ 1 px² missing from the tile: 0–3 per tile (3 of 196 at z8). The source → tiled maximum is dominated by islets under 1 px², which are dropped on purpose.
- First paint (navigation → map loaded, tiles loaded), 1440 × 900: skerries 1.0–1.5 s, Baltic 1.2 s, World 0.9 s. Range requests work through Vite (`206` responses). Fonts: 3–5 requests, 0 failures.
- Pan fps over the skerries for 5 s: cold 35 / 40 / 43 at z11 / 12 / 13, **warm about 47–50 at z11**. OFM-only fallback: 59–60. No single layer explains the gap (removing any one gives about 50). Not yet diagnosed; re-measure on the desktop GPU.
- Bundle: the demo chunk is 10.2 KB gz, of which `pmtiles` is about 8 KB gz.
- `npm run build` and `npm run lint`: **pass** (0 warnings).

## Acceptance

| Item | State |
|---|---|
| Real skerries at z12, no smoothing, islands kept | **Verified** (screenshot `coast/dark-skerries-z12.png`, verify.py) |
| No double coast | **Verified** visually at z12 inside the box. Outside the box above z6 there's no coast stroke (OFM ocean only), by design. |
| Dotted borders; labels on top in the design fonts and colours | **Verified** (Caslon italic for water, upright for places; Barlow for roads at z13+) |
| Light and dark follow tokens; setBasemapTheme recolours in place | **Verified** (land `#3b3a32` → `#efe4c6` without setStyle). The HC themes weren't screenshotted. |
| Missing tiles file degrades gracefully | **Verified** (404 → OFM coast + warning) |
| Figma comparison against `93:5` / `93:159` | **Not done** (Figma not authenticated). Screenshots are in `reports/coast/`. |
| Pan fps target 60 | **Not met under software GL** (about 47–50 warm); unverified on a GPU |
| PR open | **No** (paused on instruction) |

## Known problems

- At Baltic zoom (z4–5) the coast stroke over Norwegian fjords and the Finnish lakes is dense and dark (unsmoothed by design). Consider a thinner or lighter coast below z6, or hiding lake shores below z8 (design decision 2 in `R2-COASTLINE-REPORT.md`).
- The 4/8/4 tile is 161 KB. A z0–5 tolerance relaxed to 0.5 px would shrink it, still within ≤ 1 px.
- The pmtiles file is 91 MB; keep it git-ignored, rebuild with `npm run basemap build` after `fetch` (the cache stays in `scripts/basemap/.cache`).
- `basemapStyle` is async (deviation from the brief).

## Next steps to resume

1. `cd frontend && npm ci && npm run basemap` (fetch is resumable; on the desktop this re-downloads about 1 GB unless the `.cache` is copied).
2. `npm run dev -- --port 5176 --strictPort` → `http://localhost:5176/?demo=basemap` (`&view=baltic|world`).
3. Re-measure pan fps on a GPU. If it's still low, profile tile loading during the pan (worker parse of dense z11–z14 tiles) before changing the layers.
4. Compare with Figma `93:5` Light/Dark, then decide on the low-zoom coast weight and the lakes.
5. `scripts/basemap/.venv/bin/python scripts/basemap/verify.py` and `--stats` for the report numbers; open the PR "#40 coast: …", body "Part of #40".
