"""Leaderboard and learning-curve report for a target, as static HTML (no external files) plus JSON.

    python -m ml.core.report --target route [--out DIR]
"""
from __future__ import annotations

import argparse
import html
import json
import math
from datetime import datetime, timezone
from pathlib import Path

from ml.core import env  # noqa: F401
from ml.core.registry import DEFAULT_ARTIFACTS, Registry, open_registry
from ml.core.target import TargetSpec, get_target


def _hlabel(h) -> str:
    h = int(h)
    return f"{h // 3600} h" if h % 3600 == 0 else f"{h // 60} min" if h % 60 == 0 else f"{h} s"


def _f(x, nd=3, signed=False) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "–"
    return f"{x:+.{nd}f}" if signed else f"{x:.{nd}f}"


def _stat_fmt(x, unit) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "–"
    if unit == "m":
        return f"{x / 1000:.2f} km" if abs(x) >= 1000 else f"{x:.0f} m"
    return f"{x:.4g}{(' ' + unit) if unit else ''}"


def build(spec: TargetSpec, reg: Registry) -> dict:
    runs = reg.list_runs(spec.name)
    done = [r for r in runs if (r.get("metrics") or {}).get("state") == "done"]
    failed = [r for r in runs if (r.get("metrics") or {}).get("state") == "failed"]
    prim = [str(h) for h in spec.primary_horizons_s]

    def mean_skill(r):
        v = [r["metrics"]["skill"].get(h, {}).get("skill") for h in prim]
        v = [x for x in v if x is not None and not math.isnan(x)]
        return sum(v) / len(v) if v else float("-inf")

    def entry(r, i):
        m = r["metrics"]
        return {"seq": i, "run_id": r["run_id"], "round": r.get("round"), "model": r["model"],
                "proposer": r["proposer"], "status": r["status"], "config": r["config"],
                "parent_run": r.get("parent_run"), "created_at": r["created_at"], "skill": m["skill"],
                "summary": m["summary"], "calibration": m["calibration"], "cv": m["cv"],
                "verdict": "promoted" if r["status"] in ("champion", "retired") else
                           "passed the rule" if r["status"] == "candidate" else "rejected",
                "reasons": m["decision"]["reasons"], "against": m["decision"]["against"],
                "decision_horizons": m["decision"]["horizons"], "alpha": m["decision"]["alpha"],
                "n_train": m["split"]["n_train"], "seconds": m.get("seconds"), "mean_primary_skill": mean_skill(r)}

    entries = [entry(r, i + 1) for i, r in enumerate(done)]
    champ = next((e for e in entries if e["status"] == "champion"), None)
    holdouts = {json.dumps(r["metrics"]["holdout"], sort_keys=True) for r in done}
    curve, best = [], None
    for e in entries:   # champion skill after each run; a promoted run (champion or retired) starts a new step
        if e["status"] in ("champion", "retired"):
            best = e
        curve.append({"seq": e["seq"], "champion": best["run_id"] if best else None,
                      "skill": {h: (best["skill"].get(h, {}).get("skill") if best else 0.0) for h in prim}})
    props = reg.list_proposals(spec.name)
    return {
        "target": spec.name, "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "statistic": spec.statistic, "loss_name": spec.loss_name, "loss_unit": spec.loss_unit,
        "horizons_s": spec.horizons_s, "primary_horizons_s": spec.primary_horizons_s, "baseline": spec.baseline,
        "holdouts": [json.loads(h) for h in holdouts], "champion": champ,
        "leaderboard": sorted(entries, key=lambda e: e["mean_primary_skill"], reverse=True),
        "runs": entries, "failed_runs": [{"run_id": r["run_id"], "config": r["config"],
                                          "error": r["metrics"].get("error")} for r in failed],
        "learning_curve": curve,
        "proposals": [{k: p.get(k) for k in ("id", "round", "proposer", "proposal", "valid", "errors", "run_id",
                                              "rationale", "created_at", "loop_id")} for p in props],
        "notes": list(getattr(spec, "report_notes", [])),
    }


# ---------------------------------------------------------------- HTML

