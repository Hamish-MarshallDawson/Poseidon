# t-feeds: every promising no-account feed, actually queried

*Track t-feeds, MarineTraffic wave, Sat 7 Nov 2026, 18:18–18:50 UTC. Everything below was run from the venue network with no accounts and no credentials. `measured` = I ran it here; `documented` = primary source; `vendor claim` = the operator's own words; `unverified` = a lead I could not settle. Scratch `$WAVE=/tmp/claude-1000/-home-aiden-Projects-Personal-Hedged-Bets-hacktheburgh/703a82eb-0773-4b07-b85c-af65197add0d/scratchpad/wave`; scripts `$WAVE/scripts/t-feeds/`, data `$WAVE/data/t-feeds/`.*

## Bottom line

1. **CetaHAV is real, key-free and the only second live feed we have — and it is the only key-free live feed that covers the Danish straits.** **1,011 distinct ships in 10.7 minutes** of polling (33 requests, 1,815 fixes), with 44% of fixes in the Kattegat/Danish straits and 12% in the Skagerrak — the water where `t-match` validated radar-to-AIS matching. Nothing in it is in the Gulf, Red Sea or Malacca.
2. **Its quirks decide how it may be used.** Each call takes ~12.6 s and returns only a 48–72 ship *rolling sample* (~62% of them stopped), with **no timestamp field**; no two consecutive polls share a ship, and **6.9% of positions it serves are more than an hour old** (max 17 h) with nothing in the payload to say so. Four or more parallel calls silently return HTTP 200 with an **empty** collection; one sequential poll in 33 was empty too. It is a sampler, not a snapshot, and an empty answer never means "no ships".
3. **Every supposedly global free map is gated or Baltic/EU-only.** aiscatcher.org (1,313 stations, 105,989 ships/24 h, `vendor claim`) blocks ordinary clients with Cloudflare and gates live data behind "Confirm you are human"; its documented API is per-station, not the network. AIS Trail needs a Bearer key; its 9-station volunteer map has median range 3–8 nm. EMODnet's CC BY density layer is EU-only in fact (Hormuz tile blank, measured).
4. **The Gulf finding stands unchanged and is now tested three ways:** CetaHAV `zone-stats` on a Hormuz box = 0 vessels; CetaHAV `/ais` bbox never leaves 9.0–26.2 °E / 54.1–65.5 °N; no other candidate in the shared notes was both key-free and reachable. `mt-gulf-feeds` reaches the same conclusion from the provider side.
5. **Two documented no-account routes still fail from this network** (Kystverket TCP timeout, BarentsWatch 401) and two "promising" ones are not data services (Swedish Sjöfartsverket: order by email with a 2027 price annex; HP Radar, Vietnam: access on request). The practical free live set remains Digitraffic + CetaHAV, both Baltic.

## Findings

### 1. CetaHAV (`cetahav.org`) — measured, works, one caveat per feature

Public base `/api/public/v1`, no key, CORS `*`, docs at `/api-docs`. `measured` over 33 sequential polls at 20 s intervals (18:19:17–18:29:57 UTC) plus a 12-minute paired run against Digitraffic.

| Property | Measured value |
|---|---|
| Endpoint | `GET https://cetahav.org/api/public/v1/ais` → GeoJSON `FeatureCollection` |
| Latency | median **12.65 s**, max 14.7 s, 33/33 HTTP 200; Cloudflare-fronted, `cache-control: max-age=30` but no `cf-cache-status` returned |
| Ships per call | min 0, median **55**, max 72; **1,815 fixes total** |
| Cumulative distinct MMSI | **1,011 in 10.7 min** (33 polls, 18:19:17–18:29:57 UTC) |
| Empty answers | 1 of 33 sequential polls returned `{"features":[]}` in 0.96 s, so emptiness is not only a concurrency artefact |
| Consecutive-poll overlap | 0–2 ships; positions identical when they do repeat → no per-MMSI cache, it is a live tail |
| Fields | `mmsi`, `name`, `sog`, `cog`, `heading` only. **No timestamp, no IMO, no type, no destination, no draught, no class** |
| Geography | 9.03–26.22 °E, 54.09–65.55 °N: Danish straits/Kattegat 44% of fixes, Baltic proper 29%, Gulf of Finland 13%, Skagerrak 12% |
| Distinct ships by region (10.7 min) | Danish straits/Kattegat **426**, Baltic proper 328, Gulf of Finland **140**, Skagerrak **118** |
| Composition | 62% `sog` = 0 (moored/anchored), 28.5% `sog` > 3 kn, 20.5% > 8 kn; 0.5% blank names |
| Concurrency behaviour | 3 parallel calls: all fine, ~50 ships each, 12.5 s. **6 parallel: 4 of 6 returned `{"type":"FeatureCollection","features":[]}` in 1.2–2.8 s, and two of the non-empty bodies were byte-identical** — silent degradation, never an error |
| Documented fair use | 60 req/min per caller, 10/min for `zone-stats`, 429 with `Retry-After`; zone max 750,000 km², ≤200 vertices, ≤10 years history (`documented`, `/api-docs`) |
| Licence position | "re-serves data from public providers without altering their terms… keep the attribution of each upstream provider" (`documented`) |

