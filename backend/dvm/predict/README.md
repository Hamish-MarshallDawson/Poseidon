# `dvm/predict`: live route and go-dark prediction (#121)

The backend half of the training loop in `docs/prediction-loop/`: shared features, a live predictor, fast graders
and two read-only routes. Training lives in `ml/` and reaches the backend only through artifact directories.

| File | What |
|---|---|
| `features.py` | **The** feature code, shared with `ml/`. Pure functions of one ship's track up to `as_of`; also the route baseline and the east/north offset helpers. |
| `artifact.py` | Loads a champion artifact (LightGBM text dumps plus `model.json`); the built-in baselines when there is none. |
| `predictor.py` | Every `PREDICT_INTERVAL_S`: predict, write the ledger, then grade. |
| `grader.py` | Fast grading from our own AIS and gap detector into `outcomes`. |
| `schema.py` | `route_predictions`, `model_runs`, extra nullable `outcomes` columns. Additive, append-only. |
| `routes.py` | `GET /predictions?mmsi=`, `GET /model/leaderboard`. |

## Run

Off by default. `PREDICT=1` in the environment starts it in the backend's lifespan, once Tiger is connected.

| Variable | Default | Meaning |
|---|---|---|
| `PREDICT` | `0` | `1` runs the predictor and graders. The routes are always mounted; they answer 503 until the tables exist. |
| `PREDICT_MODEL_DIR` | `backend/data/models` | Where `champions.json`, the artifact directories and `runs.jsonl` live. |
| `PREDICT_INTERVAL_S` | `300` | Seconds between cycles. |
| `PREDICT_SAMPLE` | `150` | Active ships per cycle (route and go-dark). |

`lightgbm` and `numpy` (in `requirements.txt`) are imported only when a LightGBM champion is loaded; the baselines need
neither. `/health` has a `predict` block: cycles, rows written, rows graded, last cycle time and error, the models
running and why a champion was not loaded.

## Using the features from `ml/`

```python
import sys; sys.path.insert(0, "backend")
from dvm.predict.features import (Track, features_at, features_many, vector, baseline_point, enu_offset,
                                  apply_offset, haversine_m, FEATURE_NAMES, FEATURE_VERSION)

t = Track.from_columns(mmsi, g.ts, g.lat, g.lon, g.sog_kn, g.cog_deg, g.heading_deg, g.nav_status, g.cls)  # one ship
f = features_at(t, as_of, {"ship_type": 70, "length_m": 180, "draught_m": None})   # dict, or None (no fix in 6 h)
x = vector(f, names)                                  # list in your model's feature order, None as NaN
fix = t.last_fix(as_of)
blat, blon = baseline_point(fix, 3600)                # rhumb-line dead reckoning; stays put if anchored/stopped
east, north = enu_offset(blat, blon, true_lat, true_lon)   # the route target: offset from the baseline
```

- Only fixes with `ts <= as_of` are read, and none older than 6 h. Keep the track sorted by `ts`.
- `static` should be the latest statics row at `as_of`. The live predictor uses the latest of the last 24 h.
- ~0.3 ms per call on a 1-per-minute track, ~1.6 ms at 1 fix per 10 s (one core).
- Change `FEATURE_VERSION` with any change in meaning; the backend refuses an artifact of another version.

## Artifact (what training hands over)

```
<PREDICT_MODEL_DIR>/
  champions.json            {"route": "<artifact dir>", "godark": "<artifact dir>"}   (ml-loop writes it on promotion)
  runs.jsonl                optional: the registry, one model_runs row per line (mirrored into Tiger)
  <artifact dir>/model.json
  <artifact dir>/*.txt      LightGBM text dumps (Booster.save_model), no pickles
```

`model.json`:

```json
{
  "target": "route",
  "model": "lgbm-offset",
  "version": "route-lgbm-20261108a",
  "kind": "lightgbm",
  "feature_version": "f1",
  "features": ["sog_kn", "cog_sin", "cog_cos", "w30m_turn_deg"],
  "horizons_s": [3600, 10800, 21600, 86400],
  "data_hash": "…", "metrics": {},
  "heads": {
    "3600": {"east": "h3600_east.txt", "north": "h3600_north.txt",
             "radius_m_80": 900, "radius_m_95": {"sog_edges_kn": [2, 8, 15], "r": [800, 1500, 2600, 4000]}}
  }
}
```

