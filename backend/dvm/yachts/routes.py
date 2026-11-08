"""GET /yachts and the background job behind it. Mount with:

    app.include_router(make_router(get_pool, get_live, require_login))

The router brings its own lifespan, so the job starts with the app. It never runs per request or on the tick:
  - OpenSanctions sanctioned vessels: read from Tiger table yacht_sanctions at start, downloaded again when older
    than a day (targets.simple.csv, about 80 MB, streamed to a temp file and dropped; the raw dataset is never kept).
  - IMO -> current MMSI (latest statics row with that IMO) and each ship's last stored fix: every 10 minutes.
A request only adds live status (heard now, or silent since last_seen_ts) from the in-memory map state.
"""
from __future__ import annotations

import asyncio
import io
import logging
import tempfile
import time
from contextlib import asynccontextmanager
from typing import Awaitable, Callable

import httpx
from fastapi import APIRouter, Depends, HTTPException

from dvm.yachts import ref

log = logging.getLogger("dvm.yachts")
OS_INDEX = "https://data.opensanctions.org/datasets/latest/sanctions/index.json"
SANCTIONS_MAX_AGE_MS = 86_400_000
MATCH_EVERY_S = 600
POOL_WAIT_S = 5
LOOKBACK = "30 days"   # statics and positions searched for a match; older ships count as not seen

DDL = """CREATE TABLE IF NOT EXISTS yacht_sanctions (
  imo integer PRIMARY KEY, name text, programs text[] NOT NULL, entity_id text NOT NULL,
  version text NOT NULL, fetched_at bigint NOT NULL)"""
# No imo index on statics: one scan of the IMO column every 10 minutes, bounded to the lookback.
STATICS_SQL = (f"SELECT DISTINCT ON (imo) imo, mmsi, ship_type, length_m, name FROM statics "
               f"WHERE imo = ANY($1::int[]) AND time > now() - interval '{LOOKBACK}' ORDER BY imo, time DESC")
LAST_SEEN_SQL = (f"SELECT m.mmsi, p.ts FROM unnest($1::int[]) AS m(mmsi) CROSS JOIN LATERAL "
                 f"(SELECT ts FROM positions WHERE positions.mmsi = m.mmsi AND time > now() - interval '{LOOKBACK}' "
                 f"ORDER BY time DESC LIMIT 1) p")


def now_ms() -> int:
    return int(time.time() * 1000)


class Yachts:
    def __init__(self, get_pool: Callable[[], object]):
        self.get_pool = get_pool
        self.notable = ref.load_notable()
        self.sanctioned: dict[int, dict] = {}
        self.sanctions_version: str | None = None
        self.sanctions_fetched_at = 0
        self.rows: list[dict] | None = None      # None until the first match has run
        self.last_seen: dict[int, int] = {}
        self.last_error: str | None = None

    def pool(self):
        try:
            return self.get_pool()
        except NameError:   # the app's hub is not built yet
            return None

    async def run(self) -> None:
        while (pool := self.pool()) is None:
            await asyncio.sleep(POOL_WAIT_S)
        async with pool.acquire() as con:
            await con.execute(DDL)
            await self._load(con)
        while True:
            try:
                if now_ms() - self.sanctions_fetched_at > SANCTIONS_MAX_AGE_MS:
                    await self._refresh_sanctions(pool)
                await self._match(pool)
                self.last_error = None
            except asyncio.CancelledError:
                raise
            except Exception as e:   # a failed download or query keeps the last good list; try again next round
                self.last_error = f"{type(e).__name__}: {e}"
                log.warning("yachts refresh failed: %s", self.last_error)
            await asyncio.sleep(MATCH_EVERY_S)

    async def _load(self, con) -> None:
        rows = await con.fetch("SELECT imo, name, programs, entity_id, version, fetched_at FROM yacht_sanctions")
        self.sanctioned = {r["imo"]: {"name": r["name"], "programs": list(r["programs"]), "entity_id": r["entity_id"]}
                           for r in rows}
        if rows:
            self.sanctions_version, self.sanctions_fetched_at = rows[0]["version"], rows[0]["fetched_at"]

    async def _refresh_sanctions(self, pool) -> None:
        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as c:
            index = (await c.get(OS_INDEX)).raise_for_status().json()
            url = next(r["url"] for r in index["resources"] if r["name"] == "targets.simple.csv")
            with tempfile.TemporaryFile("w+b") as f:
                async with c.stream("GET", url, timeout=300) as res:
                    res.raise_for_status()
                    async for chunk in res.aiter_bytes():
                        f.write(chunk)
                f.seek(0)
                found = await asyncio.to_thread(_parse, f)
        version, fetched = index.get("updated_at") or index.get("version") or "unknown", now_ms()
        async with pool.acquire() as con, con.transaction():
            await con.execute("DELETE FROM yacht_sanctions")
            await con.copy_records_to_table("yacht_sanctions", records=[
                (imo, s["name"], s["programs"], s["entity_id"], version, fetched) for imo, s in found.items()])
        self.sanctioned, self.sanctions_version, self.sanctions_fetched_at = found, version, fetched
        log.info("OpenSanctions %s: %d sanctioned vessels with an IMO", version, len(found))

    async def _match(self, pool) -> None:
        imos = ref.candidate_imos(self.notable, self.sanctioned)
        async with pool.acquire() as con:
            statics = {r["imo"]: dict(r) for r in await con.fetch(STATICS_SQL, imos)}
            rows = ref.build_rows(self.notable, self.sanctioned, statics)
            mmsis = [r["mmsi"] for r in rows if r["mmsi"] is not None]
            self.last_seen = {r["mmsi"]: r["ts"] for r in await con.fetch(LAST_SEEN_SQL, mmsis)}
        self.rows = rows


def _parse(f) -> dict[int, dict]:
    return ref.sanctioned_vessels(io.TextIOWrapper(f, encoding="utf-8", newline=""))


def make_router(get_pool: Callable[[], object], get_live: Callable[[], object],
                require_login: Callable[..., Awaitable[None]]) -> APIRouter:
    yachts = Yachts(get_pool)

    @asynccontextmanager
    async def lifespan(_app):
        task = asyncio.create_task(yachts.run())
        yield
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    router = APIRouter(lifespan=lifespan)
    router.yachts = yachts   # for tests and /health-style checks

    @router.get("/yachts", dependencies=[Depends(require_login)])
    async def get_yachts() -> list[dict]:
        """Sanctioned (OpenSanctions, CC BY-NC) and notable (Wikipedia, CC BY-SA) yachts matched to our AIS by IMO.
        Owners are as reported by the source; status is ais, no_ais (silent since last_seen_ts) or not_seen."""
        if yachts.rows is None:
            raise HTTPException(503, "the yacht list is not ready (needs Tiger Data)")
        live = get_live()
        return ref.with_status(yachts.rows, live.pos, live.open_gap, yachts.last_seen)

    return router
