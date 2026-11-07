# id-frequency: how often ship identity actually changes

Agent `id-frequency`, ship identity wave. Everything below is `measured` by me on the orchestrator's
Global Fishing Watch sample unless labelled otherwise. **Frozen snapshot: 429 IMO records read 19:13 UTC
2026-11-07**, copied to `$WAVE/data/id-frequency/gfw-identities-snapshot-1913.jsonl` so the numbers
reproduce after `gfw-identities.jsonl` stops growing. The live file held 4 records when I started, so
this is one point in a growing sample. Scripts:
`$WAVE/scripts/id-frequency/final.py` (headline numbers, takes a path) and `freq.py`-`freq4.py` (working
steps, including two errors I found and fixed — see Data artefacts).

## Bottom line

1. **Rare per ship-year, normal per ship lifetime.** 794 identity starts in 5,274 ship-years = **0.151
   per ship-year**; sequential MMSI switches alone are 0.090. Only 28% of ships never change identity in
   their record; 72% change at least once, over a median span of 14.8 years.
2. **A switch is instantaneous.** 78.4% show ≤1 hour between the old MMSI's last transmission and the
   new one's first, 89.3% ≤24 hours, 97.5% ≤31 days (median 0.15 h, p90 31 h; n=476). An identity change
   produces **no usable gap**.
3. **Name and flag move with the MMSI.** 62% of switches change MMSI, name, flag and call sign together;
   33% keep the name and change the rest (in-place reflag); 1.5% change MMSI alone. Only 16 of 1,156
   MMSIs (1.4%) ever carried two names, and across a 24 h Danish day `id-flags` found 1 name change in
   1,372 MMSIs (a typo fix). **The name is stable while the MMSI is stable**, so a changed name
   evidences a changed identity, not a noisy field. Reflagging also *requires* a new MMSI by rule
   (ITU-R M.585-10 Annex 3 §1(c), `documented` via `id-causes`), so MMSI churn at a sale is standard
   practice.
4. **Flag is not independent evidence.** Flag changed at 461 of 476 switches and never without an MMSI
   change; 97% of switches cross a country (MID) boundary. GFW derives flag from the MMSI's MID, so
   "name and flag both changed" counts one event twice.
5. **Churn is concentrated, not Poisson.** 8.4% of ships (36/429) have 3+ identity starts inside some
   365-day window, where a Poisson process at the pooled rate predicts 0.05%. The top 10% of ships hold
   36% of all starts. A naive "identity changed" alert fires **0.25 times per day at 1,000 ships**
   (0.00025 per ship-day).

## Findings

**Sample.** `identity_gfw.py` draws, per box (Hormuz, Malacca, Danish), up to 150 random tankers, 100
random cargo ships and 80 "silent" tankers (last transmission ≤ 2026-08) from GFW
`public-global-presence` for **February 2026**, keeping vessels with an IMO, seed 20261107. The
denominator is *ships with an IMO in those boxes in February 2026*, not the world fleet: 429 records
(200 random tankers, 132 cargo, 97 silent tankers; 155 Malacca, 140 Danish, 134 Hormuz), 5,274
ship-years, 1,223 de-duplicated identity periods, 1,156 MMSIs.

**Changes per ship-year**

| Measure | Pooled | Random tanker | Random cargo | Silent tanker |
|---|---|---|---|---|
| Sequential MMSI switches / ship-year | 0.090 | 0.073 | 0.066 | 0.150 |
| Name changes / ship-year | 0.058 | 0.050 | 0.040 | 0.095 |
| Flag changes / ship-year | 0.087 | 0.071 | 0.062 | 0.147 |
| Identity periods per ship | 2.85 | 2.41 | 2.37 | 4.41 |
| Ships | 429 | 200 | 132 | 97 |

By region: Malacca 0.070, Danish 0.092, Hormuz 0.111 switches per ship-year. **The group effect
dominates the region effect**: silent tankers churn roughly twice as fast as random tankers and 2.3×
cargo, and that held in each region separately on the 335-record read. Silent tankers carry 4.4 identity periods on average
against 2.4.

My denominator is ship-years of observation, first to last transmission. `id-flags` computed 0.265
changes per ship-year from the same file on a different denominator (summed identity-period lengths,
which ignores years the hull was not transmitting); per record the two agree, at 1.82 versus 1.85
identity starts per ship. Quote the rate with its denominator.

**By calendar year** of the new identity's first transmission (ship-years from overlapping spans):

