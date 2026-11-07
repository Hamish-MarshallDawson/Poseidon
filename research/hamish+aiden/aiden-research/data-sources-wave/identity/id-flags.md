# id-flags: what counts as unusual, and at what threshold

Agent: id-flags. Written 19:15 UTC, Saturday 7 November 2026 (`date -u`). Data read 19:08-19:14 UTC while the shared files were still growing, so every count states its snapshot.

Question: given MMSI-only, which identity rules could we afford to show, at what threshold, with how many false positives per day, and how should we word them?

## 1. Bottom line

1. **Identity change is slow and repetitive, not hourly.** In 325 Global Fishing Watch IMO records (918 identity periods, 593 changes, 2,235 ship-years, read 19:14) a hull changes identity 0.265 times per ship-year — once every ~3.8 years. It is mostly ordinary: 89% of changes also change flag, 64% also change name, and 47% of new MMSIs start within an hour of the old one's last message. `measured`
2. **Short-window conflict is almost absent in live AIS.** A 30-minute worldwide AISStream capture (~8,600 MMSIs, 2,457 with static identity) and two Danish 30-minute windows (2,519 and 1,564 MMSIs) showed **zero** MMSIs with two IMO numbers and zero IMOs on two MMSIs; 3 name conflicts in Denmark, of which 1 was a real typo and 2 were status strings. `measured`
3. **The daily base rate is tiny and concrete:** of 1,372 Danish ships named in windows 11 hours apart, 1 name changed (0.07%), 0 IMOs, 0 call signs, 12 ship types (0.87%). Zero IMOs appeared on two MMSIs in the full 24-hour file (1,503 IMO-bearing ships). `measured`
4. **The IMO and MID validity checks are not ship leads.** Danish 24 h: 17 of 1,503 IMOs fail the 7-digit check, but 10 of the 17 contain a *valid* IMO with extra characters (mostly two trailing zeros, e.g. `919187600`); only 7 are junk. 23 of 3,475 ship-class MMSIs have a country code outside a 292-code MID table, but 17 of those are SAR aircraft (`111`), AtoN (`99x`), SART (`970`), gear buoys or test strings; about 5 look like real vessels with a typo (`223932000` for an Icelandic trawler; Iceland is `251`). `measured`
5. **One rule is worth having, one worth logging, the rest is noise.** "Same IMO on two MMSIs at once" costs ≤7 flags/day at Danish scale and any hit is a strong lead. "Name changed on the same MMSI" costs ~2-3 flags/day there; the single case I saw was a typo, so a fuzzy matcher should absorb most of them before anything is shown. MMSI change alone, flag change alone, IMO checksum failures and MID anomalies fire tens to hundreds of times a day at fleet scale: log them, do not show them.

## 2. Findings

### Global history: how often, and how fast (GFW identity records)

325 IMO records, 918 self-reported identity periods, 593 changes, 2,235 ship-years `measured`:

| transition type | count / 593 |
|---|---|
| MMSI changed | 585 (98.7%) |
| flag changed (GFW derives flag from MMSI) | 526 (88.7%) |
| name changed | 382 (64.4%) |
| MMSI **and** name changed | 374 (63.1%) |
| MMSI changed, name unchanged | 211 (35.6%) |
| name changed, MMSI unchanged | 8 (1.3%) |

Timing from the old period's last transmission to the new one's first: ≤1 hour 278/593 (46.9%), ≤1 day 318 (53.6%), 1-7 days 22, 7-365 days 40, >1 year 21. 192 changes (32.4%) overlap in time, 140 by more than a day.

The overlap is mostly an artefact: the same identity is returned with slightly different date windows by different per-region queries. **GFW history therefore cannot tell "one hull on two MMSIs" from duplicate rows; only live AIS can, and there we saw none.** `measured` In the same sample 112 of 315 ships had three or more flags in their history (max 11) — a churn-heavy subset, not a fleet average.

### Live short windows: what conflict looks like

