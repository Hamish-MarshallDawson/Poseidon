"""Learning curve for the GFW go-dark target: does more history make a better model? (#121)

    ml/.venv/bin/python -m ml.godark_gfw.curve [--data EXAMPLES.parquet] [--months 1,2,4,all]

Same test set every time: the frozen held-out set (September 2026). Training uses the newest 1, 2, 4 and all
available months before it, ending one embargo (30 days, the longest horizon) before the test month starts, so no
training label overlaps it. Each point is LightGBM (the default config) against the flag-and-type base rate fitted
on the same window, with paired bootstrap 95% intervals. Writes `<ML_ARTIFACTS>/reports/godark_gfw-learning_curve.json`,
which `python -m ml.core.report --target godark_gfw` renders as a section.
"""
from __future__ import annotations

import argparse
import html
import json
import math
import time
from datetime import datetime, timezone

import numpy as np

from ml.core import evaluate as ev
from ml.core.registry import DEFAULT_ARTIFACTS
from ml.godark_gfw import dataset as D
from ml.godark_gfw.target import CURVE_FILE, SPEC

MONTH_MS = 30 * D.D


def run(examples, months: list, cfg: dict | None = None, holdout_name: str = "v1", root=DEFAULT_ARTIFACTS,
        log=print) -> dict:
    cfg = cfg or dict(SPEC.default_config)
    hold = ev.load_holdout(SPEC.name, holdout_name, root) or ev.freeze_holdout(SPEC, examples, holdout_name, root=root)
    train_all, test, info = ev.split(SPEC, examples, hold)
    end = hold.start - ev.embargo_ms(SPEC)
    first = int(train_all["as_of"].min()) if len(train_all) else end
    avail = (end - first) / MONTH_MS
    points = []
    for m in months:
        t0 = time.monotonic()
        lo = first if m == "all" else end - int(m) * MONTH_MS
        pt = {"months": m, "months_used": round((end - max(lo, first)) / MONTH_MS, 2)}
        if m != "all" and lo < first - 3 * D.D:
            pt["skipped"] = f"only {avail:.1f} months of history before the embargo"
            points.append(pt)
            log(pt)
            continue
        tr = train_all[train_all["as_of"] >= lo]
        pt |= {"n_train": int(len(tr)), "ships_train": int(tr["mmsi"].nunique()),
               "train_from": _iso(tr["as_of"].min()), "train_to": _iso(tr["as_of"].max()), "horizons": {}}
        model = SPEC.models[cfg["model"]]().fit(tr, cfg)
        base = SPEC.models[SPEC.baseline]().fit(tr, cfg)
        s, b = SPEC.score(test, model.predict(test)), SPEC.score(test, base.predict(test))
        for h in SPEC.horizons_s:
            col = D.label_col(h)
            a, bb, mrg = ev.paired(s, b, h)
            if not len(a):
                continue
            sk, lo_, hi_ = ev.bootstrap(a, bb, ev.skill_fn("mean"))
            ll, ll_lo, ll_hi = ev.bootstrap(a, a, lambda x, _: float(np.mean(x)))
            ytr = tr[col].dropna()
            pt["horizons"][str(h)] = {
                "skill": sk, "skill_lo": lo_, "skill_hi": hi_, "log_loss": ll, "log_loss_lo": ll_lo,
                "log_loss_hi": ll_hi, "baseline_log_loss": float(np.mean(bb)), "n_test": int(len(a)),
                "test_positives": int(mrg["y"].sum()), "test_positive_ships": int(mrg.loc[mrg["y"] > 0, "mmsi"].nunique()),
                "train_positives": int(ytr.sum()),
                "train_positive_ships": int(tr.loc[tr[col] > 0, "mmsi"].nunique()),
                "auc_pr": SPEC.summarise(s[s["horizon_s"] == h])[str(h)]["auc_pr"],
                "auc_pr_baseline": SPEC.summarise(b[b["horizon_s"] == h])[str(h)]["auc_pr"],
                "fit": model.info.get(str(h))}
        pt["seconds"] = round(time.monotonic() - t0, 1)
        points.append(pt)
        log({k: v for k, v in pt.items() if k != "horizons"},
            {h: f"skill {v['skill']:+.3f} [{v['skill_lo']:+.3f},{v['skill_hi']:+.3f}] pos {v['train_positives']}/{v['test_positives']}"
             for h, v in pt["horizons"].items()})
    return {"target": SPEC.name, "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "config": cfg, "holdout": hold.describe(), "split": info, "train_end": _iso(end),
            "history_months_available": round(avail, 2), "primary_horizons_s": SPEC.primary_horizons_s,
            "points": points}


def _iso(ms) -> str:
    return datetime.fromtimestamp(int(ms) / 1000, timezone.utc).isoformat(timespec="minutes")


