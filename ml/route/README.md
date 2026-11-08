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

## One command on another machine (Hamish's desktop)

Fresh checkout, Python 3.12, no keys, no database, no GPU (LightGBM on CPU; no PyTorch). Works on Windows (the
feature pool falls back to spawn with memory-mapped files):

```bash
git clone -b 121-ml-route git@github.com:Hamish-MarshallDawson/Hedged-Bets-hacktheburgh.git && cd Hedged-Bets-hacktheburgh
python3.12 -m venv ml/.venv && ml/.venv/bin/pip install -r ml/requirements.txt          # Windows: ml\.venv\Scripts\pip
ml/.venv/bin/python -m ml.data.dma --days 14 --until 2026-11-05 --out DATA/dma --delete-zips
ml/.venv/bin/python -m ml.route.train --data DATA/dma --out DATA/models/route-dma14
```

Outputs in `DATA/models/route-dma14/`: `model.json` and 14 LightGBM text dumps (`h<h>_east.txt`, `h<h>_north.txt`,
about 31 MB) that `backend/dvm/predict` loads as they are, and `metrics.json` (held-out description and hash,
per-horizon metrics with intervals, strata, dead-zone sets, the promotion decision, run time, peak memory). The
held-out set is frozen at `DATA/models/holdout/route-v1.json`. Attach the directory to a draft release; never
commit it. Optional: `ROUTE_WORKERS` (feature processes, default 6), `ROUTE_THREADS` (LightGBM, default 8).

Measured here (16 cores shared with other jobs): venv 16 s; `ml.data.dma` about 8 min for 14 days (37 s per day in
a fresh 3-day run), 1.8 GB output, 15 GB peak while converting; `ml.route.train` about 3.5 min for 14 days
(examples 75 s, fit and score about 60 s), peak 10.5 GB RAM; about 40 s for 3 days at 2.7 GB. More days scale
roughly linearly; for `--days 90` that extrapolates (not measured) to about 20 min and 60 GB RAM in the examples step (use `ROUTE_WORKERS=4` if short
on memory).

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

### Results (8 Nov 2026, 14 Danish days 23 Oct to 5 Nov, artifact `route-dma14-v3`)

Held-out `route-v1`: the newest 20% of the as_of span (from 4 Nov 04:46 UTC), 99,421 cases, hash `3e3ee05559152b66`;
training labels end 24 h before it. Errors in metres; skill with paired-bootstrap 95% intervals. The promotion rule
(ml/core) passes against the baseline.

| horizon | n | median | baseline | p90 | skill [95% CI] | cover 80% / 95% |
|---|---|---|---|---|---|---|
| 1 h | 89,112 | 1,556 | 2,328 | 7,987 | 0.332 [0.323, 0.340] | 0.79 / 0.95 |
| 3 h | 81,870 | 6,508 | 15,763 | 25,166 | 0.587 [0.582, 0.592] | 0.79 / 0.95 |
| 6 h | 73,810 | 14,146 | 44,328 | 53,997 | 0.681 [0.677, 0.685] | 0.79 / 0.94 |
| 24 h | 41,235 | 40,729 | 296,035 | 183,496 | 0.862 [0.860, 0.865] | 0.77 / 0.93 |
| synthetic dead zones (median gap 69 min) | 1,052 | 2,018 | 2,953 | 12,817 | 0.317 [0.229, 0.409] | 0.81 / 0.95 |

Read with care: at 24 h dead reckoning is ~300 km off, so a large skill there mostly says the baseline is weak; the
model still misses by a median 41 km. Skill is highest for ferries (they repeat routes) and lowest for fishing boats.

**Transfer to our live AIS** (the same model scored on Tiger, 7 to 8 Nov, our own fixes and closed gaps): inside the
Danish box (lat 53.5 to 58.5, lon 7 to 16) skill is 0.39 at 1 h and 0.59 at 3 h, coverage 0.74 / 0.93; on 102 real
gaps there, 0.23 [-0.16, 0.50] (too few to be sure). Worldwide it still beats dead reckoning (0.18 at 1 h, 0.50 at
6 h) but the radii are too narrow (coverage 0.60 / 0.87), and on 1,154 real gaps worldwide it is no better than the
baseline (0.03 [-0.09, 0.14]). Outside Danish waters, trust the point less and widen the circle; a worldwide model
needs worldwide tracks (GFW, or our own feed as it accumulates).

Run time on a 16-core desktop (shared with other jobs, 8 LightGBM threads): examples about 75 s for 14 days
(6 feature workers), fitting and scoring about 60 s; peak memory about 10.5 GB while building examples.

## Options not on by default

- **`frame: "track"`**: learn the offset along and across the last course instead of east and north (a turn to port
  looks the same on any heading). Measured on the 14 Danish days with the earlier feature set: skill 0.353 vs 0.326 at
  1 h, 0.167 vs 0.120 at 30 min, 0.31 vs 0.22 on synthetic dead zones, about +1 point at 6 to 24 h. The backend
  loader reads only `east`/`north` heads, so this needs a small change there (rotate by the baseline course) before
  the config schema allows it; a track-frame artifact writes `along`/`cross` heads that the current backend refuses
  and falls back to its baseline, never mis-applies.

Data: Danish Maritime Authority AIS archive (http://aisdata.ais.dk/); our own live AIS (AISStream, Digitraffic).
