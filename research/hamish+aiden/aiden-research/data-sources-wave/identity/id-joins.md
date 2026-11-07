# id-joins: joining identity across sources, and where registry data comes from

Agent `id-joins`, wave 5 (DeepSeek). Snapshot read **19:07–19:11 UTC, 2026-11-07** (`date -u`); both shared JSONL files were still growing during the read, so counts are for that snapshot. Scripts: `$WAVE/scripts/id-joins/joins.py`, `joins2.py`. Raw download: `$WAVE/data/id-joins/digitraffic-vessels.json`. This track prices the join options; it does not reopen Jake's MMSI-only decision.

## 1. Bottom line

1. **IMO in AIS is a class fact, not a data-quality problem.** Danish day 2026-11-01: 1,503/2,545 Class A ships carried an IMO (59%), **0/930 Class B**. AISStream capture (worldwide, ~31 min): 1,298/2,539 Class A (51%), **1/2,083 Class B**; Class B has no IMO field in the standard. **measured**
2. **Two free AIS feeds agree almost perfectly where they overlap.** Danish ∩ AISStream = 581 MMSIs (15.7% of the Danish fleet); among the 207 with static data on both sides, 98/98 IMOs match, 166/167 names, 168 call signs with **0 conflicts**, 166/168 lengths within 1 m. Danish ∩ Digitraffic = 96 ships, 94/94 on IMO, name, call sign and length. **measured.** Drift is not an inter-feed artefact; the noise is *missing* fields, not contradictory ones.
3. **The IMO is a materially better public-list join key than the MMSI.** Danish fleet ∩ OpenSanctions: 72/1,503 by IMO (4.8%) vs 54/3,690 by MMSI (1.5%). AISStream: 41/1,298 (3.2%) vs 103/12,005 (0.9%). OpenSanctions vessel rows are 96% IMO-coded and 35% MMSI-coded. An MMSI-only design loses roughly two-thirds of cheap "is this hull on a list" hits. **measured**
4. **Cardinality is clean within a day, dirty in registries.** 1,503 Danish IMOs each mapped to one MMSI, and 1,344/1,345 AISStream IMOs did (the exception is the junk IMO `100000000` on two MMSIs). OpenSanctions lists 714 IMOs against 2 MMSIs, 37 against 3, 4 against 4, one against 9. GFW history has 66/221 IMO records with ≥2 self-reported MMSIs. **measured**
5. **Registry data is thin exactly where the build would need it.** Across 201 GFW records with both an AIS self-report and a registry row: **length null in 163 (81%)**, no owner in 30 (15%), flag differs 23 (11.4%), call sign differs 5 (2.5%), name differs 34/205 (16.6%) after normalisation. "Same hull, new name" is demonstrable from free data; "same owner" is not. **measured**

## 2. Findings

### 2.1 Source inventories and which keys each source actually offers

| Source (snapshot) | Records | Name | Call sign | IMO | Type/size | Notes |
|---|---|---|---|---|---|---|
| Danish AIS, 24 h, 2026-11-01 | 3,690 ships | 3,306 (90%) | 3,069 (83%) | 1,503 (41%) | type 3,042, length 3,073 | Class A only for IMO; 206 AtoN + 6 SART + 2 SAR aircraft + 1 PIRB rows to filter |
| Digitraffic `/vessels` (fetched 19:08 UTC) | 833 | 833 (100%) | 830 | 607 (73%) | shipType 818, dims via reference points | Static-record cache, **not** a track archive; also attaches IMO to 60/97 Class B records — impossible in raw AIS, so enriched from another register (**unverified** mechanism) |
| AISStream capture (~31 min) | 12,004 MMSI seen, 4,622 with static | 3,755 | 3,425 | 1,298 | type/dims from static | Class A 51% IMO, Class B 0% |
| Global Fishing Watch identities | 226 IMO records | via `selfReportedInfo` | yes | key | tonnage 97%, **length 19%**, owner 85% | Sample of tankers/cargo, not a fleet |
| OpenSanctions maritime | 23,833 rows = 20,989 vessel + 2,844 organisation | `caption` | no | 96% of vessel rows | flag (2-letter) | **Filter `type == "VESSEL"`**: org rows carry IMO company numbers (2,568/2,844 fail the ship check digit) |

All rows **measured** in the snapshot. OpenSanctions IMO strings are prefixed (`IMO9427366`) and MMSI is sometimes a `;`-list (396 rows), so a naive integer join fails silently.

### 2.2 Join rates

| Join | By MMSI | By IMO |
|---|---|---|
| Danish ↔ Digitraffic | 96/3,690 = 2.6% | 94/1,503 = 6.3% |
| Danish ↔ AISStream | 581/3,690 = **15.7%** | 100/1,503 = 6.7% |
| Danish ↔ OpenSanctions | 54/3,690 = 1.5% | 72/1,503 = **4.8%** |
| AISStream ↔ OpenSanctions | 103/12,005 = 0.9% | 41/1,298 = 3.2% |
| GFW sample ↔ OpenSanctions | — | 52/212 = **24.5%** |
| GFW sample ↔ Danish | 12/593 = 2.0% | 11/212 = 5.2% |
| GFW sample ↔ AISStream | — | 1/212 = 0.5% |
| GFW sample ↔ Digitraffic | 7/593 = 1.2% | — |

