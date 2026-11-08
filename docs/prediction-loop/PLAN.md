# Prediction loop: plan and decisions so far

Aiden and his backend integrator agent, 8 Nov 2026, from about 02:30 UTC. Issue #113. Feature freeze 09:00 UTC.
This is the working plan: it changes as research comes back. Decisions are marked **Decided**; the rest is open.

## The concept (Aiden)

Train a model on historical data to predict where a ship goes, mainly through areas where our live AIS can't see
it. Run it live on the AIS we receive. When delayed data arrives (satellite and archive data, days later), grade
each prediction against what really happened, add the graded cases to the training data, retrain, compare models
automatically, and keep the best. Gemini reads the evaluation results and proposes the next training runs. For the
hackathon, show that the loop works and improves, even if it can't run for weeks.

## What the data can and can't do (checked in Tiger and against GFW, 02:48 to 03:45 UTC)

| Source | What it gives | Grades a route? |
|---|---|---|
| Our live AIS (AISStream worldwide, Digitraffic for Finland) | Full tracks while ships are in range of shore receivers; since 16:51 on 7 Nov | Yes, when a dark ship reappears (hours) |
| Danish AIS archive (research wave; not ingested yet) | Complete tracks from many receivers, about 3 days late, back to 2007, Danish waters only | **Yes, the whole route** |
| GFW gap events (worldwide) | Per ship: where AIS went off and came back on, duration, implied speed, intentional-disabling flag, satellite reception | **Yes, both ends of a gap** |
| GFW AIS presence (includes satellite AIS) | 0.01 deg cells (anonymous), or per-ship daily totals per region; per-ship positions return 404 | Coarse only (was it in the region that day) |
| GFW radar detections | Anonymous cells per day, matched or not to AIS; for matched ships the time but no position | Coarse checkpoints |
| Sentinel-1 footprints (25k rows, 2020 on) and raw images (not ingested) | Where and when radar imaged; ship returns if we run a detector | Snapshots a few times a week at the coast |
| GFW port visits (2012 on) | Per ship, by MMSI and IMO | Checks destinations |

- **The research-wave matching** (data-sources-wave/SYNTHESIS.md): one Sentinel-1 pass on 1 Nov, 94% (Great Belt)
  and 88% (Fehmarn Belt) of moving ships of 50 m or more matched within 500 m, against 13 to 23% by chance. It shows
  radar confirms ships are where AIS says at the moment of a pass. It does not follow ships through dead zones.
- **Continuous routes outside shore range** exist only as commercial satellite AIS. GFW has it but only shares
  grids and events.
- **GFW gap events are missing from our database** (0 rows): every query limited to our regions returns 0, while
  worldwide queries return thousands a week. Issue #112.
- **GFW history so far:** back to late August 2026, at about 3 min per day for all four regions. Issue #111.

## The loop, as it can work on free data

1. **Train** on historical tracks, cut into "here now, where in 1, 3, 6, 24 h" examples (Danish archive), plus GFW
   gap off/on pairs (dead-zone cases worldwide), checked against port visits.
2. **Predict live** from our AIS into an append-only predictions table (model version, time made, ship, horizon,
   point, uncertainty).
3. **Grade:**
   - fast: when the ship reappears in our own AIS (hours; closes during the demo);
   - delayed: Danish archive about 3 days later (exact route error in Danish waters); GFW gap events about 4 days
     later (true reappearance point anywhere); radar passes as occasional checkpoints.
4. **Learn:** graded cases join the training data.
5. **Evaluate:** time-based splits (never train on the future; `as_of` and `available_ts` already enforce what was
   known when), a fixed held-out set, every model reported as skill over the baseline of continuing at the last
   course and speed. A challenger replaces the current best model only if it beats it on the same held-out set.
6. **Gemini** reads the evaluation results and proposes the next runs from an allowed list of settings. Promotion is
   decided by the numbers, never by Gemini.

**Demo scope:** exact route grading in Danish waters; gap-end grading elsewhere. The 3 to 4 day loop can't close live
before 09:00, so it is shown as a time-machine backtest (pretend it is a week ago, predict, grade against what has
arrived since).

