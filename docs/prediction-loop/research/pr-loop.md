# pr-loop: evaluation and the autonomous training loop

Basis: PLAN.md, the data-sources SYNTHESIS, `backend/dvm/store.py` and `sources/schema.py`, and read-only Tiger queries at about 04:15 UTC, 8 Nov. Labels: **[measured]** by me, **[documented]** in repo files, **[estimated]**.

## Recommendation

Build the loop on tables that already exist and fake nothing. Tiger already has append-only `scores` (ship, target, `made_at`, `horizon_s`, `model_version`, `features`) and `outcomes` (`score_id`, `resolved_at`, `censored`) [documented, store.py]; both hold 0 rows [measured]. Add one table, `route_predictions`, and one grader job. Skip a separate model-registry service: a `models/` folder plus a `model_runs` table is enough.

For the demo, the headline is a **time-machine backtest** on real data, plus a **live fast-grading counter**. The live counter is credible because we close gaps all the time: 960 closed gaps in about 11 h of own AIS [measured: 84 own_stall, 471 unknown, 229 coverage_gap, 176 deliberate_candidate]. Most are short (average 1.4 to 4.3 h). So several hundred real predictions per day can be graded within hours of being made, with no delayed archive.

Gemini only proposes configs from a closed schema. A deterministic script runs them, scores them and promotes by rule.

## The ledger and grading

