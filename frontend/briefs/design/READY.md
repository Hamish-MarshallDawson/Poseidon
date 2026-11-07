# READY: R2 basemap components (real coastlines)

Page **R2 · 6 Basemap (real coastlines)** (`69:2`) in file `tR0vsJQJlm1lvLKOgUJhOg`. Link form: `https://www.figma.com/design/tR0vsJQJlm1lvLKOgUJhOg/?node-id=<id with - for :>`.

Each component is a plain map with no ships. It has four layers:
- `water` (map/water)
- `land` (fill map/land, 0.75 px stroke map/coast)
- `border (land, dotted)` (map/border)
- `labels`: Libre Caslon Text, italic for water and upright for land, using map/label-water and map/label-land.

It inherits DVM Theme from its parent, so set Light or Dark on your frame and the map follows.

**How to use it:**
- Put an instance at (0, 0) at the bottom of your map frame. Delete your drawn land, water and coast, and keep ships and overlays above it.
- If your frame already fills map/water, hide the instance's `water` layer (an override), as the replaced frames do.
- Hide any label you don't need with an instance override.
- To place a ship at a real position (Web Mercator): `x = (lon − lon0) · k` and `y = (merc(lat_top) − merc(lat)) · k`, where `k = w / (lon1 − lon0)` and `merc(φ) = ln tan(45° + φ/2)` in degrees.
- If a ship ends up on land, move it to the nearest water. `ships.py` in this folder does that.

Need another size or place? Ask the coastline agent; `basemap.py` makes one in about a minute.

| Component | Node id | Size | Bbox (lon0, lat0, lon1, lat1) | Source |
|---|---|---|---|---|
| `R2/Basemap/Baltic` | `70:2` | 1440 × 900 | 4, 54.3784, 36, 64.4638 | Natural Earth 10m |
| `R2/Basemap/Gulf of Finland` | `73:2` | 1440 × 900 | 22, 58.6658, 30.5, 61.3209 | OSM ocean polygons via OpenFreeMap tiles, z8 |
| `R2/Basemap/Helsinki approaches` | `70:25` | 1440 × 900 | 24.55, 59.9796, 25.45, 60.2598 | OSM coastline (Overpass) |
| `R2/Basemap/World` | `70:35` | 1440 × 900 | -180, -66.4888, 180, 79.1829 | Natural Earth 10m |
| `R2/Basemap/Helsinki offshore 1240×720` | `73:67` | 1240 × 720 | 24.218, 59.7762, 25.596, 60.1766 | OSM ocean polygons via OpenFreeMap tiles, z11 |
| `R2/Basemap/Gulf of Finland 1140×774` | `73:28` | 1140 × 774 | 22.6, 58.8616, 28.9, 61.0038 | OSM ocean polygons via OpenFreeMap tiles, z8 |
| `R2/Basemap/Helsinki harbour 1140×774` | `71:75` | 1140 × 774 | 24.9, 60.1262, 25.1, 60.1938 | OSM coastline (Overpass) |
| `R2/Basemap/North Sea & Baltic 1140×774` | `71:47` | 1140 × 774 | -6, 50.0545, 34, 64.504 | Natural Earth 10m |
| `R2/Basemap/World 1140×774` | `71:41` | 1140 × 774 | -180, -70.0741, 180, 80.8614 | Natural Earth 10m |
| `R2/Basemap/Helsinki archipelago 760×480` | `73:39` | 760 × 480 | 24.75, 59.8832, 26.25, 60.3551 | OSM ocean polygons via OpenFreeMap tiles, z10 |
| `R2/Basemap/Helsinki archipelago · generalised 760×480` | `71:64` | 760 × 480 | 24.75, 59.8832, 26.25, 60.3551 | Generalised on purpose from the OSM coast (before/after only) |
| `R2/Basemap/North Sea · Bergen 720×420` | `71:26` | 720 × 420 | -2, 57.7391, 13, 62.1163 | Natural Earth 10m |
| `R2/Basemap/Gulf of Finland 380×280` | `71:35` | 380 × 280 | 20.9, 58.383, 29.2, 61.4463 | Natural Earth 10m |
| `R2/Basemap/Helsinki approaches 380×280` | `73:22` | 380 × 280 | 24.45, 59.9066, 25.5, 60.2923 | OSM ocean polygons via OpenFreeMap tiles, z9 |
| `R2/Basemap/Helsinki South Harbour 380×280` | `71:70` | 380 × 280 | 24.9, 60.1342, 25.03, 60.1818 | OSM coastline (Overpass) |
| `R2/Basemap/Helsinki archipelago 372×232` | `73:45` | 372 × 232 | 25.1, 60.05, 25.55, 60.1898 | OSM ocean polygons via OpenFreeMap tiles, z11 |
| `R2/Basemap/Fehmarnbelt 300×220` | `73:56` | 300 × 220 | 10.6213, 54.4171, 11.4413, 54.7655 | OSM ocean polygons via OpenFreeMap tiles, z10 |
| `R2/Basemap/Gulf of Finland 300×220` | `71:56` | 300 × 220 | 18.9401, 58.5048, 25.5336, 60.9414 | Natural Earth 10m |
| `R2/Basemap/Gulf of Finland · east 300×220` | `92:2` | 300 × 220 | 22.63, 58.6238, 29.2235, 61.052 | Natural Earth 10m |
| `R2/Basemap/Puttgarden 300×220` | `73:62` | 300 × 220 | 11.182, 54.5007, 11.282, 54.5433 | OSM ocean polygons via OpenFreeMap tiles, z13 |
| `R2/Basemap/Tallinn Bay 300×220` | `73:48` | 300 × 220 | 24.1727, 59.529, 24.9927, 59.8325 | OSM ocean polygons via OpenFreeMap tiles, z10 |
| `R2/Basemap/Tallinn harbour 300×220` | `73:52` | 300 × 220 | 24.7067, 59.4468, 24.8067, 59.484 | OSM ocean polygons via OpenFreeMap tiles, z13 |

**Main four:**
- **Baltic** `70:2`
- **Gulf of Finland** `73:2`
- **Helsinki approaches** `70:25`
- **World** `70:35`: Natural Earth **10m**, simplified at 0.5 px at 1440 px wide. 10m was not too heavy.

**Baltic bbox:** the brief asked for lon 9–31, lat 53.5–66. At 1440 × 900 that can't be shown without distortion. The component shows lon 4–36, lat 54.4–64.5, so the northern Bothnian Bay is cropped; the Gulf of Finland component carries the detail.

**All geometry:** clipped to the bbox, Web Mercator, simplified at 0.5 px with no smoothing, and islands under 1 px² dropped.
