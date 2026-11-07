# d-value: prior art and the selling point

Compiled Sat 7 Nov 2026 by agent d-value for Aiden's orchestrating agent. Labels: **measured** =
I ran it; **documented** = primary source I read; **vendor claim** = the seller says so;
**unverified** = could not confirm. Scripts in `$WAVE/scripts/d-value/`, downloads in
`$WAVE/data/d-value/`.

## 1. Bottom line

1. **Radar-plus-AIS fusion is already open source five times over, plus the xView3 benchmark, and
   one of those projects is finished and measured.** `esamoun/dark-vessel-detection` (MIT) matched 50 Sentinel-1 passes over the northern
   Kattegat against the Danish AIS archive and published 189 detections, 40 of them undeclared
   (21.2%, interval 13.6–29.4%). `gSulpizio/sat_tracker` already ships the product shape. "We fuse
   radar with AIS" earns nothing in 2026.
2. **The gap is the decision layer.** None of these projects forecasts. All answer "was this ship
   dark at time *t*"; none answers "which ship goes dark in the next 6 hours", and none publishes a
   score fixed before the outcome. That is HRT's brief exactly.
3. **Value is documented and lopsided.** Shadow-fleet sanctions and Baltic cable protection have the
   numbers (1,358 tankers tracked, 1,052 sanctioned; 2.5 mb/d out of Baltic ports) and the data
   (a working free AIS twin plus 55 Sentinel-1 passes per 30 days). Illegal fishing in Asia has the
   biggest headline (FAO: up to US$23bn a year) and no free AIS here. Hormuz has the best story and
   almost no AIS at all.
