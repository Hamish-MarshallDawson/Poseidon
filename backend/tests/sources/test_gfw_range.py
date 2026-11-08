"""gfw.fetch_range against recorded responses: the block path gives every day exactly the rows fetch_day gives it.

Fixture: Global Fishing Watch (CC BY-NC 4.0), Gulf of Oman 20-22 Oct 2026, recorded 8 Nov 2026 as three one-day
request sets and one three-day set, trimmed to the same cells, vessels and events in both. No network.
"""
import asyncio
import json
import os
from datetime import date, timedelta
from pathlib import Path

import pytest

from dvm.sources import gfw, jobs, schema
from dvm.sources.common import DAY_MS, REGIONS, day_ms

FX = json.loads((Path(__file__).parent / "fixtures" / "gfw_oman_2026-10-20_3d.json").read_text())
BOX = REGIONS["gulf_of_oman"]
D0, D2 = date(2026, 10, 20), date(2026, 10, 22)
LIVE = day_ms(D2) + 3 * DAY_MS      # fetched soon after: available_ts = our fetch
LATE = day_ms(D2) + 60 * DAY_MS     # backfilled: available_ts estimated per day
DATASET_NAME = {gfw.PRESENCE: "presence", gfw.SAR: "sar"}
EVENT_NAME = {ds: k for k, ds in gfw.EVENT_DATASETS.items()}


class Replay(gfw.Client):
    """Answers each request from the recordings, paging events by gfw.PAGE like GFW does."""

    def __init__(self):
        self.calls = 0
        self.requests = []

    def _post(self, path, params, body):
        self.calls += 1
        if path == "/4wings/report":
            start, end = (date.fromisoformat(x) for x in params["date-range"].split(","))
            name = DATASET_NAME[params["datasets[0]"]]
            if params.get("group-by") == "VESSEL_ID":
                name += "_vessels"
            else:
                name += "_cells"
                f = params.get("filters[0]")
                if f:
                    name += "_matched" if "'true'" in f else "_unmatched"
        else:
            start, end = date.fromisoformat(body["startDate"]), date.fromisoformat(body["endDate"])
            name = "events_" + EVENT_NAME[body["datasets"][0]]
        self.requests.append((name, start, end))
        if end - start == timedelta(1):
            rec = FX["days"][start.isoformat()][name]
        else:
            assert (start, end) == (D0, D2 + timedelta(1)), "only the recorded block can be replayed"
            rec = FX["range"][name]
        if path == "/4wings/report":
            return rec
        off = params["offset"]
        page = rec["entries"][off:off + params["limit"]]
        nxt = off + params["limit"] if off + params["limit"] < len(rec["entries"]) else None
        return {"entries": page, "total": rec["total"], "nextOffset": nxt}


def canon(day_result):
    obs, statics, info = day_result
    return (sorted((o.model_dump() for o in obs), key=lambda o: o["id"]),
            sorted((s.model_dump() for s in statics), key=lambda s: s["mmsi"]), info)


@pytest.fixture(autouse=True)
def small_pages(monkeypatch):
    monkeypatch.setattr(gfw, "PAGE", 3)     # the recorded events then take several pages, as a busy region does
    monkeypatch.setattr(gfw, "PAUSE_S", 0)


@pytest.mark.parametrize("recv", [LIVE, LATE])
def test_range_gives_each_day_exactly_the_day_rows(recv):
    by_day = gfw.fetch_range(Replay(), "gulf_of_oman", BOX, D0, D2, recv)
    assert list(by_day) == [D0, D0 + timedelta(1), D2]
    total = 0
    for d, got in by_day.items():
        want = gfw.fetch_day(Replay(), "gulf_of_oman", BOX, d, recv)
        assert canon(got) == canon(want), d
        total += len(got[0])
    kinds = {o.kind for got in by_day.values() for o in got[0]}
    # the fixture covers every stream that had data, including events that span days
    assert total > 50 and {"ais_presence", "sar_detection", "encounter", "loitering", "port_visit"} <= kinds


def test_range_writes_the_same_rows_as_the_day_path():
    """What the job writes: the upsert keeps one row per id, with the first recv_ts and available_ts. Walking the
    days in order through either path must leave the same table."""
    def table(results):
        rows = {}
        for obs, _, _ in results:
            for o in obs:
                prev = rows.get(o.id)
                rows[o.id] = o.model_dump() | ({"recv_ts": prev["recv_ts"], "available_ts": prev["available_ts"]}
                                               if prev else {})
        return rows
    rng = gfw.fetch_range(Replay(), "gulf_of_oman", BOX, D0, D2, LATE)
    day = [gfw.fetch_day(Replay(), "gulf_of_oman", BOX, d, LATE) for d in rng]
    assert table(rng.values()) == table(day)


