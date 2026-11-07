# 01 Live feeds and AIS behaviour (checked Sat 7 Nov 2026, ~16:00)

## 1. Verdict: AMBER

AISStream is the weak link. It is up for most people right now (users measured about 4,300 vessels per hour in the North Sea plus Baltic on 31 Oct), but it has no SLA, had a multi-day silent outage in August, has open reports of 429s and instant disconnects, and delivers positions 45 s to 2 min late (since March). Its cert expires on 17 Nov, which is after the hackathon. Digitraffic (Finland) is a solid no-key fallback and covers the Gulf of Finland well: I measured 482 vessels there, 391 reporting in the last 10 minutes, with a ~7 messages per second lower bound. It needs only a `gzip` header, plus a `Digitraffic-User` header to be safe. Kystverket is Norway only (so useless for the Baltic) and its TCP port did not even connect from this network. Plan: build the ingest behind one interface, run Digitraffic as primary or equal partner, AISStream as secondary, and record a replay file early.

## 2. Claims table

| # | Claim | Status | Evidence | Note |
|---|---|---|---|---|
| 1.1 | AISStream free, GitHub sign-up, endpoint, subscribe within 3 s | partly | https://aisstream.io/documentation | Endpoint and 3 s rule confirmed (connection closes if no valid subscription in 3 s). Docs say keys come from the Account page; the sign-up method is not on the page. Sign-up via GitHub is consistent with issue #337 (GitHub OAuth login). Also: no SLA or uptime guarantee stated. |
| 1.2 | 3 connections per account and per IP (IP counted before auth); no browser connections | confirmed | https://aisstream.io/documentation ; https://github.com/aisstream/issues/issues/287 | "4+ get a 429" (comment on #287). Backend relay needed. Ghost connections can keep slots held for days (#292). |
| 1.3 | Subscription updates 1/s; slow readers dropped; no replay | confirmed | https://aisstream.io/documentation | Faster updates close the connection. Each update replaces the old subscription. |
| 1.4 | Uncompressed connections bandwidth-limited from Sept 2026; use permessage-deflate | partly | https://aisstream.io/documentation | Docs word it as "Beginning in September 2026 ... will be subject to per-user bandwidth limits" and say to check `CompressionEnabled` in the confirmation. Enable compression. |
| 1.5 | Silent stream from 5 Aug; expired cert 11 Aug; sign-up timeouts; 429 for days (#287); GCP IPs closed ~700 ms (#285) | confirmed, with detail | https://github.com/aisstream/issues/issues/257 (silent from 2026-08-05 13:31 UTC), /269, /270 and /265 (cert expired, 7 and 11 Aug), /266 (sign-up error 524), /287, /285 | Cert expired again on 19 Jul for 50+ h (per #341). #285 and #287 have no maintainer reply; #285 author gave up and switched provider. Several of the August issues were later closed, but #269, #270, #262 are still open. |
| 1.6 | No satellite AIS mentioned | confirmed | https://aisstream.io/documentation | No mention of satellite on the docs page. Issue #288 confirms terrestrial receivers. |
| 1.7 | Digitraffic MQTT-over-WebSocket, topics, CC BY 4.0, no key | partly | https://www.digitraffic.fi/en/marine-traffic/ | `wss://meri.digitraffic.fi:443/mqtt`, SSL required, no key mentioned. The page itself is inconsistent: topics are `vessels-v2/<mmsi>/locations` in text but `location` in examples. Brief says `location`; test both. Licence is not stated on that page (CC BY 4.0 is widely stated for Digitraffic, not verified here). I did not test MQTT live (no paho or websockets installed). |
| 1.8 | Digitraffic throttles clients lacking `Digitraffic-User` (429) | confirmed | https://www.digitraffic.fi/en/news/2024/12/03/api-throttles-turned-on-en.html | Throttle began 3 Dec 2024; 429 when limits exceeded; no numbers published. My 11 REST calls (10 with the header, 1 without) all returned 200, so a light client is not hit. |
| 1.9 | Finland tracks well over 18,000 vessels at once | wrong | live test below | The current-locations endpoint returned 947 vessels (about 38 KB gzipped), all within lat 57.6 to 65.8, lon 16.6 to 32.5. Finnish waters, not 18,000. The Apify figure is likely a cumulative or mis-stated count. No primary source found. |
| 1.10 | Kystverket raw NMEA over TCP at 153.44.253.27:5631, no registration | partly | https://www.kystverket.no/en/sea-transport-and-ports/ais/access-to-ais-data/ | Address, port and "no registration" confirmed on the page. But it only covers Norway's economic zone plus Svalbard and Jan Mayen protection zones, and excludes fishing vessels under 15 m and recreational craft under 45 m. Licence NLOD. Live connection timed out (see below). |
| 2.1 | Class A 2 to 10 s underway, 3 min at anchor; Class B 30 s or 3 min | confirmed | ITU-R M.1371 reporting table (via search; NAVCEN returned 403 to my fetch, so NAVCEN not read directly) | Class A: 10 s at 0 to 14 kn, 6 s at 14 to 23 kn, 2 s above 23 kn (3.33 s when turning); 3 min at anchor or moored at 3 kn or less. Class B CS: 30 s above 2 kn, 3 min at 2 kn or less. |
| 2.2 | Static data every 6 min; Class B never sends IMO | partly | ITU-R M.1371 (search results, e.g. help.kpler.com/en/articles/9552860) | Class A message 5 every 6 min: confirmed. Class B sends message 24A/B (name, callsign, dimensions) every 6 min and has no IMO field; I am confident of that from the standard but did not read the exact clause. |
| 2.3 | AISStream `Timestamp` is only seconds-in-minute | confirmed | https://aisstream.io/documentation ("AIS UTC-second timestamp") | But `MetaData.time_utc` carries a full time (see open question 2). |
| 2.4 | First three digits of MMSI (MID) identify the flag | confirmed (standard knowledge) | ITU page https://www.itu.int/en/ITU-R/terrestrial/fmd/Pages/mid.aspx did not render in my fetch | Caveat: the MID is the flag of registration of the AIS unit's MMSI allocation. Reflagged ships keep a stale MMSI until reassigned, and fraudulent MMSIs exist. Also, MMSI prefixes differ for base stations (00MID) and SAR craft (111MID). |
| 2.5 | AIS required on 300 GT+ on international voyages | confirmed from knowledge, not re-fetched | SOLAS Ch. V Reg. 19 (not opened) | Reg. 19 also covers cargo ships of 500 GT+ not on international voyages and all passenger ships. Unverified by me. |
| 2.6 | Shore AIS fades in open ocean | confirmed from knowledge, not re-fetched | https://public.axsmarine.com/blog/ais-for-shipping (not opened) | Terrestrial range is typically ~40 nm (rule of thumb). Irrelevant to the Gulf of Finland, which is well covered by coast stations. |

## 3. Live test results

Test files are in `C:\Users\hamis\AppData\Local\Temp\claude\360f743e01c99fde\0f422719-c131-4ee1-a816-e4eaa9a35dc3\scratchpad\dvm-downloads\live-feeds\`.

### Kystverket (153.44.253.27:5631)

- Method: Python `socket.create_connection`, 10 s timeout, run twice (~3 min apart). Then a connect test on ports 5631, 80, 443.
- Result: `TimeoutError` every time, on all three ports. So the host is not reachable from this network (probably blocked or filtered here, or the host is down). I cannot give sentences per second or distinct MMSIs.
- Coverage: from Kystverket's own page it is Norwegian economic zone plus Svalbard/Jan Mayen only. It will not show the Gulf of Finland. Do not use it for this demo.

### Digitraffic (REST, not MQTT)

- Method: `curl --compressed -H "Accept-Encoding: gzip" -H "Digitraffic-User: HackTheBurgh-test" https://meri.digitraffic.fi/api/ais/v1/locations`, 10 polls 5 s apart, then one call without the user header. paho-mqtt and websockets are not installed, so MQTT was not attempted.
- Without `Accept-Encoding: gzip` the API returns `406 Not Acceptable` ("Use of gzip compression is required"). **Always send the gzip header.**
- With gzip, the call without `Digitraffic-User` also returned 200. Not throttled at this rate. Still send the header.
- Latency 0.2 to 2.4 s per call. Response ~38.7 KB gzipped.
- 947 vessels per poll. Bounding box of the data: lat 57.64 to 65.80, lon 16.56 to 32.53.

| Area | Vessels with a position | Reported in last 10 min |
|---|---|---|
| Gulf of Finland box (lat 59 to 60.6, lon 22 to 30.5) | 482 | 391 |
| Whole feed (Baltic box lat 53 to 66, lon 9 to 31) | 944 | 665 |
| Bothnia (lat 60.6 to 66, lon 17 to 26) | 160 | 133 |

- Update rate: between poll 1 and poll 10 (~62 s apart), 425 vessels had a newer position. That is about 6.9 vessel updates per second, a lower bound, because the REST endpoint keeps only the latest position per vessel. MQTT streams every message, so the real message rate is higher. No new MMSIs appeared in the minute.
- Median position age at poll time was 2.7 to 3.7 min (many vessels at anchor or moored report every 3 min).
- Fields per vessel: mmsi, lon/lat, sog, cog, heading, navStat, rot, posAcc, raim, `timestamp` (second of minute) and `timestampExternal` (epoch ms, a full time). So Digitraffic gives a full timestamp.

### AISStream

Not tested live (needs a key). State from the docs and the tracker below.

## 4. Answers to the open questions

**Q1: AISStream Baltic message rate, and does it stream Baltic now?** Yes, as of the last two weeks, per independent users on https://github.com/aisstream/issues/issues/322 :
- 31 Oct 08:05 UTC: 4,331 distinct vessels in a "North Sea + Baltic" box with a position in the last 60 min. World: 26,793.
- 26 Oct, 25 s test, one whole-world box: 1,313 positions, of which 257 in "North Sea and Baltic". That is about 10 per second for that combined region (Baltic alone not split out).
- Another user on #317 got ~54 msg/s worldwide (13,080 in 240 s), which hints that a world box may be sampled or capped; smaller boxes looked low too. Guess: expect a few per second for a Baltic-only box.
- Middle East (Hormuz, Persian Gulf, Red Sea, Suez) shows zero positions since ~16 Oct (#322, still open, no maintainer reply). **The Hormuz extension cannot work on AISStream.**
- Not verified by me: I did no key-based test. A one-minute count of your own Baltic box is the only real answer.

**Q2: Does `MetaData` carry a full UTC time?** Yes. `MetaData.time_utc` exists, in a Go-style string such as `2024-02-17 13:34:56.207576423 +0000 UTC` (nanosecond digits, not ISO 8601). Source: https://github.com/aisstream/issues/issues/74 and /176. The docs page example does not list it (its sample MetaData has only MMSI, ShipName, Latitude, Longitude), so the docs page understates the payload. Parse it with a custom format, or trim to microseconds. Important catch from #176 (open, no reply): since March 2026 `time_utc` lags the actual WebSocket delivery by 45 s to 2 min (it is the receipt time at AISStream's side, not the ship's transmit time, per the reporter). For gap detection, use `time_utc` consistently and do not compare it to your own clock to a few seconds. Also, message-level `Timestamp` stays seconds-only.

## 5. Risks and fixes for the ~17 h left (ranked)

1. **AISStream outage or silent stream during the demo.** Fix: write every message to a local JSONL file from hour 1; make the demo run from replay by default and live as a bonus. Add a "no messages for 30 s, reconnect with backoff capped at 30 min" loop (the 429 victims in #256 and #287 were caught by their own retry storms).
2. **429 or IP block on the venue wifi or a cloud host.** 3 connections per IP is shared by everyone behind the same venue NAT, and cloud IPs (GCP #285, Render #315, #328, #333) are reported blocked or throttled. Fix: run the relay on a team laptop (home or venue IP), not on Render or GCP; one connection only.
3. **Late `time_utc` in AISStream and missing receivers.** Fix: do detection on message arrival order and `time_utc` together, and never assume freshness below ~2 min. Digitraffic's `timestampExternal` has a clean timestamp.
4. **Digitraffic REST needs gzip and gives only the latest position.** Fix: poll `/api/ais/v1/locations` every 10 to 30 s (send gzip and `Digitraffic-User: HackTheBurgh`) and build your own track history, or use MQTT from Node (`mqtt` package, `wss://meri.digitraffic.fi:443/mqtt`, topic `vessels-v2/+/location`). I did not test MQTT; test it first thing.
5. **Wrong cert-expiry panic.** AISStream's cert expires 17 Nov 14:04 UTC (#341), after the event. Low risk, but it already lapsed on 19 Jul and 7 to 11 Aug.
6. **Hormuz extension.** Dead on AISStream until the Middle East receivers return. Drop from the live demo; use pre-recorded data only.

## 6. Anything missed

- **Digitraffic is the better demo feed for the Gulf of Finland.** 482 vessels there, no key, no per-IP cap documented, and a proper timestamp. Limits: covers only roughly lat 57.6 to 65.8, lon 16.6 to 32.5 (Finnish plus part of Estonian and Swedish waters), so Russian ports (Primorsk, Ust-Luga) and the eastern Gulf are likely at or beyond the edge of coverage; check by plotting. Static data (IMO, name, type) is on `vessels-v2/<mmsi>/metadata` or the REST `/api/ais/v1/vessels` (not tested).
- **Shadow-fleet tankers tend to sit in the eastern Gulf and near Russian waters** (brief claim 3.2), which is the weakest area for Finland's coverage. The "went dark" signal there may partly be a coverage edge, not a real gap. Worth a map layer showing reception.
- **Alternative to AISStream:** several users moved to other providers (Pelyr stream at dashboard.pelyr.com, openwaters.io relay mentioned on #269). Not evaluated: unknown licences and reliability, and the second looks like promotion. Treat as unverified.
- **Other Baltic coast feeds** (Denmark DMA live? Estonia, Sweden) not checked; DMA historical CSVs are another agent's area.
- AISStream's own tracker is full of licence questions (#290, #299, #334, etc.) with no maintainer replies. It has no stated commercial licence, so don't present it as a commercial product.

What I skipped: live MQTT test (no libs), Kystverket stream (unreachable here), all AISStream live tests (no key), NAVCEN and ITU primary pages (403 or empty fetch), SOLAS and AXSMarine pages. Risk: the 6.9/s figure is a floor, not the true MQTT rate.
