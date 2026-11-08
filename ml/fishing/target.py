"""Fishing in protected areas as a target for the training loop (#157): `SPEC = FishingTarget()`.

One case per fishing vessel and UTC week (ml/fishing/dataset.py). Label `y_mpa_7d`: the vessel has a GFW fishing
event inside a marine protected area in the coming week. Chosen over "next event carries potentialRisk" because
potentialRisk was false on every one of the events we pulled (no positives to learn from).

Models (ml.core.registry.Model):
- `baseline`: rate by gear type and flag, shrunk to the gear rate and then the global rate (the brief's baseline;
  skill and the promotion rule are measured against it).
- `persistence`: rate by whether the vessel fished inside an MPA in the last 28 days (a stronger, honest reference,
  reported only).
- `lgbm`: LightGBM binary with class weights and isotonic calibration on the latest slice of the training window
  (after an embargo of one week), exported as piecewise-linear breakpoints in the backend's go-dark `heads` format.
  The backend computes no GFW fishing features live, so the artifact is marked `deployable: false` for now.

Held-out set: the 13 weeks from Monday 3 Aug 2026 (`holdout_bounds`), so every run and history length uses the same
weeks. Per-case loss is log loss (mean); calibration check is ECE (10 equal-count bins) within 0.05.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

import ml  # noqa: F401
from ml import fishing  # noqa: F401  (thread cap before lightgbm loads)
from ml.core.registry import Model
from ml.core.target import TargetSpec
from ml.fishing import MAX_THREADS
from ml.fishing import dataset as D
from ml.godark.target import auc_pr, calibration_curve, ece, log_loss

H = D.HORIZON_S
Y = D.LABEL
SHRINK = 50.0
TEST_START = int(pd.Timestamp("2026-08-03", tz="UTC").value // 1_000_000)
TEST_END = TEST_START + 13 * D.WEEK
TARGET_NAME = "fishing_in_mpa_7d"


def _empty():
    return pd.DataFrame(columns=["case_id", "horizon_s", "p"])


class Baseline(Model):
    name, target = "baseline", "fishing"
    keys = ("gear", "flag")

    def __init__(self):
        self.table: dict = {}

    def _k(self, df):
        a, b = self.keys
        return df[a].astype(str).to_numpy(), (df[a].astype(str) + "|" + df[b].astype(str)).to_numpy()

    def fit(self, train_df, cfg):
        d = train_df[train_df[Y].notna()].copy()
        g = float(d[Y].mean())
        k1, k2 = self._k(d)
        d["_k1"], d["_k2"] = k1, k2
        t1 = d.groupby("_k1")[Y].agg(["sum", "count"])
        r1 = ((t1["sum"] + SHRINK * g) / (t1["count"] + SHRINK)).to_dict()
        t2 = d.groupby(["_k1", "_k2"])[Y].agg(["sum", "count"])
        r2 = {k2_: float((r["sum"] + SHRINK * r1[k1_]) / (r["count"] + SHRINK)) for (k1_, k2_), r in t2.iterrows()}
        self.table = {"global": g, "k1": {str(k): float(v) for k, v in r1.items()}, "k2": r2, "n": int(len(d)),
                      "positives": int(d[Y].sum()), "keys": list(self.keys)}
        return self

    def predict(self, df):
        if not self.table:
            return _empty()
        k1, k2 = self._k(df)
        t = self.table
        p = [t["k2"].get(b, t["k1"].get(a, t["global"])) for a, b in zip(k1, k2)]
        return pd.DataFrame({"case_id": df["case_id"].to_numpy(), "horizon_s": H, "p": p})

    def save(self, dir):
        (dir / "baseline.json").write_text(json.dumps(self.table))
        return {"features": list(self.keys), "horizons_s": [H], "kind": "baseline-table", "deployable": False}

    @classmethod
    def load(cls, dir):
        m = cls()
        m.table = json.loads((Path(dir) / "baseline.json").read_text())
        return m


class Persistence(Baseline):
    """Rate by recent MPA fishing (none / some / most of the last 28 days' hours) and region."""
    name = "persistence"
    keys = ("_recent", "region")

    def _k(self, df):
        tot = df["hours_in_mpa_28d"].fillna(0) + df["hours_out_mpa_28d"].fillna(0)
        share = np.where(tot > 0, df["hours_in_mpa_28d"].fillna(0) / tot.where(tot > 0, 1), -1)
        rec = np.select([share < 0, share == 0, share < 0.5], ["idle", "none", "some"], "most")
        return rec.astype(str), (pd.Series(rec, index=df.index) + "|" + df["region"].astype(str)).to_numpy()


class GlobalRate(Baseline):
    name = "global_rate"

    def fit(self, train_df, cfg):
        d = train_df[train_df[Y].notna()]
        self.table = {"global": float(d[Y].mean()), "k1": {}, "k2": {}, "n": int(len(d)), "keys": list(self.keys)}
        return self


def feature_list(cfg: dict) -> list[str]:
    drop = set(cfg.get("drop_features", []))
    return [f for f in D.FEATURES if f not in drop]


class Lgbm(Model):
    name, target = "lgbm", "fishing"

    def __init__(self):
        self.features: list[str] = []
        self.booster = None
        self.cal: dict | None = None
        self.vocab: dict[str, list[str]] = {}
        self.info: dict = {}

    def _matrix(self, df):
        X = pd.DataFrame(index=df.index)
        for f in self.features:
            if f in D.CATEGORICAL:
                X[f] = pd.Categorical(df[f].astype(str), categories=self.vocab[f]).codes.astype(float)
                X.loc[X[f] < 0, f] = np.nan
            else:
                X[f] = pd.to_numeric(df[f], errors="coerce").astype(float)
        return X

    def fit(self, train_df, cfg):
        import lightgbm as lgb
        from sklearn.isotonic import IsotonicRegression
        self.features = feature_list(cfg)
        d = train_df[train_df[Y].notna()].sort_values("as_of")
        self.vocab = {}
        for f in D.CATEGORICAL:
            if f in self.features:
                vc = d[f].astype(str).value_counts()
                self.vocab[f] = sorted(vc[vc >= cfg.get("min_category_rows", 50)].index.tolist())
        params = {"objective": "binary", "verbosity": -1, "seed": int(cfg.get("seed", 7)), "deterministic": True,
                  "num_leaves": int(cfg.get("num_leaves", 15)), "learning_rate": float(cfg.get("learning_rate", 0.03)),
                  "min_child_samples": int(cfg.get("min_child_samples", 100)),
                  "feature_fraction": float(cfg.get("feature_fraction", 0.8)),
                  "bagging_fraction": float(cfg.get("bagging_fraction", 0.8)), "bagging_freq": 1,
                  "lambda_l2": float(cfg.get("lambda_l2", 10.0)), "num_threads": MAX_THREADS, "force_col_wise": True}
        cats = [f for f in self.features if f in D.CATEGORICAL]
        t = d["as_of"].to_numpy()
        cut = np.quantile(t, 1 - float(cfg.get("cal_frac", 0.25)))
        fit_d, cal_d = d[t < cut - H * 1000], d[t >= cut]   # embargo of one horizon between fit and calibration
        if fit_d[Y].sum() < 20 or cal_d[Y].sum() < 10:
            fit_d, cal_d = d, None
        y = fit_d[Y].to_numpy()
        pos = y.sum()
        wp = cfg.get("pos_weight", "balanced")
        wp = (len(y) - pos) / max(pos, 1) if wp == "balanced" else float(wp)
        wp = wp if cal_d is not None else 1.0   # without a calibration slice, train unweighted so p stays calibrated
        ds = lgb.Dataset(self._matrix(fit_d), y, weight=np.where(y > 0, wp, 1.0), categorical_feature=cats or "auto",
                         free_raw_data=False)
        self.booster = lgb.train(params, ds, num_boost_round=int(cfg.get("n_estimators", 300)))
        self.cal = None
        if cal_d is not None:
            raw = self.booster.predict(self._matrix(cal_d))
            iso = IsotonicRegression(out_of_bounds="clip", y_min=0, y_max=1).fit(raw, cal_d[Y].to_numpy())
            xs, ys = iso.X_thresholds_.tolist(), iso.y_thresholds_.tolist()
            if len(xs) < 2:
                xs, ys = [0.0, 1.0], [float(cal_d[Y].mean())] * 2
            self.cal = {"x": xs, "y": ys}
        self.info = {"n_fit": int(len(fit_d)), "pos_fit": int(pos), "pos_weight": float(wp),
                     "n_cal": 0 if cal_d is None else int(len(cal_d)),
                     "pos_cal": 0 if cal_d is None else int(cal_d[Y].sum())}
        return self

    def predict(self, df):
        if self.booster is None:
            return _empty()
        r = self.booster.predict(self._matrix(df))
        p = np.interp(r, self.cal["x"], self.cal["y"]) if self.cal else np.clip(r, 0, 1)
        return pd.DataFrame({"case_id": df["case_id"].to_numpy(), "horizon_s": H, "p": p})

    def save(self, dir):
        self.booster.save_model(str(dir / f"h{H}.txt"))
        head = {"model": f"h{H}.txt", "target_name": TARGET_NAME, **({"calibration": self.cal} if self.cal else {})}
        return {"features": self.features, "horizons_s": [H], "heads": {str(H): head}, "kind": "lightgbm",
                "deployable": False, "vocab": self.vocab, "fit_info": self.info, "label": "gfw_fishing_in_mpa",
                "categorical": [f for f in self.features if f in D.CATEGORICAL]}

    @classmethod
    def load(cls, dir):
        import lightgbm as lgb
        dir = Path(dir)
        meta = json.loads((dir / "model.json").read_text())
        m = cls()
        m.features, m.vocab, m.info = meta["features"], meta.get("vocab", {}), meta.get("fit_info", {})
        spec = meta["heads"][str(H)]
        m.booster = lgb.Booster(model_file=str(dir / spec["model"]))
        m.cal = spec.get("calibration")
        return m


CONFIG_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["model"],
    "properties": {
        "model": {"type": "string", "enum": ["lgbm", "baseline", "persistence", "global_rate"]},
        "seed": {"type": "integer", "minimum": 0, "maximum": 10_000},
        "drop_features": {"type": "array", "maxItems": 20, "items": {"type": "string", "enum": D.FEATURES}},
        "num_leaves": {"type": "integer", "minimum": 4, "maximum": 127},
        "learning_rate": {"type": "number", "minimum": 0.005, "maximum": 0.3},
        "n_estimators": {"type": "integer", "minimum": 20, "maximum": 2000},
        "min_child_samples": {"type": "integer", "minimum": 10, "maximum": 5000},
        "feature_fraction": {"type": "number", "minimum": 0.2, "maximum": 1.0},
        "bagging_fraction": {"type": "number", "minimum": 0.3, "maximum": 1.0},
        "lambda_l2": {"type": "number", "minimum": 0, "maximum": 100},
        "pos_weight": {"oneOf": [{"type": "string", "enum": ["balanced"]},
                                 {"type": "number", "minimum": 1, "maximum": 100}]},
        "cal_frac": {"type": "number", "minimum": 0.1, "maximum": 0.5},
        "train_window_days": {"type": "integer", "minimum": 28, "maximum": 3650},
        "min_category_rows": {"type": "integer", "minimum": 10, "maximum": 10000},
    },
}


