"""Pure shaping for the Model Lab: run records from model_runs rows, the run detail (config diff, the promotion rule
as checks, the second-seed confirmation), proposal outcomes, and the stable ids the importer keys on. No I/O."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

RUN_FIELDS = ["run_id", "target", "model", "config", "data_hash", "train_from", "train_to", "artifact", "proposer",
              "parent_run", "status", "created_at", "loop_id", "round", "git_sha", "source", "metrics"]
FILL = ["loop_id", "round", "git_sha", "source", "data_hash", "train_from", "train_to", "artifact", "proposer",
        "parent_run"]
CONFIRM_PREFIX = "second-seed confirmation of "
# how far along a run is: a status row of lower rank never becomes a run's newest row on import
STATUS_RANK = {"candidate": 0, "rejected": 1, "champion": 1, "retired": 2}


def to_ms(v: Any) -> Optional[int]:
    """Epoch ms from ms, seconds-looking numbers or ISO text (the ML registry writes ISO); None stays None."""
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return int(v if v > 1e11 else v * 1000)
    s = str(v).strip()
    if s.lstrip("-").isdigit():
        return to_ms(int(s))
    d = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return int(d.timestamp() * 1000)


def _json(v: Any) -> Any:
    return json.loads(v) if isinstance(v, str) else v


def _num(v: Any) -> Any:
    return float(v) if hasattr(v, "is_finite") else v   # Decimal -> float


def stable_id(*parts: Any) -> str:
    return hashlib.sha1(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()[:20]


def proposal_id(p: dict) -> str:
    """The bundle's id when it is text; an integer id (a registry's bigserial) is only unique per registry, so it is
    hashed together with what makes the proposal itself."""
    if isinstance(p.get("id"), str) and p["id"]:
        return p["id"]
    return "p-" + stable_id(p.get("target"), p.get("loop_id"), p.get("round"), p.get("proposer"),
                            to_ms(p.get("created_at")), p.get("proposal"), p.get("source"), p.get("id"))


def event_id(e: dict) -> str:
    return "e-" + stable_id(to_ms(e.get("ts")), e.get("target"), e.get("kind"), e.get("run_id"), e.get("version"))


# ---------------------------------------------------------------- runs

def runs_from_rows(rows: Iterable[dict]) -> list[dict]:
    """model_runs rows (any order, several per run) -> one run record per run, newest created first. The newest row
    (recorded_at, champion first on a tie, as /model/leaderboard) gives the status; fields a row lacks (rows the
    predictor mirrored have no source, loop_id...) come from the run's other rows."""
    by: dict[str, list[dict]] = {}
    for r in rows:
        by.setdefault(r["run_id"], []).append(dict(r))
    out = []
    for rs in by.values():
        rs.sort(key=lambda r: (r.get("recorded_at") or 0, r.get("status") == "champion"), reverse=True)
        rec = {k: rs[0].get(k) for k in RUN_FIELDS}
        rec["config"] = _json(rec["config"]) or {}
        rec["metrics"] = _json(rec["metrics"]) or {}
        for k in FILL:
            if rec[k] is None:
                rec[k] = next((r[k] for r in rs if r.get(k) is not None), None)
        if not rec["metrics"]:
            rec["metrics"] = next((m for m in (_json(r.get("metrics")) for r in rs) if m), {})
        out.append({k: _num(v) for k, v in rec.items()})
    out.sort(key=lambda r: (-(r["created_at"] or 0), r["run_id"]))
    return out


def without_strata(rec: dict) -> dict:
    m = {k: v for k, v in (rec.get("metrics") or {}).items() if k not in ("strata", "strata_baseline")}
    return {**rec, "metrics": m}


def config_diff(cfg: Optional[dict], parent: Optional[dict]) -> list[dict]:
    """Keys whose value differs from the parent's (every key when there is no parent), sorted by key."""
    cfg, parent = cfg or {}, parent or {}
    return [{"key": k, "parent": parent.get(k), "value": cfg.get(k)}
            for k in sorted(set(cfg) | set(parent)) if cfg.get(k) != parent.get(k)]


def horizon_label(h: Any) -> str:
    try:
        s = int(h)
    except (TypeError, ValueError):
        return str(h)
    if s % 86400 == 0 and s >= 2 * 86400:
        return f"{s // 86400} days"
    return f"{s // 3600} h" if s % 3600 == 0 else f"{s // 60} min"


def _against(decision: dict) -> str:
    a = (decision.get("against") or "the champion").strip()
    if a.startswith("baseline"):
        return "the baseline"
    return a if a.startswith("the ") else f"the {a}"


def is_confirmation(rec: dict, rationale: Optional[str]) -> bool:
    return bool(rationale and rationale.startswith(CONFIRM_PREFIX))