- **route**: per horizon, two regressors for the east and north offset (metres) from `baseline_point(fix, h)`, and
  split-conformal radii, each a number or speed bands (`r[i]` for `edges[i-1] <= sog < edges[i]`).
- **godark**: `"heads": {"3600": {"model": "h3600.txt", "calibration": {"x": [...], "y": [...]}}}`, horizons a
  subset of 3600, 21600, 86400. The model's output goes through the piecewise-linear calibration (isotonic
  breakpoints, `x` increasing); without one, the output is used as the probability.
- `version` is what the ledger records as `model_version`, so make it unique per run.
- A broken or mismatched artifact is logged, shown in `/health` (`champion_errors`) and replaced by the baseline;
  the predictor never stops for it. `champions.json` is re-read when its mtime changes.
- `runs.jsonl` rows: `run_id, target, model, status, created_at` required; `config, data_hash, train_from, train_to,
  metrics, artifact, proposer, parent_run, recorded_at` optional. A run gets one row per status it reaches
  (key `run_id, status`); the newest `recorded_at` is its status now.

## Ledger

- `route_predictions`: id `route-{mmsi}-{as_of}-{horizon_s}-{model_version}`; the point is for `as_of + horizon_s`.
  - **Gap ships**: once per gap and model version, `as_of` = the gap's last fix, `gap_id` set. Up to 500 gaps a
    cycle, newest first.
  - **Active ships**: a random sample of moving Class A ships (>= 1 kn, not anchored or moored) heard in the last
    10 min and not in a gap, `as_of` = now. Moving only: gaps open only for moving ships, and moored ships would
    swamp the live metrics.
  - `base_lat, base_lon` is the baseline for the same time, so every grade also grades the baseline.
- Go-dark scores go to `scores`: id `score-{mmsi}-dark_{h}h-{made_at}`, target `dark_1h | dark_6h | dark_24h`
  (06 naming), `mode = live`. The feature snapshot is on the 1 h row; the others hold `{"same_as": <1 h id>}`.
- Baselines when no champion: `baseline-dr-v1` (dead reckoning; radii 500 m + 0.9 x the distance run for 80% and
  1 km + 1.35 x for 95%, fitted to 8 h of our live AIS: dead-reckoning errors are heavy-tailed) and `baseline-rate-v1` (deliberate-candidate gaps per moving Class A ship-hour over
  the last 6 h before the detector's 30 min delay, the same p for every ship; re-measured every 30 min).

## Grading (`outcomes`)

| target | truth | written when |
|---|---|---|
| `route` | our own fix nearest `as_of + h` within 5 min (`own_ais`): `error_m`, `baseline_error_m`, `in_r80`, `in_r95` | 5 min after the target time; `censored = no_truth` if no fix by 1 h after |
| `route_reappear` | where a gap's ship came back (`gap_close`), against the prediction interpolated to that lead time; `score_id = reappear-{gap id}-{model version}` | when the gap closes; `beyond_horizon` past 24 h |
| `dark_<h>h` | a `deliberate_candidate` gap of ours starting in `(made_at, made_at + h]` (`own_detector`) | 35 min after the window ends; a window with only other gaps is censored with their flag |

Our own detector makes the go-dark labels; GFW gap events (#112) are the independent check later. A delayed grader
(Danish archive, GFW) should write its own rows with a suffixed `score_id` (e.g. `<id>@dma`).

## Routes (same login as `/coverage`)

- `GET /predictions?mmsi=<n>&hours=24` → `{mmsi, route: [{as_of, made_at, model_version, gap_id, points: [{horizon_s,
  lat, lon, radius_m_80, radius_m_95, base_lat, base_lon, grade}]}], reappear: [...], godark: [...]}`, newest first.
- `GET /model/leaderboard?hours=24` → `{runs, champions, running, live_route: [{target, model_version, horizon_s, n,
  median_err_m, p90_err_m, baseline_median_err_m, skill, coverage_80, coverage_95}], live_godark: [{target,
  model_version, horizon_s, n, positives, brier, mean_p, base_rate, base_rate_brier, brier_skill}]}`.
  `route_reappear` rows are banded by lead time into the next horizon up.

## Tests

`pytest tests/test_predict_features.py tests/test_predict.py`. The database test needs a local TimescaleDB in
`SOURCES_TEST_DATABASE_URL` (it truncates the ledger tables, so never point it at a database you care about).
