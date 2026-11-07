# Short-term identity changes (minutes to days)

> **Orchestrator correction, 7 Nov:** this report misread 0.1-degree grid cells. A cell such as `570/99` means 57.0N 9.9E, in Denmark, not 98E. MMSI 219018851 is near Aalborg. There were no "inland Asia" clusters and no thousands-of-km jumps. Re-measured on the Danish day after cleaning: 35 of 3,461 MMSIs (1.0%) had a jump over 60 knots and 5 km, 14 over 100 km and 1 over 1,000 km. Use these figures and `SYNTHESIS.md` over bottom-line item 5 and section 2.5 below.


Agent: id-shortterm. Written 19:26 UTC Saturday 7 November 2026, from a full Danish AIS day (2026-11-01) and a worldwide AISStream capture. All figures `measured` unless labelled otherwise. Ships are referred to as data examples, not accusations.

## 1. Bottom line

1. **Within one day, MMSI never changed hands.** In the full Danish day (15.98M position rows, 3,505 mobile MMSIs, 1,503 with an IMO) there were **0 MMSIs carrying two IMO numbers and 0 IMO numbers on two MMSIs**. Two independent passes (mine and id-impact's) agree. A 24-hour build keyed on MMSI loses nothing measurable to identity handover.
2. **What does change inside a day is the static *string*, not the identity.** 0.72% of ship-class MMSIs (22/3,049) showed two values of name, call sign, type or size in 24 h, and 4.0% (123/3,049) showed two draughts. Nearly all of it comes from a few transmitters oscillating between two spellings, tens to hundreds of times a day. That is a normalisation problem, not a detection opportunity.
3. **The base rate says a 24 h window should almost always contain no handover at all.** At 0.090-0.151 identity starts per ship-year (id-frequency), 1,503 IMO-carrying ships in Danish waters yield **0.37-0.62 expected handovers per day** — so "0 observed" is the expected result, not proof that handovers are rare in general. Inside a 30-minute capture the expectation is 0.008.
4. **The only genuine "same IMO, two MMSIs at once" evidence in a short window is junk IMO placeholders.** In the worldwide capture, 3 IMOs sat on more than one MMSI within 11.8 minutes: 100000000 (three unrelated craft), 1, and 999999999. After rejecting zero, check-digit failures and known placeholders, **0 of 4,733 IMO-carrying MMSIs** shared an IMO in the window. Supports id-imo-fraud's rule: filter the IMO before any grouping.
5. **"Two places at once" is real but rare and unexplained.** Impossible same-MMSI jumps occur, and the lat-91 sentinel and zeroed fixes create 95% of the raw count. After cleaning, **12 of 3,505 MMSIs (0.34%)** jump thousands of km and return, e.g. 219018851 (main cluster 57.0N 98-99E, single fixes at 61.6N 103E) and 246843000 (main cluster 54-56N 119-127E, fixed clusters at 58.9N 51E and 57.6N 74E) — both European MIDs sitting in inland Asia. Either reused MMSIs or a relay/decoding artefact; unresolved, and the only short-term signal worth a look-list.

## 2. Findings

### 2.1 One MMSI, several static values, within 24 hours (Danish day 2026-11-01)

Source: `aisdk-2026-11-01.zip` (2.9 GB, 15,981,609 rows), streamed once; script `$WAVE/scripts/id-shortterm/daypass.py`; output `$WAVE/data/id-shortterm/day-summary-2026-11-01.json`, `day-pership-2026-11-01.json`. Excluded base stations, AtoN, AIS-SART, EPIRB and SAR aircraft; then excluded AtoN-like MMSIs (8-digit, 97x/99x, status-in-name). Denominator: **3,049 MMSIs with ≥20 fixes**.

| Field | MMSIs with ≥2 values | Share | Transitions that day | Transitions per ship-day |
|---|---|---|---|---|
| Name | 3 | 0.10% | 198 | 0.065 |
| Call sign | 2 | 0.07% | 137 | 0.045 |
| Ship type | 3 | 0.10% | 34 | 0.011 |
| Length | 16 | 0.52% | 672 | 0.22 |
| Width | 7 | 0.23% | 27 | 0.009 |
| Draught | 123 | 4.03% | 147 | 0.048 |
| Any of name/call sign/type/size | 22 | 0.72% | — | — |
| Any field including draught | 145 | 4.76% | — | — |

**The transitions are concentrated in a handful of oscillating transmitters**, and that is the point: "changed once" (a genuine update) and "flipped 166 times" (two strings alternating on air) look identical in a distinct-value count.

- **219033037 (Danish MID):** broadcasts both `ORSTED EVALUATOR` and `ORSTED EVAULATOR` (a typo), 166 name transitions in 24 h, both values present from 00:07 and 00:39 onwards. Same ship, same MMSI, and it hits a 20-minute window with either spelling.
- **219002719:** call sign alternates `OU07502` / `OU7502`, 135 transitions.
- **265079580:** length alternates 49 / 50, 466 transitions.
- **265123000:** name `WWW.FURUNO.SE` / `FURUNO SVERIGE AB` and type Passenger / Pleasure, 30 transitions each — a vendor demo transmitter.
- **219016938 LANGELAND:** one corrupted name `LANGELANDC]6` for 78 seconds against `LANGELAND` for the whole day. A receiver-side 6-bit decode artefact, not a rename.
- Type flips worth knowing about because they are *ship-class*: 257432330 Tanker→Cargo (1 transition), 219029601 Pleasure→Other (3).

**Draught is not identity.** 4% of ships reported two draughts in a day (6.8→8.8 m on 219034365, etc.). That is ballast/cargo, it is expected, and any "size changed" flag must exclude draught or it will alert on roughly 120 ships a day in Danish waters alone.

### 2.2 Buoys and virtual AtoN manufacture false positives

18 of the 3,067 MMSIs with ≥20 fixes rewrite their name/call sign as *status text*: `KEEP CLEAR 0.25NM 9x`, `FISHFARM 9x%`, `GILNET BOUY`, `END OF TOW 9x%`. One unit (992190005) produced **55 distinct names in a day**; 97000106 also 55. Filter 8-digit MMSIs and the 97x/99x ranges first, or the top of any change list will be fish-farm gear.

### 2.3 Worldwide capture: 11.8 minutes, 24,170 MMSIs

Source: `aisstream-capture.jsonl`, snapshot read 19:18 UTC (65,106 AIS messages). Script `$WAVE/scripts/id-shortterm/capturescan.py`, output `$WAVE/data/id-shortterm/capture-scan.json`. The capture was still growing; final numbers will be slightly larger.

| Field | MMSIs carrying the field | MMSIs with ≥2 values | Share |
|---|---|---|---|
| Name | 22,922 | 8 | 0.035% |
| Call sign | 12,552 | 5 | 0.040% |
| Ship type | 13,408 | 2 | 0.015% |
| Dimensions | 13,199 | 21 | 0.16% |
| IMO | 4,733 | 0 | 0% |

Most of the 8 name conflicts are formatting or decode noise (`LOCA LOLA 2`/`II`, `RUEY I SHYANG`/`RUEY ISHYANG`, `MIP- 3`/`MIP-3`, `LISTA@@@@N\*`/`LISTA`). Two look like real content changes inside 8 minutes, leads only:

- MMSI **244030275** sent `ALELOTTE` at t+101 s and `PIACERE` at t+473 s.
- MMSI **244000460** sent `THE VIKING` at t+104 s and `SILVER GHOST` at t+267 s.

Both are consistent with two different vessels sharing a reused MMSI, or a static message updated at a handover. IMO 0 for both, so I cannot tell ships apart. Treat as "MMSI reuse inside minutes happens at least twice in 24,170 ships in 12 minutes" — a lead, not a rate.

Dimension conflicts are mostly one-digit offsets on the same hull (`18x24x4x4`/`18x24x3x5`, A+B and C+D constant), not two ships.

### 2.4 One IMO on two MMSIs at the same time

- **Danish day: 0 of 1,503 IMO values** appeared on more than one MMSI (my pass; id-impact and id-joins independently got 0).
- **Worldwide capture: 0 genuine** of 4,733 IMO-carrying MMSIs. The three apparent collisions are placeholders: 100000000 on 266037000, 338093828, 369970482 (matches id-impact's 4-minute observation), plus `1` and `999999999`.
- Therefore the "same IMO, two MMSIs concurrently" test has **no measurable true-positive rate in free live AIS** and an unreliable positive rate until junk IMOs are removed. As a flag it is currently all false positives.

### 2.5 One MMSI in two places at once

Danish day, consecutive-fix test with the position sentinel (lat 91), out-of-range and 0/0 fixes removed (script `$WAVE/scripts/id-shortterm/twoplace.awk`; output `$WAVE/data/id-shortterm/twoplace-day.txt`):

- Two fixes on the same MMSI more than 5 km apart within 2 s, i.e. physically impossible for one transmitter: **29 MMSIs (0.83% of 3,505)**, 180 pairs.
- Implied speed over 100 kn across a gap of 2-120 s (20 km+): **134 MMSIs (3.8%)**, 192 pairs.
- The A→B→A pattern (jumps far, comes back within 3 km), the signature of two interleaved transmitters: **12 MMSIs (0.34%)**, 45 pairs.

Examples: 246843000 553 km in 0 s (and a 34 km/2 s variant later the same day); 219018851 72 km in 2 s; 211356660 56 km in 1 s; 218795000 95 km in 0 s and straight back. Some of the list is junk identity, not ships: 992111032 (AtoN-style MMSI) produced a 6,179 km same-second pair, and 257097800 a 2,921 km one at t+0.

**No MMSI showed sustained interleaving, but the far fixes are not all random.** A hull sharing an MMSI continuously would alternate every few seconds and produce thousands of impossible pairs a day; the worst case here has a handful. The far clusters are not all single corrupt seconds either. **219018851** (MMSI 219…, Danish MID) has 1,158 fixes at 57.0N 98-99E plus 2-3 fixes at **61.6N 103E**; **246843000** (Dutch MID) has its bulk at 54-56N 119-127E, plus 1-2-fix clusters at **58.9N 51E** and **57.6N 74E**. All of those are inland Asia, thousands of km from European waters, and the small clusters sit in stable cells rather than being one random point. Either a second transmitter shares the MMSI or a receiver/gateway publishes positions under the wrong MMSI; this data cannot separate those. So: **0 confirmed two-hull cases, 12 MMSIs (0.34%) with a far-away repeat cluster worth a manual look.**

Without the sentinel filter the same test fires on 567 MMSIs / 769 pairs in the same day, i.e. **95% of the crude signal is bad data** (and most of the rest is one corrupt fix). Any "MMSI in two places" flag needs the lat-91 sentinel, 0/0 and out-of-range filter plus a minimum count per MMSI, or it is a list of broken positions.

## 3. Change classification

| Change | Typical timescale | Likely causes | Rate, with denominator | Standard, noise or potentially malicious? | Effect on tracking | Effect on prediction | Suggested handling or flag | Evidence |
|---|---|---|---|---|---|---|---|---|
| Name string alternates (typo/AIS decode) | seconds to hours, repeatedly | transmitter keeps two strings; 6-bit decode artefacts | 3/3,049 MMSIs/day (0.10%), 198 transitions | noise | none if keyed on MMSI; wrong label if keyed on latest static | label noise in history (~1 ship/day in DK) | cache first-seen static per MMSI per window; normalise case/spacing/punctuation | measured, this report §2.1 |
| Call sign alternates | seconds to hours | as above (OU07502/OU7502) | 2/3,049/day, 137 transitions | noise | none | none | as above; never key on call sign | measured, §2.1 |
| Ship type alternates | hours | wrong static entry, vendor demo | 3/3,049/day | noise | wrong type in UI/forecast filter | small | prefer majority value over window | measured, §2.1 |
| Length/width alternate by 1-2 m | hours | rounding in dimensions A-D, re-measurement | 16/3,049 (0.52%) length, 7/3,049 width | noise | none | none | ignore ±2 m; never treat as size change | measured, §2.1 |
| Draught changes | hours to days | loading/ballast | 123/3,049/day (4.0%) | legitimate operational | none (not identity) | useful as cargo signal | do not flag as identity | measured, §2.1 |
| AtoN/buoy status-in-name | minutes | virtual aid encodes status in name | 18/3,067 MMSIs/day, up to 55 names each | noise by design | none if filtered | none | filter 8-digit, 97x/99x, 99xxxx MMSIs | measured, §2.2 |
| Same IMO, two live MMSIs | minutes to hours | MMSI reuse after sale, or two hulls on one number | 0/4,733 in 12 min; 0/1,503 in a day; junk only | would be a strong lead if it occurred | would split one hull into two tracks | leaks labels across hulls | check-digit + placeholder filter, then group by IMO; expect almost no hits | measured, §2.4 |
| Two fixes in impossible places on one MMSI | seconds to hours | corrupt fixes and relays (dominant), or two hulls sharing a number | 29/3,505 MMSIs/day after sentinel cleaning (567 uncleaned); 12/3,505 with a far repeat cluster | noise in most cases; potentially malicious if repeated | merges tracks or emits false jumps | pollutes speed features | filter sentinel/0/0, then look-list MMSIs with a repeated far cluster (≥3 fixes); do not treat as detection | measured, §2.5 |
| MMSI handover (old MMSI stops, new starts, same IMO) | hours to days between last/first transmission | sale, reflagging (MMSI is reassigned per ITU-R M.585-10 §1(c)) | 0.37-0.62 expected per day per 1,503 IMO ships; 0 observed | ordinary, days-scale | splits history; invisible in a 24 h window | label leakage if history joined by MMSI | IMO-keyed history; no short-term flag justified | measured base rate from id-frequency, applied here |

## 4. What this means for us, given MMSI-only

- **For the 24-hour build, MMSI keying is safe against handovers.** 0 in a day, 0.6 expected. Do not spend build time on identity-switch detection.
- **Three cheap hygiene fixes are worth doing anyway:** (a) keep the *first* static record per MMSI (or store all and display a mode) so a label doesn't flip mid-session (ORSTED EVAULATOR); (b) filter non-ship MMSIs (8-digit, 97x/99x, lat 91 sentinel, 0/0 fixes) before counting ships; (c) reject IMO 0, placeholders (100000000, 1234567, 999999999, 1) and check-digit failures before keying on IMO.
- **Optional small flag, if there is spare time:** "same MMSI in two places at once" (repeated far cluster, sentinel filtered, ≥3 fixes). Measured yield: 12/3,505 MMSIs per day in one region (0.34%), all unresolved between MMSI reuse and relay artefact. Worth a look-list, not an alert or a claim.
- **Pitch sentence that survives our data:** identity change is a days-to-years phenomenon (0.09-0.15 per ship-year, 78% with under an hour of silence), so it belongs in the history layer, not the live tracker; short-term noise is spelling and buoys.

## 5. Unknowns

- **One day, one region.** Danish waters are Class A-heavy, well received and low-churn. Hormuz or Malacca may show more concurrency; we have no free full-day feed. Settle with a longer AISStream capture.
- **Whether the two in-capture name changes are one hull or two.** Needs IMO/position history for MMSI 244030275 and 244000460.
- **Whether any cleaned A→B→A case is MMSI reuse, cloning or one receiver mislabelling two ships.** Needs per-receiver source tags, which the Danish aggregate file lacks.
- **Class B** is under-measured: name and details arrive in separate parts, and only 1 of 2,083 Class B MMSIs in the capture carried an IMO (id-joins).

## 6. Sources

- Danish Maritime Authority AIS, day 2026-11-01: `http://aisdata.ais.dk/aisdk-2026-11-01.zip` (2.9 GB; 15,981,609 rows). Local: `$WAVE/data/t-ais-history/aisdk-2026-11-01.zip`.
- AISStream worldwide capture: `$WAVE/data/identity/aisstream-capture.jsonl` (65,106 messages, 24,170 MMSIs, 19:07-19:18 UTC).
- id-frequency (base rates), id-impact (independent Danish-day pass), id-joins (cross-feed), id-imo-fraud (placeholder IMOs) — shared notes and reports in this folder.
- Scripts: `$WAVE/scripts/id-shortterm/daypass.py`, `capturescan.py`, `twoplace.awk`, `clusters.awk`. Outputs: `$WAVE/data/id-shortterm/` (`day-summary-2026-11-01.json`, `day-pership-2026-11-01.json`, `capture-scan.json`, `twoplace-day.txt`, `clusters.txt`).
