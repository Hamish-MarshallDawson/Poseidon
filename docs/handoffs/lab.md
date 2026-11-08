# Model Lab wave: briefs and the shared contract (08:55 UTC, 8 Nov)

Read `docs/handoffs/COMMON.md` first (absolute path under
`/home/aiden/.herdr/worktrees/Hedged-Bets-hacktheburgh/59-ingest-resilience/`). Goal: a **Model Lab** view that shows
how the three models (route, godark, fishing) improve over time: champions and when they changed, every run with
its config, data and evaluation, why the rule promoted or rejected it, what Gemini proposed, how the models do live
on our own feed, and how much graded data has built up. It must be easy to understand for a judge in 30 seconds and
honest (show live under-performance and rejected proposals, don't hide them).

Base every branch on `origin/main` (cebf8ae or later). Don't merge; the orchestrator (Aiden's session) integrates all
branches into `lab-integrate` and releases once. Tiger is read-only for you (`default_transaction_read_only=on`),
never print secrets. Commit small, stage your own files by name. Post to the board only if blocked; report to the
orchestrator by finishing your turn with: branch, commits, what you verified, what you could not.

Time box: a tested first version **in 35 minutes**, then polish until told to stop. Smallest change that works.

## Shared contract (every endpoint `GET`, same login as `/model/leaderboard`, JSON, times in epoch ms)

**Run record** = the ML registry's run JSON, unchanged (see
`/home/aiden/data/poseidon/registry/fishing/runs/fishing-20261108T071922-e2db5c.json`), plus `source`:
`run_id, target, model, config, data_hash, train_from, train_to, artifact, proposer ("human"|"default"|"gemini"),
parent_run, status ("champion"|"retired"|"candidate"|"rejected"), created_at (ms), loop_id, round, git_sha,
source ("pc-aiden"|"desktop-hamish"|"server"), metrics: {state, holdout {target,name,start,end,hash,n},
split {n_train,n_test,embargo_s}, statistic, loss_name, loss_unit, summary {<h>: {...}}, skill {<h>: {n, stat,
baseline_stat, skill, skill_lo, skill_hi, win_rate}}, calibration [{name, horizon_s, value, nominal, tol, ok}],
strata, strata_baseline, cv, decision {promote, against, alpha, n_comparisons, horizons {<h>: {cand, ref, diff, lo,
hi, win}}, calibration [...], reasons [str]}, seconds}`. Runs that predate the registry (route dma14/dma90,
godark-lgbm) are converted into this shape by the history import; fields they lack are null.

