# Fake and bogus IMO numbers (track: id-imo-fraud)

Agent `id-imo-fraud`, identity wave, Saturday 7 November 2026. Measurements UTC, 19:07-19:16. Ships are leads unless a published source names them. `measured` = I ran it on the shared data, with a denominator; `press`, `vendor claim`, `documented` = someone else's number.

## 1. Bottom line

1. **Published counts, with denominators, are small but rising fast.** Lloyd's List: **28** vessels transmitting IMO numbers of scrapped ships as of 3 Feb 2025 (`press`, public PDF, [daily 2025-02-03](https://www.lloydslist.com/-/media/lloyds-list/daily-pdf/2025/02-february/dailypdf030225.pdf)); **46** scrapped-ship IMOs in active use in Dec 2025 against **19** a year earlier (9 Dec 2025, abstract). Vortexa: "more than 60" (`vendor claim`, 10 Dec 2025). Windward: **49 zombie tankers of 1,358 shadow-fleet tankers = 3.6%**, Aug 2026 period (`vendor claim`, [windward.ai](https://windward.ai/maritime-intelligence-operations-center/insights-shadow-fleet/)). That is 3-4% of the illicit tanker fleet, roughly doubling yearly: a compliance story, not a property of world AIS.
2. **Free data reproduces 6 of the 7 published cases, but only if you read every identity group GFW returns per IMO.** `measured`. IMO 9177686 shows the real *New Discovery* ending 2018-10-30, then *Lavin* on Mali MMSI 649111000 (Sep-Oct 2025), then *Lavine* on a Comoros MMSI — matching the Lloyd's List account of *Macho Queen*. IMO 9292993 shows *Skyrill* (Guyana, then Tanzania) from Oct 2024, matching *Frunze*. The seventh, *Macho Queen*'s own IMO 9238868, shows no impersonation — as expected.
3. **Check digits catch typos, not fraud.** Both published fake IMOs pass the mod-10 rule (`1095337` is invented; `1123081` is real, belonging to a ship under construction). `measured`: 107 of 3,136 IMO values (3.4%) in a worldwide AIS capture fail, nearly all placeholders or field corruption (`100000000`, 9- and 10-digit values), not impersonation.
4. **The obvious retrospective rule does not discriminate.** "IMO still transmitting after its last registry record" fires on **469 of 479** GFW ships with a registry record (98%), median lag 399 days, 50% beyond a year. GFW registry snapshots are too stale for a status test; only a *definitive* status (scrapped, never built, not in the register) makes it sharp.
5. **What is worth 20 lines of code:** strip and validate IMO before any join; treat `1234567`, `100000000` and 7-digit-with-trailing-zeros as null; keep `(mmsi, imo, name, flag)` per static message instead of upserting. Everything else here needs a registry and belongs in a pitch study, not the build.

## 2. Findings

### 2.1 What the scheme guarantees, and why it enables all of this

