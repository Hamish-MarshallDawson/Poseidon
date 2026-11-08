"""Go-dark risk as a target for the training loop (#121): `SPEC = GodarkTarget()`.

Primary label: `y_deliberate_candidate_<H>` from ml/godark/dataset.py (a `deliberate_candidate` gap of ours starts
within H). Our own detector made these labels; GFW gap events (#112) are the independent check offshore.

Models (ml.core.registry.Model):
- `baseline`: the base rate per 1 degree area and ship type group from the training rows, shrunk towards the area
  rate and then the global rate (SHRINK pseudo-rows at each level). A JSON table.
- `lgbm`: LightGBM binary per horizon with class weights, then isotonic calibration fitted on the latest part of the
  training window (time-ordered, after an embargo), exported as the piecewise-linear breakpoints the backend's
  `dvm.predict.artifact.GodarkModel` reads. With `features: "track"` it uses only `dvm.predict.features`
  FEATURE_NAMES, so the backend can load it; `"track+context"` adds ml/godark/dataset.py CONTEXT_FEATURES, which the
  live predictor does not compute yet (model.json says `deployable: false`).

Per-case loss is log loss (mean is the statistic). Calibration check: expected calibration error (10 equal-count
bins) against 0 with tolerance 0.05.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

import ml  # noqa: F401  (backend/ on sys.path)
from dvm.predict import features as F
from ml.core.registry import Model
from ml.core.target import TargetSpec
from ml.godark import MAX_THREADS, PRIMARY_HORIZON_S, TARGET_NAMES
from ml.godark import dataset as D

HORIZONS = D.HORIZONS_S
PRIMARY_FLAG = "deliberate_candidate"
EPS = 1e-6
SHRINK = 50.0
MIN_POS = 20              # a horizon with fewer training positives gets no head (and the model says so)
DEFAULT_DATA = D.OUT / "examples.parquet"


def label_col(h: int, flag: str = PRIMARY_FLAG) -> str:
    return f"y_{flag}_{D.h_label(h)}"


def log_loss(y: np.ndarray, p: np.ndarray) -> np.ndarray:
    p = np.clip(p, EPS, 1 - EPS)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def ece(y: np.ndarray, p: np.ndarray, bins: int = 10) -> float:
    if len(y) == 0:
        return float("nan")
    order = np.argsort(p, kind="stable")
    err = 0.0
    for idx in np.array_split(order, bins):
        if len(idx):
            err += len(idx) * abs(p[idx].mean() - y[idx].mean())
    return err / len(y)


def calibration_curve(y: np.ndarray, p: np.ndarray, bins: int = 10) -> list[dict]:
    order = np.argsort(p, kind="stable")
    return [{"p_mean": float(p[i].mean()), "y_rate": float(y[i].mean()), "n": int(len(i))}
            for i in np.array_split(order, bins) if len(i)]


def auc_pr(y: np.ndarray, p: np.ndarray) -> float:
    from sklearn.metrics import average_precision_score
    return float(average_precision_score(y, p)) if 0 < y.sum() < len(y) else float("nan")


# ---------------------------------------------------------------- models

class Baseline(Model):
    name, target = "baseline", "godark"

    def __init__(self):
        self.table: dict[str, dict] = {}

    def fit(self, train_df, cfg):
        self.table = {}
        for h in HORIZONS:
            col = label_col(h)
            d = train_df[train_df[col].notna()]
            if d.empty:
                continue
            g = float(d[col].mean())
            area = d.groupby("area")[col].agg(["sum", "count"])
            a_rate = ((area["sum"] + SHRINK * g) / (area["count"] + SHRINK)).to_dict()
            at = d.groupby(["area", "type_group"])[col].agg(["sum", "count"])
            at_rate = {f"{a}|{t}": float((r["sum"] + SHRINK * a_rate[a]) / (r["count"] + SHRINK))
                       for (a, t), r in at.iterrows()}
            self.table[str(h)] = {"global": g, "area": {str(k): float(v) for k, v in a_rate.items()},
                                  "area_type": at_rate, "n": int(len(d))}
        return self

    def predict(self, df):
        out = []
        for h, t in self.table.items():
            a = df["area"].astype(str).to_numpy()
            k = a + "|" + df["type_group"].astype(str).to_numpy()
            p = [t["area_type"].get(kk, t["area"].get(aa, t["global"])) for kk, aa in zip(k, a)]
            out.append(pd.DataFrame({"case_id": df["case_id"].to_numpy(), "horizon_s": int(h), "p": p}))
        return pd.concat(out, ignore_index=True) if out else pd.DataFrame(columns=["case_id", "horizon_s", "p"])

    def save(self, dir):
        (dir / "baseline.json").write_text(json.dumps(self.table))
        return {"features": ["area", "type_group"], "horizons_s": [int(h) for h in self.table],
                "kind": "baseline-table", "deployable": False}

    @classmethod
    def load(cls, dir):
        m = cls()
        m.table = json.loads((Path(dir) / "baseline.json").read_text())
        return m


class GlobalRate(Baseline):
    """One base rate per horizon: the floor every model must beat."""
    name = "global_rate"

    def fit(self, train_df, cfg):
        self.table = {}
        for h in HORIZONS:
            col = label_col(h)
            d = train_df[train_df[col].notna()]
            if len(d):
                self.table[str(h)] = {"global": float(d[col].mean()), "area": {}, "area_type": {}, "n": int(len(d))}
        return self


def feature_list(cfg: dict) -> list[str]:
    feats = list(F.FEATURE_NAMES)
    if cfg.get("features", "track") == "track+context":
        feats += D.CONTEXT_FEATURES
    drop = set(cfg.get("drop_features", []))
    return [f for f in feats if f not in drop]


class Lgbm(Model):
    name, target = "lgbm", "godark"

    def __init__(self):
        self.features: list[str] = []
        self.boosters: dict[int, object] = {}
        self.cal: dict[int, dict] = {}
        self.vocab: dict[str, list[str]] = {}
        self.info: dict = {}

    def _matrix(self, df: pd.DataFrame) -> pd.DataFrame:
        X = pd.DataFrame(index=df.index)
        for f in self.features:
            if f not in df:
                X[f] = np.nan   # as the backend does for a feature it has no value for
            elif f in D.CATEGORICAL:
                X[f] = pd.Categorical(df[f].astype(str), categories=self.vocab[f]).codes.astype(float)
                X.loc[X[f] < 0, f] = np.nan
            else:
                X[f] = pd.to_numeric(df[f], errors="coerce").astype(float)
        return X

    def fit(self, train_df, cfg):
        import lightgbm as lgb
        from sklearn.isotonic import IsotonicRegression
        self.features = feature_list(cfg)
        self.vocab = {}
        for f in D.CATEGORICAL:
            if f in self.features:
                vc = train_df[f].astype(str).value_counts()
                self.vocab[f] = sorted(vc[vc >= cfg.get("min_category_rows", 200)].index.tolist())
        cal_frac = float(cfg.get("cal_frac", 0.25))
        params = {"objective": "binary", "verbosity": -1, "seed": int(cfg.get("seed", 7)), "deterministic": True,
                  "num_leaves": int(cfg.get("num_leaves", 31)), "learning_rate": float(cfg.get("learning_rate", 0.05)),
                  "min_child_samples": int(cfg.get("min_child_samples", 200)),
                  "feature_fraction": float(cfg.get("feature_fraction", 0.8)),
                  "bagging_fraction": float(cfg.get("bagging_fraction", 0.8)), "bagging_freq": 1,
                  "lambda_l2": float(cfg.get("lambda_l2", 1.0)), "num_threads": min(int(cfg.get("num_threads", MAX_THREADS)), MAX_THREADS),
                  "force_col_wise": True}
        cats = [f for f in self.features if f in D.CATEGORICAL]
        self.boosters, self.cal, self.info = {}, {}, {}
        for h in HORIZONS:
            col = label_col(h)
            d = train_df[train_df[col].notna()].sort_values("as_of")
            if d[col].sum() < MIN_POS:
                self.info[str(h)] = {"skipped": f"{int(d[col].sum())} positives < {MIN_POS}", "n": int(len(d))}
                continue
            # Calibration slice: the latest cal_frac of the window, after an embargo of H (time-ordered). When the
            # window is too short for that (6 h on half a day of data), a ship-disjoint slice instead.
            t = d["as_of"].to_numpy()
            cut = np.quantile(t, 1 - cal_frac)
            fit_d, cal_d, how = d[t <= cut - h * 1000], d[t > cut], "time"
            if fit_d[col].sum() < MIN_POS or cal_d[col].sum() < 5:
                held = (d["mmsi"].to_numpy() * 2654435761 % 2**32) / 2**32 < cal_frac
                fit_d, cal_d, how = d[~held], d[held], "ships"
            if fit_d[col].sum() < MIN_POS or cal_d[col].sum() < 5:
                fit_d, cal_d, how = d, None, "none"   # too little to calibrate: train unweighted instead
            y = fit_d[col].to_numpy()
            pos = y.sum()
            w_pos = cfg.get("pos_weight", "balanced")
            w_pos = (len(y) - pos) / max(pos, 1) if w_pos == "balanced" else float(w_pos)
            w_pos = min(w_pos, float(cfg.get("max_pos_weight", 50))) if cal_d is not None else 1.0
            w = np.where(y > 0, w_pos, 1.0)
            ds = lgb.Dataset(self._matrix(fit_d), y, weight=w, categorical_feature=cats or "auto",
                             free_raw_data=False)
            b = lgb.train(params, ds, num_boost_round=int(cfg.get("n_estimators", 300)))
            self.boosters[h] = b
            if cal_d is not None:
                raw = b.predict(self._matrix(cal_d))
                iso = IsotonicRegression(out_of_bounds="clip", y_min=0, y_max=1).fit(raw, cal_d[col].to_numpy())
                xs, ys = iso.X_thresholds_.tolist(), iso.y_thresholds_.tolist()
                if len(xs) < 2:
                    xs, ys = [0.0, 1.0], [float(cal_d[col].mean())] * 2
                self.cal[h] = {"x": xs, "y": ys}
            self.info[str(h)] = {"calibration_slice": how, "n_fit": int(len(fit_d)), "pos_fit": int(pos), "pos_weight": float(w_pos),
                                 "n_cal": 0 if cal_d is None else int(len(cal_d)),
                                 "pos_cal": 0 if cal_d is None else int(cal_d[col].sum())}
        return self

    def raw(self, df: pd.DataFrame, h: int) -> np.ndarray:
        return self.boosters[h].predict(self._matrix(df))

    def predict(self, df):
        out = []
        for h in self.boosters:
            r = self.raw(df, h)
            cal = self.cal.get(h)
            # Same as the backend's dvm.predict.artifact.calibrate: piecewise linear, clamped at both ends.
            p = np.interp(r, cal["x"], cal["y"]) if cal else np.clip(r, 0, 1)
            out.append(pd.DataFrame({"case_id": df["case_id"].to_numpy(), "horizon_s": h, "p": p}))
        return pd.concat(out, ignore_index=True) if out else pd.DataFrame(columns=["case_id", "horizon_s", "p"])

    def save(self, dir):
        heads = {}
        for h, b in self.boosters.items():
            b.save_model(str(dir / f"h{h}.txt"))
            heads[str(h)] = {"model": f"h{h}.txt", "target_name": TARGET_NAMES[h], **({"calibration": self.cal[h]} if h in self.cal else {})}
        deployable = all(f in F.FEATURE_NAMES for f in self.features)
        return {"features": self.features, "horizons_s": sorted(self.boosters), "heads": heads, "kind": "lightgbm",
                "feature_version": F.FEATURE_VERSION, "deployable": deployable, "vocab": self.vocab,
                "fit_info": self.info, "label": PRIMARY_FLAG,
                "targets": {str(h): TARGET_NAMES[h] for h in sorted(self.boosters)},
                "primary_target": TARGET_NAMES[PRIMARY_HORIZON_S]}

    @classmethod
    def load(cls, dir):
        import lightgbm as lgb
        dir = Path(dir)
        meta = json.loads((dir / "model.json").read_text())
        m = cls()
        m.features, m.vocab, m.info = meta["features"], meta.get("vocab", {}), meta.get("fit_info", {})
        for h, spec in meta["heads"].items():
            m.boosters[int(h)] = lgb.Booster(model_file=str(dir / spec["model"]))
            if "calibration" in spec:
                m.cal[int(h)] = spec["calibration"]
        return m


# ---------------------------------------------------------------- the target

CONFIG_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["model"],
    "properties": {
        "model": {"type": "string", "enum": ["lgbm", "baseline", "global_rate"]},
        "seed": {"type": "integer", "minimum": 0},
        "features": {"type": "string", "enum": ["track", "track+context"]},
        "drop_features": {"type": "array", "maxItems": 40,
                          "items": {"type": "string", "enum": list(F.FEATURE_NAMES) + D.CONTEXT_FEATURES}},
        "num_leaves": {"type": "integer", "minimum": 4, "maximum": 255},
        "learning_rate": {"type": "number", "minimum": 0.005, "maximum": 0.3},
        "n_estimators": {"type": "integer", "minimum": 20, "maximum": 2000},
        "min_child_samples": {"type": "integer", "minimum": 10, "maximum": 5000},
        "feature_fraction": {"type": "number", "minimum": 0.2, "maximum": 1.0},
        "bagging_fraction": {"type": "number", "minimum": 0.3, "maximum": 1.0},
        "lambda_l2": {"type": "number", "minimum": 0, "maximum": 100},
        "pos_weight": {"oneOf": [{"type": "string", "enum": ["balanced"]},
                                 {"type": "number", "minimum": 1, "maximum": 200}]},
        "max_pos_weight": {"type": "number", "minimum": 1, "maximum": 200},
        "cal_frac": {"type": "number", "minimum": 0.1, "maximum": 0.5},
        "train_window_h": {"type": "number", "minimum": 1, "maximum": 720},
        "min_category_rows": {"type": "integer", "minimum": 10, "maximum": 10000},
    },
}


class GodarkTarget(TargetSpec):
    name = "godark"
    horizons_s = HORIZONS
    # dark_6h is the product's primary target (frontend RiskScore). dark_1h is also checked; dark_24h has no labels
    # on the live data yet.
    primary_horizons_s = [PRIMARY_HORIZON_S, 3600]
    statistic = "mean"
    loss_name = "log_loss"
    loss_unit = ""
    strata = ["type_group", "src", "speed_band"]
    baseline = "baseline"
    default_config = {"model": "lgbm", "seed": 7, "features": "track", "num_leaves": 31, "learning_rate": 0.05,
                      "n_estimators": 300, "min_child_samples": 200, "pos_weight": "balanced", "cal_frac": 0.25}
    config_schema = CONFIG_SCHEMA
    group_by_ship = False
    models = {"lgbm": Lgbm, "baseline": Baseline, "global_rate": GlobalRate}

    def load_examples(self, cfg, data):
        return pd.read_parquet(data or DEFAULT_DATA)

    def score(self, examples, preds):
        ex = examples.set_index("case_id")
        rows = []
        for h in self.horizons_s:
            col = label_col(h)
            p = preds[preds["horizon_s"] == h].set_index("case_id")
            j = p.join(ex[[col, "mmsi", "as_of", "type_group", "src_digitraffic", "sog_kn"]], how="inner")
            j = j[j[col].notna()]
            if j.empty:
                continue
            y = j[col].to_numpy(float)
            pp = j["p"].to_numpy(float)
            rows.append(pd.DataFrame({
                "case_id": j.index.to_numpy(), "mmsi": j["mmsi"].to_numpy(), "as_of": j["as_of"].to_numpy(),
                "horizon_s": h, "loss": log_loss(y, pp), "y": y, "p": pp, "brier": (pp - y) ** 2,
                "type_group": j["type_group"].astype(str).to_numpy(),
                "src": np.where(j["src_digitraffic"].to_numpy() > 0, "digitraffic", "aisstream"),
                "speed_band": pd.cut(j["sog_kn"], [-1, 5, 12, 1e9], labels=["<5kn", "5-12kn", ">12kn"]).astype(str)
                .to_numpy()}))
        return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(columns=["case_id", "horizon_s", "loss"])

    def summarise(self, scored):
        out = {}
        for h, g in scored.groupby("horizon_s"):
            y, p = g["y"].to_numpy(), g["p"].to_numpy()
            out[str(h)] = {"target_name": TARGET_NAMES[int(h)], "n": int(len(g)), "positives": int(y.sum()), "base_rate": float(y.mean()),
                           "log_loss": float(g["loss"].mean()), "brier": float(g["brier"].mean()),
                           "auc_pr": auc_pr(y, p), "ece": ece(y, p)}
        return out

    def calibration(self, scored):
        return [{"name": "ece", "horizon_s": int(h), "value": ece(g["y"].to_numpy(), g["p"].to_numpy()),
                 "nominal": 0.0, "tol": 0.05} for h, g in scored.groupby("horizon_s")]

    def sanity(self, summary):
        bad = []
        for h, m in summary.items():
            if m.get("auc_pr", 0) > 0.95:
                bad.append(f"AUC-PR {m['auc_pr']:.3f} at {h} s is too good to be true: check for leakage")
        return bad


SPEC = GodarkTarget()
