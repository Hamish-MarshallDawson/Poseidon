# GFW go-dark risk (`godark_gfw`, #121)

Chance that a ship Global Fishing Watch saw in our four regions starts a **GFW gap event** (AIS likely off on
purpose, anywhere in the world) within **30 days** (primary) or **14 days** (second). 7 days is reported only.
Trained purely on GFW history, so it can use months of backfill and show whether more history helps.

```bash
ml/.venv/bin/python -m ml.godark_gfw.tiger      # read-only Tiger -> Parquet cache, incremental (re-pulls changed months)
ml/.venv/bin/python -m ml.godark_gfw.dataset    # cache -> examples.parquet (+ .json: rows, history used, label counts)
ml/.venv/bin/python -m ml.core.run --target godark_gfw            # train, evaluate on September, log, maybe promote
ml/.venv/bin/python -m ml.godark_gfw.curve      # learning curve: newest 1, 2, 4, all months before September
ml/.venv/bin/python -m ml.core.report --target godark_gfw         # leaderboard + learning-curve section
ml/.venv/bin/pytest -q ml/tests/test_godark_gfw.py
```

Data lives under `/home/aiden/data/poseidon/godark_gfw/` (`GODARK_GFW_DATA`): `<kind>/<YYYY-MM>.parquet` and
`manifest.json` (rows and newest `recv_ts` per month). Only the first step touches Tiger; everything after is local.
Threads are capped at 6.

- **Unit**: one row per ship and UTC week (Monday to Sunday) of `ais_presence` region rows. `as_of` = the newest
  `available_ts` of that week (about 5 days after the last day: GFW's delay).
- **Features** (only rows with `available_ts <= as_of`): region (most hours), flag, vessel type, days present and
  hours this week, hours over the previous 4 weeks and the trend, weeks seen in the previous 8, port visits (count,
  hours, days since the last), loitering (count, hours, mean distance from shore), encounters, earlier GFW gaps (in
  365 days, ever back to 2017, days since the last, its length and distance from shore). Distance to shore exists
  only on events: GFW per-vessel positions are unavailable (404), so presence rows carry none.
- **Labels** `y_7d`, `y_14d`, `y_30d`: a gap event starts in `(as_of, as_of + H]`. Null when `as_of + H` is past the
  newest gap start in the cache, because GFW publishes a gap only when it closes (gaps still open at the frontier are
  missing, so the last weeks slightly under-count).
- **Held-out set**: September 2026, fixed (`holdout_bounds`). Embargo 30 days, so training ends 1 August.
- **Models**: `baseline` (base rate by flag and type, shrunk to type and global), `global_rate`, `lgbm` (per horizon,
  class weights, isotonic calibration). Not deployable live: the backend computes no GFW features.

Labels only exist offshore: GFW's public gaps are 12 h or longer and start at least 50 nm from shore, so our straits
(the Danish straits above all) produce few positives; most come from Gulf of Oman ships.
