# ml/route: where a ship will be

Issue #121, target **route**: from a ship's track up to `as_of`, where it will be 1, 3, 6 and 24 h after its last
fix, as a point and an 80% and 95% radius. The case that matters is a dark ship (in a gap, or out of shore
receiver range); every other moving ship is training data and a live check.

## What is in here

| File | What |
|---|---|
| `examples.py` | Cases: moving ships (>= 1 kn, not anchored or moored) at a fix every 30 min per ship, truth at every horizon (interpolated between fixes no more than 5 min away); synthetic dead zones (a stretch after `as_of` hidden for a lognormal duration fitted to our detector's closed gaps, graded where the ship reappears); real dead zones from our Tiger `gaps` table (closed gaps, graded on the fix that closed them). Features and the baseline come from `backend/dvm/predict/features.py` (`features_at`, `baseline_point`), computed by ship in a forked process pool. |
| `model.py` | `RouteBaseline` (dead reckoning, rhumb line, or stay put when stopped) and `RouteLGBM` (two LightGBM regressors per horizon for the east and north offset of the truth from the baseline point). Both get Mondrian split-conformal radii per horizon and speed band (< 5, 5 to 12, >= 12 kn) from a calibration slice later in time than the fitting slice. `predict_at` interpolates to any gap length. |
| `target.py` | `SPEC` for `ml.core.run` / `ml.core.loop` (config schema, strata, calibration checks, leakage sanity check, dry-run proposals). |
| `metrics.py` | Error per case, paired-bootstrap skill, coverage, strata, reappearance sets. |
| `train.py` | One train/test run with the full route report (and transfer to our live AIS). |
| `tiger.py` | Read-only export of our live AIS (`positions`, latest `statics`, latest `gaps` versions) to Parquet. |
| `dma_io.py` | Reads `ml/data`'s Danish archive Parquet (`tracks_1m`, `identity`). |

## Run

From the repo root, Python 3.12, `ml/.venv` from `ml/requirements.txt` (no extra packages; no GPU, no PyTorch).
Data lives outside git under `/home/aiden/data/poseidon/` (override with `POSEIDON_DATA`).

```bash
ml/.venv/bin/python -m ml.data.dma --days 14 --until 2026-11-05        # Danish archive (ml/data/README.md)
ml/.venv/bin/python -m ml.route.tiger                                  # our live AIS, read-only (needs TIGER_DATABASE_URL)
ml/.venv/bin/python -m ml.route.train --data dma --transfer tiger \
    --out /home/aiden/data/poseidon/route/artifacts/route-dma14 --report /home/aiden/data/poseidon/route/reports/dma14.json
ml/.venv/bin/python -m ml.core.run  --target route                     # registered run against the frozen held-out set
ml/.venv/bin/python -m ml.core.loop --target route --rounds 3 --dry-run
ml/.venv/bin/python -m pytest -q ml/route/tests
```

`--data` takes `dma`, `dma:N` (newest N days), `tiger`, `dma+tiger` or an examples Parquet. Examples are cached in
`/home/aiden/data/poseidon/route/cache/` keyed by the source manifest and build settings. `ROUTE_WORKERS` (default
6) sets the feature pool size; LightGBM uses 4 threads per model (`num_threads`), because all-core OpenMP on a busy
machine was 100x slower.

## The artifact (what the backend runs)

`ml.core.registry.save_artifact` writes `model.json` plus `h<h>_east.txt` / `h<h>_north.txt` LightGBM text dumps.
`model.json` is the format `backend/dvm/predict/artifact.py` loads, with no `ml/` import: `kind: "lightgbm"`,
`feature_version` (= `features.FEATURE_VERSION`), `features` in column order, `horizons_s` (the contract's 1/3/6/24 h
that were trained) and `heads[h] = {east, north, radius_m_80, radius_m_95}` with radii as
`{"sog_edges_kn": [5, 12], "r": [3 values]}`. `all_heads` adds the 30 min, 2 h and 12 h heads used to interpolate
gap lengths (the backend ignores them). A test loads the artifact with the backend's own loader and checks it
predicts the same points and radii as training (`test_backend_loads_the_artifact_and_predicts_the_same`).

`age_s` is never a feature: training cases start at a fix, and the backend predicts from the last fix (`fix.ts + h`).

## Evaluation

Time-based only: the newest block of `as_of` is the test (or the loop's frozen held-out set); a training label for
horizon h must end before it starts (embargo = h, 24 h in the loop). Inside training, the newest 20% of each
horizon's span calibrates the radii, again with an embargo. Skill = 1 - median error / median baseline error, with a
paired bootstrap 95% interval. Strata: ship type, speed class, case kind.

RESULTS_PLACEHOLDER

## Options not on by default

- **`frame: "track"`**: learn the offset along and across the last course instead of east and north (a turn to port
  looks the same on any heading). Measured on the 14 Danish days with the earlier feature set: skill 0.353 vs 0.326 at
  1 h, 0.167 vs 0.120 at 30 min, 0.31 vs 0.22 on synthetic dead zones, about +1 point at 6 to 24 h. The backend
  loader reads only `east`/`north` heads, so this needs a small change there (rotate by the baseline course) before
  the config schema allows it; a track-frame artifact writes `along`/`cross` heads that the current backend refuses
  and falls back to its baseline, never mis-applies.

Data: Danish Maritime Authority AIS archive (http://aisdata.ais.dk/); our own live AIS (AISStream, Digitraffic).
