"""A small synthetic target with the same shape as route, so the loop runs end to end without real data (tests,
rehearsals, `--target toy`). Ships move along a line; the distance they cover by +1 h and +3 h is dead reckoning
(speed x time) times a factor that depends on a few features, plus noise that is larger for fishing ships.
The baseline is dead reckoning; `linear` (ridge, JSON coefficients) and `gbm` (LightGBM text dumps) learn the
factor; each predicts a radius from split-conformal residual quantiles. Loss: absolute error in metres.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from ml.core.registry import Model
from ml.core.target import TargetSpec

HORIZONS = [3600, 10800]
FEATURES = ["f1", "f2", "f3", "f1_x_f2", "type_code"]
TYPES = ["cargo", "tanker", "fishing"]
KN = 1852 / 3600   # knots to m/s


def make_examples(n_ships: int = 40, days: int = 8, step_h: int = 1, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    t0 = 1_793_000_000_000   # epoch ms, an arbitrary fixed start
    rows = []
    for s in range(n_ships):
        mmsi = 219_000_000 + s
        typ = TYPES[s % 3]
        base_speed = {"cargo": 13, "tanker": 11, "fishing": 6}[typ] + rng.normal(0, 1.5)
        for k in range(0, days * 24, step_h):
            f1, f2, f3 = rng.normal(0, 1), rng.normal(0, 1), rng.normal(0, 1)   # f3 is noise: no signal
            speed = max(0.5, base_speed + rng.normal(0, 1))
            row = {"case_id": f"toy-{mmsi}-{k}", "mmsi": mmsi, "as_of": t0 + k * 3_600_000, "speed_kn": speed,
                   "f1": f1, "f2": f2, "f3": f3, "f1_x_f2": f1 * f2, "type_code": TYPES.index(typ),
                   "ship_type": typ, "speed_class": "slow" if speed < 8 else "fast"}
            factor = 1 + 0.15 * f1 + 0.10 * f1 * f2 + (0.05 * np.tanh(f2) if typ != "fishing" else -0.1)
            for h in HORIZONS:
                dr = speed * KN * h
                noise = rng.normal(0, (0.10 if typ == "fishing" else 0.04) * dr)
                row[f"truth_{h}"] = dr * factor + noise
            rows.append(row)
    return pd.DataFrame(rows)


def _dr(df: pd.DataFrame, h: int) -> np.ndarray:
    return df["speed_kn"].to_numpy(float) * KN * h


class _Conformal:
    """Radii from held-back residual quantiles (split conformal): the last 20% of the training cases by time."""

    @staticmethod
    def split(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
        cut = df["as_of"].quantile(0.8)
        fit, cal = df[df["as_of"] <= cut], df[df["as_of"] > cut]
        return (fit, cal) if len(cal) >= 20 else (df, df)

    @staticmethod
    def radii(resid: np.ndarray) -> dict:
        n = len(resid)
        q = lambda p: float(np.quantile(resid, min(1.0, np.ceil((n + 1) * p) / n)))   # noqa: E731
        return {"r80": q(0.8), "r95": q(0.95)}


class ToyModel(Model):
    target = "toy"
    name = ""

    def __init__(self):
        self.features: list[str] = []
        self.radius: dict[str, dict] = {}

    def factor(self, df: pd.DataFrame, h: int) -> np.ndarray:
        raise NotImplementedError

    def fit_factor(self, df: pd.DataFrame, cfg: dict) -> None:
        raise NotImplementedError

    def fit(self, train_df, cfg):
        self.features = list(cfg.get("features") or FEATURES)
        fit, cal = _Conformal.split(train_df)
        self.fit_factor(fit, cfg)
        for h in HORIZONS:
            resid = np.abs(_dr(cal, h) * self.factor(cal, h) - cal[f"truth_{h}"].to_numpy(float))
            self.radius[str(h)] = _Conformal.radii(resid)
        return self

    def predict(self, df):
        out = []
        for h in HORIZONS:
            out.append(pd.DataFrame({"case_id": df["case_id"].to_numpy(), "horizon_s": h,
                                     "pred": _dr(df, h) * self.factor(df, h),
                                     "radius_m_80": self.radius[str(h)]["r80"],
                                     "radius_m_95": self.radius[str(h)]["r95"]}))
        return pd.concat(out, ignore_index=True)

    def _meta(self) -> dict:
        return {"features": self.features, "horizons_s": HORIZONS, "radius": self.radius}


class Baseline(ToyModel):
    name = "baseline"

    def fit_factor(self, df, cfg):
        self.features = ["speed_kn"]

    def factor(self, df, h):
        return np.ones(len(df))

    def save(self, dir):
        (dir / "baseline.json").write_text(json.dumps(self._meta()))
        return self._meta()

    @classmethod
    def load(cls, dir):
        m, d = cls(), json.loads((Path(dir) / "baseline.json").read_text())
        m.features, m.radius = d["features"], d["radius"]
        return m


class Linear(ToyModel):
    name = "linear"

    def fit_factor(self, df, cfg):
        lam = float(cfg.get("l2", 1.0))
        X = np.c_[np.ones(len(df)), df[self.features].to_numpy(float)]
        self.coef = {}
        for h in HORIZONS:
            y = df[f"truth_{h}"].to_numpy(float) / _dr(df, h)
            w = _weights(df, cfg)
            A = X.T @ (X * w[:, None]) + lam * np.eye(X.shape[1])
            self.coef[str(h)] = np.linalg.solve(A, X.T @ (y * w)).tolist()

    def factor(self, df, h):
        X = np.c_[np.ones(len(df)), df[self.features].to_numpy(float)]
        return X @ np.array(self.coef[str(h)])

    def save(self, dir):
        (dir / "linear.json").write_text(json.dumps({**self._meta(), "coef": self.coef}))
        return self._meta()

    @classmethod
    def load(cls, dir):
        m, d = cls(), json.loads((Path(dir) / "linear.json").read_text())
        m.features, m.radius, m.coef = d["features"], d["radius"], d["coef"]
        return m


class GBM(ToyModel):
    name = "gbm"

    def fit_factor(self, df, cfg):
        import lightgbm as lgb
        params = {"objective": "huber" if cfg.get("loss") == "huber" else "regression", "verbosity": -1,
                  "learning_rate": float(cfg.get("learning_rate", 0.05)),
                  "num_leaves": int(cfg.get("num_leaves", 15)), "seed": int(cfg.get("seed", 0)),
                  "deterministic": True, "num_threads": 2,
                  "feature_fraction": 0.9, "bagging_fraction": 0.9, "bagging_freq": 1}
        self.boosters = {}
        for h in HORIZONS:
            y = df[f"truth_{h}"].to_numpy(float) / _dr(df, h)
            ds = lgb.Dataset(df[self.features].to_numpy(float), y, weight=_weights(df, cfg))
            self.boosters[str(h)] = lgb.train(params, ds, num_boost_round=int(cfg.get("n_estimators", 200)))

    def factor(self, df, h):
        return self.boosters[str(h)].predict(df[self.features].to_numpy(float))

    def save(self, dir):
        for h, b in self.boosters.items():
            b.save_model(str(dir / f"gbm_{h}.txt"))
        (dir / "gbm.json").write_text(json.dumps(self._meta()))
        return self._meta()

    @classmethod
    def load(cls, dir):
        import lightgbm as lgb
        m, d = cls(), json.loads((Path(dir) / "gbm.json").read_text())
        m.features, m.radius = d["features"], d["radius"]
        m.boosters = {str(h): lgb.Booster(model_file=str(Path(dir) / f"gbm_{h}.txt")) for h in HORIZONS}
        return m


def _weights(df: pd.DataFrame, cfg: dict) -> np.ndarray:
    if cfg.get("sample_weight") == "recent":
        t = df["as_of"].to_numpy(float)
        return 0.5 + (t - t.min()) / max(1.0, t.max() - t.min())
    return np.ones(len(df))


class ToyTarget(TargetSpec):
    name = "toy"
    horizons_s = HORIZONS
    primary_horizons_s = HORIZONS
    statistic = "median"
    loss_name = "error_m"
    loss_unit = "m"
    strata = ["ship_type", "speed_class"]
    baseline = "baseline"
    models = {"baseline": Baseline, "linear": Linear, "gbm": GBM}
    default_config = {"model": "linear", "features": ["f1", "f2"], "l2": 1.0, "seed": 0}
    config_schema = {
        "type": "object", "required": ["model", "seed"], "additionalProperties": False,
        "properties": {
            "model": {"type": "string", "enum": ["baseline", "linear", "gbm"]},
            "seed": {"type": "integer", "minimum": 0, "maximum": 1_000_000},
            "features": {"type": "array", "items": {"type": "string", "enum": FEATURES}, "minItems": 1,
                         "uniqueItems": True},
            "l2": {"type": "number", "minimum": 0, "maximum": 100},
            "n_estimators": {"type": "integer", "minimum": 20, "maximum": 400},
            "learning_rate": {"type": "number", "minimum": 0.01, "maximum": 0.3},
            "num_leaves": {"type": "integer", "minimum": 4, "maximum": 64},
            "loss": {"type": "string", "enum": ["l2", "huber"]},
            "train_window_days": {"type": "integer", "minimum": 1, "maximum": 30},
            "sample_weight": {"type": "string", "enum": ["none", "recent"]}}}
    dry_run_proposals = [
        {"config": {"model": "linear", "features": ["f1", "f2", "f1_x_f2"], "l2": 1.0, "seed": 0},
         "rationale": "dry run: add the f1 x f2 interaction the champion lacks"},
        {"config": {"model": "gbm", "features": FEATURES, "n_estimators": 200, "learning_rate": 0.05,
                    "num_leaves": 15, "seed": 0}, "rationale": "dry run: gradient boosting on every feature"},
        {"config": {"model": "linear", "features": ["f3"], "l2": 1.0, "seed": 0},
         "rationale": "dry run: a noise-only feature, which should lose"},
        {"config": {"model": "linear", "features": ["f1", "f2", "f1_x_f2", "type_code"], "l2": 5.0, "seed": 0},
         "rationale": "dry run: add ship type for the fishing stratum"},
        {"config": {"model": "gbm", "features": FEATURES, "n_estimators": 400, "learning_rate": 0.05,
                    "num_leaves": 31, "seed": 0}, "rationale": "dry run: a bigger boosted model"},
        {"config": {"model": "gbm", "features": ["f1", "f2", "f1_x_f2", "type_code"], "n_estimators": 300,
                    "learning_rate": 0.05, "num_leaves": 15, "loss": "huber", "seed": 0},
         "rationale": "dry run: drop the noise feature and use a robust loss"},
        {"config": {"model": "gbm", "features": FEATURES, "n_estimators": 200, "learning_rate": 0.05,
                    "num_leaves": 15, "train_window_days": 2, "seed": 0},
         "rationale": "dry run: train on the last two days only"},
        {"config": {"model": "gbm", "features": ["f1", "f2", "f1_x_f2", "type_code"], "n_estimators": 200,
                    "learning_rate": 0.1, "num_leaves": 8, "sample_weight": "recent", "seed": 0},
         "rationale": "dry run: weight recent cases more"},
    ]

    def __init__(self, **make_kw):
        self.make_kw = make_kw

    def load_examples(self, cfg, data):
        if data:
            return pd.read_parquet(data)
        return make_examples(**self.make_kw)

    def score(self, examples, preds):
        ex = examples.set_index("case_id")
        out = []
        for h in self.horizons_s:
            p = preds[preds["horizon_s"] == h].set_index("case_id")
            j = p.join(ex[["mmsi", "as_of", f"truth_{h}"] + self.strata], how="inner")
            j = j[j[f"truth_{h}"].notna()]
            err = np.abs(j["pred"] - j[f"truth_{h}"])
            out.append(pd.DataFrame({"case_id": j.index, "mmsi": j["mmsi"].to_numpy(), "as_of": j["as_of"].to_numpy(),
                                     "horizon_s": h, "loss": err.to_numpy(),
                                     "in80": (err <= j["radius_m_80"]).to_numpy(),
                                     "in95": (err <= j["radius_m_95"]).to_numpy(),
                                     **{s: j[s].to_numpy() for s in self.strata}}))
        return pd.concat(out, ignore_index=True)

    def summarise(self, scored):
        return {str(h): {"n": len(g), "median_m": float(g["loss"].median()), "p90_m": float(g["loss"].quantile(0.9)),
                         "cov80": float(g["in80"].mean()), "cov95": float(g["in95"].mean())}
                for h, g in scored.groupby("horizon_s")}

    def calibration(self, scored):
        out = []
        for h, g in scored.groupby("horizon_s"):
            out.append({"name": "80% radius coverage", "horizon_s": int(h), "value": float(g["in80"].mean()),
                        "nominal": 0.80, "tol": 0.05})
            out.append({"name": "95% radius coverage", "horizon_s": int(h), "value": float(g["in95"].mean()),
                        "nominal": 0.95, "tol": 0.05})
        return out

    def sanity(self, summary):
        return [f"{h}s median error {v['median_m']:.1f} m is implausibly small" for h, v in summary.items()
                if v["median_m"] < 1.0]


SPEC = ToyTarget()