Danish, 2026-11-01 `measured`:

- 05:18-05:46 UTC, all classes, 304,209 rows, 2,519 MMSIs: 3 with two names (ORSTED EVALUATOR/EVAULATOR, a real typo; "END OF TOW 91%/95%" and "KEEP CLEAR 0.25NM 93/97" are free-text status, not names), 22 with two call signs (0.87%), 19 with two ship types (0.75%), 21 with two destinations (0.83%), 0 with two IMOs, 0 IMOs on two MMSIs.
- 16:30-17:00 UTC, class A, 294,883 rows, 1,564 MMSIs: 0 name, 0 call-sign, 0 type conflicts, 19 destination changes.
- Both windows, 1,412 common MMSIs, 1,372 named in both: name changed 1 (the typo fix), IMO 0, call sign 0, type 12 (0.87%).
- Full day: 3,475 ship-class MMSIs, 1,503 with IMO (43%), 376 blank names, 0 IMOs on two MMSIs, 17 IMO check-digit/length failures (1.1% of those with an IMO), 23 MMSI prefixes outside the MID table (0.66%).

AISStream worldwide 30-min capture `measured`: ~8,600 MMSIs, 2,457 with static identity, 0 MMSIs with two names, two IMOs or two call signs, and 0 IMOs on two MMSIs. `id-joins` found 1 IMO collision in a larger slice, on the junk IMO `100000000`.

The calibration is: **short-window identity conflict is rare enough to be informative; long-window identity change is common enough that it is not, unless narrowed.**

### Base rates translated into flags per day

Rates per ship-day come from the Danish same-day comparison (0.07% name, 0.87% type) and the GFW transition rate (0.265/ship-year = 0.00073/ship-day), multiplied by 1,000 / 3,700 (Danish-sized view, of which ~1,600 carry an IMO) / 10,000 / 100,000 ships. IMO rows assume 43% of ships carry an IMO, as in Denmark. These are arithmetic, not measurements at those sizes `derived`.

| rule | measured rate | flags/day at 1,000 / 3,700 / 10,000 / 100,000 ships |
|---|---|---|
| same IMO on 2 MMSIs, overlap ≥1 h | 0/1,503 IMO-ship-days (95% upper bound <0.2%/day) | ≤2 / ≤7 / ≤20 / ≤200 |
| name on same MMSI changes (any reason) | 1/1,372 ship-days (0.07%); the one case was a typo, so a *real* rename on an unchanged MMSI was 0/1,372 | 0.7 / 2.6 / 7 / 70 |
| MMSI changes within 1 h of old MMSI's last message | 0.125/ship-year | 0.3 / 1.3 / 3.4 / 34 |
| MMSI and name both change (any gap) | 0.167/ship-year | 0.5 / 1.7 / 4.6 / 46 |
| MMSI/flag both change (any gap) | 0.235/ship-year | 0.6 / 2.4 / 6.4 / 64 |
| new MMSI after 7-365 days of silence | 0.018/ship-year | 0.05 / 0.18 / 0.5 / 5 |
| IMO fails check digit or length | 17/1,503 IMO-ships (1.1%/day) | 5 / 18 / 49 / 490 |
| IMO unrecoverable after stripping to 7 digits | 7/1,503 IMO-ships (0.47%/day) | 2 / 8 / 20 / 200 |
| MMSI country code unknown | 23/3,475 (0.66%/day) | 7 / 24 / 66 / 660 |
| ship type changes within a day | 12/1,372 (0.87%/day) | 9 / 32 / 87 / 870 |

Caveat on every row: the GFW panel holds only ships with an IMO and matched identity history, and `id-frequency` measured 0.15/ship-year on a larger earlier panel against my 0.265, so treat 0.15-0.27 as the bracket. The Danish numbers are one day in a well-covered region; a poorly covered region will show fewer transitions and more gaps.

## 3. Change classification

