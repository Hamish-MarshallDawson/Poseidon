# What the data means for the database, backend and frontend

Proposals for discussion, written from the research on 7 November 2026 and a read of `backend/dvm/models.py`, `backend/dvm/store.py` and `frontend/src/types.ts` at commit `bfba7c9`. `models.py` says field names change only by asking on the board, so nothing here changes the contract by itself. @Hamish-MarshallDawson @JakeCallcut, please say what fits.

**Update from the board, 18:23:** Jake decided that MMSI is the only ship ID for the 24-hour build, with no vessel identity table, identity link records or `vessel_id`, and that identity-change detection is out of scope. Names come from the latest statics row for that MMSI at or before `as_of`. The identity proposals below stay as research for later. Radar tables, freshness fields, wording, map scope and live versus as-of are still open.

## Lessons from the MarineTraffic wave

Details are in `marinetraffic/SYNTHESIS.md`. Proposals only:

- **Label every position's source class and coverage basis,** so a silence says who was listening. MarineTraffic does this with terrestrial, roaming and satellite labels.
- **Model silence as states, not one flag.** For example: fresh, silent while nearby reception is normal, out of coverage, or feed outage. Adding this to `VesselView.status` would be a contract change.
- **Keep raw and cleaned layers apart.** Don't delete suspect positions, because cleaning rules are signals too. Display can be thinned, but silence analysis needs raw rates.
- **Label proxies and never present them as ships seen.** PortWatch counts and similar sources need their own table with granularity and lag.
- **Age stale ships off the map, and don't interpolate across gaps.**
- **Budget paid APIs per row returned,** not per request, if one is ever added.

## Five facts that shape the design

1. **Sources run on different clocks.** The same picture mixes data under a second old, hours old, days old and weekly.
2. **MMSI isn't a stable ship ID.** In the Hormuz data, 1,839 vessel records share 1,731 MMSIs, and ships change MMSI, name and flag. The IMO number is the better hull ID, but it's self-reported and often missing.
3. **Radar has no identity.** A detection is a position, time and rough size until it's matched to AIS.
4. **Silence is ambiguous.** It can mean a switch-off, poor reception, port entry, our own stall or a feed outage. AISStream's zero in the Middle East is a feed gap, not an empty sea.
5. **Coverage varies by feed and place.** Digitraffic removes fishing boats. Global Fishing Watch's radar barely covers the Gulf of Finland.

## Database

| Proposal | Why | Fit with today |
|---|---|---|
| **Keep separate event, received and available times** | Prevents leakage in scoring. For example, radar sensed at 05:00 might not be available until 11:00 | `ts` and `recv_ts` already exist; `available_ts` could be added for batch data |
| **Add a vessel identity table** with vessel ID, IMO, MMSI, name, flag, source, first seen and last seen | Lets one hull span several MMSIs and supports the identity-change idea | New table; `statics` can feed it |
| **Add identity link records** with confidence and evidence | Keeps "same hull" as an inference, not a rewrite of history | New table |
| **Add radar scene and detection tables** | Coverage by scene is needed to tell "not imaged" from "not there" | `SarDetection` is already in the data model for GFW; add `src`, scene ID, sensed time, line time, size, detector, score |
| **Add radar-to-AIS match records** with distance, gate, moving-ship correction and match version | Results must be re-scorable as methods improve | New table; never overwrite the raw detection |
| **Extend `Src`** with `sentinel1`, `portwatch`, `gpsjam` and later feeds | Current list doesn't include them | Contract change; ask first |
| **Keep source health per feed and cell** | Separates feed outages from ship silence | `coverage_1m` is a good start; could add `src` |
| **Keep raw logs and keep chunk settings provisional** | Replay needs raw data, and short chunks may suit live data but not GFW history | Hypertables already exist; batch data may need longer chunks |
| **Keep context reference tables with a version date** | Sanctions and detention lists change. For example, a detention isn't a sanction | Download at build time; don't commit OpenSanctions |

### Queries the schema should make easy

- Which ships were heard near this point in the 30 minutes before this radar image?
- Which radar targets were unmatched, and was the area actually imaged?
- Which vessel IDs share this IMO, and what changed?
- When did this cell last have normal traffic?
- What did the system know at time T?

## Backend

- **Separate three paths.** Live stream (AISStream, Digitraffic), batch jobs (Danish files, Global Fishing Watch, PortWatch, GPSJam) and on-demand radar. Each has a different failure mode and clock.
- **Treat each source as an adapter** that outputs the shared schema with its own provenance and quality flags. New streams from the MarineTraffic wave should plug in the same way.
- **Run radar as a job, not a stream.** Search the catalogue, read the window, detect, match, store. Reads take seconds, but detection takes from seconds on a CPU threshold to minutes on a GPU model, plus up to 2.5 GB of downloads per scene for the Ai2 detector.
- **Fix the radar traps once in one place:** Planetary Computer location metadata, per-line times, duplicates and moving-ship shift.
- **Match with stated tolerance.** Test 200, 500 and 1,000 m, include a chance control, merge duplicate boxes on the same ship and mask land and fixed structures.
- **Treat identity detection as a batch job.** It needs no live feed.
- **Serve freshness with data:** source, event time and age, so clients don't have to guess.
- **Respect licences at the API edge.** Credit Global Fishing Watch and OpenSanctions, keep tokens on the backend, and don't redistribute restricted files.

## Frontend

- **Make freshness visible.** Show live, hours-old and days-old data differently, with the age on every ship, for example "AIS 4 days old" or "radar 5 h ago".
- **Separate what is known from what is inferred.** Use different layers for announced positions, radar detections and predictions or estimates.
- **Show coverage as well as ships.** A blank Red Sea on AISStream must read as "no data from this feed", not "no ships". A radar layer should show the image footprint, because outside it we saw nothing.
- **Radar targets look different from ships.** Unmatched ones have no name, type or flag, only size, time and distance to the nearest AIS.
- **Make identity a first-class view.** A ship page could show a timeline of names, MMSIs and flags, with the evidence and alternative explanations.
- **Use a time control.** Mixed clocks suit replay and "as of" views better than a single live map. A live view fits northern Europe; a historical investigation fits Hormuz.
- **Change the language.** `coverage_flag: "deliberate_candidate"` and `GapEvent` feed the UI. Prefer wording such as "no AIS received; reception normal nearby" over "went dark". Radar can't show intent, and masters may lawfully switch off for safety.

### Suggested `VesselView` additions, if agreed

- `vessel_id`, because `mmsi` alone can split a hull.
- `src`, `age_s` and possibly `source_tier`.
- `identity_change_recent` with evidence.
- A separate `RadarTarget` type rather than overloading `VesselView`.

## Predictions later

- **Record what's possible at the time.** Scoring must use only data available then, which `available_ts` protects.
- **Danish gaps are mostly reception problems,** so per-cell reception should be a feature or filter.
- **The event rate may be low.** A live test saw only 3 strict silences in 40 minutes. Measure the base rate before relying on a gap forecast.
- **Identity change may offer a second target,** but it needs labels that separate ordinary sales from suspicious changes.
- **Market links are weak so far.** Hormuz transits correlate with Brent at r = -0.64 over 718 days, but within 2024 and 2025 alone it's +0.17, so that looks like one war-driven break rather than a usable signal.
- **Keep the radar test independent** of the system's own gap detector where possible.

## Open questions for the team

1. Should vessel identity be a new table now, or wait until after the live map?
2. Should radar be part of the demo, or a separate proof?
3. Is the map global, or focused on where data is strong?
4. Should the UI's primary view be live or as-of?
5. What should replace `deliberate_candidate`?