## Zones: protected areas and national-waters borders (Hamish's "Possible illegal fishing" idea, checked 04:40 UTC)

- **GFW fishing events** (`public-global-fishing-events:latest`) work for our regions: 526 events in 1 to 8 Oct in
  the Danish straits, 32 in the Gulf of Oman. Each carries `regions` (`eez`, `eez12Nm`, `mpa`, `mpaNoTake`,
  `protectedseas`, `rfmo`, `highSeas`), and `fishing.potentialRisk` and `vesselPublicAuthorizationStatus`. 102 of 200
  sampled Danish events were inside a protected area. About 3 to 4 days late, like the rest of GFW.
- **EEZ shapes:** Marine Regions WFS (`geo.vliz.be`, CC BY 4.0) returned the 7 EEZs touching the Danish box in 5.7 s
  (33 MB unclipped). Its `mrgid` matches GFW's `eez` tags (5674 Denmark, 5694 Sweden), so live zone tags and GFW labels
  share one id system.
- **Protected-area shapes:** the World Database on Protected Areas map service (UNEP-WCMC) answers bbox queries: 662
  non-terrestrial sites touch the Danish box, 24 in Hormuz plus the Gulf of Oman. Its `no_take` filter returned 0, so
  use GFW's `mpaNoTake` tag for no-take status. Licence: free for non-commercial use with attribution (to confirm).