class FishingTarget(TargetSpec):
    name = "fishing"
    horizons_s = [H]
    primary_horizons_s = [H]
    statistic = "mean"
    loss_name = "log_loss"
    loss_unit = ""
    strata = ["region", "gear_band"]
    baseline = "baseline"
    default_config = {"model": "lgbm", "seed": 7, "num_leaves": 15, "learning_rate": 0.03, "n_estimators": 300,
                      "min_child_samples": 100, "lambda_l2": 10.0, "pos_weight": "balanced", "cal_frac": 0.25}
    config_schema = CONFIG_SCHEMA
    group_by_ship = False
    models = {"lgbm": Lgbm, "baseline": Baseline, "persistence": Persistence, "global_rate": GlobalRate}
    dry_run_proposals = [
        {"config": {"model": "persistence", "seed": 7}, "rationale": "recent-MPA-fishing reference"},
        {"config": default_config | {"num_leaves": 31, "min_child_samples": 50}, "rationale": "more capacity"},
        {"config": default_config | {"drop_features": ["month"]}, "rationale": "without seasonality"},
    ]
    report_notes = [
        "Labels and features are Global Fishing Watch fishing events (CC BY-NC 4.0) in our four regions; an event "
        "counts as inside a marine protected area when GFW tags it with an MPA or no-take MPA. Features use only "
        "events public at the case's time (about 4 days after they end).",
        "Fishing inside an MPA is not by itself illegal: many MPAs allow some fishing. This flags where to look.",
        "potentialRisk was false on every event pulled, so it could not be a label.",
    ]

    def holdout_bounds(self, examples):
        return TEST_START, TEST_END

    def load_examples(self, cfg, data):
        p = Path(data) if data else D.DEFAULT_OUT
        if p.is_dir():
            return D.build(p)[0]
        return pd.read_parquet(p)

    def score(self, examples, preds):
        ex = examples.set_index("case_id")
        p = preds[preds["horizon_s"] == H].set_index("case_id")
        j = p.join(ex[[Y, "mmsi", "as_of", "region", "gear"]], how="inner")
        j = j[j[Y].notna()]
        if j.empty:
            return pd.DataFrame(columns=["case_id", "mmsi", "as_of", "horizon_s", "loss"])
        y, pp = j[Y].to_numpy(float), j["p"].to_numpy(float)
        g = j["gear"].astype(str)
        return pd.DataFrame({
            "case_id": j.index.to_numpy(), "mmsi": j["mmsi"].to_numpy(), "as_of": j["as_of"].to_numpy(),
            "horizon_s": H, "loss": log_loss(y, pp), "y": y, "p": pp, "brier": (pp - y) ** 2,
            "region": j["region"].astype(str).to_numpy(),
            "gear_band": np.where(g.isin(["TRAWLERS", "FIXED_GEAR", "DRIFTING_LONGLINES", "FISHING"]), g, "OTHER")})

    def summarise(self, scored):
        out = {}
        for h, g in scored.groupby("horizon_s"):
            y, p = g["y"].to_numpy(), g["p"].to_numpy()
            out[str(h)] = {"target_name": TARGET_NAME, "n": int(len(g)), "positives": int(y.sum()),
                           "positive_ships": int(g.loc[g["y"] > 0, "mmsi"].nunique()), "base_rate": float(y.mean()),
                           "log_loss": float(g["loss"].mean()), "brier": float(g["brier"].mean()),
                           "auc_pr": auc_pr(y, p), "ece": ece(y, p), "calibration_curve": calibration_curve(y, p)}
        return out

    def calibration(self, scored):
        return [{"name": "ece", "horizon_s": int(h), "value": ece(g["y"].to_numpy(), g["p"].to_numpy()),
                 "nominal": 0.0, "tol": 0.05} for h, g in scored.groupby("horizon_s")]

    def sanity(self, summary):
        return [f"AUC-PR {m['auc_pr']:.3f} at {h} s is too good to be true: check for leakage"
                for h, m in summary.items() if m.get("auc_pr", 0) > 0.97]


SPEC = FishingTarget()
