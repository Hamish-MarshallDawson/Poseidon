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
