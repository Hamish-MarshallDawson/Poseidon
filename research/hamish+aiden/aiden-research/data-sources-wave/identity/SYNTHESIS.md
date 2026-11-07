# Ship identity wave: synthesis

Saturday 7 November 2026, about 19:40 UTC. Eight DeepSeek agents, plus the orchestrator's own checks. Evidence for the team, not a decision. Identity changes here are observations in public data, and don't show why a ship changed or that anyone did anything wrong. "Checked" means the orchestrator reproduced it; other figures are the agents'.

## Answer

**Jake's MMSI-only decision holds for the live 24-hour build. Identity change is a slow, history-level event, not a short-term tracking problem.** The real costs are in historical analysis, training data and sanctions matching, and a few small changes that need no identity table would cover most of them.

**Recommendation for Aiden and Jake: the small tweak, with identity-change detection left out of the build.** A separate pitch study stays optional.

## How often each thing changes

| Change | Timescale | Rate | Evidence |
|---|---|---|---|
| **New MMSI, last 12 months** | Mostly around a sale or reflag | **14% of random cargo ships, 20% of random tankers**; Hormuz tankers 26%, Danish tankers 15% | Checked, 300 and 450 ships |
| **New name, last 12 months** | Usually with a new MMSI | 7% of cargo, 12% of tankers | Checked |
| **Two or more new MMSIs in 12 months** | Repeat changers | 2% of cargo, 6% of tankers | Checked |
| **Three or more new MMSIs in 12 months** | Rare | 0.7% of cargo, 1.1% of tankers | Checked |
| **Lifetime average** | Years | About 0.09 to 0.15 identity starts per ship-year, varying with method | Agent, 5,274 ship-years |
| **Same MMSI with two IMOs, within a day** | Should not happen | **0 in a full Danish day; 0 of 5,779 in 26 minutes worldwide** | Checked for the capture; three agents for Danish |
| **Same valid IMO on two MMSIs at once** | Should not happen | **0 of 5,779** in the capture after removing placeholders | Checked; short window |
| **Name differs on the same MMSI, within a day** | Noise or rename | 4 of 11,554 worldwide in 26 minutes; 0.72% of ships show a changed static string over a Danish day | Checked; agent |

- **Silent tankers are a selected group, not a rate:** 82% of tankers that had stopped transmitting under one identity had a new MMSI in the last 12 months. It shows that "silent" often means "changed identity".
- **Expected daily volume:** about 0.25 to 0.9 changes a day per 1,000 ships, depending on fleet. Zero observed in a day is what these rates predict, so it doesn't mean changes never happen.
- **Limits:** samples are ships present in three regions in February 2026, and Global Fishing Watch periods are its reconstruction. Danish evidence is one day.

## How changes happen

- **Almost all are switches, not gaps.** About 80% of MMSI switches had an hour or less between old and new, or overlapping records (checked). So an identity change usually produces no usable gap. Overlaps may be partly data artefacts.
- **Flag and MMSI move together by rule.** ITU guidance requires reassigning the MMSI when the flag changes (agent, documented). All 693 flag changes in one sample also changed MMSI. Global Fishing Watch derives flag from the MMSI, so "flag and MMSI both changed" is one event, not two pieces of evidence.
- **IMO is meant to be permanent.** It's designed to survive sale, rename, reflag and scrapping. A different IMO on a real hull isn't a routine ownership change, but we can't verify hull identity from AIS.
- **Ordinary and deliberate changes look alike field by field.** Lloyd's List reports that 36% of cargo ships sanctioned in 2025 reflagged, 45 days after designation on average, against 267 days for 2018 (agent, press).

## Noise, ordinary or suspicious

These are proposed starting points. Only the base rates are measured, and they have not been validated against known outcomes.

| Level | Example | Handling |
|---|---|---|
| **Noise** | Spacing, punctuation, Roman numerals, 20-character cut-off; buoys and fish-farm gear writing status text as names; type, size and destination edits | Normalise or log. Never flag |
| **Ordinary** | One new MMSI and flag with the same IMO; a name change on a stable MMSI | Log. Note "same IMO, new MMSI" if shown |
| **Worth a look** | New MMSI within 72 h of at least 24 h silence, same valid IMO | Lead, with alternative explanations |
| **Lead** | Three or more identities in a year; repeat flag changes; switch soon after designation | Lead; needs ownership and registry check |
| **Strong lead** | Same valid IMO on two moving MMSIs for at least 1 h; published scrapped or unbuilt IMO | Lead with raw messages; never "fraud" from AIS alone |
| **Bad data first** | Impossible jumps, invalid IMO, unallocated MMSI country code | Clean first. Most are errors or special devices |

**Wording:** "identity fields changed; this could be a sale, a reflag, an equipment fault or an attempt to avoid tracking, and we can't tell which." Avoid "spoofing", "dark vessel" or "evasion" from identity data alone.

