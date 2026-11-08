# Training and evaluation architecture (issue #121)

Decided by Aiden, 8 Nov about 04:55 UTC: targets **route** (where a dark ship is and reappears, 1/3/6/24 h, with an
uncertainty radius) and **go-dark risk** (chance a ship goes silent in the next 1/6/24 h), with **zone incursion** as
the stretch. The training workflow itself is part of the presentation: data keeps arriving, delayed truth grades old
predictions, graded cases join the training data, and new models are trained, compared and promoted by rule.
Training runs on Aiden's desktop (RTX 3080, 16 cores, 31 GB) and, once access exists, Hamish's desktop (RTX 5080).
Live inference runs in the backend on the Vultr server (2 vCPU, 4 GB). Plan and research: `docs/prediction-loop/`.

## Layout (new top-level folder `ml/`, plus `backend/dvm/predict/`)

```
ml/
  README.md            how to run everything; the contract below
  requirements.txt     lightgbm, duckdb, pyarrow, numpy, pandas, scikit-learn, httpx, python-dotenv, asyncpg
  core/                owner: ml-loop
    registry.py        model runs: create, log metrics, artifact path, champion pointer per target
    evaluate.py        frozen held-out sets, rolling-origin folds, paired bootstrap, promotion rule
    run.py             python -m ml.core.run --target route --config cfg.json   (train, evaluate, log, maybe promote)
    loop.py            python -m ml.core.loop --target route --rounds N         (propose, run, compare, repeat)
    propose.py         Gemini proposer: reads a metrics summary, returns configs valid against a JSON schema
    report.py          leaderboard and learning-curve report (HTML and JSON) for the demo
  data/dma.py          owner: ml-data. Danish AIS archive: download, clean, thin, write Parquet
  route/               owner: ml-route. examples, baseline, LightGBM per horizon, conformal radius, metrics
  godark/              owner: ml-godark. labels, features, LightGBM per horizon, calibration, metrics
backend/dvm/predict/   owner: be-predict. live predictor, ledger tables, graders, routes
  features.py          THE feature code, shared: ml/route and ml/godark import it (ml adds backend/ to sys.path)
```

## Contract (every owner keeps to this; change it only through be-integrate)

- **Track input.** A position table with columns `mmsi, ts (epoch ms), lat, lon, sog_kn, cog_deg, heading_deg,
  nav_status, cls, src`, sorted by `mmsi, ts`. Sources: Parquet from `ml/data/dma.py` (Danish archive) and the Tiger
  `positions` table (our live AIS, read-only). Same columns from both.
- **Features** come only from `backend/dvm/predict/features.py`: pure functions of a ship's track up to `as_of` (and
  static fields), so training and live inference compute the same thing. Nothing after `as_of` may be read.
- **Model interface** (`ml/core/registry.py` defines it, models implement it):
  `fit(train_df, cfg) -> self`, `predict(df) -> DataFrame`, `save(dir)`, `load(dir)`, plus `name` and `target`.
  Route predictions: `pred_lat, pred_lon, radius_m_80, radius_m_95` per horizon. Go-dark: `p` per horizon.
- **Artifact** (what the backend loads): a directory with `model.json` (target, model name, version, feature list
  and order, horizons, training data hash, metrics) and the model files (LightGBM text dumps, calibration tables). No
  pickles. The backend reads it without importing `ml/`.
- **Registry** (`model_runs`): `run_id, target, model, config (json), data_hash, train_from, train_to, metrics (json),
  artifact (path), proposer (human | gemini | default), parent_run, status (candidate | champion | rejected), created_at`.
  Locally in each agent's own TimescaleDB; in Tiger after be-integrate merges (additive table).
- **Evaluation:** time-based only. A frozen held-out set per target (list of case ids plus a hash, never trained on,
  never shown to Gemini case by case); rolling-origin folds for model selection; an embargo the length of the longest
  horizon between train and test; group by ship where stated. Route metrics: median and p90 error in metres per
  horizon, coverage of the 80% and 95% radius, **skill = 1 - median_err / median_err_baseline** (headline). Go-dark:
  log loss, Brier, AUC-PR, calibration curve, skill over the base-rate baseline.
- **Promotion rule** (deterministic, in `evaluate.py`): a candidate replaces the champion only if it beats it on the
  frozen held-out set at the primary horizons with a paired bootstrap 95% interval excluding zero, calibration within
  5 points of nominal, and no stratum (n >= 30) worse by more than 10%. Ties keep the champion.
- **Gemini** (`GEMINI_API_KEY` in the repo `.env`; never print it): proposes configs only, within a JSON schema per
  target (model family, features subset, hyperparameter ranges, training window, sample weights). The runner
  rejects anything outside the schema. Gemini never sees held-out cases, never edits code. Every proposal is logged,
  including rejected ones.
- **Ledger** (backend, Tiger, additive and append-only like `scores`): `route_predictions (id, mmsi, made_at, as_of,
  model_version, horizon_s, lat, lon, radius_m_80, radius_m_95, base_lat, base_lon, gap_id, feature_version)`;
  go-dark predictions go to the existing `scores` table, grades to `outcomes`.
