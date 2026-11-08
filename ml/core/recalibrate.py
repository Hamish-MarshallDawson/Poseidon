"""Recalibrate the live champions from the graded prediction ledger (the loop's fastest correction).

    python -m ml.core.recalibrate --models-dir /opt/dvm/models [--hours 48] [--apply]

Reads the outcomes the live grader and the backtest wrote to Tiger (read-only session) for the model versions that
champions.json names now, and fits:
- route: per horizon, radius multipliers k80 = quantile_0.8(error / r80) and k95 = quantile_0.95(error / r95);
- go-dark: per head, a logit shift of the isotonic map so the mean probability equals the hit rate.
Each fit is made on the older half of the rows (by made_at) and checked on the newer half: it is kept only when the
newer half gets closer to nominal (route coverage) or to a lower log loss (go-dark), and when the change is not
negligible. A kept fit is written as a new artifact folder `<version>-calN` next to the old one and, with --apply,
champions.json is rewritten atomically (the predictor reloads it every cycle; no restart). Old folders stay for
rollback. Point predictions and rankings never change here; retraining does that (ml.core.loop).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import shutil
from pathlib import Path

import numpy as np
import pandas as pd

MIN_ROUTE_ROWS = 600        # per horizon
MIN_DARK_POS = 20           # positives per head
NEGLIGIBLE = 0.03           # radius factors within 3% of 1, or a logit shift under 0.03: no new version
HEAD_TARGET = {"3600": "dark_1h", "21600": "dark_6h", "86400": "dark_24h"}


def _logit(p):
    p = np.clip(np.asarray(p, float), 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def _expit(x):
    return 1 / (1 + np.exp(-np.asarray(x, float)))


def _halves(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    d = df.sort_values("made_at", kind="stable")
    n = len(d) // 2
    return d.iloc[:n], d.iloc[n:]


def fit_route(rows: pd.DataFrame) -> dict:
    """{horizon_s: {k80, k95, n, cov80_before, cov80_after, cov95_before, cov95_after, keep}} on the newer half."""
    out = {}
    for h, d in rows.groupby("horizon_s"):
        if len(d) < MIN_ROUTE_ROWS:
            continue
        a, b = _halves(d)
        k80 = float(np.quantile(a.error_m / a.radius_m_80, 0.8))
        k95 = float(np.quantile(a.error_m / a.radius_m_95, 0.95))
        c80b, c95b = float((b.error_m <= b.radius_m_80).mean()), float((b.error_m <= b.radius_m_95).mean())
        c80a, c95a = float((b.error_m <= k80 * b.radius_m_80).mean()), float((b.error_m <= k95 * b.radius_m_95).mean())
        better = abs(c80a - 0.8) + abs(c95a - 0.95) < abs(c80b - 0.8) + abs(c95b - 0.95)
        big = max(abs(k80 - 1), abs(k95 - 1)) > NEGLIGIBLE
        # final factors from all rows, once the split has shown the fit generalises
        k80f = float(np.quantile(d.error_m / d.radius_m_80, 0.8))
        k95f = float(np.quantile(d.error_m / d.radius_m_95, 0.95))
        out[int(h)] = {"k80": round(k80f, 4), "k95": round(k95f, 4), "n": len(d), "cov80_before": round(c80b, 3),
                       "cov80_after": round(c80a, 3), "cov95_before": round(c95b, 3), "cov95_after": round(c95a, 3),
                       "keep": bool(better and big)}
    return out


def fit_godark(rows: pd.DataFrame) -> dict:
    """{target: {shift, n, positives, logloss_before, logloss_after, keep}} with the check on the newer half."""
    from scipy.optimize import minimize_scalar
    out = {}
    for tg, d in rows.groupby("target"):
        y = d.label.astype(int)
        if y.sum() < MIN_DARK_POS:
            continue
        a, b = _halves(d)
        ya, yb = a.label.astype(int).to_numpy(), b.label.astype(int).to_numpy()
        la, lb = _logit(a.p), _logit(b.p)

        def nll(s, l, yy):
            q = np.clip(_expit(l + s), 1e-9, 1 - 1e-9)
            return float(-np.mean(yy * np.log(q) + (1 - yy) * np.log(1 - q)))
        s_a = minimize_scalar(lambda s: nll(s, la, ya), bounds=(-5, 3), method="bounded").x
        before, after = nll(0.0, lb, yb), nll(s_a, lb, yb)
        l_all, y_all = _logit(d.p), y.to_numpy()
        s = float(minimize_scalar(lambda s: nll(s, l_all, y_all), bounds=(-5, 3), method="bounded").x)
        out[tg] = {"shift": round(s, 4), "n": len(d), "positives": int(y.sum()), "logloss_before": round(before, 5),
                   "logloss_after": round(after, 5), "mean_p": round(float(d.p.mean()), 5),
                   "hit_rate": round(float(y.mean()), 5), "keep": bool(after < before and abs(s) > NEGLIGIBLE)}
    return out


def next_version(version: str) -> str:
    m = re.match(r"^(.*)-cal(\d+)$", version)
    return f"{m.group(1)}-cal{int(m.group(2)) + 1}" if m else f"{version}-cal1"


def write_route(src: Path, dst: Path, fit: dict, rows_info: str) -> dict:
    shutil.copytree(src, dst)
    m = json.loads((dst / "model.json").read_text())
    kept = {h: f for h, f in fit.items() if f["keep"]}
    k80d = float(np.median([f["k80"] for f in kept.values()]))
    k95d = float(np.median([f["k95"] for f in kept.values()]))
    used = {}
    for hs, spec in m["heads"].items():
        f = fit.get(int(hs))
        if f is None:                 # too few graded rows to measure: the kept heads' median factor
            k80, k95 = k80d, k95d
        elif f["keep"]:
            k80, k95 = f["k80"], f["k95"]
        else:                         # measured and the fit refused (already calibrated): unchanged
            k80, k95 = 1.0, 1.0
        for key, k in (("radius_m_80", k80), ("radius_m_95", k95)):
            v = spec[key]
            if isinstance(v, dict):
                v["r"] = [round(x * k, 1) for x in v["r"]]
            else:
                spec[key] = round(float(v) * k, 1)
        used[hs] = {"k80": k80, "k95": k95, "measured": f is not None, "kept": bool(f and f["keep"])}
    parent = m["version"]
    m["version"] = dst.name
    m.setdefault("recalibrations", []).append({"parent": parent, "method": "radius x quantile(error/radius)",
                                               "rows": rows_info, "factors": used, "check": fit})
    (dst / "model.json").write_text(json.dumps(m, indent=1))
    return used


def write_godark(src: Path, dst: Path, fit: dict, rows_info: str) -> dict:
    shutil.copytree(src, dst)
    m = json.loads((dst / "model.json").read_text())
    used = {}
    for hs, spec in m["heads"].items():
        f = fit.get(HEAD_TARGET.get(hs, ""))
        if not f or not f["keep"] or not spec.get("calibration"):
            continue
        cal = spec["calibration"]
        cal["y"] = [float(v) for v in np.maximum.accumulate(_expit(_logit(cal["y"]) + f["shift"]))]
        used[hs] = f["shift"]
    parent = m["version"]
    m["version"] = dst.name
    m.setdefault("recalibrations", []).append({"parent": parent, "method": "logit shift of the isotonic map",
                                               "rows": rows_info, "shifts": used, "check": fit})
    (dst / "model.json").write_text(json.dumps(m, indent=1))
    return used


async def fetch_rows(url: str, route_version: str | None, godark_version: str | None, hours: float):
    import asyncpg
    con = await asyncpg.connect(url, server_settings={"default_transaction_read_only": "on",
                                                      "statement_timeout": "120000"})
    try:
        since = f"(extract(epoch from now()) * 1000 - {int(hours * 3_600_000)})::bigint"
        route = await con.fetch(
            "SELECT r.made_at, r.horizon_s, r.radius_m_80, r.radius_m_95, o.error_m FROM outcomes o "
            "JOIN route_predictions r ON r.id = o.score_id WHERE o.error_m IS NOT NULL AND r.model_version = $1 "
            f"AND r.made_at >= {since}", route_version) if route_version else []
        dark = await con.fetch(
            "SELECT s.made_at, o.target, s.p, o.label FROM outcomes o JOIN scores s ON s.id = o.score_id "
            "WHERE o.label IS NOT NULL AND s.model_version = $1 "
            f"AND s.made_at >= {since}", godark_version) if godark_version else []
    finally:
        await con.close()
    return (pd.DataFrame([dict(r) for r in route]), pd.DataFrame([dict(r) for r in dark]))


def write_champions(models_dir: Path, champions: dict) -> None:
    tmp = models_dir / "champions.json.tmp"
    tmp.write_text(json.dumps(champions, indent=1))
    os.replace(tmp, models_dir / "champions.json")


def recalibrate(models_dir: Path, url: str, hours: float = 48, apply: bool = False, log=print) -> dict:
    champs = json.loads((models_dir / "champions.json").read_text())
    version = {t: json.loads((models_dir / f / "model.json").read_text())["version"]
               for t, f in champs.items() if t in ("route", "godark") and (models_dir / f / "model.json").exists()}
    route_rows, dark_rows = asyncio.run(fetch_rows(url, version.get("route"), version.get("godark"), hours))
    out = {"champions_before": dict(champs), "rows": {"route": len(route_rows), "godark": len(dark_rows)}}
    new = dict(champs)
    if len(route_rows):
        fit = fit_route(route_rows)
        out["route"] = fit
        if any(f["keep"] for f in fit.values()):
            dst = models_dir / next_version(champs["route"])
            if not dst.exists():
                write_route(models_dir / champs["route"], dst, fit, f"{len(route_rows)} graded rows, {hours} h")
            new["route"] = dst.name
    if len(dark_rows):
        fit = fit_godark(dark_rows)
        out["godark"] = fit
        if any(f["keep"] for f in fit.values()):
            dst = models_dir / next_version(champs["godark"])
            if not dst.exists():
                write_godark(models_dir / champs["godark"], dst, fit, f"{len(dark_rows)} graded rows, {hours} h")
            new["godark"] = dst.name
    out["champions_after"] = new
    out["changed"] = {t: new[t] for t in new if new[t] != champs.get(t)}
    if out["changed"] and apply:
        write_champions(models_dir, new)
    log(f"recalibrate: rows {out['rows']}, changed {out['changed'] or 'nothing'}{'' if apply else ' (dry run)'}")
    return out


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="python -m ml.core.recalibrate", description=__doc__.split("\n\n")[0])
    ap.add_argument("--models-dir", type=Path, default=Path(os.getenv("PREDICT_MODEL_DIR", "/opt/dvm/models")))
    ap.add_argument("--hours", type=float, default=48)
    ap.add_argument("--apply", action="store_true", help="rewrite champions.json (else only report and write folders)")
    a = ap.parse_args(argv)
    from ml.core import env  # noqa: F401  (loads the repo .env)
    url = os.environ["TIGER_DATABASE_URL"]
    print(json.dumps(recalibrate(a.models_dir, url, a.hours, a.apply), indent=1, default=str))


if __name__ == "__main__":
    main()