| Change | Typical timescale | Likely causes | Rate, with denominator | Standard, noise or potentially malicious? | Effect on tracking | Effect on prediction | Suggested handling or flag | Evidence |
|---|---|---|---|---|---|---|---|---|
| Name, same MMSI | hours to years | typo correction, rename after sale, operator editing free text | 1/1,372 ships/11 h, Denmark; 8/593 GFW changes | ordinary; noise if a single character | cosmetic; breaks name-keyed dedupe | label change mid-history | log; flag when normalised difference exceeds typo distance | measured |
| Name + new MMSI | same hour to weeks | sale, reflag, new operator | 374/593 changes; 0.167/ship-year | ordinary, common | history splits into two ships | history reset, breaks gap baseline | link via IMO when both carry it; else log | measured |
| MMSI, same IMO/name | minutes to weeks | reflag, re-registration, ITU/flag reallocation, deliberate ID change | 211/593 changes; 0.125/ship-year within an hour | mostly ordinary; the post-gap subset is the suspicious one | duplicate track; false gap and jump | confuses sales with evasion | weak; moderate after ≥24 h silence | measured |
| Flag (MID), with MMSI | same as MMSI | sale/reflag; grey-flag migration | 526/593 changes; new flags on 566 moves: LBR 60, PAN 59, MHL 50, COM 12, CMR 12 | ordinary; flag-shopping not visible in AIS alone | flag field changes, history does not | flag one-hot features reset | never alone; context only | measured |
| IMO present but invalid | static message | keypad/encoding error, truncated IMO, deliberate junk | 17/1,503 ships/day; 10 recoverable, 7 junk | mostly encoding noise; some deliberate | IMO join fails silently | loss of hull linkage | strip to 7 digits and re-validate; show "IMO unverified" | measured |
| IMO changed on same MMSI | rare | re-entry of static data, or the same radio now on another hull | 0/1,503 ship-days in Denmark; 0 in 30-min captures | strong if it persists; glitch otherwise | hull identity jumps | worse: poisons history for both hulls | require ≥2 messages or ≥1 h persistence | measured |
| Same IMO, two MMSIs at once | minutes to days | duplicated/borrowed IMO, transponder duplication, or an actual second hull | 0/1,503 IMO-ship-days; 0/2,457 worldwide | strongest cheap lead; unexplainable, not proven | two moving tracks for one hull | duplicated features; label leakage | alert when overlap ≥1 h and both move | measured |
| Type/size/draught change | hours | refit, defaults, vendor quirks, mis-keying | 19/2,519 (30 min), 12/1,372 (day) | noise | cosmetic | weak | log only; fuzzy tolerance on length | measured |
| Destination/ETA change | minutes | normal operations | 19-21/2,519 per 30 min | ordinary | none | none | never flag | measured |
| Call sign change | minutes | static re-entry, class B quirks | 22/2,519 per 30 min, 0/1,372 across a day | noise | cosmetic | none | log only | measured |

## 4. What this means for us, given MMSI-only

- **MMSI-only is defensible for the map and indefensible for history.** 98.7% of identity changes involve a new MMSI, so a new MMSI looks like a new ship: the hull's past disappears, the gap detector restarts, and "went dark before" never fires for the same hull. One small fix covers most of it: link hulls on `(imo, normalised name)` when an IMO is present, keep MMSI as the display key.
- **Flagging is cheap only if the rule fires rarely.** At 3,700 ships only two rules stay under ~5 flags/day: concurrent same-IMO (≤7) and same-MMSI name change (~2-3). The rest either need a 10,000-ship fleet or drown the operator.
- **Registry comparison is not a flag.** `id-joins` measured 11.4% flag and 16.6% name disagreement between GFW self-report and registry snapshots; my read at the 153-record snapshot gave 73/118 flags and 98/118 names differing on the latest registry row. Snapshot lag explains most of it. Show it as "registry says X", never as a warning.
- **Evidence ladder, for the UI and the pitch:**
  1. *Log only:* any single-field static change, old and new values.
  2. *Weak:* MMSI changed for a hull linked by IMO, no gap.
  3. *Moderate:* new MMSI within 72 h of ≥24 h of silence, same IMO or normalised name.
  4. *Strong:* same IMO on two MMSIs, ≥1 h overlap, both moving (0/1,503 ship-days).
  5. *Corroborated lead:* 4 plus a flag change and a destination change, with the raw messages attached.
  Wording: "identity fields changed in a way our data cannot explain", "could be a sale, a reflag, an equipment fault or an attempt to avoid tracking; we cannot tell which". Never "spoofing", "dark vessel" or "sanctions evasion" from identity data alone.