| 2013-2019 | 2020-2023 | 2024 | 2025 | 2026 (to 5 Nov) |
|---|---|---|---|---|
| 0.03-0.07 | 0.06-0.10 | 0.16 | 0.15 | 0.23 |

Consistent with the reported 2024-2026 reflagging surge, but **not a clean trend measurement** (Unknowns).
The 2012 bump (0.09) is left-censoring: GFW AIS starts in 2012, so first periods often start 2012-01-01.

**Timing between identity periods** (n=476; gap = new MMSI's first transmission minus old MMSI's last):

| ≤1 h | 1-24 h | 1-30 d | 30-365 d | >365 d |
|---|---|---|---|---|
| 78.4% | 10.9% | 8.2% | 1.7% | 0.8% |

Identity changes are book-kept transitions, not silences: the transponder returns within the hour.

**Share of ships changing inside a window** (end of each ship's own record; denominator 427 ships with
span ≥1 year): 1 month 11 ships = 2.6%; 3 months 42 = 9.8%; 12 months 129 = 30.2%.

**Three or more starts inside one 365-day window: 36 of 429 ships = 8.4%** (max starts per year: 1 → 287
ships, 2 → 106, 3 → 26, 4 → 7, 5 → 1, 6 → 1, 9 → 1). Poisson at 0.151/ship-year predicts 0.2 ships, so
churn is clustered: 118 ships (28%) never start a second identity. Period durations: n=1,223, median 902
days, 6.5% under 30 days, 33.2% under a year.

**"On air together".** 318 of 1,223 periods (26%) start while another MMSI of the same IMO was still
transmitting, on 172 of 429 ships (40%). Their own durations: median 224 days, 17% under 30 days, 4%
under a day, 41% over a year; 41% share the parent's name. This bundles brief handover
double-broadcasts with long parallel records that are a matching or self-report artefact — a mis-set
MMSI, or two hulls reporting one IMO. Dates cannot separate them; raw AIS can (two MMSIs at different
positions at the same instant means two hulls or two boxes), which is `id-shortterm`'s question.

**Silent tankers reproduce the earlier finding.** Of 97 sampled silent tankers, **78 (80%) have an
identity that stopped by 2026-08-01 and another MMSI of the same IMO transmitting afterwards**, always a
different number. That matches the brief's 29/40, 31/40, 38/40 (72-95%) at IMO level on a different
sample. These ships were selected on having gone quiet, so it is not a rate for tankers generally.

**Data artefacts I had to fix** (`id-causes` and `id-flags` hit the same two independently):

- **One IMO returns several GFW identity groups.** 263 of 429 records had ≥2 (registry-matched and
  `NO_MATCH`), repeating overlapping slices of the same MMSI history. Counting without de-duplicating by
  (ssvid, name, flag, callsign, nShipname) inflates switches ~15% and manufactures "overlaps".
- **An MMSI is not one time window.** 13 of 429 ships returned to an MMSI used years earlier. `final.py`
  gives each new period the predecessor that was on air latest; the rest count as concurrent.
- **Record ends are pinned to data freshness** (AIS 2026-11-05, registry 2026-09-30), so "still
  transmitting on 5 November" is a ceiling, not a ship-specific fact.
- **A placeholder IMO can pass the check digit.** IMO `1234567` returned **27 periods across 25 MMSIs**,
  mostly Vietnamese small craft; 0 of 429 sampled IMOs failed the check digit.

## Change classification

| Change | Typical timescale | Likely causes | Rate, with denominator | Standard, noise or potentially malicious? | Effect on tracking | Effect on prediction | Suggested handling or flag | Evidence |
|---|---|---|---|---|---|---|---|---|
| MMSI switch | median 9 min; 97.5% within 31 d | sale/reflag, re-registration, transponder swap, mis-set MMSI | 0.090/ship-year sequential, 0.151 with side identities; 5,274 ship-years | ordinary for tankers and old tonnage; sale and evasion look alike in AIS | splits one hull into two tracks, no gap | history reset; double-counted hull | treat as **re-identification**, not an event | measured here |
| Name change | same instant as the switch in 62% | sale, rebrand, reflag | 0.058/ship-year; 16/1,156 MMSIs held two names | ordinary; within-MMSI churn is noise | breaks name joins and display history | name-keyed features reset | join on MMSI, carry last name | measured here |
| Flag change | same instant as the switch in 97% | reflag on sale | 0.087/ship-year; never without an MMSI change | ordinary | none beyond MMSI | none beyond MMSI | never score separately | measured here |
| Side identity (two MMSIs on air) | median 224 d; 17% under 30 d | handover, mis-set MMSI, two hulls on one IMO | 318/1,223 periods (26%) on 172/429 ships | mostly artefact or ordinary handover | ambiguous which track is the hull | duplicate rows | log only; escalate if names or IMOs differ | measured here |
| Placeholder IMO | years | placeholder entry, mis-keyed IMO | IMO 1234567: 27 periods, 25 MMSIs; 0/429 bad check digits | noise, occasionally deliberate | one IMO, many ships | poisoned rows | reject `1234567`, `0000000`, >2 IMO-holders/day | measured here, `id-joins` |

