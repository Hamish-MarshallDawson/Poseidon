# ml/data: Danish AIS archive

Source: **Danish Maritime Authority** (Søfartsstyrelsen), AIS data, http://aisdata.ais.dk/. Cite the DMA wherever
this data or a model trained on it is shown.

`dma.py` downloads the archive's daily files (`aisdk-YYYY-MM-DD.zip`, 550 to 750 MB zipped, about 4.5 GB of CSV),
cleans them with DuckDB and writes Parquet in the ml track contract (`docs/handoffs/ml-architecture.md`).

## On a fresh machine (one command, Python 3.12, no keys, no database)

```bash
git clone -b 121-ml-data git@github.com:Hamish-MarshallDawson/Hedged-Bets-hacktheburgh.git && cd Hedged-Bets-hacktheburgh
python3.12 -m venv ml/.venv && ml/.venv/bin/pip install -r ml/data/requirements.txt \
  && ml/.venv/bin/python -m ml.data.dma --days 14 --until 2026-11-05 --out ~/data/poseidon/dma --delete-zips
ml/.venv/bin/python -m ml.data.dma --out ~/data/poseidon/dma --verify    # optional: re-hash against manifest.json
```

`--days 14 --until 2026-11-05` fixes the exact days (23 Oct to 5 Nov 2026) so every machine builds the same data;
without `--until` it takes the newest days in the archive. `ml/requirements.txt` (the whole ml stack) pins the same
versions, so either file works. Re-running skips days already converted (`--force` redoes them) and reuses zips
already downloaded.

What to expect (measured 8 Nov on a 16-core desktop with 31 GB RAM, duckdb 1.5.6):

- Time: about 9 minutes for 14 days at defaults (3 downloads and 2 conversions at once): download 10 to 50 s per
  day (all 14 zips arrive in about 1.5 minutes), unzip 6 to 18 s, convert 20 to 70 s.
- Memory: about 3.2 GB per conversion, so about 7 GB at the default 2 at once (`--converts 1` halves it).
- Disk: 1.8 GB of output. Peak while running about 20 GB with `--delete-zips` (estimated, not measured: zips not
  yet converted, plus a 4.5 GB CSV and DuckDB scratch per conversion); the 8.7 GB of zips stay if it is not given.
- The same days give byte-identical Parquet with the same duckdb version (checked across thread counts), so
  `dataset_hash` in `manifest.json` can be compared between machines. Per-day row counts are in `stats/`.
- Expected result for `--days 14 --until 2026-11-05`: 137,129,082 rows (29,905,123 at 1 per minute), 8,458 ships,
  `dataset_hash` `ac9a4c343baad38e8c62554ed499a6cc222b7625258135850c9ba84ae39ad8f4` (duckdb 1.5.6).

## Output (`--out`, default `$POSEIDON_DMA_DIR`, else `~/data/poseidon/dma`)

| Path | What |
|---|---|
| `tracks/YYYY-MM-DD.parquet` | cleaned positions: `mmsi int32, ts int64 (epoch ms UTC), lat, lon float64, sog_kn, cog_deg float32, heading_deg, nav_status int16, cls ('A'/'B'), src ('dma')`, sorted by `mmsi, ts` |
| `tracks_1m/YYYY-MM-DD.parquet` | the same, first fix per ship per UTC minute |
| `identity/YYYY-MM-DD.parquet` | per ship per day: `cls, imo, name, callsign, ship_type` (DMA text), `type_group` (same groups as `dvm/normalise.py`), `length, width, draught, destination` (latest non-empty value), `fixes, first_ts, last_ts` |
| `stats/YYYY-MM-DD.json` | rows after each cleaning step, timings, bytes, sha256 |
| `manifest.json` | days, rows, ships, bytes, `dataset_hash` (over every file's sha256), cleaning parameters |

Reading from other ml code:

```python
from ml.data.dma import tracks_sql
con.execute(f"SELECT * FROM {tracks_sql(thin=True)} WHERE mmsi = 219000001 ORDER BY ts")
```

## Cleaning, in order

1. Class A and Class B only (drops base stations, AtoN, SAR aircraft); vessel MMSIs only (MID 200 to 799, the live
   normaliser's rule).
2. Placeholder positions dropped (|lat| > 90, |lon| > 180, lat or lon exactly 0), and fixes outside a box round the
   Danish coverage (lat 50 to 62, lon -2 to 22).
3. AIS "not available" values to NULL: sog >= 102.3, cog >= 360, heading >= 360, nav status 15.
4. Same mmsi and same second de-duplicated (copies from several receivers; 35 to 56% of rows, 23 Oct to 5 Nov 2026).
5. Speed gate at 40 kn with 200 m slack: first isolated spikes (both legs too fast), then any remaining jump from the
   previous kept fix.

Other options: `--day YYYY-MM-DD` (repeatable), `--download-only`, `--manifest-only`, `--downloads`, `--converts`,
`--threads`, `--memory`. Tests: `ml/.venv/bin/python -m pytest -q ml/data/tests`.
