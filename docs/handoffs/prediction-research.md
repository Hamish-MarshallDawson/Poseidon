# Brief: prediction research wave (issue #113)

Four Sonnet agents, read-only on the repo. Each writes one report to
`/home/aiden/Projects/Personal/dvm-be/prediction-research/<name>.md` (create the folder if needed) and nothing else:
no repo edits, no commits, no board posts, no database writes. `be-integrate` reviews the reports and brings
proposals to Aiden, who decides.

Read first: `docs/prediction-loop/PLAN.md` (the concept and what the data can and can't do),
`research/hamish+aiden/aiden-research/data-sources-wave/SYNTHESIS.md`, and `research/NextSteps/flag-and-prediction-next-steps.md`.
Tiger is readable for real numbers: load `TIGER_DATABASE_URL` from the repo `.env` with python-dotenv and open
read-only sessions (`server_settings={"default_transaction_read_only": "on"}`); never print the URL. Keep queries
light (the live backend writes to it). Web search and short HTTP checks are fine; keep downloads small (headers,
listings, one small sample at most).

**Constraints every proposal must respect:** feature freeze 09:00 UTC (about 5 hours away); training on this desktop
(check `nvidia-smi` for the GPU) or the laptop; inference on the Vultr server (2 vCPU, 4 GB, shared with the live
backend); our own AIS only since 16:51 UTC on 7 Nov; delayed truth from GFW (3 to 4 days) and possibly the Danish AIS
archive (about 3 days). Every claim with a number says where it came from: measured (by you), documented (with a
link), or estimated.

**Report shape** (at most about 1,200 words): recommendation first; 2 to 4 options compared in a table (what it
predicts, data needed and whether we have it, effort to a working first version in hours, expected quality and how
we'd measure it, risks); what to build first; open questions for Aiden.

## `pr-models`: route prediction model options
What can predict a ship's position or path through a dead zone from its AIS history? Compare at least:
continuing at the last course and speed, and great-circle variants (the baseline); gradient-boosted corrections on top
of the baseline per horizon; historical-analogue methods (nearest similar past tracks, shipping-lane graphs or route
networks built from historical AIS); sequence models (GRU, LSTM, Transformer) and any open pretrained vessel-trajectory
models. Include uncertainty (how each gives a radius or distribution), input features, compute on our hardware, and
how each improves as graded data accumulates (retrain from scratch, warm start, fine-tune).

## `pr-data`: training and grading data
Confirm with real checks what historical data we can get for free in time: the Danish Maritime Authority AIS archive
(current URL, access, file size per day, delay, schema, licence; the research wave used it, see
`research/.../scripts/t-ais-history/`), NOAA MarineCadastre (US), Norway's Kystverket, Digitraffic history, and any
other free historical AIS; GFW gap events (worldwide counts per day; fields; see issue #112, another agent is fixing
ingestion); GFW port visits; Sentinel-1 and GFW radar as checkpoints. Measure what's in Tiger now (row counts, spans
per source and region). Recommend the training set and the grading sources for the first model, with sizes and load
times.

## `pr-loop`: evaluation and the autonomous training loop
Design the continuous loop: prediction ledger and grading (fast from our own AIS reappearance, delayed from archive
and GFW), metrics (position error by horizon, final and average displacement error, calibration of uncertainty, skill
over the baseline), time-based splits and k-fold variants that avoid leakage (the `as_of` and `available_ts` columns),
a fixed held-out set, champion and challenger promotion, scheduling on our hardware, an experiment log and model
registry. Then Gemini in the loop: what it reads, the allowed settings it may propose (JSON schema), guardrails so it
can't cause false "improvement", and prior art (LLM-driven experiment search). Include how to show the loop live in the
demo within 5 hours, including a time-machine backtest for the 3 to 4 day delay.

## `pr-targets`: other prediction targets worth showing
Beyond route through dead zones: go-dark risk in the next N hours (labels from our gap detector and GFW gap events;
note Jake's planned `score.py` overlaps), next port or destination, ETA, rendezvous or ship-to-ship transfer risk,
identity change (same IMO, new MMSI), reappearance location. For each: labels and data we have, how the delayed data
grades it, effort, and demo value. Recommend which one or two to pair with route prediction.