- **Upstream is AISStream, so its coverage ceiling is AISStream's.** `mt-rivals` found the map labels AIS as "Live AIS (AISStream)", which matches every measurement here (Baltic + Danish straits only, no Gulf). The `/sources` list (20 entries, 5,651 B JSON) names **no AIS provider at all** — a licensing gap worth flagging if anyone republishes it.
- **`zone-stats` is the useful extra.** `POST /api/public/v1/zone-stats` with `{"ring":[…],"years":N}` returns a live vessel count, SMHI station freshness, protected-area overlap and — with `years>0` — yearly **sighting counts**. Measured: Kattegat box (10–14 °E, 54–57 °N, 84,029 km²) = **15 vessels live**, 14 SMHI stations, 4.7% wind-farm overlap, history `{2024: 3,219,232 sightings, 2025: 0, 2026: 0}`. The same call on a Hormuz box (56–57 °E, 26–27 °N) = **0 vessels, 0 stations**. So "history" exists only for 2024 — likely an archived 2024 AIS extract, `unverified`; the zeros for 2025–26 are not traffic data.

### 2. Age of a CetaHAV fix — inferred, because the payload has no clock

Method (`pair_poll.py`): poll CetaHAV every 60 s and Digitraffic `locations` every 20 s, then snap each CetaHAV position onto the Digitraffic track of the same MMSI. Positions are the *same broadcast message*, so a correct match is metre-exact (median match distance **0.002 nm ≈ 4 m**), which makes the matched Digitraffic fix time a true broadcast time.

- **58 matched positions** (12 min of paired polling, 24 Digitraffic polls at 20 s). Ships under way (`sog` > 3 kn, n = 19): **median −17 s, p90 40 s** — i.e. CetaHAV's position is as new as Digitraffic's CDN-cached snapshot (60 s cache) to within ±40 s. Stopped ships (`sog` ≤ 3 kn, n = 39): **median 107 s, p90 3,405 s**.
- Overall **12.1% of served positions are older than 10 minutes and 6.9% older than an hour** (max 62,112 s ≈ 17.2 h). Those are not transport delay: they are last-known fixes for ships that have not transmitted since, served without any age field. So the trap is not that the feed is slow, it is that **an old fix and a fresh fix are indistinguishable** — in the paired sample 7 of 58 matched positions were over 10 minutes old and 4 over an hour, and nothing in the payload would have told us.
- **CetaHAV is not a sub-minute feed and cannot be shown as one**; anything under way is roughly a minute old, anything alongside may be any age.
- This agrees with AISStream's own ~45 s–3 min (orchestrator/Hamish figures) and with Digitraffic's sub-second, which is 20–100× fresher on the same water.

### 3. Digitraffic, re-confirmed as the yardstick (`measured`)

`GET https://meri.digitraffic.fi/api/ais/v1/locations` with `Digitraffic-User` + gzip → 200, 38,427 B, **939 features in 0.16–0.21 s**, every feature carrying `timestampExternal` (epoch ms) plus `navStat`, `rot`, `posAcc`, `raim`. 26 consecutive polls returned the same 939 MMSIs, zero churn. Same water, same minutes: **939 ships vs CetaHAV's 48–72 per poll and 140 distinct Gulf-of-Finland ships in 10.7 min** — in Finland Digitraffic is ~17× deeper per poll and ~6.7× cumulatively, while in Denmark CetaHAV is the only live option we have. Digitraffic's 60 s CDN cache is also why some CetaHAV positions match *newer* than the newest Digitraffic fix.

### 4. aiscatcher.org — a good story, not an accessible feed

- Figures from its own coverage page (`vendor claim`, read 18:22 UTC): **1,313 stations online**, 981 public, **105,989 unique ships per 24 h**, **276.3 M messages per 24 h**, 3,485 ports.
- Access: `curl` gets a Cloudflare **"Sorry, you have been blocked"** page even for `robots.txt`, and the site's own banner is **"Confirm you're human to load live AIS data"**. Live map therefore behind a human check, non-browser clients blocked — boundaries I did not work around; no data taken.
- The documented developer surface (`/developers`, `docs.aiscatcher.org`) is **per-station**: your own AIS-catcher receiver exposes `/api/v1/vessels`, and from another machine you mint a key on your own device. No network-wide API exists. Useful only if we host a receiver (`mt-receivers`: weeks to months).

