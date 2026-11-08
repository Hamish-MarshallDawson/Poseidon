# Model Lab v2: the final wave (10:00 UTC, hard stop 10:25)

Read `docs/handoffs/COMMON.md`, then `docs/handoffs/lab.md` (contract, now implemented on `origin/lab-integrate`).
Absolute paths under `/home/aiden/.herdr/worktrees/Hedged-Bets-hacktheburgh/59-ingest-resilience/`. Base: your
worktree is already on a branch from `origin/lab-integrate`. **Push a working version by 10:18**, then polish until
10:24, push, and finish your turn. Smallest change that works. Don't merge, no PR. Tiger read-only. Commit small, your
own files by name.

Live local instance (real data, the current Lab): API `http://localhost:55570` (no login), app
`http://100.81.113.30:55572/#lab`. For your own browser checks serve your branch on your own port (copy
`frontend/vite.lab-remote.config.ts` from `/home/aiden/.herdr/worktrees/Hedged-Bets-hacktheburgh/lab-integrate/frontend/`,
set host 127.0.0.1 and your port, keep the `/lab` proxy to 55570; never commit it).

## Goal
The Lab must be understood in 30 seconds by someone new to ML, show the value and the technical depth at a glance, and
keep the details one click away. Only real data at the demo (no mock): the empty or loading states must be honest.

Design rules:
- No jargon on levels 1 and 2: never "skill", "Brier", "log loss", "dead reckoning", "isotonic". Plain units: km, %,
  "N times more likely", "7 in 10". The comparison for route is "a straight-line guess", and only in details.
- One short line per card or chart, as a caption, never paragraphs. Numbers first.
- Status colour: green on target, amber drifting, red off target, grey no data. The same everywhere.
- A Gemini badge on anything Gemini proposed; "rule" decides, shown as ✓/✗.
- Existing tokens and styles, inline SVG chart kit in `frontend/src/lab/charts/`, no new dependencies. Desktop first,
  works at 390 px. `npm run build`, `npm run lint`, `npx vitest run` pass.

Structure:
- **Home** (`#lab`): a slim totals strip (training runs, Gemini proposals, graded predictions) and **3 model cards**
  (Route: where is a silent ship now? / Go-dark: will this ship go dark? / Fishing: will it fish in a protected area?):
  headline sentence, status line with dot, a small champion sparkline, "N runs · M by Gemini", click to open.
- **Model page** (`#lab/route`, `#lab/godark`, `#lab/fishing`; Escape or back returns home): the **pipeline strip**
  on top (New data → Gemini proposes → Train → Judge on frozen test → Promote / reject → Live grading, each with its
  real count and latest time), then 4 tabs: **Overview** (champion, 3 key numbers, one chart of the champion over time
  with live dots), **Champions & challengers** (the centrepiece), **Live**, **Data**.
- **Run side panel** (opens over the page from any run): what changed versus the parent, Gemini's reasoning, the rule
  as a ✓/✗ checklist, then the technical numbers (intervals, statistic names, strata).