**measured.** AISStream and Danish cover Europe well enough to overlap heavily; GFW's identity universe is a tanker sample from three regions and barely touches either. Digitraffic keys almost perfectly when it has the ship but covers 2.6% of a Danish day — a national static cache, not a global key. GFW denominators are from the 201–214-record reads at 19:10 UTC (the file passed 226 records by the end of the run); the rates were stable across reads.

Danish ∩ OpenSanctions hits come mostly from `ua_war_sanctions` (31), `ext_tokyo_mou_psc` (21) and `ext_abuja_mou_psc` (8): an IMO join yields **"listed"**, mostly port-state detentions, not OFAC/EU designations. One hit is a plausible AIS typo — MMSI 257711000 (HOEGH ASIA) broadcasts `919187600`, the list has `9191876` — the case where MMSI and IMO joins give different answers.

### 2.3 Where fields conflict

| Comparison | Agreement | Disagreement | One side blank |
|---|---|---|---|
| Danish ↔ Digitraffic, name | 94 | 0 | 2 |
| Danish ↔ Digitraffic, IMO / call sign / length | 94 / 94 / 94 | 0 / 0 / 0 | 2 / 2 / 2 |
| Danish ↔ AISStream, IMO | 98 | 0 | — |
| Danish ↔ AISStream, name | 166 | 1 | 40 |
| Danish ↔ AISStream, call sign | 168 | 0 | 39 |
| Danish ↔ AISStream, length | 166 | 2 (130 vs 128 m; 16 vs 26 m) | — |
| AISStream ↔ Digitraffic, name | 46 | 0 | — |
| GFW self-report vs registry, name | 171/205 | 34 (16.6%) | — |
| GFW self-report vs registry, flag | 178/201 | 23 (11.4%) | — |
| GFW self-report vs registry, call sign | 196/201 | 5 (2.5%) | — |

**measured.** The single AIS↔AIS name difference is MMSI 265123000: "WWW.FURUNO.SE" vs "FURUNO SVERIGE AB" — one Swedish dealer typed differently, which a fuzzy matcher must treat as ignorance rather than evidence. GFW's name differences are part normalisation (`FS BITUMEN NO.2` / `FSBITUMEN2`), part real renames (`SAN FERNANDO` / `KOHZANMARU3`, `AEON` / `SELENE`, `SANMAR REGENT` / `CLIPPER HARALD`) — the "same hull, new name" story, at 17% of a tanker sample.

**Identifier validity.** MMSI that is not 9 digits or whose MID falls outside 200–799: Danish 237/3,690 (6.4%), but 204 are AtoN, 6 SART, 2 SAR aircraft and 1 PIRB — actual ships: Class A 14/2,545 (0.6%), Class B 10/930 (1.1%). Elsewhere 0.2% (AISStream 22/12,005 including one blank; Digitraffic 2/833; OpenSanctions 15/6,923). IMO check-digit failures: Danish 17/1,503 (1.1%), AISStream 49/1,298 (3.8%), GFW 0/226, OpenSanctions vessels 1/20,147. **measured.** Two pure functions — IMO check digit, MMSI MID plus class sanity — reject 1–4% of static records and remove AtoN/SART/PIRB from a "ship" table.

## 3. Change classification

Change rates belong to `id-frequency` and `id-shortterm`; this table classifies what each change does to a *join*.