def test_range_makes_fewer_calls_and_keeps_raw_once():
    rc, dc = Replay(), Replay()
    raw = {}
    gfw.fetch_range(rc, "gulf_of_oman", BOX, D0, D2, LATE, raw_sink=lambda n, b: raw.setdefault(n, b))
    for d in (D0, D0 + timedelta(1), D2):
        gfw.fetch_day(dc, "gulf_of_oman", BOX, d, LATE)
    assert rc.calls < dc.calls
    # vessel reports stay per day; cells and events are one block request each (events paged)
    assert sorted(n for n, s, e in rc.requests if "vessels" in n and e - s == timedelta(1)) == \
        sorted(["presence_vessels"] * 3 + ["sar_vessels"] * 3)
    assert all(e - s == timedelta(3) for n, s, e in rc.requests if "vessels" not in n)
    assert {"presence_cells", "sar_cells_matched", "2026-10-21_presence_vessels", "events_port_visit_p0",
            "events_port_visit_p2"} <= set(raw)


def test_one_day_range_equals_fetch_day():
    got = gfw.fetch_range(Replay(), "gulf_of_oman", BOX, D0, D0, LATE)
    assert list(got) == [D0]
    assert canon(got[D0]) == canon(gfw.fetch_day(Replay(), "gulf_of_oman", BOX, D0, LATE))


def test_event_days_follow_the_one_day_request():
    e = lambda s, en: {"start": s, "end": en}
    assert gfw.event_days(e("2026-10-19T22:00:00Z", "2026-10-21T00:00:00Z"), D0, D2) == [D0]   # end is exclusive
    assert gfw.event_days(e("2026-10-20T23:00:00Z", "2026-10-21T00:00:01Z"), D0, D2) == [D0, D0 + timedelta(1)]
    assert gfw.event_days(e("2012-01-01T00:00:00Z", "2026-12-01T00:00:00Z"), D0, D2) == [D0, D0 + timedelta(1), D2]
    assert gfw.event_days(e("2026-10-21T00:00:00Z", None), D0, D2) == [D0 + timedelta(1)]      # an instant
    assert gfw.event_days(e("2026-10-21T00:00:00Z", "2026-10-21T00:00:00Z"), D0, D2) == [D0 + timedelta(1)]
    assert gfw.event_days(e("2026-10-25T00:00:00Z", "2026-10-26T00:00:00Z"), D0, D2) == []
    assert gfw.event_days({"end": "2026-10-21T00:00:00Z"}, D0, D2) == []


def test_cell_row_outside_the_block_is_an_error():
    class Bad(Replay):
        def _post(self, path, params, body):
            r = super()._post(path, params, body)
            if path == "/4wings/report" and params.get("group-by") != "VESSEL_ID":
                r = json.loads(json.dumps(r))
                for e in r["entries"]:
                    for rows in e.values():
                        for x in rows or []:
                            x["date"] = "2026-11-30"
            return r
    with pytest.raises(RuntimeError, match="outside"):
        gfw.fetch_range(Bad(), "gulf_of_oman", BOX, D0, D2, LATE)


URL = os.getenv("SOURCES_TEST_DATABASE_URL", "")
needs_db = pytest.mark.skipif(not URL or "tsdb.cloud" in URL or "timescale.com" in URL,
                              reason="set SOURCES_TEST_DATABASE_URL to a local TimescaleDB")


@needs_db
def test_range_and_day_paths_leave_the_same_rows_in_the_database():
    """Write the three days through each path, day by day as the jobs do, and compare the tables."""
    rng = gfw.fetch_range(Replay(), "gulf_of_oman", BOX, D0, D2, LATE)
    day = {d: gfw.fetch_day(Replay(), "gulf_of_oman", BOX, d, LATE) for d in rng}
    ids = sorted({o.id for r in (*rng.values(), *day.values()) for o in r[0]})
    mmsis = sorted({s.mmsi for r in (*rng.values(), *day.values()) for s in r[1]})
    span = (day_ms(D0), day_ms(D2) + DAY_MS)

    async def run():
        pool = await jobs.connect(URL)
        try:
            async with pool.acquire() as con:
                async def clear():
                    await con.execute("DELETE FROM observations WHERE id = ANY($1)", ids)
                    await con.execute("DELETE FROM statics WHERE src = 'gfw' AND mmsi = ANY($1) "
                                      "AND ts >= $2 AND ts < $3", mmsis, *span)

                async def write(results):
                    await clear()
                    for obs, statics, _ in results:
                        async with con.transaction():
                            await schema.write_observations(con, obs)
                            await schema.write_statics(con, statics)
                    o = await con.fetch("SELECT * FROM observations WHERE id = ANY($1) ORDER BY id, time", ids)
                    s = await con.fetch("SELECT * FROM statics WHERE src = 'gfw' AND mmsi = ANY($1) AND ts >= $2 "
                                        "AND ts < $3 ORDER BY mmsi, ts", mmsis, *span)
                    return [dict(r) for r in o], [dict(r) for r in s]

                a = await write(day[d] for d in sorted(day))
                b = await write(rng[d] for d in sorted(rng))
                await clear()
                return a, b
        finally:
            await pool.close()

    (day_obs, day_st), (rng_obs, rng_st) = asyncio.run(run())
    assert len(day_obs) == len(ids) > 50 and day_st
    assert rng_obs == day_obs and rng_st == day_st