- **How it ties into prediction:**
  1. Live detection layer (Hamish's filter): tag each live ship with its EEZ, any protected area it is in, and its
     distance to the nearest EEZ border; flag fishing-type ships at fishing speeds inside protected areas, and gaps
     that open near a border.
  2. Features for go-dark risk and route models: inside a protected area, distance to the border, EEZ changes along
     the path.
  3. Predicted incursion: a dark ship's predicted cone crossing a protected area or another country's EEZ becomes an
     alert with a probability.
  4. Delayed grading and labels: GFW fishing events, tagged with the same zones, confirm 3 to 4 days later whether the
     ship fished there, the same predict-now, grade-later loop; historical events (with `potentialRisk`) are labels
     for a fishing-risk target.

## Work in flight

| Who | What | Issue |
|---|---|---|
| Opus agent `gfw-month` | GFW timings, month-range requests split per day, equality tests | #111 |
| Opus agent `gfw-parallel` | Safe concurrency against GFW, regions in parallel, `--workers` by date range | #111 |
| Opus agent `gfw-gaps` | Fetch GFW gap events from wider queries, keep those touching our areas, backfill | #112 |
| Sonnet research wave (4) | Model options, data sources, evaluation and autonomous loop, other prediction targets | #113 |

Briefs are in `docs/handoffs/`. Research reports land in `docs/prediction-loop/research/` once reviewed.

## Decided

- **Decided:** Aiden's side takes over training and the database (Aiden, 8 Nov).
- **Decided:** one `.env` in the primary checkout, linked into every worktree on the desktop and copied to the laptop.
- **Decided:** speed up the GFW backfill (month-range requests and parallel workers) and fix gap events first, in the
  background, while the prediction plan is researched.
- **Decided:** training and inference run on Hamish's desktop (RTX 5080), not on Aiden's desktop (RTX 3080) or the
  Vultr server (Aiden, 8 Nov, about 04:00 UTC). Access to that machine is still to be arranged with Hamish.
- **Decided:** delegated Claude agents start in auto permission mode (hc templates changed 8 Nov).

## Open, for Aiden

1. Prediction target(s): route through dead zones only, or also go-dark risk, destination or ETA.
2. Model family for the first version (research wave recommends).
3. How far back to backfill GFW (about 13 MB per day for four regions: one year about 5 GB, 2017 about 45 GB).
4. Whether to ingest the Danish AIS archive (size and access to be confirmed by research).
5. Overlap with Jake's planned `score.py` (go-dark risk): coordinate on the board through Hamish.
6. Frontend for predictions (path cones, graded predictions, leaderboard): Hamish's FrontEndLead owns `frontend/`.

## Status and decisions, 8 Nov 06:30 UTC

### Decided (Aiden)
- Targets: **route** (#1) and **go-dark risk** (#2), with **zone incursion** (#3) as the stretch (04:55).
- The training workflow itself is part of the presentation (04:55).
- Go fully off mock data on the site (05:15). Frontend asks posted to Hamish's FrontEndLead.
- Route training on Hamish's desktop (RTX 5080) by a Hamish-side agent from a posted command; go-dark on Aiden's
  desktop (05:20). First Hamish job: route on 90 days of the Danish archive (option b), started 05:29.
- GFW backfill: 7-day blocks and 2 workers (05:16), then **30-day blocks with 2 workers** after the server upgrade
  (06:27). History depth and cap unchanged (2017, 60 GB).
- Hold the training batch (#141) until Hamish's FrontEndLead finishes its UI pass (05:45).
- Delegated Claude agents start in auto mode; integrator approves trust prompts itself (04:00).

### Data (Tiger, read-only checks)
- Main GFW backfill: about 20 days of history an hour before the speed-ups, about 45 with 7-day blocks on one worker,
  about 80 with two workers; reached 3 May 2026 at 06:21. GFW gap events: 40,502 by 06:07, back to Aug 2024 at 06:21,
  heading for 2017. Sentinel-1 footprints complete back to July 2017. Database 3.18 GB at 06:07.
- Danish AIS archive: 14 days on Aiden's desktop (137 M clean positions, 8,458 ships, 1.48 GB tracks, 227 s); 90 days on
  Hamish's desktop for the route run.
- Server upgraded to 6 vCPU, 16 GB, 320 GB at 06:15 (snapshot kept); about 3 min of live-data gap 06:13 to 06:16.

### First results
- **Route `dma14-v1`** (train 23 Oct to 2 Nov, test 3 to 5 Nov, about 70k to 108k cases per horizon), skill over
  dead reckoning: +0.17 at 30 min, +0.35 at 1 h, +0.52 at 2 h, +0.58 at 3 h, +0.68 at 6 h, +0.75 at 12 h, all with tight
  95% intervals; 80% and 95% radii cover 79 to 80% and 94 to 95%. Synthetic Danish dead zones; real gaps are the next test.
- **Go-dark on our detector's labels** (11 h): open-sea silence (`unknown`) predictable (Brier skill +0.13 at 1 h, +0.12
  at 6 h); `deliberate_candidate` not yet beyond the base rate. Improves as labels accumulate.
- **Go-dark from GFW history:** 1.05 M ship-days from 42k ships; only 47 gap events in 7 days and 139 in 30 days
  (mostly Gulf of Oman, since GFW gaps start 50 nm or more offshore). Plan: 30-day label, ship-week rows, September as
  the fixed test month, learning curve over 1, 2, 4 and all months; meaningful from a rerun at about 08:30.
- **Training loop** (toy target): propose, train, evaluate, promote end to end; one real Gemini round promoted a
  winner after a second-seed check. The shared Gemini key is capped by the free tier (20 a day on flash), so the
  proposer uses flash-lite and at most 6 calls a day.

### PRs
| PR | What | State |
|---|---|---|
| 115, 122, 124 | GFW gap events; parallel workers; block fetch | merged and live |
| 129, 132, 133, 134, 140 | archive data, loop, go-dark, live predictor, route | combined in draft **141** (integration branch, 228 backend and 61 ml tests passing together) |
| 144 | replay with gaps, risk and predictions as of the scrub time | open, base the integration branch |
| 146 | `GET /observations?mmsi=` and `GET /observations/heat` for FrontEndLead | reviewed, CI green, waiting for Aiden to merge |
| backtest (pending) | prediction ledger for the past, `mode = backtest` | agent running |

### Still to do before the freeze
1. Merge 146; merge the 141 batch (with 144 and the backtest) after the UI pass; Hamish's combined release; model
   files on the server; `PREDICT=1`; frontend wiring of scores, outcomes, timeline and pred fields.
2. Hamish's 90-day route results: compare with `dma14-v1`; promote through the loop if better.
3. GFW-history go-dark rerun at about 08:30 for the learning curve.
4. Presentation: the training report, the learning curve, and live graded predictions.
