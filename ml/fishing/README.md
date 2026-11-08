# Fishing in protected areas (`fishing`, #157)

Chance that a fishing vessel Global Fishing Watch saw fishing in our four regions has a **fishing event inside a
marine protected area in the coming week** (`y_mpa_7d`). Trained straight from the GFW API, without waiting for the
backend ingest (`gfw-fishing`, #157). GFW data is CC BY-NC 4.0.

```bash
ml/.venv/bin/python -m ml.fishing.fetch --minutes 15      # GFW /events -> Parquet per region and month (polite, serial)
ml/.venv/bin/python -m ml.fishing.dataset                 # cache -> examples.parquet (+ .json: rows, label rates)
ml/.venv/bin/python -m ml.core.run --target fishing       # train, evaluate on the held-out weeks, log, maybe promote
ml/.venv/bin/python -m ml.core.report --target fishing    # leaderboard HTML and JSON
ml/.venv/bin/pytest -q ml/tests/test_fishing.py
```

Data lives under `/home/aiden/data/poseidon/fishing/` (`FISHING_DATA`): `events/<region>/<YYYY-MM>.parquet` and
`manifest.json`. Port visits and gear type come from the read-only Tiger cache of `ml.godark_gfw.tiger`
(`/home/aiden/data/poseidon/godark_gfw/`), if present; nothing here connects to Tiger. Threads are capped at 6.

- **Why this label.** The other candidate, "the next fishing event carries `potentialRisk = true`", had no positives:
  `potentialRisk` was false on every event we pulled. MPA fishing is common (about a third of events, mostly in the
  Danish straits), so the weekly label has a usable rate.
- **Unit**: a vessel and a UTC week (Monday 00:00 = `as_of`), for vessels with a known fishing event that started in
  the previous 8 weeks.
- **Leakage clock**: features use only events with `available_ts <= as_of`: the end of the event's last UTC day
  plus GFW's 4-day publication lag (`gfw.available`). Labels are null where the week runs past the frontier (newest
  event start minus 2 days).
- **Features**: fishing hours inside and outside MPAs (28 and 90 days), shares of events inside an MPA, a no-take
  MPA, the 12 nm zone, on an EEZ border (more than one EEZ tagged) or flagged `potentialRisk`, recency, weeks active,
  distance from shore, speed, port visits, flag, gear type, latest public authorisation status, region, month.
- **Held-out set**: the 13 weeks from Monday 3 Aug 2026 (`holdout_bounds`); embargo one week.
- **Models**: `baseline` (rate by gear and flag, shrunk to gear then global: the reference for skill and promotion),
  `persistence` (rate by recent MPA fishing and region: a stronger reference, reported), `global_rate`, `lgbm`
  (class weights, isotonic calibration on the latest quarter of the training window). The artifact uses the backend's
  go-dark format (`heads` with `model` and `calibration`) but is marked `deployable: false`: the live backend does not
  compute these GFW features yet.

Fishing inside an MPA is not by itself illegal (many MPAs allow some fishing); the score says where to look.
