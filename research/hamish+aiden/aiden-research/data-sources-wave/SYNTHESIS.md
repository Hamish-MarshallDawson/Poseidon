# Data sources wave: synthesis

Saturday 7 November 2026, about 18:00 UTC. Eleven DeepSeek agents, plus the orchestrator's own queries of AISStream and Global Fishing Watch (GFW). **This is evidence for discussion, not a project decision.** Agent reports sit beside this file. "Checked" below means the orchestrator ran it; agent-only figures are labelled.

## Verdict

Comparing what ships announce with what radar sees **does work**, for ships of about 50 m or more, on free data. It is strongest in northern European waters. Elsewhere it works mainly as a historical study, days old. It cannot name a ship from radar alone, prove intent, or follow a ship continuously.

## Is radar-to-AIS matching real?

`t-match`, one Sentinel-1 pass, 1 Nov, Great Belt and Fehmarn Belt. The orchestrator added a chance control by shifting AIS positions 3 to 8 km and keeping only sea positions.

| Moving ships, 50 m or more (16 per window) | Real, within 500 m | Chance, within 500 m |
|---|---|---|
| Great Belt, all detections | 94% | 13% |
| Fehmarn Belt, all detections | 88% | 23% |
| Great Belt, detections of 50 px or more | 94% | 4% |
| Fehmarn Belt, detections of 50 px or more | 62% | 3% |

- The signal is well above chance, but the sample is small and from one pass.
- Precision is the weak side: about 3,000 detections per window, mostly land edges, bridges and harbour works. A better land mask and structure mask are required.
- The moving-ship shift (about 600 m at 10 knots) is unresolved, because nearest-target matching hides it.
- **The open Ai2 detector runs here (108 s per 40 km window, RTX 4060) but is unproven.** In its larger window of 2,812 km² it reported 3 detections on valid imagery against 8 AIS vessels, 2 of them matched, and missed 4 that had bright returns. No moving ship was in valid imagery, so moving-ship performance is untested. Its 10 and 20 km chance control gave 0 matches at 200 and 500 m, on only 2 to 7 shifted points per shift. Its one radar-only target (85 m, 12.6444E 56.4543N) had no AIS within 3 km. GFW shows no detection within about 2 km of that point that day, so it remains unexplained.

## How current is the data? (checked unless noted)

| Source | Delay | Covers |
|---|---|---|
| Digitraffic AIS | About 0.5 s (agent) | Northern Baltic; Class A only; no fishing boats; no history |
| AISStream | Live; about 1 update a minute per ship | Strong in North Sea, Danish straits, Channel, US East; zero in Middle East, Natuna |
| Sentinel-1 raw radar | Usually 1 to 5 h, sometimes 10+ h | Coasts, not most open ocean |
| GPSJam | About 1 day (agent) | Follows aircraft coverage |
| Danish AIS archive | About 3 days | Danish waters; full tracks; back to 2007 |
| GFW radar detections | 3 to 4 days | Global coastal; almost none in Gulf of Finland |
| GFW AIS presence | 4 days | Global, all ship types |
| FRED Brent | About 4 days | Price |
| PortWatch | 6 days, weekly | 28 chokepoints, daily counts |

Global live satellite AIS exists only commercially.

## Regions

| Region | Radar passes a week at a point | Live AIS | Delayed AIS | Assessment |
|---|---|---|---|---|
| Danish straits | About 4.7 | Yes | Full tracks, 3 days | Best test bench |
| Gulf of Finland | About 5.1 | Best | Own recording only | Best live AIS, but few GFW radar detections |
| Hormuz | About 3 | None | GFW counts, 4 days | Strong study, not live |
| Malacca | About 0.7 to 0.9 | Only near Singapore | GFW | Sparse radar |
| Natuna | About 0.5 to 0.9, some points zero | None | GFW | Study only; no routine checks |
| Open ocean | Mostly zero | None | GFW | Out of scope |

## Hormuz and tankers

- **Official flow collapsed:** PortWatch tanker transits fell from 43.5 a day (Feb) to 0.7 a day (Oct). Tanker capacity fell from about 2.0 Mt to 13 kt a day, roughly 15 million to 0.1 million barrels a day of ship capacity at 7.33 barrels a tonne. This is carrying capacity, not cargo.
- **Ships did not vanish from the wider area:** GFW AIS in the box averaged 393 ships in February and 220 in October. Radar detections per day with data were 212 and 200.
- **Radar counts cannot measure traffic:** `t-regions` found its target counts fell only 0 to 32% across a 95% fall in transits. Many targets are anchored or small craft. Radar shows hulls, not cargo.
- **Silence:** tankers seen in the box in February 2026 and silent since August: 19%, compared with 10% for the same test in 2025. Malacca 12% vs 7%; Danish 10% vs 10%.
- **Most silent tankers came back under another identity:** in random samples of 40 with an IMO number, the same IMO later appeared under a different MMSI for 29 at Hormuz, 31 at Malacca and 38 in Danish waters. So this is widespread, not Hormuz-specific. IMO numbers in AIS are self-reported, and a reflag can be an ordinary sale.
- **Courses:** GFW's per-vessel position queries return 404 "temporarily unavailable". Anonymous hourly cell positions and per-vessel port visits work.

## Other findings

- **Danish gaps are mostly reception:** 1,407 gaps of 20 minutes or more on one day, clustered in the emptiest cells (agent).
- **Listed shadow tankers transmit normally there:** 31 had full data; 16 of 74 list-matched ships broadcast a name not on the list (agent).
- **Honest event rate may be low:** only 3 strict silences in 40 minutes on Digitraffic (agent). Hamish's forecast depends on this rate.
- **Open-source fusion already exists:** `esamoun/dark-vessel-detection`, `sat_tracker`, and Skylight's free map. None of the projects reviewed forecasts.
- **Reuse:** the hackathon allows open-source code if its licence is followed. `sat_tracker` has an unclear licence and `OrmuzOsint` has no licence file.

## Selling-point options

1. **Identity-aware tracking:** "this ship disappeared, and the same hull came back under a new name and flag". Testable today on free data. Needs a false-positive check against ordinary sales.
2. **Radar-checked gaps with a stated error budget:** one verified Danish example and honest match rates, with chance controls.
3. **Forecast frozen before the outcome:** no open project reviewed does this. Depends on enough real events.
4. **Hormuz investigation:** official transits against AIS presence, radar and identity changes, labelled as days old.

## Open questions

- A larger radar test: more passes, moving-ship correction and a better mask.
- How many identity changes are ordinary sales? Needs ownership data, such as Equasis.
- Whether GFW's per-vessel positions return during the hackathon.
- Whether Sunday's predicted passes occur: Danish straits about 05:23 UTC and Hormuz about 02:14 UTC (agent extrapolation).

## Corrections to earlier statements

- GFW radar is 3 to 4 days old, not at least 5 (checked here on one date range).
- `t-sat-access` (2.3 passes a week) and `d-imagery` (zero) on the mid-Atlantic used different points, 40N and 20N.
- `d-methods` 49% and `t-ais-history` 28% duplicate rates use different definitions and samples.
- Reports written before the GFW token arrived say Hormuz and Asia have no AIS access; GFW provides delayed AIS there.

Measurements come from a single day or small samples unless stated.
