# ml/: training, evaluation and the improvement loop

Issue #121. Targets: **route** (where a dark ship is at +1/3/6/24 h, with an 80% and 95% radius) and **go-dark**
(chance a ship goes silent in the next 1/6/24 h). Training runs on a desktop; the backend on the server loads the
champion artifact and runs it live (`backend/dvm/predict/`).

The loop: data keeps arriving, delayed truth grades old predictions, graded cases join the training data, new
models are trained and compared on a frozen held-out set, and a rule (not a person, not Gemini) promotes the winner.

## Setup

```bash
python3 -m venv ml/.venv && ml/.venv/bin/pip install -r ml/requirements.txt   # Python 3.12
# local registry database (never Tiger; the registry refuses it)
docker run -d --name ml-tsdb -p 55522:5432 -e POSTGRES_PASSWORD=local timescale/timescaledb:latest-pg17
export ML_DATABASE_URL=postgresql://postgres:local@localhost:55522/postgres
```

Without `ML_DATABASE_URL` the registry is a folder of JSON files (`/home/aiden/data/poseidon/registry`), same
behaviour. Data and model files live under `/home/aiden/data/poseidon/` (override with `ML_ARTIFACTS` for models),
never in git. Keys (`GEMINI_API_KEY`) come from the repo `.env`; never print them.

## Commands (run from the repo root)

```bash
ml/.venv/bin/python -m ml.core.run  --target route --config cfg.json        # train, evaluate, log, maybe promote
ml/.venv/bin/python -m ml.core.loop --target route --rounds 3 --dry-run     # propose, run, compare, repeat
ml/.venv/bin/python -m ml.core.report --target route                       # leaderboard HTML and JSON
ml/.venv/bin/python -m ml.core.loop --target toy --rounds 3 --dry-run       # whole loop on synthetic data
ml/.venv/bin/pytest -q ml/tests
```

`--dry-run` uses fixed proposals instead of Gemini (logged with proposer `default`), so tests and rehearsals never
call it. Tests use a file registry; set `ML_TEST_DATABASE_URL` to a local database to also test the SQL registry.

What one loop does: with no champion yet, round 0 runs the target's default config against the baseline (and
promotes it if it passes the rule). Each round then builds a summary of past runs (aggregates only), gets K
proposals, refuses invalid ones and exact repeats of a config already evaluated (logged with the reason), trains
and scores the rest with Bonferroni over K, re-runs the best passing one with `seed + 1`, and promotes it only if
that passes too. At the end it writes `<ML_ARTIFACTS>/reports/<target>.html` and `.json`. Measured on the toy target
(7,680 cases): 3 rounds of 3 proposals in about 10 s; one Gemini round adds about 8 s.

## Plugging in a target (ml/route, ml/godark)

Expose `SPEC` in `ml/<target>/target.py`, an instance of a subclass of `ml.core.target.TargetSpec`
(see `ml/core/toy.py` for a complete small example):

| Field / method | Meaning |
|---|---|
| `name`, `horizons_s`, `primary_horizons_s` | e.g. `"route"`, `[3600, 10800, 21600, 86400]`, the horizons the promotion rule tests |
| `statistic` | `"median"` (route error) or `"mean"` (log loss, Brier) of the per-case `loss` |
| `loss_name`, `loss_unit` | for the report, e.g. `"error_m"`, `"m"` |
| `strata` | per-case columns checked one value at a time (e.g. `ship_type`, `speed_class`) |
| `baseline` | model name of the reference model (dead reckoning; base rate). Skill is measured against it |
| `models` | `{name: class}` of `ml.core.registry.Model` subclasses, the baseline included |
| `default_config`, `config_schema` | the first run's config; the JSON Schema every config and Gemini proposal must pass |
| `group_by_ship` | `True` keeps held-out ships out of training entirely |
| `load_examples(cfg, data)` | examples frame: `case_id` (str, stable), `mmsi`, `as_of` (epoch ms), then features and truth |
| `score(examples, preds)` | long frame `case_id, mmsi, as_of, horizon_s, loss` + strata + extras; no truth, no row |
| `summarise(scored)` | `{"3600": {"median_m": .., "p90_m": .., "cov80": .., "n": ..}, ...}` for the report |
| `calibration(scored)` | `[{"name", "horizon_s", "value", "nominal", "tol"}]`, e.g. 80% radius coverage vs 0.80 |
| `sanity(summary)` | reasons the numbers are too good to be true; any reason fails the run |
| `dry_run_proposals` (optional) | list of `{"config", "rationale"}` the dry run steps through; else numeric settings are stepped |
| `report_notes` (optional) | list of sentences printed under the report, e.g. "labels come from our own gap detector" |

