# d-methods: comparing radar with AIS, and what "going dark" really means

Saturday 7 November 2026. Labels: `measured` (I ran it), `documented` (primary
source), `author-measured` (number published by the project that measured it),
`unverified`.

## 1. Bottom line

1. **Radar-to-AIS matching is a solved, published problem with published limits.**
   Global Fishing Watch's matching code is open, and the 2024 *Nature* paper gives
   the detection floor: **>70% of 25 m vessels, >90% of 50 m and above**
   `documented`. That floor, not the idea, decides which regions and which
   stories work.
2. **Motion, not position accuracy, is the error that bites.** Sentinel-1 locates
   a *stationary* point to 7 m `documented`, but a moving ship appears displaced
   along the satellite track by roughly 117 s × its range-direction speed:
   **~600 m at 10 kn, ~1.2 km at 20 kn** `measured` (arithmetic, matching GFW's
   published formula). One open project recovered **89 of 149 matches** by
   correcting it `author-measured`.
3. **Image time is a range, not a timestamp.** One Sentinel-1 IW GRD product is
   25 s of sensing; the 1 November Denmark scene is four consecutive products
   spanning **~100 s** `measured`. A 20 kn ship moves about **1 km** across it.
4. **A quarter of ordinary AIS traffic cannot be matched at a small gate.** At that
   scene time the nearest Danish fix was 3 s old for half the Class A vessels under
   way, but **23% had no fix within 300 s** `measured`, and **49% of archive rows
   are duplicate receptions** `measured`. Both would otherwise look like silence.
5. **No AIS never implies intent.** Carriage is mandatory for most commercial
   tonnage, and the master may lawfully switch off for safety or security if the
   reason is logged (`IMO A.1106(29)` §22) `documented`. The only method with
   published accuracy for separating deliberate silence from reception loss that I
   could find needs **≥12 h gaps, >50 nm from shore and ≥19 satellite fixes
   beforehand** `documented` — it does not transfer to the Baltic approaches.

## 2. Findings

### 2.1 What published matching methods do

Every method I read follows five steps: gather AIS either side of the image,
project each vessel to the image time, correct the radar's own moving-target
displacement, score detection–vessel pairs, accept a *ranked* match rather than a
fixed distance.

**GFW's code** (`GlobalFishingWatch/paper-longline-ais-sar-matching`, read
directly) `documented`: a **12 h** AIS window either side; AIS within **200 nm** of
the scene; one segment per vessel per scene; the vessel extrapolated along its
course by speed × elapsed minutes; then an explicit Doppler/azimuth correction
`v_perp · sin(look_angle) / v_sat · slant_range` subtracted along the satellite
track; candidates scored against 1° probability rasters of where the vessel could
be before and after its last fix; the **top four** candidate matches kept. No
acceptance-threshold radius appears in the code.

**Paolo et al., *Nature* 2024** (same code path) `documented`: 53 billion AIS
positions compared with Sentinel-1 detections; the threshold was set so matches
equalled the number of detections expected from AIS-carrying vessels — **17
million matches at score 7.4 × 10⁻⁶**. They write "not publicly tracked", not
"dark", and note that vehicles on roads at >100 km/h appear up to **1 km** from the
road, sometimes over water.

**Pelich et al. (ESA 2019)** `documented`: ±15 min window; English Channel, 10
images, ~2,000 vessels: **15–20% of AIS positions with no radar correlation**;
North Sea: 145 matched, **65 radar detections without AIS**, **76 AIS positions
without radar** (≈69% and ≈66% respectively). **Kurekin et al. 2019** (Ghana,
operational) `documented`: "detection success rate of 91% for AIS-registered
vessels", products within **2 h** of the overpass, over 17 months.

**esamoun/dark-vessel-detection** (repo docs) `author-measured`: Kattegat, **200 m**
tolerance, azimuth fix worth 89/149 matches; **65** fixed positions recurred in ≥20
acquisitions and produced **782 of 972** high-confidence detections; 189 detections
from 49 acquisitions, **21.2%** undeclared.