| Change | Typical timescale | Likely causes | Rate, with denominator | Standard, noise or potentially malicious? | Effect on tracking | Effect on prediction | Suggested handling or flag | Evidence |
|---|---|---|---|---|---|---|---|---|
| IMO absent | persistent per ship | Class B cannot transmit one; Class A owners leave it 0 | 0/930 Class B vs 1,503/2,545 Class A (DK day); 1/2,083 vs 1,298/2,539 (AISStream) | Standard | No registry/sanctions join for ~44% of Class A and all Class B | Any IMO feature is class-biased | Store IMO nullable, branch features on class, never impute | measured |
| Same IMO, new MMSI | years to minutes (GFW's extreme case) | sale, reflag, transponder swap, GFW history merge | 0/1,503 IMOs on 2 MMSIs in one Danish day; 66/221 GFW records over years | Ordinary in history | Breaks MMSI-keyed continuity, not IMO-keyed | Training labels split across MMSIs | Keep a dated IMO→MMSI crosswalk; flag same-day collisions only | measured |
| Name differs | hours to years | normalisation, dealer/URL names, rename after sale | 1/167 shared MMSIs across AIS feeds; 34/205 GFW self-report vs registry | Mostly harmless; renames standard | Cosmetic if name is not a key | Name-keyed history resets create false "new ship" labels | Join on MMSI+IMO; names display-only | measured |
| Flag differs | months, at reflag | sale, open-registry move, registry lag | 23/201 GFW records (11.4%); MID sanity fails 0.2% elsewhere | Standard business decision | Registry flag and AIS MID are both right on different dates | Flag features drift with the fleet | Store flag as-of-date, never as a fixed attribute | measured |
| Registry row thin/missing | persistent | list derivation, coverage gaps | length null 163/201 (81%), no owner 30/201 | Coverage limit | Cannot size-match registry to radar for most hulls | Size features must come from AIS | Use AIS dims, record provenance | measured |
| Listed under another IMO | unknown | AIS typo, list typo, identity change | 1 case in 54 MMSI-level list hits (HOEGH ASIA, `919187600` vs `9191876`) | Mostly typo | Misses a real list hit | Missed positive label | Match on MMSI **and** IMO; validate check digit before matching | measured, n=1 |

## 4. What this means for us, given MMSI-only

- **The MMSI key is internally sound.** Zero IMO/MMSI collisions in a Danish day, near-perfect field agreement across two independent free feeds, 16% MMSI overlap between a Danish day and a half-hour global capture. A 24-hour MMSI-keyed tracker is not building on sand. **measured**
- **MMSI-only costs external breadth.** List-join recall falls from 4.8% to 1.5%, and the 930/3,690 Danish and 2,083/4,622 AISStream-static Class B records can never be IMO-joined. If "is this hull listed?" is in the pitch it needs **one nullable `imo` column beside the MMSI** — not a second identity, not identity-change detection.
- **Three cheap ingest guards:** IMO check digit (rejects 1.1% Danish, 3.8% AISStream static records); MMSI MID/class sanity (removes AtoN, SART, PIRB and malformed IDs — 6.4% of the Danish file as parsed); `type == "VESSEL"` filtering plus prefix/`;` parsing for OpenSanctions.
- **Cross-feed disagreement is rare; within-registry disagreement is the story.** The GFW self-report-vs-registry conflict rate (11–17%) is worth showing a judge, because that is the join behind any "same hull, new identity" claim.
- **Label hits honestly.** 4.8% of the Danish fleet is in OpenSanctions maritime, almost all as PSC detentions or Ukrainian war-sanctions entries; calling that "sanctions matches" would be wrong.

## 5. Unknowns, and how to settle them

- **Owner and true flag history.** Equasis and IMO GISIS are login-walled (homepages 200 with login/register, 19:11 UTC). ITU MARS `ShipStation/list` returns 200 with a WAF "Request Rejected" body to curl — browser-only. This wave forbids sign-ups, so ownership stays out; GFW `registryOwners` (85% present) is the only owner-ish field available.
- **Flag registers as substitutes.** `liscr.com` 200 but my search path redirected (302, empty); `register-iri.com` no response. Each is a manual form — an hour of browser work, not automation.
- **Digitraffic's IMO on Class B.** Mechanism unknown; check `meri.digitraffic.fi` v1 metadata for a `source` field before treating it as broadcast data.
- **Fleet-scale registry completeness.** My 226-IMO GFW snapshot is tanker-biased and was still growing; `id-frequency`'s full file settles whether 81% null length holds.
- **MMSI reallocation dates and reflag versus registry lag** — both need a dated registry (ITU MARS, Equasis).

## 6. Sources

- Danish AIS: `http://aisdata.ais.dk/aisdk-2026-11-01.zip` (local `$WAVE/data/t-ais-history/`), day 2026-11-01, 3,690 ships. **measured**
- Digitraffic: `https://meri.digitraffic.fi/api/ais/v1/vessels`, header `Digitraffic-User: hacketheburgh/feasibility`, fetched 2026-11-07 19:08 UTC, 833 records. **measured**
- AISStream capture: `$WAVE/data/identity/aisstream-capture.jsonl`, snapshot 17,202 messages / 12,004 MMSIs at 19:10 UTC. **measured**
- Global Fishing Watch identity records: `$WAVE/data/identity/gfw-identities.jsonl`, 226 IMO records at 19:10 UTC. CC BY-NC 4.0. **measured**
- OpenSanctions maritime: `https://data.opensanctions.org/datasets/latest/maritime/`, local copy 2026-11-07 16:31 UTC, 23,833 rows. CC BY-NC 4.0. **measured**
- Access checks 19:11 UTC: `gisis.imo.org/Public/Default.aspx` (login/register), `equasis.org/EquasisWeb/public/HomePage` (login), `itu.int/mmsapp/ShipStation/list` (WAF reject), `iuu-vessels.org/Home/Search` (200, ASP.NET form), `liscr.com` (302). **measured**
- Prior wave reused: `d-context.md` — Equasis/GISIS accounts, ITU MARS public form, TMT combined list has no machine-readable link. **measured by that agent**
