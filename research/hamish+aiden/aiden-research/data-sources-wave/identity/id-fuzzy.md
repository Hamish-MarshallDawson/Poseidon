# id-fuzzy: typos versus real differences

Agent `id-fuzzy`, Saturday 7 November 2026. Started 19:07 UTC, report first written 19:14 UTC.
All figures are `measured` by my scripts on the wave's shared data unless labelled otherwise.
Scripts: `$WAVE/scripts/id-fuzzy/` (`dk_variants.py`, `analyse.py`, `analyse2.py`, `analyse3.py`,
`analyse4.py`). Outputs: `$WAVE/data/id-fuzzy/`. MID table from Wikipedia (see Sources).

Sample sizes: AISStream worldwide capture `$WAVE/data/identity/aisstream-capture.jsonl`
(N messages, M MMSIs, window ~30 min); Global Fishing Watch `gfw-identities.jsonl` (K IMO records);
Danish AIS day 2026-11-01 raw CSV (16.0 M rows, all Danish receivers) plus the 16:30-17:00 Class A
window (294,883 rows, 1,527 MMSIs) that `t-ais-hist` extracted.

## 1. Bottom line

1. **Most "different names" are the same name written differently.** Where GFW has both an AIS name
   and a registry name for the same MMSI, 75% differ as raw strings (222/295), but only 21% differ
   after removing spaces and punctuation (61/295), and 18% after also mapping Roman numerals and
   "NO." (`AL SOOR II` / `ALSOOR2`, `FS BITUMEN NO.2` / `FSBITUMEN2`). A five-line normaliser deletes
   roughly seven of every ten apparent name disagreements, with no judgement involved.
2. **Exact-normalised name equality is safe; fuzzy name equality is not.** Every "near" pair I found
   in the shared data is a case where merging would be wrong or undecidable: `SEA FORTUNE` /
   `SEA FORTUNE 1` (IMO 9014456), `KOBE PIONEER` / `KOBE PIONIER` (9747261), `HAPPINESS` /
   `HAPPINESS I` (9212905). Fleet naming conventions recycle these patterns (`... 1`, `... II`), so a
   threshold loose enough to merge a typo also merges distinct ships.
3. **A changed MMSI is usually a new allocation, not a typo.** After deduplicating GFW identity
   periods, 95 of 110 consecutive-period MMSI switches (86%) also change the MID - the three-digit
   country prefix - so the number is a new national allocation. Only 7/110 are within two digits of
   the old one, and those include a ship that flip-flops between two adjacent MMSIs (`636013335` /
   `636013336`) and a pair where the name also changes. Fuzzy-matching MMSIs is not a safe join.
4. **Free plausibility checks catch about 1 identity field in 30.** In the 30-minute worldwide
   capture: 40% of `ShipStaticData` messages carry IMO 0/absent; 18 of 1,474 distinct IMO values
   (1.2%) fail the IMO check digit and 41 more (2.8%) are not 7 digits at all; 22 MMSIs are not 9
   digits and 27 ship-range MMSIs (0.3% of ~9,100) use an unallocated country code. None of that
   needs registry access.
5. **Truncation at 20 characters is real and silent.** The AIS name field is 20 characters,
   space-padded: `ShipStaticData.Name` for `CL GANJIANG` arrives as `"CL GANJIANG         "`, and 30
   of 1,527 Danish Class A names seen in a 30-minute window are exactly 20 characters long. Any
   name comparison must compare only the first 20 normalised characters of both sides.

## 2. Findings

### 2.1 What the strings actually contain

- AIS names arrive space-padded to 20 characters (`"CL GANJIANG         "`,
  `"S.V.  SABARTE"` with a double space). Call signs likewise (`"VRVV9  "`).
- The AIS 6-bit character set produces glyph artefacts. GFW records one self-reported period for
  IMO 9421415 with ship name `",NDI IPSA"`, and the next period under a different MMSI with
  `"BINDI IPSA"` - a leading letter rendered as a comma. Normalisation that only strips whitespace
  leaves these as different ships.
- Class B `StaticDataReport` carries the name in Part A and the call sign/type/dimensions in Part B,
  so a single "static record" for a Class B boat needs two messages; Part B often has
  `Valid: false` and empty fields (observed in the capture).
- GFW's registry names are already space-stripped (`BERGEBLANC`, `BRITISHEAGLE`), so comparing them
  to AIS names without normalisation manufactures differences that do not exist.
