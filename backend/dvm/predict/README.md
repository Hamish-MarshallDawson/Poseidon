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
| `routes.py` | `GET /predictions`, `/model/leaderboard`, `/scores`, `/outcomes`, `/timeline`, `/model/report`. |
| `forecast.py` | The newest forecasts in memory for the WebSocket frames: risk, watchlist, gap ghost circles, detail. |
| `backtest.py` | Fills the ledger for stored history with the live code (`mode = 'backtest'`) and grades it. |

## Run

Off by default. `PREDICT=1` in the environment starts it in the backend's lifespan, once Tiger is connected.

| Variable | Default | Meaning |
|---|---|---|
| `PREDICT` | `0` | `1` runs the predictor and graders. The routes are always mounted; they answer 503 until the tables exist. |
| `PREDICT_MODEL_DIR` | `backend/data/models` | Where `champions.json`, the artifact directories and `runs.jsonl` live. |
| `PREDICT_INTERVAL_S` | `300` | Seconds between cycles. |
| `PREDICT_SAMPLE` | `150` | Active ships with a route prediction per cycle. |
| `PREDICT_SCORE_SAMPLE` | `300` | Ships with a go-dark score per cycle, those scored longest ago first (covers every moving ship in about an hour). |
| `PREDICT_P_ALERT` | `0.2` | `dark_6h` p for `HIGH_FORECAST` and the `inspect` decision. |
| `PREDICT_REPORT_DIR` | `<PREDICT_MODEL_DIR>/reports` | Where `ml.core.report` writes its HTML; `/model/report` serves the newest. |

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
- Go-dark: each cycle scores `PREDICT_SCORE_SAMPLE` moving ships (in memory, for the map). **On each full hour**
  the predictor commits a frozen set to `scores`: every ship's newest score of the hour before, re-issued with
  `made_at` = the hour (id `score-{mmsi}-dark_{h}h-{hour}`, target `dark_1h | dark_6h | dark_24h`, 06 naming,
  `mode = live`), plus the feature `scored_age_s` (how old the data was at the hour). The label window starts at the
  hour. These sets are what gets graded and what `/scores` serves (the frontend's forecast check works on hourly
  sets). The feature snapshot is on the dark_6h row; the others hold `{"same_as": <6 h id>}`. `contrib` holds the
  model's top 5 SHAP contributions per horizon (raw log-odds units; empty for the baseline).
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

## Backtest (`python -m dvm.predict.backtest`)

```
python -m dvm.predict.backtest --from 2026-11-07T20:00Z --to 2026-11-08T05:50Z --step-min 10 [--db URL] [--json out.json]
```

Walks stored history and, at each step t, runs the live predictor's code (`route_rows`, `godark_rows`, the champions or
baselines, `Forecast.frozen_set`) on what was known at t, then grades with the graders' functions. Reads `positions`,
`statics`, `gaps` from `--source` (default `TIGER_DATABASE_URL`, read-only session); writes `route_predictions`,
`scores` and `outcomes` to `--db` (default `BACKTEST_DATABASE_URL`, else the local database on port 55542). Tiger as
`--db` is refused without `--allow-tiger` (the Vultr server only). Prints a JSON summary: rows written, rows per hour of
history, seconds per hour, and skill over the baseline from the graded backtest rows.

