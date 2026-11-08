# Brief: GFW gap events never land (issue #112)

Read `docs/handoffs/COMMON.md` first. Agent `gfw-gaps`, branch `112-gfw-gaps`.

## What's wrong
`observations` holds 0 rows of `kind = 'gap'`. `gfw.fetch_day` asks `/events` for `public-global-gaps-events:latest`
with each region's polygon. Checked at 03:40 UTC with the working token: every geometry query for our regions returns
`total = 0` (Danish straits for 1 day, 30 days and all of 2024; Hormuz for Sep to Oct 2026). The same dataset with no
geometry returns 9,117 events for one October 2026 week and 16,930 for one January 2024 week. Each event has
`gap.offPosition`, `gap.onPosition`, `durationHours`, `distanceKm`, `impliedSpeedKnots`, `intentionalDisabling`,
`positionsPerDaySatReception`, `positions12HoursBeforeSat`, plus `start`, `end`, `position`, `boundingBox`, `regions`
and `vessel` (ssvid = MMSI). Some `start` values were years before the requested window: check how GFW selects events
by date (start, end or overlap).

These events are the most direct labels we have for go-dark training: where a ship's AIS went off and came back on.

## Outcome
1. **Find out** why geometry queries return 0 (for example: GFW gaps start offshore, so narrow coastal polygons miss
   them; or geometry filters by a field gaps don't use; or a `regions` filter works where geometry doesn't). Try a few
   variants (larger polygons such as the Baltic plus North Sea, or the Arabian Sea; the `regions` body filter; date
   semantics) with short, polite calls.
2. **Fetch** gap events in a way that works: wider areas or worldwide by date, kept when the off or on position (or the
   segment between them) falls in an area we care about. Propose the areas (at least the waters around our four
   regions; say if worldwide is affordable: count events per day and estimate rows and MB per year).
3. **Store** each as an observation, `kind = 'gap'`, `src = 'gfw'`, stable id `gfw:gap:<event id>`, `ts` = AIS off,
   `end_ts` = AIS on, `lat`/`lon` = off position, the on position and the gap fields in `attrs`, `mmsi` from ssvid,
   `available_ts` as `gfw.available` does. Use a new ledger stream (for example `src = 'gfw', stream = 'gaps'`, region =
   your area name) so it backfills and resumes separately from the existing per-region windows.
4. **Code:** put the gap logic in a new module `backend/dvm/sources/gfw_gaps.py`. In `jobs.py` add only the small
   registration your stream needs (another agent, `gfw-parallel`, is editing `jobs.py`; keep your change minimal so
   the rebase is trivial), and stop `gfw.fetch_day` asking for gaps per region if your stream replaces it (a one-line
   change in `EVENT_DATASETS` usage; `gfw-month` owns the rest of `gfw.py`, so keep it to that).
5. **Test** parsing with recorded responses, the area filter, idempotent re-fetch, and a backfill of a short range into
   a local TimescaleDB. Report: why the queries returned 0, events per day in each area, the estimated size of a year,
   and the command the Vultr server needs to backfill gaps.