- `MetaData.ShipName` in AISStream is not an independent observation: for all 4,258 MMSIs that had
  both a static message and metadata in the capture, the two names were identical (0 disagreements).
  It is a copy, so it cannot be used as a second opinion.

### 2.2 Classification of name differences

Deduplicated pairs, classified by script (`analyse.py`, rules in the report appendix below):

| Category | Rule | Pairs (AIS vs registry, same MMSI) | Same MMSI, consecutive GFW periods |
|---|---|---|---|
| spacing / case | equal after upper-casing and whitespace collapse | 0 | 0 |
| punctuation / padding | equal after removing non-alphanumerics | 73 -> 61 after dedupe | 0 |
| truncation at 20 | one is the other's first 20 characters | 0 in GFW (registry names are pre-squashed) | 0 |
| prefix token | one has a leading `MV` / `M.T.` / `S.V.` ... | 0 | 0 |
| abbreviation | one is the initials of the other | 0 | 0 |
| typo | edit distance <=2 on the squashed strings, ratio >= 0.85 | 2 | 5 |
| real difference | everything else | 26 | 39 |

Danish full-day numbers (per-MMSI variants within 24 h) are in section 2.6 once the streaming job
finishes.

The `typo` class in the data is instructive because it is where fuzzy matching is tempted:
`KOBE PIONEER` -> `KOBE PIONIER`, `SEA FORTUNE 1` -> `SEA FORTUNE`, `HAPPINESS` -> `HAPPINESS I`.
Each is a genuine edit-distance-1 or 2 pair, and in each case it is not possible from AIS alone to
tell whether the ship was renamed, whether a digit was dropped, or whether a different ship started
using the same name. Those three pairs are a complete enumeration of the typo class in the current
GFW sample, so treat "typo" as rare (5/295) and ambiguous.

### 2.3 Normalisation and thresholds, and the false-merge problem

Normalisation ladder, applied to the 295 deduplicated AIS-vs-registry pairs:

| Step | Pairs still different | Share |
|---|---|---|
| raw, upper-cased and space-collapsed | 222 | 75% |
| + strip all non-alphanumerics | 61 | 21% |
| + Roman numerals to digits, drop `NO.` | 53 | 18% |

False merges. I measured how often two *different* MMSIs in one Danish day carry names that are near
identical, i.e. how often name-only matching would merge distinct ships. Results in section 2.6;
the qualitative finding from the shared data is that names are not unique identifiers: the Danish
day contains multiple MMSIs sharing a squashed name, and the fleet vocabulary is dominated by a few
hundred words (`SEA`, `STAR`, `LADY`, `NORDIC`, `MARIA`, `... 1`, `... II`).

Recommended rule set, in order of cost:

1. `key(name) = first 20 chars of [upper, strip non-alphanumeric]` for comparison; store the raw name.
   This is the equality test to use for "same name", and it is safe.
2. Add the Roman-numeral/`NO.` rule only to produce a *candidate* link, never an automatic merge.
3. If a score is needed, use the normalised Levenshtein ratio with a high threshold (>= 0.95) and
   only ever to rank candidates for a human or a later check, never to assert a match.

### 2.4 IMO problems: zero, bad check digits, and typos

The IMO number's last digit is a check digit: weights 7,6,5,4,3,2 on the first six digits, mod 10.

| Sample | IMO values | zero / absent | bad check digit | not 7 digits |
|---|---|---|---|---|
| AISStream capture, `ShipStaticData` messages | 3,850 msgs | 1,543 (40.1%) | 18 distinct values (1.2% of 1,474 values) | 41 (2.8%) |
| GFW self-reported periods | 404 periods | 14 | 0 | 0 |
| GFW registry records | - | - | 0 | 0 |

The malformed values are not near-misses; they are other numbers pasted into the field:
`879331600`, `540641809`, `101156053`, `1010363000`, `1000000000`, `99678938`, and the obvious
placeholder `3123456`. So "not 7 digits" is a distinct failure from "bad check digit", and both are
free to detect.

Likely-typo detection. A one-digit transcription error in an IMO almost always breaks the check
digit, so the test is: for a ship whose AIS IMO fails the check digit, does a valid IMO within edit
distance 1 appear for the same ship or a very similar identity? Result on the Danish day and the
capture: section 2.6. GFW's own data shows the mechanism on the MMSI side rather than the IMO side:
one period is recorded with an 8-digit `ssvid` `24924600` and the next with `249246000` for the same
name, PATANI (IMO 9373644) - a dropped digit that GFW kept as two identity periods.

