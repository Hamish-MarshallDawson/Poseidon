# 04. Tech stack and build plan (checked Sat 7 Nov 2026, ~16:00)

## 1. Verdict: AMBER

The map stack works and is free, with one real caveat: **deck.gl on MapLibre's globe is still buggy.** It is fine for dots on a flat map. It is risky for the "spinning globe" opener. The architecture is mostly sensible but has too many moving parts for ~16.5 hours. A convincing live map plus watchlist is achievable by 09:00 if the team ships the small version below and treats the ML model, GFW radar layer and Digitraffic failover as optional. The biggest risk is not the stack. It is that the live feed shows few real dark events during judging, so the demo needs a replay of a staged or recorded event.

## 2. Claims table

| # | Claim | Status | Evidence | Note |
|---|---|---|---|---|
| 1.17 | OpenFreeMap dark style at `https://tiles.openfreemap.org/styles/dark`, no key, no request limits | **confirmed** | https://openfreemap.org ("no registration, no user database, no API keys", "no limits on the number of map views or requests"); live GET returned HTTP 200, `application/json`, valid style v8 JSON | Attribution to OpenFreeMap, OpenMapTiles and OSM is required (MapLibre adds it automatically). The site lists the Dark style but does not print the URL; the URL works. Offline bulk download is capped at 3,000 tiles / 50 MB per download (irrelevant for us). |
| 1.18 | CARTO basemaps need a free key; non-commercial free to 5M tile requests/month | **confirmed, with a detail** | https://docs.carto.com/faqs/carto-basemaps | Since 25 Sep 2026 **raster** tiles are not served without a key. **Vector styles still load without a key "for now"**; CARTO recommends adding one. Live test: `https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json` returned 200 with no key. Counts are across all keys, raster and vector, per UTC month. So CARTO works as a fallback today with no sign-up, but could change. |
| 1.19a | MapLibre GL JS v5+ supports globe via `map.setProjection({type:'globe'})` | **confirmed** | https://maplibre.org/maplibre-gl-js/docs/examples/display-a-globe-with-an-atmosphere/ ; deck.gl docs install example uses `maplibre-gl@5.0.0` | Current release is **v6.16.0** (25 Oct 2026, GitHub releases). Jake's text says "v5 or later", which is true. Pin an exact version in `package.json` and do not upgrade mid-hack. |
| 1.19b | deck.gl `MapboxOverlay` with `interleaved: true` works with MapLibre's globe | **partly** | https://deck.gl/docs/api-reference/mapbox/overview says "Maplibre's globe projection is fully supported". GitHub issues say otherwise: visgl/deck.gl#10206, #9592, #10519, #9466 (all open) | Docs overclaim. Open bugs, detailed in section 3. Current deck.gl is **9.4.1** (28 Oct 2026); 9.4.2 is being tracked (#10972). Interleaved needs maplibre-gl v3+, which we satisfy. |

## 3. Known issues: deck.gl on MapLibre globe (all open on 7 Nov)

