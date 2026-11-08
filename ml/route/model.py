"""Route models: the dead-reckoning baseline and a LightGBM corrector per horizon, both with split-conformal radii.

Interface: `ml.core.registry.Model` (`fit(train_df, cfg)`, `predict(df)` long, `save(dir) -> dict`, `load(dir)`).
Input is the wide examples frame from examples.py. Output: one row per case and horizon with `case_id, horizon_s,
pred_lat, pred_lon, radius_m_80, radius_m_95, base_lat, base_lon`.

The artifact is what `backend/dvm/predict/artifact.py` loads, with no ml/ import: per horizon a pair of LightGBM text
dumps for the east and north offset (metres) of the ship from `features.baseline_point(fix, h)`, and conformal
radii per speed band (`{"sog_edges_kn": [5, 12], "r": [3 values]}`). Predictions start from the last fix: horizon h
means fix time + h, as in the backend.

Option `frame: "track"` learns the offset along and across the last course instead (a turn to port looks the same
on any heading). It scores better (see ml/route/README.md) but the backend loader reads only east/north heads, so a
track-frame artifact writes `along`/`cross` heads that the current backend refuses (it then falls back to its
baseline, never mis-applies them). The default is `enu` until the backend supports the frame.

Radii are Mondrian split-conformal per horizon and speed band on a calibration slice that comes after the fitting
slice in time (embargo = the horizon), so they are honest for the next stretch of time.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from ml.core.registry import Model
from ml.route import HORIZONS_S, TRAIN_HORIZONS_S
from ml.route.examples import SPEED_EDGES_KN
from ml.route.geo import apply_enu_offset, enu_offset_m, haversine_m

from dvm.predict import features as F  # noqa: E402

MIN_BAND_N = 50                           # smaller speed bands use the horizon's pooled quantile
MIN_FIT_N = 500                           # fewer fitting rows: the horizon is not trained
_W = lambda w: [n for n in F.FEATURE_NAMES if n.startswith(f"w{w}_")]   # noqa: E731
FEATURE_GROUPS = {
    "kinematics": ["sog_kn", "cog_sin", "cog_cos", "ve_kn", "vn_kn", "heading_cog_diff_deg", "nav_status",
                   "anchored", "is_class_a"],
    "position": ["lat", "lon"],
    "history_30m": _W("30m"), "history_2h": _W("2h"), "history_6h": _W("6h"),
    "static": ["ship_type", "length_m", "draught_m"],
    "time": ["hour_sin", "hour_cos"],
}
# age_s is never a feature: training cases start at a fix (age 0); live predictions start from the last fix too
DEFAULT_CFG = {
    "model": "lgbm", "seed": 0,
    "horizons_s": list(TRAIN_HORIZONS_S),     # the contract's 1/3/6/24 h plus 30 min, 2 h, 12 h for gap lengths
    "feature_groups": list(FEATURE_GROUPS),
    "frame": "enu",                           # enu (backend format) | track
    "objective": "l1",                        # l1 | l2 | huber
    "num_leaves": 63, "learning_rate": 0.05, "n_estimators": 400, "min_child_samples": 50,
    "feature_fraction": 0.8, "bagging_fraction": 0.8, "lambda_l2": 1.0,
    "calib_frac": 0.2,                        # newest share of each horizon's training span kept for the radii
    "real_gap_weight": 1.0,                   # sample weight of real dark-ship cases relative to track cases
    "sample_weight": "none",                  # none | recent
    "num_threads": 4,
}


def band(sog) -> np.ndarray:
    return np.digitize(np.nan_to_num(np.asarray(sog, float), nan=0.0), SPEED_EDGES_KN)


def conformal_q(scores: np.ndarray, level: float) -> float:
    """Split-conformal quantile with the finite-sample correction: the ceil((n+1) level)-th smallest score."""
    n = len(scores)
    if n == 0:
        return float("nan")
    k = int(np.ceil((n + 1) * level))
    return float(np.sort(scores)[min(k, n) - 1])


def course_rad(df: pd.DataFrame) -> np.ndarray:
    """The baseline's course (cog, else heading; 0 for a stopped ship), as features.baseline_point uses it."""
    cog, hdg = df["fix_cog"].to_numpy(float), df["fix_hdg"].to_numpy(float)
    ok_c = (cog >= 0) & (cog < 360)
    c = np.where(ok_c, cog, np.where((hdg >= 0) & (hdg < 360), hdg, 0.0))
    return np.radians(np.where(df["stopped"].to_numpy(bool), 0.0, c))