### 5. AIS Trail (`aistrail.com`) — key-gated, tiny network

`api.aistrail.com` requires `Authorization: Bearer ap_live_…` (`documented`). Its public volunteer-station file (`measured` 18:20:03 UTC): **9 stations**, C-square footprints, `range_nm` median 3–8 nm, one offline 7.5 h, one with 4 ships today, nothing in the Gulf. As a calibration of what one home receiver sees, it explains *why* receivers will not close the Gulf gap.

### 6. EMODnet density — free, but EU-only in practice

`ows.emodnet-humanactivities.eu/wms` is key-free (1.05 MB capabilities, 207 layers, `vesseldensity_00…05` by ship type plus `routedensity_*`). Abstract (`documented`): built since 2019 by Cogea from **AIS purchased from CLS, ORBCOMM and vesseltracker.com**, 1×1 km cells, "covering all EU waters and some neighbouring areas", hours per km² per month. Measured `GetMap`: Gulf of Finland tile 24,909 B with a full gradient, **Hormuz tile 1,671 B, 3 distinct byte values (blank)**; `GetFeatureInfo` there → "no features were found". Confirms `mt-gulf-feeds`. CC BY 4.0, so usable as a *prior* for European water, not the Gulf.

### 7. Routes that failed, with the exact error

| Route | Result (measured) |
|---|---|
| Kystverket TCP `153.44.253.27:5631` | `TimeoutError` after 8 s (retry; same as `t-ais-live`); `:5632` connects in 0.1 s then returns 0 bytes |
| BarentsWatch AIS Live | 401 `Bearer` on every endpoint (`t-ais-live`, unchanged) |
| Swedish Sjöfartsverket AIS | page 200: real-time stream from ~40 base stations and RAIS history back to 2006-09-28, but **ordered by email to `sma@sjofartsverket.se` with a 2027 price annex**; RAIS extracts billed by handler time. Not testable without a purchase (`documented`) |
| aiscatcher.org | Cloudflare block / human check (above) |
| AIS Trail | key required |
| HP Radar (Vietnam), Thai MD layer, KKP Indonesia | request-only / not real data / OAuth (`mt-gulf-feeds`; not re-tested) |

## Source rows

| Source | Operator | Type | Regions covered | Access route | Account or cost | What one record contains | Update rate | Delay | Identifies the ship? | Licence, limits | Likely used by MarineTraffic? | Usable by us? | Evidence |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| CetaHAV public API `/ais` | Cetasol/Quokka/SEI/Lst Gotland pilot | aggregated live AIS (AISStream upstream) | Baltic + Danish straits + Skagerrak, 9.0–26.2 °E / 54.1–65.5 °N | HTTP GET, no key | none | mmsi, name, sog, cog, heading | rolling sample; ~55 ships per 12.65 s call | under way ≈0–40 s; 6.9% of served fixes >1 h old, no age field | MMSI + name only | re-serves upstream terms; 60 req/min; **empty 200 under ≥4 parallel calls, occasionally sequential** | no (it consumes AISStream) | **yes** as cumulative sampler, Denmark especially | measured, 33 polls + paired run, `$WAVE/data/t-feeds/` |
| CetaHAV `/zone-stats` | same | live count + yearly sightings per polygon | same | HTTP POST JSON ring | none | vessel count, density, SMHI stations, overlap %, yearly sightings | on request | live count current | no | 10 req/min, 750,000 km² cap | no | yes for counts, not positions | measured (Kattegat 15 vessels; Hormuz 0) |
| Digitraffic AIS REST | Fintraffic | national shore AIS | Finland + N Baltic | REST + MQTT, header only | none | position + navStat/rot/posAcc/raim + timestamps | continuous, CDN 60 s | 0.16 s response, 0.5 s MQTT | yes | CC BY 4.0 | no | **yes**, primary | measured (939 features) |
| aiscatcher.org network | volunteer community (open-source AIS-catcher) | volunteer shore AIS | 1,313 stations, 981 public (claim) | web map behind human check; per-station API | none for data; needs own station for API | per-station vessels, tracks, port calls (own station) | live | vendor claims "no delay" | yes (per station) | no central API/terms found | no | **no** | measured: CF block + human check |
| AIS Trail | commercial | aggregated AIS API | 9 volunteer stations + national feeds | `api.aistrail.com`, Bearer key | key; free tier per plan | vessels, tracks, port calls | live + history | unknown | yes | plan terms | no | not without a key | measured 401-style requirement, stations.json |
| EMODnet Vessel Density | EMODnet HA (Cogea) | aggregated AIS raster | EU waters + neighbours, 1 km cells | WMS, no key | none | hours/km² per month, per ship type | annual | ~1 year | no | CC BY 4.0 | no (it buys CLS/ORBCOMM/vesseltracker) | yes in Europe only | measured (Hormuz blank) |
| Swedish AIS (Sjöfartsverket) | Swedish Maritime Administration | national shore AIS + RAIS archive | Swedish waters, ~40 base stations | email order; streaming + historical extract | paid, 2027 price annex | full AIS attributes, CSV/Shape/PDF | live stream; archive since 2006 | real time | yes | commercial terms | unknown | only via purchase | documented (page 200) |
| Kystverket AIS TCP | Norwegian Coastal Administration | national shore AIS | Norway | `153.44.253.27:5631` | none (documented) | raw NMEA | live | – | yes | NLOD | no | **no** from here: timeout | measured retry |
| HP Radar (Vietnam) | private | 8 ground stations | Hai Phong area only | API on request | free tier 100 req/h after email approval | vessels | live | – | yes | request-only | no | no (approval needed, and not our region) | `mt-gulf-feeds` |

