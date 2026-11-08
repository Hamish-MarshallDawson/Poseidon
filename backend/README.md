# Dark Vessel Monitor backend

One Python process that:

- reads live AIS from **AISStream** (`wss://stream.aisstream.io/v0/stream`, permessage-deflate, subscription sent on connect, reconnect with backoff and jitter);
- writes every raw message to an **append-only JSONL log** (`data/raw/aisstream/<UTC hour>.jsonl`, gzipped when the hour rolls over), the replay source;
- normalises messages to `PositionReport` and `VesselStatic` from `06-unified-data-model.md` (field names and units as there; non-vessel MMSIs and lat 91 / lon 181 are dropped);
- stores them in **Tiger Data** (Tiger Cloud, TimescaleDB) hypertables `positions` and `statics`, copied in batches once a second;
- serves the map over **FastAPI**: `GET /health` and a WebSocket at `/ws` that sends `hello`, a `snapshot` of the latest position per vessel, then a `delta` every second (shapes per 06 section 4.3);
- gates `/ws` with **Auth0**: the client's first message must be `{"type": "auth", "token": "<access token>"}`. The token is checked as an RS256 JWT against the tenant's JWKS, with expiry, issuer and audience; anything else is closed with code 1008 before any data is sent.

## Run

Python 3.11 or newer.

One `.env` per machine, at the repo root: `cp .env.example .env` there, then fill in the keys (see the notes in `.env.example`).

```bash
cd backend
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt     # macOS/Linux: .venv/bin/pip
.venv/Scripts/python -m dvm                       # macOS/Linux: .venv/bin/python -m dvm
```

It listens on http://127.0.0.1:8000. Check http://127.0.0.1:8000/health; the log prints the feed rate, ships tracked and rows written every 10 s. Tests: `.venv/Scripts/python -m pytest -q tests` (normaliser, and token validation against a local RSA key).

## Configuration (the repo-root `.env`)

The backend reads the root `.env`. An optional `backend/.env` is loaded first and wins for any variable set in both; real environment variables win over both.

