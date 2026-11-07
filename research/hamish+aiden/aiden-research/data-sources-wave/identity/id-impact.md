# id-impact: what MMSI-only breaks

id-impact, identity wave, 7 Nov 2026. Jake's decision (MMSI is the only ship ID; identity-change
detection out of scope) is taken as given. This says what that costs and where. All figures `measured`;
scripts in `$WAVE/scripts/id-impact/`, outputs in `$WAVE/data/id-impact/`. Danish day =
`aisdk-2026-11-01.zip`, 15,981,609 rows, 3,497 mobile MMSIs, 1,507 IMO numbers, streamed whole.

## 1. Bottom line

1. **Within 24 hours, MMSI-only costs almost nothing.** In the Danish day, 0 of 1,507 IMOs appeared on
two MMSIs, 0 MMSIs carried two IMOs, and 0 of the 776 gaps whose record carries an IMO were a key
change. In a 12.5-minute worldwide AISStream window (24,553 mobile MMSIs), 0 keys carried two IMOs and 1
key plausibly carried two transmitters.2. **Over history the split is structural.** In the GFW identity panel, 604 of 858 hulls (70%) used more
than one MMSI. Of 1,619 handovers, 613 came within 20 minutes (invisible to a 20-minute gap detector) and
413 left a gap long enough for a detector to fire: 0.48 per hull lifetime.
3. **"Went dark and came back" is what MMSI-only cannot represent.** 157 of 1,619 handovers (10%)
followed more than 7 days of silence on the old key. A per-MMSI feature sees a permanent disappearance
plus a brand-new vessel; never a return.
4. **Sanctions matching loses about a third of its hits.** Keyed on the Danish day: 54 of 76 matches by
MMSI (71%); 22 (29%) reachable only through the IMO. Consistent with id-joins' 4.8% IMO vs 1.5% MMSI.
5. **The reverse hazard is real: a bad IMO merges unrelated ships.** IMO 100000000 was carried by three
unrelated small craft in Sweden, California and Maryland inside the same 12 minutes; 1 and 999999999 were
each shared by two MMSIs. Any IMO-keyed grouping fuses them. That is the honest argument *for* Jake's
decision, not against it.

The cheapest fix is not a new ID scheme. It is keeping IMO as a side attribute with a validity check, and
treating a new MMSI carrying a known valid IMO as the same hull.

## 2. Findings

### 2.1 Within one day (Danish, 2026-11-01)

| Measure | Result | Denominator |
|---|---|---|
| IMO seen under more than one MMSI in the day | 0 | 1,507 IMOs |
| MMSI carrying more than one IMO in the day | 0 | 3,497 mobile MMSIs |
| Gaps (20 min or more) explained by same IMO on another MMSI | 0 | 776 gaps carrying an IMO |
| MMSI with more than one distinct name | 7 (0.2%) | 3,497 |
| MMSI with more than one call sign | 6 (0.17%) | 3,497 |
| MMSI with more than one ship type | 3 (0.09%) | 3,497 |
| MMSI with more than one reported size | 20 (0.57%) | 3,497 |

The gap result is the important one. `t-ais-history` attributed the 1,407 Danish gaps to reception; this
measures it from the other side. 776 of the 1,407 carry an IMO on the gap record (631 do not, mostly
Class B and the reception-only keys), and not one of those 776 is an identity handover. The 13 within-key
name and call sign changes are renames, corrections or two units on one key; none of the 7 names was
punctuation-only. Caveat: a hull that switched MMSI *and* stopped reporting its IMO on the new key would
be invisible to this test, so read it as "no IMO-carrying hull handed over inside the day".

### 2.2 Within twelve minutes, worldwide (AISStream)

Window 751.5 s, 68,756 messages, 24,553 mobile MMSIs, 4,155 (17%) giving an IMO.

