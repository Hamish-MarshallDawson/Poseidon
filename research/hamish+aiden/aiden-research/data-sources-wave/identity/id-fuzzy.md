# id-fuzzy: typos versus real differences

Agent `id-fuzzy`. Started 19:07 UTC, first draft 19:14, this version 19:22 UTC.
Figures are `measured` by my scripts on the wave's shared data from one snapshot at 2026-11-07
19:16 UTC (`$WAVE/data/id-fuzzy/final_snapshot.txt`) unless labelled otherwise; the shared files were
still growing, so AISStream and GFW counts are snapshots. Scripts `$WAVE/scripts/id-fuzzy/`, outputs
and the 52 hand labels in `$WAVE/data/id-fuzzy/` (labels in `analyse6.py`).

Samples: AISStream capture, 49,043 messages, 21,798 MMSIs, 9,559 named, 15,447 name strings.
Global Fishing Watch, 631 IMO records -> 599 deduplicated AIS-vs-registry name pairs and 258
deduplicated consecutive-period MMSI changes. Danish AIS day 2026-11-01 raw CSV, 15,981,609 rows,
3,331 vessels with static fields (plus the 16:30-17:00Z Class A window, 1,527 MMSIs). MID table:
292 codes parsed from Wikipedia.

## 1. Bottom line

1. **Most "different names" are the same name written differently.** Of 599 deduplicated pairs where
   GFW holds both the AIS and a registry name for one MMSI, 83% are formatting: 25% spacing/case
   (GFW strips spaces: `BERGE BLANC`/`BERGEBLANC`), 55% punctuation, 2% Roman-vs-Arabic or `NO.`
   (`AL SOOR II`/`ALSOOR2`, `FS BITUMEN NO.2`/`FSBITUMEN2`), 1% an `MV`/`M/T` prefix. Five lines of
   normalisation remove three-quarters of it.
2. **Normalised equality is safe; similarity thresholds are not.** On 52 hand-labelled pairs:
   normalised equality gives precision 1.00, recall 0.55-0.62; Levenshtein ratio >= 0.85 gives recall
   0.69 at precision 0.62 (12 wrong merges in 52). The errors are systematic: test-transmitter names
   differing in a trailing number (`KEEP CLEAR 0.25NM 91` vs `...94`, `FISHFARM 92%` vs `96%`) and
   fleet names differing by a trailing token (`HAPPINESS` vs `HAPPINESS I`, `SEA FORTUNE` vs
   `SEA FORTUNE 1`).
3. **Names are not unique.** In one Danish day 94 normalised names appear on more than one MMSI,
   covering 218 of 3,331 named vessels (6.5%) - `MISSING` on 9 MMSIs, `FREJA`, `NEPTUN`, `ODIN` on 4
   each. Of 4,723 distinct-ship pairs sharing a four-letter name prefix, 178 (3.8%) exceed ratio 0.95,
   272 (5.8%) exceed 0.90, 429 (9.1%) exceed 0.85: the false-merge rate of any name-similarity join.
4. **A changed MMSI is usually a new national allocation, not a typo.** Of 258 deduplicated
   consecutive-period MMSI switches, 214 (83%) change the MID. Only 21 (8.1%) are within two digits;
   233 (90%) are four or more apart. 93 keep the same name, 25 (10%) the same name and flag.
5. **Free plausibility checks catch about 1 field in 30.** AISStream: IMO absent or zero on 4,452 of
   11,234 `ShipStaticData` messages (40%); 38 of 3,320 distinct IMO values (1.1%) fail the check digit
   and 81 (2.4%) are not seven digits (`879331600`, `1010363000`, `1000000000`, `3123456`); 21 of
   21,763 ship-range MMSIs (0.1%) use an unallocated country code; 26 MMSIs are not nine digits.

## 2. Findings

### 2.1 What the strings contain

- Names arrive space-padded to 20 characters (`"CL GANJIANG         "`, call sign `"VRVV9  "`); Class
  B names carry double spaces (`"S.V.  SABARTE"`).