def find_confirm(rec: dict, runs: list[dict], rationale_of: dict[str, Optional[str]]) -> Optional[dict]:
    """The second-seed re-run of this run: a child run logged as its confirmation, or (when the proposal log is
    missing) a child with the same config and seed + 1. Passed when the re-run did not fail the rule."""
    cfg = rec.get("config") or {}
    for c in runs:
        if c["run_id"] == rec["run_id"] or c.get("parent_run") != rec["run_id"]:
            continue
        why = rationale_of.get(c["run_id"]) or ""
        ccfg = c.get("config") or {}
        same = (isinstance(cfg.get("seed"), int) and ccfg.get("seed") == cfg["seed"] + 1
                and {k: v for k, v in ccfg.items() if k != "seed"} == {k: v for k, v in cfg.items() if k != "seed"})
        if why == CONFIRM_PREFIX + rec["run_id"] or same:
            return {"run_id": c["run_id"], "passed": c.get("status") != "rejected"}
    return None


def rule(rec: dict, confirm: Optional[dict]) -> list[dict]:
    """The promotion rule (ml/core/evaluate.decide) as a checklist: one win check per primary horizon, one per
    calibration check, the strata check, and the second-seed confirmation when there was one. Runs that predate the
    registry have no decision and get []."""
    d = (rec.get("metrics") or {}).get("decision") or {}
    if not d:
        return []
    out, vs = [], _against(d)
    for h, x in sorted((d.get("horizons") or {}).items(), key=lambda kv: int(kv[0]) if str(kv[0]).isdigit() else 0):
        detail = None
        if isinstance(x.get("diff"), (int, float)):
            detail = f"diff {x['diff']:+.4g}"
            if isinstance(x.get("lo"), (int, float)) and isinstance(x.get("hi"), (int, float)):
                detail += f" [{x['lo']:+.4g}, {x['hi']:+.4g}]"
        win = x.get("win")
        out.append({"check": f"beats {vs} at {horizon_label(h)}", "passed": bool(win) if win is not None else None,
                    "detail": detail})
    for c in d.get("calibration") or []:
        ok = c.get("ok")
        if ok is None and c.get("value") is not None:
            ok = abs(c["value"] - c.get("nominal", 0)) <= c.get("tol", 0.05)
        out.append({"check": f"calibration {c.get('name')} within {c.get('tol', 0.05):g} of {c.get('nominal', 0):g}"
                             + (f" at {horizon_label(c['horizon_s'])}" if c.get("horizon_s") is not None else ""),
                    "passed": bool(ok),
                    "detail": f"{c['value']:.3g}" if isinstance(c.get("value"), (int, float)) else None})
    if "strata_worse" in d:
        w = d.get("strata_worse") or []
        out.append({"check": "no group of 30+ cases more than 10% worse", "passed": not w,
                    "detail": (", ".join(f"{x.get('stratum')}={x.get('value')}" for x in w[:5])
                               + (f" and {len(w) - 5} more" if len(w) > 5 else "")) or None})
    if confirm:
        out.append({"check": "wins again with a second seed", "passed": bool(confirm["passed"]),
                    "detail": confirm["run_id"]})
    return out


def run_detail(rec: dict, runs: list[dict], proposals: list[dict]) -> dict:
    """GET /lab/runs/{id}: the full record plus its parent, config diff, rationale, rule checklist and confirm."""
    by = {r["run_id"]: r for r in runs}
    rationale_of: dict[str, Optional[str]] = {}
    for p in sorted(proposals, key=lambda p: p.get("created_at") or 0):
        if p.get("run_id"):
            rationale_of[p["run_id"]] = p.get("rationale")
    parent = by.get(rec.get("parent_run")) if rec.get("parent_run") else None
    why = rationale_of.get(rec["run_id"])
    confirm = None if is_confirmation(rec, why) else find_confirm(rec, runs, rationale_of)
    return {**rec, "parent": parent, "config_diff": config_diff(rec.get("config"), (parent or {}).get("config")),
            "rationale": why, "rule": rule(rec, confirm), "confirm": confirm}


# ---------------------------------------------------------------- proposals

def proposal_outcome(p: dict, run_status: Optional[str]) -> Optional[str]:
    """champion | candidate | rejected | invalid | duplicate. From the run's status now when it has a run (a
    retired champion was once promoted, so it stays champion); otherwise from the proposal's errors."""
    errs = p.get("errors") or []
    if any(str(e).startswith("duplicate") for e in errs):
        return "duplicate"
    if p.get("valid") is False:
        return "invalid"
    if run_status in ("champion", "retired"):
        return "champion"
    if run_status in ("candidate", "rejected"):
        return run_status
    return p.get("outcome")


PROPOSAL_FIELDS = ["id", "target", "loop_id", "round", "proposer", "created_at", "proposal", "valid", "errors",
                   "rationale", "source", "run_id", "outcome"]


def proposal_record(row: dict, run_status: Optional[str]) -> dict:
    p = {k: row.get(k) for k in PROPOSAL_FIELDS}
    p["proposal"], p["errors"] = _json(p["proposal"]), _json(p["errors"]) or []
    p["outcome"] = proposal_outcome(p, run_status)
    return p


def event_record(row: dict) -> dict:
    e = {k: row.get(k) for k in ("ts", "target", "kind", "run_id", "version", "label", "detail")}
    e["detail"] = _json(e["detail"]) or {}
    return e
