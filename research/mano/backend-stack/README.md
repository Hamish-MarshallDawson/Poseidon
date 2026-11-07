# Provisional backend stack: Dark Vessel Monitor

Written Sat 7 Nov 2026 by Mano's agent. **Research only.** It assumes the team goes ahead with Dark Vessel Monitor, which is not yet agreed. Front end is out of scope. Built on [REPORT.md](../../hamish+aiden/hamish-research/dark-vessel-check/REPORT.md), [04-stack-and-build-plan.md](../../hamish+aiden/hamish-research/dark-vessel-check/04-stack-and-build-plan.md) and [06-unified-data-model.md](../../hamish+aiden/hamish-research/dark-vessel-check/06-unified-data-model.md).

## Feasibility

**Feasible, amber, no red.** The checks put about 16.5 hours between now and the 09:00 Sunday freeze. The data is free and working, and the team has the skills. The real risks are the live feed on the day and honest forecast labels, not the code.

**Unverified:** AISStream from the venue (needs a key), Digitraffic over MQTT (only REST was tested), and the GFW API (needs a token). Tiger Data and Auth0 details below come from general knowledge, not from a check of current docs, pricing or prize rules.

## Stack

| Layer | Choice | Why |
|---|---|---|
| Ingest | Python asyncio and `websockets`; the reader loop only enqueues | AISStream drops messages for slow readers, and drops look like dark ships. |
| Raw log | Gzipped JSONL, one file per hour, kept even with a database | Replay and demo insurance. The database must not be the only copy. |
| API | FastAPI WebSocket at 1 update/s (snapshot, then deltas) | The browser cannot connect to AISStream directly. |
| Live state | In-memory dict of ship state | Detection stays fast and the 1 Hz path never waits on a database. |
| Store | Tiger Data (Postgres with TimescaleDB, plus PostGIS if available) | See below. |
| Detection and model | Plain Python rules, then logistic regression or weighted rules | The report treats LightGBM and Polars as optional. |
| Auth | Auth0 on the review actions only | See below. |
| Schemas | Pydantic, from the unified data model | Already written; field names frozen by 17:30. |

## Tiger Data: fits

Tiger Data is the rebrand of Timescale: Postgres with time-series features.

- **Position reports:** a hypertable keyed on `ts` and `mmsi`, with compression on older chunks.
- **Coverage baseline:** the per-0.1° cell message rate, which separates dark ships from coverage holes, is a continuous aggregate.
- **Neighbour check:** "at least 3 neighbours within 20 km" is a PostGIS radius query.
- **Forecast scoring:** the 10-minute snapshots and the Sunday 11:00 prospective scoring become SQL joins.
- **Replay:** the same table can replay through the same `normalise()` and detectors as live data.

Cautions:

1. **Keep it off the hot path.** Batch inserts from the ingest process instead of writing per message.
2. **Network.** Ingest must stay on a phone hotspot, and the report advises against cloud VMs for AISStream. A hosted database is a separate matter, but writes then cross the hotspot.
3. **Local fallback.** A hosted database must not stop the demo. The JSONL log is the fallback. A local Timescale container is the alternative, but Mano's machine has no Docker, so another teammate would have to host it.
4. **Unchecked:** the free tier, limits and prize rules. Ask the sponsor.

## Auth0: thin fit

The map reads public data, so there is little to protect. The honest use is an analyst sign-in for the watchlist: a reviewer confirms, dismisses or annotates an alert, and their identity is recorded. That supports "ranked for human review, never an accusation".

- Universal Login, JWT validated in FastAPI, a role claim for reviewer versus viewer.
- Keep the map and replay public. Gate only the review actions.
- Add a demo bypass, because a judge's table may have no internet.
- Auth0 proves who approved something. It does not decide what is allowed.

## Cut order

Tiger Data and Auth0 are add-ons. The earlier team convention cut them in the order Tiger Data, then Auth0, then Gemini. Build the core first: live dots, the raw log, replay, the ghost marker, and the ranked watchlist with a one-line reason.

## Open questions

- Has the team agreed to build Dark Vessel Monitor? REPORT.md condition 1 needs everyone's agreement today.
- Who has Docker, if a local Timescale fallback is wanted?
- What do the MLH rules for the Tiger Data and Auth0 prizes require? They are still unread.
