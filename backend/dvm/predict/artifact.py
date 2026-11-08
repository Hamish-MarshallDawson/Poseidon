"""Model artifacts the live predictor loads (#121), and the built-in baselines it runs when no champion exists.

The backend never imports `ml/`. An artifact is a directory with `model.json` and LightGBM text dumps:

    {
      "target": "route" | "godark",
      "model": "lgbm-offset",              # family, free text
      "version": "route-lgbm-20261108a",   # written to the ledger as model_version; unique per run
      "kind": "lightgbm",                  # or "baseline" (no files: the built-in baseline of that target)
      "feature_version": "f1",             # must equal dvm.predict.features.FEATURE_VERSION
      "features": ["lat", "lon", ...],     # names from features.FEATURE_NAMES, in the model's column order
      "horizons_s": [3600, 10800, 21600, 86400],
      "data_hash": "...", "metrics": {...},
      "heads": {
        # route: LightGBM regressors for the east and north offset (metres) from the baseline point, and the
        # split-conformal radii (metres): a number each, or per speed band
        # {"sog_edges_kn": [2, 8, 15], "r": [4 values]} (band i is edges[i-1] <= sog < edges[i])
        "3600": {"east": "h3600_east.txt", "north": "h3600_north.txt", "radius_m_80": 900, "radius_m_95": 2100},
        # godark: a LightGBM classifier (raw probability out) and optional isotonic calibration, as the
        # increasing breakpoints of a piecewise-linear map from the model's output to a probability
        "3600": {"model": "h3600.txt", "calibration": {"x": [0, 0.1, 1], "y": [0, 0.04, 0.9]}}
      }
    }

Champions: `<PREDICT_MODEL_DIR>/champions.json` maps a target to an artifact directory name under PREDICT_MODEL_DIR,
e.g. {"route": "route-lgbm-20261108a", "godark": "godark-lgbm-20261108a"}. ml-loop's registry writes it on promotion.
"""
from __future__ import annotations

import json
import logging
import math
from bisect import bisect_left, bisect_right
from pathlib import Path
from typing import Mapping, Optional

from dvm.predict import features as F

log = logging.getLogger(__name__)

ROUTE_HORIZONS_S = (3600, 3 * 3600, 6 * 3600, 24 * 3600)
GODARK_HORIZONS_S = (3600, 6 * 3600, 24 * 3600)
ROUTE_BASELINE_VERSION = "baseline-dr-v1"
GODARK_BASELINE_VERSION = "baseline-rate-v1"


class ArtifactError(ValueError):
    pass


def _radius(spec, sog: Optional[float]) -> float:
    if isinstance(spec, (int, float)):
        return float(spec)
    edges = spec["sog_edges_kn"]
    return float(spec["r"][bisect_right(edges, sog or 0.0)])


class RouteBaseline:
    """Dead reckoning (features.baseline_point). The radius is a heuristic, not calibrated: 300 m plus 20% (80%) or
    600 m plus 40% (95%) of the distance run at the last speed, at least 1 km per hour for stopped ships. The graders
    measure its real coverage, and a trained model's conformal radii replace it."""

    target, kind, version, feature_version = "route", "baseline", ROUTE_BASELINE_VERSION, F.FEATURE_VERSION
    horizons_s = ROUTE_HORIZONS_S

    def predict(self, fix: Mapping, feats: Optional[Mapping]) -> list[dict]:
        out = []
        for h in self.horizons_s:
            blat, blon = F.baseline_point(fix, h)
            run = 0.0 if F.is_stopped(fix) else fix["sog_kn"] * F.KN_MS * h
            floor = 1000 * h / 3600 if F.is_stopped(fix) else 0
            out.append({"horizon_s": h, "lat": blat, "lon": blon, "base_lat": blat, "base_lon": blon,
                        "radius_m_80": max(300 + 0.2 * run, floor), "radius_m_95": max(600 + 0.4 * run, 2 * floor)})
        return out


