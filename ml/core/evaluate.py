"""Frozen held-out sets, time splits with an embargo, rolling-origin folds, the paired bootstrap and the promotion
rule. Everything here is deterministic for a given input and seed; nothing here is editable by the proposer."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from ml.core.registry import DEFAULT_ARTIFACTS
from ml.core.target import TargetSpec

STRATUM_MIN_N = 30
STRATUM_MAX_WORSE = 0.10   # a stratum may not get more than 10% worse
CALIB_TOL = 0.05           # calibration within 5 points of nominal
ALPHA = 0.05               # 95% intervals, before the multiple-comparison correction
BOOTSTRAP_B = 2000


# ---------------------------------------------------------------- held-out sets

@dataclass
class Holdout:
    target: str
    name: str
    start: int            # epoch ms: first as_of in the block
    end: int              # epoch ms: last as_of in the block
    case_ids: list[str]
    ships: list[int]      # held-out ships (kept out of training when the target groups by ship)
    hash: str
    n: int
    created_at: str
    group_by_ship: bool

    def describe(self) -> dict:
        d = asdict(self)
        d.pop("case_ids")
        d.pop("ships")
        d["n_ships"] = len(self.ships)
        d["from"] = _iso(self.start)
        d["to"] = _iso(self.end)
        return d


def _iso(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, timezone.utc).isoformat(timespec="minutes")


def _hash_ids(ids: list[str]) -> str:
    return hashlib.sha256("\n".join(ids).encode()).hexdigest()[:16]


def holdout_dir(root: Path | None = None) -> Path:
    return (root or DEFAULT_ARTIFACTS) / "holdout"


def freeze_holdout(spec: TargetSpec, examples: pd.DataFrame, name: str = "v1", frac: float = 0.2,
                   root: Path | None = None) -> Holdout:
    """Freeze the latest `frac` of the examples' time span as the held-out set `name`. If it already exists it is
    returned unchanged: a frozen set is never rewritten (add a new name instead)."""
    path = holdout_dir(root) / f"{spec.name}-{name}.json"
    if path.exists():
        return load_holdout(spec.name, name, root)
    lo, hi = int(examples["as_of"].min()), int(examples["as_of"].max())
    start = hi - int(frac * (hi - lo))
    block = examples[examples["as_of"] >= start]
    if spec.group_by_ship:
        # Half of the ships seen in the block, chosen by a stable hash of the mmsi so a re-freeze picks the same.
        ships = sorted(int(m) for m in block["mmsi"].unique()
                       if int(hashlib.md5(str(int(m)).encode()).hexdigest(), 16) % 2 == 0)
        block = block[block["mmsi"].isin(ships)]
    else:
        ships = sorted(int(m) for m in block["mmsi"].unique())
    ids = sorted(map(str, block["case_id"]))
    if not ids:
        raise ValueError("the held-out block is empty: not enough data to freeze a held-out set")
    h = Holdout(spec.name, name, start, int(block["as_of"].max()), ids, ships, _hash_ids(ids), len(ids),
                datetime.now(timezone.utc).isoformat(timespec="seconds"), spec.group_by_ship)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(h)))
    return h


def load_holdout(target: str, name: str | None = None, root: Path | None = None) -> Holdout | None:
    """The named held-out set, or the newest one for the target."""
    d = holdout_dir(root)
    if name:
        paths = [d / f"{target}-{name}.json"]
    else:
        paths = sorted(d.glob(f"{target}-*.json"), key=lambda p: json.loads(p.read_text())["created_at"])[-1:]
    if not paths or not paths[0].exists():
        return None
    h = Holdout(**json.loads(paths[0].read_text()))
    if _hash_ids(h.case_ids) != h.hash:
        raise ValueError(f"held-out set {paths[0]} does not match its hash: it was edited")
    return h


# ---------------------------------------------------------------- splits

def embargo_ms(spec: TargetSpec) -> int:
    return max(spec.horizons_s) * 1000


def split(spec: TargetSpec, examples: pd.DataFrame, holdout: Holdout) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """(train, test, info). Test = the held-out cases present in `examples`. Train = cases whose whole label window
    ends before the held-out block starts (as_of < start - longest horizon), minus held-out ships if grouped."""
    ids = set(holdout.case_ids)
    is_test = examples["case_id"].astype(str).isin(ids)
    test = examples[is_test]
    train = examples[(examples["as_of"] < holdout.start - embargo_ms(spec)) & ~is_test]
    if holdout.group_by_ship:
        train = train[~train["mmsi"].isin(holdout.ships)]
    info = {"n_train": len(train), "n_test": len(test), "n_holdout_missing": len(ids) - len(test),
            "embargo_s": embargo_ms(spec) // 1000}
    return train, test, info


def rolling_folds(spec: TargetSpec, train: pd.DataFrame, n_folds: int = 3) -> list[tuple[pd.DataFrame, pd.DataFrame]]:
    """Expanding-window folds inside the training data: the last n_folds blocks of time are each a test block once,
    trained on everything before it minus the embargo. Folds with too little data on either side are skipped."""
    if n_folds <= 0 or train.empty:
        return []
    lo, hi = int(train["as_of"].min()), int(train["as_of"].max())
    width = (hi - lo) / (n_folds + 1)
    folds = []
    for i in range(n_folds):
        t0 = lo + width * (i + 1)
        t1 = t0 + width if i < n_folds - 1 else hi + 1
        fit = train[train["as_of"] < t0 - embargo_ms(spec)]
        val = train[(train["as_of"] >= t0) & (train["as_of"] < t1)]
        if len(fit) >= 50 and len(val) >= 20:
            folds.append((fit, val))
    return folds


# ---------------------------------------------------------------- statistics

def stat(x: np.ndarray, which: str) -> float:
    return float(np.median(x) if which == "median" else np.mean(x))


def paired(cand: pd.DataFrame, ref: pd.DataFrame, horizon_s: int) -> tuple[np.ndarray, np.ndarray, pd.DataFrame]:
    """Losses of two models on exactly the same cases at one horizon."""
    a = cand[cand["horizon_s"] == horizon_s]
    b = ref[ref["horizon_s"] == horizon_s][["case_id", "loss"]].rename(columns={"loss": "loss_ref"})
    m = a.merge(b, on="case_id", how="inner")
    return m["loss"].to_numpy(float), m["loss_ref"].to_numpy(float), m


def bootstrap(a: np.ndarray, b: np.ndarray, fn, alpha: float = ALPHA, B: int = BOOTSTRAP_B,
              seed: int = 0) -> tuple[float, float, float]:
    """Point estimate and (1 - alpha) percentile interval of fn(a, b), resampling cases jointly (paired)."""
    if len(a) == 0:
        return float("nan"), float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    reps = []
    for k in range(0, B, 64):   # in chunks: a (B, n) index matrix would be GBs for large held-out sets
        for i in rng.integers(0, len(a), size=(min(64, B - k), len(a))):
            reps.append(fn(a[i], b[i]))
    lo, hi = np.quantile(reps, [alpha / 2, 1 - alpha / 2])
    return float(fn(a, b)), float(lo), float(hi)


def skill_fn(which: str):
    """skill = 1 - stat(model) / stat(reference); positive is better than the reference."""
    def f(a, b):
        sb = stat(b, which)
        return 1.0 - stat(a, which) / sb if sb else float("nan")
    return f


def diff_fn(which: str):
    return lambda a, b: stat(a, which) - stat(b, which)


def skill_table(spec: TargetSpec, scored: pd.DataFrame, base: pd.DataFrame, alpha: float = ALPHA) -> dict:
    """Per horizon: n, model statistic, baseline statistic, skill with its paired bootstrap interval."""
    out = {}
    for h in spec.horizons_s:
        a, b, _ = paired(scored, base, h)
        if len(a) == 0:
            continue
        s, lo, hi = bootstrap(a, b, skill_fn(spec.statistic), alpha)
        out[str(h)] = {"n": len(a), "stat": stat(a, spec.statistic), "baseline_stat": stat(b, spec.statistic),
                       "skill": s, "skill_lo": lo, "skill_hi": hi, "win_rate": float(np.mean(a < b))}
    return out


def strata_table(spec: TargetSpec, scored: pd.DataFrame) -> dict:
    """Per stratum column, value and primary horizon: n and statistic (for the report and the rule)."""
    out: dict = {}
    for col in spec.strata:
        if col not in scored:
            continue
        for (h, v), g in scored[scored["horizon_s"].isin(spec.primary_horizons_s)].groupby(["horizon_s", col]):
            out.setdefault(col, []).append({"horizon_s": int(h), "value": str(v), "n": len(g),
                                            "stat": stat(g["loss"].to_numpy(float), spec.statistic)})
    return out


# ---------------------------------------------------------------- the promotion rule

def decide(spec: TargetSpec, cand: pd.DataFrame, ref: pd.DataFrame, n_comparisons: int = 1,
           ref_label: str = "champion") -> dict:
    """Does the candidate replace the reference? All of:
    1. at every primary horizon, the paired bootstrap interval of stat(cand) - stat(ref) lies below zero, at
       confidence 1 - ALPHA / n_comparisons (Bonferroni over the proposals tried in a round);
    2. every calibration check at a primary horizon is within its tolerance of nominal;
    3. no stratum value with n >= 30 (in both) is more than 10% worse than the reference.
    Anything else, including a tie, keeps the reference."""
    alpha = ALPHA / max(1, n_comparisons)
    reasons, horizons = [], {}
    for h in spec.primary_horizons_s:
        a, b, _ = paired(cand, ref, h)
        if len(a) == 0:
            reasons.append(f"no paired held-out cases at {h}s")
            continue
        d, lo, hi = bootstrap(a, b, diff_fn(spec.statistic), alpha)
        win = hi < 0
        horizons[str(h)] = {"n": len(a), "cand": stat(a, spec.statistic), "ref": stat(b, spec.statistic),
                            "diff": d, "lo": lo, "hi": hi, "win": bool(win)}
        if not win:
            reasons.append(f"{h}s: {spec.statistic} {spec.loss_name} difference {d:+.4g} "
                           f"[{lo:+.4g}, {hi:+.4g}] does not exclude zero in the candidate's favour")
    calib = [c for c in spec.calibration(cand) if c["horizon_s"] in spec.primary_horizons_s]
    for c in calib:
        c["ok"] = bool(abs(c["value"] - c["nominal"]) <= c.get("tol", CALIB_TOL))
        if not c["ok"]:
            reasons.append(f"{c['horizon_s']}s: {c['name']} {c['value']:.3f} is not within "
                           f"{c.get('tol', CALIB_TOL):.2f} of {c['nominal']:.2f}")
    worse = []
    for col in spec.strata:
        if col not in cand:
            continue
        for h in spec.primary_horizons_s:
            _, _, m = paired(cand, ref, h)
            for v, g in m.groupby(col):
                if len(g) < STRATUM_MIN_N:
                    continue
                sa, sb = stat(g["loss"].to_numpy(float), spec.statistic), stat(g["loss_ref"].to_numpy(float),
                                                                            spec.statistic)
                if sa > sb + STRATUM_MAX_WORSE * abs(sb):
                    worse.append({"stratum": col, "value": str(v), "horizon_s": h, "n": len(g), "cand": sa, "ref": sb})
                    reasons.append(f"{h}s: {col}={v} (n={len(g)}) is {sa / sb - 1:+.0%} worse" if sb
                                   else f"{h}s: {col}={v} is worse")
    return {"promote": not reasons, "against": ref_label, "alpha": alpha, "n_comparisons": n_comparisons,
            "horizons": horizons, "calibration": calib, "strata_worse": worse, "reasons": reasons}
