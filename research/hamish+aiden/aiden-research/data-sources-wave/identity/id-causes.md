# id-causes: why identity fields change

Agent id-causes, 2026-11-07 19:07-19:25 UTC. Labels: **measured** (this wave's data), **documented** (rule/official text), **press**, **vendor claim**, **unverified**.

Snapshot: `gfw-identities.jsonl`, 424 IMO records at 19:16 UTC (130 random cargo, 197 random tankers, 97 silent tankers), 1,018 self-reported periods, 791 transitions after dedupe. Silent tankers were selected for having gone silent, so these are sample rates, not fleet rates. AISStream capture snapshot: 19,044 messages, 12,910 MMSIs, about 19:00-19:12 UTC.

## 1. Bottom line

1. **Most changes are a rule working.** An MMSI's first three digits are the flag's Maritime Identification Digits (MID). ITU guidance requires administrations to reassign "all of the assigned means of ship station identification, including the MMSI" when a ship changes flag (documented, ITU-R M.585-10, April 2026, Annex 3 §1(c)). Reflagging mechanically brings a new MMSI, call sign and usually a name.
2. **The IMO number is the only identifier meant to be permanent** through sale, rename, reflag and scrapping (documented, IMO Resolution A.1117(30)). It is self-reported in AIS and easy to alter, so the stable key is the unverified one.
3. **Measured: flag and MMSI move together.** 693 of 693 flag changes also changed the MMSI; none kept it. MMSI changed without a flag change in 83 of 791 transitions (10.5%), some visibly one-day artefacts or re-issuance. Names changed in 498 of 791, usually with flag/MMSI.
4. **Ordinary and deliberate changes look alike field-by-field.** Timing, registry quality and repetition separate them. Lloyd's List: 36% of cargo ships sanctioned in 2025 reflagged, 45 days after designation on average, versus 85 days for 2024 and 267 for 2018 (press). Our sample had 3+ flags within 365 days for 15 of 97 silent tankers (15%), 7 of 197 tankers (3.6%) and 5 of 130 cargo ships (3.8%, excluding a placeholder IMO).
5. **Inside 24 hours MMSI-only costs almost nothing; over months it breaks history.** No named MMSI showed two names, IMOs, call signs or types inside the capture (0 of 10,705 named). Published fraud (scrapped-ship IMOs, cloned MMSIs, false flags) is real but low-rate and needs registry data to confirm.

## 2. Findings

### 2.1 The rules

- **MMSI**: nine digits, `MID + 6`; the MID denotes the administration with jurisdiction (documented, M.585-10 Annex 1 §1). Other prefixes mark group, coast, SAR aircraft, AIS-SART, MOB and EPIRB stations.
- **Reflag**: reassign all ship station identities including the MMSI, and notify ITU (documented, Annex 3 §1(c)). An MMSI may be reused "after being absent from two successive editions of List V ... or after a period of two years, whichever is the greater" (documented, §1(d)). An old MMSI on another hull is therefore expected after two years, not proof of spoofing.
- **IMO number**: seven digits, allocated by IHS/S&P Global at build or first registration, permanent, unchanged on transfer of flag, marked on the hull under SOLAS XI-1/3 (documented, A.1117(30) §§3-7). It anticipates name changes and refers doubtful numbers to the register or flag State (§6). IMO numbers are never reassigned, which lets a scrapped ship's IMO serve as cover.
- **Sale and rename**: neither scheme forbids renaming; a same-flag sale can keep name, call sign and MMSI. In practice a sale often brings a new name, call sign, flag and therefore MMSI. Lloyd's List: "Not every flag change is a cause for concern ... mainstream commercial trades move between registries ... but this is to legitimate registers and happens infrequently" (press).

### 2.2 How changes arrive

- **Flag and MMSI switch as a pair at handover**: 693 flag changes, all with an MMSI change; 776 MMSI changes in 791 transitions. 407 (51%) new periods start within a day of the old one ending.
- **Same-flag MMSI changes: 83/791 (10.5%).** Some are clear noise: IMO 9814909 (DIONNE) shows an alternate MMSI 354996064 for one day only, same name and flag. Some look like re-issuance: IMO 9610341 (TUVAQ W.) gets a new Marshall Islands MMSI in successive seasons (…538090546, …578, …613, …655, …678, …717). Telling them apart needs ITU List V.
- **Name-only changes are few**: 12/791, e.g. 9392858 GAS ARIA to CS ARIA (Indonesia), and typo/abbreviation variants. Most of the 498 name changes came with flag or MMSI.
- **Long series are common**: per IMO, 127 of 424 records show one flag, 137 two, 76 three and 84 four or more, some eight; cumulative 2012-2026, not a rate. GFW's AIS flag appears to be derived from the MID, so flag and MMSI are not independent evidence (id-frequency); the registry flag differs in 17% of records (id-joins).
- **Rapid hopping concentrates in the silent-tanker sample**: 15/97 (15%) versus 7/197 tankers (3.6%) and 5/130 cargo (3.8%). Data example: IMO 9297371 went GBR, MHL, KNA/PAN, COM, BEN, CMR, RUS between 2012 and 2026, as DIVA 1 from 2025; 9318034 ran similarly to STP, MWI, GMB, CMR, RUS. Conversely ZALIV VOSTOK kept its name across six flags (LBR 2012 to OMN 2025), so name stability is not legitimacy.
- **Data warning**: 270 of 791 transitions overlap, many by months or years; long overlaps cannot be concurrent transmission. They are GFW periodisation or duplicate-row artefacts, not live dual transmitters (id-flags, id-frequency agree).

### 2.3 Noise that is not a change

- **Placeholder IMO 1234567 passes the check digit** but appears on 25 MMSIs and 27 names in the 308-record snapshot (measured). Treat it as null.
- IMO 0 on 175/494 Baltic `ShipStaticData`, 6 bad check digits, 1 blank name (orchestrator, measured); Class B `StaticDataReport` has no IMO and splits name from details. Typos (EAELE QYDNEY for EAGLE SYDNEY), stripped spaces (`FSBITUMEN2`) and 6-bit charset artefacts (`,NDI IPSA`) are normalisation issues; see id-fuzzy.

### 2.4 Deliberate practice in published reporting

- **Zombie IMOs**: 28 vessels transmitting IMO numbers of ships scrapped since November 2024; 18/28 had an MMSI unrecognised in GISIS. Frunze (IMO 9263643), sanctioned 2 October 2024, dropped its assigned IMO and MMSI on 21 October, took the name Skyrill, a Guyana-style MMSI and a scrapped tanker's IMO (press, Lloyd's List, 3 February 2025). A transponder's IMO often needs only the same password as the name; a JRC manual showed default "0000". By December 2025 Lloyd's List counted 46 scrapped-ship IMOs in use, against 19 a year earlier; unallocated MID 646 appeared on 7 tankers since June 2025 (press, via id-imo-fraud).
- **Scale**: 49 of 1,358 tracked tankers are zombie tankers; 300 broadcast flags from registries not recognised by IMO, 268/300 (89.3%) also sanctioned. Distinct tankers changing MMSI: 114 July, 87 August, 58 September, 38 to 26 October 2026 (vendor claim, Windward dashboard, August 2026 period).
- **Post-designation flag hopping**: 218 cargo ships sanctioned in 2025, 78 reflagged (36%); 2024: 323 designated, 220 reflagged (68%), 66% within three months; 215 flag changes by mid-2025 versus 200 in all 2024; 7 of the 2025 ships (3%) reflagged twice or more. About half of flag changes since November 2024 used MMSIs of Comoros, Guyana or the Netherlands Antilles; 24 ships moved to Djibouti, 5 Oman, 2 Timor-Leste. Sooraj, Gabon-flagged at UK designation on 24 February 2025, used a Panama-affiliated MMSI from 14 March and a Djibouti one from 7 April (press, Lloyd's List half-year outlook 2025, pp. 8-10).
- **Honest limit**: "It is not possible to assess whether a vessel is flying a false or legitimate flag using an MMSI number alone" (press, same article). Windward: an MMSI change "doesn't prove deception" alone (vendor claim).

### 2.5 Legitimate-looking-suspicious, and the reverse

Suspicious: 3+ flags in a year, especially to Comoros, Cameroon, Benin, Gabon, Gambia, Sao Tome, Djibouti, Timor-Leste or Oman; a name held while flags churn; a new MMSI with no flag change and no register explanation; a change days after sanctions or a dark gap. Odd but legitimate: one sale to another mainstream register with name/flag/MMSI/call sign changing together; a one-day alternate MMSI; seasonal renumbering; a placeholder IMO on small craft; an MMSI reused after two years.

## 3. Change classification

| Change | Timescale | Likely causes | Rate (denominator) | Standard, noise or malicious? | Effect on tracking | Effect on prediction | Handling or flag | Evidence |
|---|---|---|---|---|---|---|---|---|
| MMSI + flag | same day at handover | sale, reflag, sanctions, registry purge, flag of convenience | 693/693 flag changes (791 transitions) | standard | track splits unless IMO-linked | history reset; "went dark" breaks | join on IMO; show "same hull, new identity" | measured; documented |
| MMSI, same flag | days-months, often one day | re-issuance, programming error, duplicate MMSI, renumbering | 83/791 (10.5%) | mostly noise; unexplained cases suspicious | duplicate or broken track | one hull inherits another's history | flag if old and new overlap or MID changes; check List V | measured |
| Name | sale/rename day | rebranding, new owner, charterer brand, typo | 498/791; 12 name-only | standard or noise | label changes, track survives | minor; name joins break | normalise; never key on name | measured |
| Flag | handover day; 45 days after sanctions (2025) | sale, reflag, sanctions, registry action, false flag | 693/791; 15/97 silent tankers had ≥3 flags/365 days | rare = standard; rapid repetition suspicious | MMSI changes with it | flag weak; leakage if post-hoc | flag ≥3 flags/12 months or change within 90 days of a gap | measured; press |
| IMO field on same hull | one static message | reprogramming, placeholder, typo, zombie identity | 0 multi-IMO MMSIs in 19,044 messages; 1234567 on 25 MMSIs | deliberate in published cases, else noise | breaks the reliable join; merges hulls | worst case for history and sanctions | reject 0/1234567; checksum; alert on change for a persistent MMSI | measured; press |
| Call sign | reflag/sale day | new register issues it | changes with reflag; not tabulated separately | standard | none if MMSI/IMO kept | minor | ignore as a key | measured |
| Type/size/destination | refit or per voyage | conversion, data entry, class change | not measured cleanly | standard or noise | filters misclassify | weak feature drift | not an identity change | unverified |
| Deliberate substitution | days after sanctions or a gap | zombie IMO, cloned MMSI, false flag | 28 zombie-IMO vessels (LL 2025); 49/1,358 tankers (Windward 2026) | potentially malicious | false merges, lost leads | poisoned history; wrong sanctions match | needs GISIS/register plus behaviour | press; vendor claim |

## 4. What this means for us, given MMSI-only

- **The 24-hour product loses nothing measurable.** No MMSI changed name, IMO, call sign or type inside the capture; reflags are not a within-hours event. Live map and gap detector are unaffected.
- **History features are not safe.** Every reflag ends the MMSI series, and an MMSI can belong to another hull after two years. "This MMSI was silent in August" and "went dark before" inherit both errors; sanctions matching is also weaker by MMSI than IMO (id-joins: 1.5% vs 4.8% on the Danish fleet).
- **If we keep history, key on IMO**, after checking seven digits, check digit, not 0 or 1234567, and not active on another MMSI. It links claims, not verified identity.
- **Do not ship "MMSI changed = evasion".** Say "this hull's identity fields changed; it does / does not fit the ordinary sale-or-reflag pattern". The strongest published lead is flag-hopping after sanctions.
- **Options**: (a) leave identity-change detection out; the 24-hour product loses nothing. (b) Add one small flag from data we already store: a persistent MMSI whose name, IMO or type changes, or an IMO appearing under a new MMSI; label "identity change, cause unknown". (c) Run a separate pitch study joining GFW periods to GISIS/List V to price ordinary versus flagged changes; not a build task.

## 5. Unknowns, and how to settle them

- **Same-flag MMSI churn: re-issuance or error?** ITU List V/MARS or register enquiries; 83/791 is too contaminated for a rate.
- **How much GFW overlap is real?** Long overlaps are artefacts; measure concurrency from raw AIS (id-shortterm).
- **Ordinary sale base rate by flag and year.** Needs registry/ownership data (Equasis, GISIS, commercial), which we lack.
- **Whether a flag is real, false or unrecognised.** Needs the flag State's register or GISIS; the MID is only a claim.
- **Whether any sample case is fraud.** Not decidable from AIS; a scrapped or unbuilt ship needs register status and last-record date (S&P/GISIS).

## 6. Sources

- ITU-R M.585-10 (April 2026), Annex 1 §1, Annex 3 §1(c)-(d): https://www.itu.int/dms_pubrec/itu-r/rec/m/R-REC-M.585-10-202604-I!!PDF-E.pdf (documented).
- IMO Resolution A.1117(30), 6 December 2017, preamble and §§3-7: https://wwwcdn.imo.org/localresources/en/KnowledgeCentre/IndexofIMOResolutions/AssemblyDocuments/A.1117%2830%29.pdf (documented).
- Lloyd's List, "Dead identities: over 25 ships using scrapped IMO numbers", 3 February 2025, pp. 1-2: https://www.lloydslist.com/-/media/lloyds-list/daily-pdf/2025/02-february/dailypdf030225.pdf (press).
- Lloyd's List, "Flag hopping increasingly popular with sanctioned fleet", Half-year outlook 2025, pp. 8-10: https://www.lloydslist.com/-/media/lloyds-list/images/special-reports-2025/half-year-outlook/nor_shipping-2025.pdf (press).
- Windward shadow-fleet dashboard (August 2026 period): https://windward.ai/maritime-intelligence-operations-center/insights-shadow-fleet/ (vendor claim, accessed 7 November 2026).
- This wave: `$WAVE/data/identity/gfw-identities.jsonl`, `aisstream-capture.jsonl` (measured, 19:12-19:16 UTC snapshots); scripts `$WAVE/scripts/id-causes/gfw_final.py`, `capture_static.py`; orchestrator counts from the brief (measured).
