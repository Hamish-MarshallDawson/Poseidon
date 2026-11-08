# pr-targets: other prediction targets worth showing

Agent pr-targets, 8 Nov 2026 about 04:20 UTC. Read-only. Numbers are **measured** (Tiger, read-only sessions, 04:15 UTC),
**documented** (repo files), or **estimated** (marked).

## Recommendation

Pair route prediction with **go-dark risk** first, and **next port** second.

- **Go-dark risk** has labels in Tiger now, grades itself within hours from our own AIS, and the `scores` and `outcomes`
  tables already exist for it (`backend/dvm/store.py`). It is also the one target Jake's `score.py` already plans, so
  it costs the least, and the loop (predict, grade, retrain, skill over baseline) runs live in the demo.
- **Next port** is the best second story: a different question, graded by data we already hold (GFW port visits,
  91,886 in the last 60 days), and it has a built-in baseline to beat (the ship's own AIS destination field).
- Treat **reappearance location** as part of route prediction, not a separate target. Do not build rendezvous risk or
  identity-change prediction before 09:00; show them as detections only.

## What Tiger holds (measured)

| Thing | Count |
|---|---|
| Our positions | 2.49 M rows, 42,212 ships, 7 Nov 16:51 to 8 Nov 04:11 UTC; 27,702 Class A ships in the last 24 h |
| Gap versions in `gaps` (all `src=derived`, 0 from GFW) | 8,625; latest state per gap: 3,538 gaps, 957 closed |
| Closed `deliberate_candidate` gaps | 176 (all 176 have the reappearance point `next_lat/lon`); median 78 min, 90th percentile 159 min; median implied speed 3.3 kn |
| Ships that ever had a `deliberate_candidate` gap | 904 of 27,702 Class A in 24 h (about 3.3%) |
| Other closed gaps | `unknown` 472, `coverage_gap` 229, `own_stall` 84 |
| Statics rows with an IMO | 160,669 rows, 16,482 IMOs, 51,978 MMSIs |
| GFW `port_visit` (2012 to 3 Nov) | 202,289; 91,886 in the last 60 days, each with MMSI, start and end port, duration |
| GFW `encounter` / `loitering` | 44 / 5,072 rows (3,165 loitering in the last 60 days) |
| GFW gap events | 0 rows (issue #112 in flight) |
| `scores` / `outcomes` | empty |

Caveat on the gap labels: the detector only began on 7 Nov, and most gaps are still open (the 24 h expiry). Closed gaps
are biased to short ones, so any go-dark label rate computed now is a lower bound.

## Targets compared

| Target | Labels and data we have | How delayed data grades it | Effort to a first version | Demo value |
|---|---|---|---|---|
| **Go-dark risk next N h** (N = 1, 6, 24) | Positive: our gaps (176 closed `deliberate_candidate`, plus open ones that passed the 30 min limit); GFW gap events when #112 lands (worldwide, flag `intentional_disabling`). Negative: Class A ships heard throughout (27,702/day). Features from live AIS: speed, nav status, area reception, past gaps, time of day, flag, ship type | Fast: our own detector, within N h, no delay. Delayed: GFW gap events about 4 days later confirm or find missed gaps (also catches ones we could not see) | 3 to 4 h with gradient-boosted trees on tabular features (estimated). Overlaps `score.py`; ask Hamish on the board before touching `scores` | **High.** Live ranked list, outcomes shown within hours, calibration plot |
| **Next port / destination** | Labels: GFW `port_visit` end port per MMSI. Baseline: AIS `destination` text, present for 9,229 of 9,857 cargo and tanker ships (type 70 to 89) in 24 h (94%), but free text ("ROTTERDAM", "FOR ORDERS") and needs mapping to GFW port ids | Delayed: port visit about 3 to 4 days (GFW), graded as top-1 or top-3 accuracy and as "ETA error" | 4 to 6 h: port-name matcher plus classifier over last-known position and heading; or only grade the AIS destination field (1 to 2 h) | **Medium-high.** Easy to explain, graded by independent data. Risk: the destination field alone is strong, so skill over it may be small |
| **ETA** | `eta_utc` in statics: 155,516 of 690,076 rows in 24 h (23%). Arrival time from port visit start | Delayed with port visits; error in hours | 3 h on top of next port | Medium. Only meaningful with a port target; self-reported ETAs are often stale (estimated) |
| **Rendezvous / ship-to-ship risk** | Only 44 GFW encounters in two months, 5,072 loitering. Nothing from our own detector yet (flag not built) | GFW encounters, 3 to 4 days | 6+ h, too few positives to train. Could only be a rule | Low-medium as prediction, high as a detection layer |
| **Identity change (same IMO, new MMSI)** | 34 IMOs with more than one MMSI in statics, but several are junk IMOs (1, 103, 1111111). 275 MMSIs with more than one name. The research wave found 29 to 38 of 40 sampled silent tankers returned under another MMSI (documented in `SYNTHESIS.md`) | Same IMO re-appearing under another MMSI in later statics or GFW. Cannot tell a sale from evasion | Detection 2 h; prediction not credible in 5 h | Detection only; high wow, no honest prediction |
| **Reappearance location** | The 176 closed gaps give the true point; GFW gap events add worldwide pairs | Exactly the route-model target (end of a gap) | Same as route model | Same as route model, so fold in |

## Why go-dark risk first

1. The plan's loop needs a target that closes during the demo; this one does. A prediction made at 06:00 for the next
   6 h is graded by 12:00. Route-through-dead-zone grading takes days (GFW) or only works in Danish waters.
2. Training rows exist now: about 3,500 gaps and 27,702 ships at risk; the 6 h label rate is estimated at a few percent,
   which is workable for gradient boosting with class weights.
3. The leakage rule is simple: build features only from positions with `recv_ts` before `made_at`; use `as_of` and
   `available_ts` for any GFW label.
4. Key trap to state in the demo: `deliberate_candidate` is the detector's guess, not intent. Wording stays "possibility
   of going dark", as the team agreed (documented in `research/NextSteps/flag-and-prediction-next-steps.md`).

## Risks

- **Circularity:** go-dark risk graded by our own detector learns the detector's rules (30 min floor, neighbour count).
  Mitigation: also grade against GFW gap events once #112 lands, and report the skill over a simple baseline
  (base rate by area and ship type).
- **Small and young label set:** seven hours of detector output. Use time-based splits and report confidence intervals.
- **Port matching:** AIS destination text needs cleaning; budget 1 h for it or cut to top-level country or region.
- **Overlap with Jake's `score.py`:** same table, same target. Coordinate via Hamish so we write to `scores` with a
  distinct `model_version` and do not duplicate his feature set.

## What to build first (in order)

1. Label view: one row per (mmsi, `made_at`, horizon) with `gone_dark = exists a gap starting in (made_at, made_at+N]`,
   excluding ships already in a gap at `made_at`. (1 h)
2. Gradient-boosted trees (LightGBM) on tabular features, 3 horizons, time-split by hour, baseline = area base rate.
   Write predictions to `scores`, and the fast grader to `outcomes`. (2 to 3 h)
3. Port-visit grader for AIS destination text as the next-port baseline, shown as a table; model only if time remains.
4. Add the GFW gap events as delayed grading as soon as #112 lands.

## Open questions for Aiden

1. Is Jake's `score.py` the owner of go-dark risk, or does your side write the model and he writes the UI/API? Needs one
   board post through Hamish.
2. Should go-dark risk count only `deliberate_candidate` gaps, or all non-reception gaps (`unknown` included, which is
   73% of gaps, mostly open sea)? I recommend `deliberate_candidate` plus GFW `intentional_disabling` once available.
3. Is next port worth the hour for destination cleaning, or should the second target be a simple rendezvous rule layer?
