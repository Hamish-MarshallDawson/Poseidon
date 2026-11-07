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

## Tiger Data

Tiger Cloud runs TimescaleDB 2.31 on PostgreSQL 18. Everything below is created on start-up by `dvm/store.py` (`SCHEMA`, then `SETUP`, one statement at a time). Running it twice is safe; `tests/test_tiger.py` does that against the live database.

**What we use**

- **Hypertables** `positions` and `statics`, partitioned on `time timestamptz` (= `ts`, as Tiger's docs recommend). `ts` and `recv_ts` stay epoch milliseconds per 06.
- **Continuous aggregate `coverage_1m`**: per 1-minute bucket and 0.1-degree cell, `ships = count(DISTINCT mmsi)` and `msgs = count(*)`. Real-time aggregation is on (`materialized_only = false`), so the latest minute is correct without waiting for a refresh. `count(DISTINCT)` is allowed in a 2.31 continuous aggregate.
- **Refresh policy** on `coverage_1m`: every 1 minute, over the window from 2 hours ago to 1 minute ago.
- **Columnstore** on both hypertables (15-minute chunks, provisional), with a policy that compresses chunks older than 1 hour.
- **`GET /coverage`** returns `{"cells": [{cell_id, bucket_ts, ships, msgs}]}` for the last `minutes` (default 10, capped at 120), optionally `?bbox=[[lon1,lat1],[lon2,lat2]]`. It takes the same Auth0 access token as `/ws`, as `Authorization: Bearer <token>`, and returns 401 without a valid one. It is open when Auth0 is not configured.

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

**Chunks: 15 minutes, provisional.** `CHUNK_INTERVAL` in `dvm/store.py` is 15 minutes for now, so the 1-hour compression policy has closed chunks to compress during the hackathon. Jake may change it once the data model settles. Existing chunks can't be resized, so a change moves the tables with `python -m dvm.rechunk`. It copies into new hypertables while ingest runs, then waits for the backend to be stopped with Ctrl+C. It copies the last few minutes, swaps names only if the row counts match, and keeps the old tables as `*_old` until `python -m dvm.rechunk --drop-old`. The restarted backend recreates `coverage_1m` and the columnstore policy. Set `CHUNK_INTERVAL` first, because start-up applies it with `set_chunk_time_interval`.

**Gotchas**

- A continuous aggregate can't be created inside a transaction block, and asyncpg sends a multi-statement string as one. So `SETUP` runs one statement per `execute()`.
- `add_columnstore_policy` is a procedure in 2.31: `CALL`, not `SELECT`.
- The columnstore `ALTER TABLE ... SET` runs only while columnstore is still off (a catalog check in a `DO` block), because changing it once chunks are compressed is refused. To change `segmentby` or `orderby` later, do it by hand.
- Only the base tables must succeed at start-up. A failing extra (columnstore, policy, aggregate) is logged as a warning and never stops positions being written.

If the database is unreachable, ingest and the map carry on: rows are buffered (capped) and retried, and the JSONL log keeps everything. `/coverage` returns 503 until the connection is up.

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
- Client messages on `/ws` (`subscribe`, `replay`, `detail`) are ignored; trails, gaps, spoofs and the watchlist are sent empty.
- Replay from the JSONL log, Digitraffic backup feed, MID-to-flag lookup (`flag` is null).
