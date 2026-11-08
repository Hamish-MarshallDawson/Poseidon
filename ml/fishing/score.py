"""Live fishing-in-protected-areas scores without the GFW ingest: fetch, build this week's features, score, grade.

    ml/.venv/bin/python -m ml.fishing.score [--as-of 2026-11-02] [--no-fetch] [--write --allow-tiger]

1. Fetch the GFW fishing events of our four regions for the months covering the last 13 weeks (the features look back
   90 days; the cases are vessels with an event in the last 8 weeks) from the GFW API, politely (one request at a
   time, as `ml.fishing.fetch`), into `<FISHING_DATA>/live/events/<region>/<month>.parquet`.
2. Build the features of this UTC week (`as_of` = its Monday 00:00) with the training code's own builder
   (`ml.fishing.dataset.features`, which uses only events with `available_ts <= as_of`).
3. Score them with the champion (`<POSEIDON_DATA>/models/fishing/champion.json`).
4. Grade: every live `fishing_mpa_7d` score in Tiger whose week has passed (week end before the label frontier,
   newest event minus 2 days) and has no outcome gets one: label = a fishing event starting in that week inside an MPA.

Without `--write --allow-tiger` it is a dry run: Tiger is opened read-only (grading candidates are counted) and the
score distribution is printed. Rows: scores (target `fishing_mpa_7d`, mode `live`, model_version = the champion run
id, made_at = time = the week start, horizon 7 d, features = the snapshot); outcomes keyed by the score id.
Token: `GFW_API_TOKEN` from the repo `.env`, never printed. GFW data is CC BY-NC 4.0.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from pathlib import Path

import numpy as np
import pandas as pd

import ml
from ml.fishing import dataset as D
from ml.fishing import fetch

TARGET = "fishing_mpa_7d"
FEATURE_VERSION = "fishing-v1"
LIVE_DATA = fetch.DEFAULT_OUT / "live"
MODELS = Path(os.getenv("ML_ARTIFACTS") or Path(os.environ.get("POSEIDON_DATA", "/home/aiden/data/poseidon")) / "models")
LOOKBACK_DAYS = 91


def week_start(ms: int) -> int:
    return ((int(ms) - D.MONDAY0) // D.WEEK) * D.WEEK + D.MONDAY0


def refresh(out: Path, as_of: int, log=print) -> dict:
    """Fetch every month overlapping [as_of - LOOKBACK_DAYS, now] for every region (newest data overwrites)."""
    from dotenv import load_dotenv
    load_dotenv(ml.REPO / ".env")
    from dvm.sources import gfw
    from dvm.sources.common import REGIONS
    lo = pd.Timestamp(as_of - LOOKBACK_DAYS * D.D, unit="ms")
    months = pd.period_range(lo.to_period("M"), pd.Timestamp.utcnow().tz_localize(None).to_period("M"), freq="M")
    client = gfw.Client()
    stats = {"calls": 0, "events": 0}
    try:
        for m in months[::-1]:
            for region, bbox in REGIONS.items():
                t = time.time()
                df, info = fetch.fetch_month(client, region, bbox, m.start_time.date())
                f = out / "events" / region / f"{m}.parquet"
                f.parent.mkdir(parents=True, exist_ok=True)
                df.to_parquet(f, index=False)
                stats["events"] += info["events"]
                log(json.dumps({"region": region, "month": str(m), **info, "s": round(time.time() - t, 1)}))
    finally:
        stats["calls"] = client.calls
        client.close()
    return stats


def champion(models: Path = MODELS) -> tuple[object, dict]:
    from ml.fishing.target import Lgbm
    c = json.loads((models / "fishing" / "champion.json").read_text())
    art = Path(c["artifact"])
    meta = json.loads((art / "model.json").read_text())
    if meta.get("model") != "lgbm":
        raise SystemExit(f"fishing champion {c['run_id']} is a {meta.get('model')} model; only lgbm is served")
    return Lgbm.load(art), c


def live_cases(ev: pd.DataFrame, as_of: int) -> pd.DataFrame:
    """Vessels with a known event (available by as_of) that started in the LOOKBACK_WEEKS weeks before as_of."""
    lo = as_of - D.LOOKBACK_WEEKS * D.WEEK
    k = ev[(ev["available_ts"] <= as_of) & (ev["ts"] >= lo) & (ev["ts"] < as_of)]
    return pd.DataFrame({"mmsi": np.sort(k["mmsi"].unique()).astype("int64"), "as_of": int(as_of)})


def score_week(ev: pd.DataFrame, as_of: int, model, gfw_cache: Path = D.GODARK_GFW) -> pd.DataFrame:
    c = live_cases(ev, as_of)
    if c.empty:
        return pd.DataFrame(columns=["mmsi", "as_of", "case_id", "p"] + D.FEATURES)
    f = pd.concat([c, D.features(c, ev, gfw_cache)], axis=1)
    f["case_id"] = f["mmsi"].astype(str) + ":" + pd.to_datetime(f["as_of"], unit="ms").dt.strftime("%Y-%m-%d")
    p = model.predict(f)
    f["p"] = p["p"].to_numpy()
    return f


def score_id(mmsi: int, as_of: int) -> str:
    return f"{TARGET}:{int(mmsi)}:{int(as_of)}"


def score_rows(f: pd.DataFrame, run_id: str) -> list[tuple]:
    rows = []
    for r in f.to_dict("records"):
        feats = {k: (None if isinstance(v, float) and not np.isfinite(v) else
                     (v.item() if hasattr(v, "item") else v)) for k, v in r.items() if k in D.FEATURES}
        t = pd.Timestamp(int(r["as_of"]), unit="ms", tz="UTC").to_pydatetime()
        rows.append((t, score_id(r["mmsi"], r["as_of"]), int(r["mmsi"]), TARGET, int(r["as_of"]), D.HORIZON_S,
                     float(r["p"]), run_id, FEATURE_VERSION, json.dumps(feats), None, "live"))
    return rows


def grade(pending: list[dict], ev: pd.DataFrame, frontier: int, now_ms: int) -> list[tuple]:
    """Outcome rows for scores whose week ended before the frontier. Label: an MPA fishing event starting in the week."""
    by = {int(m): g for m, g in ev[ev["in_mpa"]].groupby("mmsi")}
    out = []
    for s in pending:
        a = int(s["made_at"])
        if a + D.WEEK > frontier:
            continue
        g = by.get(int(s["mmsi"]))
        hit = None if g is None else g[(g["ts"] >= a) & (g["ts"] < a + D.WEEK)]
        label = hit is not None and len(hit) > 0
        eid = str(hit["event_id"].iloc[0]) if label else None
        lead = int((int(hit["ts"].iloc[0]) - a) // 1000) if label else None
        out.append((s["id"], int(s["mmsi"]), TARGET, a, D.HORIZON_S, now_ms, label, None, eid, lead))
    return out


async def tiger(rows: list[tuple], ev: pd.DataFrame, frontier: int, write: bool) -> dict:
    import asyncpg
    from ml.godark_gfw.tiger import READ_ONLY, _env_url
    conn = await asyncpg.connect(_env_url(), server_settings=None if write else READ_ONLY, command_timeout=300)
    try:
        pending = [dict(r) for r in await conn.fetch(
            "SELECT s.id, s.mmsi, s.made_at FROM scores s LEFT JOIN outcomes o ON o.score_id = s.id "
            "WHERE s.target = $1 AND s.mode = 'live' AND o.score_id IS NULL", TARGET)]
        outs = grade(pending, ev, frontier, int(time.time() * 1000))
        res = {"pending": len(pending), "gradable": len(outs), "positives": sum(bool(o[6]) for o in outs)}
        if write:
            async with conn.transaction():
                await conn.executemany(
                    "INSERT INTO scores (time, id, mmsi, target, made_at, horizon_s, p, model_version, feature_version,"
                    " features, contrib, mode) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10::jsonb,$11::jsonb,$12)"
                    " ON CONFLICT (id, time) DO NOTHING", rows)
                await conn.executemany(
                    "INSERT INTO outcomes (score_id, mmsi, target, made_at, horizon_s, resolved_at, label, censored,"
                    " event_id, lead_s) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10) ON CONFLICT (score_id) DO NOTHING",
                    outs)
            res |= {"scores_written": len(rows), "outcomes_written": len(outs)}
        return res
    finally:
        await conn.close()


def distribution(p: np.ndarray) -> dict:
    if not len(p):
        return {"n": 0}
    q = np.quantile(p, [0.1, 0.25, 0.5, 0.75, 0.9, 0.99])
    bins = [0, 0.05, 0.1, 0.2, 0.3, 0.5, 1.0001]
    h = np.histogram(p, bins=bins)[0]
    return {"n": int(len(p)), "mean": round(float(p.mean()), 4),
            "quantiles": dict(zip(["p10", "p25", "p50", "p75", "p90", "p99"], [round(float(x), 4) for x in q])),
            "bins": {f"{bins[i]:.2f}-{min(bins[i + 1], 1):.2f}": int(h[i]) for i in range(len(h))},
            "distinct": int(len(np.unique(np.round(p, 6))))}


def run(as_of: int | None = None, data: Path = LIVE_DATA, do_fetch: bool = True, write: bool = False,
        tiger_check: bool = True, log=print) -> dict:
    as_of = week_start(time.time() * 1000) if as_of is None else week_start(as_of)
    t0 = time.time()
    info: dict = {"as_of": pd.Timestamp(as_of, unit="ms", tz="UTC").isoformat()}
    if do_fetch:
        info["fetch"] = refresh(data, as_of, log)
    info["fetch_s"] = round(time.time() - t0, 1)
    ev = D.prepare(fetch.load(data))
    frontier = int(ev["ts"].max()) - 2 * D.D
    model, champ = champion()
    f = score_week(ev, as_of, model)
    info |= {"model_version": champ["run_id"], "events": len(ev), "vessels_scored": len(f),
             "by_region": f["region"].value_counts().to_dict() if len(f) else {},
             "label_frontier": pd.Timestamp(frontier, unit="ms", tz="UTC").isoformat(),
             "p": distribution(f["p"].to_numpy(float) if len(f) else np.array([]))}
    if len(f):
        info["top"] = f.nlargest(5, "p")[["mmsi", "region", "flag", "gear", "p"]].round(4).to_dict("records")
    if tiger_check:
        info["tiger"] = asyncio.run(tiger(score_rows(f, champ["run_id"]), ev, frontier, write))
    info["mode"] = "write" if write else "dry-run"
    info["s"] = round(time.time() - t0, 1)
    return info


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--as-of", help="a date in the week to score (default: this week)")
    ap.add_argument("--data", type=Path, default=LIVE_DATA)
    ap.add_argument("--no-fetch", action="store_true", help="score from the events already in --data")
    ap.add_argument("--no-tiger", action="store_true", help="skip Tiger entirely (no grading count)")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--allow-tiger", action="store_true")
    a = ap.parse_args()
    if a.write and not a.allow_tiger:
        raise SystemExit("--write writes to Tiger: pass --allow-tiger as well")
    if a.write and a.no_tiger:
        raise SystemExit("--write needs Tiger")
    as_of = int(pd.Timestamp(a.as_of, tz="UTC").value // 1_000_000) if a.as_of else None
    print(json.dumps(run(as_of, a.data, not a.no_fetch, a.write, not a.no_tiger), indent=1, default=str))


if __name__ == "__main__":
    main()
