# Go-dark risk (`ml/godark/`, issue #121)

The chance that a moving Class A ship goes silent in the next 1, 6 or 24 h, where "goes silent" means **a gap of
ours**: the backend's own detector (`backend/dvm/gaps.py`) opens a gap. The primary label is a
`deliberate_candidate` gap (the area still heard other ships); `unknown` (open sea, no neighbours) is reported
separately. **Our own detector made every label.** GFW gap events (issue #112) are the independent check offshore
and are not used yet.

## Pipeline

```
ml/.venv/bin/python -m ml.godark.tiger      # Tiger positions, statics, gaps -> /home/aiden/data/poseidon/godark/tiger (read-only)
ml/.venv/bin/python -m ml.godark.replay     # replay dvm/gaps.py over every stored position -> replay_gaps.parquet
ml/.venv/bin/python -m ml.godark.dataset    # labels + features -> examples.parquet (--gaps table: labels from the stored table)
ml/.venv/bin/python -m ml.godark.evaluate   # train, evaluate, report (report/), deployable artifact (/home/aiden/data/poseidon/models)
ml/.venv/bin/pytest -q ml/tests/test_godark.py
```

Run from the repo root. About 1 min export, 4 min replay, 20 s examples on 12 h of data. `ml.godark.target.SPEC` is
the target for ml-loop's runner (`--target godark`).

## Why replay the detector instead of reading the `gaps` table

The live table holds trustworthy flags only from about 23:40 UTC on 7 Nov: writing began at 00:54 on 8 Nov, the warm
start after a restart sees only the 2 h before it (older silences become `unknown`), and ingest was down 21:57 to
23:36. Every later restart re-checks long-open gaps without their old neighbours and turns them `unknown` too. The
replay runs the same code over all stored positions with one continuous state, and notes our outages (no position
from any source for 30 s, plus `gaps.KNOWN_STALLS`) the way the backend does. `replay.compare` measures agreement
with the table; the report states it, and also trains on the table's labels for comparison.

## Labels and population

- Grid: every 10 min, from 2 h after the data starts, skipping 30 min after each outage.
- Population: Class A ships whose latest fix is at most 10 min old, at 1 kn or more and not at anchor or moored (only
  those can open a gap).
- Label for horizon H: a gap of the ship with `start_ts` in [latest fix, made_at + H]. Labelled only if
  made_at + H + 35 min is inside the data (the detector needs 30 min to open a gap); otherwise NaN, never 0.

## Features

- The shared track features, `backend/dvm/predict/features.py` (`features_at`, FEATURE_VERSION f1): what the live
  predictor computes. The deployable model uses only these.
- Context, known at made_at (`dataset.CONTEXT_FEATURES`): Class A ships and messages heard nearby (0.2 degree buckets,
  3 x 3, last 10 and 30 min, and 2 h earlier), gaps detected in the 1 degree area in the last 6 h (first version only,
  so the flag is the one known at detection), this ship's earlier gaps, ship type group, flag state, source, local
  solar time. **Not in the live predictor yet**, so a model using them is marked `deployable: false`.

## Models and evaluation

- `global_rate`, `baseline` (base rate per 1 degree area and type group, shrunk to the area and global rates).
- `lgbm`: LightGBM per horizon, positive class weighted, isotonic calibration on a held-back slice (the latest part
  of the window after an embargo; ship-disjoint when the window is too short), exported as the breakpoints the
  backend's `GodarkModel` reads.
- 1 h: time split with a 1 h embargo. 6 h: ship-disjoint (6 h labels cover only a few hours of made_at so far).
  24 h: no labels yet. Intervals: 95% paired bootstrap over ships. Skill = 1 - Brier / Brier of the reference.