Headline numbers (from `/lab/summary` once lab-plain adds them; until then derive them in the frontend from existing
fields): route "Finds a silent ship within X km after 3 hours" (live median error at 3 h) + "Circle held the ship N% of
the time · target 80%"; go-dark "Flagged ships go dark N× more often" (top-10% lift) + "Says P%, actual Q%"; fishing
"Spots N in 10 protected-area fishing weeks" (held-out recall at the champion's operating threshold) + live status.

## Briefs

### `lab2-nav` (frontend/src/lab: Lab.tsx, home, model page, nav, pipeline strip, style)
Replace the current single long page with Home + Model page + tabs + hash routing, the new simplified visual style
(bigger numbers, fewer words), and the pipeline strip component (counts from `/lab/summary.pipeline` when present, else
derived from runs, proposals, events and summary.totals). Define and export the props each tab gets so lab2-champions
and lab2-live mount in your slots: `<ChampionsTab model runs proposals events loadDetail />`,
`<LiveTab model metrics />`, `<DataTab model data />`, `<OverviewTab model runs events metrics />` (you build
Overview). **Push the shell and the props by 10:10** so the others can merge it.

### `lab2-champions` (frontend/src/lab/runs/ and a new champions/ folder)
The centrepiece tab: a timeline per model (x = time, y = the primary number in plain words; every run a dot, champions
joined by a line, rejected challengers grey, Gemini-proposed runs badged), a "latest decision" card in one plain
sentence ("Gemini proposed fewer leaves: rejected, not better than the champion at 3 h"), the proposals list (valid,
invalid, duplicate with the reason), and the run side panel. Reuse runs/shape.ts and the decision-label helper.

### `lab2-live` (frontend/src/lab/live/ and a new data/ folder)
Live tab: 2 big tiles (accuracy versus target, calibration as a simple gauge "circle held 44% · target 80%"), a 24 h
trend line, and per-horizon detail behind an "Show details" toggle. Data tab: 3 counters (graded predictions, training
examples, history depth), a growth chart (live and backtest), the sources list. Plain words only.

### `lab2-plain` (backend/dvm/lab/ only)
`/lab/summary`: add per model `headline {text, value, unit}` and `status {level: ok|warn|bad|none, text}` in plain
words as above, `pipeline {new_data, proposed, trained, judged, promoted, rejected, graded, last_ts each}` (from
outcomes, ml_proposals, model_runs, ml_events), and `runs_total`, `runs_gemini`. Remove "dead reckoning" from every
user-facing string in backend/dvm/lab (notes, labels, rule checks): say "straight-line guess". Fishing headline: held-out
recall at the champion's threshold if stored in the run metrics, else the AUC-PR in words ("ranks 7 in 10 correctly").
Tests on the local database (your own database name on `replay-tsdb`, port 55545). Push by 10:15.

### `lab2-cycle` (ml/ only)
Make the first server run of `python -m ml.auto` (PR 171, now in this branch) succeed first time and land in the Lab:
(1) run it locally end to end on **all three real targets** (godark, fishing, route) with `ML_NO_REFRESH` unset where
the data refresh works from this PC (Tiger read-only, GFW 5 min) and `--no-deploy`, in a scratch `POSEIDON_DATA`
copy, without Gemini (no `ML_GEMINI_API_KEY`); fix whatever breaks; time each step and keep the whole cycle under
about 20 min on 3 threads (trim rounds, examples window or folds if needed, via env or flags); (2) at the end of a
cycle, import its history into the Lab tables automatically: call `dvm.lab.importer` on the cycle's bundle when
`ML_LAB_IMPORT_URL` (or the backend's TIGER_DATABASE_URL with an explicit `ML_LAB_IMPORT=1`) is set, never by default;
(3) write the exact server commands for one manual cycle (with Gemini via `ML_GEMINI_API_KEY`, the import on) into
`ml/deploy/README.md`. Report the measured times.

### `fishing-live` (ml/ and backend/dvm/predict/ minimal; frontend only the Lab fishing card if needed)
Serve the fishing model live without the held GFW ingest: a scorer (`python -m ml.fishing.score`) that fetches the
last 8 weeks of GFW fishing events for our regions from the GFW API (polite, as `ml.fishing.fetch`), builds this week's
features for vessels active in it (the training code's own feature builder, `available_ts <= as_of`), scores them with
the champion (`/home/aiden/data/poseidon/models/fishing/champion.json`), and writes rows to Tiger `scores`
(target `fishing_mpa_7d`, mode `live`, model_version the run id, made_at the week start, features snapshot) only with
`--write --allow-tiger`; plus grading: rows whose week has passed get an `outcomes` row (label from the events). Dry
run here, read-only: report how many vessels are scored and the score distribution. Hook it into `ml.auto` as an
optional step (`ML_FISHING_SCORE=1`). Make `/lab/summary` and `/lab/metrics` count fishing scores and outcomes
(coordinate field names with lab2-plain by reading its pushed branch; keep your backend change to metrics.py small).
