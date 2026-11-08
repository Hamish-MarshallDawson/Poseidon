"""GFW go-dark risk as a target for the training loop (#121): `SPEC = GodarkGfwTarget()`.

One case per ship and week (ml/godark_gfw/dataset.py). Label: the ship starts a GFW gap event within 30 days
(primary) or 14 days (second); 7 days is reported only, because it has too few positives (about 50 rows).

Models (ml.core.registry.Model):
- `baseline`: base rate by flag and vessel type, shrunk to the type rate and then the global rate. A JSON table.
- `global_rate`: one rate per horizon.
- `lgbm`: LightGBM binary per horizon with class weights, then isotonic calibration on a held-back slice of the
  training window (the latest part after an embargo of H; ship-disjoint if that slice has too few positives),
  exported as piecewise-linear breakpoints. Not deployable to the live backend: its features come from GFW
  history, not `dvm.predict.features`.

The held-out set is September 2026 (`holdout_bounds`), so the learning curve and every run use the same month.
Per-case loss is log loss (mean is the statistic); calibration check is ECE (10 equal-count bins) within 0.05.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

import ml  # noqa: F401
from ml import godark_gfw  # noqa: F401  (thread cap before lightgbm loads)
from ml.core.registry import DEFAULT_ARTIFACTS, Model
from ml.core.target import TargetSpec
from ml.godark.target import auc_pr, calibration_curve, ece, log_loss
from ml.godark_gfw import MAX_THREADS
from ml.godark_gfw import dataset as D

HORIZONS = D.HORIZONS_S
PRIMARY = [30 * 86400, 14 * 86400]
SHRINK = 200.0
MIN_POS = 20
TEST_START = int(pd.Timestamp("2026-09-01", tz="UTC").value // 1_000_000)
TEST_END = int(pd.Timestamp("2026-10-01", tz="UTC").value // 1_000_000)
CURVE_FILE = "godark_gfw-learning_curve.json"


def hname(h: int) -> str:
    return f"gfw_dark_{h // 86400}d"


# ---------------------------------------------------------------- models

class Baseline(Model):
    name, target = "baseline", "godark_gfw"

    def __init__(self):
        self.table: dict[str, dict] = {}

    def _keys(self, df):
        return df["type_group"].astype(str).to_numpy(), (df["flag"].astype(str) + "|" + df["type_group"].astype(str)).to_numpy()

    def fit(self, train_df, cfg):
        self.table = {}
        for h in HORIZONS:
            col = D.label_col(h)
            d = train_df[train_df[col].notna()]
            if d.empty:
                continue
            g = float(d[col].mean())
            t = d.groupby("type_group")[col].agg(["sum", "count"])
            t_rate = ((t["sum"] + SHRINK * g) / (t["count"] + SHRINK)).to_dict()
            ft = d.groupby(["flag", "type_group"])[col].agg(["sum", "count"])
            ft_rate = {f"{f}|{ty}": float((r["sum"] + SHRINK * t_rate[ty]) / (r["count"] + SHRINK))
                       for (f, ty), r in ft.iterrows()}
            self.table[str(h)] = {"global": g, "type": {str(k): float(v) for k, v in t_rate.items()},
                                  "flag_type": ft_rate, "n": int(len(d)), "positives": int(d[col].sum())}
        return self

    def predict(self, df):
        out = []
        ty, ft = self._keys(df)
        for h, t in self.table.items():
            p = [t["flag_type"].get(k, t["type"].get(a, t["global"])) for k, a in zip(ft, ty)]
            out.append(pd.DataFrame({"case_id": df["case_id"].to_numpy(), "horizon_s": int(h), "p": p}))
        return pd.concat(out, ignore_index=True) if out else pd.DataFrame(columns=["case_id", "horizon_s", "p"])

    def save(self, dir):
        (dir / "baseline.json").write_text(json.dumps(self.table))
        return {"features": ["flag", "type_group"], "horizons_s": [int(h) for h in self.table],
                "kind": "baseline-table", "deployable": False}

    @classmethod
    def load(cls, dir):
        m = cls()
        m.table = json.loads((Path(dir) / "baseline.json").read_text())
        return m


class GlobalRate(Baseline):
    name = "global_rate"

    def fit(self, train_df, cfg):
        self.table = {}
        for h in HORIZONS:
            d = train_df[train_df[D.label_col(h)].notna()]
            if len(d):
                self.table[str(h)] = {"global": float(d[D.label_col(h)].mean()), "type": {}, "flag_type": {},
                                      "n": int(len(d))}
        return self


def feature_list(cfg: dict) -> list[str]:
    drop = set(cfg.get("drop_features", []))
    return [f for f in D.FEATURES if f not in drop]


class Lgbm(Model):
    name, target = "lgbm", "godark_gfw"

    def __init__(self):
        self.features: list[str] = []
        self.boosters: dict[int, object] = {}
        self.cal: dict[int, dict] = {}
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
        self.vocab = {}
        for f in D.CATEGORICAL:
            if f in self.features:
                vc = train_df[f].astype(str).value_counts()
                self.vocab[f] = sorted(vc[vc >= cfg.get("min_category_rows", 300)].index.tolist())
        params = {"objective": "binary", "verbosity": -1, "seed": int(cfg.get("seed", 7)), "deterministic": True,
                  "num_leaves": int(cfg.get("num_leaves", 15)), "learning_rate": float(cfg.get("learning_rate", 0.03)),
                  "min_child_samples": int(cfg.get("min_child_samples", 300)),
                  "feature_fraction": float(cfg.get("feature_fraction", 0.8)),
                  "bagging_fraction": float(cfg.get("bagging_fraction", 0.8)), "bagging_freq": 1,
                  "lambda_l2": float(cfg.get("lambda_l2", 10.0)), "num_threads": MAX_THREADS, "force_col_wise": True}
        cats = [f for f in self.features if f in D.CATEGORICAL]
        cal_frac = float(cfg.get("cal_frac", 0.3))
        self.boosters, self.cal, self.info = {}, {}, {}
        for h in HORIZONS:
            col = D.label_col(h)
            d = train_df[train_df[col].notna()].sort_values("as_of")
            if d[col].sum() < MIN_POS:
                self.info[str(h)] = {"skipped": f"{int(d[col].sum())} positives < {MIN_POS}", "n": int(len(d))}
                continue
            t = d["as_of"].to_numpy()
            cut = np.quantile(t, 1 - cal_frac)
            fit_d, cal_d, how = d[t <= cut - h * 1000], d[t > cut], "time"
            if fit_d[col].sum() < MIN_POS or cal_d[col].sum() < 10:
                held = (d["mmsi"].to_numpy().astype(np.int64) * 2654435761 % 2**32) / 2**32 < cal_frac
                fit_d, cal_d, how = d[~held], d[held], "ships"
            if fit_d[col].sum() < MIN_POS or cal_d[col].sum() < 5:
                fit_d, cal_d, how = d, None, "none"
            y = fit_d[col].to_numpy()
            pos = y.sum()
            wp = cfg.get("pos_weight", "balanced")
            wp = (len(y) - pos) / max(pos, 1) if wp == "balanced" else float(wp)
            wp = min(wp, float(cfg.get("max_pos_weight", 100))) if cal_d is not None else 1.0
            ds = lgb.Dataset(self._matrix(fit_d), y, weight=np.where(y > 0, wp, 1.0),
                             categorical_feature=cats or "auto", free_raw_data=False)
            b = lgb.train(params, ds, num_boost_round=int(cfg.get("n_estimators", 300)))
            self.boosters[h] = b
            if cal_d is not None:
                raw = b.predict(self._matrix(cal_d))
                iso = IsotonicRegression(out_of_bounds="clip", y_min=0, y_max=1).fit(raw, cal_d[col].to_numpy())
                xs, ys = iso.X_thresholds_.tolist(), iso.y_thresholds_.tolist()
                if len(xs) < 2:
                    xs, ys = [0.0, 1.0], [float(cal_d[col].mean())] * 2
                self.cal[h] = {"x": xs, "y": ys}
            self.info[str(h)] = {"calibration_slice": how, "n_fit": int(len(fit_d)), "pos_fit": int(pos),
                                 "pos_weight": float(wp), "n_cal": 0 if cal_d is None else int(len(cal_d)),
                                 "pos_cal": 0 if cal_d is None else int(cal_d[col].sum())}
        return self

    def predict(self, df):
        out = []
        for h, b in self.boosters.items():
            r = b.predict(self._matrix(df))
            cal = self.cal.get(h)
            p = np.interp(r, cal["x"], cal["y"]) if cal else np.clip(r, 0, 1)
            out.append(pd.DataFrame({"case_id": df["case_id"].to_numpy(), "horizon_s": h, "p": p}))
        return pd.concat(out, ignore_index=True) if out else pd.DataFrame(columns=["case_id", "horizon_s", "p"])

    def save(self, dir):
        heads = {}
        for h, b in self.boosters.items():
            b.save_model(str(dir / f"h{h}.txt"))
            heads[str(h)] = {"model": f"h{h}.txt", "target_name": hname(h),
                             **({"calibration": self.cal[h]} if h in self.cal else {})}
        return {"features": self.features, "horizons_s": sorted(self.boosters), "heads": heads, "kind": "lightgbm",
                "deployable": False, "vocab": self.vocab, "fit_info": self.info, "label": "gfw_gap_start"}

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
    "type": "object", "additionalProperties": False, "required": ["model"],
    "properties": {
        "model": {"type": "string", "enum": ["lgbm", "baseline", "global_rate"]},
        "seed": {"type": "integer", "minimum": 0, "maximum": 10_000},
        "drop_features": {"type": "array", "maxItems": 20, "items": {"type": "string", "enum": D.FEATURES}},
        "num_leaves": {"type": "integer", "minimum": 4, "maximum": 127},
        "learning_rate": {"type": "number", "minimum": 0.005, "maximum": 0.3},
        "n_estimators": {"type": "integer", "minimum": 20, "maximum": 2000},
        "min_child_samples": {"type": "integer", "minimum": 20, "maximum": 5000},
        "feature_fraction": {"type": "number", "minimum": 0.2, "maximum": 1.0},
        "bagging_fraction": {"type": "number", "minimum": 0.3, "maximum": 1.0},
        "lambda_l2": {"type": "number", "minimum": 0, "maximum": 100},
        "pos_weight": {"oneOf": [{"type": "string", "enum": ["balanced"]},
                                 {"type": "number", "minimum": 1, "maximum": 1000}]},
        "max_pos_weight": {"type": "number", "minimum": 1, "maximum": 1000},
        "cal_frac": {"type": "number", "minimum": 0.1, "maximum": 0.5},
        "train_window_days": {"type": "integer", "minimum": 14, "maximum": 3650},
        "min_category_rows": {"type": "integer", "minimum": 10, "maximum": 10000},
    },
}


class GodarkGfwTarget(TargetSpec):
    name = "godark_gfw"
    horizons_s = HORIZONS
    primary_horizons_s = PRIMARY
    statistic = "mean"
    loss_name = "log_loss"
    loss_unit = ""
    strata = ["region", "type_band"]
    baseline = "baseline"
    default_config = {"model": "lgbm", "seed": 7, "num_leaves": 15, "learning_rate": 0.03, "n_estimators": 300,
                      "min_child_samples": 300, "lambda_l2": 10.0, "pos_weight": "balanced", "cal_frac": 0.3}
    config_schema = CONFIG_SCHEMA
    group_by_ship = False
    models = {"lgbm": Lgbm, "baseline": Baseline, "global_rate": GlobalRate}
    report_notes = [
        "Labels are Global Fishing Watch gap events (AIS likely switched off on purpose; only gaps of 12 h or more "
        "starting 50 nm or more from shore are published), worldwide, for ships GFW saw in our four regions. "
        "Features use only GFW rows public at the case's time. GFW data is CC BY-NC 4.0.",
        "7-day labels are reported only: too few positives to judge.",
    ]

    def holdout_bounds(self, examples):
        return TEST_START, TEST_END

    def load_examples(self, cfg, data):
        p = Path(data) if data else D.DEFAULT_OUT
        if p.is_dir():   # a cache directory: build from it
            return D.build(p)[0]
        return pd.read_parquet(p)

    def score(self, examples, preds):
        ex = examples.set_index("case_id")
        rows = []
        for h in self.horizons_s:
            col = D.label_col(h)
            p = preds[preds["horizon_s"] == h].set_index("case_id")
            j = p.join(ex[[col, "mmsi", "as_of", "region", "type_group"]], how="inner")
            j = j[j[col].notna()]
            if j.empty:
                continue
            y, pp = j[col].to_numpy(float), j["p"].to_numpy(float)
            tg = j["type_group"].astype(str)
            rows.append(pd.DataFrame({
                "case_id": j.index.to_numpy(), "mmsi": j["mmsi"].to_numpy(), "as_of": j["as_of"].to_numpy(),
                "horizon_s": h, "loss": log_loss(y, pp), "y": y, "p": pp, "brier": (pp - y) ** 2,
                "region": j["region"].astype(str).to_numpy(),
                "type_band": np.where(tg.isin(["FISHING", "CARGO", "TANKER", "PASSENGER"]), tg, "OTHER")}))
        return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(columns=["case_id", "horizon_s", "loss"])

    def summarise(self, scored):
        out = {}
        for h, g in scored.groupby("horizon_s"):
            y, p = g["y"].to_numpy(), g["p"].to_numpy()
            out[str(h)] = {"target_name": hname(int(h)), "n": int(len(g)), "positives": int(y.sum()),
                           "positive_ships": int(g.loc[g["y"] > 0, "mmsi"].nunique()), "base_rate": float(y.mean()),
                           "log_loss": float(g["loss"].mean()), "brier": float(g["brier"].mean()),
                           "auc_pr": auc_pr(y, p), "ece": ece(y, p), "calibration_curve": calibration_curve(y, p)}
        return out

    def calibration(self, scored):
        return [{"name": "ece", "horizon_s": int(h), "value": ece(g["y"].to_numpy(), g["p"].to_numpy()),
                 "nominal": 0.0, "tol": 0.05} for h, g in scored.groupby("horizon_s")]

    def sanity(self, summary):
        return [f"AUC-PR {m['auc_pr']:.3f} at {h} s is too good to be true: check for leakage"
                for h, m in summary.items() if m.get("auc_pr", 0) > 0.95]

    def report_sections(self):
        from ml.godark_gfw.curve import render_section
        p = DEFAULT_ARTIFACTS / "reports" / CURVE_FILE
        return [render_section(json.loads(p.read_text()))] if p.exists() else []


SPEC = GodarkGfwTarget()
