# Fake and bogus IMO numbers (track: id-imo-fraud)

Agent `id-imo-fraud`, identity wave, Saturday 7 November 2026. All measurements UTC, taken 19:07-19:35. Ships are leads unless a published source names them. `measured` = I ran it on the shared data and say so with a denominator; `press`, `vendor claim`, `documented` = someone else's number.

## 1. Bottom line

1. **Published zombie-IMO counts, with denominators, are small but rising fast.** Lloyd's List: **28** vessels transmitting IMO numbers of scrapped ships as of 3 Feb 2025 (`press`, public PDF, [lloydslist.com daily 2025-02-03](https://www.lloydslist.com/-/media/lloyds-list/daily-pdf/2025/02-february/dailypdf030225.pdf)); **46** scrapped-ship IMOs in active use in Dec 2025 against **19** a year earlier (9 Dec 2025, abstract only). Vortexa: "more than 60" (`vendor claim`, 10 Dec 2025). Windward: **49 zombie tankers of 1,358 shadow-fleet tankers = 3.6%**, August 2026 reporting period (`vendor claim`, [windward.ai shadow-fleet dashboard](https://windward.ai/maritime-intelligence-operations-center/insights-shadow-fleet/)). So the phenomenon is ~3-4% of the illicit tanker fleet and doubling roughly yearly, which is a compliance story, not a property of world AIS.
2. **Free data reproduces 6 of the 7 published zombie cases — but only if you read every identity group GFW returns for an IMO.** `measured`. In `gfw-named-imos.jsonl` the impersonations appear as extra entry groups: IMO 9177686 shows the real *New Discovery* ending 2018-10-30, then *Lavin* on Mali MMSI 649111000 (Sep-Oct 2025) and *Lavine* on a Comoros MMSI (from Oct 2025) — matching the Lloyd's List account of *Macho Queen*. IMO 9292993 shows *Skyrill* (Guyana, then Tanzania) from Oct 2024, matching the *Frunze* case. Only *Macho Queen*'s own IMO (9238868) shows nothing.
3. **Check digits catch typos, not fraud.** Both published fake IMO numbers pass the mod-10 rule (`1095337`, invented and absent from GISIS; `1123081`, a real number of a ship under construction). `measured`: 48 of 1,268 IMO values (3.8%) in a worldwide AISStream capture fail the check digit and almost all are placeholders or field corruption (`100000000`, 9- and 10-digit values), not impersonation.
4. **The obvious retrospective rule does not discriminate.** "IMO still transmitting after its last registry record" fires on **415 of 424** GFW ships that have a registry record (98%), median lag 430 days, 51% by more than a year and 43% by more than two years, because GFW's registry snapshots are stale. Only a *definitive* status — scrapped, never built, not in the current register — makes the same test sharp.
5. **What is worth 20 lines of code:** strip and validate IMO before any join; treat `1234567`/`100000000`/7-digit-with-trailing-zeros as null; keep `(mmsi, imo, name, flag)` per static message instead of upserting. Everything else in this track needs a registry and belongs in a pitch study, not the build.

## 2. Findings

### 2.1 What the scheme guarantees, and why it enables all of this

