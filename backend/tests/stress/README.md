# Stress and failure suite (#46)

These tests feed the real ingest path (`normalise` and `Live`) and the gap detector with broken, hostile and very heavy input. They then check the output against known ground truth.

The suite is **off by default**: plain `pytest tests` skips it.

## Run it

From `backend/`, with the venv from `backend/README.md`:

```bash
.venv/bin/pip install -r tests/stress/requirements.txt              # pytest-xdist

# Quick run, about 15 s on 4 cores
.venv/bin/python tests/stress/run_stress.py --workers 4

# Full run, Hamish's desktop: all cores but 4 by default
.venv/bin/python tests/stress/run_stress.py --scale full --workers 12 --replay ../data/raw/aisstream

# Check the detector tests with the reference checker
.venv/bin/python tests/stress/run_stress.py --detector reference
```

With `--replay`, pass the folder holding the raw log. The default is `data/raw/aisstream/` under `DATA_DIR`. Replay only reads it.

**Memory:** the full scale holds about 0.5 GB per worker, so 12 workers need about 6 GB free. Lower `--workers` if the live backend is short of RAM.

**Safety:** the suite never opens an AISStream connection, never touches Tiger, and never changes the log.

## What it covers

### Ingest (`test_ingest_stress.py`)

This file runs today.

| Fault | What is checked |
|---|---|
| Fuzzed fields | Out-of-range values of the right JSON type never crash. Values of the wrong JSON type (known gap 1) are tested too. |
| Bad positions | Latitude 91 and longitude 181 are dropped. 0/0 is tested as known gap 2. |
| Placeholder IMOs | `1`, `100000000`, `999999999` and `9999999` are always flagged, and `0` becomes null. `1234567` is known gap 3. |
| Duplicates | Duplicates change nothing that is stored. |
| Reordered delivery | No vessel's dot moves back in time, and the newest fix wins. |
| Late messages | Event time is exact when a message is up to 50 s late. Over 55 s is known gap 4. |
| Clock skew | A skew of ±30 to ±120 s never drops a live ship from the map. A single future-dated fix is known gap 5. |
| Bursts | The full consume path runs at 20 or more times the live rate of 90 msg/s. The quick run measured about 30,000 msg/s on one core. |
| Queue overflow | Dropped messages are counted, not raised. |

### Gap detector (`test_gaps_stress.py`)

These tests target Jake's `dvm/gaps.py` and skip until it is merged. They use the thresholds from 06: a 1800 s floor, k of 20, and at least 3 neighbours within 20 km.

| Scenario | What is checked |
|---|---|
| A lone switch-off inside a convoy | Flagged `deliberate_candidate`. The gap has the exact `start_ts` and `end_ts`, is raised between 30 and 32 minutes after the last fix, and its implied speed is within 5%. No other ship is falsely flagged. |
| Open sea with no neighbours | Flagged `unknown`. |
| Inside a 45 km receiver hole | Ships more than 20 km inside the edge are never flagged deliberate. Ships near the edge are a non-strict xfail: they hear neighbours outside the hole, so they need the coverage cell state. |
| Whole-area receiver outage | Nothing is flagged deliberate. |
| Our own 45-minute stall | Every gap is flagged `own_stall`. |
| GNSS jamming | Positions jump but no gaps open. |
| Traffic that is lossy but alive | With 30% loss, Class B ships reporting every 3 minutes and interval jitter, no gaps open. |
| A switch-off with faults on top | With ±120 s clock skew, or with 30% duplicates plus reordering, there is still exactly one gap. |
| A quarter of the fleet switching off | All are found, at 50 or more times real time. |

### Recorded log (`test_replay_stress.py`)

These tests need `--replay`.

- **Every real message:** none crashes `normalise`, and the run reports the rate and its speed against real time.
- **Gaps per real hour:** the run prints how many gaps of each flag the detector raises. This is information, not pass or fail.
- **Injected switch-off:** 45 minutes of the busiest steady ship is deleted from three merged hours. The suite expects one gap, flagged deliberate if 3 or more neighbours were heard.

## Known gaps found so far

These are `xfail(strict=True)` tests. They pass while the gap exists and fail once someone fixes it, at which point the marker should be removed.

1. **One malformed message can stop ingest.** A field of the wrong JSON type, such as `Sog` as a string, raises inside `normalise`. `Hub.consume` in `app.py` has no try/except, so ingest would stop. AISStream sends typed JSON, so this is unlikely live, but a try/except per message is the cheap fix.
2. **0/0 positions are accepted.** `DATA-MODEL-IMPLICATIONS.md` proposes filtering them.
3. **The placeholder IMO 1234567 passes as clean**, because its check digit is valid.
4. **Messages over about 55 s late get an event time exactly 60 s wrong**, and they aren't flagged `late`. This is the `rebuild_ts` shortcut in 06 section 1.3.
5. **One future-dated fix freezes a vessel.** Later true fixes are older, so the dot never moves again.

There's also a limit and a log issue:

- **The 06 neighbour test is fooled at the edge of a receiver hole** (the non-strict xfail). The detector needs the coverage cell state, or a same-class rate check, to catch it.
- **`rawlog.py` gzips in a daemon thread.** If the process exits mid-rotation, it leaves a truncated `.jsonl.gz` beside the complete `.jsonl`. The replay reader prefers the plain file. This is low risk: shutdown would have to land within seconds of the hour rolling over.

## Detector interface

`adapter.py` is the only file that knows the detector's names. The proposed interface is `GapDetector()` with three methods:

- `observe(PositionReport)` returns a list of `GapEvent`, and closes gaps.
- `tick(now_ms)` returns a list of `GapEvent`, runs every 5 s on the recv clock, and opens and updates gaps.
- `note_stall(start_ms, end_ms)`, which the harness calls once a stall has ended.

If the real names differ, change `adapter.py` only.

`reference_detector.py` follows the 06 rules in about 100 lines. It exists only to prove these tests are right. Three deliberately broken versions of it each fail the expected tests, which shows the tests catch real faults. It is not the product's detector.