- 0 MMSIs carried two IMOs. 9 (0.04%) carried two names, 5 two call signs, 3 two types.
- Of the 9 double names: 3 were punctuation or spacing only ("MIP- 3"/"MIP-3", "LEB 62"/"LEB-62",
  "RUEY I SHYANG"/"RUEY ISHYANG"), 1 padding ("LISTA@@@@N\*" vs "LISTA"), 1 a numeral style ("LOCA LOLA
  2"/"LOCA LOLA II"). Three of the four real differences sat at the same position within 0.1 nm:
  alternate labels on one transmitter. **One was a key collision**: 366999010 reported "SURVEY VESSEL
  GRAHAM" at 47.24N -122.43 and "ISLAND VOYAGER" at 45.58N -122.76 — 1 in 24,553 keys (0.004%).
- Three IMOs appeared on more than one MMSI and **all are invalid placeholders**: 100000000 (266037000
  "KARLSKRONAVARVET" Sweden, 338093828 "LA FIREBOAT 5" California, 369970482 "YP708" Maryland), 1 (two
  MMSIs), 999999999 (two). No valid IMO was duplicated.
- 83% of these keys have no IMO and cannot be re-identified when their MMSI changes. For them MMSI-only
  is the only option — the strongest practical defence of the decision.

### 2.3 Over a hull's life (GFW identity panel)

892 IMO records after dedupe (the feed ships overlapping NO_MATCH groups; not deduping inflates period
counts ~15%). 858 hulls, 2,477 self-reported identity periods, 2012–2026, three regions.

- **604/858 hulls (70%) used more than one MMSI.** 1,619 handovers. Gap from the old key's last
  transmission to the new key's first: 0–20 min 613 (38%), 20 min–6 h 170, 6–24 h 40, 1–7 d 46, over 7 d
  157 (10%), negative/overlapping 533 (33%). The 533 are probably a GFW period-boundary artefact; confirm
  before quoting them. The 60 remaining handovers kept the same MMSI and changed name or flag — the
  merges a per-MMSI table absorbs silently.
- **997 name changes, 9 punctuation-only.** At identity-period level renames are real strings, matching
  the 3-in-9 punctuation share in the raw AISStream window. 1,374 flag changes are essentially the same
  events as MMSI changes (GFW derives flag from the MID prefix), so they are not independent evidence.
- **History concentration:** the median hull keeps 82% of its AIS history under one MMSI. But 104/858
  (12%) have their largest key under half, and 2 under a quarter. No hull had all keys under 30 days.

### 2.4 Sanctions matching

OpenSanctions `maritime.csv`, `type == "VESSEL"`: 20,989 rows, 1 with a bad IMO check digit. Danish day
fleet: 3,475 mobile vessels, 1,503 (43%) with an IMO.

| Join key | Matches | Share of the 76 found by either key |
|---|---|---|
| MMSI | 54 | 71% |
| IMO | 72 | 95% |
| Only IMO finds it | 22 | 29% |
| Only MMSI finds it | 4 | 5% |

This is the one hole visible today rather than only in history: a sanctions flag stored on an MMSI is
lost the moment the hull changes MMSI, which is 70% of hulls eventually and 10% within a week of silence.

### 2.5 False jumps on the map

The AIS "not available" sentinel (latitude 91) dominates naive teleport counts: a first pass without a
filter flagged 326 MMSIs (9.3%), almost all sentinel-to-real transitions at 40,000–90,000 knots. Excluding
22,374 sentinel positions and requiring 100+ knots, 5+ nm and 30 minutes or less: **27 of 3,497 MMSIs
(0.77%), 164 events**. Examples are decode errors (one flipped bit turns longitude 9.92 into 89.92) and
cross-border teleports — position quality, not identity. Filter the sentinel before judging a jump.

## 3. Change classification

| Change | Timescale | Likely causes | Rate, with denominator | Standard, noise or malicious? | Effect on tracking | Effect on prediction | Suggested handling | Evidence |
|---|---|---|---|---|---|---|---|---|
| MMSI change | minutes to days; 38% of handovers inside 20 min | sale, reflag, new owner or MID; sometimes deliberate | 604/858 hulls (70%) over a hull's history; 0/1,507 in one Danish day | mostly standard (sales, reflags) | splits one hull into two tracks; old key goes permanently silent | breaks per-key history and resets the hazard clock | IMO as side attribute; "new MMSI + same valid IMO" = continuation, not new ship | measured; SYNTHESIS; id-frequency |
| MMSI change after long silence | 10% of handovers follow 7+ days silent | sale completed outside coverage; identity swap | 157/1,619 (10%); 413/1,619 (26%) leave a gap of 20 min or more | cannot separate sale from evasion publicly | looks like vanished then new vessel | worst case for "went dark before": history resets when it matters | log as one event with two keys, "reappeared under new identity" | measured |
| Name change, same MMSI | days | rename after sale; correcting a typo | 7/3,497 in a day (0.2%); 9/24,553 in 12 min (0.04%); 997 period changes, 9 punctuation-only | standard | none while the key holds | slight drift if name is a feature | store name history, never key on it | measured |
| Call sign change, same MMSI | days | reflag, correction | 6/3,497 (0.17%); 5/24,553 (0.02%) | standard | none | low | log only | measured |
| Two hulls on one MMSI | any; rare | key collision, typo, shared handheld | 1/24,553 keys in 12 min (0.004%); 0/3,497 in a day; 20/3,497 show >1 size (0.57%) | noise at this rate | merges two hulls, invents teleports, distorts size/speed | label contamination if the key is the unit | log only; treat >20% size change or >20 nm teleport as a lead | measured |
| Shared/placeholder IMO | any | manual entry; deception at tanker level | 3 IMOs on 6 MMSIs in 12 min, all invalid values | noise for small craft; fraud for tankers (id-imo-fraud) | false merge if IMO is the key | corrupts any IMO-grouped split | reject 0 and failed check digits before grouping | measured; id-imo-fraud |

## 4. What this means for us, given MMSI-only

**Recommendation: add a small flag to the current design, and do not build identity-change detection.**
Concretely, keep MMSI as the key and add (a) a validated-IMO hull attribute and (b) one event label,
"reappeared under a new MMSI with a known IMO", used as a side note rather than a detector. Leave the
full change-detection study out of the build; if the team wants the pitch line, run it as a separate
study with an ownership check, not as a feature.

**Inside the 24-hour build, nothing measured here breaks.** One key per transmitter, names stable at
99.8% within a day, gaps not identity events, and no IMO-carrying Danish hull switched MMSI during
1 November. The demo will not produce a false identity event on a normal day.

**What it costs, in order of size:**

1. **History and training.** 70% of hulls change key at least once, so a per-MMSI track table turns them
   into several short ships. Median loss is small (82% retained) but 12% of hulls lose half or more.
   Split by hull (IMO), or the model learns identity boundaries as behaviour.
2. **Label leakage at handovers.** 413 of 1,619 handovers leave a detectible gap and 157 follow a week of
   silence, so a per-MMSI label set holds the same hull twice: "went silent" and "new vessel, no
   history". That is a false positive and a false negative for one hull at once, and it is exactly the
   pattern the pitch claims to detect. Evaluate by hull, not by key.
3. **Sanctions.** 29% of list matches need the IMO; a flag stored on an MMSI dies with the key.

**Small fixes that cover most of the harm**, none of which is identity-change detection:

- Keep `imo` on the static record (already in `VesselStatic`), add a hull view keyed on check-digit-valid
  IMO falling back to MMSI, and reject 0, 100000000 and failed check digits outright.
- When a new MMSI appears with an IMO seen in the last N days, emit "key change, same hull" instead of a
  second vessel. A lookup, not a detector.
- Copy sanctions and name history to the hull on handover.
- Drop sentinel positions before any speed or jump test, and group train/eval splits by hull.

**For the pitch.** "This hull disappeared and came back under a new radio identity" is supported: 10% of
handovers follow more than a week of silence, and the earlier wave found the same IMO under a new MMSI for
38 of 40 silent Danish tankers. What is not supported is calling any of it evasion: sales look identical.

## 5. Unknowns

- **Sale versus evasion is not separable here.** Ownership needs Equasis (login wall, per id-joins).
  Settle by hand-checking 20 handovers against public sale records.
- **The 533 overlapping handovers may be artefacts.** Compare one hull's raw AIS timeline against GFW's
  period boundaries.
- **The panel is sampled, not random** (silent tankers oversampled), so 70% is a lead, not a fleet rate;
  id-frequency owns that.
- **One Danish day, a 12.5-minute global window.** Repeat on 2026-10-31 to 2026-11-04 (zip pattern in the
  brief; 11-01 already downloaded). Registry and AIS disagree on names in ~17% of records.

## 6. Sources

- Danish day 2026-11-01: `$WAVE/data/t-match/aisdk-2026-11-01.zip`; gaps from
  `$WAVE/data/t-ais-history/day_2026-11-01/gaps.csv`.
- AISStream worldwide capture 19:07–19:20 UTC 7 Nov: `$WAVE/data/identity/aisstream-capture.jsonl` (still
  growing when sampled). GFW panel: `$WAVE/data/identity/gfw-identities.jsonl` (CC BY-NC 4.0).
  OpenSanctions: `$WAVE/data/t-ais-history/os/maritime.csv`, `type == "VESSEL"` (CC BY-NC 4.0).
- Rates were stable across three snapshots of the growing captures (4, 12 and 20 minutes; 38, 371 and 858
  hulls).