- **Pitch value: yes, as a measured story, not a feature.** Judges reward base rates and precision. "Identity change is common (≈0.15-0.27 per hull-year), most of it is sales and reflags, one class is rare and unexplained (two live MMSIs on one IMO), and here is the false-positive budget per day" beats another detector slide. The smallest credible study: hand-label 200 GFW identity transitions (sale, reflag, rename, typo, unexplained) and run the "same IMO on two MMSIs" test across 5-7 Danish days plus 24 hours of AISStream — about half a day, putting a real number on the only rule we would ship.

## 5. Unknowns and how to settle them

- **Whether GFW overlaps are real concurrency.** Reconstruct periods from raw messages for the 192 overlapping pairs and look for two simultaneous moving tracks; `id-shortterm` is on this.
- **Rates outside well-covered waters.** All short-window numbers are Baltic/Danish. One day of AISStream per region, same window comparison, gives the non-European base rate.
- **The 57% of ships with no IMO**, which no identity rule can link. The only cheap test is name+call-sign fuzzy matching; `id-fuzzy` owns the false-merge analysis.
- **Temporal trend.** My per-year starts rise from ~7 per 100 ship-years (2014-2019) to 25-36 (2024-2026), almost certainly because recent identities are better observed and matched. `id-frequency`'s panel should settle it.
- **MID list completeness.** My first hand-parsed table (285 codes) produced false "unknown" hits for real registries such as São Tomé (668). The figures above use `id-fuzzy`'s 292-code table at `$WAVE/data/id-fuzzy/mid_wikipedia.json`, which still lacks 780/785/790; re-check before reporting any single MMSI as invalid.
- **Whether a bad-IMO rate differs by flag.** Not measured; would need the GFW registry join per flag.

## 6. Sources

- Shared wave data: `$WAVE/data/identity/gfw-identities.jsonl` (325 records at 19:14); `aisstream-capture.jsonl` (~11,200 messages at 19:12); `$WAVE/data/t-match/ais_0532_raw.csv`; `$WAVE/data/t-ais-history/day_2026-11-01/{classa_1630_1700Z.csv,vessels.csv}`. All `measured`.
- Scripts (mine): `$WAVE/scripts/id-flags/{ais_flags.py,gfw_flags.py,danish_flags.py}`; outputs in `$WAVE/data/id-flags/`.
- ITU Maritime Identification Digits table: `https://en.wikipedia.org/wiki/Maritime_identification_digits` (fetched 19:14 UTC) and `id-fuzzy`'s 292-code extraction at `$WAVE/data/id-fuzzy/mid_wikipedia.json`. Used only for MMSI plausibility. `documented`
- Cross-agent numbers used: `id-frequency` (0.15/ship-year pooled, 51% ≤1 h, dedupe warning), `id-joins` (IMO vs MMSI sanctions-join rates, AISStream IMO bad check digit 49/1,298, registry disagreement 11.4%/16.6%, one IMO collision on `100000000`), `id-fuzzy` (MetaData.ShipName is not an independent source; 292 codes in their MID table). Each is `measured` by that agent.
- Earlier wave: `data-sources-wave/SYNTHESIS.md` "Hormuz and tankers" for the 29/40, 31/40, 38/40 same-IMO-new-MMSI samples, and the Lloyd's List/Windward figures in my brief. `press` / `vendor claim` as labelled there; not re-measured here.
