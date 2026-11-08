"""What a prediction target plugs into the loop. ml/route, ml/godark (and the toy target in ml/core/toy.py) each
expose one `SPEC = MyTarget()` in `ml/<target>/target.py`; `get_target("route")` imports it.

The loop never looks inside a target's data: it needs case ids, ships and times (for splits), a per-case loss
(lower is better, for the paired bootstrap and the promotion rule), strata, and calibration checks.
"""
from __future__ import annotations

import importlib
from typing import Any

import pandas as pd

# Columns every examples frame has. One row per case (a ship at a time `as_of`); more columns are the target's own
# (features, truth). `as_of` is epoch ms: features use data up to it, truth comes after it.
CASE_COLS = ["case_id", "mmsi", "as_of"]
# Columns every per-case score frame has (long: one row per case and horizon), plus the target's strata columns.
SCORE_COLS = ["case_id", "mmsi", "as_of", "horizon_s", "loss"]


class TargetSpec:
    name: str = ""
    horizons_s: list[int] = []            # every horizon the models predict
    primary_horizons_s: list[int] = []    # the horizons the promotion rule tests
    statistic: str = "median"             # "median" (route error, heavy tails) or "mean" (log loss, Brier)
    loss_name: str = "loss"               # what `loss` is, for the report, e.g. "error_m" or "log_loss"
    loss_unit: str = ""                   # e.g. "m"; empty for unitless
    strata: list[str] = []                # per-case columns the promotion rule checks one value at a time
    baseline: str = "baseline"            # model name of the reference every run is scored against (skill)
    default_config: dict[str, Any] = {}   # what `run` uses with no --config and the loop's first run
    config_schema: dict[str, Any] = {}    # JSON Schema; Gemini proposals and --config files must validate
    group_by_ship: bool = False           # keep held-out ships out of training entirely
    models: dict[str, type] = {}          # model name -> class implementing ml.core.registry.Model

    def load_examples(self, cfg: dict, data: str | None) -> pd.DataFrame:
        """Build the examples frame (CASE_COLS first) from `data` (a path or URL the target understands; None means
        its default). Must be deterministic for the same data and cfg: case ids are what the held-out set freezes."""
        raise NotImplementedError

    def score(self, examples: pd.DataFrame, preds: pd.DataFrame) -> pd.DataFrame:
        """Join a model's predictions (case_id, horizon_s, outputs) to the truth in `examples` and return SCORE_COLS
        plus `self.strata` plus any extra columns `summarise` and `calibration` need. Cases without truth at a
        horizon are left out (not scored as zero)."""
        raise NotImplementedError

    def summarise(self, scored: pd.DataFrame) -> dict[str, dict[str, float]]:
        """Headline metrics per horizon, keyed by str(horizon_s): e.g. {"3600": {"median_m": .., "p90_m": .., "n": ..}}."""
        raise NotImplementedError

    def calibration(self, scored: pd.DataFrame) -> list[dict]:
        """Calibration checks: [{"name", "horizon_s", "value", "nominal", "tol"}]. The promotion rule needs
        |value - nominal| <= tol (default 0.05) for every primary horizon. Empty if the target has none."""
        return []

    def sanity(self, summary: dict) -> list[str]:
        """Reasons a run's numbers are too good to be true (leakage); any reason fails the run."""
        return []


def get_target(name: str) -> TargetSpec:
    """`route` -> ml.route.target.SPEC; `toy` -> ml.core.toy.SPEC; `pkg.module:ATTR` for anything else."""
    if ":" in name:
        mod, attr = name.split(":", 1)
    elif name == "toy":
        mod, attr = "ml.core.toy", "SPEC"
    else:
        mod, attr = f"ml.{name}.target", "SPEC"
    return getattr(importlib.import_module(mod), attr)
