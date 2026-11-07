# Dark Fleet Radar: API and Visualisation Research

Nov 7, 2026 · @Jake Callcut

*Exported from the Claude doc of the same name. "Dark Fleet Radar" was the working title at the time; the project is now "Dark Vessel Monitor (working title)". The doc is the live version; this copy is for review.*

## Verdict

Yes, we can build this on AISStream in 24 hours, with three conditions.

1. **Run a small server relay.** AISStream refuses direct browser connections, so the frontend talks to our own backend, never to AISStream.
2. **Focus on the Baltic (Gulf of Finland and the Danish straits).** Shore receivers there are dense, so a ship that disappears has probably switched off rather than sailed out of range. It is also the busiest shadow-fleet corridor in Europe.
3. **Keep a second live feed ready.** AISStream had a multi-day outage in August 2026. Finland's free Digitraffic feed covers the same waters and takes under an hour to wire in.

The biggest technical risk is mistaking a coverage hole for a ship going dark. The fix: only flag a gap when nearby ships are still being heard.

## AISStream: what you actually get

One free WebSocket that pushes decoded AIS messages as JSON for any area you draw boxes around ([docs](https://aisstream.io/documentation)). Sign-up is through a GitHub account.

| Item | Detail |
| --- | --- |
| Endpoint | `wss://stream.aisstream.io/v0/stream` |
| Subscribe | Send JSON within 3 seconds of connecting: `APIKey` (required), `BoundingBoxes` (required), `FiltersShipMMSI` (optional, up to 200), `FilterMessageTypes` (optional) |
| Box format | `[[[lat1, lon1], [lat2, lon2]]]`, several boxes allowed, overlaps not duplicated |
| Change area | Resend the subscription on the same socket; it replaces the old one |
| Envelope | `MessageType`, `MetaData` (MMSI, ShipName, Latitude, Longitude), `Message` |
| Message types | 25, including `PositionReport`, `ShipStaticData`, `StandardClassBPositionReport`, `ExtendedClassBPositionReport`, `StaticDataReport`, `StandardSearchAndRescueAircraftReport` |
| Position fields | `UserID` (MMSI), `Latitude`, `Longitude`, `Sog` (speed), `Cog` (course), `TrueHeading`, `NavigationalStatus`, `Timestamp` |
| Static fields | `ImoNumber`, `Name`, `CallSign`, `Destination`, `Eta`, `MaximumStaticDraught`, `Dimension`, ship type |
| Wire format | Binary frames of UTF-8 JSON; enable `permessage-deflate` compression |

Two things matter for us. `ShipStaticData` carries the IMO number, which is how we join live ships to the sanctions list. `MaximumStaticDraught` changes when a tanker loads, so a draught jump after a gap hints at a hidden cargo pickup.

AISStream describes itself as beta, and its data models are not guaranteed stable, so parse defensively.

## Limits and gotchas

The limits are generous for one team, but the service is unreliable enough that we must plan for it dropping out mid-demo.

| Constraint | Limit | What it means for us |
| --- | --- | --- |
| Connections per account | 3; a fourth is rejected | One ingest process, one spare, one for testing |
| Connections per IP | 3, counted before authentication | Teammates on the same venue Wi-Fi share this |
| Browser connections | Not permitted | Backend relay is mandatory |
| Subscription updates | 1 per second per connection | Do not resubscribe on every map pan |
| Slow readers | Messages dropped once buffers fill | Read in a tight loop, queue processing separately |
| Replay | None; missed events are gone | Record the stream to disk from hour one |
| Uncompressed connections | Bandwidth-limited since September 2026 | Turn compression on |
| Uptime | No SLA stated | Fallback feed ready (next sections) |

**Recent reliability problems.** Open issues on the project's [issue tracker](https://github.com/aisstream/issues/issues) include a silent stream from 5 August 2026 (connects and subscribes, zero messages), an expired SSL certificate on 11 August, API key sign-up timing out, and connections from a Google Cloud IP closing about 700 ms after subscribing. The last one suggests running the relay from a laptop rather than a cloud server.

No error codes are documented. Connections close for: a late or malformed subscription, a bad key, too many connections, updating too fast, fragmented messages, missed keepalives or a slow connection. Reconnect with exponential backoff and resend the full subscription each time.

## The coverage trap, and why the Baltic

A ship vanishing from AISStream usually means it left receiver range, not that it switched off. AISStream's data comes from a network of receiving stations, and it mentions no satellite feed. Shore-based AIS fades quickly once ships move into open ocean ([AXSMarine](https://public.axsmarine.com/blog/ais-for-shipping)). Judges from quant firms will spot a false-positive machine immediately.

**Our rule: a gap only counts if the neighbours are still talking.** If other ships in the same area are still being received while one goes silent, reception is fine and the silence is the ship's choice. Global Fishing Watch uses the same logic in stricter form: it only calls a gap intentional if it lasts 12 hours or more, starts at least 50 nautical miles from shore, and starts in an area with good reception ([gfwr notes](https://globalfishingwatch.r-universe.dev/gfwr/NEWS.txt)). We cannot wait 12 hours in a demo, so we lean on the neighbour check and a shorter threshold.

**Why the Baltic is the right stage:**

- Dense, open shore coverage. Finland's network alone tracks well over 18,000 vessels at a time across the Gulfs of Finland and Bothnia ([Digitraffic via Apify](https://apify.com/parseforge/finland-digitraffic-marine-ais-scraper.md)).
- It matters. Around half of shadow-fleet oil exports pass through the Baltic ([CEPA](https://cepa.org/article/choking-russias-shadow-fleet-in-the-baltic/)). In April 2026, 30 to 40 shadow-fleet tankers were idling near Russian waters and in the narrow strip of international water between Finland and Estonia ([Moscow Times](https://www.themoscowtimes.com/2026/04/14/idling-shadow-fleet-tankers-threaten-baltic-security-and-environment-experts-warn-a92498)).
- The EU's shadow-fleet list passed 670 vessels in its 21st sanctions package on 23 July 2026 ([Grosswald tracker](https://www.grosswald.org/baltic-sea-security-tracker/)), so there are plenty of labelled ships to test against.

First-hour check: plot a few hours of AISStream positions in the Baltic box. Wherever there are no dots, there is no receiver, and gaps there must be ignored.

**Second trap: GPS jamming.** Finland's Coast Guard has reported constant satellite-navigation interference in the Baltic, and tankers spoofing their positions to hide visits to Russia ([MarineLink](https://marinelink.com/news/finland-coast-guard-detects-satnav-518723?cid=87)). Jamming makes honest ships look odd. So in the Baltic, *spoofing* (impossible jumps, circling while "anchored") is as important a signal as going dark. One documented case: an LPG tanker heading for Ust-Luga drew circular AIS patterns for about 10 days in the Gulf of Finland while it was really loading in port ([Hellenic Shipping News](https://www.hellenicshippingnews.com/?p=1110298)). That is a ready-made demo story.

## Backup feeds and supporting datasets

Everything we need beyond AISStream is free for non-commercial use, which covers a hackathon.

| Source | What it gives us | Access | Role |
| --- | --- | --- | --- |
| [Digitraffic (Finland)](https://digitraffic.fi/en/marine-traffic) | Live vessel locations and metadata over MQTT-over-WebSocket, covering most of the Baltic and Gulf of Finland | No key; topics `vessels-v2/+/location` and `vessels-v2/+/metadata`; CC BY 4.0 | **Hot spare live feed** for the Baltic |
| [Kystverket (Norway)](https://www.kystverket.no/en/sea-transport-and-ports/ais/access-to-ais-data/) | Raw AIS (NMEA) over TCP covering Norwegian coastal waters | `153.44.253.27:5631`, no registration; decode with `pyais` | Optional second spare |
| [Danish Maritime Authority](https://www.dma.dk/safety-at-sea/navigational-information/ais-data) | Daily historical AIS CSVs for Danish waters (roughly 0.5 to 2.6 GB a day) | Free download | **Training and backtesting** |
| [Global Fishing Watch Events API](https://globalfishingwatch.github.io/GFW_technical_documentation/files/gaps.html) | Catalogued AIS gap events, filtered for likely intentional switch-offs | Free token, non-commercial | **Labels** to check our gap detector |
| [Global Fishing Watch SAR detections](https://globalfishingwatch.org/our-apis/documentation/docs/v3/4wings) | Ships detected by Sentinel-1 satellite radar, matched or unmatched to AIS, 2017 to 5 days ago | Same token; PNG map tiles available | **"Seen by radar, silent on AIS" overlay** |
| [OpenSanctions maritime](https://www.opensanctions.org/datasets/maritime/) | Sanctioned vessels CSV (4.9 MB), columns include `imo`, `mmsi`, `flag`, `risk`, `datasets`, `aliases` | Daily updates, CC BY-NC 4.0 | **Ground truth**: which ships are sanctioned |

**The join that makes it work:** a live `ShipStaticData` message gives a ship's IMO number; OpenSanctions lists sanctioned IMO numbers (and MMSIs where known). That match turns an anonymous dot into "EU-sanctioned tanker, Cook Islands flag".

**The overlay that wins G-Research:** Global Fishing Watch's radar detections that match no AIS signal are, literally, ships that are there but not broadcasting. Showing them beside our live gaps is the clearest possible answer to "show us what's hidden". The data runs to 5 days ago, so it's a historical layer, not live.

## What we detect, predict and decide

We turn the stream into a live risk score per ship, then an automated, ranked watchlist that we can test against the sanctions list.

**Signals computed live, per vessel:**

| Signal | How we compute it | Why it matters |
| --- | --- | --- |
| Dark gap | Silent for longer than its usual reporting interval allows, while ships within ~20 km are still heard | Deliberate switch-off |
| Spoofing | Speed implied between two fixes is impossible (e.g. over 40 knots for a tanker), positions on land, or tight circles while reporting "at anchor" | Faked location, common in the Gulf of Finland |
| Identity mismatch | The flag implied by the MMSI's first three digits differs from the declared flag; IMO missing or changed; name changes | False flags and reflagging |
| Rendezvous | Two tankers within ~500 m, both under 1 knot, for over an hour, away from port | Ship-to-ship oil transfers |
| Draught jump | `MaximumStaticDraught` rises after a gap or rendezvous | Picked up cargo out of sight |
| Destination games | Destination blank, vague or changed often | Hides where the cargo goes |
| Sanctions link | IMO or MMSI on OpenSanctions | Known bad actor |

The thresholds above are starting points to tune on the Danish historical data, not established values.

**Prediction (HRT's brief):** the probability that a vessel is shadow fleet, from behaviour alone with the sanctions flag hidden. Train a simple gradient-boosted model or logistic regression on per-vessel features from a few days of Danish data, with sanctioned ships as positives. Test on sanctioned ships held out of training: *would we have picked them out without being told?*

**Automated decision:** a ranked "inspect next" queue of the top 20 vessels, refreshed every minute, with an alert when a ship crosses a risk threshold.

**Evaluation slide:** precision in the top 20 for our model, against two naive baselines: "flag every tanker" and "flag every ship with a dark gap". Add an ablation showing how much each signal adds. That table is what the HRT judges will look at hardest.

Open question: OpenSanctions' CSV has no designation dates. If the entity JSON has them, we can test whether we flag ships *before* they were sanctioned, which is a much stronger claim.

## Map and visualisation stack

Use MapLibre GL JS for the map and deck.gl on top for the data. It's free, needs no paid tokens, and does a spinning globe that zooms down to a flat map.

| Piece | Choice | Why |
| --- | --- | --- |
| Map engine | [MapLibre GL JS](https://maplibre.org/maplibre-gl-js/docs/examples/display-a-globe-with-an-atmosphere/) v5 or later | Globe projection with atmosphere, set with `map.setProjection({type: 'globe'})` after the style loads |
| Data layers | [deck.gl](https://deck.gl/docs/api-reference/mapbox/overview) via `MapboxOverlay` with `interleaved: true` | GPU rendering of thousands of moving points; MapLibre's globe is fully supported |
| Basemap | [OpenFreeMap](https://openfreemap.org) dark style, `https://tiles.openfreemap.org/styles/dark` | No key, no request limits; keep the OpenStreetMap attribution |
| Basemap fallback | [CARTO Dark Matter](https://docs.carto.com/faqs/carto-basemaps) | Now needs a free key; non-commercial use is free up to 5 million tile requests a month |
| Frontend | React with `react-map-gl` | deck.gl's documented pattern for this setup |

**Layers, in drawing order:**

1. **Radar detections (historical):** Global Fishing Watch SAR tiles, unmatched detections only, as a faint raster layer.
2. **Trails:** deck.gl's [`TripsLayer`](https://deck.gl/docs/api-reference/geo-layers/trips-layer) gives fading wakes behind each ship, driven by a `currentTime` value. The same clock powers a replay scrubber.
3. **Ships:** a scatter or icon layer, coloured by risk score (grey for normal, amber, red), sized by ship length.
4. **Ghosts:** where a ship went dark, a hollow marker at its last position, plus a growing "could be anywhere in here" circle (radius = last speed × time since last seen). This is the signature visual.
5. **Spoofing:** the faked track in dashed red, with impossible jumps highlighted.
6. **Rendezvous:** a pulsing ring where two tankers met.

**Around the map:** a ranked watchlist panel on the right (click to fly to a ship), a live counter of ships tracked and messages per second (proof for HRT that we handle a real stream), and a timeline at the bottom for replay.

**Performance:** batch the server's updates to the browser once a second, not per message. Keep ship state in typed arrays and only rebuild the layers that changed.

## Architecture

One Python backend running on a laptop does ingest, detection and fan-out. The browser only ever talks to it.

```
AISStream (WebSocket) --+
                         +--> Ingest + normalise --> Vessel state (in memory) --> Detectors + model --> Risk scores
Digitraffic (MQTT) -----+          |                                                                    |
                                   +--> Raw log to disk (replay)                                        v
Danish history (CSV) --> Offline training --> model file                FastAPI WebSocket, 1 update/s --> Browser map
OpenSanctions CSV ------> IMO/MMSI lookup -----------------------------^
```

| Component | Tech | Job |
| --- | --- | --- |
| Ingest | Python `asyncio` + `websockets` (AISStream), `paho-mqtt` (Digitraffic) | Read both feeds, map to one schema: `mmsi, ts, lat, lon, sog, cog, heading, source` plus static fields |
| Raw log | Append-only Parquet or JSON lines | Replay mode for the demo; nothing is lost on a crash |
| State | Dict keyed by MMSI, plus a grid of recent positions for neighbour checks | Last fix, short track, static data, risk |
| Detectors | Plain Python or Polars, run every few seconds | Gap, spoofing, identity, rendezvous, draught signals |
| Model | scikit-learn or LightGBM, trained offline | Turns signals into one risk score |
| API | FastAPI WebSocket | Pushes batched ship updates, alerts and the watchlist |
| Frontend | React, MapLibre, deck.gl | Map, watchlist, counters, replay |

Replay mode matters most: if both live feeds die during judging, we replay the recorded stream at 10 to 60 times speed and the demo looks the same.

## 24-hour build plan and team split

Assumes four people; with three, merge Detection into Data. Have the live map working by hour 8 so everything after that is improvement, not rescue.

| Hours | Data and ingest | Detection and model | Map and frontend | Pitch and brand |
| --- | --- | --- | --- | --- |
| 0–2 | AISStream key, Baltic box, messages on screen; start raw logging | Download one Danish day and the OpenSanctions CSV; count sanctioned ships present | MapLibre globe + OpenFreeMap dark + dummy dots | Name, logo, colour palette; draft the 3-minute story |
| 2–6 | Digitraffic fallback; unified schema; FastAPI WebSocket | Gap detector with the neighbour check; spoofing (impossible speed) | Live ships from the backend; trails with `TripsLayer` | Find 2 or 3 real documented cases to feature |
| 6–12 | Coverage map from logged data; static-data join to sanctions | Identity, rendezvous and draught signals; features from Danish data | Ghost markers, risk colours, watchlist panel | Slides: problem, how we find it, results |
| 12–18 | Replay mode; load testing | Train model; precision in top 20 vs baselines; ablation | Replay scrubber; Global Fishing Watch radar layer; counters | Record a backup demo video |
| 18–22 | Freeze the backend; bug fixes | Final numbers onto slides | Polish, fly-to animations, loading states | Rehearse twice, timed |
| 22–24 | Submission write-up | Q&A prep on method and false positives | Freeze the frontend | Final run-through |

Feature freeze at hour 18. Anything not working by then is cut, not fixed.

## Demo script and branding

Lead with the map and the vanishing ship; finish on the results table.

**Name options**

- **Ghostwake**: the trail a ship leaves after it disappears.
- **Lights Out**: plain and memorable.
- **Dark Fleet Radar**: the working title, clear but generic.

**Tagline:** "Every big ship must say where it is. We find the ones that stop." (AIS is required on ships of 300 gross tonnes and above on international voyages, per [AISStream's overview](https://aisstream.io).)

**Look:** near-black navy background (#0B1220), radar green for normal traffic (#3DDC97), amber for watch (#FFB020), red for alerts (#FF4D4F). JetBrains Mono for numbers and readouts (JetBrains is a sponsor), Inter for text. A slow radar sweep on the loading screen.

**Three-minute demo:**

1. **0:00** Spinning globe, live dots everywhere. Counter: ships tracked, messages per second.
2. **0:20** Fly into the Gulf of Finland. Trails flowing past Helsinki and Tallinn.
3. **0:40** One tanker goes silent. Its ghost circle starts growing. "Ships around it are still heard, so it's not coverage. It chose to go dark."
4. **1:05** Click it: sanctions match, flag mismatch, draught jumped after its last gap.
5. **1:25** Spoofing case: the circling "anchored" tanker that was really in port.
6. **1:45** Radar layer on: satellite-detected ships with no AIS at all. "These are the ships nobody can see."
7. **2:05** The watchlist: our model's top 20, ranked automatically.
8. **2:25** Results: precision in the top 20 vs naive baselines, and which signals mattered.
9. **2:50** Close: what this does for coastguards, insurers and commodity traders.

**Framing to keep:** the tool ranks ships for a human to check. It does not accuse anyone. Judges will ask about false positives; have the precision numbers and the GPS-jamming caveat ready.

## Risks and first-hour checks

Do these in the first hour; each one can kill or reshape the project.

- [ ] AISStream key works and Baltic messages arrive within 10 minutes (sign-up itself had timeouts in August)
- [ ] Measure messages per second for the Baltic box, so we know what the backend must handle
- [ ] Digitraffic MQTT connects and shows the same area
- [ ] Plot an hour of positions to map where coverage actually is
- [ ] Join the OpenSanctions CSV to live IMO numbers: how many sanctioned ships are in the Baltic right now?
- [ ] Create a Global Fishing Watch token (issued instantly after registering)
- [ ] Download one Danish historical day and check it loads in Polars
- [ ] Start raw logging and leave it running all night
- [ ] Run ingest from a phone hotspot, not venue Wi-Fi (shared IP, see below)
- [ ] Disable sleep on the ingest laptop (`caffeinate -dims` on macOS) and keep it plugged in

### Failure playbook

Most failures are fixable with fallbacks we build in the first six hours. A few are limits of the data itself and are handled by how we frame the demo.

**Access and rate limits**

| Problem | How it shows up | Fix |
| --- | --- | --- |
| Venue shares one public IP | AISStream allows 3 open connections per IP, counted before authentication. Other teams on the same Wi-Fi using AISStream can lock us out | Ingest over a phone hotspot; hold one long-lived connection |
| Retry storm gets the IP blocked | One team's reconnect loop got its IP rate-limited (HTTP 429) for days in August 2026 ([issue #287](https://github.com/aisstream/issues/issues)) | Exponential backoff with jitter, capped; never reconnect in a tight loop |
| Digitraffic throttles anonymous clients | 429 errors without a `Digitraffic-User` header ([Digitraffic](https://www.digitraffic.fi/en/news/2024/12/03/api-throttles-turned-on-en.html)) | Send `Digitraffic-User: <team>/darkfleet` on every connection |
| Cloud IPs closed after subscribing | Reported for a Google Cloud IP ([issue #285](https://github.com/aisstream/issues/issues)) | Run the relay on a laptop |
| Venue firewall blocks odd ports | Kystverket's raw feed uses TCP port 5631 | Hotspot, or skip Kystverket; Digitraffic uses standard HTTPS |
| Big downloads on shared Wi-Fi | Danish history is 0.5 to 2.6 GB a day | Start now, one or two days only, crop to the Baltic box, save as Parquet |

**Reliability**

| Problem | How it shows up | Fix |
| --- | --- | --- |
| AISStream goes silent with no error | Connects and subscribes, zero messages (happened from 5 August 2026) | Watchdog: no message for 30 s, switch to Digitraffic automatically; show the live source on screen |
| Disconnects mid-stream | Socket closes for many undocumented reasons | Reconnect, resend the full subscription within 3 s |
| **Our own backend falls behind** | AISStream silently drops messages for slow readers. Dropped messages look exactly like ships going dark | Reading loop does nothing but enqueue; processing runs separately; log queue depth; discard any gap that overlaps one of our own stalls |
| Laptop sleeps overnight | Logging stops, no replay data | `caffeinate`, power on, check logs at 3am |
| Live data dies during judging | Nothing moves on screen | Replay mode, labelled "Replay" on screen; a recorded video as the last resort |
| Basemap tiles fail to load | Blank map | CARTO key as a second basemap; a bundled coastline GeoJSON as the offline floor |

**Weak or misleading signal**

| Problem | How it shows up | Fix |
| --- | --- | --- |
| Anchored ships look dark | Class A ships report every 2 to 10 s underway but only every 3 minutes at anchor; Class B every 30 s or 3 minutes ([US Coast Guard](https://www.navcen.uscg.gov/node/84)) | Gap threshold relative to the ship's expected rate, with a floor (start at 30 minutes and tune) |
| A receiver goes offline | Every ship in one area "goes dark" at once | Track message rate per map cell; many ships silent together means a receiver outage, not intent |
| GPS jamming | Many ships jump together | Same cell-level check: simultaneous jumps are jamming; one ship alone is spoofing |
| Timestamps are coarse | The position report's `Timestamp` is only the second within the minute (0 to 59) | Use our receive time; check whether `MetaData` carries a full UTC time |
| Duplicates | Same report heard by several receivers | De-duplicate on MMSI + timestamp + position |
| Identity arrives late or lies | Static data (with the IMO number) comes every 6 minutes; Class B never sends IMO; IMO and MMSI are self-reported | Show "identity pending"; treat conflicts between MMSI, IMO and flag as a risk signal, not an error |
| Few real dark events in 24 hours | Nothing dramatic happens live | Replay historical events from the Danish data; feature documented cases; lean on spoofing, which is more common in the Gulf of Finland |
| Few labelled positives, circular labels | Only a handful of sanctioned ships in a few days of data; some were sanctioned *because* of the behaviour we detect | Split train and test by vessel; report precision in the top 20 with the sample size; say plainly what it does and does not show |

**Limits we cannot engineer around (handle them in the pitch)**

- **We cannot prove intent.** There is no ground truth for a live gap. We rank ships for a human to check; we do not accuse.
- **We only see where receivers are.** Many shadow-fleet transfers happen in open water out of shore range. The radar layer helps, but only for the past.
- **Radar data is at least 5 days old**, so it is never a live layer.
- **Free services have no uptime guarantee.** We can fail over and replay, not fix them.
- **Sanctions lists are incomplete by design.** Unsanctioned shadow ships count as "clean" in our labels, which makes our precision look worse than it is. Say so; it's a point in our favour.

## Sources

- [AISStream documentation](https://aisstream.io/documentation)
- [AISStream home page](https://aisstream.io)
- [AISStream issue tracker](https://github.com/aisstream/issues/issues)
- [AXSMarine: AIS coverage, terrestrial vs satellite](https://public.axsmarine.com/blog/ais-for-shipping)
- [Global Fishing Watch: AIS gaps documentation](https://globalfishingwatch.github.io/GFW_technical_documentation/files/gaps.html)
- [Global Fishing Watch: gfwr release notes (gap criteria)](https://globalfishingwatch.r-universe.dev/gfwr/NEWS.txt)
- [Global Fishing Watch: 4Wings API and SAR detections](https://globalfishingwatch.org/our-apis/documentation/docs/v3/4wings)
- [Digitraffic marine traffic](https://digitraffic.fi/en/marine-traffic)
- [Finland Digitraffic AIS scraper listing (vessel counts)](https://apify.com/parseforge/finland-digitraffic-marine-ais-scraper.md)
- [Kystverket: access to AIS data](https://www.kystverket.no/en/sea-transport-and-ports/ais/access-to-ais-data/)
- [pyais: reading the Kystverket live stream](https://pyais.readthedocs.io/en/stable/_sources/examples.rst.txt)
- [Danish Maritime Authority: AIS data](https://www.dma.dk/safety-at-sea/navigational-information/ais-data)
- [OpenSanctions: maritime dataset](https://www.opensanctions.org/datasets/maritime/)
- [CEPA: choking Russia's shadow fleet in the Baltic](https://cepa.org/article/choking-russias-shadow-fleet-in-the-baltic/)
- [Moscow Times: idling shadow fleet tankers](https://www.themoscowtimes.com/2026/04/14/idling-shadow-fleet-tankers-threaten-baltic-security-and-environment-experts-warn-a92498)
- [Grosswald: Baltic Sea security tracker](https://www.grosswald.org/baltic-sea-security-tracker/)
- [MarineLink: Finland Coast Guard detects jamming and spoofing](https://marinelink.com/news/finland-coast-guard-detects-satnav-518723?cid=87)
- [Hellenic Shipping News: spoofing LPG tanker](https://www.hellenicshippingnews.com/?p=1110298)
- [MapLibre: globe with atmosphere](https://maplibre.org/maplibre-gl-js/docs/examples/display-a-globe-with-an-atmosphere/)
- [deck.gl: Mapbox and MapLibre integration](https://deck.gl/docs/api-reference/mapbox/overview)
- [deck.gl: TripsLayer](https://deck.gl/docs/api-reference/geo-layers/trips-layer)
- [OpenFreeMap](https://openfreemap.org)
- [CARTO basemaps FAQ](https://docs.carto.com/faqs/carto-basemaps)