def fix_dict(r) -> dict:
    nan = lambda v: None if v is None or (isinstance(v, float) and np.isnan(v)) else v   # noqa: E731
    return {"lat": r.fix_lat, "lon": r.fix_lon, "sog_kn": nan(r.fix_sog), "cog_deg": nan(r.fix_cog),
            "heading_deg": nan(r.fix_hdg), "nav_status": None if nan(r.fix_nav) is None else int(r.fix_nav)}


class _Route(Model):
    target = "route"
    name = ""

    def __init__(self):
        self.cfg: dict = dict(DEFAULT_CFG)
        self.features: list[str] = []
        self.horizons: list[int] = []
        self.boosters: dict[int, tuple] = {}
        self.radius: dict[int, dict] = {}       # h -> {"r80": [per band], "r95": [...], "n": [...]}
        self.meta: dict = {}

    # ---- frames ------------------------------------------------------------------------------------------------
    def _to_frame(self, df, east, north):
        if self.cfg["frame"] != "track":
            return east, north
        th = course_rad(df)
        return east * np.sin(th) + north * np.cos(th), east * np.cos(th) - north * np.sin(th)

    def _from_frame(self, df, a, b):
        if self.cfg["frame"] != "track":
            return a, b
        th = course_rad(df)
        return a * np.sin(th) + b * np.cos(th), a * np.cos(th) - b * np.sin(th)

    # ---- fit ---------------------------------------------------------------------------------------------------
    def fit(self, train_df: pd.DataFrame, cfg: dict) -> "_Route":
        self.cfg = {**DEFAULT_CFG, **(cfg or {})}
        self.horizons, self.boosters, self.radius = [], {}, {}
        self.features = [f for f in F.FEATURE_NAMES if any(f in FEATURE_GROUPS[g] for g in self.cfg["feature_groups"])]
        self.meta = {"n_fit": {}, "n_calib": {}, "calib_start": {}, "train_from": int(train_df["as_of"].min()),
                     "train_to": int(train_df["as_of"].max())}
        for h in sorted(int(x) for x in self.cfg["horizons_s"]):
            if f"truth_lat_{h}" not in train_df:
                continue
            d = train_df[train_df[f"truth_lat_{h}"].notna()]
            if d.empty:
                continue
            lo, hi = int(d["as_of"].min()), int(d["as_of"].max())
            cut = hi - int((hi - lo) * self.cfg["calib_frac"])
            fit = d[d["as_of"] + h * 1000 <= cut]               # embargo: no fitting truth inside the calib slice
            cal = d[d["as_of"] >= cut]
            self.meta["n_fit"][h], self.meta["n_calib"][h], self.meta["calib_start"][h] = len(fit), len(cal), cut
            if len(cal) < MIN_BAND_N or (self.trains and len(fit) < MIN_FIT_N):
                continue
            if self.trains:
                self.boosters[h] = self._fit_h(fit, h)
            self.horizons.append(h)
            self.radius[h] = self._calibrate(cal, h)
        if not self.horizons:
            raise ValueError(f"no horizon has enough data: {self.meta}")
        return self

    trains = True

    def _weights(self, d):
        w = np.where(d["kind"].to_numpy() == "real_gap", float(self.cfg["real_gap_weight"]), 1.0)
        if self.cfg.get("sample_weight") == "recent":
            t = d["as_of"].to_numpy(float)
            w = w * (0.5 + (t - t.min()) / max(1.0, t.max() - t.min()))
        return w

    def _fit_h(self, d: pd.DataFrame, h: int):
        import lightgbm as lgb
        east, north = enu_offset_m(d[f"base_lat_{h}"].to_numpy(float), d[f"base_lon_{h}"].to_numpy(float),
                                   d[f"truth_lat_{h}"].to_numpy(float), d[f"truth_lon_{h}"].to_numpy(float))
        ya, yb = self._to_frame(d, east, north)
        params = {"objective": self.cfg["objective"], "num_leaves": int(self.cfg["num_leaves"]),
                  "learning_rate": float(self.cfg["learning_rate"]),
                  "min_child_samples": int(self.cfg["min_child_samples"]),
                  "feature_fraction": float(self.cfg["feature_fraction"]),
                  "bagging_fraction": float(self.cfg["bagging_fraction"]), "bagging_freq": 1,
                  "lambda_l2": float(self.cfg["lambda_l2"]), "seed": int(self.cfg["seed"]), "verbose": -1,
                  "num_threads": int(self.cfg["num_threads"]), "deterministic": True, "force_col_wise": True}
        if self.cfg["objective"] == "huber":
            params["alpha"] = float(np.quantile(np.hypot(ya, yb), 0.9)) or 1.0
        X = d[self.features].to_numpy(np.float64)
        w = self._weights(d)
        return tuple(lgb.train(params, lgb.Dataset(X, y, weight=w, feature_name=self.features, free_raw_data=True),
                               int(self.cfg["n_estimators"])) for y in (ya, yb))

    def _calibrate(self, cal: pd.DataFrame, h: int) -> dict:
        lat, lon = self._point(cal, h)
        err = haversine_m(lat, lon, cal[f"truth_lat_{h}"].to_numpy(float), cal[f"truth_lon_{h}"].to_numpy(float))
        b = band(cal["fix_sog"])
        pooled = (conformal_q(err, 0.8), conformal_q(err, 0.95))
        r = {"r80": [], "r95": [], "n": [], "pooled": list(pooled), "n_pooled": int(len(err))}
        for k in range(len(SPEED_EDGES_KN) + 1):
            e = err[b == k]
            ok = len(e) >= MIN_BAND_N
            r["r80"].append(round(conformal_q(e, 0.8) if ok else pooled[0], 1))    # 0.1 m: as saved
            r["r95"].append(round(conformal_q(e, 0.95) if ok else pooled[1], 1))
            r["n"].append(int(len(e)))
        return r

    # ---- predict -----------------------------------------------------------------------------------------------
    def _offset(self, df, h):
        if h not in self.boosters:
            z = np.zeros(len(df))
            return z, z
        X = df[self.features].to_numpy(np.float64)
        a, b = (bst.predict(X) for bst in self.boosters[h])
        return self._from_frame(df, a, b)

    def _point(self, df, h):
        east, north = self._offset(df, h)
        return apply_enu_offset(df[f"base_lat_{h}"].to_numpy(float), df[f"base_lon_{h}"].to_numpy(float), east, north)

    def predict(self, df: pd.DataFrame) -> pd.DataFrame:
        out = []
        b = band(df["fix_sog"])
        for h in self.horizons:
            lat, lon = self._point(df, h)
            out.append(pd.DataFrame({"case_id": df["case_id"].to_numpy(), "horizon_s": h, "pred_lat": lat,
                                     "pred_lon": lon, "radius_m_80": np.asarray(self.radius[h]["r80"])[b],
                                     "radius_m_95": np.asarray(self.radius[h]["r95"])[b],
                                     "base_lat": df[f"base_lat_{h}"].to_numpy(float),
                                     "base_lon": df[f"base_lon_{h}"].to_numpy(float)}))
        return pd.concat(out, ignore_index=True)

    def predict_at(self, df: pd.DataFrame, secs) -> pd.DataFrame:
        """Prediction at any time after the last fix (a gap's length): the offset and radii are interpolated
        linearly between 0 and the trained horizons and held beyond the longest (the radius grows in proportion).
        Used for reappearance grading; the backend predicts only at the artifact's horizons."""
        secs = np.asarray(secs, float)
        grid = np.array([0.0, *self.horizons])
        e = np.minimum(secs, grid[-1])
        k = np.clip(np.searchsorted(grid, e, side="right") - 1, 0, len(grid) - 2)
        w = (e - grid[k]) / (grid[k + 1] - grid[k])
        offs = [(np.zeros(len(df)), np.zeros(len(df)))] + [self._offset(df, h) for h in self.horizons]
        east = np.choose(k, [o[0] for o in offs]) * (1 - w) + np.choose(k + 1, [o[0] for o in offs]) * w
        north = np.choose(k, [o[1] for o in offs]) * (1 - w) + np.choose(k + 1, [o[1] for o in offs]) * w
        b = band(df["fix_sog"])
        rad = {}
        for lvl in ("r80", "r95"):
            tab = np.vstack([np.zeros(len(SPEED_EDGES_KN) + 1)] + [np.asarray(self.radius[h][lvl]) for h in self.horizons])
            r = tab[k, b] * (1 - w) + tab[k + 1, b] * w
            rad[lvl] = np.where(secs > grid[-1], tab[-1, b] * secs / grid[-1], r)
        base = np.array([F.baseline_point(fix_dict(r), s) for r, s in zip(df.itertuples(index=False), secs)])
        lat, lon = apply_enu_offset(base[:, 0], base[:, 1], east, north)
        return pd.DataFrame({"case_id": df["case_id"].to_numpy(), "secs": secs, "pred_lat": lat, "pred_lon": lon,
                             "radius_m_80": rad["r80"], "radius_m_95": rad["r95"], "base_lat": base[:, 0],
                             "base_lon": base[:, 1]})

    # ---- artifact ----------------------------------------------------------------------------------------------
    def _radius_spec(self, h, lvl):
        return {"sog_edges_kn": list(SPEED_EDGES_KN), "r": [round(float(x), 1) for x in self.radius[h][lvl]]}

    def save(self, dir: Path) -> dict:
        dir = Path(dir)
        heads = {}
        for h in self.horizons:
            spec = {"radius_m_80": self._radius_spec(h, "r80"), "radius_m_95": self._radius_spec(h, "r95"),
                    "radius_n": self.radius[h]["n"]}
            if h in self.boosters:
                a, b = ("east", "north") if self.cfg["frame"] != "track" else ("along", "cross")
                for key, bst in zip((a, b), self.boosters[h]):
                    spec[key] = f"h{h}_{key}.txt"
                    bst.save_model(str(dir / spec[key]))
            heads[str(h)] = spec
        live = [h for h in self.horizons if h in HORIZONS_S]
        return {"kind": "lightgbm" if self.trains else "baseline", "feature_version": F.FEATURE_VERSION,
                "features": self.features, "horizons_s": live, "heads": {str(h): heads[str(h)] for h in live},
                "all_heads": heads, "all_horizons_s": self.horizons, "frame": self.cfg["frame"],
                "route_cfg": self.cfg, "fit_meta": self.meta,
                "about": "east/north offset (m) from features.baseline_point(fix, h); radii are split-conformal "
                         "per speed band on a later calibration slice"}

    @classmethod
    def load(cls, dir: Path) -> "_Route":
        import lightgbm as lgb
        dir = Path(dir)
        spec = json.loads((dir / "model.json").read_text())
        m = cls()
        m.cfg = {**DEFAULT_CFG, **spec.get("route_cfg", {})}
        m.features = spec["features"]
        m.horizons = [int(h) for h in spec.get("all_horizons_s", spec["horizons_s"])]
        m.meta = spec.get("fit_meta", {})
        a, b = ("east", "north") if m.cfg["frame"] != "track" else ("along", "cross")
        for h, s in spec.get("all_heads", spec["heads"]).items():
            m.radius[int(h)] = {"r80": s["radius_m_80"]["r"], "r95": s["radius_m_95"]["r"]}
            if a in s:
                m.boosters[int(h)] = (lgb.Booster(model_file=str(dir / s[a])), lgb.Booster(model_file=str(dir / s[b])))
        return m


class RouteLGBM(_Route):
    name = "lgbm"


class RouteBaseline(_Route):
    """Dead reckoning (features.baseline_point) with conformal radii fitted the same way as the model's."""
    name = "baseline"
    trains = False


def examples_hash(df: pd.DataFrame) -> str:
    h = hashlib.sha256(pd.util.hash_pandas_object(df["case_id"], index=False).to_numpy().tobytes())
    return h.hexdigest()[:16]