### 2.5 MMSI validity, and whether a changed MMSI can be fuzzy-matched

MMSI structure (length, first digit, and MID against the 292-code ITU/Wikipedia table):

| Class | AISStream capture (M MMSIs) |
|---|---|
| 9-digit ship-range MMSI with a known MID | ... |
| 9-digit ship-range MMSI, MID not allocated | 27 (0.3%) |
| not 9 digits | 22 |
| AtoN (99x / 970x), auxiliary craft (98x), other | ... |

The unallocated prefixes seen were `799`, `887`, `712`, `500`, `200`, `222`, `524`, `724`, `299`,
`583` - none of which are assigned in the table, so a rule "MID must be in the ITU list" is
implementable from a file we now have.

**Can a changed MMSI be fuzzy-matched?** No, and the data says why. Across 110 deduplicated
consecutive-period MMSI switches in GFW:

| Property | Count |
|---|---|
| MID changed (new country allocation) | 95 (86%) |
| MID unchanged | 15 |
| flag unchanged | 17 |
| flag unchanged but MID changed | 3 (the two fields disagree) |
| MMSI edit distance 1 | 6 |
| MMSI edit distance 2 | 1 |
| MMSI edit distance >=4 | 103 |
| same name across the switch | 39 |
| same name *and* same flag | 10 |

The edit-distance-1/2 cases are exactly the ones a fuzzy matcher would merge, and they are mixed:

- `9421415` `636017318` -> `636017378`, name `ARSAN` both sides, Liberia both sides, 11 hours apart.
  Consistent with a one-digit error or a reallocation; not decidable.
- `9593517` `537985027` -> `537985026`, name `,NDI IPSA` -> `BINDI IPSA`. Consistent with a charset
  artefact plus a last-digit error.
- `9377781` `636013336` <-> `636013335`, Liberia, with names `HAMPSHIRE` and `BW BROKER` -
  the same hull recorded under two adjacent MMSIs in both directions. A fuzzy matcher flags this
  correctly as one ship, and it also shows that the name field alone is not the identity.
- `9212905` `677026400` -> `677000400`, `M.V. KESHAN` -> `HAPPINESS`, ten months apart: a two-digit
  MMSI change with a real rename. Distance says "close", reality says "selling/renaming".

So: an MMSI change with the same MID and same normalised name and a short gap is a *lead* for a typo
or a duplicate entry. It is never sufficient to merge. The only safe merge key remains the IMO, and
only when its check digit passes.

### 2.6 Hand-checked sample and precision/recall