## Typos and fuzzy matching

- **Names:** 83% of 599 name differences between AIS and registry records are formatting (agent). Simple normalisation removes most of them.
- **Fuzzy matching is unsafe for ship names.** Normalised equality had precision 1.00 and recall 0.55 to 0.62; a Levenshtein ratio of 0.85 or more had precision 0.62 and recall 0.69 on 52 hand-labelled pairs (agent, small sample). 4 to 9% of distinct-ship pairs sharing a prefix exceed common similarity thresholds, and 6.5% of named vessels share a name with another MMSI in one Danish day.
- **MMSI changes are not typos:** 83% change the country code and 90% differ by four or more digits. Don't fuzzy-match them. Only 2% of name pairs were typo-like.
- **IMO:** 39% of `ShipStaticData` messages have IMO 0 and 1.4% are invalid or placeholders (checked). The check digit catches typos, not fraud, because both published fake IMOs pass it. Reject `0`, `1`, `1234567`, `100000000` and `999999999` before any join: unrelated ships share them.

## Fake and bogus IMOs

- **Size:** Lloyd's List counted 28 ships transmitting scrapped-ship IMOs in February 2025, and 46 IMOs in December 2025 against 19 a year earlier. Windward reports 49 zombie tankers of 1,358 tracked in August 2026, or 3.6% of its shadow-fleet list (press and vendor claims, agent). None of this is a rate for all ships.
- **Free data shows matching chains.** `id-imo-fraud` reports that Global Fishing Watch reproduces 6 of 7 published cases. The orchestrator saw the same shape for those IMOs: for example, a ship name ending in 2018, then new names under the same IMO from 2024 or 2025. Reading the published articles themselves was limited to public text.
- **Chain shape alone proves nothing.** Confirming a scrapped or unbuilt ship needs registry or demolition records. "Still transmitting after its last registry record" fired on 98% of ships, so it's useless with these snapshots.

## Effect on the platform

| Area | Within 24 hours | Over history and training |
|---|---|---|
| **Live tracking, map** | Safe. No MMSI took a second IMO in the Danish day or 26-minute capture | Hull split across MMSIs |
| **Gap detector** | Handovers don't cause gaps: 0 of 776 Danish gaps with an IMO were a key change. Reception is the bigger problem | 413 of 1,619 handovers would leave a detectable gap |
| **"Went dark before" feature** | Little effect | **A real weakness:** 10% of handovers follow more than 7 days' silence and look like a disappearance plus a new ship |
| **Sanctions match** | **Weaker now:** on the Danish day 72 ships match by IMO against 54 by MMSI. Of the 76 in total, 22 need IMO. Using only `sanction` and `mare.shadow`, 34 by IMO and 25 by MMSI, with 9 needing IMO (checked) | History stored on the MMSI dies with it |
| **Name display** | Can flip between spellings across sources or from noisy transmitters | Use a name valid at the time |
| **Prediction evaluation** | Little effect | Split train and test by hull where possible, or one hull can land on both sides |

**One correction to the wave:** `id-shortterm` reported ships jumping thousands of km to inland Asia. That was a misread of grid cells. On the Danish day, after cleaning, 35 of 3,461 MMSIs (1.0%) had a jump over 60 knots and 5 km, 14 over 100 km and 1 over 1,000 km (checked). Causes are unresolved. Those positions should be filtered before any speed or spoof test.

## Recommended small tweak

None of this needs an identity table, or a change to MMSI as the key. These are proposals for Jake and Hamish:

1. **Use a validated IMO for sanctions matching,** falling back to MMSI. This is the one change with a measured benefit in the live build. Label results honestly: most OpenSanctions hits are detentions.
2. **Normalise names** for comparison, while displaying the broadcast name.
3. **Filter junk before use:** placeholder IMOs, non-ship MMSIs, latitude 91 and 0/0 positions.
4. **Keep a store of `(mmsi, imo, name, flag)` per static change,** so history can be linked later without any change now.
5. **Optional display note:** "same IMO seen earlier under another MMSI", as a side note, not a detector.
6. **If history is used for training,** group evaluation by valid IMO where available.

## Optional pitch study

Worth considering only if the team wants the angle. It's about half a day and separate from the build:

- Hand-label about 200 Global Fishing Watch transitions as sale, reflag, rename, typo or unexplained.
- Include the published scrapped-IMO cases as a worked example.
- Run the "same IMO on two MMSIs" test over several days.

The honest claim: "identity change is common and mostly ordinary; here's the base rate, the rare unexplained class, and our false-positive budget." Without ownership data, sales and evasion can't be reliably separated. Equasis, GISIS and demolition lists are the next data to try, and the first two need free accounts.

## Open questions

- Hormuz and Malacca short-term behaviour, because no free full-day feed exists there.
- Causes of the position jumps.
- How much of the overlap in Global Fishing Watch periods is real.
- How many identity changes are ordinary sales.
