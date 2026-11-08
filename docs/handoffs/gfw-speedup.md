# Brief: GFW backfill speed-up (issue #111)

Read `docs/handoffs/COMMON.md` first. Two agents share this issue, on separate branches and separate files.

## Why
The GFW backfill on the Vultr server does one region and one UTC day per window. Per region-day it makes 9 or more
calls in series (`fetch_day` in `backend/dvm/sources/gfw.py`: presence cells, presence vessels, radar cells matched and
unmatched, radar vessels, then 4 event datasets with paging), each after a 0.3 s pause, and `backfill_back` in
`backend/dvm/sources/jobs.py` does the regions and days in series. Measured in Tiger at 02:48 UTC: about 10 to 30 s
per region-day in the Gulf of Oman, Hormuz and the Gulf of Finland, about 110 s in the Danish straits, so about 2.5 to
3 min per day of history. History reached late August 2026. We need much more history for training before 09:00.

The ledger (`source_windows`, one row per src, stream, region and day) and stable observation ids already make
fetches resumable and idempotent: keep both.

## Agent `gfw-month`, branch `111-gfw-month` (part of #111)
Files: `backend/dvm/sources/gfw.py`, its tests, and the GFW part of `backend/dvm/sources/README.md`.

1. **Measure** (short script, no database writes): time each call of `fetch_day` for one day in the Danish straits and
   one in the Gulf of Oman. Then make each report and event call for a 30-day range and check:
   - the 4Wings report with `temporal-resolution=DAILY` over a multi-day `date-range` returns per-day entries, and
     the rows for a sample day equal those from the single-day call;
   - events over a range page correctly and every event lands in the right day;
   - response size and time (the client timeout is 170 s), and whether 7, 14 or 30 days is the best block.
2. **Build** `fetch_range(client, region, bbox, start_day, end_day, recv_ts, raw_sink=None)` returning, per day, the
   same `(observations, statics, info)` that `fetch_day` returns, with identical ids and fields. Keep `fetch_day`
   working. Add a tested equality check: for the same days, the range path writes exactly the rows the day path
   writes (recorded responses in tests; one live comparison in your run).
3. Report the measured speed-up per region-day for each block size, and the recommended block size.

## Agent `gfw-parallel`, branch `111-gfw-parallel` (part of #111)
Files: `backend/dvm/sources/jobs.py`, `backend/dvm/sources/__main__.py`, their tests, and the jobs part of
`backend/dvm/sources/README.md`. Not `gfw.py` (that's `gfw-month`'s).

1. **Measure** safe concurrency: run 1, 2, 4, then at most 8 GFW report calls at once (short bursts, a few seconds
   apart), and record latency, errors and any 429. Remember the Vultr backfill uses the same token. Recommend a
   worker count with margin.
2. **Build:**
   - regions of a day fetched concurrently (bounded by a semaphore), each region still one transaction per window;
   - `--workers N` for `backfill` and `backfill-back`: split the date range into N contiguous shards, each walking its
     shard; the ledger keeps them from overlapping or double-writing; the size cap check stays per day;
   - a seam to use `gfw.fetch_range` when it exists (detect it with `hasattr`), falling back to `fetch_day`, so the two
     branches merge in either order;
   - tests against a local TimescaleDB: N workers produce the same rows and ledger as one worker; a crash and restart
     resumes without gaps or duplicates.
3. Report the measured speed-up with the recommended worker count, and the exact command and systemd change the
   Vultr server would need (`be-integrate` posts it to Hamish's laptop agent).

## Phase 3 (be-integrate, not you)
After review and merge, `be-integrate` asks Hamish's laptop agent to apply the backend and restart the backfill
services with the new options, then checks progress in Tiger (read-only).
