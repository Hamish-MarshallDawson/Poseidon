# t-ais-live: live AIS feeds, actually connected and measured (agent t-ais-live)

One continuous run: Sat 7 Nov 2026 **16:31:50–17:12:16 UTC** — 40 min of MQTT (86,999 position
messages), 480 REST polls, plus point tests. Everything here is `measured` unless marked `documented`;
AISStream figures are the orchestrator's, not mine.

Scratch `$WAVE=/tmp/claude-1000/-home-aiden-Projects-Personal-Hedged-Bets-hacktheburgh/703a82eb-0773-4b07-b85c-af65197add0d/scratchpad/wave`.
Scripts `$WAVE/scripts/t-ais-live/` (`mqtt_collect.py`, `rest_collect.py`, `analyze.py`, `silence.py`,
`anomalies.py`, `rest_silence.py`); raw JSONL in `$WAVE/data/t-ais-live/`.

**AIS** = Automatic Identification System: ships broadcast identity, position, course, speed and
static details over VHF. **Class A** is the mandatory commercial transponder (2–10 s under way, 3 min
at anchor); **Class B** is the cheap leisure version (30 s).

## Bottom line

1. **Digitraffic (Fintraffic, Finland) is the only no-account live feed that works from here, and it
   is good**: 36.25 messages/s, 656 distinct vessels in 40 min, measured delay from fix to our process
   **median 0.5 s, p90 0.9 s**. CC BY 4.0, commercial use with attribution. Routes: MQTT over
   WebSocket (live) and REST (last-known snapshot).
2. **The Norwegian route is dead for us.** Kystverket's documented no-registration TCP feed times out;
   BarentsWatch's AIS Live API returns `401 www-authenticate: Bearer` on every endpoint — registration
   plus OAuth client is mandatory.
3. **No history in either route.** REST serves one last-known position per MMSI and `from`/`to` filter
   that timestamp, so positions at a past satellite pass are unrecoverable. What it does give is a
   long-retention **silence index** ("who last reported in this 10-minute window"), which I validated
   against our own log: across three past windows REST returned 19/18/21 against our truth 20/18/20.
4. **Digitraffic is Class A only and deletes fishing vessels** (documented; 0 of 837 vessels has ship
   type 30). Fine for the tanker story, useless for illegal fishing. Ship types are folded, so
   "tanker" is always type 80.
5. **Silence is separable from reception loss in the core lanes and the honest event rate is tiny**:
   of 213 silences ≥ 5 min, reception held in 94%, but only **3** were "under way, not anchored or
   moored, with ≥ 3 neighbours still reporting". Bonus: five vessels reported the **same impossible
   inland Russian coordinate at 34–102 kn**, one teleporting 352 km from the Primorsk approach.

## Findings

### 1. Digitraffic MQTT — the working live feed

Working recipe (paho-mqtt 2.2.0, Python 3.12):

```python
c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, transport="websockets")
c.ws_set_options(path="/mqtt", headers={"Digitraffic-User": "hacktheburgh/feasibility"})
c.tls_set()                      # required; without it the WebSocket handshake hangs, then times out
c.connect("meri.digitraffic.fi", 443, 60)
c.subscribe([("vessels-v2/+/location", 0), ("vessels-v2/+/metadata", 0), ("vessels-v2/status", 0)])
```

Failures I hit: MQTT-over-TLS on port 8883 **times out**; WebSocket without `tls_set()` times out at
the handshake. MMSI is the topic, not a payload field. Payload: `time` (epoch **seconds**), `lat`,
`lon`, `sog`, `cog`, `heading`, `navStat`, `rot`, `posAcc`, `raim` — no class, flag or dimensions.

Measured over 40 min:

- **36.25 location messages/s**, 2,052–2,303 per minute, flat; no reconnect, no throttle.
- **656 distinct vessels**; the population saturates at **627 by 10 minutes** (312 by 10 s, 428 by
  1 min, 618 by 5 min) and then gains nothing for 30 min. REST meanwhile advertises 943.
- **Delay (our receive time − reported fix time)**: median **0.5 s**, p10 0.1, p90 0.9, p99 1.0, max
  4.6 s, 3 negative values in 87,000. Fix times are whole seconds, so the honest statement is
  "delivered within about a second; this feed cannot resolve delay below 1 s".
