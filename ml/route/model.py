"""Route models: the dead-reckoning baseline and a LightGBM corrector per horizon, both with split-conformal radii.

Interface (ml-architecture.md): `fit(train_df, cfg) -> self`, `predict(df) -> DataFrame`, `save(dir)`, `load(dir)`,
`name`, `target`. Input rows are examples (see examples.py): features at as_of plus `horizon_s`. Output per row:
`pred_lat, pred_lon, radius_m_80, radius_m_95` (plus `base_lat, base_lon`).

Every prediction starts from the ship's last fix: the effective horizon is `age_s + horizon_s`, so a live
prediction for a ship silent for an hour, asked for +3 h, uses the 4 h correction. Horizons between the trained ones
are interpolated linearly (no correction and no radius at 0 h); beyond the longest one the correction is held and
the radius grows in proportion to time.

LightGBM predicts the offset of the truth from the baseline point in the baseline's own frame (along and across
the last course), so a turn to port looks the same on any heading; offsets are rotated back to east and north.

Radii are Mondrian split-conformal per horizon and speed bucket on a calibration slice that comes after the
fitting slice in time (with an embargo of the horizon), so they hold for the next stretch of time, not the past.

Artifact: `model.json` plus one LightGBM text dump per horizon and component. No pickles.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from ml.route import TRAIN_HORIZONS_S
from ml.route.features import FEATURE_GROUPS, FEATURE_VERSION, baseline_course, baseline_position, feature_names
from ml.route.geo import apply_enu_offset, enu_offset_m

SPEED_BUCKETS_KN = (5.0, 12.0)            # < 5, 5 to 12, >= 12 kn at the last fix
MIN_BUCKET_N = 50                         # smaller buckets use the horizon's pooled quantile
MIN_FIT_N = 500                           # fewer fitting rows: the horizon is not trained
DEFAULT_CFG = {
    "model": "lgbm",                      # lgbm | baseline
    "horizons_s": list(TRAIN_HORIZONS_S),  # the contract's 1/3/6/24 h plus in-between ones for interpolation
    "feature_groups": list(FEATURE_GROUPS),
    "objective": "l1",                    # l1 | l2 | huber
    "num_leaves": 63, "learning_rate": 0.05, "n_estimators": 400, "min_child_samples": 50,
    "feature_fraction": 0.8, "bagging_fraction": 0.8, "lambda_l2": 1.0,
    "calib_frac": 0.2,                    # newest share of the training time span kept for conformal radii
    "real_gap_weight": 1.0,               # sample weight for real dark-ship cases relative to track cases
    "seed": 0, "num_threads": 4,
}


def speed_bucket(sog) -> np.ndarray:
    s = np.nan_to_num(np.asarray(sog, float), nan=0.0)
    return np.digitize(s, SPEED_BUCKETS_KN)          # 0, 1, 2


def conformal_q(scores: np.ndarray, level: float) -> float:
    """Split-conformal quantile with the finite-sample correction: ceil((n+1) level)-th smallest score."""
    n = len(scores)
    if n == 0:
        return float("nan")
    k = int(np.ceil((n + 1) * level))
    return float(np.sort(scores)[min(k, n) - 1]) if k <= n else float(np.max(scores))


def data_hash(df: pd.DataFrame) -> str:
    h = hashlib.sha256()
    for col in ("case_id", "horizon_s"):
        h.update(pd.util.hash_pandas_object(df[col], index=False).to_numpy().tobytes())
    return h.hexdigest()[:16]


class RouteModel:
    target = "route"

    def __init__(self, cfg: dict | None = None):
        self.cfg = {**DEFAULT_CFG, **(cfg or {})}
        self.name = "route_baseline" if self.cfg["model"] == "baseline" else "route_lgbm"
        self.features = [f for g in self.cfg["feature_groups"] for f in FEATURE_GROUPS[g]]
        self.features = [f for f in feature_names() if f in self.features]         # canonical order
        self.horizons = sorted(int(h) for h in self.cfg["horizons_s"])
        self.boosters: dict[int, tuple] = {}
        self.radius: dict[int, dict] = {}
        self.meta: dict = {}

    # ---- geometry -------------------------------------------------------------------------------------------
    @staticmethod
    def _frame(df):
        brg, _, _ = baseline_course(df)
        return np.radians(brg)

    def _offsets_to_frame(self, df, east, north):
        th = self._frame(df)
        along = east * np.sin(th) + north * np.cos(th)
        cross = east * np.cos(th) - north * np.sin(th)              # positive = to starboard
        return along, cross

    def _frame_to_offsets(self, df, along, cross):
        th = self._frame(df)
        return along * np.sin(th) + cross * np.cos(th), along * np.cos(th) - cross * np.sin(th)

    # ---- fit --------------------------------------------------------------------------------------------------
    def fit(self, train_df: pd.DataFrame, cfg: dict | None = None) -> "RouteModel":
        if cfg:
            self.__init__({**self.cfg, **cfg})
        df = train_df[train_df["truth"] == "fixed"] if "truth" in train_df else train_df
        df = df[df["horizon_s"].isin(self.horizons)]
        t_lo, t_hi = int(df["as_of"].min()), int(df["as_of"].max())
        self.meta = {"train_from": t_lo, "train_to": t_hi, "calib_start": {}, "data_hash": data_hash(df),
                     "n_fit": {}, "n_calib": {}}
        for h in self.horizons:
            d = df[df["horizon_s"] == h]
            if d.empty:
                self.meta["n_fit"][h] = self.meta["n_calib"][h] = 0
                continue
            lo, hi = int(d["as_of"].min()), int(d["as_of"].max())
            calib_start = hi - int((hi - lo) * self.cfg["calib_frac"])   # per horizon: its own newest slice
            self.meta["calib_start"][h] = calib_start
            fit = d[d["as_of"] + h * 1000 <= calib_start]                 # embargo: truth before calibration
            cal = d[d["as_of"] >= calib_start]
            self.meta["n_fit"][h], self.meta["n_calib"][h] = len(fit), len(cal)
            if len(cal) < MIN_BUCKET_N or (self.cfg["model"] == "lgbm" and len(fit) < MIN_FIT_N):
                continue                                                  # the data can't support this horizon
            if self.cfg["model"] == "lgbm":
                self.boosters[h] = self._fit_h(fit, h)
            self.radius[h] = self._calibrate(cal, h)
        self.meta["horizons_dropped"] = [h for h in self.horizons if h not in self.radius]
        self.horizons = [h for h in self.horizons if h in self.radius]
        if not self.horizons:
            raise ValueError(f"no horizon has enough data: fit {self.meta['n_fit']}, calib {self.meta['n_calib']}")
        return self

    def _fit_h(self, d: pd.DataFrame, h: int):
        import lightgbm as lgb
        blat, blon = baseline_position(d, h)
        east, north = enu_offset_m(blat, blon, d["true_lat"].to_numpy(float), d["true_lon"].to_numpy(float))
        along, cross = self._offsets_to_frame(d, east, north)
        w = np.where(d["kind"].to_numpy() == "real_gap", self.cfg["real_gap_weight"], 1.0)
        params = {"objective": self.cfg["objective"], "num_leaves": self.cfg["num_leaves"],
                  "learning_rate": self.cfg["learning_rate"], "min_child_samples": self.cfg["min_child_samples"],
                  "feature_fraction": self.cfg["feature_fraction"], "bagging_fraction": self.cfg["bagging_fraction"],
                  "bagging_freq": 1, "lambda_l2": self.cfg["lambda_l2"], "seed": self.cfg["seed"],
                  "verbose": -1, "num_threads": self.cfg["num_threads"], "deterministic": True,
                  "force_col_wise": True}
        if self.cfg["objective"] == "huber":
            params["alpha"] = float(np.quantile(np.hypot(along, cross), 0.9)) or 1.0
        X = d[self.features].to_numpy(np.float64)
        out = []
        for y in (along, cross):
            out.append(lgb.train(params, lgb.Dataset(X, y, weight=w, feature_name=self.features,
                                                     free_raw_data=True), self.cfg["n_estimators"]))
        return tuple(out)

    def _calibrate(self, cal: pd.DataFrame, h: int) -> dict:
        if cal.empty:
            return {"pooled": {"q80": float("nan"), "q95": float("nan"), "n": 0}}
        lat, lon = self._point(cal, np.full(len(cal), h, float), only=h)
        err = _dist(lat, lon, cal)
        b = speed_bucket(cal["last_sog"])
        r = {"pooled": {"q80": conformal_q(err, 0.8), "q95": conformal_q(err, 0.95), "n": int(len(err))}}
        for k in range(len(SPEED_BUCKETS_KN) + 1):
            e = err[b == k]
            if len(e) >= MIN_BUCKET_N:
                r[str(k)] = {"q80": conformal_q(e, 0.8), "q95": conformal_q(e, 0.95), "n": int(len(e))}
        return r

    # ---- predict ----------------------------------------------------------------------------------------------
    def _correction(self, df: pd.DataFrame, h: int):
        if h not in self.boosters:
            z = np.zeros(len(df))
            return z, z
        X = df[self.features].to_numpy(np.float64)
        a, c = self.boosters[h]
        return a.predict(X), c.predict(X)

    def _point(self, df, eff_h, only: int | None = None):
        """Predicted point at effective horizon eff_h seconds after the last fix."""
        blat, blon = baseline_position(df.assign(age_s=0.0), eff_h)
        along, cross = self._interp(df, eff_h, only)
        east, north = self._frame_to_offsets(df, along, cross)
        return apply_enu_offset(blat, blon, east, north)

    def _interp(self, df, eff_h, only=None):
        hs = [only] if only is not None else self.horizons
        corr = {h: self._correction(df, h) for h in hs}
        if only is not None:
            return corr[only]
        grid = np.array([0, *hs], float)
        along = np.zeros(len(df))
        cross = np.zeros(len(df))
        e = np.minimum(eff_h, grid[-1])
        k = np.clip(np.searchsorted(grid, e, side="right") - 1, 0, len(grid) - 2)
        w = (e - grid[k]) / (grid[k + 1] - grid[k])
        for idx in range(len(grid) - 1):
            m = k == idx
            if not m.any():
                continue
            a0, c0 = (np.zeros(m.sum()), np.zeros(m.sum())) if idx == 0 else (corr[hs[idx - 1]][0][m], corr[hs[idx - 1]][1][m])
            a1, c1 = corr[hs[idx]][0][m], corr[hs[idx]][1][m]
            along[m] = a0 + w[m] * (a1 - a0)
            cross[m] = c0 + w[m] * (c1 - c0)
        return along, cross

    def _radii(self, df, eff_h):
        b = speed_bucket(df["last_sog"])
        grid = np.array([0, *self.horizons], float)
        out = {}
        for lvl in ("q80", "q95"):
            tab = np.zeros((len(self.horizons) + 1, len(SPEED_BUCKETS_KN) + 1))
            for hi, h in enumerate(self.horizons, start=1):
                r = self.radius.get(h, {})
                for k in range(tab.shape[1]):
                    tab[hi, k] = r.get(str(k), r.get("pooled", {})).get(lvl, np.nan)
            e = np.asarray(eff_h, float)
            k = np.clip(np.searchsorted(grid, np.minimum(e, grid[-1]), side="right") - 1, 0, len(grid) - 2)
            w = (np.minimum(e, grid[-1]) - grid[k]) / (grid[k + 1] - grid[k])
            r0, r1 = tab[k, b], tab[k + 1, b]
            rad = np.where(w <= 0, r0, np.where(w >= 1, r1, r0 + w * (r1 - r0)))
            out[lvl] = np.where(e > grid[-1], tab[-1, b] * e / grid[-1], rad)
        return out["q80"], out["q95"]

    def predict(self, df: pd.DataFrame) -> pd.DataFrame:
        eff = df["horizon_s"].to_numpy(float) + df["age_s"].to_numpy(float)
        lat, lon = self._point(df, eff)
        blat, blon = baseline_position(df.assign(age_s=0.0), eff)
        r80, r95 = self._radii(df, eff)
        return pd.DataFrame({"pred_lat": lat, "pred_lon": lon, "radius_m_80": r80, "radius_m_95": r95,
                             "base_lat": blat, "base_lon": blon}, index=df.index)

    # ---- artifact ---------------------------------------------------------------------------------------------
    def save(self, d) -> Path:
        d = Path(d)
        d.mkdir(parents=True, exist_ok=True)
        files = {}
        for h, (a, c) in self.boosters.items():
            files[str(h)] = {"along": f"h{h}_along.txt", "cross": f"h{h}_cross.txt"}
            a.save_model(str(d / files[str(h)]["along"]))
            c.save_model(str(d / files[str(h)]["cross"]))
        spec = {"target": self.target, "model": self.name, "version": self.version, "feature_version": FEATURE_VERSION,
                "features": self.features, "horizons_s": self.horizons, "cfg": self.cfg,
                "data_hash": self.meta.get("data_hash"), "train_from": self.meta.get("train_from"),
                "train_to": self.meta.get("train_to"), "meta": self.meta, "metrics": self.meta.get("metrics", {}),
                "speed_buckets_kn": list(SPEED_BUCKETS_KN), "radius": {str(h): r for h, r in self.radius.items()},
                "boosters": files,
                "how_to_predict": ("baseline = dead reckoning from the last fix (features.baseline_position, age 0) at "
                                   "eff = age_s + horizon_s; correction (along, cross) in metres in the baseline "
                                   "course frame from the booster pair per horizon, interpolated linearly in eff "
                                   "between 0 and the trained horizons and held beyond the last; radius per speed "
                                   "bucket, interpolated the same way and scaled by eff / last horizon beyond it.")}
        (d / "model.json").write_text(json.dumps(spec, indent=1, default=_json))
        return d

    @property
    def version(self) -> str:
        blob = json.dumps({"cfg": self.cfg, "data": self.meta.get("data_hash")}, sort_keys=True, default=_json)
        return f"{self.name}-{hashlib.sha256(blob.encode()).hexdigest()[:10]}"

    @classmethod
    def load(cls, d) -> "RouteModel":
        import lightgbm as lgb
        d = Path(d)
        spec = json.loads((d / "model.json").read_text())
        m = cls(spec["cfg"])
        m.features = spec["features"]
        m.horizons = [int(h) for h in spec["horizons_s"]]
        m.radius = {int(h): r for h, r in spec["radius"].items()}
        m.meta = spec.get("meta", {})
        for h, f in spec["boosters"].items():
            m.boosters[int(h)] = (lgb.Booster(model_file=str(d / f["along"])),
                                  lgb.Booster(model_file=str(d / f["cross"])))
        return m


def _dist(lat, lon, df):
    from ml.route.geo import haversine_m
    return haversine_m(lat, lon, df["true_lat"].to_numpy(float), df["true_lon"].to_numpy(float))


def _json(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    raise TypeError(type(o))