| Endpoint | Returns |
|---|---|
| `/lab/summary` | `{generated_at, models: [{target, label, champion: {run_id, version, since, proposer, source}, offline: {primary_h, skill, skill_lo, skill_hi, holdout}, live: {hours, n, primary: {name, value, ref_label}, calibration: {name, value, nominal, ok}} or null, deployed: bool, note}], cycle: {state: "manual"|"scheduled", last, next}, totals: {runs, proposals, graded_outcomes, graded_last_hour}}` |
| `/lab/runs?target=` | `[run record]`, newest first, `metrics.strata*` dropped |
| `/lab/runs/{run_id}` | run record (full) plus `parent` (its run record or null), `config_diff [{key, parent, value}]`, `rationale` (the proposal's text or null), `rule [{check, passed, detail}]` (one per primary horizon win, per calibration check, and the second-seed confirmation), `confirm {run_id, passed} or null` |
| `/lab/proposals?target=` | `[{id, target, loop_id, round, proposer, created_at, proposal, valid, errors [], rationale, source, run_id, outcome: "champion"|"candidate"|"rejected"|"invalid"|"duplicate"}]` newest first |
| `/lab/events?hours=` | `[{ts, target, kind: "trained"|"promoted"|"rejected"|"recalibrated"|"deployed"|"proposal", run_id, version, label, detail {}}]` oldest first (`hours` absent = all) |
| `/lab/metrics?hours=24&bucket=3600` | `{bucket, route: [{t, model_version, horizon_s, n, cov80, cov95, median_err_m, baseline_median_err_m, skill}], godark: [{t, target, model_version, n, positives, mean_p, hit_rate, brier, brier_skill}], reliability: [{target, bins: [{p_mean, hit_rate, n}]}], lift: [{target, top_share, top_hit_rate, all_hit_rate}]}`; `mode` live and backtest both count (field `mode` in each row) |
| `/lab/data` | `{outcomes: [{t, mode, n, cumulative}], sources: [{src, stream, label, oldest, newest, windows, rows}], training: [{target, run_id, created_at, n_train}], holdouts: [{target, name, n, start, end, hash}]}` |

Storage: runs in the existing Tiger table `model_runs` (`backend/dvm/predict/schema.py`, `RUN_COLS`; one row per
status a run reaches, the newest row is its status). New, additive: `ml_proposals` (the proposal record above) and
`ml_events` (the event record above). History bundle: `data/lab-history/{runs,proposals,events}.jsonl` (one record
per line, the shapes above), committed (small), imported on the server with
`python -m dvm.lab.importer --bundle data/lab-history --allow-tiger` (idempotent).

Sample data for the frontend: `frontend/src/lab/fixtures.json` (`{summary, runs, run_detail: {<run_id>: ...},
proposals, events, metrics, data}`, the same shapes), written by the orchestrator from this morning's real numbers;
`lab-history` replaces it with the real bundle when ready. The Lab must work on fixtures alone.

## Design rules (frontend agents)
- No Figma: use the existing design tokens (`frontend/src/tokens/tokens.css`), the panel and window styles
  (`frontend/src/panels/panels.css`, `frontend/src/windows/windows.css`, `frontend/src/ui/`), the same fonts, colours,
  radii and spacing, light and dark as the app does. Look at `frontend/src/forecast/ForecastCheck.tsx` for the
  closest existing view.
- No new dependencies. Charts are inline SVG built from `frontend/src/lab/charts/` (lab-shell builds these first:
  `<Chart>` with x/y scales and axes, `<Line>`, `<Step>`, `<Band>` for intervals, `<Markers>`, `<Bars>`, `<RefLine>`
  for nominal values, tooltips on hover). Until they land, build your layout and tables; wire charts after.
- Plain words on screen: "skill over dead reckoning", "80% circle held the ship 81% of the time (target 80%)",
  "rejected: did not beat the champion at 3 h". Every number says what it is compared against.
- Width: desktop first, readable down to 390 px (stack panels). `npm run build` and `npm run lint` must pass; add
  vitest tests for any data shaping you write.
- Hands off: `frontend/src/map/`, `frontend/src/forecast/` (FrontEndLead is on the map overlay), `App.tsx` except
  lab-shell's one entry point.

## Briefs

### `lab-history` (branch `lab-history`, ml/ and data/lab-history/)
Gather every model run we have into the bundle. Sources on this PC: `/home/aiden/data/poseidon/registry/**` (registry
JSON: fishing, godark_gfw), `/home/aiden/data/poseidon/models/**/model.json` (godark-lgbm-*, fishing, godark_gfw),
`/home/aiden/data/poseidon/route/artifacts/**` and `route/dl/dma90-v2/x/*report.json` (route dma14-v1/v2, dma90-v2,
holdout), `/home/aiden/data/poseidon/models/reports/*.json`, the recalibrations in
`/home/aiden/data/poseidon/recal/*/model.json` (`recalibration` blocks: events kind `recalibrated`), and the champion
history in `docs/prediction-loop/PLAN.md` (deploy times: events kind `deployed`). Convert pre-registry artifacts into
the run record shape (metrics from their reports; null what is missing; `source` `pc-aiden` or `desktop-hamish` for
the dma90 report). Derive events (trained/promoted/rejected/deployed/recalibrated) and proposals (registry
`proposals/` if any). Write `python -m ml.core.history export --out data/lab-history` (reruns cleanly) and, on the
`170-auto-loop` branch's `ml/auto.py` (base your branch on `origin/170-auto-loop`), append each cycle's runs,
proposals and events to the same bundle format under `$POSEIDON_DATA/lab-history/`. Tests for the conversion. Then
replace `frontend/src/lab/fixtures.json`'s `runs`, `run_detail`, `proposals`, `events` with the real bundle content in
a separate commit (only that file, after lab-shell has created it: coordinate by finishing your turn and saying so).

### `lab-store` (branch `lab-store`, backend/dvm/lab/ except metrics.py)
`backend/dvm/lab/` package: `schema.py` (additive `CREATE TABLE IF NOT EXISTS ml_proposals`, `ml_events`, indexes),
`importer.py` (CLI above; reads the bundle, upserts runs into `model_runs` without duplicates, proposals, events;
refuses Tiger without `--allow-tiger`), `routes.py` with `/lab/runs`, `/lab/runs/{run_id}` (config_diff, rule,
confirm, rationale derived from the record and its proposal), `/lab/proposals`, `/lab/events`, and `make_router(...)`
like `backend/dvm/predict/routes.py`. Mount it in `backend/dvm/app.py` with one `include_router` line (and schema
setup where the predict schema is set up). Tests against a local TimescaleDB (`replay-tsdb` on port 55545 is running:
`SOURCES_TEST_DATABASE_URL=postgresql://postgres:local@127.0.0.1:55545/postgres`), using a tiny bundle fixture.

### `lab-metrics` (branch `lab-metrics`, backend/dvm/lab/metrics.py only, plus its tests)
`/lab/metrics`, `/lab/data`, `/lab/summary` as a `make_router(...)` in `metrics.py` (lab-store mounts both routers;
if lab-store's package isn't there yet, create `backend/dvm/lab/__init__.py` empty and say so). From Tiger tables
that exist now: `outcomes` joined to `route_predictions` and `scores` (see `backend/dvm/predict/routes.py` LIVE_ROUTE
and LIVE_DARK, and `ml/core/recalibrate.py` on `origin/170-auto-loop` for the joins), `source_windows`, `model_runs`,
and the champions from `/health`'s predict block (`running()` as predict routes get it). Bucket in SQL
(`time_bucket` or integer division), keep each query bounded by `hours` and indexed columns, at most a few hundred
rows out. Measure each query against Tiger read-only and keep each under about 2 s. Tests on the local database.

### `lab-shell` (branch `lab-shell`, frontend/src/lab/ shell, data, charts; one entry in the toolbar)
The Lab as a full-screen view opened from the app's toolbar and by `#lab` in the URL (Escape or a close button
returns to the map; no router library). `frontend/src/lab/`: `Lab.tsx` (layout: overview cards on top, then the
sections `improve/`, `live/`, `runs/` which the other agents fill; give each a placeholder slot and export a clear
props interface), `api.ts` (fetch the seven endpoints with the app's existing auth token pattern from
`frontend/src/data/live.ts`, fall back to `fixtures.json` per endpoint on error or when the app runs on mock data),
`types.ts` (the contract), `fixtures.json` (copy it from the orchestrator's
`/home/aiden/.herdr/worktrees/Hedged-Bets-hacktheburgh/59-ingest-resilience/docs/handoffs/lab-fixtures.json`),
`charts/` **first, within 15 minutes, then commit and push so the others can use it**, and `Overview.tsx` (one card
per model: champion, since, offline skill with interval, live primary metric and calibration with a pass/fail
marker, deployed or not, plus a totals strip and the cycle state). Screenshot it with Playwright at 1440 and 390 px.