`route_predictions` (append-only, same trigger as `scores`): `id, mmsi, made_at, as_of, model_version, horizon_s, lat, lon, sigma_m` (or `cov` / quantile radii), `base_lat, base_lon` (the baseline's prediction, stored at prediction time), `feature_version`, `gap_id`.

Storing the baseline's point beside every prediction makes skill scoring cheap and impossible to retroactively change.

Grading writes to `outcomes`, plus `err_m, base_err_m, truth_src, truth_kind`.

| Truth | Latency | Truth point | Notes |
|---|---|---|---|
| Own AIS reappearance | Hours | The first fix after `made_at + h`, or interpolation on the true track | Fast. Own coverage is shore-range only, so it is biased to ships near coasts; label it so. |
| Closed gap row (`next_lat/lon`) | Hours | Reappearance point | Already in `gaps`. Gives final displacement only. |
| Danish archive | About 3 days [documented] | Full track, so every horizon | Danish waters only; not ingested yet. |
| GFW gap events | 3 to 4 days [documented] | Off and on points worldwide | Blocked by #112 (0 rows now). |
| Sentinel-1 / GFW radar | Days | A coarse check only | Not a metric; a sanity check. |

Rule: a prediction is graded only once `available_ts` of the truth is at or after `made_at`, which is true by construction for real truth. Ungraded after a timeout is recorded as `censored` (the ship never reappeared in the window), never dropped. Dropping those would reward models that predict ships that come back soon.

## Metrics

- **Position error by horizon** (1, 3, 6, 24 h): haversine metres; report median and p90, not just mean (heavy tails).
- **FDE / ADE**: final displacement error at the horizon, and the average over the path where a full track exists.
- **Skill vs baseline**: `1 - median_err_model / median_err_baseline` per horizon, plus the paired win rate. Baseline = last course and speed (also store a "stay put" baseline for ships at anchor).
- **Calibration**: coverage of the stated radius (a 90% radius should contain truth about 90% of the time) and the mean radius. Track CRPS or a pinball loss if quantiles are used. A model with great error but no honest radius should lose on calibration.
- **Stratify** by horizon, ship type, speed class and coverage flag. One global number hides regressions.
- **Minimum n** per cell before any cell is shown or used (for example 30).

## Splits and leakage

- **Time split only.** Example's `as_of` = `made_at`. Features use rows with `available_ts <= as_of`; labels use rows after. The `available_ts` column [documented, schema.py] is the enforcement tool: a training query that filters on it cannot see delayed data from the future.
- **Embargo**: drop training examples whose label window overlaps the test start.
- **Group by ship**: no mmsi in both train and held-out within the same period; otherwise memorisation of a ship's habits inflates scores. Report a second number on seen ships.
- **Rolling-origin folds** (expanding window, 3 to 5 folds, each test block one day, train on everything before) rather than random k-fold. Random k-fold leaks neighbouring points of the same track.
- **Fixed held-out set**: freeze a list of (mmsi, `made_at`) case IDs once, store it in a table with a hash, never train on it, and never let Gemini see per-case results. Refresh it only by appending a new dated set; keep old ones for trend lines.
- **Honest limit**: our own AIS began 16:51 UTC on 7 Nov [measured], so roughly 11 h of positions (2.49 M rows, about 31k ships in the last hour [measured]). Median ship has 36 fixes [measured]. Before any delayed data lands, training must use the Danish archive (back to 2007 [documented]) and the held-out set must come from our own recent AIS. That is the only real out-of-time test.

## Champion and challenger

A challenger is promoted only if, on the frozen held-out set: median error beats the champion at every primary horizon (or at least the weighted sum) with a paired bootstrap 95% interval excluding zero; calibration coverage stays within 5 points of nominal; and no stratum with n at least 30 gets worse by more than 10%. Ties go to the champion. The registry row records data hash, config, git SHA, seed, metrics, and who proposed it (human, Gemini, or default). The champion pointer is one row; rollback is flipping it.

## Scheduling on our hardware

Training on the desktop (RTX 3080 12 GB, 16 cores, 31 GB RAM [measured]); the server only runs inference (2 vCPU, 4 GB). A simple loop: cron or systemd timer hourly runs `grade` (SQL, seconds), then `train_candidates` (the queued configs, each capped at, say, 10 min), then `evaluate` and `promote`. Models ship to the server as a small file (GBM is under a few MB; a small GRU is a few MB) via the existing deploy path. Inference of GBM or a small GRU on 2 vCPU for thousands of ships every few minutes is fine [estimated; measure before the freeze].

## Gemini in the loop

**Reads:** a compact summary JSON, not raw rows: per-horizon and per-stratum metrics for the last N runs, the config diffs, the champion's weak strata, data volume, and the cost of each run. It never sees held-out case-level rows or labels.

**May propose** (JSON schema, enum and range checked; reject anything else):

```json
{"model": "gbm|gru|baseline_blend", "features": ["subset of an allowed list"],
 "horizons_s": [3600, 10800, 21600, 86400], "train_window_days": [7, 365],
 "lr": [1e-4, 1e-1], "n_estimators": [50, 800], "max_depth": [2, 10],
 "loss": "l2|huber|quantile", "sample_weight": "none|recent|by_stratum",
 "seed": 0, "rationale": "<= 300 chars"}
```

**Guardrails against false improvement:**
1. Evaluation code, held-out IDs, split dates and metrics are outside its reach. It edits a config, never code.
2. Fix the number of proposals per round (for example 5) and apply a multiple-comparison correction: with many tries one will beat the champion by luck. Require the win to repeat on the next fold or next day's fresh cases before promotion.
3. Held-out set refreshes on a schedule so overfitting to it by selection decays.
4. Seeds fixed, plus a re-run with a second seed on any winner.
5. Log every proposal, including the rejected ones. Promotion is by rule only.
6. Sanity checks that fail the run: errors that look too good (for example near-zero at 24 h), or any feature with `available_ts > as_of`.

**Prior art** (from memory, [estimated], verify the links before citing): AutoML and hyperparameter search (Optuna, AutoGluon); "AI Scientist" style LLM-run experiments; FunSearch and AlphaEvolve (an LLM proposes, a fixed evaluator scores); Eureka (LLM-written reward functions). Common lesson: it works when the evaluator is fixed and not editable by the proposer.

## Showing it live in under 5 hours

1. **Backtest (the headline).** Pick a cut-off about 7 days back that still has data in Tiger (GFW AIS presence starts 8 Aug [measured]; but ship tracks only from our 16:51 start, so for a real week back we need the Danish archive). Train on data before the cut-off, predict, grade against archive data that arrived after. Chart skill vs baseline over horizons and a few rounds of "retrain with graded cases added". If the archive is not ingested in time, the fallback is: cut-off 6 h ago on our own AIS, which is smaller but real.
2. **Live fast loop.** Run the predictor over every ship that opens a gap; show a counter ("N predictions made, M graded, median error vs baseline"). Closed gaps arrive at a rate of tens per hour [measured: 960 in 11 h].
3. **Gemini panel.** Show one round: summary in, proposal out, the run, the verdict from the promotion rule (including a rejected proposal, which is the best proof the guardrail is real).
4. State plainly in the UI that a 3 to 4 day loop is shown as a backtest.

## What to build first (in order)

1. Baseline predictor and `route_predictions` + grader on closed gaps (about 2 h).
2. Metrics script and frozen held-out table (1 h).
3. One GBM correction model, trained on whatever tracks we have (2 h; depends on `pr-data`).
4. Promotion rule and `model_runs` table (1 h).
5. Gemini proposal step, last, if time allows.

## Open questions for Aiden

1. Is skill measured at gap reappearance only (cheap, available now), or also at fixed horizons (needs full tracks)?
2. Danish archive ingest: yes or no? The backtest is much stronger with it.
3. Overlap with Jake's `scores` and `outcomes`: reuse them for go-dark risk, and keep route predictions in their own table?
4. Should the held-out set be frozen now (tonight) from our own AIS?

Unverified: prior-art names, inference timings on the server, and the Danish archive's availability (see `pr-data`).