The spread (66–91%) is not disagreement: papers differ in tolerance, density and
which denominator they use. Report the gate, the correction applied, and both
denominators — detections matched and AIS matched.

### 2.2 Error budget

| Contribution | Size | Evidence |
|---|---|---|
| S1 IW GRD pixel / resolution | 10 m / 20.4 × 22.5 m | `documented` SentiWiki |
| S1 IW GRD location accuracy (NRT) | **7 m** | `documented` SentiWiki |
| Sensing time, one product | **25 s** (±12 s per line) | `measured`, STAC start/stop |
| Sensing time, 1 Nov Denmark acquisition | **~100 s** (4 products at 25 s) | `measured` |
| Along-track shift of a moving ship | 117 s × radial speed: 300 m @5 kn, **600 m @10 kn, 1.2 km @20 kn** beam-on, ~0.7× at 45° | `measured`; formula from GFW code |
| AIS nominal interval, Class A | 2–10 s; 3 min at anchor | `documented` ITU-R M.1371-5 |
| AIS interval, Danish coastal, de-duplicated | median **9 s**, p90 11, p99 31 | `measured`, 181,493 intervals |
| Duplicate receptions | **49%** (DMA archive, multi-receiver); 0.25% (Digitraffic MQTT) | `measured` here; `measured` by t-ais-live |
| AIS staleness at image time | median 3 s; **23% of vessels >300 s** | `measured`, 432 vessels |
| Implied AIS error at image time, 8–16 kn | median 13–15 m, p90 33–48 m | `measured` |
| Satellite AIS first-pass detection (on-board processing), dense area | **~15%** where a footprint holds ~1,000 ships | `documented` IALA A-124 App.19 |
| Terrestrial AIS range | 20–30 nm design, 40–50 nm typical | `documented` ITU-R M.2084; IALA/vendor |
| Chance coincidence, 200 m gate | ~1 × 10⁻⁴ per detection (500 moving vessels, 50,000 km²) | `measured` arithmetic |

So: **use each product's own line times** (t-match found the AWS annotation XML
carries `productFirstLineUtcTime`/`LastLineUtcTime`, which is the exact route),
**correct the azimuth shift**, and **report match counts at 200 / 500 / 1,000 m**.
At 200 m, chance matching is negligible even in a busy basin, so an unmatched
detection means no recent fix — conditional on the vessel transmitting at all.

### 2.3 Who must transmit, and when silence is lawful

- **SOLAS V/19.2.4** `documented`: AIS required on ships ≥300 GT on international
  voyages, cargo ships ≥500 GT on domestic voyages, all passenger ships; phased
  2002–2008.
- **IMO A.1106(29)** §22 `documented` (full text read): "AIS should always be in
  operation when ships are underway or at anchor. If the master believes that the
  continual operation of AIS might compromise the safety or security of his/her
  ship or where security incidents are imminent, the AIS may be switched off…
  the master should report this action and the reason for doing so to the
  competent authority… Actions of this nature should always be recorded in the
  ship's logbook… The master should however restart the AIS as soon as the source
  of danger has disappeared."
- **EU 2002/59/EC Annex II** `documented`: fishing vessels >15 m overall, phased
  in by 31 May 2014.
- **US 33 CFR 164.46** `documented`: Class A on self-propelled commercial vessels
  **≥65 ft**, towing vessels ≥26 ft and >600 hp, vessels certificated for >150
  passengers; deviations available for confined-area and short-voyage craft.
- **Unverified**: national rules for small/artisanal fleets in Indonesia,
  Malaysia, Thailand, Vietnam, the Philippines; the exact US power-down clause;
  warship exclusions (only that guidance warns they may not be fitted).