### `lab-improve` (branch `lab-improve`, frontend/src/lab/improve/)
"How it improved": per model (tabs or small multiples), a step line of the champion's offline primary skill over time
(each step a promotion, with its interval as a band), the live skill as a line over it (from `/lab/metrics`), and
event markers (promoted, rejected, recalibrated, deployed, Gemini proposal) with a tooltip naming the run, what
changed and why. Below it, the recalibration log: each `calN` with its factors and before/after coverage, kept or
rejected and why. Consume `Lab.tsx`'s props; charts from `lab/charts`.

### `lab-live` (branch `lab-live`, frontend/src/lab/live/)
"Live track record" from `/lab/metrics`: route coverage at 80% and 95% per hour against nominal reference lines,
median error against dead reckoning, per horizon (selector); go-dark reliability diagram (predicted against
observed, diagonal reference, bin sizes) and the top-10% lift, plus Brier skill over time with zero marked.
"Data collected" from `/lab/data`: cumulative graded outcomes (live and backtest), history depth per source (a bar
per source from oldest to newest), training examples per run, and the frozen held-out sets.

### `lab-runs` (branch `lab-runs`, frontend/src/lab/runs/)
Run table from `/lab/runs` (filters: model, proposer, status; columns: when, model, proposer, change versus parent,
data window and n_train, primary skill with interval, decision) and run detail on click from `/lab/runs/{id}`: config
diff against the parent, Gemini's rationale, skill per horizon with intervals against the champion and the baseline,
calibration, **the promotion rule as a pass/fail checklist**, weakest strata. Proposals log from `/lab/proposals`
(including invalid and duplicate ones with their errors), linked to their runs.