- **Duplicates**: 172 of 86,999 (0.20%) repeat an identical (MMSI, fix second).
- **Reporting interval**: median 10 s, p10 3, p90 12, p99 181 s. Per-vessel medians: 57 vessels
  < 10 s, 297 at 10–30 s, 21 at 30–120 s, **237 at 2–5 min** (the 3-minute anchored rate), 8 at
  5–15 min. Gap thresholds must be per vessel.
- **Geography**: 439 distinct 0.1° cells; 54.5% of positions in the Gulf of Finland box (21–30 °E,
  59.2–61 °N); 86% east of 20 °E; peaks at 24 °E (Helsinki–Tallinn), 21 °E and 28 °E (Ust-Luga/
  Primorsk approach). Excluding five corrupt vessels (see 5), coverage is **17.7–29.6 °E**, so
  St Petersburg itself (30.2 °E) is outside it.
- **Static data** (609 vessels): name 100%, call sign 100%, ship type 98%, ETA 98%, destination 92%,
  draught 89%, **IMO 69%**; REST `/vessels` does better on IMO (73% of 837). At connect the broker
  dumps **retained** static records for ~280 vessels, so identity is instant, but there is **no
  retained position snapshot** (9 messages in the first second).
- **Fleet mix** (folded types): cargo 164, pilot/SAR/service 162, passenger 100, **tanker 96**
  (9,448 messages), other 47, tug/dredge/sailing 21, unknown 14. Within 30 km of the Russian oil
  ports: **Ust-Luga 18 tankers / 58 vessels**, Primorsk 1 / 4, Vysotsk 1 / 15, St Petersburg 0 / 1.
- **Quality**: `posAcc` true 58.9%, `raim` true 11.3%, `sog` = 102.3 ("not available") 0.10% of fixes,
  `cog` = 360 (unavailable) 4.0%, no 91/181 invalid positions.

### 2. Digitraffic REST — snapshot, not archive

`GET https://meri.digitraffic.fi/api/ais/v1/locations` needs **both** `Digitraffic-User` and
`Accept-Encoding: gzip` (else `406 Use of gzip compression is required`); 35–38 kB gzipped, 77 ms
median latency, 941–942 features.

- **941–942 features in every one of 480 polls, 943 distinct MMSIs across the run, zero churn between
  consecutive polls**: a per-vessel cache. Position age at receipt: median 158 s, p10 43 s, **p90
  12.8 h, max 24.0 h**. 285 of the 943 never appeared in the live stream, so counting ships from this
  endpoint overcounts the live population by ~50%.
- `?from=`/`?to=` are **epoch milliseconds** (ISO strings → `400 ... required type 'java.lang.Long'`)
  and filter the last-known-position time: a 1-minute window 3 days ago → 0 features, a 1-hour window
  3 days ago → 4, 1–2 minutes ago → 102. **History impossible**; retention ≥ 13 months (399–400 days
  ago still returned 5).
- **Silence-index validation** (`rest_silence.py`): 10-minute windows ending 16:52, 16:42, 16:32 gave
  REST 19 / 18 / 21 vs our own 20 / 18 / 20. A window re-queried later shows fewer (105 vs 598)
  because a vessel's last position is overwritten once it transmits again: **the index lists only
  ships that are still silent** — the semantics a dark-ship screen wants — and it self-cleans.
- `?mmsi=`, `?latitude=&longitude=&radius=` (km) work. `cache-control: max-age=60` via CloudFront
  (`x-cache: Hit ... age: 37`), so **REST cannot be fresher than 60 s**. Eight rapid requests all 200;
  no 429.

### 3. Kystverket, BarentsWatch, AISStream

- **Kystverket TCP** `153.44.253.27:5631`: 6 s connect timeout; `:5632` accepts then closes with
  0 bytes (auth/whitelist); 5630/5633/5634/80 filter. Not usable from this network.
- **BarentsWatch AIS Live** (`live.ais.barentswatch.no`, spec `/openapi/ais/openapi.json`): `/v1/ais`,
  `/v1/latest/ais`, `/v1/sse/ais`, `/v1/openaisarea` all `401 Bearer`. Spec: "you need to register a
  user at barentswatch.no and create an AIS-API client at My Page." **Account required, untestable
  here.** If the team ever registers, `/v1/latest/ais` ("latest AIS messages per MMSI within 24 hours",
  lat/lon/radius) is the Norwegian analogue of Digitraffic REST.
