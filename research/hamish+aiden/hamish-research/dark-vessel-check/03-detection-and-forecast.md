# 03. Detection and forecast method check

Checked Sat 7 Nov 2026, about 16:30. Area: the "find it" and "predict and decide" parts that G-Research and HRT will judge. Build time left: about 17 h (feature freeze 09:00 Sunday).

## 1. Verdict: AMBER

A credible, honestly scored detect, predict and decide pipeline fits in 17 hours, but only in a reduced form, and only if one decision is made now: **forecast "a suspicious gap starts in the next 6 h", not "this ship is shadow fleet".** The detector is easy and well precedented. The weak point is evaluation: the number of real events is unknown until the live log has run for a few hours, and top-10 precision on a handful of events will have very wide error bars. The fix is to frame the score honestly (confidence intervals, a cell-level baseline, an ablation) and to start logging frozen forecasts early. The "GFW-style" 12 h / 50 nm rule cannot be used in a Baltic demo, so our gap detector is a different and weaker thing than GFW's, and we should say so.

## 2. Claims and findings

| # | Claim | Status | Evidence | Note |
|---|---|---|---|---|
| 1.16 | GFW calls a gap intentional only if >= 12 h, starts >= 50 nm from shore, in good reception | **partly (more conditions)** | [pipe-gaps README, Apache-2.0](https://github.com/GlobalFishingWatch/pipe-gaps) | There are four conditions, not three: gap >= 12 h; OFF point > 92,600 m (50 nm) from shore; satellite reception at the OFF point > 10 positions/day for its 1 degree cell and AIS class; and >= 14 satellite positions in the 12 h before the gap. Classification only applies from 2017 (Spire satellites). |
| inconsistency | Pitch says P(go dark in 6 h); API doc says P(shadow fleet) | **confirmed, resolved in section 3** | `claims-to-verify.md` bottom | Recommendation below. |
| OQ5 | 30 min floor and ~20 km neighbour radius sensible? | **partly** | section 4 | Neighbour check is necessary but not sufficient. 30 min is fine as a live "silent" alert, weak as a scored label. No published Baltic-tuned value exists. |
| OQ8 | 6 h go-dark forecast trainable from a few days of DMA data? | **partly: yes if labels come from our own gap detector on DMA, not from sanctions** | section 3 | Event count is unknown until measured. |
| 3.4 | Finland Coast Guard reports constant GNSS interference and tanker spoofing | **confirmed (search snippets from several outlets, pages not opened)** | [MarineLink](https://www.marinelink.com/news/finland-coast-guard-detects-satnav-518723), [gCaptain](https://gcaptain.com/finland-warns-of-russias-satellite-jamming-and-tanker-spoofing-in-baltic-sea/) | Interference is a Baltic operating condition, so jamming handling is core, not a footnote. |
| spoof thresholds | Plan says "over 40 knots for a tanker" | **unverifiable as published; it is a guess** | section 5 | No published AIS spoofing paper found with a standard knot threshold. Plan already labels these "starting points". |

## 3. The target: which thing do we forecast?

Two candidate targets:

- **A. P(a suspicious gap starts within 6 h).** Label comes from our own detector run on history and on the live log.
- **B. P(vessel is shadow fleet).** Label is "on the OpenSanctions list".

| Criterion | A. Go dark in 6 h | B. Is shadow fleet |
|---|---|---|
| Label availability | Free: any AIS history gives gaps. Needs only the gap rule. | Static list, a few hundred to ~700 vessels globally (EU list > 670 per the plan, unchecked here); how many are in the Baltic on a given day is open question 4. |
| Base rate | Unknown until measured. Guess: low single-digit percent per ship per 6 h after filters. Measure it in hour 1. | Probably a few percent of tankers in the Baltic, but a tiny share of all ships. |
| Does it forecast anything? | Yes, a real future event with a clock. | No. A ship is or is not on the list. It is a classifier, not a forecast. HRT's brief is "predictions and decision making", so this is a poor fit. |
| Visible live to judges | Yes. Show a score, then a ship going dark, then the score being right or wrong. | No outcome to watch. The list is already known, so the demo looks like a lookup. |
| Honest scoring before demo | Yes. Freeze forecasts at an early time, score against logged outcomes at demo time. Needs no human labelling. | Circular. Many ships were sanctioned for the very behaviour we measure (gaps, STS transfers), so the model rediscovers the list. Held-out vessels help but do not remove this. |
| Risk | The label is "what our detector says", so it can learn receiver blind spots, not intent. | Judges ask "so you rebuilt the sanctions list?" |

**Recommendation: A as the single forecast target, with sanctions as a feature and a report stratum, not the label.**

1. Target: `y = 1` if a **qualifying gap** starts within the next 6 h. Qualifying gap = silent for longer than the floor (section 4), neighbours still heard, vessel not in a port polygon or moored/anchored status.
2. Use sanctions match as an input feature and as a reported split: "among sanctioned ships, the model's hit rate vs among others". That gives the shadow-fleet story without making it the label.
3. Keep "P(shadow fleet)" out of the build. If a judge asks, say it is a static label and we chose the question that has a future outcome.
4. Say plainly in the pitch: we forecast **behaviour**, not intent.

Caveat to state openly: because the label is our own detector, add a **cell-level baseline** (historic gap rate in the same grid cell and hour). If the model only ties that baseline, it has learned coverage holes, and we must say so.

## 4. Gap detection

### Is "silent while neighbours within ~20 km are still heard" sound?

**Necessary, not sufficient.** It is the right first filter, and it mirrors the intent of GFW's reception test, but GFW's version is much stricter (reception measured per grid cell over history, plus a pre-gap message count, plus distance from shore). Weaknesses of a pure neighbour test:

| Weakness | Why | Cheap fix (within 17 h) |
|---|---|---|
| Neighbours may be heard by a different receiver | AIS reception is per receiver station; shadowing by islands or terrain can hide one ship while another 15 km away is fine | Require several neighbours (e.g. >= 3), not one, and compare against the recent message rate for that grid cell |
| Class A and Class B differ | Class B has lower power and shorter range | Compare against same-class neighbours, or only count Class A |
| Fade-out looks different from switch-off | Coverage loss tends to show falling message rate and signal gaps before the silence; a switch-off is an abrupt stop mid-stream | Feature: the ship's rate in its last 10 min vs its earlier rate; require a steady rate before the gap (GFW requires >= 14 positions in the 12 h before) |
| Dense-traffic collisions | Crowded cells lose messages | Use a per-cell expected-rate baseline built from our own log |
| Our own stalls | Dropped messages look like gaps | Already in the plan; keep it |
| Receiver outage | Whole cell goes quiet | Already in the plan (many ships silent together = receiver, not intent). Make it a hard rule: if > X% of ships in the cell stop, drop the gap |

The most defensible form is a per-cell **expected-vs-observed** test using the logged stream: "this cell normally gives N messages per 10 min at this hour; it is giving about N now; one ship stopped". This is also a simple chart to show a judge.

### Is the 30-minute floor sensible?

Partly. Reference points:

- Class A reports every 2 to 10 s underway and every 3 min at anchor (the plan cites USCG NAVCEN, not re-checked by me). 30 min is 10 or more expected intervals even at anchor, which is a safe silence test.
- GFW uses **12 h** for "intentional" because shorter gaps are too often coverage or equipment ([pipe-gaps README](https://github.com/GlobalFishingWatch/pipe-gaps), [Welch et al. 2022 summary](https://globalfishingwatch.org/article/hotspots-of-unseen-fishing-vessels-qa/)). Their threshold is a configurable parameter, and their code takes it in hours (`GapDetector(threshold=timedelta(hours=2))` in the example).
- An open-source Baltic tracker ([FormerLab/shadow-fleet-tracker-light](https://github.com/FormerLab/shadow-fleet-tracker-light), MIT) flags "AIS blackouts" at **60 min** and loitering at < 0.5 kn for 20 min within 0.5 km.
- A published deep-learning approach avoids a fixed floor entirely and predicts whether a message should arrive in the next minute ([Bernabe et al., arXiv 2310.15586](https://arxiv.org/abs/2310.15586), Norwegian satellite AIS; no quantitative results in the abstract, code not stated).

**Recommendation: two tiers, and tune the label tier on DMA data.**

| Tier | Rule | Use |
|---|---|---|
| Live "silent" alert | silent > max(10 x the ship's expected interval, 10 min), neighbours heard | Drives the map ghost circle in the demo |
| Scored gap (the forecast label) | silent >= 60 min (also report at 30 min as a sensitivity row), neighbours heard, outside port polygon, last status not moored or at anchor | The thing we forecast and score |

Reason for 60 not 30 on the label: more precise, matches another open-source Baltic tool, and we can still show 30 as a sensitivity check. The cost is fewer events, which hurts evaluation (section 6). Decide after the event count is known: **if 60 min gives fewer than about 40 events in the training data, drop to 30 min** and say so.

### How GFW and others do it (summary)

- **GFW:** gap = time between consecutive positions exceeds a threshold; messages first filtered by a segment-quality flag (`good_seg2`); "intentional disabling" adds the four conditions in claim 1.16. Research code that built the labelled gap dataset and fitted boosted regression trees to drivers of disabling is public ([AIS-disabling-high-seas](https://github.com/GlobalFishingWatch/AIS-disabling-high-seas)). The raw AIS inputs are not public, so that code cannot be run externally.
- **Welch et al. 2022 (Science Advances):** about 55,000 suspected disabling events found for 2017 to 2019 per a search summary of [the paper](https://www.science.org/doi/10.1126/sciadv.abq2109) (full text not fetched; timed out). Treat the number as unverified.
- **Self-supervised transformer** ([arXiv 2310.15586](https://arxiv.org/abs/2310.15586)): predicts "should a message arrive?" and flags disagreement; validated by rediscovering known shutdowns.
- **Fusion papers** ([DarkVesselNet, arXiv 2606.00445](https://arxiv.org/abs/2606.00445)): combine SAR and optical imagery with AIS gap logic. Not usable live; useful for the radar overlay story.

## 5. Spoofing detection

### What published methods use

Honest answer: I did not find a published AIS spoofing method with a standard knot threshold. What the literature does show:

| Source | What it does | Threshold |
|---|---|---|
| Piraeus-style cleaning in [AIS-LLM, arXiv 2508.07668](https://arxiv.org/pdf/2508.07668) | Drops messages above a speed cap as sensor error | 30 kn (per search summary; not opened) |
| Barge tracking study [arXiv 2501.00615](https://arxiv.org/pdf/2501.00615) | Removes speeds as erroneous | 25 kn, plus the value 102.3 which means "speed not available" (per search summary; not opened) |
| [IEOM 2022 outlier paper](https://ieomsociety.org/proceedings/2022istanbul/129.pdf) | Flags jumps by distance between consecutive fixes against a threshold | Not stated in the snippet |
| GNSS receiver patents (USPTO) | Compare a filtered prediction with the received fix | No AIS number |
| [C4ADS "Above Us Only Stars"](https://books.google.com/books/about/Above_Us_Only_Stars.html?id=2SEJxQEACAAJ) (via [Maritime Executive](https://maritime-executive.com/editorials/report-russian-gps-spoofing-threatens-safety-of-navigation)) | Found almost 10,000 spoofing events affecting over 1,300 vessels in Russia, Crimea and Syria; circle patterns were common | No published algorithm found |

So **the thresholds in the plan are our own and must be labelled as such.** Suggested, all guesses to tune on DMA data:

| Signal | Suggested rule | Reasoning |
|---|---|---|
| Impossible jump | implied speed between two fixes > 50 kn for any ship, or > 2 x reported SOG + 10 kn, ignoring pairs less than ~60 s apart and pairs spanning a long gap | The plan's "40 kn for a tanker" is stricter than needed; a laden tanker's service speed is well under 20 kn, so 50 kn is a very safe floor. Short intervals amplify ordinary GNSS noise. |
| Position on land | Point-in-polygon on a coastline file | Cheap and unambiguous. Needs a land polygon (Natural Earth is public domain, not checked here). |
| Circling at anchor | Reported SOG < 1 kn or status "at anchor", but fixes trace a loop: accumulated heading change >= 360 degrees over a short window and net displacement small | Matches the documented Ust-Luga LPG case and the circle spoofing in C4ADS coverage. Thresholds are ours. |
| Jamming vs spoofing | Count affected ships per grid cell and time window. If a large share jump together, label it area jamming. One ship alone is spoofing. | The plan already says this. No published share threshold found; pick a rule such as >= 5 ships and >= 30% of the cell in 10 min, then check it on a real jamming period. |

## 6. Evaluation: is the plan credible, and how to make it strongest

The plan: precision@10 against two baselines, a calibration check, forecasts made early and scored at demo time. **Credible in structure, thin on numbers.** The size problem:

| Hits in top 10 (or top 20) | 95% Wilson interval for true precision |
|---|---|
| 6 of 10 | 31% to 83% |
| 3 of 10 | 11% to 60% |
| 1 of 10 | 2% to 40% |
| 12 of 20 | 39% to 78% |
| 30 of 60 | 38% to 62% |

(My own calculation.) Ten picks alone can only show a big effect. For scale: if the true base rate were 10%, getting 4 or more hits in a random top 10 happens about 1.3% of the time, so a large lift is detectable, a small one is not.

**How many events are needed (rule of thumb, mine):** about 30 to 50 positive events to compare two rankers' precision or average precision with a useful interval; 100 or more for a calibration plot with 5 bins. Below that, show the numbers but call them anecdotal.

### The strongest honest evaluation we can run

1. **Temporal and vessel-grouped backtest on DMA data.** Train on early days, test on the last 1 to 2 days, and keep every vessel's rows on one side. Compute features only from information before the forecast time.
2. **Three baselines, not two:** (a) "ships that went dark before"; (b) "all tankers near Russian ports"; (c) **cell-hour prior** (historic gap rate in the same grid cell and hour). Baseline (c) is the one that exposes a coverage-hole model.
3. **Rank-quality metrics over every snapshot, not just top 10:** average precision, lift at top 10 and top 20, with a **bootstrap that resamples vessels** (not snapshots; snapshots of the same ship are correlated). Report intervals.
4. **Calibration:** reliability table with few bins (3 to 5) and a Brier score against "predict the base rate". If events are few, say the calibration check is indicative only.
5. **Decision curve (HRT-flavoured):** "if we can inspect k ships per 6 h, what share of gaps do we capture?" Plot capture rate vs k against each baseline. This is the cumulative gains view of the watchlist and answers "decision making" directly.
6. **Live pre-registered forecasts:** from the moment ingest runs, write a snapshot of scores every 10 min to an append-only file. Freeze the *model* at a stated time (suggest about 23:00 Sat, once trained), commit the frozen model and the first snapshot to git so the timestamp is checkable, then score at about 11:00 Sunday. That gives roughly 12 h of outcomes: two clean non-overlapping 6 h windows, many overlapping snapshots. Report the pooled result with the vessel bootstrap, and say how few independent windows there are.
7. **Ablation:** drop each feature group (loitering, port proximity, past gaps, sanctions, destination) and show the change in average precision. Already in the plan.
8. **Sanctions stratum:** report hit rate separately for listed ships. Only claim "we flagged ships before they were sanctioned" if open question 3 confirms designation dates; do not claim it otherwise.

State the limits on the results slide: label is our own detector; events are few; no ground truth for intent.

### The decision step

Keep it small and explicit: `inspect_score = P(gap in 6 h) x importance`, where importance is a simple count (sanctions match, tanker, laden draught jump, blank destination). Rank by that, take the top k. This is a real decision rule under a budget and is easy to defend.

## 7. Can it be built in 17 hours? The minimum version that earns both tracks

Yes, with these cuts. Assumes Jake (statistics/ML) owns the detector and evaluation, Hamish (ML) owns features and the model. Hours are from about 16:30 Sat.

| Hours | Work | Done when |
|---|---|---|
| 0 to 3 | Streaming gap detector with neighbour check and per-cell rate; forecast-snapshot logger; **measure event counts** from the first logs | Live "silent" alerts on the map; count of gaps per hour known |
| 3 to 6 | Spoofing: impossible-speed, land point, circle rule; cell-level jamming flag | Documented case replays correctly |
| 4 to 10 | DMA day(s) to Parquet; gap labels; features; logistic regression first, LightGBM only if time; three baselines | Backtest table with intervals |
| 10 to 12 | Freeze model about 23:00; commit; start the pre-registered window | Frozen file in git |
| 12 to 17 | Watchlist ranking, decision curve, ablation, results slide; score live forecasts about 11:00 | Numbers on slides |

**Cut first (in order):** LightGBM (use logistic regression), rendezvous and draught signals as model features, radar overlay as a model input (keep it as a visual), calibration plot (keep the Brier score).

**Minimum that still earns both tracks:**
- G-Research: live silent-ship ghost circles with visible evidence ("N neighbours still heard"), plus one spoofing case.
- HRT: a 6 h gap forecast, three baselines, vessel-bootstrap intervals, the decision curve, and forecasts frozen before the outcome.

## 8. Open-source repos and papers

Stars, licence and push dates from `gh` on 7 Nov 2026. "Reuse" means copying code is legally possible under the licence; the hackathon rule that only code written during the event counts means **copying whole modules weakens the claim, so prefer ideas, and import only libraries.**

| Repo / paper | URL | Stars | Licence | Last push | Reuse? |
|---|---|---|---|---|---|
| GFW pipe-gaps (gap detector, intentional-disabling rules) | https://github.com/GlobalFishingWatch/pipe-gaps | 3 | Apache-2.0 | 2026-11-03 | Ideas and the exact rule table. Code is built on Apache Beam, BigQuery and an internal `gfw-common` package, so it will not drop in. |
| GFW AIS-disabling-high-seas (Welch 2022 code) | https://github.com/GlobalFishingWatch/AIS-disabling-high-seas | 9 | MIT | 2024-01-09 | Ideas: labelled-gap and boosted-tree structure. Cannot run (raw AIS not public). |
| GFW pipe-segment (track de-noising, `good_seg2`) | https://github.com/GlobalFishingWatch/pipe-segment | 1 | Apache-2.0 | 2026-07-24 | Ideas only (Dataflow pipeline). |
| GFW pipe-events | https://github.com/GlobalFishingWatch/pipe-events | 1 | Apache-2.0 | 2026-11-03 | Ideas only. |
| GFW anchorages_pipeline (port and anchorage finding) | https://github.com/GlobalFishingWatch/anchorages_pipeline | 8 | Apache-2.0 | 2026-11-04 | Ideas; useful for a port polygon exclusion. |
| GFW vessel-scoring | https://github.com/GlobalFishingWatch/vessel-scoring | 15 | Apache-2.0 | 2022-02-15 | Ideas only; old. |
| gfwr (R client for GFW APIs) | https://github.com/GlobalFishingWatch/gfwr | 93 | Apache-2.0 | 2026-11-05 | Optional: pulls GFW gap events as external labels. Needs a token (not tested). |
| pyais (AIS decode/encode) | https://github.com/M0r13n/pyais | 263 | MIT | 2026-11-01 | **Import as a library** if any raw NMEA is used (Kystverket). AISStream and Digitraffic are already decoded. |
| MovingPandas (trajectory analysis, stop detection) | https://github.com/movingpandas/movingpandas | 1425 | BSD-3-Clause | 2026-09-30 | **Import as a library** for stop and loiter features, if time. Not needed for the minimum. |
| TrAISformer (AIS trajectory prediction) | https://github.com/CIA-Oceanix/TrAISformer | 211 | CeCILL-C (GitHub shows NOASSERTION; LICENSE file reads "CeCILL-C FREE SOFTWARE LICENSE AGREEMENT") | 2023-09-12 | Ideas only. Weak copyleft, heavy training, wrong target (position forecast, not gap forecast). |
| AISdb (AIS storage and processing) | https://github.com/AISViz/AISdb | 76 | AGPL-3.0 | 2026-11-04 | Ideas only. AGPL would force us to release our whole service if we link or modify it. |
| FormerLab shadow-fleet-tracker-light (Baltic tracker, loiter and 60 min blackouts) | https://github.com/FormerLab/shadow-fleet-tracker-light | 44 | MIT | 2026-04-29 | Ideas and thresholds; the closest comparable project. Check it so we can say how we differ. |
| FogProtocol ais-spoof-detector | https://github.com/FogProtocol/ais-spoof-detector | 4 | MIT | not checked | Ideas only; tiny and unvetted. |
| Efficient-Computing-Lab AIS_Gap_Detection | https://github.com/Efficient-Computing-Lab/AIS_Gap_Detection | 0 | none found | not checked | Do not use (no licence). |
| Bernabe et al., self-supervised AIS shutdown detection | https://arxiv.org/abs/2310.15586 | n/a | n/a | 2023 preprint | Paper only; no code found. |
| Welch et al. 2022, "Hotspots of unseen fishing vessels" | https://www.science.org/doi/10.1126/sciadv.abq2109 | n/a | n/a | 2022 | Cite for the gap-labelling approach. Full text not fetched. |
| DarkVesselNet | https://arxiv.org/abs/2606.00445 | n/a | n/a | 2026 | Cite for SAR plus AIS-gap fusion framing. Abstract-level only. |

## 9. Risks and fixes, ranked

1. **Too few events to score.** Fix: measure the count in hour 1; fall back from 60 to 30 min; report intervals; call small-sample results anecdotal. Do not drop the pre-registered forecast, it is the strongest evidence we can produce.
2. **Model learns coverage holes.** Fix: the cell-hour prior baseline, and include the neighbour test in the label.
3. **Detector disagrees with itself under jamming.** Fix: cell-level jamming flag drops affected ships from the label set and from scoring; report how many were dropped.
4. **Base rate is so low the top 10 are all misses.** Fix: report average precision and capture-rate-at-k; show the lift over the cell prior, not absolute precision.
5. **Label leakage.** Fix: vessel-grouped splits; features use only data before the forecast time.
6. **Judges ask "why not predict shadow fleet?"** Fix: scripted answer in section 3.
7. **Time overrun.** Fix: the cut list in section 7.

## 10. Anything missed

- Competing and comparable open projects: FormerLab's Baltic tracker is the nearest. We differ by adding a forecast, a baseline comparison and a frozen-forecast score.
- GFW publishes gap events through its API (needs a token, not tested). They are mostly far-offshore, 12 h plus, so they will not match Baltic gaps. Use them only for the "radar overlay" story, not as labels.
- The licence question on GFW and OpenSanctions non-commercial data (open question 6) is outside this file.
- Not checked: DMA event counts, AIS report-interval claim (2.1), Welch full text, the C4ADS report itself.
