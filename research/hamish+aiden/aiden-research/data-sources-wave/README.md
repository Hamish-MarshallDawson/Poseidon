# Data sources: start here

Living index of what the team has found about data for the ship-tracking project. Research only; nothing here decides what gets built.

Last updated: Saturday 7 November 2026, evening. A MarineTraffic research wave is still running and will add to this folder.

## Read in this order

1. **[SYNTHESIS.md](SYNTHESIS.md):** what works, where, and how well.
2. **[DATA-STREAMS.md](DATA-STREAMS.md):** catalogue of every source, how to reach it, how delayed it is and whether we've tested it. Add new sources here.
3. **[DATA-MODEL-IMPLICATIONS.md](DATA-MODEL-IMPLICATIONS.md):** what the data means for the database, backend, frontend and later predictions. These are proposals for discussion.

## The short version

- **Radar-versus-AIS matching is real for ships of about 50 m or more.** In Danish waters, 88 to 94% of moving ships had a radar detection within 500 m, against 13 to 23% by chance. That's 32 ship observations from one pass, so treat it as early evidence.
- **Live AIS is regional.** It's good in northern Europe. AISStream shows zero vessels in the Middle East and Natuna. Global Fishing Watch covers those areas with AIS about 4 days old.
- **Raw Sentinel-1 radar is hours old, but occasional:** roughly 5 passes a week at a point in the Baltic, 3 at Hormuz, and under 1 at Malacca and Natuna.
- **Radar can't name a ship.** Identity comes only from AIS, so identity tracking matters as much as detection.
- **Ships that "vanish" often return under a new identity.** In samples of 40 silent tankers, the same IMO number later appeared under a different radio ID for 29 at Hormuz, 31 at Malacca and 38 in Danish waters. It's common everywhere, and some cases will be ordinary sales.
- **Gaps are noisy.** Danish gaps are mostly reception problems, and strict silence events look rare. That matters for any forecast.

## Folder map

| Path | Contents |
|---|---|
| `BRIEF.md` | The brief for the 11-agent wave |
| `d-*.md` | Discovery reports: AIS, imagery, context data, methods, value and prior art |
| `t-*.md` | Direct test reports: live AIS, history, satellite access, radar matching, detector, regions |
| `shared-notes.md` | Running notes the agents shared |
| `results/` | Measurement outputs from the orchestrator's AISStream and Global Fishing Watch tests |
| `scripts/` | The throwaway scripts behind the tests, for reference, not production |
| `marinetraffic/` | The MarineTraffic wave's brief, notes and reports |

Agent reports are AI-generated and may contain errors. SYNTHESIS.md says which results the orchestrator checked. Where a report conflicts with SYNTHESIS.md, trust SYNTHESIS.md and tell Aiden's agent on the board.

## Keeping this current

When you find or test a source, add a row to DATA-STREAMS.md through a PR and post on the board. Never commit API keys. Downloaded data stays out of the repo; OpenSanctions in particular should be fetched at build time.

Global Fishing Watch and OpenSanctions are CC BY-NC 4.0, so credit them wherever their data appears.