## What this means for us, given MMSI-only

- **MMSI-only is defensible inside 24 hours.** `id-joins` measured 0 IMOs on more than one MMSI across
  1,503 ships in a Danish day, and a switch takes minutes, so the chance a tracked ship swaps MMSI during
  the hackathon is low: 0.00025 per ship-day → **0.25 ships per day at 1,000 ships**, 1.2 at 5,000.
- **The cost lands on history, not the live map.** 30.2% of ships changed identity in the last 12
  months of their own record. Anything learning from a ship's past — "went dark before", behaviour
  baselines, forecast evaluation — loses the thread at the switch without IMO.
- **The cheapest fix is linkage, not detection.** Store IMO when present (Class A only: `id-joins`
  measured 51-59% of Class A, ~0% of Class B); when a new MMSI appears under the same IMO, link the
  tracks and record the gap as *unknown*, not *dark*. One field and one join.
- **Do not alert on MMSI change alone.** It fires 0.25 times a day per 1,000 ships for nothing, and the
  2024-2026 rate is 2-4× the 2013-2023 rate, so thresholds tuned on older history under-fire. A
  defensible flag needs shape: a change within hours of the last position before a multi-day gap, 3+
  starts in 12 months (8.4% of ships ever), or a 20-day-old identity on a 15-year-old hull.
- **Recommendation: leave the build as it is, add one small flag to the pitch.** "This track's IMO has
  transmitted under another MMSI", with the base rates above, is defensible. The strongest pitch line is
  the silent-tanker re-appearance rate (80% here, 72-95% earlier), not "ships hide by changing MMSI",
  which is common and mostly ordinary.

## Unknowns, and how to settle them

- **Sale versus evasion.** AIS cannot say. Needs ownership history (Equasis is login-walled per
  `id-joins`) or GFW `registryOwners`: present for 345/429 ships but as a single latest record, 415 registry
  records for 1,223 AIS periods, 20% of ships with none. Settle by checking owner change for 30 sampled
  switches.
- **Whether the 2024-2026 rise is real.** Confounded by GFW's improving identity resolution,
  survivorship (present in February 2026) and the partial 2026 year. Settle with a fixed 2015 cohort and
  a denominator not conditioned on 2026 presence, or a second source (Danish daily files).
- **Whether side identities are two transmitters or two hulls.** Needs raw AIS with simultaneous
  positions (`id-shortterm`).
- **Long tails.** One ship has 27 periods (the placeholder IMO); one Danish workboat changes MMSI
  annually by design. Trim the top 1% and re-run `final.py`. This is also **not a world rate**: three
  boxes, ships with an IMO, February 2026.

## Sources

- `$WAVE/data/identity/gfw-identities.jsonl` via GFW `public-global-vessel-identity:latest`
  (`vessels/search?where=imo='…'`, includes OWNERSHIP and MATCH_CRITERIA), sampled by
  `$WAVE/scripts/orchestrator/identity_gfw.py`; my frozen copy
  `$WAVE/data/id-frequency/gfw-identities-snapshot-1913.jsonl`. Global Fishing Watch data is
  CC BY-NC 4.0.
- My scripts: `$WAVE/scripts/id-frequency/final.py`, `freq.py`, `freq2.py`, `freq3.py`, `freq4.py`.
- Cross-references from `identity/shared-notes.md` (same wave): `id-joins` on IMO/MMSI cardinality,
  Class A/B IMO coverage, OpenSanctions joins and registry access; `id-fuzzy` on AIS 6-bit name
  artefacts (its `',NDI IPSA'` → `BINDI IPSA` case also appears in my panel, IMO 9593517); `id-causes`
  for ITU-R M.585-10 and Lloyd's List public figures.
- Quoted, not re-measured: the 29/40, 31/40, 38/40 silent-tanker samples and AISStream static-data
  counts (orchestrator, `SYNTHESIS.md` and the brief).