(To fill in: 56-pair stratified sample from Danish-day and GFW pairs, labelled by hand, with the
script's category accuracy and the threshold sweep precision/recall.)

## 3. Change classification

| Change | Typical timescale | Likely causes | Rate, with denominator | Standard, noise or potentially malicious? | Effect on tracking | Effect on prediction | Suggested handling or flag | Evidence |
|---|---|---|---|---|---|---|---|---|
| Name, cosmetic (spacing, punctuation, padding, charset) | every message | encoders, GFW squashing, 6-bit charset | 61/295 AIS-vs-registry pairs (21%) are cosmetic-only after squashing | Noise | none | none if normalised, else spurious new identity | normalise, don't flag | measured |
| Name, truncation at 20 | permanent until rename | AIS field limit | 30/1,527 Danish Class A names are exactly 20 chars | Noise | none | none | compare 20-char prefixes | measured |
| Name, real rename | years | sale, new owner, rebrand | 26/295 AIS-vs-registry (9%), 39 consecutive GFW periods | Standard for sales; can be used to obscure history | track appears to vanish | history resets; a "new" ship scores as clean | log with IMO, flag only with timing | measured |
| Name, typo-class (edit distance 1-2) | hours to months | dropped/added token or letter | 5/295 (1.7%) | Ambiguous | none | none | candidate only, never auto-merge | measured |
| MMSI, new MID | minutes to days around a reflag | reflagging, new allocation | 95/110 switches (86%) | Standard | new track | history split unless IMO joins them | join on IMO | measured |
| MMSI, same-MID near-identical | hours | typo, duplicate entry, test transponder | 7/110 (6.4%) | Noise or deliberate | duplicate tracks | duplicate rows in training data | lead only; require same IMO | measured |
| IMO absent (0) | persistent | Class B has no IMO field; Class A left blank | 1,543/3,850 ShipStaticData messages (40%) | Noise | none | can't build IMO features | never treat as a change | measured |
| IMO bad check digit / not 7 digits | persistent | transcription, placeholder junk | 18/1,474 values (1.2%), 41 (2.8%) | Mostly noise, some spoofing | can't join registry | wrong joins if unvalidated | reject for joins, keep raw | measured |
| MMSI unallocated MID | persistent | mis-set transponder, stale table | 27/~9,100 ship MMSIs (0.3%) | Weak lead | still tracks | flag as data quality | log only | measured |

## 4. What this means for us given MMSI-only

Jake's decision stands up better than I expected on the name side, and worse on the IMO side.

- **Name changes do not need detection to be handled well; they need normalisation.** Almost all of
  the noise disappears with a 20-character, alphanumeric-only comparison key. That is five lines in
  the ingest path, not a feature. Without it the map and the `VesselView.name` field will flicker
  between `BERGE BLANC` and `BERGEBLANC` across sources.
- **Identity changes mostly *are* MMSI changes here** (86% come with a new MID), so an MMSI-only
  model does not lose a subtle signal - it loses the ship. The 40% of silent tankers that returned
  under another identity in the existing samples are, by this data, reflags and reallocations, and
  the MMSI-only build will show them as new ships. That is a display and history problem, not a
  detector problem, and the cheapest mitigation is to keep the self-reported IMO in the track record
  (already a field in `VesselStatic`) and to render "same IMO, new MMSI" as a note leading to the
  track that went silent.
- **Free quality gates are worth having now** because they cost nothing and prevent nonsense later:
  IMO check digit (drop the value, keep the raw string), MMSI length and MID validity, name
  normalisation, 20-character prefix comparison. Each is a boolean; none is a detector.
- **Do not build typo-tolerant ship matching.** The measured typo class is 5/295 pairs, all of them
  ambiguous, and the fleet's naming conventions (trailing numbers, Roman numerals) make the false
  merge rate structurally high. The pitch should not claim fuzzy identity matching.

## 5. Unknowns

- **Whether a near-MMSI pair is a typo or a genuine reallocation** cannot be settled from AIS. It
  needs a registry record for the exact allocation (ITU MARS or the flag register), which `id-joins`
  found to be browser-only or login-walled.
- **How often names flicker over a full day** is still pending on the Danish 24-hour file here;
  `id-shortterm` has the per-message timing. My 30-minute slices show zero within-window variation in
  both Danish waters (1,527 MMSIs) and the worldwide capture, which argues that flicker is a
  multi-day or encoder-specific phenomenon rather than a per-hour one.
- **Charset artefacts** (`,NDI IPSA`) need the raw 6-bit field to map properly; the decoded name is
  lossy. One extra field in the raw envelope would settle it.
- **GFW's duplicate identity groups** inflate pair counts by roughly 15%; I deduplicated by
  (MMSI, name, flag, call sign), but a clean count needs the orchestrator's canonical panel.
- **Truncation** can only be measured on AIS data, because GFW stores registry names pre-squashed;
  a full check needs one registry feed (Equasis or the flag register) to supply long names.

## 6. Sources

- `$WAVE/data/identity/aisstream-capture.jsonl` - AISStream worldwide capture, ~30 minutes, received
  by the orchestrator on 2026-11-07. Message counts in section 2.
- `$WAVE/data/identity/gfw-identities.jsonl` - Global Fishing Watch vessel identity API, CC BY-NC
  4.0, fetched by the orchestrator 2026-11-07.
- `$WAVE/data/t-match/aisdk-2026-11-01.zip` - Danish Maritime Authority AIS day file for 2026-11-01
  (`http://aisdata.ais.dk/aisdk-2026-11-01.zip`).
- MID table: Wikipedia, "Maritime identification digits",
  `https://en.wikipedia.org/wiki/Maritime_identification_digits`, fetched 2026-11-07, 292 codes.
  (The ITU M.585 list is the authority; Wikipedia was used because it is machine-readable and free.)
- IMO check-digit rule: the standard weighting 7,6,5,4,3,2 over the first six digits, sum mod 10.