- The AIS 6-bit character set leaves glyph artefacts. Four of 9,559 named MMSIs (0.04%) sent two
  different static names inside 30 minutes, and all four are formatting, not renames:
  `LOCA LOLA 2`/`LOCA LOLA II`, `MIP- 3`/`MIP-3`, `RUEY I SHYANG NO.106`/`RUEY ISHYANG NO.106`,
  `LISTA@@@@N\*`/`LISTA` (padding decoded into the name). GFW shows the same over years: IMO 9421415
  appears as `,NDI IPSA` and then `BINDI IPSA`, a leading letter rendered as a comma.
- GFW's registry names are already space-stripped, so raw comparison against AIS manufactures
  differences. That is the largest single "name change" signal in free data and it is the
  aggregator's artefact.
- AISStream `MetaData.ShipName` is a cache of the last static message, not a second observation: for
  9,559 MMSIs carrying both, names differed in 2 cases (0.02%): `244000460` metadata `THE VIKING`
  then static `SILVER GHOST`, `244030275` `ALELOTTE` then `PIACERE` (Dutch inland craft, same position
  each time). It lags; it is not a cross-check.
- Class B `StaticDataReport` splits name (Part A) from call sign/type/dimensions (Part B), and Part B
  often arrives with `Valid: false` and empty fields, so a complete Class B record needs two messages.
- 163 of 15,447 capture names (1.1%) and 74 of 3,357 Danish names (2.2%) are exactly 20 characters,
  i.e. at the cut. Comparing more than 20 characters is meaningless. GFW cannot measure this: its
  registry names are pre-squashed and never exceed 20 characters, so the test needs a real registry.

### 2.2 Classification, and where the signal is actually lost

599 deduplicated same-MMSI AIS-vs-registry pairs: spacing/case 150 (25%), punctuation 330 (55%),
Roman/`NO.` 11 (2%), prefix token 4 (1%), typo 12 (2%), real difference 92 (15%). Normalisation
ladder: raw 75% still differ, after stripping non-alphanumerics 20%, after Roman/`NO.` 18%.

Danish whole day: only 10 of 3,331 vessels show more than one name in 24 hours (67 pairs), 64 of them
number changes by moving test/buoy transmitters (`KEEP CLEAR 0.25NM 91` -> `...94`, `FISHFARM 92%` ->
`96%`, `END OF TOW 90%` -> `92%`). No Danish vessel carried two IMOs in a day (0 of 1,507), 7 changed
call sign, 22 changed dimensions. The 30-minute Danish window shows no name variation in 1,527
MMSIs. So short-term name instability is rare and almost always a transmitter label, not a rename.

### 2.3 Precision and recall on 52 hand-checked pairs

Sample: 29 cosmetic, 22 substantive, 1 ambiguous (only cosmetic pairs should match).

| Rule | Merged | TP | FP | FN | Precision | Recall |
|---|---|---|---|---|---|---|
| normalised (alphanumeric-only) equality | 16 | 16 | 0 | 13 | 1.00 | 0.55 |
| + Roman/`NO.` rule | 18 | 18 | 0 | 11 | 1.00 | 0.62 |
| Levenshtein ratio >= 0.85 | 32 | 20 | 12 | 9 | 0.62 | 0.69 |
| Levenshtein ratio >= 0.90 | 29 | 17 | 12 | 12 | 0.59 | 0.59 |

Seven points of recall cost 38 points of precision. My own taxonomy agreed with the hand labels on
35 of 52 pairs (67%); every disagreement was a buoy-number change called "typo" (11) or a
Roman/`Ø`/OCR difference called "real" (5). `KEEP CLEAR 0.25NM 91` vs `...94` and `EAGLE SYDNEY` vs
`EAELE QYDNEY` are similar distances apart and opposite in meaning; the data does not say which.

### 2.4 IMO problems

| Sample | IMO values | zero/absent | bad check digit | not 7 digits |
|---|---|---|---|---|
| AISStream, `ShipStaticData` messages | 11,234 msgs | 4,452 (40%) | - | - |
| AISStream, distinct values | 3,320 | 0 recorded as zero | 38 (1.1%) | 81 (2.4%) |
| Danish day, per vessel | 1,507 | 0 | 2 (0.1%) | 15 (1.0%) |
| GFW, self-reported periods | 1,815 | 53 | 0 | 0 |

