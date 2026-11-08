# pr-models: route prediction model options

Tags: **[M]** measured by me, **[D]** documented (link), **[E]** estimated.

## Recommendation

Build in this order, all inside the 09:00 UTC freeze:
1. **Baseline** (last course and speed, dead reckoning on the sphere). 1 hour. It is the skill reference for everything else.
2. **LightGBM residual corrector per horizon** (1, 3, 6, 24 h) predicting east/north offset from the baseline, with quantile heads or conformal radius for uncertainty. About 4 to 6 hours to a first graded version. This is the right "first real model": it trains in minutes on CPU, and it retrains from scratch in seconds as graded cases arrive, so the loop can be shown improving.
3. **Analogue / lane-graph model** as a stretch option, only if step 2 is done before the freeze.
4. **Sequence model (GRU, then TrAISformer-style)**: do not promise it before the freeze. Offer it as the "challenger" the loop can promote later.

Do not plan on a pretrained vessel model. I found no published weights; TrAISformer has open code (PyTorch, minGPT-based, trained on Danish Maritime Authority data) but the search showed no released checkpoint [D: https://arxiv.org/abs/2109.03958, https://github.com/hyzcn/TrAISformer]. Its paper reports mean error under about 10 nautical miles out to roughly 10 h, in Danish waters only [D, same link].

## What we have to train and run on

- GPU: RTX 3080, 12 GB (0.5 GB in use), 16 threads, 31 GB RAM [M: nvidia-smi, nproc, free]. Plenty for GBM and small GRUs. Inference on Vultr is 2 vCPU / 4 GB shared [brief], so LightGBM (millisecond predict) or a small ONNX/CPU GRU only.
- Our own AIS in Tiger: first position 7 Nov 16:51 UTC, latest 8 Nov 04:11 UTC (about 11.3 h) [M]. In the last hour: AISStream class A 170,720 rows / 20,548 ships, class B 40,601 / 10,154, Digitraffic class A 117,309 / 628 ships [M]. 18,345 class A ships have 30+ positions [M]. So we have many ships but only half a day of each: enough for 1 to 6 h horizons, thin for 24 h and useless for lane learning on its own.
- Tiger `gaps`: 10,626 rows; 959 closed (with last and next position, so gap-end grading is possible), 9,667 still open with no next position; all `derived`, none from GFW (issue #112). Closed gaps: median 2.3 h, max 9 h [M]. Tiny for training, fine as a first grading set.
- Longer history therefore must come from the Danish archive (see `pr-data`). Without it, any learned model is trained on 11 hours of data.

## Options compared

| | A. Baseline (dead reckoning / great-circle) | B. GBM residual corrector | C. Historical analogues / lane graph | D. Sequence model (GRU/LSTM/Transformer) |
|---|---|---|---|---|
| Predicts | Point at horizon h from last COG/SOG; variants: damped speed, constant turn rate, great-circle for long hops | Offset from A at each horizon, from features | Point or path from nearest past tracks, or by walking a graph of lane cells | Next positions autoregressively, or the whole path; TrAISformer classifies lat/lon/SOG/COG bins |
| Data needed, have it? | Only the last fix. **Yes** | Training windows of (history, truth at h). Own AIS: yes for ≤6 h, thin for 24 h. Danish archive: not ingested yet | Lots of history over the same waters. Danish archive only; own 11 h is not enough | Hundreds of thousands of windows. Needs the archive |
| Effort to first version | 1 h | 4 to 6 h [E] | 6 to 10 h [E] (cell grid, transition counts, lookup) | GRU 6 to 8 h [E]; TrAISformer port 10+ h and data prep [E] |
| Expected quality | Good below 1 h; drifts fast through turns, and straits and port approaches are where it fails | Typically a sizeable cut over A at 1 to 6 h because it learns turn tendencies, speed changes, nav status, lane position [E, consistent with literature; not measured here] | Best where traffic is channelised (Danish straits, TSS lanes); weak in open water or for unseen routes [E] | Best published accuracy in Danish waters (≈10 nmi at ~10 h) [D]; needs more data and tuning than we have time for [E] |
| Uncertainty | Growing circle: radius = k·h·speed error, fit empirically from residuals | LightGBM quantile objective (e.g. 50/80/95%) or split-conformal radius per horizon; cheap and calibratable | Spread of the K neighbours' endpoints gives a real distribution (multi-modal at forks) | Sample N paths (TrAISformer samples from its bin distribution) or predict a Gaussian/mixture; heavier |
| Compute | None | CPU, seconds to minutes; inference trivial on Vultr | Pure lookup, memory-bound; precomputed grid is small | GPU training minutes to hours; inference needs a small model on 2 vCPU |
| Improves with graded data | n/a (parameters only: tune damping) | Retrain from scratch each cycle in seconds; or warm-start with `init_model` and extra trees | Just add tracks to the index; no training | Warm start / fine-tune on new cases with a low LR; risk of forgetting, so keep a replay set; retrain from scratch overnight |
| Main risks | Low skill ceiling | Leakage if windows cross the time split; distribution shift as only 11 h of our data exist | Sparse coverage; most dead zones are exactly where history is thinnest | Overfits small data; can't be tuned and validated in the time available |

## Features (for B, reusable by D)

Last fix: lat, lon, SOG, COG, heading, nav status, ship class A/B, time since last fix. Derived from the last 30 min to 6 h: mean and variance of SOG, COG change (turn rate), acceleration, distance travelled, straightness. Static: ship type, length (from `statics`), draught if present. Context: distance to coast and to nearest port, depth if available, grid-cell traffic density, hour of day. Target: east and north metres from the baseline point, per horizon. Train and evaluate in a local metric projection to avoid longitude distortion; the baseline should use geodesic (e.g. pyproj) steps.

## Uncertainty and grading

For every model the stored prediction should be point plus radius (or sample set). Measure: median and 90th percentile position error per horizon, final displacement error, average displacement error, empirical coverage of the stated 80/95% radius, and **skill = 1 − error_model / error_baseline**, which is the headline metric. Conformal calibration on a held-out time slice is the simplest route to honest radii for B.

## What to build first (concrete)

1. Window builder from `positions`: for each ship and each t on a 10-min grid, features from history before t, truth = position nearest t+h within ±5 min, drop if absent. One time split (train earlier, test later, a gap between them equal to the longest horizon).
2. Baseline plus its residual stats; report error per horizon on the test slice.
3. LightGBM per horizon, quantile or conformal radius, compare to baseline in one table.
4. Write `model_version`, horizon, point, radius to the predictions ledger. Demo shows predicted cone then actual reappearance.
5. Archive training (when `pr-data` confirms access) is a drop-in: more rows, same code.

## Honest limits

- With 11 h of our own data, "improvement" on 24 h horizons is not measurable; show 1 to 6 h live and 24 h only on archive backtest.
- Dead-zone cases are selected (ship went silent), so train and test on gap-conditioned windows too, not just random windows; otherwise skill looks better than it is.
- Gap-end grading scores only the endpoint, not the path.

## Open questions for Aiden

1. Is ship-level path (cone) enough for the demo, or must the endpoint after a real gap be the headline? That decides whether gap-conditioned training is mandatory.
2. May we spend hours ingesting the Danish archive before building B, or train B on 11 h of our own data first and swap later? I recommend the second: it gets a working loop sooner.
3. Is one GRU challenger worth the 6 to 8 hours, versus polishing the loop around GBM?