## What this means for us

- **A second live feed exists after all, and it is the right one for our validation region.** `t-ais-live` planned "one feed plus our own recording"; CetaHAV adds Danish-straits positions key-free, cumulatively. For a Hormuz claim it adds **nothing** — 0 vessels, tested twice.
- **Never treat a CetaHAV response as a fleet snapshot.** It is a ~12.6 s live tail: 48–72 ships, no repeats, 62% stationary, no clock, and 7% of served positions already hours old. So store **our** receive time labelled "received at", never "position at"; dedupe on (MMSI, lat, lon) because identical bodies repeat; require ≥3 consecutive non-empty polls before drawing a region; and treat an empty 200 as "back off 60 s", since a single empty response would otherwise read as "the whole sea went dark".
- **Claim freshness per feed, not globally.** Digitraffic can carry "delivered within a second"; CetaHAV can only carry "about a minute, and the ship may simply have been alongside". One merged "last seen" column would re-introduce the reporting-interval confound `t-ais-live` already fought.
- **Borrow the shape, not the data.** CetaHAV's `zone-stats` is a cheap pattern worth copying: one polygon in; vessel count, freshness class, protected-area overlap and yearly history out. Do not build on aiscatcher.org or any human-checked map, and nothing here changes the region verdict — free live AIS reachable from the venue is Baltic plus the Danish straits; everything else is derived-and-delayed or paid.

## Unknowns

- Whether CetaHAV's 2024-only `zone-stats` history is an archived AIS extract worth using, and under what licence — a question for its operators.
- CetaHAV's exact upstream: AISStream is stated on their map and matches every measurement, but `/sources` omits AIS, so the attribution chain is broken. Anyone republishing needs that resolved.
- Whether the empty/duplicated bodies at ≥4 concurrency are a rate limit, an upstream connection-pool limit or a Cloudflare cache artefact — one polite test from a second IP separates them.
- Whether any Gulf state publishes AIS for research behind a free registration (e.g. Oman, Qatar). `mt-gulf-feeds` found none; a registration would test it, which is a team decision, not this track's.

## Sources

- `https://cetahav.org/api-docs`, `/api/public/v1/`, `/sources` (20 sources, no AIS), `/health` (`degraded`; `open-meteo-marine` 429) — endpoints, limits, attribution text, fair use (read 18:18 UTC).
- `https://cetahav.org/api/public/v1/ais` — 33 polls 18:19:17–18:29:57 UTC plus 8 polls inside a 12-min paired Digitraffic run (raw JSONL in `$WAVE/data/t-feeds/`); `/zone-stats` Kattegat and Hormuz boxes, `years` 0 and 3.
- `https://meri.digitraffic.fi/api/ais/v1/locations` — 939 features, `timestampExternal`, 0.16–0.21 s, 26 identical polls.
- `https://www.aiscatcher.org/` (`/stats`, `/developers`), `https://docs.aiscatcher.org` — station/server counts, human-check banner, per-station API model, Cloudflare block for non-browser clients.
- `https://map.aistrail.com/live/stations.json` — 9 stations, ranges, uptime; `https://aistrail.com/docs/` — Bearer-key requirement.
- `https://ows.emodnet-humanactivities.eu/wms?...GetCapabilities / GetMap / GetFeatureInfo` — layer list, CLS/ORBCOMM/vesseltracker provenance, EU-only extent measured.
- `https://www.sjofartsverket.se/sv/tjanster/sjokortsprodukter/digital-data/ais-data/` — 40+ base stations, RAIS since 2006-09-28, order by email, 2027 price annex (page updated 2026-10-13).
