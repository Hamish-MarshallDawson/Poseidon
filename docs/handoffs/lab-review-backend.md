  1. The go-dark card compares two different metrics at two different horizons as if they were the same thing
  - Files: backend/dvm/lab/metrics.py:276-290 (note), :379-382 and :400, plus frontend/src/lab/Overview.tsx SkillStrip.
  - The held-out number is the champion's log-loss skill at 6 h. The live number is Brier skill at 1 h: Tiger has no live dark_6h grades yet, so the code falls back to 1 h.
  - On screen at 390 px with real data: "Held-out +2.6% skill over the base rate at 6 h" and "Live −7.8% Brier skill over the base rate, 1 h" sit on one chart axis. The note reads "live skill below
    offline".
  - This is a different statistic at a different horizon, and the held-out label never says "log-loss". It's the most visible honesty problem in the Lab.
  - Fix: compare only when the statistic and horizon match (the converted go-dark runs already store summary[h].brier_skill, so the held-out Brier skill at the live horizon is available). Otherwise
    drop the comparison note and the shared axis, and label the held-out number as log-loss skill.
  2. recalibrate.write_route gives a refused head the other heads' factor
  - File: ml/core/recalibrate.py:104-110.
  - kept.get(int(hs)) is None both for a head that had too little data and for a head that was measured and refused. Both get the median factor of the kept heads.
  - I ran it in memory: the 1 h head measured 78.7% coverage, so its fit was refused (k80 0.999, keep False). The 3 h head fitted k80 1.59 and was kept. The output still scales 1 h radii by 1.59 and
    marks it measured: False. So 1 h circles that were already calibrated get about 59% larger and over-cover.
  - ml.auto runs this with --apply by default, so champions.json would be rewritten if the timer is installed.
  - Fix: use the default factor only for heads that are missing from fit. For a head that is in fit with keep False, use 1.0.
  3. Hand-promoted runs read as "promoted: beat the baseline" with an all-pass checklist
  - Files: frontend/src/lab/runs/shape.ts:176-182 (decisionLine) and backend/dvm/lab/records.py:133-166 (rule).
  - For route-dma90-v2 (promoted by hand, compared with route-dma14-v3), the detail shows "promoted: beat the baseline" and eight green calibration checks. The champion and the baseline are never
    mentioned.
  - The record's own reasons say "not a paired test". For godark-lgbm-…051156 they say "Brier skill … does not exclude zero", yet it also shows "beat the baseline".
  - Fix: when decision.by == "human", say "promoted by hand over <against>". In rule(), add a check with passed: null saying no paired test was run.
  Lower severity
  4. After cal1 is installed, the route card shows the old model's live coverage under the new name
  - Files: backend/dvm/lab/metrics.py:152-163 (pick_version), :249-259 and :235-246.
  - With the champion set to route-dma90-v2-cal1 and no cal1 grades yet (at least 3 h at the 3 h horizon), pick_version falls back to route-dma90-v2.
  - The card would say "Champion route-dma90-v2-cal1 … 80% circle coverage 44%, Off target", which is the uncalibrated model's number. Overview.tsx never shows live.model_version.
  - "Since" would also be the recal folder's build time (about 08:19), not when it went live, because a recalibrated event of the exact version matches first.
  - Fix: return live: null ("no live grades for this version yet") when the picked version isn't the champion, or show the picked version on the card. Only count deployed events for "since".
  Checked and sound
  - Auth: both routers sit behind Depends(require_login) at router level. Paths are validated and every query is parameterised.
  - Start-up: the predictor's lab_schema.setup is wrapped in try/except, and its DDL is additive (IF NOT EXISTS). app.py only adds two include_router lines.
  - Importer:
    - refuses Tiger without --allow-tiger;
    - stays idempotent (skips a status a run already has, never rolls a status back, and is safe with the append-only trigger);
    - re-running it updates proposals instead of duplicating them.
  - Tiger timing (read-only, today's 126k outcomes):
    - every metrics, data and summary query runs in 0.16–0.56 s;
    - recalibrate.fetch_rows takes 1.6 s.
  - Empty or partial data: an empty model_runs on Tiger (the state before import) works, and so do missing ml_* tables (they return defaults) and empty reliability and lift results.
  - Route numbers: live skill (1 − median ÷ dead-reckoning median at exactly 3 h) matches the offline statistic. Live horizons are exactly 3600, 10800 and 21600, so the CASE bucketing is safe.
  - Bundle: events, deploy mapping (dma14-v2 → route-dma14-v3) and run status are all correct. The rule checklists match the stored decisions for every run.
  - 390 px: no horizontal page scroll (document width 390). Only the runs table scrolls, inside its own wrapper.
  Not verified and residual risk
  - OUTCOMES_BEFORE and TOTALS count across the whole ledger. They are fast today, but they grow with the ledger, and the Lab polls all six endpoints every 60 s on the shared store pool. Bounding or
    caching them would help as the ledger grows.
  - /lab/metrics?hours=168 at hourly buckets can pass MAX_ROWS = 2000. Results are sorted oldest first, so the newest buckets would be cut silently. The frontend only requests 24 h today.
  - Once installed, the ml.auto timer applies recalibrations to the live champions.json by default (only --no-deploy stops it). That contradicts the board's line that Hamish decides cal installs. It's
    an install-time decision, not a code bug.
  - The cycle's lab-history file on the server is only appended to; nothing imports it into Tiger, so the Lab stays at the last manual import.
  Optional polish
  - "95% interval[+62%" is missing a space before the bracket.
  - The godark_gfw strata detail repeats "type_band=FISHING, type_band=PASSENGER" once per horizon, with no horizon label.
  - cycle.last counts the cal1 build that isn't installed as the last cycle.