class GodarkBaseline:
    """The base rate: p = 1 - exp(-rate * h), with `rate` deliberate-candidate gaps per moving Class A ship-hour,
    measured by the predictor from the recent gaps table on each cycle."""

    target, kind, version, feature_version = "godark", "baseline", GODARK_BASELINE_VERSION, F.FEATURE_VERSION
    horizons_s = GODARK_HORIZONS_S

    def __init__(self, rate_per_h: float = 0.0):
        self.rate_per_h = rate_per_h

    def predict(self, feats: Mapping) -> dict[int, float]:
        return {h: 1 - math.exp(-self.rate_per_h * h / 3600) for h in self.horizons_s}


class _Lgbm:
    def __init__(self, path: Path, meta: dict):
        try:
            import lightgbm  # noqa: PLC0415 - only needed once a trained champion exists
        except ImportError as e:   # pragma: no cover
            raise ArtifactError("lightgbm is not installed") from e
        self.meta, self.path = meta, path
        self.version, self.feature_version = meta["version"], meta["feature_version"]
        self.features = meta["features"]
        self.horizons_s = tuple(int(h) for h in meta["horizons_s"])
        if self.feature_version != F.FEATURE_VERSION:
            raise ArtifactError(f"{path}: feature_version {self.feature_version}, backend has {F.FEATURE_VERSION}")
        unknown = set(self.features) - set(F.FEATURE_NAMES)
        if unknown:
            raise ArtifactError(f"{path}: unknown features {sorted(unknown)}")
        self._booster = lambda name: lightgbm.Booster(model_file=str(path / name))
        missing = [str(h) for h in self.horizons_s if str(h) not in meta["heads"]]
        if missing:
            raise ArtifactError(f"{path}: no heads for horizons {missing}")

    def _row(self, feats: Mapping):
        import numpy as np  # noqa: PLC0415
        return np.array([F.vector(feats, self.features)], dtype=float)


class RouteModel(_Lgbm):
    target, kind = "route", "lightgbm"

    def __init__(self, path: Path, meta: dict):
        super().__init__(path, meta)
        self.heads = {}
        for h in self.horizons_s:
            spec = meta["heads"][str(h)]
            self.heads[h] = (self._booster(spec["east"]), self._booster(spec["north"]),
                             _norm_radius(spec["radius_m_80"]), _norm_radius(spec["radius_m_95"]))

    def predict(self, fix: Mapping, feats: Mapping) -> list[dict]:
        x, out = self._row(feats), []
        for h, (be, bn, r80, r95) in self.heads.items():
            blat, blon = F.baseline_point(fix, h)
            lat, lon = F.apply_offset(blat, blon, float(be.predict(x)[0]), float(bn.predict(x)[0]))
            out.append({"horizon_s": h, "lat": lat, "lon": lon, "base_lat": blat, "base_lon": blon,
                        "radius_m_80": _radius(r80, fix.get("sog_kn")), "radius_m_95": _radius(r95, fix.get("sog_kn"))})
        return out


def _norm_radius(spec):
    """A radius spec as _radius reads it: a number, or {"sog_edges_kn": [...], "r": [one more than edges]}."""
    if isinstance(spec, (int, float)) and not isinstance(spec, bool):
        return float(spec)
    if isinstance(spec, dict) and isinstance(spec.get("sog_edges_kn"), list) and isinstance(spec.get("r"), list) \
            and len(spec["r"]) == len(spec["sog_edges_kn"]) + 1:
        return spec
    raise ArtifactError(f"bad radius {spec!r}: a number or {{'sog_edges_kn': [...], 'r': [len(edges) + 1]}}")


