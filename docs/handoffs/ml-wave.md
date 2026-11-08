# Briefs: the training wave (issue #121)

Read `docs/handoffs/COMMON.md` and `docs/handoffs/ml-architecture.md` first (absolute paths under
`/home/aiden/.herdr/worktrees/Hedged-Bets-hacktheburgh/59-ingest-resilience/`). Context and research:
`docs/prediction-loop/PLAN.md` and `docs/prediction-loop/research/`. Freeze 09:00 UTC: aim for a working, tested first
version by about 07:30, then polish. Each agent: its own branch and worktree, `Part of #121`, one PR, don't merge.

Shared rules for this wave, on top of COMMON.md:
- ML environment: `python3 -m venv ml/.venv && ml/.venv/bin/pip install -r ml/requirements.txt` in your worktree
  (add `ml/.venv/` to a `ml/.gitignore`). ml-loop creates `ml/requirements.txt`; others add lines they need and say so.
- Data lives outside git under `/home/aiden/data/poseidon/` (create it). Never commit data or model files.
- Tiger: read-only, as COMMON.md says. Use your own local TimescaleDB for anything you write.
- The `ml/` folder is new: ml-loop owns `ml/core/`, `ml/README.md`, `ml/requirements.txt`; the others own only their
  subfolder. Until ml-loop's interface lands, code against the contract in ml-architecture.md.

## `ml-data` (branch `121-ml-data`, port 55521)
`ml/data/dma.py`: download the Danish AIS archive days `aisdk-YYYY-MM-DD.zip` from `http://aisdata.ais.dk/`
(anonymous; files about 550 to 750 MB; newest is about 2 to 3 days old) for the 14 newest available days, in
parallel but politely (2 to 3 at once). Convert with DuckDB to Parquet in the contract's track columns: drop base
stations and placeholders (lat 91, lon 0 or 181), de-duplicate same-second multi-receiver rows (about 28%), speed-gate
jumps over 40 kn, keep Class A and B with `cls`, keep identity columns separately (`mmsi, imo, name, ship_type,
length, draught` per day). Also write a thinned 1-per-minute version per ship. Output under
`/home/aiden/data/poseidon/dma/` with a manifest (days, rows, ships, bytes, hash). Download the first 2 days first and
tell be-integrate the schema works (end a turn early if you must) so ml-route can start; then the rest. Report sizes
and times. Licence: cite the Danish Maritime Authority.

## `ml-loop` (branch `121-ml-loop`, port 55522)
`ml/core/` per the architecture: registry (local TimescaleDB table `model_runs`), evaluation (frozen held-out sets,
rolling folds, embargo, paired bootstrap, the promotion rule), the runner, the loop, the Gemini proposer (JSON schema
per target, validation, logging, a `--dry-run` that uses a fixed proposal so tests never call Gemini), and the report
(leaderboard, skill over baseline per horizon, learning curve across rounds, accepted and rejected proposals) as
static HTML plus JSON. Ship a toy model and dataset in tests so the whole loop runs end to end without real data. Write
`ml/README.md` and `ml/requirements.txt` first and commit early so the others can pull them. The report is part of
the presentation: make it clear and honest (state the held-out set, n, intervals).

## `ml-route` (branch `121-ml-route`, port 55523)
`ml/route/`: example builder (for a ship and `as_of`, features from history up to `as_of`, truth at +1/3/6/24 h within
5 min; synthetic dead zones by hiding a stretch of a complete track, labelled synthetic; real dead-zone cases from our
`gaps` table's closed gaps, read-only from Tiger), the baseline (dead reckoning on the sphere from last course and
speed, plus "stay put" for anchored ships), and LightGBM per horizon predicting the east and north offset from the
baseline, with split-conformal radii (80%, 95%). Metrics per the contract, stratified by horizon, ship type and speed.
Start on Tiger `positions` (our own 11+ hours, read-only) so you are not blocked, then switch to the Danish archive
Parquet from ml-data. Put feature code in `backend/dvm/predict/features.py` only if be-predict hasn't yet; coordinate
through be-integrate (end your turn with the question if you need a decision). Report skill over baseline per horizon
with intervals.

## `ml-godark` (branch `121-ml-godark`, port 55524)
`ml/godark/`: label view (one row per ship and `made_at` on a grid; label = a gap of ours starts within the next 1, 6,
24 h; exclude ships already in a gap; read Tiger `positions` and `gaps` read-only; count `deliberate_candidate` as the
primary label and report `unknown` separately), features (from `features.py`, plus area reception, past gaps, ship
type, flag, time of day, distance to shore if cheap), LightGBM per horizon with class weights and isotonic
calibration, baselines (base rate by area and ship type). Metrics per the contract; time split by hour with an
embargo. Say clearly in the report that our own detector made these labels (GFW gap events, issue #112, are the
independent check offshore). Report AUC-PR, Brier and skill over the baseline.

## `be-predict` (branch `121-be-predict`, port 55525)
`backend/dvm/predict/`: `features.py` per the contract (shared with ml; pure functions, tested), the ledger tables
(`route_predictions`, and `model_runs` mirrored for the backend to find champions; additive, append-only trigger like
`scores`), a live predictor (every 5 minutes: for ships with an open gap and a sample of active ships, load the
champion artifact per target from a configured directory, predict, write the ledger; go-dark to `scores`), the fast
grader (own AIS reappearance and closed gaps grade route predictions; our detector grades go-dark; results to
`outcomes` with error, baseline error, truth source), and read-only routes `GET /predictions?mmsi=` and
`GET /model/leaderboard` (same login as `/coverage`). Wire it into `app.py` lifespan behind `PREDICT=1` (default off
until a champion exists). Without a champion, run the baseline so the ledger and graders work from the start. Add
`lightgbm` to `backend/requirements.txt` only if the predictor needs it (it does for LightGBM text models). Test with
a local server (no AISStream key) and a toy artifact.
