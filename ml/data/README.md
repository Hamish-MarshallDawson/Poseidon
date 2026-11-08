# ml/data: Danish AIS archive

Source: **Danish Maritime Authority** (Søfartsstyrelsen), AIS data, http://aisdata.ais.dk/. Cite the DMA wherever
this data or a model trained on it is shown.

`dma.py` downloads the archive's daily files (`aisdk-YYYY-MM-DD.zip`, 550 to 750 MB zipped, about 4.5 GB of CSV),
cleans them with DuckDB and writes Parquet in the ml track contract (`docs/handoffs/ml-architecture.md`).

```bash
python3 -m venv ml/.venv && ml/.venv/bin/pip install duckdb pyarrow httpx pytest
ml/.venv/bin/python -m ml.data.dma                   # 14 newest days (3 downloads, 2 conversions at once)
ml/.venv/bin/python -m ml.data.dma --day 2026-11-05  # one day; --days N for the N newest
ml/.venv/bin/python -m pytest -q ml/data/tests
```

Days already converted are skipped (`--force` redoes them); zips already downloaded with the listed size are reused.

## Output (`/home/aiden/data/poseidon/dma/`, or `--out`, or `$POSEIDON_DMA_DIR`)

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
4. Same mmsi and same second de-duplicated (copies from several receivers; about 56% of rows in Nov 2026).
5. Speed gate at 40 kn with 200 m slack: first isolated spikes (both legs too fast), then any remaining jump from the
   previous kept fix.