`documented` ([IMO identification number schemes](https://www.imo.org/en/OurWork/MSAS/Pages/IMO-identification-number-scheme.aspx), Circular letter 1886/Rev.5): assigned by IHS Maritime/S&P Global at keel laying; seven digits; "never reassigned to another ship"; mandatory since 1 Jan 1996 for cargo ships of 300 GT+ and passenger ships of 100 GT+; voluntary for fishing vessels of 100 GT+ since 2013; meant to survive changes of owner and flag.

Three consequences. A number exists **before** the hull does (assigned at keel laying/contract), so numbers of hulls not yet delivered, or never delivered, are valid-looking and silent. A number **outlives** the hull, so a scrapped ship's number is a permanently clean identity attached to nobody. And the number is typed in by crew: Lloyd's List reports IMO entry is often password-only, with JRC's default "0000", and that AIS transponders from scrapped ships are sometimes reused without clearing old data (`press`, 3 Feb 2025) — a benign explanation that must be ruled out before calling anything fraud. The IMO itself acknowledges the problem: its Navigation, Communication and Search and Rescue subcommittee has been considering measures to improve AIS integrity, with VDES expected to address it (`documented` via the same article).

### 2.2 The check-digit battery, measured

`measured`. Worldwide AISStream capture (`$WAVE/data/identity/aisstream-capture.jsonl`), 6 minutes from 19:07:31 UTC: 4,509 distinct MMSIs, 1,268 distinct IMO values in 2,282 static messages.

| Test | Result | Denominator |
|---|---|---|
| IMO value fails check digit | 48 (3.8%) | 1,268 values |
| Messages carrying a failing IMO | 62 (2.7%) | 2,282 messages |
| IMO value of non-standard length (1-6 or >7 digits) | 29 | 48 failures |
| 7-digit failing IMO with exactly one single-edit repair | 0 | 21 |
| 7-digit failing IMO with several possible single-edit repairs | 21 (100%) | 21 |

Two negatives worth keeping. **Most failures are not ships' mistakes about a real number**: `100000000`, `1000000000`, `1010363000`, `0630414`, `1`, `1234567`-style round values. **You cannot reconstruct a mistyped IMO from the check digit**: every 7-digit failure in my sample had several one-edit repairs that satisfy the rule (substituting the check digit always does), so "repair then join" would invent identities. Danish corroboration from `id-flags`: of 17 non-conforming IMO values in a full Danish day, 11 were a valid 7-digit IMO with extra characters (mostly two trailing zeros) — so strip and re-check before judging.

Placeholders matter for joins, not fraud. `id-causes` measured `1234567` (which passes the check digit) on 25 MMSIs and 27 names.

### 2.3 Documented patterns and how they are detected in practice

**Zombie (scrapped hull).** Numbers above. Signals used by the analysts: an IMO whose registry status is broken-up re-appearing in AIS; a name that exists in no register (`Quasar`); an MMSI that GISIS does not recognise (18 of Lloyd's List's 28); a flag claim that GISIS says is false (*Birth Young*/*Brave M* under Guyana). Named cases, as leads, all `press`: *Macho Queen* → *Lavin* (IMO 9177686, Mali then Comoros MMSI, one of them simultaneously used by *Guly*); *Panda* → *Birth Young* (IMO 9233313, then 9259173); *Koen* → *Rada*'s IMO 9213301; *Jaya* using scrapped *Assos*' IMO 9233791, TankerTrackers putting "more than 50 tankers using fake identities" at that time; *Freesia I* in Venezuela.

**Newbuild (never-completed or under-construction hull).** First published case: sanctioned *Frunze* transmitting IMO `1123081`, belonging to an aframax under construction at Wanlong, appearing as *Cordula* with a Tanzania MID (`press`, Lloyd's List, 26 Jan 2026). Vortexa's Claire Jungman: such a number "is not expected to transmit AIS or appear in operational databases, which reduces the chance of immediate detection". Detection needs build/contract dates — no free source in our stack.

**Invented number.** `1095337` (absent from GISIS) used by *Tia* as *Arcusat*; and hijack of a live number, `1107697`, belonging to a Chinese tug, used by *Izumo* as *Tiko*/*Homya*.

**Unallocated MID.** Seven tankers since June 2025 using MID `646`, unallocated per ITU; one of them, *Symphony*, transmitting on its real identity and on fake MMSIs with fake IMOs at the same time, i.e. two transponders (`press`, Lloyd's List, 21 Aug 2025). That dual-transmission detail is the only observation of its kind in this literature and it is visible only if MMSI→IMO pairs are kept.

**Fraudulent flags.** Windward counts **300** fraudulently flagged tankers of 1,358 (22%), 268 of them also sanctioned (`vendor claim`, Aug 2026). Lloyd's List: "not possible to assess whether a vessel is flying a false or legitimate flag using an MMSI number alone" (quoted in the shared notes by `id-causes`). Since we derive flag from the MID, a false flag is invisible to us.

**Detection signals per pattern, and whether free data can compute them** (my assessment, `measured` where tested):

| Pattern | Signal used in practice | Computable free? | Missing piece |
|---|---|---|---|
| Scrapped IMO reused | IMO's registry status = broken up, yet transmitting | no | demolition date (LL Intelligence, GMS, NGO Platform) |
| Unbuilt IMO reused | IMO belongs to a hull at a yard, yet transmitting | no | build/contract dates (S&P, IHS) |
| Invented IMO | IMO absent from GISIS | yes, with registration | GISIS lookup or `imonumbers.ihs.com` |
| Live IMO hijacked | same IMO on two MMSIs at once, with position conflict | yes | only from raw multi-receiver AIS, not GFW history |
| Unallocated MID | MID not in ITU table | partly | a vetted ITU MID list; non-ship MMSIs must be excluded |
| Fake flag | MMSI/GISIS flag claim contradicted by administration | no | GISIS + flag-registry confirmation |
| Junk/typo IMO | fails length or check digit | yes (cheap) | none — but it is noise, not fraud |

### 2.4 What I reproduced on free data

`measured`, `gfw-named-imos.jsonl` (7 published-case IMOs, all identity groups) and `gfw-identities.jsonl` (449-465 IMO records across Hormuz, Malacca, Danish waters as it grew):

| Test | Result | Denominator |
|---|---|---|
| Published cases with the impersonation visible in GFW identity groups | 6 | 7 |
| Published cases where AIS self-report continues after the last registry record | 7 | 7 |
| Ordinary ships with AIS after their last registry record | 415 | 424 (98%) |
| ...by more than 1 year | 215 | 424 (51%) |
| ...by more than 2 years | 184 | 424 (43%) |
| IMOs with a chain of ≥3 non-overlapping identities | 144 | 449 (32%) |
| IMOs with ≥3 distinct names across such a chain | 95 | 449 (21%) |
| IMOs with ≥4 identity periods | 68 | 449 (15%) |

The chains are not rare, and most are ordinary: IMO 9268112 runs *Fuji Spirit* (Bahamas) → *Blue Power* (Liberia) → *ARC 1* (Panama) → *Olia* (Gabon) → *Alba* (Belgium/Gambia) through 2026, handovers dated the same day. That is what a sale-and-reflag looks like in this data — indistinguishable from a zombie without a scrapping date. The published fraud cases are not distinguishable by chain length either; they were caught by registry status, not by AIS shape.

One measured detail does link cases computationally: the fake name **BIRTH YOUNG** appears on *two different* dead IMOs (9233313 from 2025-04-24, 9259173 from 2025-04-03), and **NORTH LAKE** appears on four MMSIs on 9231468, **SCIONG** on three MMSIs on 9259173. Reused fake names are a cheap graph edge between otherwise unrelated IMOs — but they require the identity-history layer we are not building.

### 2.5 Tests that look promising and are not

- **MID allocation.** I built a 292-code allocated-MID list from the public Wikipedia table and checked 4,509 MMSIs: 11 (0.24%) fell outside it. Half are 8xx/9xx special MMSIs (handheld, AtoN, SART) and one is a Danish Class B unit `500000001`. `id-flags` found 30/3,475 Danish ship-class MMSIs outside a 285-code list, of which 22 are buoys, aircraft, test strings or AtoN. Verdict: not a ship lead. The ITU's own MID page is JavaScript-only and the USCG mirror returns 403, so we cannot even claim a vetted list offline.
- **"IMO above the current issuance front".** `measured` and unsafe. Current numbers sit around 1.12M (the under-construction aframax is 1,123,081), but my capture contains check-digit-valid values at 1,140,558, 1,184,059, 1,330,000+ and 4.5M-5.2M on real, plausible vessels (old ships and small US craft with US callsigns). Allocation is not contiguous, so range rules produce false leads.
- **Overlap of identity periods in GFW.** Not usable: `id-causes` and `id-flags` both show most overlaps are repeated period rows from per-region queries. My raw count (28 of 164 ships) shrinks to 2 ships with ≤48 h overlap on the visible sample.

## 3. Change classification

| Change | Typical timescale | Likely causes | Rate, with denominator | Standard, noise or potentially malicious? | Effect on tracking | Effect on prediction | Suggested handling or flag | Evidence |
|---|---|---|---|---|---|---|---|---|
| IMO absent / zero | always | not fitted, Class B, crew skipped it | 175/494 static msgs (Baltic sample); 0/2,282 in worldwide capture | standard | no IMO join | none if MMSI keyed | `imo_missing`; never join by IMO alone | measured |
| IMO fails check digit | always | placeholder, 9/10-digit entry, trailing zeros | 3.8% of 1,268 values; 17/1,503 Danish ships (11 repairable) | noise | broken join, fake "new" ship | identity churn injected into history | `imo_bad_checksum` (already in `models.py`); strip-then-recheck | measured |
| IMO of scrapped ship | weeks-months per hull | deliberate reuse for sanctions trade; occasionally a reused transponder | 28 vessels (Feb 2025), 46 vs 19 IMOs (Dec 2025), 49/1,358 tankers = 3.6% (Aug 2026) | potentially malicious | several hulls under one identity; tracks merge, fleet counts inflate | contaminates history, double counting, label leakage | strong lead: needs broken-up date, not AIS shape | press/vendor |
| IMO of unbuilt ship | months | deliberate; nobody expects AIS from a yard hull | 1 published case (IMO 1123081) | potentially malicious | identity with no history looks clean | cold-start bias | flag only with build dates (not free) | press |
| Invented IMO passing check digit | months | deliberate | 1-2 published cases (1095337; 1107697 is a live hijack) | potentially malicious | unresolvable in any registry | orphan identity | needs registry lookup | press |
| Two hulls, one IMO, same minute | hours-days | deliberate dual transponder; or two receivers, one spoof | 0 in 1,268 AISStream values; 0/1,503 Danish day; 1/1,345 AISStream (junk `100000000`) | malicious when paired with a fake MID | duplicate tracks, false jumps | feature instability | flag with care; require 2+ receivers and position conflict | measured |
| MMSI with unallocated MID | days-weeks | deliberate "stateless" ID | 7 tankers since Jun 2025 (press); 11/4,509 worldwide, 30/3,475 Danish, mostly non-ship | potentially malicious | sanctions match fails | none directly | not a ship lead without a vetted MID list | press + measured |
| Name+flag+MMSI change, IMO kept | days-years | sale, reflag, rename | 32% of 449 IMOs have ≥3 non-overlapping identities; 46% of switches ≤1 h apart (`id-frequency`) | standard | continuity survives only via IMO | resets features if MMSI keyed | keep IMO as alias link | measured |

## 4. What this means for us, given MMSI-only

- **For a 24-hour build, nothing here breaks.** Zero duplicate IMO/MMSI identities in the Danish day and in the AIS capture at our measured rates; the fraud phenomenon lives at days-to-months scale on hulls, not minutes.
- **For the pitch, there is a real and honest demo**: free data already reproduces 6 of 7 published zombie cases as identity chains under one IMO. That is a story about *history*, and it is exactly what MMSI-only gives up. It is also the smallest credible study: 7 published IMOs, 6 reproduced, 1 miss, and a base rate showing that chain shape alone is not evidence.
- **Cheap insurance, not new features:** persist the IMO per static message (already in `VesselStatic`); never coerce junk IMO to int; keep a `(mmsi, imo)` change log; filter IMO before any external join (`id-joins` shows IMO beats MMSI as a sanctions-join key, 4.8% vs 1.5% in Danish data, so IMO has value even if not the key).
- **Do not build:** MID-allocation alarms, IMO range rules, check-digit "repair", silence-after-registry-record flags. All three measured as noise or as 100% base rate.

## 5. Unknowns, and how to settle them

1. **Scrapped or never-built status per IMO.** Needs a demolition list (GMS weekly sales, NGO Shipbreaking Platform), GISIS ship particulars, or S&P/IHS. Free-ish: NGO Shipbreaking Platform publishes vessel names per yard; GISIS needs registration. This single field is what turns every lead in section 2.4 into evidence.
2. **Whether an IMO was ever issued.** `imonumbers.ihs.com` (free registration) or GISIS. Settles `1095337`-style inventions without any AIS reasoning.
3. **A vetted MID list.** ITU `mid.aspx` (JavaScript-rendered) or the ITU ship-stations dataset. Until then, unallocated-MID claims stay leads; `id-fuzzy` already parsed a 291-code table to `$WAVE/data/id-fuzzy/mid_wikipedia.json`.
4. **Whether GFW's identity groups are complete.** Our 7-case check used `total` groups per IMO (7, 12, 4, 6, 5, 8, 2) — but we do not know if GFW drops groups. Ask for GFW identity records by MMSI rather than by IMO for the same cases to see whether the fake MMSIs resolve.
5. **Ownership and beneficial control.** Out of reach without Equasis/IHS (`id-joins`: Equasis is login-walled). No free path this weekend.

## 6. Sources

`documented`: IMO identification number schemes, Circular letter 1886/Rev.5, imo.org. Allocated-MID list from Wikipedia "Maritime identification digits" (292 codes, incomplete).

`press`: Lloyd's List Daily Briefing 3 Feb 2025 (public PDF: 28 vessels, 18/28 MMSIs unrecognised in GISIS, JRC "0000" default); Lloyd's List "From zombie tankers to fake IMO numbers" (LL1155512); "Tanker identity theft cases have risen dramatically this year" (LL1155819, 9 Dec 2025, abstract); "Newbuild identity theft is the latest deceptive shipping tactic" (LL1156174, 26 Jan 2026); "Shadow fleet tankers experiment with stateless identification numbers" (LL1154597, 21 Aug 2025); "US-blocked VLCC Jaya skirts sanctions with scrapped ship masquerade" (LL1153764). gCaptain/Bloomberg "'Scrapped' Tanker Rises From the Dead" (Dec 2025). `vendor claim`: Vortexa "Hidden Capacity: The Rise of Zombie Tankers" (10 Dec 2025); Windward shadow-fleet dashboard (Aug 2026 period).

`measured`: AISStream worldwide capture 2026-11-07 19:07-19:35 UTC; GFW identity records (`gfw-identities.jsonl`, `gfw-named-imos.jsonl`, snapshots taken during the wave); Danish AIS day 2026-11-01 window 16:30-17:00 (`classa_1630_1700Z.csv`, 294,883 rows, 1,564 MMSIs, 949 IMOs: 1 bad check digit `2222222`, 0 MMSIs with two IMOs, 0 IMOs on two MMSIs, 4 MMSIs with MIDs outside the list, all special-format). Scripts `$WAVE/scripts/id-imo-fraud/{ais_anom,gfw_ids,gfw_ids2,gfw_chains,day_agg}.py`; outputs `$WAVE/data/id-imo-fraud/`.