A config is a dict with at least `"model"` (a key of `models`) and `"seed"`; the rest is the target's (features,
hyperparameters, sample weights). The loop reads `cfg["model"]` and applies `train_window_days` if the schema
allows it; the model reads the rest. `load_examples` should compute every candidate feature, because the loop
loads examples once and each config picks its subset.

### Model interface (`ml.core.registry.Model`)

`fit(train_df, cfg) -> self`, `predict(df) -> DataFrame`, `save(dir) -> dict`, `classmethod load(dir)`, attributes
`name`, `target`. `predict` returns one row per case and horizon: `case_id, horizon_s` plus the outputs (route:
`pred_lat, pred_lon, radius_m_80, radius_m_95`; go-dark: `p`). `save` writes LightGBM text dumps or JSON (pickles are
refused) and returns at least `{"features": [...], "horizons_s": [...]}`.

### Artifact (what the backend loads)

`<ML_ARTIFACTS>/<target>/<run_id>/model.json` plus the model's files. `model.json` holds `target, model, version`
(the run id), `features` (in order), `horizons_s`, `data_hash`, `config`, `metrics`, `files`, `created_at`. The
current champion is the registry row with `status = 'champion'`; `<ML_ARTIFACTS>/<target>/champion.json` points to
it too, so the backend can find it without a database.

## Evaluation (`ml/core/evaluate.py`)

- **Frozen held-out set** per target: the latest block of time in the examples when first frozen (default the last
  20% of the `as_of` span), stored as `<ML_ARTIFACTS>/holdout/<target>-<name>.json` (case ids + hash). Never trained
  on, never shown to Gemini case by case. New sets are added under new names, old ones are kept.
- **Embargo**: training examples whose `as_of` is within the longest horizon before the held-out start are dropped,
  so no training label overlaps it. With `group_by_ship`, held-out ships are dropped from training too.
- **Rolling-origin folds** (expanding window, one block per fold) inside the training data for model selection.
- **Promotion rule** (deterministic): a candidate replaces the champion (or, with none, the baseline) only if, on
  the frozen held-out set, at every primary horizon, the paired bootstrap interval of the statistic's difference
  excludes zero in the candidate's favour (95%, Bonferroni-corrected for the proposals tried in a round); every
  calibration check is within its tolerance (5 points); and no stratum with n >= 30 is worse by more than 10%. Ties
  keep the champion. In the loop the winner must also win again with a second seed.
- **Gemini** proposes configs only; the runner validates them against `config_schema` and logs every proposal,
  accepted or rejected, in `model_proposals`.

## Registry tables (local)

`model_runs (run_id, target, model, config, data_hash, train_from, train_to, metrics, artifact, proposer, parent_run,
status, created_at, loop_id, round, git_sha)`, status `candidate | champion | rejected | retired` (retired: a former
champion). `model_proposals (id, target, loop_id, round, proposer, proposal, valid, errors, run_id, rationale,
created_at)`.

Data: Danish Maritime Authority AIS archive; Global Fishing Watch (CC BY-NC 4.0); our own live AIS.