| Issue | What breaks | Hits us? | Workaround |
|---|---|---|---|
| [#10206](https://github.com/visgl/deck.gl/issues/10206) | **ScatterplotLayer**, interleaved + globe: z-fighting flicker on pan/zoom; large-radius circles are flat discs, not draped on the globe. Maintainer: ScatterplotLayer does not tessellate in globe mode. | **Yes.** Ship dots (small, pixel radius) are fine apart from flicker. The growing "ghost circle" (large radius) is wrong. | Set `parameters: {depthCompare: 'always', cullMode: 'back'}` on the layer to stop flicker. Draw ghost circles as a **GeoJsonLayer polygon** (turf `circle`) or as a native MapLibre `fill` layer, not a big ScatterplotLayer. |
| [#9592](https://github.com/visgl/deck.gl/issues/9592) | Globe integration: depth/culling wrong, layers draw behind the globe when `depthCompare:'always'`; non-billboard text upside down | Partly | Keep text/labels in MapLibre or HTML, not deck TextLayer. Use billboard text only. |
| [#10519](https://github.com/visgl/deck.gl/issues/10519) | Since 9.3.3, `TextLayer` and non-billboard `IconLayer` invisible on near side of globe (reported to affect zoom < 12) | Only if we use them | Avoid TextLayer; use pixel-sized Scatterplot or billboard icons. |
| [#9466](https://github.com/visgl/deck.gl/issues/9466) | Layers misproject when toggling mercator and globe at runtime; BitmapLayer/GeoJsonLayer do not react to projection change | Only if we toggle | Pick one projection at load. Or force new layer ids on `projectiontransition` (workaround in thread). |
| TripsLayer | I found **no open issue for TripsLayer on MapLibre globe specifically.** Related open: [#5631](https://github.com/visgl/deck.gl/issues/5631) (wrapLongitude, not relevant to Baltic), [#10387](https://github.com/visgl/deck.gl/issues/10387) (occasional artifacts), [#8927](https://github.com/visgl/deck.gl/issues/8927) (short segments with fine timestamps look wrong) | Maybe | **Untested by me on globe.** Trails are 2-D paths, so likely OK, but treat as unverified. Test in the first hour of frontend work. |

**Recommendation:** default to **flat Mercator**, zoomed to the Baltic, which has no known deck.gl bugs. Make the globe a 20-minute stretch goal, only for the opening 10 seconds, and fall back on the first glitch. Judges will remember a live map with a working watchlist, not a globe. If Aiden wants the globe, run deck.gl **non-interleaved** (`interleaved: false`), which avoids the depth-buffer fights (though #9592 says the non-interleaved case has culling oddities too; untested).

## 4. Architecture sanity check (answers Q1)

| Piece | Verdict | Note |
|---|---|---|
| Python asyncio + `websockets` ingest | Keep | Simple and right. Reader loop only enqueues; it matters because AISStream drops messages for slow readers and drops look like dark ships. |
| FastAPI WebSocket relay at 1 update/s | Keep | Browser cannot connect to AISStream directly. Send one JSON array per second, full snapshot of changed ships. Do not build rooms or auth. |
| Raw log for replay | Keep, **simplify** | Append **JSON lines** (gzip per hour), not Parquet. Replay is then `for line in file: sleep`. Convert to Parquet only if Jake needs it for Polars. This one file is also the training/eval set and the demo insurance. Start it in the first 30 minutes. |
| Polars + LightGBM | **Cut to optional** | Polars is fine for offline analysis, but live detection should be plain Python dicts. LightGBM adds value only if Jake gets enough labelled positives; with a few days of data, a hand-weighted score plus logistic regression (or even rule weights) is honest and explainable. Versions if used: polars 2.1.0, lightgbm 4.7.0, fastapi 0.162.2, websockets 17.4 (PyPI). |
| Digitraffic MQTT failover | **Demote to "only if time"** | Costs 1 to 2 hours (second schema, second library). The raw log already gives a fallback for the demo. Do it only if AISStream is flaky in the first 3 hours. |
| GFW SAR radar layer | **Cut first** | Needs a token, a licence question (non-commercial), tile handling, and is 5+ days old. Pretty, but not live. Replace with 3 or 4 hard-coded example detections if you still want the "seen by radar" beat. |
| Danish DMA history for training | **Risky** | 0.5 to 2.6 GB per day on shared Wi-Fi. Start one day downloading now on a phone hotspot or skip it and train/evaluate on the team's own recorded stream plus a threshold sweep. |
| Three lenses (Baltic, fishing, Hormuz) | **Cut** | Integration doc itself warns of this. One lens, live, Baltic. |

**Missing from the plan**

1. **A "never sleeps" laptop.** `caffeinate` is macOS; on Windows use `powercfg /change standby-timeout-ac 0` and disable lid-close sleep, plug in. Ingest laptop must not be the same machine the presenter closes.
2. **Network.** Ingest on a **phone hotspot**, not venue Wi-Fi (3 connections per IP, counted before auth; other teams may use AISStream). Judges' tables may have no good Wi-Fi, so the demo browser must work with the relay running **locally** (`localhost`). OpenFreeMap tiles need internet; bundle a small coastline GeoJSON as an offline basemap (~30 min job, Aiden) so a dead network does not give a blank map.
3. **A deployed URL for judges.** Not essential. Devpost reviewers like a link, but the hackathon is judged in person. If wanted: run the relay on the laptop and expose it with a Cloudflare quick tunnel (`cloudflared tunnel --url http://localhost:8000`). I did not test this. Do not host the relay on a cloud VM: AISStream issue #285 reports cloud IPs being closed after subscribing (not verified by me; see the sibling research file for AISStream).
4. **A scripted event.** A live feed rarely shows a clean "goes dark" in 3 minutes. Pre-pick 2 or 3 real gaps from the recorded log and bookmark their timestamps for replay. Be honest on screen that it is a replay.
5. **Ship-stale vs dark UI.** Without a one-line "why we think it is intentional" explanation per ship, the watchlist reads as a black box.
6. **Source control hygiene.** AISStream key in `.env`, not git. Repo is public-ish; the rules file says never make the repo public without asking.
7. **Time sync/dedupe.** Use receive time; AISStream `Timestamp` is second-of-minute only (claim 2.3, sibling check).

## 5. Critical path: ~16.5 h, Sat 16:30 to Sun 09:00 freeze

Principle: **a thin vertical slice first** (ingest, relay, dots, watchlist, all by about 21:00), then add signals. Everything after that is improvement, not rescue.

Assignments follow `team-skills.md`: Hamish = backend relay + agents + front-end integration; Aiden = map/React (his Cesium and web-app experience); Jake = detection, features, evaluation numbers; Mano = pitch, replay clips, rendezvous numerics, demo video. Jake also has a JPMorgan interview Monday, not a constraint tonight, but do not plan him for a 06:00 task.

| Clock | Hamish (ingest + relay) | Aiden (map + UI) | Jake (detection + eval) | Mano (pitch + replay + QA) |
|---|---|---|---|---|
| 16:30 to 18:00 | AISStream key, Baltic box, messages on screen, **raw JSONL logging running**, hotspot, disable sleep | Vite + React + MapLibre flat dark map (OpenFreeMap), dummy dots, deck.gl overlay working | Download OpenSanctions CSV; check how many sanctioned IMO/MMSI appear in the log after an hour; write signal definitions | Draft 3-minute story, pick 2 real documented cases, name and palette |
| 18:00 to 20:30 | `ShipState` dict, FastAPI WS 1 Hz snapshot, static-data join for IMO | Live ships from WS, risk colours, trails (`TripsLayer`) | Gap detector with neighbour check and per-cell message rate; speed-jump spoofing | Rendezvous detector prototype on the log (pairs <1 kn, <500 m, >1 h), numerics owner |
| 20:30 to 23:00 | **Replay mode** (same WS, reads JSONL at Nx speed, labelled "REPLAY"); watchdog and reconnect with backoff | Ghost marker + GeoJSON growth circle, watchlist panel, click to fly | Risk score v1 (weighted rules); sanctions join; precision numbers | Slides skeleton, results table template |
| 23:00 to 02:00 | Stabilise, queue-depth logging, discard gaps overlapping our own stalls | Counters (ships, msgs/s), replay scrubber, offline coastline fallback | Optional LightGBM/logistic vs baselines; top-20 precision with sample size | Record screen capture of a good replay event |
| 02:00 to 07:00 | **Sleep in shifts.** One person checks log at 03:00 and 06:00 | Sleep, then polish | Sleep, then freeze numbers | Sleep, then slides |
| 07:00 to 09:00 | Freeze backend, tag a git commit, test cold start on the demo laptop | Freeze frontend, optional globe opener | Final numbers into slides | Rehearse twice with timer, backup video |
| 09:00 to 12:00 | Bug fixes only | Bug fixes only | Q&A prep: false positives, GPS jamming caveat | Devpost write-up, final video |

**Likely to overrun**

1. Rendezvous detector and draught-jump signal (needs static data that arrives only every 6 minutes). Overruns by 2+ hours.
2. LightGBM training with few positives. Looks scientific, delivers noise.
3. Globe polish (bugs above).
4. Digitraffic second feed and schema unification.
5. GFW token, licence and tiles.
6. Sleep: the plan above has no slack for fatigue errors after 02:00.

**Cut order, first to last:** GFW radar layer, globe, Fishing and Hormuz lenses, Digitraffic, LightGBM (replace with weighted rules), draught-jump, rendezvous, spoofing, trails. **Never cut:** live dots, raw log, replay mode, ghost marker for a dark ship, ranked watchlist with a one-line reason.

## 6. Open-source starting points (answers Q3)

Stars, licence and push date via `gh api`, 7 Nov 2026. **Hackathon rule: only code written during the hackathon counts.** Treat these as references and libraries; copying code means following the licence and saying so on Devpost.

### Libraries to use directly

| Repo / package | Stars | Licence | Use |
|---|---|---|---|
| [visgl/deck.gl](https://github.com/visgl/deck.gl) 9.4.1 | 14,742 | MIT | `MapboxOverlay`, `ScatterplotLayer`, `TripsLayer`, `GeoJsonLayer` |
| [maplibre/maplibre-gl-js](https://github.com/maplibre/maplibre-gl-js) 6.16.0 | 12,036 | GitHub shows "NOASSERTION" (BSD-3-Clause per repo LICENSE, not re-verified by me) | Map engine |
| [visgl/react-map-gl](https://github.com/visgl/react-map-gl) 8.1.3 | 8,513 | GitHub shows "NOASSERTION" (MIT in package; not re-verified) | React wrapper; optional, plain MapLibre in a `useEffect` is as easy |
| [hyperknot/openfreemap](https://github.com/hyperknot/openfreemap) | 6,365 | GitHub shows "NOASSERTION" | Tile service we call, no code reuse needed |
| [M0r13n/pyais](https://github.com/M0r13n/pyais) 3.3.1 | 263 | MIT | Decode NMEA only if we use Kystverket or a raw feed. **Not needed for AISStream** (already JSON). |
| [aisstream/example](https://github.com/aisstream/example) | 133 | none shown (assume all rights reserved; read, do not copy) | 20-line subscribe example in several languages; shows the 3-second subscribe rule |

### Existing AIS maps and detectors (reference or competitor)

| Repo | Stars | Licence | What we could reuse | Warning |
|---|---|---|---|---|
| [FormerLab/shadow-fleet-tracker-light](https://github.com/FormerLab/shadow-fleet-tracker-light) | 44 | MIT | Python Baltic shadow-fleet tracker with `loitering_module.py`, `transshipment_module.py`, `webserver.py`, a vessel DB. Good for reading how someone defined loitering and STS. | It is a near-same idea. Judges who search will find it. Differentiate on replay, explanations and honest evaluation. |
| [MagicLex/ghost-fleet](https://github.com/MagicLex/ghost-fleet) | 1 | none shown | README: scores Baltic vessels by behaviour vs sanctioned fleet (gaps, loitering, STS, flag-hopping, draught swings), gradient-boosted model, claims ROC-AUC 0.92 and a "9.4x above a blind sanctions lookup". | **This is essentially our pitch, already built** (on Hopsworks). Read it for the evaluation framing (flag-grouped CV, lift over list lookup). Do not copy. Its numbers are unverified by me. |
| [imaddde867/NaviCast](https://github.com/imaddde867/NaviCast) | 3 | MIT | Live Baltic map from Digitraffic with FastAPI, MQTT client (`mqtt_client.py`), Digitraffic REST snapshot approach. Its README says it is in maintenance mode. Useful for Digitraffic topic and header handling. | Leaflet, not deck.gl. |
| [time2map/marine-eye](https://github.com/time2map/marine-eye) | 2 | MIT | React + MapLibre AIS map. Closest front-end skeleton to what Aiden will write. Demo at time2map.github.io/marine-eye. | Tiny, so check quality before trusting it. |
| [tg12/phantomtide](https://github.com/tg12/phantomtide) | 130 | none shown | Large maritime-intel dashboard with AIS anomaly features. Reference for UI ideas. | No licence means no reuse. |
| [Anton-Geo/shadow-fleet-ais-detection](https://github.com/Anton-Geo/shadow-fleet-ais-detection) | 0 | MIT | Streaming AIS pipeline for shadow-fleet anomalies and ranking, with `src`, `tests`, `visualization`. | Unproven. |
| [FogProtocol/ais-spoof-detector](https://github.com/FogProtocol/ais-spoof-detector) | 4 | MIT | Physics-based spoof checks (speed jumps etc.) in a small script. Quick reference for thresholds. | Tiny. |
| [sansastra/Anomaly-Detection](https://github.com/sansastra/Anomaly-Detection) | 36 | MIT | AIS on/off switching anomaly detection (academic). | Last pushed 2021. |
| [Ysurac/FlightAirMap](https://github.com/Ysurac/FlightAirMap) | 622 | AGPL-3.0 | Not useful. | AGPL; avoid. |

Searches for "deck.gl AIS" turned up no well-starred, maintained deck.gl AIS example. Everything with deck.gl and AIS is a single-digit-star demo, so the deck.gl official examples (TripsLayer, Mapbox overlay) are the better starting point. I did not find a mature, widely used open-source "dark vessel" tool; the closest are the three Baltic ones above.

## 7. Demo risk (answers Q4)

**Is the replay plan enough? Not quite.** Replay alone covers "the feed died." It does not cover these:

| Risk | Fix |
|---|---|
| Live feed is quiet, nothing "goes dark" in the slot | Open demo already in **replay at 30x** on a prepared 20-minute window that contains a known gap and a spoof. Switch to live only for the "this is real" proof (counter and msgs/s). |
| Venue Wi-Fi is blocked, slow or shared | Presenter laptop runs relay locally; replay reads a local file; basemap fallback is a bundled coastline GeoJSON. Test with Wi-Fi switched off. |
| Three slots, so the demo restarts three times | One-command start script; app boots straight into replay with no clicks. Each slot starts from a known state; no manual setup. |
| Replay looks fake | Label "REPLAY" on screen and say so. Judges from quant firms respect honesty; being caught unlabelled is fatal. |
| Browser dies or GPU glitch (globe) | Flat map by default. Backup screen recording on a USB stick and on the phone. |
| Recorded log is corrupted by a crash | Rotate files hourly; copy the best window to a separate `demo/` file at 02:00 and 07:00. |
| Judge asks "how do you know it is intentional?" | Have per-cell message-rate and neighbour check on a slide, plus the GPS-jamming caveat and top-20 precision with sample size. |

## 8. Smallest version that still demos well (answers the key judgement)

**Yes, this team can ship it.** Four people, two with strong web/back-end skill, one data person, one pitch person; the hard parts (decode, relay, map) are standard. The things that kill hackathon demos here are the feed, Wi-Fi and a thin story, not code.

**Minimum viable demo, buildable in about 8 hours of focused work:**

1. AISStream Baltic box, one Python process, JSONL log, FastAPI WS at 1 Hz.
2. Flat dark MapLibre map, deck.gl dots coloured by risk, fading trails.
3. Dark-gap detector with the "neighbours still talking" check, per-cell message rate to suppress receiver outages.
4. Speed-jump spoof flag.
5. OpenSanctions IMO/MMSI join, sanctions badge.
6. Ghost marker with growing circle on a gap; ranked top-20 watchlist with a one-line reason each.
7. Replay mode with speed control; three bookmarked events.
8. One slide of numbers: top-20 precision vs "all tankers" and "all gaps" baselines, with the sample size and honest limits.

That covers G-Research (visible, well-structured) and HRT (ranking, decision, evaluation). Everything else (model sophistication, radar layer, globe, Digitraffic, other lenses) is a bonus.

**Biggest threats to the 09:00 freeze:** (1) AISStream outage again, which is why the raw log must start within 30 minutes; (2) detector false positives eating Jake's night; (3) nobody owning the demo script. Name an owner (Mano) now.

## 9. Anything missed

- Competitor risk: `MagicLex/ghost-fleet` and `FormerLab/shadow-fleet-tracker-light` already do much of the pitch. Judges can search. Say what is different (live explanation, honest evaluation, replay of real events).
- `maplibre-gl` is already at 6.16 while Jake's doc says v5; the globe example still works on 5.x. Whatever is installed, pin it.
- CARTO and OpenFreeMap are both fine today; keep both style URLs in config and fall back on a tile-load error.
- I did not test AISStream, Digitraffic or the TripsLayer rendering in a browser, and did not verify licences beyond GitHub metadata (several show NOASSERTION).