def _svg(curve: dict, h: str) -> str:
    pts = [p for p in curve["points"] if h in p.get("horizons", {})]
    if not pts:
        return "<p class='muted'>No points.</p>"
    W, H, L, R, T, B = 520, 220, 46, 16, 14, 34
    xs = [p["months_used"] for p in pts]
    vals = [p["horizons"][h] for p in pts]
    ys = [0.0] + [v["skill_lo"] for v in vals] + [v["skill_hi"] for v in vals]
    ys = [y for y in ys if not math.isnan(y)]
    y0, y1 = min(ys), max(ys)
    pad = (y1 - y0) * 0.08 or 0.05
    y0, y1 = y0 - pad, y1 + pad
    x1 = max(xs) * 1.08 or 1
    X = lambda x: L + x * (W - L - R) / x1   # noqa: E731
    Y = lambda y: T + (y1 - y) * (H - T - B) / (y1 - y0)   # noqa: E731
    o = [f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" aria-label="skill by months of history">']
    for fr in (0, 0.5, 1):
        yv = y0 + fr * (y1 - y0)
        o.append(f'<line x1="{L}" x2="{W - R}" y1="{Y(yv):.1f}" y2="{Y(yv):.1f}" stroke="var(--line)"/>'
                 f'<text x="{L - 6}" y="{Y(yv) + 4:.1f}" text-anchor="end">{yv:+.2f}</text>')
    o.append(f'<line x1="{L}" x2="{W - R}" y1="{Y(0):.1f}" y2="{Y(0):.1f}" stroke="var(--zero)" stroke-dasharray="4 3"/>'
             f'<text x="{W - R}" y="{Y(0) - 4:.1f}" text-anchor="end">base rate</text>')
    o.append('<path d="' + " ".join(f"{'M' if i == 0 else 'L'}{X(x):.1f},{Y(v['skill']):.1f}"
                                    for i, (x, v) in enumerate(zip(xs, vals))) +
             '" fill="none" stroke="var(--accent)" stroke-width="2"/>')
    for x, v, p in zip(xs, vals, pts):
        o.append(f'<line x1="{X(x):.1f}" x2="{X(x):.1f}" y1="{Y(v["skill_lo"]):.1f}" y2="{Y(v["skill_hi"]):.1f}" '
                 f'stroke="var(--accent)"/><circle cx="{X(x):.1f}" cy="{Y(v["skill"]):.1f}" r="4" fill="var(--accent)">'
                 f'<title>{p["months"]} month(s) ({x:.1f} used): skill {v["skill"]:+.3f} [{v["skill_lo"]:+.3f}, '
                 f'{v["skill_hi"]:+.3f}], {v["train_positives"]} training positives</title></circle>'
                 f'<text x="{X(x):.1f}" y="{H - 20}" text-anchor="middle">{x:.1f}</text>')
    o.append(f'<text x="{(L + W - R) / 2}" y="{H - 4}" text-anchor="middle">months of history used for training</text></svg>')
    return "".join(o)


def render_section(curve: dict) -> dict:
    e = html.escape
    hold = curve["holdout"]
    prim = [str(h) for h in curve["primary_horizons_s"]]
    parts = [f"<p class='muted'>Same test set for every point: <code>{e(hold['name'])}</code>, "
             f"{e(hold['from'][:10])} to {e(hold['to'][:10])}, {hold['n']:,} ship-weeks. Training ends "
             f"{e(curve['train_end'][:10])} (30-day embargo); {curve['history_months_available']:.1f} months of "
             f"history were available. Skill is against the flag-and-type base rate fitted on the same window; "
             f"brackets are paired bootstrap 95% intervals.</p><div class='charts'>"]
    for h in prim:
        parts.append(f"<div class='panel'><b>{int(h) // 86400}-day label</b>{_svg(curve, h)}</div>")
    parts.append("</div><div class='panel scroll'><table><tr><th>Months asked</th><th>Months used</th>"
                 "<th>Train ship-weeks</th>" + "".join(
                     f"<th>{int(h) // 86400} d skill</th><th>{int(h) // 86400} d AUC-PR (model / base)</th>"
                     f"<th>{int(h) // 86400} d positives (train / test)</th>"
                     for h in prim) + "</tr>")
    for p in curve["points"]:
        if "skipped" in p:
            parts.append(f"<tr><td>{e(str(p['months']))}</td><td colspan='{2 + 3 * len(prim)}' class='muted'>"
                         f"{e(p['skipped'])}</td></tr>")
            continue
        cells = ""
        for h in prim:
            v = p["horizons"].get(h)
            cells += ("<td>–</td><td>–</td><td>–</td>" if not v else
                      f"<td>{v['skill']:+.3f} <span class='muted'>[{v['skill_lo']:+.3f}, {v['skill_hi']:+.3f}]</span></td>"
                      f"<td>{v['auc_pr']:.3f} / {v['auc_pr_baseline']:.3f}</td>"
                      f"<td>{v['train_positives']} ({v['train_positive_ships']} ships) / {v['test_positives']} "
                      f"({v['test_positive_ships']} ships)</td>")
        parts.append(f"<tr><td>{e(str(p['months']))}</td><td>{p['months_used']:.1f}</td><td>{p['n_train']:,}</td>"
                     f"{cells}</tr>")
    parts.append("</table></div>")
    return {"title": "More history, better model? (learning curve)", "html": "".join(parts), "data": curve}


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="python -m ml.godark_gfw.curve", description=__doc__.split("\n")[0])
    ap.add_argument("--data", help="examples Parquet or cache directory (default: the built examples)")
    ap.add_argument("--months", default="1,2,4,all")
    ap.add_argument("--holdout", default="v1")
    a = ap.parse_args(argv)
    ex = SPEC.load_examples({}, a.data)
    months = [m if m == "all" else int(m) for m in a.months.split(",")]
    curve = run(ex, months, holdout_name=a.holdout)
    out = DEFAULT_ARTIFACTS / "reports" / CURVE_FILE
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(curve, indent=1, default=str))
    print(json.dumps({"out": str(out)}))


if __name__ == "__main__":
    main()