CSS = """
:root{--bg:#f7f8fa;--panel:#fff;--ink:#14181f;--muted:#5b6472;--line:#dfe3e8;--accent:#0b6bcb;--good:#1a7f37;
--bad:#b42318;--dim:#9aa3ae;--zero:#8a94a0}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#0f1318;--panel:#171c23;--ink:#e6e9ee;
--muted:#9aa4b2;--line:#2a313b;--accent:#5aa9ff;--good:#4ac26b;--bad:#ff7b72;--dim:#5d6672;--zero:#6b7480}}
:root[data-theme="dark"]{--bg:#0f1318;--panel:#171c23;--ink:#e6e9ee;--muted:#9aa4b2;--line:#2a313b;--accent:#5aa9ff;
--good:#4ac26b;--bad:#ff7b72;--dim:#5d6672;--zero:#6b7480}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font:14px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
main{max-width:1180px;margin:0 auto;padding:24px 16px 64px}h1{font-size:22px;margin:0 0 4px}
h2{font-size:16px;margin:32px 0 10px}p{margin:6px 0}.muted{color:var(--muted)}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:16px;margin:12px 0}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}
.tile .k{color:var(--muted);font-size:12px}.tile .v{font-size:24px;font-weight:600;font-variant-numeric:tabular-nums}
.tile .s{font-size:12px;color:var(--muted);font-variant-numeric:tabular-nums}
.scroll{overflow-x:auto}table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top;white-space:nowrap}
th{font-size:12px;color:var(--muted);font-weight:600}td.wrap{white-space:normal;min-width:240px}
.pill{display:inline-block;padding:1px 8px;border-radius:99px;font-size:12px;border:1px solid var(--line)}
.champion{color:var(--accent);border-color:var(--accent)}.retired{color:var(--accent)}
.candidate{color:var(--good);border-color:var(--good)}.rejected,.invalid{color:var(--bad);border-color:var(--bad)}
.pos{color:var(--good)}.neg{color:var(--bad)}code{font-size:12px;color:var(--muted)}
svg text{fill:var(--muted);font-size:11px}.charts{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:12px}
"""


def _pill(s):
    return f'<span class="pill {html.escape(s)}">{html.escape(s)}</span>'


def _skill_cell(v):
    if not v:
        return "<td>–</td>"
    cls = "pos" if v["skill_lo"] > 0 else "neg" if v["skill_hi"] < 0 else ""
    return (f'<td><span class="{cls}">{_f(v["skill"], 3, True)}</span> '
            f'<span class="muted">[{_f(v["skill_lo"], 3, True)}, {_f(v["skill_hi"], 3, True)}]</span></td>')


def _loss_word(rep: dict) -> str:
    n, u = rep["loss_name"], rep["loss_unit"]
    return n[: -len(u) - 1].replace("_", " ") if u and n.endswith("_" + u) else n.replace("_", " ")


def _short_verdict(r: dict, unit: str) -> str:
    """Why a run lost, briefly: horizons where it was not better than the reference (difference and interval),
    then any calibration, stratum or sanity failure."""
    out = []
    for h, v in r["decision_horizons"].items():
        if not v["win"]:
            out.append(f"{_hlabel(h)}: not better (Δ {_stat_fmt(v['diff'], unit)}, "
                       f"[{_stat_fmt(v['lo'], unit)}, {_stat_fmt(v['hi'], unit)}])")
    out += [x for x in r["reasons"] if "does not exclude zero" not in x]
    return "; ".join(out[:3]) + (" …" if len(out) > 3 else "")


