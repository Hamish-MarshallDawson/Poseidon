# Dark Vessel Monitor: feasibility report and go/no-go

Compiled Sat 7 Nov 2026, ~16:10, by Hamish's agent from six Sonnet agents' checks of `research/jake/dark-vessel-monitor/`. Details and every source are in the numbered files in this folder. Build time left: about **16.5 hours** (now to the 09:00 Sunday feature freeze), not 24.

## Verdict: GO, with five conditions

Every area came back **AMBER**: workable, nothing blocking, but the plan needs changes. Nothing came back RED. The idea fits G-Research well and HRT reasonably. The data is free and works today, and the team has the skills. Most of the risk is in the forecast's honesty and the live feed on the day, not in the code.

**Conditions:**
1. **The whole team agrees to it today.** Aiden has dropped Wordsmith and is free. The plan below needs all four people.
2. **Change the forecast target** (see "The forecast" below), and drop two claims: "flagged before it was sanctioned" and the 18,000-vessel figure.
3. **Live data is flowing and logged by about 17:30**, through AISStream on a phone hotspot with Digitraffic as backup. The raw log must start in the first 30 minutes and keep running.
4. **Flat map first; the globe is a stretch goal.** The demo opens in labelled replay mode, then switches to live.
5. **Freeze the model at about 23:00 tonight and commit it**, so that its forecasts can be scored against what really happens by Sunday morning.

**Stop or pivot if:** by about 18:00 neither AISStream nor Digitraffic gives a steady Baltic feed for 30 minutes. In that case, fall back to replay-only on Danish historical data, or reconsider the idea. If the first hours show almost no qualifying gaps, keep the forecast as a labelled "6-hour outlook" and lead with G-Research.

## Scorecard

| Area | Verdict | Headline | File |
|---|---|---|---|
| Live feeds | AMBER | **Digitraffic works with no key:** 947 vessels, 482 of them in the Gulf of Finland, at least 7 updates/s. It needs a gzip header. AISStream is up but has no SLA, lags 45 s to 2 min, and risks 429s on shared IPs. It has had **no Middle East data since mid-October**. Kystverket is Norway-only and timed out. | [01](01-live-feeds.md) |
| Historical data and labels | AMBER | DMA history is free, but it covers **Danish waters only**, lags 3 days, and is 3.4 GB a day unzipped. The OpenSanctions file is 36% port-state detentions: filter on `sanction` or `mare.shadow`. That leaves about 870 sanctioned vessels with an MMSI, and 11 to 23 shadow-tagged ships per 70 minutes in Danish waters. Only 25 vessels have both a designation date and an MMSI. | [02](02-historical-data-and-labels.md) |
| Detection and forecast | AMBER | Forecast "a suspicious gap starts in the next 6 h". Use sanctions as an input feature, not as the label. The neighbour check alone isn't enough: add a per-cell message rate. Evaluate against three baselines with intervals. | [03](03-detection-and-forecast.md) |
| Stack and build plan | AMBER | Use a flat MapLibre map, because **deck.gl on the globe has open bugs** (flicker, broken text and icons). Draw ghost circles as GeoJSON polygons. It can ship by 09:00 if the thin slice is done first. | [04](04-stack-and-build-plan.md) |
| Track fit and competition | AMBER | G-Research fit **8/10**, HRT **6.5/10**: lead with G-Research. Several stage claims need fixing (below). The nearest open-source rival is FormerLab's shadow-fleet-tracker-light (MIT, 44 stars, no forecast). | [05](05-track-fit-and-competition.md) |
| Unified data model | Fits | **Every source maps onto one schema.** Unverified until a key or token is available: GFW v3 field names, AISStream `time_utc` in a live payload, and Kystverket timestamps. Includes Pydantic and TypeScript code to paste in. | [06](06-unified-data-model.md) |

## The forecast: what changes

Jake's notes mix up two targets. The checks settle it:

- **Use target A: "a qualifying gap starts within 6 h"**, labelled by our own detector. A qualifying gap means: silent past the floor, at least 3 neighbours still heard, a steady message rate before the gap, and not in port, moored or anchored. This target forecasts a real future event with a clock, so judges can watch it come true or not.
- **Drop target B, "is this a shadow-fleet ship".** Its labels are circular, there's nothing to watch happen, and it looks like we rebuilt the sanctions list.
- **The labels are the weak point.** DMA history covers Danish waters only. Gaps there are mostly coverage holes and port entries, and GFW's own definition gives zero labels in the Danish straits. So **don't lean on a DMA backtest as the headline.** The honest headline is the **prospective test**:
  1. Freeze the model at about 23:00 and commit it to git.
  2. Log a forecast snapshot every 10 minutes.
  3. Score it at about 11:00 Sunday against what our detector saw.
  4. Report it against three baselines: "went dark before", "tankers near Russian ports", and the **cell-hour gap rate**. The cell-hour baseline exposes a model that only learned coverage holes.
  5. Include Wilson intervals and a vessel-level bootstrap. Six hits in ten means 31% to 83%, and the slide must say so.
- **Where the sanctions match goes:** agent 3 said use it as an input feature; agent 6 said keep it out of the headline model. Do both by keeping the forecast **behaviour-only** and bringing sanctions in at the **decision step** (the importance weight below), plus one "with list" ablation. Then the headline model can't simply rebuild the sanctions list.
- **Model:** logistic regression or weighted rules. LightGBM goes first if time is short, because with few positives it produces noise.
- **The decision step (HRT):** `inspect_score = P(gap in 6 h) × importance`. Importance counts the sanctions match, tanker type, draught jump and blank destination. Rank the ships and inspect the top k. Show a capture-rate-at-k curve against the baselines.
- **A second, quick number** (from agent 2): do behaviour-only features rank the shadow-tagged ships above the rest in a few hours of Danish data? This can be measured tonight. It supports "behaviour finds hidden ships" without claiming a forecast.
- **The mockup already fits this.** Its Replay/LIVE scrub bar and "Backtest top 10: hit vs baseline" card are the right shape. They need to show the real prospective numbers and one real replayed case.

## The unified data model (agent 6)

One schema that ingest, replay, detectors, forecast, watchlist, map and evaluation all use. Full tables, source mappings, WebSocket JSON shapes and code are in [06-unified-data-model.md](06-unified-data-model.md).

- **Keys and time:**
  - `mmsi` is the key. `imo` is a linked attribute whose check digit is validated before any sanctions join.
  - Identity changes (MMSI or IMO swaps, duplicate MMSIs) are recorded as spoof evidence, not errors.
  - Every record carries `ts` (event time) and `recv_ts` (when we had it), both as UTC epoch milliseconds. Detectors and the forecast only use records with `recv_ts <= as_of`, which is the no-leakage rule.
  - Where a source gives only the second within the minute, there's a rule to rebuild the full time.
- **Ten record types,** each with a source and quality flag: PositionReport, VesselStatic, Vessel (merged state in memory), GapEvent, SpoofEvent, SanctionsMatch, RiskScore/Forecast, WatchlistEntry, CoverageCell and Outcome.
- **One path for live, replay and backtest:** the raw append-only log replays through the same `normalise()` and detectors as live data. History goes into Parquet tables, and the browser gets a snapshot plus 1 Hz deltas over one WebSocket.
- **First-hour defaults:**
  - Hamish owns `dvm/models.py` and `normalise.py`, and field names are frozen by 17:30.
  - Class B vessels show on the map but are excluded from gaps, the forecast and the watchlist.
  - Gaps need at least 30 minutes, 20 times the ship's own reporting interval, and at least 3 neighbours within 20 km.
  - Coverage uses 0.1-degree cells over the Baltic box.
  - AISStream and Digitraffic are merged with de-duplication.

## Build plan (from agent 4, by skill)