Consequence: in the Baltic and Hormuz nearly every merchant hull must transmit, so
"was transmitting, then stopped" is a meaningful observation. In Asian small-scale
fisheries a boat may have no duty at all, so no AIS carries no signal, and radar
cannot name anyone. Separately, note that **Digitraffic publishes Class A only and
filters out fishing vessels entirely** `documented` (t-ais-live), so an absence in
that feed is not an absence at sea.

### 2.4 Deliberate silence vs reception loss

Welch et al. 2022 (*Sci Adv*, text and code read) `documented`:

1. gaps **≥12 h** (shorter gaps are dominated by reception variability);
2. both ends **>50 nm from shore**;
3. reception in the cell **>10 pings/day**;
4. **≥19 satellite positions in the 12 h before the gap**;
5. a rule-based classifier over reception rate at the gap's start and end cells,
   positions beforehand, and gap geometry.

Performance `documented`: **precision 0.86, false-positive rate 3.72%, F0.5 0.739**,
giving **55,368 events from 5,269 MMSIs**; disabling hid up to **6%** of fishing
activity. GFW's own API caveats call gap events algorithm outputs and warn that
reception variability causes them `documented`.

The *shape* transfers; the thresholds do not. In the Danish straits reception is
continuous and duplicate-rich, so a 30-minute gap with three neighbours still heard
is proportionally stronger evidence than at 50 nm offshore — but only with a
per-cell rate baseline and a duplicate filter.

**GNSS interference is the other confounder.** GPSJam bulk files need no key, and
the wave measured bad-aircraft share on 6 Nov 2026: **Hormuz 12.5%, Gulf of Finland
8.3%, Danish straits 0.9%, Natuna 0%** `measured` (d-context). Where jamming is
heavy, both the AIS fix quality and any "impossible speed" inference degrade
together, so spoofing claims must be cell-level and time-local, never ship-only.

### 2.5 What can honestly be said

