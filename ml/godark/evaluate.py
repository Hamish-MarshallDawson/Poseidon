"""Train and evaluate go-dark risk models on the live-AIS examples, write the report and the deployable artifact (#121).

    ml/.venv/bin/python -m ml.godark.evaluate [--examples PATH] [--out DIR] [--artifacts DIR]

Splits (stated in the report):
- 1 h: time split. Held-out = made_at in the last HOLDOUT_FRAC of the labelled 1 h grid times; training ends one
  horizon (the embargo) before it, so no training label window overlaps the held-out period.
- 6 h: labels exist only for a short stretch of made_at so far (the data started 7 Nov 16:51 and ingest was down
  21:57 to 23:36), too short for a time split with a 6 h embargo. So 6 h uses a ship-disjoint split over the same
  period: held-out ships never appear in training. This is weaker than a time split and the report says so.
- 24 h: no labels yet (needs 24 h of data after made_at).

Intervals: 95% bootstrap over ships (cluster bootstrap, paired: model and reference scored on the same resampled
ships). Skill = 1 - Brier_model / Brier_reference.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
import time
import os
from pathlib import Path

import numpy as np
import pandas as pd

from ml.core.registry import save_artifact
from ml.godark import PRIMARY_HORIZON_S, TARGET_NAMES
from ml.godark import dataset as D
from ml.godark.target import SPEC, Baseline, GlobalRate, Lgbm, auc_pr, calibration_curve, ece, label_col, log_loss

HOLDOUT_FRAC = 0.25
B = 1000
SEED = 7
OUT = D.OUT / "report"
ARTIFACTS = (Path(os.environ.get("POSEIDON_DATA", "/home/aiden/data/poseidon")) / "models")


def iso(ms: int) -> str:
    return dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc).strftime("%d %b %H:%M")


def split(ex: pd.DataFrame, h: int, flag: str = "deliberate_candidate"):
    col = label_col(h, flag)
    d = ex[ex[col].notna()]
    t = np.sort(d["as_of"].unique())
    if h <= 3600:
        cut = t[int(len(t) * (1 - HOLDOUT_FRAC))]
        test = d[d["as_of"] >= cut]
        train = d[d["as_of"] < cut - h * 1000]
        how = (f"time split: held-out made_at {iso(cut)} to {iso(int(t[-1]))} UTC; training made_at "
               f"{iso(int(t[0]))} to {iso(int(train['as_of'].max()))} (embargo {h // 3600} h)")
    else:
        ships = np.sort(d["mmsi"].unique())
        rng = np.random.default_rng(SEED)
        held = set(rng.choice(ships, int(len(ships) * HOLDOUT_FRAC), replace=False).tolist())
        m = d["mmsi"].isin(held)
        test, train = d[m], d[~m]
        how = (f"ship-disjoint split (not a time split): made_at {iso(int(t[0]))} to {iso(int(t[-1]))} UTC, "
               f"{len(held)} held-out ships never in training")
    return train, test, how


def holdout_hash(test: pd.DataFrame) -> str:
    return hashlib.sha256(",".join(sorted(test["case_id"])).encode()).hexdigest()[:16]


def metrics(y: np.ndarray, p: np.ndarray) -> dict:
    return {"n": int(len(y)), "positives": int(y.sum()), "log_loss": float(log_loss(y, p).mean()),
            "brier": float(((p - y) ** 2).mean()), "auc_pr": auc_pr(y, p), "ece": ece(y, p)}


def paired_skill(y, p_m, p_r, ships, B: int = B) -> dict:
    """Brier skill of model over reference, and log-loss difference, with a paired cluster bootstrap over ships."""
    bm, br = (p_m - y) ** 2, (p_r - y) ** 2
    lm, lr = log_loss(y, p_m), log_loss(y, p_r)
    codes, uniq = pd.factorize(ships)
    k = len(uniq)
    sums = lambda v: np.bincount(codes, weights=v, minlength=k)  # noqa: E731
    sbm, sbr, slm, slr, cnt = sums(bm), sums(br), sums(lm), sums(lr), np.bincount(codes, minlength=k)
    rng = np.random.default_rng(SEED)
    skills, dll = np.empty(B), np.empty(B)
    for i in range(B):
        w = np.bincount(rng.integers(0, k, k), minlength=k)
        n = (w * cnt).sum()
        skills[i] = 1 - (w * sbm).sum() / max((w * sbr).sum(), 1e-12)
        dll[i] = ((w * slr).sum() - (w * slm).sum()) / n
    return {"skill_brier": float(1 - bm.sum() / br.sum()),
            "skill_brier_ci": [float(np.quantile(skills, 0.025)), float(np.quantile(skills, 0.975))],
            "logloss_gain": float(lr.mean() - lm.mean()),
            "logloss_gain_ci": [float(np.quantile(dll, 0.025)), float(np.quantile(dll, 0.975))]}


def evaluate(ex: pd.DataFrame, flag: str = "deliberate_candidate", artifacts: Path | None = None,
             label_source: str = "replay") -> dict:
    res = {"label": flag, "label_source": label_source, "horizons": {}}
    for h in sorted(SPEC.horizons_s, key=lambda x: (x != PRIMARY_HORIZON_S, x)):   # dark_6h first
        col = label_col(h, flag)
        if ex[col].notna().sum() == 0:
            res["horizons"][str(h)] = {"skipped": "no labelled rows yet (needs that long after made_at)"}
            continue
        train, test, how = split(ex, h, flag)
        # The models read the primary label column; relabel for the secondary flags.
        tr, te = train.copy(), test.copy()
        if flag != "deliberate_candidate":
            for hh in SPEC.horizons_s:
                tr[label_col(hh)] = tr[label_col(hh, flag)]
                te[label_col(hh)] = te[label_col(hh, flag)]
        y = te[col].to_numpy(float)
        ships = te["mmsi"].to_numpy()
        models = {
            "global_rate": GlobalRate().fit(tr, {}),
            "baseline": Baseline().fit(tr, {}),
            "lgbm_track": Lgbm().fit(tr, {**SPEC.default_config, "features": "track"}),
            "lgbm_context": Lgbm().fit(tr, {**SPEC.default_config, "features": "track+context"}),
        }
        hres = {"split": how, "holdout_hash": holdout_hash(te), "n_train": int(len(tr)),
                "train_positives": int(tr[label_col(h)].sum()), "models": {}}
        preds = {}
        for name, m in models.items():
            pr = m.predict(te)
            pr = pr[pr["horizon_s"] == h].set_index("case_id")["p"]
            if pr.empty:
                hres["models"][name] = {"skipped": getattr(m, "info", {}).get(str(h), "no head")}
                continue
            p = pr.reindex(te["case_id"]).to_numpy(float)
            preds[name] = p
            hres["models"][name] = {**metrics(y, p), "calibration_curve": calibration_curve(y, p)}
        for name, p in preds.items():
            for ref in ("global_rate", "baseline"):
                if name != ref and ref in preds:
                    hres["models"][name][f"vs_{ref}"] = paired_skill(y, p, preds[ref], ships)
        for name in ("lgbm_track", "lgbm_context"):
            m = models[name]
            if h in m.boosters:
                gain = m.boosters[h].feature_importance("gain")
                order = np.argsort(gain)[::-1][:12]
                hres["models"][name]["top_features"] = [[m.features[i], float(gain[i] / gain.sum())] for i in order]
                hres["models"][name]["fit_info"] = m.info.get(str(h))
        # Strata for the deployable model.
        if "lgbm_track" in preds:
            te2 = te.assign(p=preds["lgbm_track"], pb=preds["baseline"], y=y)
            te2["speed_band"] = pd.cut(te2["sog_kn"], [-1, 5, 12, 1e9], labels=["<5kn", "5-12kn", ">12kn"]).astype(str)
            te2["src"] = np.where(te2["src_digitraffic"] > 0, "digitraffic", "aisstream")
            strata = {}
            for s in ("type_group", "speed_band", "src"):
                for v, g in te2.groupby(s):
                    if len(g) >= 30 and g["y"].sum() >= 3:
                        bm, bb = ((g.p - g.y) ** 2).mean(), ((g.pb - g.y) ** 2).mean()
                        strata[f"{s}={v}"] = {"n": int(len(g)), "positives": int(g.y.sum()),
                                              "auc_pr": auc_pr(g.y.to_numpy(), g.p.to_numpy()),
                                              "skill_brier_vs_baseline": float(1 - bm / bb) if bb > 0 else None}
            hres["strata_lgbm_track"] = strata
        res["horizons"][str(h)] = hres
        if artifacts is not None and flag == "deliberate_candidate":
            res.setdefault("_models", {})[h] = models["lgbm_track"]
    return res


def write_artifact(ex: pd.DataFrame, artifacts: Path, results: dict) -> Path:
    """Fit the deployable model (shared track features only) on every labelled row and write the backend artifact."""
    m = Lgbm().fit(ex, {**SPEC.default_config, "features": "track"})
    version = f"godark-lgbm-{dt.datetime.now(dt.timezone.utc):%Y%m%dT%H%M%S}"
    data_hash = hashlib.sha256(pd.util.hash_pandas_object(ex[["case_id"]], index=False).values.tobytes()).hexdigest()
    metrics_ = {h: {k: v for k, v in r["models"].get("lgbm_track", {}).items()
                    if k in ("n", "positives", "log_loss", "brier", "auc_pr", "ece", "vs_baseline")}
                for h, r in results["horizons"].items() if "models" in r}
    path = artifacts / version
    save_artifact(m, path, {"version": version, "data_hash": data_hash[:16], "metrics": metrics_,
                            "train_from": int(ex["as_of"].min()), "train_to": int(ex["as_of"].max()),
                            "note": "labels from our own gap detector (dvm/gaps.py replayed over Tiger positions)"})
    return path


# ---------------------------------------------------------------- report

def _fmt(x, d=3):
    return "–" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:.{d}f}"


def _ci(c):
    return f"[{c[0]:+.3f}, {c[1]:+.3f}]"


def markdown(all_res: dict) -> str:
    L = ["# Go-dark risk: first results (#121)", "",
         f"Generated {all_res['generated']} from {all_res['data']}.", "",
         "**Our own gap detector made these labels.** A positive is a `deliberate_candidate` gap of ours (the backend's "
         "`dvm/gaps.py`, replayed over every stored Tiger position) starting within the horizon. It says the ship went "
         "quiet where other ships were still heard, not that it switched off. GFW gap events (issue #112) are the "
         "independent check offshore and are not used here yet.", "",
         "Population: moving Class A ships (at least 1 kn, not at anchor or moored) heard in the last 10 minutes, on "
         "a 10-minute grid. Intervals: 95% paired bootstrap over ships. Skill = 1 - Brier / Brier of the reference.",
         ""]
    for r in all_res["runs"]:
        L += [f"## Label `{r['label']}` (label source: {r['label_source']})", ""]
        for h, hr in r["horizons"].items():
            name = TARGET_NAMES[int(h)]
            L.append(f"### {name} ({int(h)} s){' (primary)' if int(h) == PRIMARY_HORIZON_S else ''}")
            if "skipped" in hr:
                L += ["", f"Skipped: {hr['skipped']}.", ""]
                continue
            L += ["", f"{hr['split']}. Held-out hash `{hr['holdout_hash']}`; training rows {hr['n_train']} "
                  f"({hr['train_positives']} positive).", "",
                  "| Model | n | pos | AUC-PR | Brier | Log loss | ECE | Skill vs area x type base rate | Skill vs global rate |",
                  "|---|---|---|---|---|---|---|---|---|"]
            for name, m in hr["models"].items():
                if "skipped" in m:
                    L.append(f"| {name} | skipped: {m['skipped']} |||||||| ")
                    continue
                sb = m.get("vs_baseline")
                sg = m.get("vs_global_rate")
                L.append(f"| {name} | {m['n']} | {m['positives']} | {_fmt(m['auc_pr'])} | {_fmt(m['brier'], 4)} | "
                         f"{_fmt(m['log_loss'], 4)} | {_fmt(m['ece'])} | "
                         f"{_fmt(sb['skill_brier']) + ' ' + _ci(sb['skill_brier_ci']) if sb else '–'} | "
                         f"{_fmt(sg['skill_brier']) + ' ' + _ci(sg['skill_brier_ci']) if sg else '–'} |")
            tf = hr["models"].get("lgbm_context", {}).get("top_features")
            if tf:
                L += ["", "Top features (lgbm_context, share of gain): " +
                      ", ".join(f"{n} {v:.2f}" for n, v in tf[:8]) + "."]
            st = hr.get("strata_lgbm_track")
            if st and r["label"] == "deliberate_candidate":
                L += ["", "Strata (lgbm_track, n >= 30): " + "; ".join(
                    f"{k} n={v['n']} AUC-PR {_fmt(v['auc_pr'])} skill {_fmt(v['skill_brier_vs_baseline'])}"
                    for k, v in st.items()) + "."]
            L.append("")
    if all_res.get("artifact"):
        L += ["## Deployable artifact", "", f"`{all_res['artifact']}`: lgbm with the shared track features only "
              "(`dvm.predict.features`, feature_version f1), fitted on every labelled row, isotonic calibration as "
              "breakpoints. lgbm_context is not deployable until its context features are in the live predictor.", ""]
    return "\n".join(L)


def html_report(md: str, all_res: dict) -> str:
    """A static page: the markdown as preformatted sections plus calibration curves as inline SVG."""
    def curve_svg(cc, title):
        w, hgt, pad = 220, 220, 28
        mx = max([c["p_mean"] for c in cc] + [c["y_rate"] for c in cc] + [0.05])
        sx = lambda v: pad + v / mx * (w - 2 * pad)  # noqa: E731
        sy = lambda v: hgt - pad - v / mx * (hgt - 2 * pad)  # noqa: E731
        pts = " ".join(f"{sx(c['p_mean']):.1f},{sy(c['y_rate']):.1f}" for c in cc)
        return (f'<figure><svg viewBox="0 0 {w} {hgt}" width="{w}" height="{hgt}" role="img">'
                f'<line x1="{sx(0)}" y1="{sy(0)}" x2="{sx(mx)}" y2="{sy(mx)}" class="diag"/>'
                f'<polyline points="{pts}" class="cal"/>'
                + "".join(f'<circle cx="{sx(c["p_mean"]):.1f}" cy="{sy(c["y_rate"]):.1f}" r="3"/>' for c in cc)
                + f'<text x="{pad}" y="{hgt - 6}">predicted (max {mx:.2f})</text></svg>'
                f'<figcaption>{html.escape(title)}</figcaption></figure>')
    figs = []
    for r in all_res["runs"]:
        if r["label"] != "deliberate_candidate":
            continue
        for h, hr in r["horizons"].items():
            for name in ("baseline", "lgbm_track", "lgbm_context"):
                cc = hr.get("models", {}).get(name, {}).get("calibration_curve")
                if cc:
                    figs.append(curve_svg(cc, f"{TARGET_NAMES[int(h)]} {name} ({r['label_source']} labels)"))
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport"
content="width=device-width,initial-scale=1"><title>Go-dark risk report</title><style>
:root{{--bg:#fff;--fg:#1a1a1a;--mut:#666;--acc:#1f6feb}}
@media (prefers-color-scheme:dark){{:root{{--bg:#111;--fg:#eee;--mut:#999;--acc:#58a6ff}}}}
body{{background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif;max-width:1100px;margin:0 auto;padding:16px}}
pre{{white-space:pre-wrap;font:13px/1.45 ui-monospace,monospace}} figure{{display:inline-block;margin:8px}}
svg text{{fill:var(--mut);font-size:10px}} .diag{{stroke:var(--mut);stroke-dasharray:3 3}}
.cal{{fill:none;stroke:var(--acc);stroke-width:2}} circle{{fill:var(--acc)}} figcaption{{color:var(--mut);font-size:12px}}
</style></head><body><pre>{html.escape(md)}</pre><h2>Calibration (held-out, 10 equal-count bins; dashed = perfect)</h2>
{''.join(figs)}</body></html>"""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--examples", type=Path, default=D.OUT / "examples.parquet")
    ap.add_argument("--table-examples", type=Path, default=D.OUT / "examples_table.parquet")
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--artifacts", type=Path, default=ARTIFACTS)
    ap.add_argument("--no-artifact", action="store_true")
    a = ap.parse_args()
    t = time.time()
    ex = pd.read_parquet(a.examples)
    runs = [evaluate(ex, "deliberate_candidate", label_source="replay"),
            evaluate(ex, "unknown", label_source="replay")]
    if a.table_examples.exists():
        et = pd.read_parquet(a.table_examples)
        # The stored flags have a full neighbour baseline only from 8 Nov 00:36 (see replay.py).
        et = et[et["as_of"] >= 1794098160000]
        runs.append(evaluate(et, "deliberate_candidate", label_source="stored gaps table, from 8 Nov 00:36"))
    meta = json.loads((D.OUT / "replay_meta.json").read_text())
    all_res = {"generated": dt.datetime.now(dt.timezone.utc).strftime("%d %b %Y %H:%M UTC"),
               "data": f"Tiger positions {iso(meta['data_from'])} to {iso(meta['data_to'])} UTC "
                       f"({meta['positions']} rows; replayed gaps {meta['gaps']})",
               "runs": runs}
    if not a.no_artifact:
        all_res["artifact"] = str(write_artifact(ex, a.artifacts, runs[0]))
    for r in runs:
        r.pop("_models", None)
    a.out.mkdir(parents=True, exist_ok=True)
    md = markdown(all_res)
    (a.out / "report.json").write_text(json.dumps(all_res, indent=1, default=float))
    (a.out / "report.md").write_text(md)
    (a.out / "report.html").write_text(html_report(md, all_res))
    print(md)
    print(f"\n{time.time() - t:.0f} s; report in {a.out}")


if __name__ == "__main__":
    main()
