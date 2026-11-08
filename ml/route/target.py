"""The route target for ml/core (run, loop, report): `SPEC`.

    ml/.venv/bin/python -m ml.core.run  --target route [--data dma|tiger|dma+tiger|FILE.parquet]
    ml/.venv/bin/python -m ml.core.loop --target route --rounds 3 --dry-run

Data (`--data`): `dma` (default: the Danish archive, every day in /home/aiden/data/poseidon/dma), `dma:N` (the
newest N days), `tiger` (our live AIS exported read-only by `python -m ml.route.tiger`, with our closed gaps),
`dma+tiger`, or a path to an examples Parquet. Examples are cached under /home/aiden/data/poseidon/route/cache,
keyed by the source manifests and the build settings, so the loop builds them once.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

from ml.core.target import TargetSpec
from ml.route import HORIZONS_S, TRAIN_HORIZONS_S, examples
from ml.route.metrics import score as score_frame
from ml.route.model import DEFAULT_CFG, FEATURE_GROUPS, RouteBaseline, RouteLGBM

DATA = Path(os.environ.get("POSEIDON_DATA", "/home/aiden/data/poseidon"))
BUILD = {"step_min": 30, "min_sog_kn": 1.0, "n_synthetic": 5000, "seed": 0, "version": 2}


def source_dir(source: str) -> tuple[str, Path]:
    """("dma" | "tiger", directory): a name with the default directory, or a directory (kind from its files)."""
    if source in ("dma", "tiger"):
        return source, DATA / ("dma" if source == "dma" else "route/tiger")
    d = Path(source).expanduser()
    if (d / "tracks_1m").is_dir():
        return "dma", d
    if (d / "positions.parquet").exists():
        return "tiger", d
    raise ValueError(f"{source!r} is neither dma, tiger, nor a directory with tracks_1m/ or positions.parquet")


def _build(source: str, days: int | None) -> pd.DataFrame:
    kind, d = source_dir(source)
    kw = {k: v for k, v in BUILD.items() if k != "version"}
    if kind == "dma":
        from ml.route import dma_io
        tr, st = dma_io.load(d, days=days)
        return examples.build(tr, st, None, source="dma", gate=True, **kw)
    if kind == "tiger":
        tr, st, gp = (pd.read_parquet(d / f) for f in ("positions.parquet", "statics.parquet", "gaps.parquet"))
        return examples.build(tr, st, gp, source="tiger", gate=True, **kw)
    raise ValueError(f"unknown route data source {source!r}")


def _manifest_key(source: str, days: int | None) -> str:
    kind, d = source_dir(source)
    f = d / "manifest.json"
    man = f.read_text() if f.exists() else ""
    blob = json.dumps({"src": kind, "days": days, "build": BUILD, "man": hashlib.sha256(man.encode()).hexdigest()})
    return hashlib.sha256(blob.encode()).hexdigest()[:12]


def load_source(source: str, days: int | None = None) -> pd.DataFrame:
    kind, d = source_dir(source)
    root = Path(os.environ["ROUTE_CACHE"]) if os.environ.get("ROUTE_CACHE") else d.parent / "route" / "cache"
    cache = root / f"{kind}{'-' + str(days) if days else ''}-{_manifest_key(source, days)}.parquet"
    if cache.exists():
        return pd.read_parquet(cache)
    df = _build(source, days)
    cache.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(cache, index=False)
    return df


_GROUPS = list(FEATURE_GROUPS)
CONFIG_SCHEMA = {
    "type": "object", "required": ["model", "seed"], "additionalProperties": False,
    "properties": {
        "model": {"type": "string", "enum": ["baseline", "lgbm"]},
        "seed": {"type": "integer", "minimum": 0, "maximum": 1_000_000},
        "feature_groups": {"type": "array", "items": {"type": "string", "enum": _GROUPS}, "minItems": 1,
                           "uniqueItems": True},
        # "track" scores better but needs backend support (artifact.py reads east/north heads only)
        "frame": {"type": "string", "enum": ["enu"]},
        "objective": {"type": "string", "enum": ["l1", "l2", "huber"]},
        "num_leaves": {"type": "integer", "minimum": 7, "maximum": 255},
        "learning_rate": {"type": "number", "minimum": 0.01, "maximum": 0.3},
        "n_estimators": {"type": "integer", "minimum": 50, "maximum": 1500},
        "min_child_samples": {"type": "integer", "minimum": 10, "maximum": 1000},
        "feature_fraction": {"type": "number", "minimum": 0.3, "maximum": 1.0},
        "bagging_fraction": {"type": "number", "minimum": 0.3, "maximum": 1.0},
        "lambda_l2": {"type": "number", "minimum": 0, "maximum": 100},
        "calib_frac": {"type": "number", "minimum": 0.1, "maximum": 0.4},
        "real_gap_weight": {"type": "number", "minimum": 0, "maximum": 20},
        "sample_weight": {"type": "string", "enum": ["none", "recent"]},
        "train_window_days": {"type": "integer", "minimum": 1, "maximum": 30},
    }}
_TUNABLE = set(CONFIG_SCHEMA["properties"])
DEFAULT_CONFIG = {k: v for k, v in DEFAULT_CFG.items() if k in _TUNABLE}


class RouteTarget(TargetSpec):
    name = "route"
    horizons_s = list(TRAIN_HORIZONS_S)
    primary_horizons_s = list(HORIZONS_S)          # the contract's 1, 3, 6 and 24 h
    statistic = "median"
    loss_name, loss_unit = "error_m", "m"
    strata = ["type_group", "speed_class"]
    baseline = "baseline"
    models = {"baseline": RouteBaseline, "lgbm": RouteLGBM}
    default_config = DEFAULT_CONFIG
    config_schema = CONFIG_SCHEMA
    group_by_ship = False
    report_notes = [
        "Route error is the great-circle distance from the predicted point to where the ship really was; the "
        "baseline is dead reckoning at the last course and speed (a rhumb line), or staying put if stopped.",
        "Cases are moving ships (>= 1 kn, not anchored or moored) at a fix, every 30 min per ship. Truth is the "
        "position at the horizon, interpolated between fixes no more than 5 min away.",
        "Held-out set: the newest block of time, never trained on; training labels end a full 24 h before it.",
        "Danish waters (Danish Maritime Authority AIS archive, complete tracks); results elsewhere are not implied.",
    ]
    dry_run_proposals = [
        {"config": {**DEFAULT_CONFIG, "objective": "huber"}, "rationale": "dry run: robust loss for heavy tails"},
        {"config": {**DEFAULT_CONFIG, "feature_groups": [g for g in _GROUPS if g != "position"]},
         "rationale": "dry run: no latitude/longitude, so the model must generalise outside the lanes it saw"},
        {"config": {**DEFAULT_CONFIG, "num_leaves": 127, "n_estimators": 800, "learning_rate": 0.03},
         "rationale": "dry run: a bigger boosted model"},
        {"config": {**DEFAULT_CONFIG, "sample_weight": "recent"}, "rationale": "dry run: weight recent cases more"},
        {"config": {**DEFAULT_CONFIG, "feature_groups": ["kinematics"]},
         "rationale": "dry run: last-fix kinematics only, which should lose to the full feature set"},
    ]

    def load_examples(self, cfg, data):
        data = data or "dma"
        if data.endswith(".parquet"):
            return pd.read_parquet(data)
        parts = []
        for src in data.split("+"):
            name, _, days = src.rpartition(":") if src.rsplit(":", 1)[-1].isdigit() else (src, "", "")
            parts.append(load_source(name, int(days) if days else None))
        df = pd.concat(parts, ignore_index=True) if len(parts) > 1 else parts[0]
        return df.sort_values(["as_of", "case_id"], kind="stable").reset_index(drop=True)

    def score(self, examples_df, preds):
        return score_frame(examples_df, preds, strata=tuple(self.strata))

    def summarise(self, scored):
        return {str(int(h)): {"n": int(len(g)), "median_m": float(g["loss"].median()),
                              "p90_m": float(g["loss"].quantile(0.9)), "cov80": float(g["in80"].mean()),
                              "cov95": float(g["in95"].mean()), "median_radius_m_80": float(g["radius_m_80"].median())}
                for h, g in scored.groupby("horizon_s")}

    def calibration(self, scored):
        out = []
        for h, g in scored.groupby("horizon_s"):
            for col, nom in (("in80", 0.80), ("in95", 0.95)):
                out.append({"name": f"{int(nom * 100)}% radius coverage", "horizon_s": int(h),
                            "value": float(g[col].mean()), "nominal": nom, "tol": 0.05})
        return out

    def sanity(self, summary):
        # a moving ship (>= 1 kn) covers >= 900 m in 30 min; a median error under 5% of that at any horizon means
        # the truth leaked into the features
        return [f"{h}s median error {v['median_m']:.0f} m is implausibly small" for h, v in summary.items()
                if v["n"] >= 100 and v["median_m"] < 0.05 * 1852 * int(h) / 3600]


SPEC = RouteTarget()