**From radar alone:** position, an estimated length (GFW regress it from the
signature), wake-implied course and speed. No name, flag, type or MMSI. Fixed
structures, turbines, bridges, wakes and road traffic all produce targets: a
20.5 km test window gave 30 blobs of which **28 sat on one fixed structure**
`measured` (t-sat-access), and recurrence across passes is the practical mask
(65 such positions explained 80% of esamoun's detections).

**From a track either side of a gap:** a reachable-area bound (speed × elapsed
time), a course/speed consistency test, and — only where the AIS identity is
continuous — an attribution that the same MMSI reappeared.

Wording that holds, with the claim it supports:

- "A radar target at 55.21 N 12.61 E, estimated length 90 m, has no AIS report
  within 500 m in the preceding 19 minutes, while 11 vessels within 20 nm were
  reporting normally." *(a measurement with its condition)*
- "Last fix 4 minutes before the image; at 12 knots the vessel could be up to
  1.5 km away." *(bounds)*
- "No AIS received 14:05–15:40; reception in the surrounding 0.1° cell was normal
  throughout." *(silence plus reception control)*
- "The reported position implies 41 knots over 12 minutes, which is not physically
  possible for this hull." *(inconsistency, not intent)*
- "Consistent with AIS switched off, a transponder fault, or reception loss we
  cannot rule out." *(honest trivalent)*

Avoid: "dark vessel" as a finding, "went dark to hide", "confirmed spoofing",
"sanctioned ship detected by radar", and "no AIS" without saying where and when you
looked.

## 3. Source rows

| Source | Type | Regions | Free access | Account? | One record | Update | Delay | Accuracy | Identifies ship? | Licence | Evidence |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Terrestrial AIS (DMA archive, Digitraffic, Kystverket) | self-report | coastal Baltic/Norway | HTTP zip, REST/MQTT | No | MMSI, position, SOG/COG, type, IMO | 2–10 s per ship | s (live), 3 d (DMA) | ~10 m | Yes | CC BY 4.0 (Digitraffic); DMA terms | `measured` this wave |
| Satellite AIS (commercial aggregation) | self-report | global | paid; via GFW products | Yes | same fields, sparser | ~hourly | min–hours | ~10 m | Yes | commercial | IALA A-124 App.19; Kurekin 2019 |
| Sentinel-1 IW GRD C/D | radar | global; ~5 passes/wk Baltic point | Earth Search / PC STAC + COG ranges | No | VV/VH amplitude, 10 m pixels | 6–12 d repeat | 0.5–1.2 h in Europe | 7 m location, 20×22 m | No (length only) | Copernicus, free | `documented` SentiWiki; `measured` timing |
| GFW Sentinel-1 detections | derived radar | global | dataset download | Yes (free token) | lat/lon, time, length, AIS match | daily | ≥5 d | as Sentinel-1 | Sometimes | CC BY-NC 4.0 | GFW docs; brief |
| GFW AIS disabling events | derived gaps + code | high seas | dataset + GitHub | No (code) | gap ends, positions before, reception | static 2017–19 | — | n/a | Yes (MMSI) | CC BY 4.0 paper | paper and code read |
| Danish AIS archive | self-report archive | Danish waters/W Baltic | `aisdata.ais.dk` | No | full field set | daily, 3 d behind | 3 d | ~10 m | Yes | DMA terms | `measured`, 15.98 M rows |

## 4. Consequence for feasibility

**Possible now.** In the Baltic a defensible comparison exists: coastal AIS at 9 s
median, ~5 Sentinel-1 passes per week over a fixed point (t-sat-access), 0.5–1 h
from sensing to catalogue, and a 25–50 m detection floor covering every merchant
hull the sanctions story is about. The claim that survives is narrow and real:
*this hull was transmitting, then stopped, while its neighbours were heard, and
radar saw a target of its size where it should have been.*

**Ruled out.** Intent; live radar; gap counts without a per-cell reception model;
matching a moving ship at 200 m without azimuth correction and per-product times;
any "no AIS therefore suspicious" claim where small fishing boats have no duty.

**Regions.** Baltic and Danish straits: full matching plus identity, and historical
AIS exists for Denmark only (Digitraffic keeps last positions, not tracks — no
backfill `measured`, t-ais-live). Hormuz, Malacca, Natuna: radar works on large
hulls, but with no free live AIS the comparison is retrospective and identity-poor;
the honest fallback is radar target counts against published transit numbers.

## 5. Unknowns

- GFW's probability rasters are not obviously public; a 200–500 m gate plus azimuth
  correction is the tractable substitute, and its measured match rate in the Baltic
  is unknown until t-match reports.
- No C-band detection-probability table found (the detectability models are X-band,
  Tings et al. 2018).
- Sentinel-1C/D need per-satellite CFAR recalibration — GFW's September 2026 note
  says so for their own pipeline `documented`.
- Whether a short-gap neighbour test has acceptable precision: the only published
  figure (0.86) is for 12 h high-seas gaps.

## 6. Sources

- GFW matching code (12 h window, 200 nm, Doppler correction, ranking, top 4):
  `github.com/GlobalFishingWatch/paper-longline-ais-sar-matching`.
- Paolo et al., *Nature* 625 (2024); Kroodsma et al., *Sci Rep* 12:21004 (2022);
  Pelich et al., ESA Atlantic-from-Space 2019; Kurekin et al., *Remote Sens*
  11(3):293 (2019); esamoun/dark-vessel-detection docs; Welch et al., *Sci Adv*
  8:eabq2109 (2022) and `github.com/GlobalFishingWatch/AIS-disabling-high-seas`.
- IMO A.1106(29) §22 (text via rise.odessa.ua), SOLAS V/19.2.4 (LISCR/NAVCEN),
  EU 2002/59/EC Annex II, 33 CFR 164.46 (govinfo XML).
- ITU-R M.1371-5; ITU-R M.2084; IALA A-124 Appendix 19; SentiWiki "S1 Products";
  GFW API "Data Caveats"; Digitraffic AIS documentation.
- Scripts: `$WAVE/scripts/d-methods/error_budget.py`, `scene_duration.py`,
  `ais_interval_budget.py`.