4. **The honest hard part is published and quantified — a warning and the best available
   credential.** SAR displaces a moving ship along-track by ~117 s × its radial speed: ~600 m at 10
   knots, ~1,200 m at 20 knots beam-on (d-methods' measured arithmetic), against the 200 m tolerance
   the best open project uses. Naive matching manufactures dark ships; correcting for it was worth
   **89 of 149 matches**.
5. **What impresses these two judges is not more sensors.** G-Research asked for a hidden pattern
   made visible and well structured; HRT for decisions from data made fast. The cheap, defensible
   edge is a pre-registered live forecast plus an evidence-first audit trail.

## 2. Findings

### 2.1 Open-source prior art, read in full

GitHub metadata is **measured** via the unauthenticated API on 7 Nov 2026.

| Project | Licence | Stars / last push | What works | Missing for us |
|---|---|---|---|---|
| `esamoun/dark-vessel-detection` | MIT | 1 / 2026-10-25 (v1.0.0) | S1 GRD → CNN detector → pixel→ground → Danish AIS interpolated to image time → 200 m match → map; 65 fixed structures found by recurrence over 47 passes and excluded; published precision/recall and failure log | Batch only, one 17 km box, detector scored on LS-SSDD never on the Kattegat, no forecast, no identity; output is *candidates* |
| `gSulpizio/sat_tracker` | unclassified (NOASSERTION) | 2 / 2026-07-05 | COG windowed reads, xView3 detector (Apache-2.0 weights), length estimate, AIS dead-reckoning, Hungarian matching on a 1 km gate, verified/AIS-only/dark classes, review UI | Three credentials incl. paid Replicate; no measured accuracy published; no forecast |
| `kelu124/OrmuzOsint` | README says MIT, no LICENSE file | 3 / 2026-05-31 | S1 downloader, false-colour renderer, AIS collector, list of 15 AIS sources | A toolkit, not a matcher: no AIS↔radar comparison despite the title |
| `FormerLab/shadow-fleet-tracker-light` | MIT | 44 / 2026-04-29 | Live AISStream over a Baltic box, 1,200+ vessel GUR watchlist, 10 km cable alerts, 20-min loitering, 21-day transshipment flags | AIS only: no radar, no gap detection, no score. The "watchlist on a map" shape is already free |
| `allenai/rslearn_projects` | Apache-2.0 | 25 / 2026-11-07 | S1 detector using the scene **plus a historical scene** (how it separates ships from fixed infrastructure); attribute model (~1M examples) for type/length/heading/speed | ~1.2 GB weights, scene-id route likely needs CDSE; no matching, no forecast |
| xView3 weights | Apache-2.0 | 2021–22 challenge | 991 scenes, 243,018 labelled objects over 43.2M km²; benchmark plus 2nd-place weights | Labels are CFAR + AIS matching + analysts, not truth |

Two numbers behind the field, **documented**: Paolo et al. (*Nature* 625, 2024) put **72–76% of
industrial fishing vessels not publicly tracked** against 21–30% of transport and energy vessels,
with >90% detection only for objects ≥50 m; Kroodsma et al. (*Sci. Rep.* 2022) replaced radius
matching with probability rasters from ~10 billion AIS positions, which none of these projects
implements. Research stacks have moved past detection too (`DarkVesselNet`, arXiv 2606.00445), but
their published evidence is software-grounded, not on-water accuracy. Plenty of stacks, thin on
scores.

### 2.2 Commercial products

| Product | What it does | Access | Evidence |
|---|---|---|---|
| **Windward** | AIS + dark-vessel signals + EO/SAR/RF; Remote Sensing Intelligence launched 18 Nov 2025; monthly shadow-fleet and daily Hormuz dashboards | Paid; dashboards readable free | **vendor claim**: 1,358 tankers tracked Aug 2026, 1,052 (77%) sanctioned, 264 Russia-flag |
| **Skylight (Ai2)** | Detections from S1, S2, Landsat 8/9 with type/length/heading/speed attributes; 18 months of history on a **public map, no account** | Free map; platform free for governments/NGOs | **vendor claim**: ~1.3M detections/month. Their docs: identity is "generally" not obtainable from imagery alone |
| **Kpler / Vortexa** | Cargo-by-cargo flow intelligence; Vortexa advertises "signalled and dark vessels" | Paid | **vendor claim**; their sales are the evidence that dark-transit inference has a paying market |
| **GFW** | Token API with SAR detections, gap/encounter events, published matching code | Free, CC BY-NC 4.0 | **documented** |

### 2.3 Use cases compared

| Use case | Documented value | Data needed | Fit here |
|---|---|---|---|
| Sanctions / shadow fleet (Baltic) | 862 shadow vessels since 2023, 583 (68%) sanctioned somewhere, 314 not EU-sanctioned (KSE Jun 2026); Aug 2026: 3.0 mb/d shadow exports, 2.5 mb/d from Baltic ports | Live AIS + sanctions + gaps | **Strong**: Digitraffic live (947 vessels), DMA history, sanctions CSV, all free |
| Baltic cable protection | Eagle S seized Dec 2024; Fitburg seized 31 Dec 2025, captain convicted Nov 2026; ACLED (May 2026) calls the fleet a hybrid-war platform | AIS + cable geometry + loitering | **Strong story, cheap data**; the MIT tracker already ships 10 km cable alerts |
| Illegal fishing, Asia | FAO: up to US$23bn/yr, ~26 Mt; 72–76% of industrial vessels untracked | Radar plus *some* AIS | **Weak data**: no free AIS here, Skylight free there, 11 passes/30 d at Natuna |
| Hormuz | AIS traffic "near-zero" (JMIC, Mar 2026); Windward: dark activity up ~600% Apr 19–May 3 2026; ~470 vessels jammed near Fujairah in 24 h | Radar counts, almost no AIS | **Story only**: no Middle East data since ~16 Oct (AISStream #322), PortWatch daily — counting, not matching |
| Market signals | Vortexa/Kpler sell this | Transits + prices | **Plausible, unprovable in 24 h**: report the raw relationship only |

### 2.4 The hackathon rules

"Only work built during the hackathon counts. Projects started earlier and adapted are not allowed.
Public open-source code and libraries are allowed if you follow their licences."
(`research/InductionPresentations/SlideSummaryFromTranscription.MD`, lines 40–44, **documented**.)
So MIT/Apache-2.0 code and weights are usable as libraries or reference with attribution; lifting a
pipeline wholesale is the disqualifying move. `sat_tracker`'s licence is unclassified and
`OrmuzOsint`'s MIT claim has no licence file — neither is usable as code without a decision.

### 2.5 Selling points, ranked by evidence

| # | Selling point | Evidence it is real | Depends on |
|---|---|---|---|
| 1 | **A forecast frozen before the outcome, scored live against named baselines** ("which ship goes silent in the next 6 h") with intervals and top-10 capture rate | No open project forecasts; Windward advertises anomaly detection but publishes no score I could find (unverified absence); HRT's brief is this | Steady Baltic feed for hours; a gap base rate above ~1 event/hour in our cells; model frozen ~23:00 |
| 2 | **Evidence-first audit trail**: reason codes, the neighbouring-ship coverage check, and the alternative explanations tested before display | Paid products are black boxes; the judges stressed structure and creativity; the team's ethics rule requires it | Coverage map from our own log |
| 3 | **The Baltic cable/loitering story with documented cases** | All primary, above | Sanctions join + cable geometry; no extra sensing |
| 4 | **A radar-vs-AIS comparison that states its error budget** — ~600 m of shift at 10 knots against a 200 m gate, fixed structures masked, false positives counted | esamoun measured 89/149 matches hinge on the shift; Paolo's ≥50 m floor | t-match's numbers on a DMA day with an S1 pass |
| 5 | **Dark-transit counting where AIS has collapsed** (Hormuz), labelled satellite-only | JMIC "near-zero"; Windward +600%; "electronic fog" reporting | No-account S1 reads; honest framing |
| 6 | **"Patrol tonight" decision for illegal fishing** | FAO US$23bn; 72–76% untracked | In-region AIS or patrol ground truth; absent |
| 7 | **Dark transits as a supply signal** | Sold by Vortexa/Kpler | Weeks of clean dark counts; not one weekend |

The rare combination for a student hackathon is #1 with #2: a timestamped prediction, a public
commitment to being wrong, and a UI that shows why each flag exists. #4 is the credibility
multiplier — it separates a team that read the literature from one that did not.

## 3. Source rows

| Source | Type | Regions covered | Free access route | Account needed? | What one record contains | Update rate | Delay from event to us | Position or resolution accuracy | Identifies the ship? | Licence, commercial limits | Evidence |
|---|---|---|---|---|---|---|---|---|---|---|---|
| esamoun/dark-vessel-detection | OSS pipeline | N. Kattegat, Danish AIS | GitHub | No | lat/lon, matched/dark, position_basis, length | Batch/scene | Hours | 10 m pixels, 200 m gate | No (candidate) | MIT | measured |
| gSulpizio/sat_tracker | OSS app | Any AOI | GitHub | Yes: CDSE S3, aisstream, Replicate | detection, length, verified/AIS-only/dark | Per pass | Hours | ~20 m, 1 km gate | No | unclassified | measured |
| kelu124/OrmuzOsint | OSS toolkit | Hormuz default, any bbox | GitHub | Yes: CDSE + Sentinel Hub | scene, JPG, AIS log line | Per run | Hours | 130 m preview / 10 m SAFE | No | MIT claimed, no file | measured |
| FormerLab/shadow-fleet-tracker-light | OSS AIS app | Baltic | GitHub | Yes: AISStream key | position, watchlist match, cable proximity | ~3 min | Seconds | as received | Yes (watchlist) | MIT | measured |
| allenai/rslearn_projects | OSS models + weights | Global (S1) | GitHub + GCS weights | Scene-id route likely yes (CDSE) | detection + type/length/heading/speed | Batch | Hours | ~20 m | No (type/length) | Apache-2.0 | measured (t-model has weights) |
| Skylight public map | Product, free tier | Global | skylight.global | No | detection, imagery type, attributes | 18-month archive | Days | ~10–20 m | Partial (attributes) | product terms, no bulk export | documented + vendor claim |
| Global Fishing Watch | Product + OSS | Global | globalfishingwatch.org, GitHub | Yes: token (instant) | SAR detections, gap/encounter events | Daily+ | ≥5 days (radar) | — | Partial (MMSI when matched) | CC BY-NC 4.0 | documented |
| Windward | Product | Global | windward.ai dashboards | No to read | aggregates, case studies | Monthly/daily | — | — | Yes in products | Commercial | vendor claim |
| Kpler / Vortexa | Product | Global | marketing pages | Yes (paid) | Cargo/vessel flows incl. dark | Real-time | — | — | Yes | Commercial | vendor claim |

## 4. Consequence for feasibility

**Made possible.** The Baltic works end to end and is the only region where all three legs exist at
once: live free AIS (measured: 947 vessels via Digitraffic), free historical AIS for backtesting
(Danish, 3-day lag), free Sentinel-1 most days over the straits, and a documented, sanctionable
population. A weekend entry can legitimately claim a live behavioural forecast scored on
pre-registered predictions, a handful of radar cross-checks with the error budget stated, and
cable/loitering context from free lists.

**Ruled out, honestly.** "We detect dark ships from space" — Skylight does it free, globally, with no
account. "We identify a ship from radar alone" — Skylight's docs and Paolo's detection floor say no;
identity comes from AIS either side of a gap, or a length/type match. "We do Asia or Hormuz" — without
AIS there is no comparison, only counting, which is already done. "Live radar" — a pass is a snapshot
a few hours old. "We beat Windward" — the honest line is "same category, open, with a measured score".

**Regions.** Baltic: feasible, best story. Danish straits: best radar-AIS test bed. Hormuz:
satellite-only counting with a strong narrative. Natuna/Malacca: value without verifiable data — a
future-extension slide at most.

## 5. Unknowns

- Whether a 24-hour Baltic window holds enough qualifying gaps for a live score to mean anything.
  Settle from t-ais-live's gap rate; if near zero, use a labelled 6-hour outlook on a replayed day.
- Whether the judges reward a published negative result as much as a positive one (probably for
  G-Research, unknown for HRT).
- Whether Skylight's public map is queryable for a place and time without an account (no endpoint
  tested).
- Whether `sat_tracker`'s licence permits reuse, and whether OrmuzOsint's MIT claim is intended.
- Whether sanctions-matched ships appear in the Gulf of Finland feed during the hackathon (t-ais-live).

## 6. Sources

- `github.com/esamoun/dark-vessel-detection` (+ `docs/related-work.md`, `docs/evaluation.md`) — the
  chain, its measured numbers, the field's best short literature review.
- `sat_tracker`, `OrmuzOsint`, `shadow-fleet-tracker-light`, `rslearn_projects` on GitHub (+ their
  `docs/sentinel1_vessels.md` and sentinel1 attribute README); `iuu.xview.us`; DIU xView3 results.
- skylight.global public-map post and support.skylight.global attribute methodology — free map, and
  what imagery can and cannot identify.
- windward.ai shadow-fleet dashboard (Aug 2026), "One Month Into the Ceasefire" (7 May 2026), Remote
  Sensing Intelligence launch (18 Nov 2025).
- KSE Shadow Fleet Tracker (Sep 2026) and remaining-targets paper (Jun 2026). FAO IUU pages (US$23bn,
  26 Mt).
- Reuters 2025-12-31, AP 2026-11-05, ACLED 2026-05-22, Carnegie 2025-06-05, RUSI 2026-01-28;
  kpler.com/product/maritime; vortexa.com; arXiv 2606.00445.
- `research/InductionPresentations/SlideSummaryFromTranscription.MD` — rules and track briefs.