| Variable | Meaning |
|---|---|
| `AISSTREAM_API_KEY` | AISStream key. Without it the server runs but has no live data. |
| `AIS_BBOX` | `[[lon1,lat1],[lon2,lat2]]` (06 order; converted to AISStream's lat, lon). Empty = whole world. Baltic: `[[19,54],[31,61]]`. |
| `TIGER_DATABASE_URL` | Tiger Cloud service URL (`TIMESCALE_SERVICE_URL` from Tiger's credentials file). Empty = JSONL log only. |
| `DATA_DIR` | Raw log directory, default `data`. |
| `HOST`, `PORT` | Default `127.0.0.1`, `8000`. |
| `FRONTEND_ORIGINS` | CORS origins, default `http://localhost:5173`. |
| `AUTH0_DOMAIN`, `AUTH0_AUDIENCE`, `AUTH0_ISSUER` | Auth0 tenant domain, API identifier, issuer (default `https://<domain>/`). With domain and audience set, `/ws` needs a valid token; empty means no login (local dev only, logged as a warning). |
| `GEMINI_API_KEY`, `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID` | AI briefing (`dvm/briefing`): `POST /briefing` `{"mmsis": [...]}` summarises ships in the live picture (404 if one isn't, 503 without the Gemini key); `POST /briefing/speech` `{"text"}` returns MP3 (503 without the ElevenLabs key). Both take the same Bearer token as `/coverage`. Keep the voice ID set: empty is not the default. |
| `DIGITRAFFIC` | Default `1`: also stream Fintraffic's Digitraffic AIS (Finnish waters, MQTT, no key; `dvm/sources/digitraffic.py`). Its raw messages go to `data/raw/digitraffic/`. AISStream and Digitraffic records both pass through one `dvm.merge.FeedMerger` before the map and the store, so a fix both feeds heard is stored once. `/health` shows `digitraffic` and the `merger` counters. `0` turns it off. |
| `PREDICT`, `PREDICT_MODEL_DIR`, `PREDICT_INTERVAL_S`, `PREDICT_SAMPLE` | Route and go-dark predictor with its graders (`dvm/predict`, #121), off unless `PREDICT=1`. Every 5 min it predicts for ships in open gaps and a sample of moving ships, writes `route_predictions` and `scores`, grades due rows into `outcomes`, and serves `GET /predictions?mmsi=` and `GET /model/leaderboard` (same login as `/coverage`). Champions are artifact directories in `PREDICT_MODEL_DIR` (default `backend/data/models`); without one it runs the baselines. See `dvm/predict/README.md`. |
| `MODEL_API_TOKEN` | Optional static Bearer token for `/model/*` (training scripts); otherwise those routes take the normal login. |

## Tiger Data

Tiger Cloud runs TimescaleDB 2.31 on PostgreSQL 18. Everything below is created on start-up by `dvm/store.py` (`SCHEMA`, then `SETUP`, one statement at a time). Running it twice is safe; `tests/test_tiger.py` does that against the live database.

**What we use**

- **Hypertables** `positions` and `statics`, partitioned on `time timestamptz` (= `ts`, as Tiger's docs recommend). `ts` and `recv_ts` stay epoch milliseconds per 06.
- **Continuous aggregate `coverage_1m`**: per 1-minute bucket, 0.1-degree cell and AIS class (`cls`, `A` or `B`), `ships = count(DISTINCT mmsi)` and `msgs = count(*)`. Real-time aggregation is on (`materialized_only = false`), so the latest minute is correct without waiting for a refresh. `count(DISTINCT)` is allowed in a 2.31 continuous aggregate.
- **Refresh policy** on `coverage_1m`: every 1 minute, over the window from 2 hours ago to 1 minute ago.
- **Continuous aggregate `coverage_1h`**: the same counts per hour, for the hour-of-day `expected_vessels` baseline (06 section 2.9). Built on `positions`, not on `coverage_1m`, because distinct ships per hour can't be added up from per-minute distinct counts. Refreshed every 15 minutes; no retention.
- **Detector, forecast and evaluation tables** (06 sections 2.4, 2.7, 2.10), written with `store.append(con, table, rows)`. All three refuse `UPDATE` and `DELETE` with a trigger, so a forecast stays exactly as it was made:
  - `gaps`: one row per gap version, key `(id, version)`; the latest version wins. Indexed on `(mmsi, start_ts)` and `detected_at`.
  - `scores`: a hypertable on `time` (= `made_at`) with 1-hour chunks, unique on `(id, time)`, indexed on `(mmsi, time DESC)` and `(time, p DESC)` for the top-K watchlist.
  - `outcomes`: one row per score, key `score_id`, indexed on `made_at`.
- **`mmsi` is the only vessel ID** (Jake, 7 Nov): no identity table; a ship's name is the latest `statics` row for its MMSI.
- **Columnstore** on both hypertables (15-minute chunks, provisional), with a policy that compresses chunks older than 1 hour.
- **`GET /coverage`** returns `{"cells": [{cell_id, bucket_ts, ships, msgs}]}` for Class A only (what the gap detector uses), for the last `minutes` (default 10, capped at 120), optionally `?bbox=[[lon1,lat1],[lon2,lat2]]`. It takes the same Auth0 access token as `/ws`, as `Authorization: Bearer <token>`, and returns 401 without a valid one. It is open when Auth0 is not configured.

**Why**

- **Coverage baseline for the gap detector.** Per cell, per minute, the message rate says how much the feed should see. A ship that goes quiet where the baseline is high is a dark-ship candidate; a cell where the baseline drops to zero is a coverage hole (06 section 2.9). The aggregate answers that without scanning raw positions.
- **Live map stats** from the same aggregate, cheap enough to poll.
- **Storage**: the columnstore cuts the size of old data (below).

**Query and timing.** The per-cell message count over the same closed window (up to 5 minutes ago, so nothing is still being written). 5,641 cells and 165,635 messages; both queries return identical results. Median of 7 runs from the dev machine to Tiger Cloud, timed in Python with asyncpg:

```sql
-- aggregate: 114 ms median (min 114, max 156)
SELECT lat_bin, lon_bin, sum(msgs) AS msgs FROM coverage_1m
WHERE bucket < date_trunc('minute', now()) - interval '5 min' GROUP BY 1, 2;

-- raw positions: 300 ms median (min 294, max 301)
SELECT floor(lat*10)::int AS lat_bin, floor(lon*10)::int AS lon_bin, count(*) AS msgs FROM positions
WHERE time < date_trunc('minute', now()) - interval '5 min' GROUP BY 1, 2;
```

The gap is modest at this size (about 2.6x) because the raw query is already a sequential scan of 180,000 rows. It grows with the table, while the aggregate reads one row per cell per minute.

**Compression.** `positions` is ordered by `mmsi, time` with no segment-by. We first set `segmentby = mmsi`, as the design suggested. At live density (about 3,000 rows a minute over about 7,000 ships) a 1-hour chunk holds roughly a dozen rows per ship, and that made the compressed chunk bigger than the raw one. Measured on a throwaway copy of 188,239 live rows in two 1-hour chunks, with the same settings:

| Setting | Before | After | Ratio |
|---|---|---|---|
| `segmentby = mmsi`, `orderby = time` | 30.0 MB | 53.9 MB | 0.6x (worse) |
| no segment-by, `orderby = mmsi, time` (used) | 30.2 MB | 7.0 MB | 4.3x |

The policy has not compressed any chunk on the live database yet (see below), so there is no ratio on live data. The probe copy was dropped afterwards. `statics` uses the same settings.

**Chunks: 15 minutes, provisional.** `CHUNK_INTERVAL` in `dvm/store.py` is 15 minutes for now, so the 1-hour compression policy has closed chunks to compress during the hackathon. Jake may change it once the data model settles. Existing chunks can't be resized, so a change moves the tables with `python -m dvm.rechunk`. It copies into new hypertables while ingest runs, then waits for the backend to be stopped with Ctrl+C. It copies the last few minutes, swaps names only if the row counts match, and keeps the old tables as `*_old` until `python -m dvm.rechunk --drop-old`. The restarted backend recreates `coverage_1m`, `coverage_1h` and the columnstore policy. Set `CHUNK_INTERVAL` first, because start-up applies it with `set_chunk_time_interval`.

**Gotchas**

- A continuous aggregate can't be created inside a transaction block, and asyncpg sends a multi-statement string as one. So `SETUP` runs one statement per `execute()`.
- `add_columnstore_policy` is a procedure in 2.31: `CALL`, not `SELECT`.
- The columnstore `ALTER TABLE ... SET` runs only while columnstore is still off (a catalog check in a `DO` block), because changing it once chunks are compressed is refused. To change `segmentby` or `orderby` later, do it by hand.
- Start-up drops a `coverage_1m` without a `cls` column (the first version) and rebuilds it from `positions`, so its history is kept. Each `SETUP` step has a 15-minute timeout for such a rebuild.
- Only the base tables must succeed at start-up. A failing extra (columnstore, policy, aggregate) is logged as a warning and never stops positions being written.

If the database is unreachable, ingest and the map carry on: rows are buffered (capped) and retried, and the JSONL log keeps everything. `/coverage` returns 503 until the connection is up.

## Replay and history (scrub bar)

Per-client replay over `/ws` (06 section 4.3), built from the Tiger `positions` and `statics` hypertables (`dvm/replay.py`). A client in replay gets no live broadcasts; everything it receives is as of the replay clock.

| Client sends | Server answers |
|---|---|
| `{"type":"replay","action":"seek","t":<ms>}` | `status`, then a `snapshot` whose `now_ts` is `t` (clamped to the stored range): the last position of every ship heard in the 30 min before `t`, with its latest known name and type. About 5 s for the whole world (27,000 ships). |
| `{"type":"replay","action":"play"}` | `status` (`paused: false`), then a `delta` every wall-clock second whose `now_ts` moves on by `speed` seconds. It pauses itself at the newest stored time. |
| `{"type":"replay","action":"pause"}` | `status` (`paused: true`); deltas stop. |
| `{"type":"replay","action":"speed","speed":60}` | `status` with the new speed (1 to 600, default 60). |
| `{"type":"replay","action":"live"}` | `status` (`mode: "live"`), then the live `snapshot`; live deltas resume. |

- `status` carries `mode`, `speed`, `paused` (an addition to 06), `now_ts`, `sources` and `replay: {from_ts, to_ts}`.
- Sending play, pause or speed while live first seeks to the newest stored time.
- `detail` during replay answers from the replay state.
- **`GET /history/range`** returns `{"from_ts", "to_ts"}` (epoch ms, null when empty): the first and last stored position. It needs the same Bearer token as `/coverage`.

## Gap detector (`dvm/gaps.py`, #76)

Finds Class A ships that stop reporting, and says whether the silence looks like the ship or like reception (06 sections 2.4, 2.9 and 5). The Hub feeds it every merged position, ticks it every 5 s on the receive clock, puts its gap versions on the map state, sends them to browsers and writes them to the Tiger `gaps` table. First-version rules, settled with Jake on 7 and 8 Nov:

| Rule | Value |
|---|---|
| Ships | Class A only. A ship that has sent any Class A fix counts as Class A; Class B ships stay on the map with no gaps. |
| Moving only | No gap if the last fix was at anchor or moored (nav status 1 or 5), slower than 1 kn, had no speed, or the ship's real displacement over its last 5 to 60 min works out under 1 kn (in port the reported speed jitters above 1 kn while the ship stays put). In the 7 Nov log stopped ships were about 95% of all silences, mostly in port, where AISStream drops their slow reports. |
| Opens | Silent for `max(1800 s, 20 x report_interval_s)`. `report_interval_s` is an exponentially weighted mean (alpha 0.2) of the time between fixes while moving, so the 30-minute floor decides for almost every ship. |
| `own_stall` | Our own outages explain the silence: what is left of it outside them is shorter than the ship's limit. Outages are 7 Nov 19:39:44-19:50:08 and 21:57:13-23:36 UTC (`gaps.KNOWN_STALLS`) and any backend restart (the last stored fix to start-up). A 10 s deploy restart doesn't explain a 2 h silence, so that gap is judged on the rules below; an open `own_stall` gap is re-judged once its silence outgrows the outage. |
| `unknown` | No other Class A ship was heard within 20 km in the 30 min before the silence (open sea). |
| `coverage_gap` | Fewer than 3 other Class A ships heard within 20 km in the last 10 min, or at least half of the ships that were near it before have gone silent too: a receiver hole, not the ship. |
| `deliberate_candidate` | Otherwise: the area still hears ships and this one went quiet. It is a candidate, not proof; a master may switch off lawfully for safety. |

- **Versions.** The id is `gap-{mmsi}-{start_ts}`. A new version is written when the gap opens, when its flag changes (re-checked every 60 s while open) and when it closes on the next fix. The flag at the close is the last one seen while open, because after an outage the neighbours come back at the same moment as the ship. Rows are append-only; a version written again after a restart is skipped (`ON CONFLICT (id, version) DO NOTHING`).
- **The 06 "cell not dead" test** is done by following the ship's earlier neighbours rather than its 0.1 degree cell. A convoy that sails out of a cell keeps being heard elsewhere, so the cell doesn't look dead when it isn't. It also catches most ships just inside a receiver hole, the case Mano's stress suite marks as a known limit.
- **On the map.** A ship with an open gap stays at its last fix with `open_gap_id` for up to 24 h, instead of dropping off after 30 min. Its `status` is `gap_open` only when the gap is `deliberate_candidate`; for `own_stall`, `coverage_gap` and `unknown` it is `silent`, so only likely dark ships are drawn as dark. `snapshot.gaps` has the open gaps and those closed in the last hour, `delta.gaps` has every new version, and `detail.gaps` has the ship's last 5. The frontend draws the "could be anywhere in here" circle from `last_sog_kn` and `start_ts`.
- **Warm start.** On start-up the backend reads Tiger on its own read-only connection: every Class A fix of the last 2 h (rhythms and neighbours), each Class A ship's last fix of the last 6 h (ships already silent), their latest names, and the gaps still open. Open gaps carry on with their versions, ships already silent get their gap, and the restart itself counts as `own_stall`. The detector's clock waits until this is done. About 2 s for 300,000 fixes and 22,500 ships on a local copy. A gap whose ship was last heard more than 2 h before start-up has no neighbour baseline, so it is `unknown` unless it overlaps an outage.
- **`/health`** has a `gaps` block: `opened`, `closed`, `versions`, `open`, `not_moving` (silences skipped because the ship wasn't moving), `warm` (`pending`, `ready`, `failed: ...` or `off`) and `written`.

**Measured on the recorded 7 Nov log** (16:51-21:57, 1.65 million messages, 24,615 Class A ships, replayed offline): 2,326 gaps, of which 654 `deliberate_candidate`, 1,097 `coverage_gap`, 495 `unknown` and 80 `own_stall`. Closed deliberate gaps lasted a median of 69 min (90% under 178). The detector took 56 s of CPU for the 5 hours. On the live server the first warm start opened about 2,160 gaps, using 421 MB for the whole backend.

**Tests.** `tests/test_gaps.py` (rules, map state, table rows) runs with plain `pytest`. Mano's stress suite runs it too: `.venv/bin/python -m pytest tests/stress --stress --detector dvm`.

## Measured

World-wide, 7 Nov 2026 around 16:55 UTC: about 90 messages a second, 7,300 ships after 3 minutes, queue depth 0, nothing dropped. One process keeps up easily, so the default box is the whole world.

## AISStream rate rule (hard rule)

AISStream bans clients for what they send: connections, reconnects and subscription updates. All the limits live in **`dvm/limits.py`**, as constants with a source on each, and the code enforces them. A breach is refused and logged as `AISSTREAM RATE RULE BREACH REFUSED`, and ingest stops instead of retrying.

- **Connections:** at most 1 per process, and 1 process per machine (a localhost port lock). AISStream's cap is 3 per account and 3 per IP. Run only one backend per API key.
- **Reconnects:** backoff from 5 s doubling to 30 min with jitter, and at most 12 connects in any hour. After HTTP 429, 401 or 403, an error message from the server, or a policy close, there is no connection for 1 hour. Ban reports in https://github.com/aisstream/issues (#256, #287, #302) came from reconnect loops capped at 2 to 5 minutes.
- **Restarts:** the backoff, the hourly count and any penalty are saved in `data/aisstream_limits.json`, so a restart doesn't reset them. Delete the file only after checking the account.
- **Subscription updates:** at most 1 per 2 s per connection (theirs is 1 per second), sent within 3 s of connecting.
- **Compression:** permessage-deflate always. The log warns if `SubscriptionConfirmation` says it is off.
- **Slow reader:** the reader never waits, it only enqueues. If the queue is full, messages are dropped and counted locally instead of slowing the socket.
- **Shutdown:** stop the backend with Ctrl+C so the WebSocket closes cleanly. A forced kill can leave a "ghost" connection that holds AISStream's quota (#292).

`GET /health` shows `aisstream.limits`: open connections, connects in the last hour, seconds until the next connect is allowed, and any penalty. Tests: `tests/test_limits.py`.

## References

- **AISStream: https://aisstream.io/documentation#reference** is the canonical reference for message types, fields, the subscription and limits. Read it before touching `dvm/ingest.py` or `dvm/normalise.py`, and point any sub-agent at it.
  - Checked against the code on 7 Nov 2026: the subscription fields and lat, lon box order, the five subscribed type names, the field names of all five models, binary frames of UTF-8 JSON, the 3-second subscription rule, 3 connections, and reading continuously.
  - Live payloads differ from the docs example. MetaData has `MMSI`, `MMSI_String`, `ShipName`, lower-case `latitude`/`longitude`, and `time_utc`. `time_utc` was on all of 122,000 live messages, has 4 to 9 fraction digits, and lags our clock by about 1 s. `MaximumStaticDraught` is metres (median 3.5, max 25.5).
  - The feed counts as `up` only after `SubscriptionConfirmation`. If `CompressionEnabled` is false, the log warns, because uncompressed connections are bandwidth-limited and drop messages.
- Data model: `research/hamish+aiden/hamish-research/dark-vessel-check/06-unified-data-model.md`.
- Tiger Data hypertables: https://www.tigerdata.com/docs/use-timescale/latest/hypertables/create
- Auth0 API access tokens: https://auth0.com/docs/secure/tokens/access-tokens/validate-access-tokens

## Not done yet

- The token is checked once at connect, not again when it expires. `/health` stays public; there are no other HTTP routes yet.
- `subscribe` on `/ws` is ignored; trails, spoofs and the watchlist are sent empty (gaps are live, see Gap detector).
- Replay from the JSONL log, Digitraffic backup feed, MID-to-flag lookup (`flag` is null).
