# Dark Vessel Monitor backend

One Python process that:

- reads live AIS from **AISStream** (`wss://stream.aisstream.io/v0/stream`, permessage-deflate, subscription sent on connect, reconnect with backoff and jitter);
- writes every raw message to an **append-only JSONL log** (`data/raw/aisstream/<UTC hour>.jsonl`, gzipped when the hour rolls over), the replay source;
- normalises messages to `PositionReport` and `VesselStatic` from `06-unified-data-model.md` (field names and units as there; non-vessel MMSIs and lat 91 / lon 181 are dropped);
- stores them in **Tiger Data** (Tiger Cloud, TimescaleDB) hypertables `positions` and `statics`, copied in batches once a second;
- serves the map over **FastAPI**: `GET /health` and a WebSocket at `/ws` that sends `hello`, a `snapshot` of the latest position per vessel, then a `delta` every second (shapes per 06 section 4.3).

## Run

Python 3.11 or newer.

```bash
cd backend
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt     # macOS/Linux: .venv/bin/pip
cp .env.example .env                              # then fill in the keys
.venv/Scripts/python -m dvm                       # macOS/Linux: .venv/bin/python -m dvm
```

It listens on http://127.0.0.1:8000. Check http://127.0.0.1:8000/health; the log prints the feed rate, ships tracked and rows written every 10 s. Tests: `.venv/Scripts/python -m pytest -q tests`.

## Configuration (`backend/.env`)

| Variable | Meaning |
|---|---|
| `AISSTREAM_API_KEY` | AISStream key. Without it the server runs but has no live data. |
| `AIS_BBOX` | `[[lon1,lat1],[lon2,lat2]]` (06 order; converted to AISStream's lat, lon). Empty = whole world. Baltic: `[[19,54],[31,61]]`. |
| `TIGER_DATABASE_URL` | Tiger Cloud service URL (`TIMESCALE_SERVICE_URL` from Tiger's credentials file). Empty = JSONL log only. |
| `DATA_DIR` | Raw log directory, default `data`. |
| `HOST`, `PORT` | Default `127.0.0.1`, `8000`. |
| `FRONTEND_ORIGINS` | CORS origins, default `http://localhost:5173`. |
| `AUTH0_DOMAIN`, `AUTH0_AUDIENCE` | Milestone 2, not used yet. |

## Tiger Data

Tables are created on start-up (`dvm/store.py`). Each has a `time timestamptz` partition column equal to `ts`, as Tiger's docs recommend, while `ts` and `recv_ts` stay epoch milliseconds per 06. Example:

```sql
SELECT time_bucket('1 minute', time) AS minute, count(*) AS positions, count(DISTINCT mmsi) AS ships
FROM positions WHERE time > now() - interval '1 hour' GROUP BY minute ORDER BY minute;
```

If the database is unreachable, ingest and the map carry on: rows are buffered (capped) and retried, and the JSONL log keeps everything.

## Measured

World-wide, 7 Nov 2026 around 16:55 UTC: about 90 messages a second, 7,300 ships after 3 minutes, queue depth 0, nothing dropped. One process keeps up easily, so the default box is the whole world.

## Not done yet

- Auth0 access-token validation on `/ws` and the API (milestone 2; planned with `auth0-api-python`).
- Client messages on `/ws` (`subscribe`, `replay`, `detail`) are ignored; trails, gaps, spoofs and the watchlist are sent empty.
- Replay from the JSONL log, Digitraffic backup feed, MID-to-flag lookup (`flag` is null).