- **AISStream**: free key via GitHub, so untested here. Orchestrator: one global connection = 26,133
  vessels, 85 msgs/s, ~3 s delay, **zero vessels in Hormuz, Persian Gulf or Gulf of Oman**; Baltic-only
  subscription gave the Gulf of Finland **0.56 msgs/s from 142 vessels** against Digitraffic's 36.25/s
  from 656 in the same water. Digitraffic is ~20× the rate and ~4.6× the vessels locally; AISStream's
  value is global reach, not depth.

### 4. Can silence be told apart from reception loss?

Method (`silence.py`): every internal silence ≥ 5 min with ≥ 2 min of observation either side; for
each, other vessels reporting in the same 0.1° cell and within 20 km during the gap, the cell's rate in
the prior 20 min, and the vessel's last speed and nav status.

- **213 internal silences ≥ 5 min** (median 6.0, max 36 min) from 656 vessels; **198 had last speed
  < 3 kn** (ordinary Class A anchoring), 15 under way. 182 were isolated (≥ 3 neighbours within 20 km
  still reporting), 31 had dead local reception. **Only 7 were isolated and under way; only 3 were
  isolated, under way and not anchored/moored** — that is the entire honest candidate set for "went
  quiet while others were heard" in 40 min of Gulf of Finland traffic.
- **Reception held, quantitatively**: across the 188 silences with a baseline, the cell's message rate
  during the gap was a median **1.33×** its pre-gap rate; **94% had ≥ 50% of baseline**, 4% below 20%.
- **Presence/absence fails**: only **9 of 439 cells were active in all nine 5-minute bins**, 181 in
  half or fewer — coverage is bursty at 0.1° because ships pass through. Compare rates, never "did
  this cell go quiet".
- **End-of-window silences are contaminated by range**: 49 of 634 vessels vanished from the last
  10 min; 11 were last seen west of 20 °E (Åland/Bothnian edge), 25 were anchored/moored, and the 8
  "under way, east of 20 °E, not anchored" had last fixes at 28.4–29.4 °E — the eastern edge by
  Primorsk/Ust-Luga. **Without a second feed or satellite AIS, none of those 8 can be called a
  switch-off.**
- Published yardstick for the real question (d-methods found the code): gap ≥ 12 h, both ends > 50 nm
  from shore, ≥ 19 satellite AIS positions in the prior 12 h, then a per-cell reception classifier
  (`github.com/GlobalFishingWatch/AIS-disabling-high-seas`). The per-cell half is cheap on one
  national feed; the offshore half needs satellite AIS.

### 5. Position corruption seen live (bonus and warning)

`anomalies.py` (implied speed > 50 kn between consecutive fixes ≥ 2 s apart): **351 events from 6
vessels**, two patterns. **Five unconnected vessels converged on one inland coordinate, 57.67 °N
32.53 °E, in Novgorod Oblast, Russia**: YANGTZE DORA (cargo) teleported 352 km there from the Primorsk
approach (60.06 N 28.49 E) at 17:04:05Z and kept reporting 34–102 kn, impossible for these hulls
(102.3 is AIS's "not available" code); CYCLONE and OBELISK (tankers, OBELISK's destination "PRIMORSK")
appear only at that point; TRUVOR and VYATICH (tugs) jitter there. That is what spoofed or jammed GNSS
looks like, though AIS alone cannot prove the mechanism — do not assert it without a second source
such as GPSJam for the same hours. Separately **RATNIK** (tug) made 188 > 50 kn jumps at its real
position (fix jitter), so a detector needs both tests: impossible jump and impossible cluster.

## Source rows

