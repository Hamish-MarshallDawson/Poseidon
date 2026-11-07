# mt-sources: where MarineTraffic's data comes from

*Track mt-sources, MarineTraffic wave, Sat 7 Nov 2026, 18:17–19:00 UTC. Public material only: help pages, product pages, press releases, archived pages, SEC/CMA documents, trade press. No MarineTraffic account, no map or endpoint inspection, no automation against their site. Labels: `documented` = the operator's own page read directly here; `vendor claim` = the operator's own figure, not independently checked; `press` = reporting by others; `unverified` = a lead I could not confirm. Secondary encyclopaedic sources are marked `secondary`.*

## Bottom line

1. **The base is a volunteer/partner shore network, not government data.** Kpler's MarineTraffic product page (read 7 Nov 2026) claims 6,600+ AIS receivers, 400k+ vessels tracked daily and 1 billion+ AIS signals a day; MarineTraffic's help centre says stations are "managed and maintained by our dedicated partners". Satellite is bought in, or since 2025 owned. `vendor claim` / `documented`.
2. **Three source labels, defined by MarineTraffic itself:** **Terrestrial** = land-based receiver; **Satellite** = space-based receiver; **Roaming** = "the position was received via a shared network of AIS receivers". Roaming is therefore *reciprocal access to other operators' terrestrial networks*, not satellite and not their own stations. `documented`.
3. **Satellite AIS changed hands twice in eighteen months.** ORBCOMM supplied MarineTraffic from 2013 under a contract extended to end-2023. Kpler then bought **Spire Maritime** (agreed 13 Nov 2024, closed 25 Apr 2025, $233.5M). Kpler launched "Kpler AIS" on 19 Sep 2025 as Terrestrial + Roaming + Satellite on "over 13,000 receivers", replacing MarineTraffic AIS. Meanwhile ORBCOMM's AIS business went to S&P Global (agreed 24 Apr 2025, completed 10 Nov 2025). `documented`/`press`.
4. **What we see publicly is downsampled.** Kpler publishes at most one terrestrial position per MMSI per 5-minute window by default (full T-AIS on request); their own 2021 example is 80M messages/day downsampled against 300M+ full. Satellite messages are not downsampled but arrive in bursts. `documented`.
5. **No published split between volunteers, company stations, partners, governments and satellites.** The only quantitative statements are totals and growth points. Anything finer is `unverified`.

## Findings

### A. What the four possible origins actually are

- **Volunteers / station hosts.** Help pages invite anyone to host a station ("practically, anyone can set-up and operate a receiving station"), offer a free MarineTraffic-optimised receiver on application, and describe stations as run by "our dedicated partners", each with a public page, ID, operator and coverage statistics. `documented` (support articles 9552994, 9552984, 9552934).
- **MarineTraffic/Kpler's own stations.** Nothing public separates company-owned from host-owned stations; the wording is always collective ("MarineTraffic AIS network"). `unverified` split.
- **Roaming (other networks).** Their definition: "the position was received via a shared network of AIS receivers"; the 2025 launch note adds that Roaming fills "gaps in high-traffic but challenging coastal zones where collisions or signal obstructions can degrade reliability". Same idea as other aggregators' roaming AIS (MariTrace advertises "public AIS, Roaming AIS, and proprietary feeds"). No partner names published. `documented` definition, `unverified` partners. Related, and documented: an active AIS partner can ask for a raw NMEA stream "from certain areas or vessels of your choice" in exchange for feeding a roughly equal volume (support article 9552990, found by mt-receivers) — so barter, not just volunteers, is part of how they acquire coverage.
- **Satellites.** ORBCOMM 2013 → end-2023 (`documented`), then Spire Maritime from 2025 (`documented`). The Jan 2024 – Apr 2025 supplier is not public. `unverified`.
- **Governments.** I found **no evidence that MarineTraffic ingests government AIS or VTS feeds**, and no claim that it does. The documented government relationship runs the other way: in January 2016 it began supplying positioning data to **Equasis** and joined its board. `press` (FreightWaves).

### B. "AIS roaming" — what it means and why it matters to us

Roaming is a **commercial reciprocity layer over terrestrial coverage**, so it could explain dense coastal coverage in places with no open feed (Red Sea approaches, Gulf ports) without implying satellite. The source is visible per position: help article 14594297 says the vessel page shows **"Data received from: Terrestrial / Satellite / Roaming"**, and MarineTraffic pages found in search results show "(AIS Source: Roaming)". Satellite positions need a paid plan. `documented`.

### C. Dated timeline with confidence