class GodarkModel(_Lgbm):
    target, kind = "godark", "lightgbm"

    def __init__(self, path: Path, meta: dict):
        super().__init__(path, meta)
        self.heads = {}
        for h in self.horizons_s:
            spec = meta["heads"][str(h)]
            cal = spec.get("calibration")
            if cal and (len(cal["x"]) != len(cal["y"]) or len(cal["x"]) < 2
                        or any(a > b for a, b in zip(cal["x"], cal["x"][1:]))):
                raise ArtifactError(f"{path}: calibration for {h} must be increasing x with matching y")
            self.heads[h] = (self._booster(spec["model"]), cal)

    def predict(self, feats: Mapping) -> dict[int, float]:
        x = self._row(feats)
        return {h: calibrate(float(b.predict(x)[0]), cal) for h, (b, cal) in self.heads.items()}


def calibrate(raw: float, cal: Optional[Mapping]) -> float:
    """Piecewise-linear map through the isotonic breakpoints, clamped at both ends; identity without one."""
    if not cal:
        return min(1.0, max(0.0, raw))
    xs, ys = cal["x"], cal["y"]
    if raw <= xs[0]:
        return float(ys[0])
    if raw >= xs[-1]:
        return float(ys[-1])
    i = bisect_left(xs, raw)
    x0, x1, y0, y1 = xs[i - 1], xs[i], ys[i - 1], ys[i]
    return float(y0 + (y1 - y0) * (raw - x0) / (x1 - x0)) if x1 > x0 else float(y1)


def load(path: Path):
    """The model in an artifact directory. Raises ArtifactError if it isn't one the backend can run."""
    try:
        meta = json.loads((path / "model.json").read_text())
    except (OSError, ValueError) as e:
        raise ArtifactError(f"{path}: cannot read model.json: {e}") from e
    target, kind = meta.get("target"), meta.get("kind", "lightgbm")
    if kind == "baseline":
        return RouteBaseline() if target == "route" else GodarkBaseline()
    try:
        if target == "route":
            return RouteModel(path, meta)
        if target == "godark":
            return GodarkModel(path, meta)
    except (KeyError, TypeError) as e:
        raise ArtifactError(f"{path}: model.json is missing {e}") from e
    except Exception as e:  # noqa: BLE001 - a broken LightGBM file must never stop the predictor
        if isinstance(e, ArtifactError):
            raise
        raise ArtifactError(f"{path}: {type(e).__name__}: {e}") from e
    raise ArtifactError(f"{path}: unknown target {target!r}")


class Champions:
    """The champion per target from <dir>/champions.json, reloaded when the file changes. A missing, broken or
    unloadable champion falls back to the baseline (and says why in `errors`), so the ledger never stops."""

    def __init__(self, model_dir: Optional[Path]):
        self.dir = model_dir
        self._mtime: Optional[float] = None
        self.route = RouteBaseline()
        self.godark = GodarkBaseline()
        self.errors: dict[str, str] = {}

    def refresh(self) -> None:
        if self.dir is None:
            return
        f = self.dir / "champions.json"
        try:
            mtime = f.stat().st_mtime
        except OSError:
            mtime = None
        if mtime == self._mtime:
            return
        self._mtime = mtime
        names = {}
        if mtime is not None:
            try:
                names = json.loads(f.read_text())
            except ValueError as e:
                self.errors = {"champions.json": str(e)}
                return
        self.errors = {}
        rate = self.godark.rate_per_h if isinstance(self.godark, GodarkBaseline) else 0.0
        for target, base in (("route", RouteBaseline()), ("godark", GodarkBaseline(rate))):
            model = base
            if names.get(target):
                try:
                    model = load(self.dir / names[target])
                    if model.target != target:
                        raise ArtifactError(f"{names[target]} is a {model.target} model")
                    log.info("Predictor champion for %s: %s", target, model.version)
                except ArtifactError as e:
                    self.errors[target] = str(e)
                    log.warning("Predictor champion for %s not loaded, using the baseline: %s", target, e)
                    model = base
            setattr(self, target, model)