| Source | Type | Regions covered | Free access route | Account needed? | What one record contains | Update rate | Delay from event to us | Position or resolution accuracy | Identifies the ship? | Licence, commercial limits | Evidence |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Digitraffic AIS, MQTT | Live AIS, Class A only, national shore receivers | Finland, Gulf of Bothnia, N Baltic: 17.7–29.6 °E / 57.7–65.8 °N | `wss://meri.digitraffic.fi:443/mqtt` (paho `transport="websockets"` + `tls_set()`, path `/mqtt`, header `Digitraffic-User`) | No | MMSI (topic), epoch-second fix time, lat/lon, SOG, COG, heading, navStat, ROT, posAcc, RAIM; static data on `/metadata` | every report: 2–10 s under way, 3 min anchored | measured median 0.5 s, p90 0.9 s, max 4.6 s | ship-reported GNSS, typically < 10 m, not independently checked | MMSI always; name ~100%, IMO 69–73%, type ~98%, destination ~92%, draught ~89% | CC BY 4.0, commercial use with attribution | 40-min run, `$WAVE/data/t-ais-live/` |
| Digitraffic AIS, REST | Last-known-position snapshot | same | `https://meri.digitraffic.fi/api/ais/v1/locations` + `/vessels`, headers gzip + `Digitraffic-User` | No | one position per MMSI; `/vessels` static set (837) | continuous upstream, CDN cache 60 s | median 158 s age, p90 12.8 h, max 24 h | as above | MMSI; join `/vessels` for identity | CC BY 4.0 | 480 polls + silence-index validation |
| Kystverket AIS TCP | Live AIS, shore receivers | Norway coast | `153.44.253.27:5631` (documented as no registration) | Documented: none | AIS NMEA sentences | – | – | – | – | NLOD (per d-ais) | **failed**: 6 s timeout; `:5632` closes with 0 bytes |
| BarentsWatch AIS Live | Live AIS + 24 h per-MMSI latest | Norway | `https://live.ais.barentswatch.no/v1/{ais,latest/ais,sse/ais,openaisarea}` | **Yes**: user + OAuth client | Position/StaticData/AtoN/MetHyd JSON; optional 1/min per MMSI | continuous | untested | ship-reported | MMSI + static data | NLOD per spec | 401 Bearer on all four endpoints + spec text |
| AISStream | Live AIS, aggregated global | global; Middle East dead since ~16 Oct (issue #322) | `wss://stream.aisstream.io/v0/stream` | **Yes**, free key via GitHub | position + static per message | per report | ~3 s (orchestrator) | ship-reported | MMSI + name/IMO in static | vendor terms, no SLA | not tested here; orchestrator: 26,133 vessels global, 142 in Gulf of Finland |

## Consequence for feasibility

- **The Baltic live leg is real, cheap and measurable**: one WebSocket, no key, sub-second, CC BY 4.0,
  ~630 ships plus a reception map. "Live dots + silence + ranks" can be shown honestly.
- **No second live feed exists without an account**, so the plan's "two independent live feeds on the
  day" is one feed plus a recording of our own JSONL (plus Danish history). A risk-table correction,
  not a blocker.
- **Radar-vs-AIS matching at a past satellite time cannot use Digitraffic**: Danish DMA is the right
  AIS source for the Sentinel-1 scenes (t-match, t-ais-history). Digitraffic's roles are the live leg
  and a long-retention silence census.
- **Region verdict**: Baltic = enough for live monitoring and archive matching. Hormuz, Natuna and
  Malacca have no reachable live AIS here, so claims must rest on archives (PortWatch, NOAA) plus
  imagery. Norway/Skagerrak — the shadow-fleet lane past Bergen — is outside live coverage; the Russian Baltic ports are covered thinly
  (Ust-Luga 58 vessels in 40 min, Primorsk 4, St Petersburg 0).
- **Fishing is closed for Finland**: type-30 vessels are stripped, so an illegal-fishing demo needs
  GFW/Skylight-class data (token), not this feed.

## Unknowns

1. Whether Kystverket's TCP feed works from another network (venue wifi, phone hotspot) — one-line
   retry if Norway matters.
2. BarentsWatch latency and coverage — needs one free registration (name + OAuth client).
3. Whether the 0.20% duplicates are broker-side or client-side: a second subscriber would show it.
4. Digitraffic's true seaward footprint: our data shows where receivers hear, never where they do not;
   and whether ships going silent here are heard by Swedish or Estonian receivers (no no-account feed
   for either was found by any agent).
5. The mechanism behind the five-vessel inland cluster — needs independent GNSS interference data.

## Sources

- `https://meri.digitraffic.fi/swagger/openapi.json` — "latest vessel locations", `from`/`to` in epoch
  ms, mmsi/radius filters, metadata fields, `posType` = GNSS device type (1 GPS, 3 GPS+GLONASS,
  15 internal) — **not** AIS class.
- `https://www.digitraffic.fi/en/marine-traffic/ais/` — Class A only; all fishing vessels (type 30)
  filtered; ship types folded (80–89 → 80).
- `https://www.digitraffic.fi/en/terms-of-service/` — CC BY 4.0, commercial use with attribution.
- `https://live.ais.barentswatch.no/openapi/ais/openapi.json` — AIS Live API: registration required,
  `/v1/latest/ais` = latest per MMSI within 24 h, NLOD licence.
- `https://github.com/GlobalFishingWatch/AIS-disabling-high-seas` — published gap criteria (via
  d-methods).