The two Danish failures are placeholders: `2222222` (MMSI 219033078) and `1048576` (MMSI 220076700,
exactly 2^20). No Danish vessel has both a bad and a good IMO, so nothing is repairable by matching.
Only one bad-check IMO in the capture is one digit from a valid IMO claimed elsewhere in the same
capture (`9903595` vs `9903592`), and two Antarctic fishing hulls are more plausible than a typo. So
**a failed check digit is not repairable by fuzzy matching**: the digit exists to expose single-digit
errors, and what the data holds is junk, not slips. The dropped-digit mechanism shows up on the MMSI
instead: IMO 9373644 has one period with the 8-digit `ssvid` `24924600` and the next with
`249246000`, same name PATANI, two days apart.

### 2.5 MMSI validity, and whether a changed MMSI can be fuzzy-matched

21,763 ship-range MMSIs: 21 (0.1%) use an unallocated country code; 26 of 21,798 MMSIs (0.12%) are
not nine digits. Unallocated prefixes seen: `200, 222, 223, 260, 299, 302, 386, 500, 524, 583, 712,
724, 741, 799, 825, 887`. A bad MID is a data-quality flag, not a lead: a mis-keyed transponder looks
the same.

Across 258 deduplicated consecutive-period MMSI switches: MID changed 214 (83%); flag unchanged 47
(18%); same name 93 (36%); same name and flag 25 (10%); edit distance 1 or 2 in 21 cases (8.1%); four
or more in 233 (90%). The close ones are the only ones a fuzzy matcher could act on, and they split
three ways:

- Likely typo or duplicate record: IMO 9421415, `636017318` -> `636017378`, `ARSAN` both sides,
  Liberia both sides, 11 hours apart; IMO 9593517, `537985027` -> `537985026`, `,NDI IPSA` ->
  `BINDI IPSA`; IMO 9373644, `24924600` -> `249246000`.
- Same hull, two numbers in parallel: IMO 9377781 under `636013336` and `636013335` in both
  directions, with names `HAMPSHIRE` and `BW BROKER`. Proximity gets this right; the name misleads.
- Close but a real reallocation: IMO 9212905, `677026400` -> `677000400`, `M.V. KESHAN` ->
  `HAPPINESS`, ten months apart.

So a same-MID, one-or-two-digit MMSI change with an unchanged normalised name and a short gap is a
**lead** that a transponder was mis-keyed, never a merge. The MID must be part of the test: a change
of MID is a new allocation 83% of the time.

## 3. Change classification

| Change | Timescale | Likely causes | Rate, with denominator | Standard, noise or malicious | Effect on tracking | Effect on prediction | Suggested handling | Evidence |
|---|---|---|---|---|---|---|---|---|
| Name, cosmetic | every message | padding, GFW squashing, 6-bit charset | 495/599 pairs (83%) | Noise | none | none if normalised | normalise, never flag | measured |
| Name, truncation at 20 | until rename | AIS field limit | 163/15,447 (1.1%) capture, 74/3,357 (2.2%) Danish | Noise | none | none | compare 20-char prefixes | measured |
| Name, real rename | months to years | sale, rebrand, operator prefix | 92/599 (15%) | Standard, and an ordinary way to obscure history | track looks new | history resets, "clean" score | store with IMO, flag only with timing | measured |
| Name, typo-class | hours to years | dropped token, transposition | 12/599 (2%) | Ambiguous, undecidable from AIS | none | none | candidate list only | measured |
| Name, buoy/test transmitter | within hours | operator relabels unit | 64/67 Danish same-MMSI pairs | Noise | one MMSI, many names | none | filter by name pattern | measured |
| Name, two names in 30 min | minutes | encoder inconsistency, shared MMSI | 4/9,559 named MMSIs (0.04%) | Noise | momentary duplicate label | none | keep latest static | measured |
| MMSI, new MID | minutes to days | reflag, new allocation | 214/258 (83%) | Standard | new track unless IMO joins | history split | join on IMO | measured |
| MMSI, same-MID close | hours to years | mis-key, duplicate record, two transponders | 21/258 (8.1%) | Mostly noise, occasionally deliberate | duplicate tracks | duplicate training rows | lead only (same MID + name + short gap) | measured |
| IMO absent (0) | persistent | Class B has no IMO field, Class A blank | 4,452/11,234 messages (40%) | Noise | none | no IMO features | never treat as a change | measured |
| IMO bad digit / not 7 digits | persistent | placeholders, pasted numbers | 38/3,320 (1.1%), 81 (2.4%); 2 and 15 of 1,507 Danish | Mostly noise | can't join registry | wrong joins if unvalidated | drop for joins, keep raw | measured |
| MMSI unallocated MID | persistent | mis-key, stale table | 21/21,763 (0.1%) | Weak lead | still tracks | quality flag | log only | measured |