| Clock | Hamish | Aiden | Jake | Mano |
|---|---|---|---|---|
| 16:30 to 18:00 | AISStream key, Baltic box, raw JSONL log running, hotspot, laptop never sleeps | Vite, React, MapLibre flat dark map (OpenFreeMap), deck.gl overlay | OpenSanctions filter and join; signal definitions; **measure the gap base rate** | 3-minute story, pick 2 real documented cases |
| 18:00 to 20:30 | Ship state, FastAPI WebSocket at 1 Hz, static-data IMO join | Live ships, risk colours, trails | Gap detector (neighbours plus per-cell rate), speed-jump spoof | Replay clips, demo script owner |
| 20:30 to 23:00 | Replay mode (same WebSocket, labelled REPLAY), watchdog and reconnect | Ghost circle, watchlist, click to fly | Risk score v1, **freeze the model at 23:00 and commit** | Slides skeleton, results template |
| 23:00 to 02:00 | Stabilise; drop gaps during our own stalls | Counters, scrub bar, offline coastline fallback | Baselines, intervals, decision curve | Record a good replay event |
| 02:00 to 07:00 | Sleep in shifts; check the log at 03:00 and 06:00 | Sleep, then polish | Sleep | Sleep, then slides |
| 07:00 to 09:00 | Freeze the backend, cold-start test | Freeze the frontend | Numbers into slides | Two timed rehearsals, backup video |

**Cut order, first to last:** GFW radar layer, globe, the Fishing and Hormuz scenes (Hormuz can't run live anyway), Digitraffic as a second live feed, LightGBM, draught jump, rendezvous detector, spoofing, trails. **Never cut:** live dots, the raw log, replay, the ghost marker, the ranked watchlist with a one-line reason.

## Fix before saying it on stage

| Claim | Correction |
|---|---|
| 1.9 Finland tracks 18,000+ vessels | Digitraffic showed **947** (482 in the Gulf of Finland) |
| 3.1 Half of shadow-fleet exports pass through the Baltic | The CEPA source dates from **Jan 2025**; say "2025 estimate" |
| 3.3 EU list passed 670 | **673** (41 added to 632); Council release via secondary sources |
| 3.4 "Constant" GNSS interference | The source is Oct 2024 and doesn't say "constant" |
| 4.4 VIIRS latency ~4 h | About **6 h** |
| 6.2 Palantir demo flags a warship going dark | **Unverified: don't say it** |
| 6.5 Skylight free, 300+ organisations | Free only for governments and qualifying NGOs; its own site says 200+ |
| 1.16 GFW intentional gap rule | Four conditions, not three (adds 14+ satellite positions in the prior 12 h) |
| Open question 3 | **"We flagged it before it was sanctioned" can't be tested.** Only 25 vessels qualify. Don't promise it. |

## Licences

OpenSanctions and GFW are both **CC BY-NC 4.0**. A student hackathon demo is very likely non-commercial, though this isn't legal advice. Credit both on screen and on Devpost, keep the GFW token on the backend, and don't redistribute the OpenSanctions file in the repo: download it at build time. Digitraffic is CC BY 4.0. Libraries: pyais (MIT) and MovingPandas (BSD-3) are reusable as libraries. GFW's repos (Apache-2.0) and AISdb (AGPL) are for ideas.

## Ethics answer (team rule: have a real privacy answer)

We rank ships for human review and never accuse. Every alert shows its reason codes and confidence. An alert is suppressed when neighbouring ships go quiet at the same time, which means coverage loss or jamming. Only ships already on public lists are named; all others show their MMSI or IMO only. The tool uses public broadcast data only and doesn't track crews. Show the false-positive rate.

## "Isn't this just Windward?"

"Windward is a paid platform scoring past behaviour for compliance teams. In a weekend, on free data, we built a forecast of which ships go dark next, ranked into an inspect-next list. Its accuracy was measured on forecasts we froze before the outcome, against simple baselines. We don't claim better data; we show the method and its measured accuracy."

## Still unverified

- The real gap base rate in the Gulf of Finland. Measure it in hour 1.
- AISStream live from the venue: it needs a key.
- Digitraffic over MQTT: only REST was tested.
- TripsLayer on the map.
- The GFW API: it needs a token.
- Kpler and Vortexa specifics.
- Several primary sources (NAVCEN, ITU) returned 403 and were checked through secondaries.