- **Known at t:** positions and statics with `recv_ts <= t`; a gap from when the detector opened it, start +
  max(30 min, 20 x report interval) (dvm/gaps.py's rule) or the stored `detected_at` if earlier, until its `end_ts`.
  The rule is used because a warm start re-detects older gaps with `detected_at` = the restart time.
- **Same as live:** gap ships once per gap and model version (`as_of` = last fix); `--sample` moving Class A ships per
  step (seeded by t); every moving Class A ship scored once an hour (at a step fixed by its mmsi) and an hourly
  frozen set in `scores`. Hours that already hold a live set are skipped. Ids are the live ids.
- **Grading:** everything the history can decide by `--data-end` (default: the newest position), `resolved_at` =
  when the live grader would have decided. Go-dark windows that start before the first gap in `gaps` are not graded
  (no gap there means no detector, not no gap), and the baseline rate counts only that covered time.
- **Idempotent:** ON CONFLICT DO NOTHING on stable ids and time-seeded sampling: a re-run writes nothing new.
- A champion trained on part of the range is graded on its own training data: pass `--model-dir` with an artifact
  trained before `--from`, or read its skill as in-sample.

## Routes (same login as `/coverage`)

- `GET /predictions?mmsi=<n>&hours=24` → `{mmsi, route: [{as_of, made_at, model_version, gap_id, points: [{horizon_s,
  lat, lon, radius_m_80, radius_m_95, base_lat, base_lon, grade}]}], reappear: [...], godark: [...]}`, newest first.
- `GET /model/leaderboard?hours=24` → `{runs, champions, running, live_route: [{target, model_version, horizon_s, n,
  median_err_m, p90_err_m, baseline_median_err_m, skill, coverage_80, coverage_95}], live_godark: [{target,
  model_version, horizon_s, n, positives, brier, mean_p, base_rate, base_rate_brier, brier_skill}]}`.
  `route_reappear` rows are banded by lead time into the next horizon up.

## Frontend contract (frontend/src/types.ts, addendum 05:15)

All routes take the same login as `/coverage`.

| Path | Returns |
|---|---|
| `GET /scores?as_of=<ms>&target=dark_6h` | `RiskScore[]`: the newest hourly frozen set at or before `as_of` (default now, at most 2 h back), ranked by p (`rank` 1 = highest). `as_of` = `made_at` = the hour. `features` numeric only. `target` may be `dark_1h`, `dark_6h` (default), `dark_24h`. |
| `GET /outcomes?from_ts=<ms>&to_ts=<ms>&target=dark_6h` | `Outcome[]` of frozen scores whose window closed in the range: `made_at + horizon + 30 min` (the frontend's RESOLVE_LAG_MS) in `[from_ts, to_ts]`. `label` hit/miss; a censored row keeps miss and says why (`coverage_gap`, incl. our `unknown`; `own_stall`). `lead_s` only on hits. |
| `GET /timeline?from_ts=<ms>&to_ts=<ms>[&mmsi=<n>]` | `TimelineEvent[]`: `gap` (latest version, overlapping, newest 5,000), `freeze` (one per hourly set, id `freeze-<ms>`), `outcome` (dark_6h, `ts` = resolved_at, `label` hit/miss/censored), `coverage` (`data` over stored history, `own_stall` for `dvm.gaps.KNOWN_STALLS`). No `spoof` or `meeting`: no detector yet. |
| `GET /model/report` | The newest `*.html` under `PREDICT_REPORT_DIR` (text/html, header `X-Report-File`), 404 when none. |

WebSocket frames (only with `PREDICT=1`; otherwise exactly as before):

- `VesselView.risk_p`, `risk_rank`: newest `dark_6h` p of the last hour and its rank among all scored ships; null
  when unscored. Ships whose risk or rank changed are in the next `delta.vessels`.
- `snapshot.watchlist`, `delta.watchlist` (only when the ranks, decisions or codes change, else null): `{snapshot_ts,
  entries: WatchlistRow[]}`, top 50. Reason codes are 06's fixed set, from evidence: `HIGH_FORECAST` (p >=
  PREDICT_P_ALERT), `OPEN_GAP`, `RECENT_GAP` (gap in the last 24 h), `DRAUGHT_JUMP` (>= 1 m across a recent gap),
  `BLANK_DESTINATION`. `decision`: `inspect` = rank <= 10 and p >= p_alert; `watch` = p >= p_alert or OPEN_GAP or
  RECENT_GAP; else `none`. `evidence`: the score (`kind: score`, id = score id) and any open or recent gap.
- Open `GapEvent`s in `snapshot.gaps`, `delta.gaps` and `detail.gaps` gain optional `pred_lat, pred_lon, pred_r80_m,
  pred_r95_m, pred_horizon_s, pred_made_at, pred_model`: the gap's newest route prediction at the first horizon not
  yet passed since the last fix (so the circle grows with the gap; re-sent when that changes). Absent without one.
- `detail` gains `route_prediction` (absent without one): `{as_of, made_at, model_version, gap_id, points:
  [{horizon_s, lat, lon, radius_m_80, radius_m_95, base_lat, base_lon}]}` for 1, 3, 6 and 24 h; and `detail.score`
  is the ship's newest `dark_6h` RiskScore (null when unscored).

With the baseline go-dark model every ship has the same p, so the ranking and the watchlist order carry no
information until a LightGBM champion is promoted (decisions are then all `none` unless a gap raises them to watch).

## Tests

`pytest tests/test_predict_features.py tests/test_predict.py tests/test_predict_frames.py tests/test_predict_backtest.py`. The frame and route
shapes are checked against the interfaces parsed from `frontend/src/types.ts`. The database test needs a local TimescaleDB in
`SOURCES_TEST_DATABASE_URL` (it truncates the ledger tables, so never point it at a database you care about).