`documented` ([IMO identification number schemes](https://www.imo.org/en/OurWork/MSAS/Pages/IMO-identification-number-scheme.aspx), Circular letter 1886/Rev.5): assigned by IHS Maritime/S&P Global at keel laying, seven digits, "never reassigned to another ship", mandatory since 1 Jan 1996 for cargo ships of 300 GT+ and passenger ships of 100 GT+, voluntary for fishing vessels of 100 GT+ since 2013, and meant to survive changes of owner and flag.

Two consequences drive everything below. A number exists **before** the hull (assigned at keel laying/contract), so numbers of hulls not yet delivered, or never delivered, look valid and stay silent. A number **outlives** the hull, so a scrapped ship's number is a permanently clean identity attached to nobody. Crew also type it in: Lloyd's List reports IMO entry is often password-only (JRC default "0000") and that transponders from scrapped ships are sometimes reused without clearing old data — a benign explanation to rule out first. The IMO's NCSR subcommittee has been considering AIS integrity measures, with VDES expected to help (`documented` via the same article).

### 2.2 The check-digit battery, measured

`measured`. Worldwide AISStream capture, 19:07:31-19:15:45 UTC (8 minutes): 10,718 MMSIs, 6,218 static messages, 3,136 distinct IMO values.

| Test | Result | Denominator |
|---|---|---|
| IMO value fails check digit | 107 (3.4%) | 3,136 values |
| Messages carrying a failing IMO | 149 (2.4%) | 6,218 messages |
| Failures that are not 7 digits (8, 9 or 10) | 63 | 107 failures |
| 7-digit failures with exactly one single-edit repair | 0 | 44 |
| 7-digit failures with several possible repairs | 44 (100%) | 44 |
| Non-9-digit MMSI | 13 (0.12%) | 10,718 MMSIs |
| IMO on >1 MMSI (raw) | 2 | 3,136 values |
| ...after excluding junk IMOs (`100000000`, `1`) | 0 | 3,136 values |
| MMSI with >1 name | 1 (0.01%) | 10,718 MMSIs |

Two negatives worth keeping. **Most failures are not a mistyped real number**: `100000000`, `1000000000`, `1010363000`, `0630414`, `1`, round values. **You cannot reconstruct a mistyped IMO from the check digit**: every 7-digit failure had several one-edit repairs that pass the rule (substituting the check digit always does), so "repair then join" invents identities. The two IMO-on-two-MMSI hits were junk (`100000000`, `1`), and the single multi-name MMSI was spacing (`RUEY I SHYANG` / `RUEY ISHYANG`).

A full Danish day (`aisdk-2026-11-01`, 15.98 M rows, 3,331 MMSIs, 1,492 IMOs) agrees: **0 MMSIs with two IMOs, 0 IMOs on two MMSIs**, only 2 bad check digits (`2222222`, `1048576`) and 10 multi-name MMSIs — all buoys, AtoN labels with percentage suffixes (`FISHFARM 97%`), a test string, and one 6-bit charset artefact (`LANGELANDC]6`). `id-flags` adds: of 17 non-conforming IMO values that day, 11 were a valid 7-digit IMO with extra characters, mostly two trailing zeros.

Placeholders matter for joins, not fraud: `id-causes` measured `1234567` (which *passes* the check digit) on 25 MMSIs and 27 names.

### 2.3 Documented patterns, and which signals we could compute

**Zombie (scrapped hull).** Signals the analysts use: an IMO whose registry status is broken up reappearing in AIS; a name in no register (`Quasar`); an MMSI GISIS does not recognise (18 of Lloyd's List's 28); a flag claim GISIS calls false (*Birth Young*, *Brave M* under Guyana). Named cases, as leads, `press`: *Macho Queen* → *Lavin* (IMO 9177686, Mali then Comoros MMSI, one simultaneously used by another tanker); *Panda* → *Birth Young* (IMO 9233313, then 9259173); *Koen* → *Rada* (9213301); *Jaya* → scrapped *Assos* (9233791), TankerTrackers then counting "more than 50 tankers using fake identities"; *Freesia I* in Venezuela.

**Newbuild (under construction).** Sanctioned *Frunze* transmitting IMO `1123081`, belonging to an aframax under construction at Wanlong, as *Cordula* with a Tanzania MID (`press`, 26 Jan 2026). Vortexa's Claire Jungman: such a number "is not expected to transmit AIS or appear in operational databases, which reduces the chance of immediate detection".

**Invented and hijacked numbers.** `1095337` (absent from GISIS) used by *Tia* as *Arcusat*; and `1107697`, a Chinese tug's number, used by *Izumo* as *Tiko*/*Homya*.

**Unallocated MID.** Seven tankers since Jun 2025 on MID `646`, unallocated per ITU; one, *Symphony*, transmitting on its real identity and on fake MMSIs with fake IMOs at the same time — two transponders (`press`, 21 Aug 2025). That is only visible if MMSI→IMO pairs are kept.

**Fake flags.** Windward counts **300** fraudulently flagged tankers of 1,358 (22%), 268 also sanctioned (`vendor claim`). Lloyd's List: "not possible to assess whether a vessel is flying a false or legitimate flag using an MMSI number alone". Since we derive flag from the MID, a false flag is invisible to us.

**One pattern in the brief I could neither source nor test: numbers issued through deception.** I found no published, citable case of a valid IMO number being obtained by registering a fictitious ship, and I will not assert one. The mechanism would be registration fraud rather than AIS manipulation, and nothing in the free data could show it (see unknowns).

### 2.4 What I reproduced, and the base rates that kill naive versions

`measured`, `gfw-named-imos.jsonl` (7 published IMOs, all groups) and `gfw-identities.jsonl` (595 IMO records, 19:16 snapshot; `gfw_chains.py`, `baserate.py`):

| Test | Result | Denominator |
|---|---|---|
| Published cases whose fake identities appear in GFW groups | 6 | 7 |
| Published cases with AIS after the last registry record | 7 | 7 |
| Ordinary ships with AIS after the last registry record | 469 (98%) | 479 with a registry record |
| ...by more than 1 year | 240 (50%) | 479 |
| ...by more than 2 years | 206 (43%) | 479 |
| IMOs with a chain of ≥3 non-overlapping identities | 188 (32%) | 595 |
| IMOs with ≥4 such periods | 88 (15%) | 595 |
| IMOs whose 3+ chain carries 3+ distinct names | 127 (21%) | 595 |

The chains are not rare and mostly ordinary: IMO 9268112 runs *Fuji Spirit* (Bahamas) → *Blue Power* (Liberia) → *ARC 1* (Panama) → *Olia* (Gabon) → *Alba* (Belgium/Gambia) to 2026, handovers same-day. That is what a sale-and-reflag looks like, and it is indistinguishable from a zombie without a scrapping date. In the published cases the *first* fake identity appears 189-2,545 days after the real one stops, while the fake-to-fake swaps are same-day (11 of 25 transitions in the named file are 0 days) — a shape ordinary sales also produce.

One detail does link cases computationally: the fake name **BIRTH YOUNG** appears on two different dead IMOs (9233313 from 2025-04-24, 9259173 from 2025-04-03); **NORTH LAKE** appears on four MMSIs on 9231468; **SCIONG** on three MMSIs on 9259173. Reused fake names are a cheap graph edge — but they need the identity-history layer we are not building.

### 2.5 Promising tests that are not

- **MID allocation.** 25 of 10,718 MMSIs (0.23%) fall outside a 292-code public list, half of them 8xx/9xx special uses (handheld, AtoN, SART) or test strings; `id-flags` found 30/3,475 Danish ship-class MMSIs outside a 285-code list, 22 of them buoys, aircraft or AtoN. Not a ship lead, and the ITU's own page is JavaScript-only (USCG mirror 403), so we cannot even claim a vetted list offline.
- **"IMO above the current issuance front".** Unsafe: numbers cluster near 1.12M today, yet my capture has check-digit-valid values at 1,140,558, 1,184,059 and 4.5M-5.2M on plausible vessels (old ships, small US craft). Allocation is not contiguous.
- **GFW identity-period overlap as "two ships at once".** No: most overlaps are repeated period rows from per-region queries (`id-causes`, `id-flags`). Live concurrency needs raw AIS captures.
- **Flag-set alarms.** Of 692 sampled GFW ships with a flag, **137 (19.8%)** had at least one identity period under a flag that published reporting most often links to shadow-fleet reflagging (Comoros 35, Sierra Leone 33, Cameroon 28, Gabon 28, Palau 25, St Kitts 23, Tanzania 19, and smaller counts). Split by group: silent tankers 62/144 (43%), random tankers 48/326 (15%), random cargo 27/222 (12%). These are legitimate open registries, so this is a base rate for a flag-set alert, not evidence about any ship: it fires on a fifth of an ordinary sample.

## 3. Change classification

| Change | Typical timescale | Likely causes | Rate, with denominator | Standard, noise or potentially malicious? | Effect on tracking | Effect on prediction | Suggested handling or flag | Evidence |
|---|---|---|---|---|---|---|---|---|
| IMO absent / zero | always | not fitted; Class B; skipped | 175/494 static msgs (Baltic) | standard | no IMO join | none if MMSI keyed | `imo_missing`; never join by IMO alone | measured |
| IMO fails check digit | always | placeholder, 9/10-digit entry, trailing zeros | 3.4% of 3,136 values; 17/1,503 Danish ships | noise | broken join; fake "new" ship | churn injected into history | `imo_bad_checksum` (in `models.py`); strip then re-check | measured |
| IMO of scrapped ship | months per hull | deliberate reuse; rarely a reused transponder | 28 vessels Feb 2025 → 46 vs 19 IMOs Dec 2025 → 49/1,358 tankers Aug 2026 | potentially malicious | hulls merge; fleet counts inflate | contaminated history, label leakage | strong lead only with a broken-up date | press, vendor |
| IMO of unbuilt ship | months | deliberate | 1 published case | potentially malicious | identity with no history looks clean | cold-start bias | needs build dates, not free | press |
| Invented IMO passing check digit | months | deliberate | 2 published cases | potentially malicious | unresolvable in any registry | orphan identity | needs a registry lookup | press |
| Two hulls, one IMO, same minute | hours-days | dual transponder; or one spoof | 0/3,136 after junk filter; 0/1,503 Danish day | malicious with a fake MID | duplicate tracks, false jumps | unstable features | require 2+ receivers and position conflict | measured |
| MMSI with unallocated MID | days-weeks | deliberate "stateless" ID | 7 tankers since Jun 2025 (press); 25/10,718 MMSIs, mostly non-ship | potentially malicious | sanctions match fails | none directly | not a ship lead without a vetted list | press, measured |
| Flag change to a reflagging-associated register | days | sale, sanctions pressure, evasion | 19.8% of 692 sampled ships have such a period; 43% of silent tankers | standard for most, potentially malicious in the tail | flag derived from MID changes with MMSI | flag feature drifts with MMSI | treat as context, never as a flag alone | measured |
| Name+flag+MMSI change, IMO kept | days-years | sale, reflag, rename | 32% of 595 IMOs have ≥3 identities; 51% of switches ≤1 h apart (`id-frequency`) | standard | continuity only via IMO | features reset if MMSI keyed | keep IMO as an alias link | measured |

## 4. What this means for us, given MMSI-only

- **For a 24-hour build nothing here breaks.** Zero duplicate IMO/MMSI identity in a Danish day and, after junk filtering, zero in an 8-minute worldwide capture. Identity fraud happens over days to months on hulls.
- **For the pitch there is an honest demo**: free data reproduces 6 of 7 published zombie cases as chains under one IMO — a story about history, exactly what MMSI-only gives up. The smallest credible study is those 7 IMOs, 6 reproductions, 1 miss, plus the base rate showing chain shape alone proves nothing.
- **Cheap insurance, not features:** keep IMO per static message (already in `VesselStatic`), never coerce junk to int, keep a `(mmsi, imo)` change log, filter IMO before any join (`id-joins`: IMO beats MMSI for sanctions matching, 4.8% vs 1.5% in Danish data).
- **Do not build:** MID-allocation alarms, IMO range rules, check-digit repair, silence-after-recency flags — all measured as noise, 100%-base-rate, or identity-inventing.

## 5. Unknowns and how to settle them

1. **Scrapped or never-built status per IMO** — the one field that turns leads into evidence. GMS demolition sales and NGO Shipbreaking Platform publish free; GISIS needs registration.
2. **Whether an IMO was ever issued** — `imonumbers.ihs.com` (free registration) or GISIS; settles `1095337`-style cases without any AIS reasoning.
3. **A vetted MID list** — ITU `mid.aspx` (JS-rendered); `id-fuzzy` already parsed 291 codes to `$WAVE/data/id-fuzzy/mid_wikipedia.json`.
4. **Whether GFW's groups are complete** — ask for the same cases by MMSI; if the fake MMSIs do not resolve, GFW drops groups.
5. **Ownership** — Equasis/IHS only, login-walled.
6. **Numbers issued through deception** — untested here for lack of a source; it would show up only as a hull whose registry particulars are fictive, which needs S&P or GISIS amendments history.

## 6. Sources

`documented`: IMO identification number schemes, Circular letter 1886/Rev.5. Allocated-MID list from Wikipedia "Maritime identification digits" (292 codes, known incomplete).

`press`: Lloyd's List daily 3 Feb 2025 (public PDF: 28 vessels, 18/28 MMSIs unrecognised in GISIS, JRC "0000"); "From zombie tankers to fake IMO numbers" (LL1155512); "Tanker identity theft cases have risen dramatically this year" (LL1155819, abstract); "Newbuild identity theft" (LL1156174); "Shadow fleet tankers experiment with stateless identification numbers" (LL1154597); "US-blocked VLCC Jaya" (LL1153764). gCaptain/Bloomberg "'Scrapped' Tanker Rises From the Dead" (Dec 2025). `vendor claim`: Vortexa (10 Dec 2025); Windward dashboard (Aug 2026 period).

`measured`: AISStream worldwide capture 2026-11-07 19:07:31-19:15:45 UTC; GFW identity records `gfw-identities.jsonl` (595 records) and `gfw-named-imos.jsonl` (7 published IMOs, provided by the orchestrator); Danish `classa_1630_1700Z.csv` for 2026-11-01 16:30-17:00 (294,883 rows, 1,564 MMSIs, 949 IMOs: 1 bad check digit `2222222`, 0 MMSIs with two IMOs, 0 IMOs on two MMSIs, 4 MMSIs outside the MID list, all special-format). Scripts `$WAVE/scripts/id-imo-fraud/{ais_anom,gfw_ids,gfw_ids2,gfw_chains,baserate,day_agg}.py`; outputs `$WAVE/data/id-imo-fraud/`.