| Date | Event | Confidence / source |
|---|---|---|
| 2007 | Started as an academic project at the University of the Aegean (Ermoupoli); Prof. Dimitris Lekkas publishes a trial version late 2007 | `secondary` (Wikipedia; eKathimerini 2020; Monocle 2018) |
| 2009 | ORBCOMM launches commercial satellite-AIS service | `secondary` (Wikipedia, ORBCOMM) |
| 2012 | Demitris Memos becomes CEO; first paid subscriptions | `secondary` (eKathimerini, Endeavor podcast) |
| 2013 | MarineTraffic–ORBCOMM satellite partnership begins | `documented` (ORBCOMM, 15 Oct 2020) |
| May 2015 | "over 2,000 AIS stations in more than 165 countries", ~20M positions/day | `press` (All About Shipping, 27–28 May 2015) |
| Jan 2016 | Supplies position data to Equasis; joins Equasis board | `press` (FreightWaves) |
| Oct 2020 | ORBCOMM contract extended to end-2023 | `documented` (ORBCOMM release; Maritime Journal, Port Technology, Marinelink) |
| Dec 2020 | ">4,500 active" terrestrial stations, largest terrestrial network | `vendor claim` (MarineTraffic LinkedIn post, 29 Dec 2020) |
| 2021 | Spire Global acquires exactEarth (satellite AIS) | `secondary` (Wikipedia) |
| Jun 2022 | AIS Toolbox released as open source | `secondary` (Wikipedia; archived MarineTraffic blog) |
| 2022 | MarineTraffic acquires FleetMon (Rostock) | `documented` (Kpler release: "earlier acquisition of FleetMon by MarineTraffic"; DLA Piper) |
| 15 Feb 2023 (closed 7 / 13 Mar 2023) | Kpler acquires MarineTraffic then FleetMon, "coordinated double acquisition" | `documented` (Kpler release, updated 14 Mar 2023; Reuters 15 Feb 2023) |
| Aug 2023 | Networks merged as the "MarineTraffic AIS network": "more than 6,250 community-based stations globally" | `press` (Splash247, 29 Aug 2023, quoting Kpler's AIS director) |
| 13 Nov 2024 (closed 25 Apr 2025) | Kpler buys Spire Maritime: $233.5M + $7.5M services; excludes Spire's satellite network/operations | `documented` (Kpler releases; Spire 8-K; Via Satellite 28 Apr 2025; CMA ME/2238/25 decision, 25 Jul 2025) |
| 24 Apr 2025 (completed 10 Nov 2025) | S&P Global buys ORBCOMM's AIS business | `documented` (ORBCOMM newsroom; S&P Global release) |
| 19 Sep 2025 | "Kpler AIS" launches: Terrestrial + Roaming + Satellite, "over 13,000 receivers", replacing MarineTraffic AIS | `documented` (MarineTraffic support article, updated 10 Oct 2025) |
| Read 7 Nov 2026 | MarineTraffic product page still claims 6,600+ receivers, 400k+ vessels/day, 1bn+ signals/day | `vendor claim` (kpler.com/product/maritime/hub) |

Note the tension: 6,250 stations (2023) → 6,600 receivers (current MarineTraffic page) → 13,000+ receivers (Sep 2025 Kpler AIS). The 13,000 figure is for the new feed and presumably counts everything including roaming capacity; the 6,600 is MarineTraffic-branded receiving stations. They are not the same metric and neither is defined. `unverified` comparability.

### D. What the Kpler documentation reveals about the machinery

From `servicedocs-sm.kpler.com/ais-fundamentals/` (read 7 Nov 2026, `documented`):

- **Satellite:** "Kpler satellites spend most of their time over open ocean… messages are published shortly after our satellites pass over a Kpler ground station", so S-AIS arrives in bursts. Download priority is "the most recent message for each MMSI… first", older messages backfilled later, and messages are **not** re-sorted by timestamp, so published order can be out of time order.
- **Dynamic AIS™:** "2860+ satellite-enabled AIS receivers" travelling the busiest lanes, hearing traffic "within 60 nautical miles", uplinking "at least every 15 minutes", ~15 added a month; claimed gain "up to ten thousand" extra MMSIs and "up to six million additional AIS messages per day" (South China Sea emphasis). The mechanism reads as receivers carried on ships or buoys rather than a pure constellation. `vendor claim`; mechanism `unverified`.
- **Downsampling:** terrestrial messages reduced to one per MMSI per 5 minutes by default **in the data products**; their 2021-06-22 example is "up to about 80 million" messages/day on satellite + downsampled terrestrial, against 300M+ full. Separate help pages describe a different cadence for the consumer map (1 per MMSI per minute live, 3–20 minutes for history older than 3 months — mt-methods).

### E. How much comes from each?

No public breakdown exists. Terrestrial is the stated foundation and low-latency layer; roaming fills coastal gaps; satellite gives global reach and is gated behind paid plans. Coverage at sea therefore rests on the satellite and roaming layers — the parts not obtainable free. The Gulf/Red Sea density Aiden saw is consistent with either dense partner stations plus roaming, or satellite, and public material does not let me choose. Settlement: read the "Data received from" field on a handful of public Gulf and Red Sea vessel pages by hand (no automation) and check the station layer there; both are free web views, not endpoints.

## Source rows

| Source | Operator | Type | Regions covered | Access route | Account or cost | What one record contains | Update rate | Delay | Identifies the ship? | Licence, limits | Likely used by MarineTraffic? | Usable by us? | Evidence |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| MarineTraffic terrestrial network | MarineTraffic/Kpler + host partners | shore AIS, volunteer/partner | coastal worldwide, density uneven | closed; host a station to join | free web view; API/plan paid | MMSI, position, SOG/COG, static data, source label | seconds near shore | seconds (downsampled to 5 min by default in feeds) | yes | proprietary terms; academic page 403 (d-ais) | **is** the product | only via hosting/paid API | vendor claim 6,600/6,250/4,500 counts; help articles |
| "Roaming" layer | unnamed partner networks, via Kpler | shore AIS, reciprocal | high-traffic coastal gaps | closed | none public | position + source = Roaming | as partner | unknown | yes | unpublished | **yes**, one of three named layers | no | help article 14594297; Kpler AIS launch note |
| Kpler satellite AIS (ex-Spire Maritime) | Kpler (Spire data/services agreement) | satellite AIS | global ocean | commercial only | paid; satellite view needs Mobile Pro on web | position, occasionally sparse per pass | per pass; "sub-minute" claimed | bursts after ground-station pass | yes | proprietary | **yes** (since Apr 2025) | no | Kpler releases; Spire 8-K; Kpler docs |
| Dynamic AIS™ | Kpler (ex-Spire) | ship/buoy-borne AIS receivers + sat uplink | busiest lanes, 60 nm radius | commercial only | paid | position | ≥ every 15 min | minutes to hours | yes | proprietary | **yes** | no | Kpler docs (`vendor claim`) |
| ORBCOMM satellite AIS | ORBCOMM → S&P Global (Nov 2025) | satellite AIS | global ocean | commercial only | paid | position | per pass | pass latency | yes | proprietary | **yes, 2013–2023**; unknown after | no | ORBCOMM release 15 Oct 2020; S&P release 10 Nov 2025 |
| FleetMon network (absorbed) | FleetMon → MarineTraffic (2022/23) | shore AIS, volunteer | coastal, esp. Europe | closed since merger | was freemium | position + static | seconds | seconds | yes | proprietary | **yes**, merged 2023 | no | Kpler release; DLA Piper; Splash247 |
| MarineTraffic free web/app (as a view) | Kpler | derived display | global | browser | free, login optional | last position + source label + delay text | per source | per source; satellite needs paid plan | yes | terms forbid reuse | n/a | **no** — display only, not a data route | help article 14594297 |

## What this means for us

- **Borrow the provenance model, not the data.** MarineTraffic labels each position with how it arrived (terrestrial / satellite / roaming) and shows its age. That is cheap to copy and it is what our "silence" story needs: a gap in a roaming-fed area is not the same claim as a gap under a satellite pass. Positions should carry `source_class` and `source_id`, and silence tests should be conditioned on them.
- **Expect 5-minute granularity from anything MarineTraffic-derived.** Default terrestrial downsampling is one message per MMSI per 5 minutes; "their feed looks sparse next to ours" is a product decision, not coverage.
- **Do not treat their Gulf density as satellite-only, and do not try to reverse it.** The three layers are commercially closed and the terms forbid reuse. Recording which layer served a few named ships (by hand) is a paragraph of evidence, not a pipeline.
- **Satellite AIS now has two owners:** Kpler (Spire Maritime) and S&P Global (ex-ORBCOMM), with CLS and similar alongside, so there is no small-scale seller to buy from for a weekend.
- **Their own published timings are a fair benchmark:** terrestrial immediate, satellite in bursts after a pass, satellite views paywalled. Our free stack (Digitraffic sub-second, Danish archive ~3 days, GFW ~4 days) is a different, honestly-labelled mix rather than a worse one.

## Unknowns

1. **Split of the 13,000 / 6,600 receivers** between company-owned, host volunteers, partners and roaming — settle by reading operator names for a sample of Gulf/Red Sea stations on the public station layer.
2. **Satellite supplier Jan 2024 – Apr 2025**, between the ORBCOMM contract end and the Spire close — an ORBCOMM or Kpler statement from that window would settle it.
3. **Whether ORBCOMM data still reaches MarineTraffic after the S&P Global purchase**, given S&P is a Kpler competitor.
4. **Any government ingestion** — a Kpler statement, or a station operated by a coast guard or port authority, would settle it.
5. **Which networks "Roaming" covers**, and **pre-2013 satellite AIS** — both unpublished as far as I could see.

## Sources

- `https://support.marinetraffic.com/en/articles/14594297-how-was-the-vessel-s-position-received-terrestrial-or-satellite` — the three source definitions, per-vessel "Data received from" field, satellite needs Mobile Pro.
- `https://support.marinetraffic.com/en/articles/12495052-19-september-2025-announcing-the-launch-of-kpler-ais` — Kpler AIS launch (19 Sep 2025), 13,000+ receivers, Terrestrial/Roaming/Satellite descriptions.
- `https://servicedocs-sm.kpler.com/ais-fundamentals/` — S-AIS bursts and download priority, Dynamic AIS™ (2,860+ receivers, 15 min, 60 nm), 5-minute terrestrial downsampling, 80M vs 300M messages/day.
- `https://support.marinetraffic.com/en/articles/9552994-ais-receiving-stations` and `.../9552984-station-detail-page` — volunteer/partner station model, station pages, free receiver applications.
- `https://www.kpler.com/product/maritime/hub` (read 7 Nov 2026) — 6,600+ AIS receivers, 400k+ vessels/day, 1bn+ signals/day.
- `https://www.kpler.com/blog/kpler-acquires-marinetraffic-and-fleetmon-for-maritime-sector-expansion` — double acquisition, dates, FleetMon bought first, founding year 2007.
- `https://www.kpler.com/blog/kpler-acquires-spire-maritime-to-enhance-maritime-data-and-analytics-capabilities` — Spire Maritime deal, 13 Nov 2024.
- `https://www.satellitetoday.com/finance/2025/04/28/spire-pays-off-its-debt-with-maritime-business-sale/` — $233.5M + $7.5M services; satellite network excluded.
- `https://assets.publishing.service.gov.uk/media/68879b301e72aed40611b019/Full_text_decision.pdf` — CMA ME/2238/25, 25 Jul 2025: merger completed 25 Apr 2025, no market analysis published.
- `https://www.orbcomm.com/newsroom/s-p-global-agrees-to-acquire-orbcomms-automatic-identification-system-business-strengthening-its-supply-chain-and-maritime-offerings` and `https://press.spglobal.com/2025-11-10-S-P-Global-Announces-Successful-Completion-of-its-Acquisition-of-ORBCOMMs-Automatic-Identification-System-Business` — ORBCOMM AIS to S&P Global, Apr–Nov 2025.
- ORBCOMM release 15 Oct 2020 (copies: `finance.yahoo.com/news/marinetraffic-extends-partnership-orbcomm-satellite-123000083.html`, `marinelink.com/news/marinetraffic-extends-partnership-orbcomm-482450`) — partner since 2013, extended to end-2023, combined with land-based network.
- `https://splash247.com/marinetraffic-takes-primacy-over-fleetmon/` (29 Aug 2023) — merged network, "more than 6,250 community-based stations".
- `https://www.linkedin.com/posts/marinetraffic_ais-network-marinetraffic-activity-6749687772728066048-dJEx` (29 Dec 2020) — ">4,500 active" stations.
- `https://allaboutshipping.co.uk/2015/05/27/marinetraffic-com-releases-visualisation-of-global-ship-movements-for-2013-2014/` and `.../2015/05/28/marinetraffic-presses-for-open-data.../` — 2015: 2,000+ stations, 165+ countries, ~20M positions/day.
- `https://www.freightwaves.com/news/equasis-taps-marinetraffic-for-vessel-positioning-data` (11 Jan 2016) — MarineTraffic supplies Equasis.
- `https://www.dlapiper.com/en/news/2023/02/dla-piper-advises-founders-on-sale-of-fleetmon-to-marinetraffic` — MarineTraffic bought FleetMon before Kpler.
- `https://en.wikipedia.org/wiki/MarineTraffic`, `/wiki/ExactEarth`, `/wiki/ORBCOMM` (read 7 Nov 2026) — founding, CEO change, AIS toolbox, Spire–exactEarth; used only for dates not otherwise found.
- Wayback snapshots of `marinetraffic.com/en/p/expand-coverage` (2016, 2019, 2022, 2024) — same volunteer "cover your area" pitch; no station counts on that page.
