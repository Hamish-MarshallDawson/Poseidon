# Briefs: wave 2 (issue #121), from 05:50 UTC

Read `docs/handoffs/COMMON.md` and `docs/handoffs/ml-architecture.md` first (absolute paths under
`/home/aiden/.herdr/worktrees/Hedged-Bets-hacktheburgh/59-ingest-resilience/`). Everything builds on the integrated
batch, branch `121-ml-integration` (draft PR #141: main plus PRs 134, 132, 129, 133, 140), not on main.

Shared rules for this wave:
- **Setup:** in your new worktree, `git fetch origin && git reset --hard origin/121-ml-integration` (your branch has no
  commits yet). Open your PR with base `121-ml-integration`, `Part of #121`. Don't merge.
- **Hands off:** Hamish's agents are working in `frontend/` and `backend/dvm/collab/` right now. Don't touch either. Don't
  touch `backend/dvm/gaps.py` (Jake's) beyond reading it.
- **Speed:** aim for a tested PR within about 45 minutes. Smallest change that does the job, tests that prove it, one
  real run. If something needs a decision, end your turn with the question.
- **Tiger:** read-only (COMMON.md). Write only to your own local TimescaleDB.

## `replay-preds` (branch `121-replay-preds`, port 55541)
`backend/dvm/replay.py` sends `gaps: []`, `watchlist` empty or null and no risk in every replay snapshot and delta. Make
scrubbing show what was known at the replay time:
- **gaps:** latest version of every gap (`gaps` table) with `detected_at <= t` that is open at t or closed in the last
  hour, in the same shape live frames use (`Live.apply_gaps` and `snapshot_gaps`); the replay ships' `status` and
  `open_gap_id` follow them, as in `Live.view`.
- **go-dark:** `risk_p` and `risk_rank` on vessels and the `watchlist` from the newest `scores` set with `made_at <= t`
  (any `mode`, live or backtest), in the frontend's types (`frontend/src/types.ts`, read only).
- **route predictions:** the `pred_*` fields on open gaps from the newest `route_predictions` row with `made_at <= t`
  for that gap or ship, as be-predict sends them live.
- deltas carry changes as the replay clock moves; seek rebuilds everything as of t.
Keep queries cheap (one query per table per step, indexed on time); the 2 vCPU server runs it. Tests with a fake
history (like `tests/test_replay.py`) and one run against a local database seeded by the backtest writer's format.

## `backtest` (branch `121-backtest`, port 55542)
Fill the prediction ledger for the past, so replay and the forecast check show predictions with outcomes before the
freeze: a CLI `python -m dvm.predict.backtest --from <iso> --to <iso> --step-min 10 [--db URL]` in
`backend/dvm/predict/backtest.py` that walks stored history (Tiger `positions`, `statics`, `gaps`, read-only as
input), and at each step uses only data available then (`recv_ts <= t`, `available_ts <= t`) to run the same predictor
code as live (route for ships with an open gap at t and a sample of moving ships; go-dark for moving Class A ships),
then runs the same graders, writing `route_predictions`, `scores` (with `mode = 'backtest'`) and `outcomes` to the
target database (default: your local one; it must refuse Tiger unless `--allow-tiger`, which only the server will
use). Idempotent (stable ids, re-runs write nothing new). Report rows per hour of history, run time per hour, and
skill over baseline from the graded backtest rows. State the exact server command.

## `godark-gfw` (branch `121-godark-gfw`, port 55543)
A second go-dark model trained purely on GFW history, so it can use months of backfill and show a learning curve:
- **Unit:** one row per ship and day for ships GFW saw in our four regions (`observations` kind `ais_presence` per
  vessel, plus `port_visit`, `loitering`, `encounter` by mmsi), features from that ship's GFW history up to the day
  (presence hours trend, days since last port visit, loitering and encounter counts, flag, type, region, distance to
  shore when present), every row filtered by `available_ts <= as_of`.
- **Label:** a GFW gap event (`kind = 'gap'`, worldwide) starting for that ship within the next 7 days (and 30 days if
  the counts allow). Report the label rate first; if positives are too few in our regions, say so and propose the
  fix rather than forcing a model.
- **Model:** LightGBM with class weights and isotonic calibration, baseline = base rate by flag and type, time split
  with an embargo, through `ml/core` (TargetSpec in `ml/godark_gfw/target.py`), so the loop and report pick it up.
- **Learning curve:** train on the newest 1, 2, 4 and all available months before a fixed test period, same test set
  each time, and plot skill against months of history in the report. This is the presentation's "more data, better
  model" evidence: keep it honest (n, intervals). Cache Tiger pulls as local Parquet under
  `/home/aiden/data/poseidon/godark_gfw/` and refresh incrementally; cap threads at 6.
- The GFW backfill is still filling Tiger (about 80 days an hour, back to about June 2026 at 05:30; gap events back to
  2017 by about 09:00), so make the pipeline rerunnable and report which history it used.

## `obs-routes` (branch `143-obs-routes`, port 55544, issue #143): base on origin/main, not the integration branch
FrontEndLead is blocked on two read-only additions in `backend/dvm/sources/routes.py` and `query.py` (owned by us;
keep the existing routes' behaviour, auth, attribution and limits):
1. `GET /observations` gains an optional `mmsi` (repeatable, at most 100, 9-digit ints) filter that, when given, makes
   `bbox` optional and allows a longer window (up to 400 days) for one ship's full history: port visits, loitering,
   encounters, gaps, per-vessel presence and radar rows, newest first, with the existing limit and attribution.
   Use the `observations_mmsi_time` index.
2. `GET /observations/heat?bbox=&start=&end=&kinds=ais_presence&cell_deg=0.1` returns server-side aggregated cells
   `{"cells": [{"lat", "lon", "value", "n"}], "cell_deg", "kinds", "attribution"}`: anonymous cell rows (`mmsi IS
   NULL`, `cell_deg` set) summed into a grid of `cell_deg` (0.05 to 1), `value` = summed presence hours (or
   detection counts for `sar_detection`), capped at about 20,000 cells, bbox required, window up to 90 days. Fast:
   one GROUP BY on `observations_kind_time`; check the plan with EXPLAIN on a local database seeded with realistic
   volume.
Tests in `backend/tests/sources/` against a scratch local database (as `test_routes.py` does), the full suite, a real
local server curl, `Closes #143`, and post the exact request and response shapes in the PR for FrontEndLead. Target:
PR within about 30 minutes. Don't merge.