## 4. What this means given MMSI-only

- **Name handling is normalisation, not detection.** Upper-case, strip non-alphanumerics, cut to 20,
  map Roman numerals, drop `NO.` removes three-quarters of cross-source disagreement, and normalised
  equality never merged two distinct names in my sample. Without it `VesselView.name` flips between
  `BERGE BLANC` and `BERGEBLANC` by source; with it, "name changed" becomes rare and meaningful.
- **Nothing here supports fuzzy ship matching.** Typo-class pairs are 2% and undecidable, the
  false-merge rate on real distinct ships is 4-9%, and the vocabulary recycles (`... 1`, `... II`,
  `MISSING`). A pitch claiming identity resolution meets this number.
- **MMSI-only is mostly fine for 24 hours; the gap is history.** 83% of MMSI changes come with a new
  MID, i.e. a reflag: the build shows a new ship, right on the map and wrong in history. Cheap
  mitigation: keep the self-reported IMO in `VesselStatic` (already a field), compare normalised names
  at 20 characters, and render "same IMO, new MMSI" as a note pointing at the track that went quiet.
  That is one lookup, not identity-change detection.
- **Free quality gates, all booleans:** IMO check digit; IMO seven digits; MMSI nine digits; MMSI MID
  in the ITU table; normalised 20-character name; a recorded same-MID-close-MMSI lead.
  `VesselStatic.q` already has `imo_bad_checksum`, which is the right home.
- **Judge-facing wording:** not "we detect identity fraud", but "identity noise is measurable and
  cheap to normalise, and what remains is a data problem, not a detector". That survives someone who
  knows AIS.

## 5. Unknowns

- **Typo vs genuine reallocation** of a near-identical MMSI cannot be settled from AIS; it needs the
  allocation record (ITU MARS ShipStation or the flag register), both browser-only or login-walled per
  `id-joins`.
- **Flicker rate over a full day** is only partly covered: 4 cases in 9,559 MMSIs in 30 minutes
  worldwide, 10 vessels in 3,331 in a Danish day. A per-30-minute sweep over the Danish day (already
  downloaded) would settle it; `id-shortterm` has the per-message timing.
- **Charset artefacts** need the raw 6-bit field; the decoded name is lossy (`LISTA@@@@N\*`).
- **Truncation against a real registry** needs one feed with long names.
- **GFW duplicate identity groups** inflate pair counts by roughly 15% (flag from `id-frequency`); I
  deduplicated by (MMSI, name, flag, call sign) per record, but a canonical panel would be cleaner.
- **Ownership** is out of reach: whether a rename followed a sale needs Equasis or a register, and
  that needs a login.

## 6. Sources

- AISStream worldwide capture, ~30 min, received by the orchestrator 2026-11-07
  (`$WAVE/data/identity/aisstream-capture.jsonl`).
- Global Fishing Watch vessel identity API, CC BY-NC 4.0, fetched by the orchestrator 2026-11-07
  (`$WAVE/data/identity/gfw-identities.jsonl`).
- Danish Maritime Authority AIS day 2026-11-01, `http://aisdata.ais.dk/aisdk-2026-11-01.zip`,
  downloaded once by the team (`$WAVE/data/t-match/aisdk-2026-11-01.zip`).
- MID table: Wikipedia, "Maritime identification digits",
  `https://en.wikipedia.org/wiki/Maritime_identification_digits`, fetched 2026-11-07, 292 codes
  (`$WAVE/data/id-fuzzy/mid_wikipedia.json`). The ITU M.585 list is the authority; re-check
  unallocated prefixes against ITU before any flag rule.
- IMO check digit: weights 7,6,5,4,3,2 on the first six digits, sum mod 10.
- The 52 hand labels are in `analyse6.py` (`LABELS`) so anyone can re-check them.
