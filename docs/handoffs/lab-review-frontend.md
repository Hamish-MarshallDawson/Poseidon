● PR 179 defect review: frontend/src/lab, plus the App.tsx and MapControls.tsx entry lines

  I found four real defects. Three show wrong or misleading numbers to a judge, and one can crash the whole app. All four are confirmed against the live local API (:55570) and the running app at #lab.
  The lab vitest suites pass (6 files, 53 tests).

  Fix before merge

  1. runs/shape.ts:176 — decisions are credited to "the baseline" when the run was judged against a champion, and hand promotions read as passes.
  - The code only recognises a champion when against starts with the word champion. On real data, against is a run id (route-dma14-v3, route-dma14-v1) or "global base rate".
  - On the page, route-dma90-v2 and route-dma14-v3 both say "promoted: beat the baseline". They were in fact promoted by hand over the previous champion.
  - route-dma14-v2's detail labels its comparison column "vs baseline", and its weakest areas "vs the baseline".
  - go-dark's champion says "promoted: beat the baseline". It was promoted by hand (decision.by: "human"), its 1 h skill is −3.3% and its 6 h interval [−1.5%, +6.5%] includes zero. That is a
    misleading pass label.
  - Fix: if decision.by === 'human', say "promoted by hand" and show the first reason. Only say "the baseline" when against matches baseline, base rate, dead reckoning or "no champion"; otherwise say
    "the champion".

  2. improve/shape.ts:173-174 — the same inference in the Improve tab gets it wrong in the other direction.
  - Anything without "baseline" in against becomes "the champion". With promote true it also always claims "at every primary horizon".
  - go-dark's promoted marker says "beat the champion at every primary horizon". There was no champion and no horizon win.
  - route-dma14-v1's marker says "beat the champion…". It was compared with dead reckoning.
  - Fix: share one helper with runs/shape.ts that handles hand promotions as in #1.

  3. Go-dark mixes two statistics and two horizons on one axis.
  - The held-out "skill" is log-loss skill at 6 h (+2.6%). The live figure is Brier skill, at 1 h on the card and at 6 h in the Improve chart. The held-out Brier skill at 6 h is actually +1.2%.
  - This shows up in three places:
    - Overview.tsx:85-110 (SkillStrip): puts the 6 h log-loss point and the 1 h Brier diamond on one strip, under a single legend, "skill over the base rate".
    - improve/shape.ts:120-123 with Improve.tsx:337-342: draws the 6 h Brier backtest line over the 6 h log-loss step, against one y-axis labelled "skill over the base rate".
    - Improve.tsx:353: prints "Live skill is below the offline result" by comparing the 1 h Brier value (−7.8%) with the 6 h log-loss value (+2.6%).
  - Fix: name the statistic in the held-out label (metrics.loss_name, i.e. "log-loss skill"), or use the held-out Brier skill from metrics.summary[h].brier_skill. Only compare live with held-out at
    the same horizon and on the same statistic.

  4. improve/shape.ts:127-133 — the "live on our feed" line for the route champion averages in a retired model.
  - The code only drops baseline rows. Each hour it averages every other model version, weighted by sample size.
  - In the 3 h bucket at 1794121200000, live rows hold dma14-v2 (skill 8.5%, n 19) and route-dma90-v2 (27.8%, n 43). The chart plots 21.9% and calls it the champion's live skill.
  - The backtest line averages the two models the same way in every hour.
  - Fix: keep only rows whose model_version matches the champion. Use the same -calN handling as live/shape.ts:headline, and apply it in liveSkill.

  5. runs/Runs.tsx:88 — a failed refresh can crash the whole app.
  - byId.get(current)! assumes the selected run is still in the list. useLab reloads every 60 s, and when an endpoint fails, api.get silently swaps in the fixtures.
  - Scenario: the auto loop adds a run that isn't in fixtures.json, a user selects it, then one /lab/runs refresh fails (a backend restart or token blip). byId.get(current) returns undefined, and
    .target throws during render.
  - There is no error boundary anywhere in src/, so the React root unmounts and the map goes blank too.
  - Fix: derive current only from runs in byId (fall back to shown[0]). Optionally wrap <Lab> in LabEntry.tsx in an error boundary.

  Checked and found sound

  - Entry points: LabRoot is a lazy import, mounted once in Monitor. LabChip sits in the toolbar. Opening and closing #lab through the hash works.
  - Auth: the frontend sends the Bearer token as the app does. The routes' auth is in backend code, outside this scope; locally they answer with no login.
  - Fallback: each endpoint falls back to fixtures, and the "Sample data" tag appears whenever any endpoint is the sample. It didn't appear on the live instance.
  - Empty data: the guards hold. Proposals are empty on real data and the page shows the empty-state copy.
  - Graded-outcome total: the live and backtest cumulative counts add up to totals.graded_outcomes (122,093).
  - Units: the run tables use metres for route and unitless values for the others, and horizon labels are correct.
  - Hooks order: correct in Improve, LiveTrackRecord and Runs.
  - 390 px (Firefox, live data): no element overflows outside the scroll containers, and .lab's scrollWidth equals 390.

  Optional polish

  - The same "route live skill at 3 h" shows three different numbers. The card and Improve heading say 36%. The live section says about 35%, because it averages hourly medians weighted by count. The
    Improve points show per-hour values. Using summary.live as the single headline figure, or saying "pooled hourly medians", would avoid this.
  - closeLab replaces the current history entry instead of going back. After opening from the chip and closing, Back stays on the same URL once.
  - Calibration rows in the run detail use fmtStat, so route coverage would read "0.8000 (target 0.8000 ± 0.05)" rather than percentages. No route run on real data has stored calibration checks, so
    this is not visible today.

  Not verified