def _curve_svg(rep: dict, h: str) -> str:
    runs, curve = rep["runs"], rep["learning_curve"]
    if not runs:
        return ""
    W, H, L, R, T, B = 520, 220, 46, 12, 14, 30
    pts = [(e["seq"], e["skill"].get(h)) for e in runs if e["skill"].get(h)]
    ys = [0.0] + [v["skill_lo"] for _, v in pts] + [v["skill_hi"] for _, v in pts]
    ys = [y for y in ys if y is not None and not math.isnan(y)]
    y0, y1 = min(ys), max(ys)
    pad = (y1 - y0) * 0.08 or 0.05
    y0, y1 = y0 - pad, y1 + pad
    n = max(len(runs), 2)
    X = lambda s: L + (s - 1) * (W - L - R) / (n - 1)   # noqa: E731
    Y = lambda y: T + (y1 - y) * (H - T - B) / (y1 - y0)   # noqa: E731
    out = [f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" aria-label="skill at {_hlabel(h)} by run">']
    for frac in (0, 0.5, 1):
        yv = y0 + frac * (y1 - y0)
        out.append(f'<line x1="{L}" x2="{W - R}" y1="{Y(yv):.1f}" y2="{Y(yv):.1f}" stroke="var(--line)"/>'
                   f'<text x="{L - 6}" y="{Y(yv) + 4:.1f}" text-anchor="end">{yv:+.2f}</text>')
    out.append(f'<line x1="{L}" x2="{W - R}" y1="{Y(0):.1f}" y2="{Y(0):.1f}" stroke="var(--zero)" '
               f'stroke-dasharray="4 3"/><text x="{W - R}" y="{Y(0) - 4:.1f}" text-anchor="end">baseline</text>')
    step = []
    for c in curve:
        y = c["skill"].get(h)
        if y is None:
            continue
        x = X(c["seq"])
        if step:
            step.append(f"L{x:.1f},{float(step[-1].split(',')[1]):.1f}")
        step.append(f"{'M' if not step else 'L'}{x:.1f},{Y(y):.1f}")
    if step:
        out.append(f'<path d="{" ".join(step)}" fill="none" stroke="var(--accent)" stroke-width="2"/>')
    for s, v in pts:
        st = next(e["status"] for e in runs if e["seq"] == s)
        col = {"champion": "var(--accent)", "retired": "var(--accent)", "candidate": "var(--good)"}.get(st, "var(--dim)")
        out.append(f'<line x1="{X(s):.1f}" x2="{X(s):.1f}" y1="{Y(v["skill_lo"]):.1f}" y2="{Y(v["skill_hi"]):.1f}" '
                   f'stroke="{col}"/><circle cx="{X(s):.1f}" cy="{Y(v["skill"]):.1f}" r="4" fill="{col}">'
                   f'<title>run {s}: {st}, skill {v["skill"]:+.3f} [{v["skill_lo"]:+.3f}, {v["skill_hi"]:+.3f}]'
                   f'</title></circle>')
    out.append(f'<text x="{(L + W - R) / 2}" y="{H - 6}" text-anchor="middle">run, in order</text></svg>')
    return "".join(out)


def render_html(rep: dict) -> str:
    e = html.escape
    unit, prim = rep["loss_unit"], [str(h) for h in rep["primary_horizons_s"]]
    hs = [str(h) for h in rep["horizons_s"]]
    ch = rep["champion"]
    hold = rep["holdouts"][-1] if rep["holdouts"] else None
    stat_word = "Median" if rep["statistic"] == "median" else "Mean"
    parts = [f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' "
             f"content='width=device-width,initial-scale=1'><title>{e(rep['target'])} model leaderboard</title>"
             f"<style>{CSS}</style></head><body><main>",
             f"<h1>{e(rep['target'])}: models, held-out results and the improvement loop</h1>",
             f"<p class='muted'>Generated {e(rep['generated_at'])}. Skill = 1 − {stat_word.lower()} "
             f"{e(_loss_word(rep))} of the model ÷ that of the baseline (<code>{e(rep['baseline'])}</code>) on the "
             f"same held-out cases; 0 is the baseline, positive is better. Brackets are paired bootstrap 95% "
             f"intervals (2000 resamples).</p>"]
    if hold:
        parts.append(
            f"<div class='panel'><b>Frozen held-out set</b> <code>{e(hold['name'])}</code> · {hold['n']:,} cases"
            f" from {hold['n_ships']:,} ships · {e(hold['from'][:16].replace('T', ' '))} to {e(hold['to'][:16].replace('T', ' '))} UTC · hash "
            f"<code>{e(hold['hash'])}</code>. Never trained on; the proposer sees aggregate metrics only. Training "
            f"uses cases whose label window ends before it starts (embargo = the longest horizon)"
            f"{'; held-out ships are kept out of training' if hold.get('group_by_ship') else ''}.")
        if len(rep["holdouts"]) > 1:
            parts.append(f" <b>Note:</b> these runs used {len(rep['holdouts'])} different held-out sets; compare "
                         f"skill only within one set.")
        parts.append("</div>")
    if ch:
        parts.append(f"<h2>Champion: <code>{e(ch['run_id'])}</code> ({e(ch['model'])}, proposed by "
                     f"{e(ch['proposer'])})</h2><div class='grid'>")
        for h in hs:
            v, s = ch["skill"].get(h), ch["summary"].get(h, {})
            if not v:
                continue
            extra = " · ".join(f"{k} {_f(val, 2) if isinstance(val, float) and abs(val) < 10 else val}"
                               for k, val in s.items() if k.startswith("cov"))
            parts.append(f"<div class='panel tile'><div class='k'>{_hlabel(h)} ahead"
                         f"{' · primary' if h in prim else ''} · n = {v['n']:,}</div>"
                         f"<div class='v'>{_f(v['skill'], 3, True)}</div>"
                         f"<div class='s'>[{_f(v['skill_lo'], 3, True)}, {_f(v['skill_hi'], 3, True)}] · "
                         f"{stat_word.lower()} {_stat_fmt(v['stat'], unit)} vs {_stat_fmt(v['baseline_stat'], unit)}"
                         f" baseline · wins {v['win_rate']:.0%} of cases{(' · ' + extra) if extra else ''}</div></div>")
        parts.append("</div>")
    else:
        parts.append("<h2>No champion yet</h2><p class='muted'>No run has passed the promotion rule against the "
                     "baseline.</p>")
    parts.append("<h2>Learning curve</h2><p class='muted'>Each dot is a run's held-out skill with its interval (blue: "
                 "promoted, green: passed the rule but not promoted, grey: rejected). The line is the champion's "
                 "skill as runs complete.</p><div class='charts'>")
    for h in prim:
        parts.append(f"<div class='panel'><b>{_hlabel(h)} ahead</b>{_curve_svg(rep, h)}</div>")
    parts.append("</div><h2>Leaderboard</h2><div class='panel scroll'><table><tr><th>#</th><th>Run</th><th>Round</th>"
                 "<th>Model</th><th>Proposer</th><th>Status</th>"
                 + "".join(f"<th>Skill {_hlabel(h)}</th>" for h in prim)
                 + "".join(f"<th>{stat_word} {_hlabel(h)}</th>" for h in prim)
                 + "<th>Train n</th><th>Verdict (rule)</th></tr>")
    for i, r in enumerate(rep["leaderboard"], 1):
        why = "beat " + e(r["against"]) if r["verdict"] == "promoted" else (
            "passed vs " + e(r["against"]) if r["verdict"] == "passed the rule" else e(_short_verdict(r, unit)))
        parts.append(f"<tr><td>{i}</td><td><code>{e(r['run_id'])}</code></td><td>{r['round'] if r['round'] is not None else '–'}</td>"
                     f"<td>{e(r['model'])}</td><td>{e(r['proposer'])}</td><td>{_pill(r['status'])}</td>"
                     + "".join(_skill_cell(r["skill"].get(h)) for h in prim)
                     + "".join(f"<td>{_stat_fmt(r['skill'].get(h, {}).get('stat'), unit)}</td>" for h in prim)
                     + f"<td>{r['n_train']:,}</td><td class='wrap'>{why}</td></tr>")
    parts.append("</table></div>")
    if rep["proposals"]:
        parts.append("<h2>Proposals</h2><p class='muted'>Every proposal, including the ones the runner refused. "
                     "Configs are checked against a fixed schema; the proposer cannot change code, data or the "
                     "rule.</p><div class='panel scroll'><table><tr><th>Round</th><th>Proposer</th><th>Valid</th>"
                     "<th>Config</th><th>Rationale</th><th>Outcome</th></tr>")
        status = {r["run_id"]: r["status"] for r in rep["runs"]}
        for p in rep["proposals"]:
            outcome = (_pill(status.get(p["run_id"], "run")) + f" <code>{e(p['run_id'])}</code>") if p["run_id"] \
                else e("; ".join(p.get("errors") or [])[:240])
            parts.append(f"<tr><td>{p['round'] if p['round'] is not None else '–'}</td><td>{e(p['proposer'])}</td>"
                         f"<td>{_pill('valid' if p['valid'] else 'invalid')}</td>"
                         f"<td class='wrap'><code>{e(json.dumps(p['proposal'], separators=(',', ':')))}</code></td>"
                         f"<td class='wrap'>{e(p.get('rationale') or '')}</td><td class='wrap'>{outcome}</td></tr>")
        parts.append("</table></div>")
    if rep["failed_runs"]:
        parts.append(f"<p class='muted'>{len(rep['failed_runs'])} run(s) crashed and are listed in report.json.</p>")
    parts.append("<h2>How promotion works</h2><div class='panel'><p>A candidate replaces the champion (or, with "
                 "none, the baseline) only if, on the frozen held-out set: at every primary horizon the paired "
                 "bootstrap interval of the difference in the statistic excludes zero in its favour, at 95% "
                 "Bonferroni-corrected for the number of proposals tried that round; every calibration check (radius "
                 "coverage or probability calibration) is within 5 points of nominal; and no stratum with at least 30 "
                 "cases is more than 10% worse. In the loop, the winner must win again with a second seed. Ties keep "
                 "the champion.</p>")
    for n in rep["notes"]:
        parts.append(f"<p>{e(n)}</p>")
    parts.append("</div></main></body></html>")
    return "".join(parts)


def write(spec: TargetSpec, reg: Registry, out_dir: Path) -> dict[str, Path]:
    rep = build(spec, reg)
    out_dir.mkdir(parents=True, exist_ok=True)
    j, h = out_dir / f"{spec.name}.json", out_dir / f"{spec.name}.html"
    j.write_text(json.dumps(rep, indent=2, default=str))
    h.write_text(render_html(rep))
    return {"json": j, "html": h}


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="python -m ml.core.report")
    ap.add_argument("--target", required=True)
    ap.add_argument("--registry")
    ap.add_argument("--out", default=str(DEFAULT_ARTIFACTS / "reports"))
    a = ap.parse_args(argv)
    paths = write(get_target(a.target), open_registry(a.registry), Path(a.out))
    print(json.dumps({k: str(v) for k, v in paths.items()}))


if __name__ == "__main__":
    main()
