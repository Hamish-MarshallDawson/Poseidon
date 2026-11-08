"""Config proposals: Gemini (or a fixed dry-run list) reads a metrics summary and returns configs; every config is
validated against the target's JSON Schema before anything runs, and every proposal is logged, valid or not.

Gemini sees aggregate metrics only (per horizon and per stratum), never held-out cases, and edits configs, never
code. Promotion is decided by `evaluate.decide`, never by the proposer.
"""
from __future__ import annotations

import copy
import fcntl
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import urllib.error
import urllib.request

import jsonschema

from ml.core.target import TargetSpec

DEFAULT_MODEL = "gemini-3.5-flash-lite"
# The key's free tier is shared with the site's briefings (20 requests a day on gemini-3.5-flash), so the loop caps
# its own calls per UTC day and counts them in a file (per machine).
DEFAULT_DAILY_CAP = 6
DRY_RUN_LABEL = "fixed dry-run list"
URL = "https://generativelanguage.googleapis.com/v1beta/interactions"   # same API as backend/dvm/briefing
TIMEOUT_S = 90
MAX_RATIONALE = 300


class ProposerError(Exception):
    pass


class ProposerSkipped(ProposerError):
    """Gemini was not asked or said no for quota reasons (429, or our own daily cap): fall back, don't stop."""


def gemini_model() -> str:
    from ml.core import env  # noqa: F401  (loads the repo .env)
    return os.getenv("GEMINI_MODEL") or DEFAULT_MODEL


def daily_cap() -> int:
    return int(os.getenv("ML_GEMINI_DAILY_CAP", DEFAULT_DAILY_CAP))


def counter_path() -> Path:
    return Path(os.getenv("ML_GEMINI_COUNTER", "/home/aiden/data/poseidon/gemini_calls.json"))


def take_call() -> int:
    """Reserve one Gemini call for today (UTC), or raise ProposerSkipped at the cap. Returns today's count.
    Locked so parallel loops on one machine share the count."""
    p = counter_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    today = datetime.now(timezone.utc).date().isoformat()
    with open(p, "a+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.seek(0)
        try:
            d = json.loads(f.read() or "{}")
        except ValueError:
            d = {}
        n = int(d.get(today, 0))
        if n >= daily_cap():
            raise ProposerSkipped(f"daily Gemini cap reached ({n}/{daily_cap()} calls today, ML_GEMINI_DAILY_CAP)")
        d = {today: n + 1}
        f.seek(0)
        f.truncate()
        f.write(json.dumps(d))
    return n + 1


def validate(spec: TargetSpec, cfg) -> list[str]:
    """Reasons `cfg` may not run; empty means valid."""
    if not isinstance(cfg, dict):
        return ["config is not an object"]
    errs = [f"{'/'.join(map(str, e.absolute_path)) or '(root)'}: {e.message}"
            for e in jsonschema.Draft202012Validator(spec.config_schema).iter_errors(cfg)]
    if cfg.get("model") not in spec.models and not any(e.startswith("model:") for e in errs):
        errs.append(f"model {cfg.get('model')!r} is not one of {sorted(spec.models)}")
    if not isinstance(cfg.get("seed"), int):
        errs.append("seed must be an integer")
    return errs


# ---------------------------------------------------------------- dry run

def dry_run_proposals(spec: TargetSpec, k: int, round_: int) -> list[dict]:
    """Fixed, deterministic proposals so tests and rehearsals never call Gemini. A target may define its own
    `dry_run_proposals` list; otherwise numeric settings of the default config are stepped through their ranges.
    One extra proposal per round is deliberately invalid, so the rejection path is always exercised."""
    fixed = getattr(spec, "dry_run_proposals", None)
    if fixed:
        start = ((round_ - 1) * k) % len(fixed)
        out = [copy.deepcopy(fixed[(start + i) % len(fixed)]) for i in range(k)]
    else:
        out = []
        props = spec.config_schema.get("properties", {})
        numeric = [(n, p) for n, p in props.items() if p.get("type") in ("integer", "number")
                   and "minimum" in p and "maximum" in p and n != "seed"]
        for i in range(k):
            cfg = copy.deepcopy(spec.default_config)
            for j, (n, p) in enumerate(numeric):
                frac = ((round_ * 7 + i * 3 + j * 5) % 10) / 10 + 0.05
                v = p["minimum"] + frac * (p["maximum"] - p["minimum"])
                cfg[n] = int(round(v)) if p["type"] == "integer" else round(v, 4)
            out.append({"config": cfg, "rationale": f"dry run: step numeric settings (round {round_}, #{i + 1})"})
    for p in out:
        p.setdefault("rationale", "dry run")
        p["config"].setdefault("seed", spec.default_config.get("seed", 0))
    if out:
        bad = copy.deepcopy(out[-1])
        bad["config"]["model"] = "not_a_model"
        bad["rationale"] = "dry run: deliberately invalid, to show that the runner rejects it"
        out.append(bad)
    return out


# ---------------------------------------------------------------- Gemini

SYSTEM = """You propose the next training runs for a maritime prediction model. You are given a JSON summary of past
runs: their configs, metrics on a frozen held-out set per horizon (statistic of the loss, skill over the baseline
with a 95% interval), calibration, weak strata, data volume, and which proposals were rejected and why.
Rules:
- Return ONLY configs that satisfy the supplied config_schema exactly (allowed keys, enums, ranges).
- Each proposal changes something specific for a stated reason grounded in the summary; do not repeat a config
  that already ran. Prefer a mix: refine the champion, and try one bolder change.
- You never see individual held-out cases. Promotion is decided by a fixed statistical rule, not by you.
- rationale: at most 300 characters, plain English, naming the metric or stratum that motivates the change."""


def _strip(schema):
    """Gemini's response schema accepts a subset of JSON Schema: drop keywords it rejects. Local validation still
    applies the full schema."""
    if isinstance(schema, dict):
        return {k: _strip(v) for k, v in schema.items()
                if k not in ("$schema", "additionalProperties", "uniqueItems", "$id", "title", "default")}
    if isinstance(schema, list):
        return [_strip(v) for v in schema]
    return schema


def _post(payload: dict, key: str) -> dict:
    req = urllib.request.Request(URL, json.dumps(payload).encode(),
                                 {"Content-Type": "application/json", "x-goog-api-key": key})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 429:
            raise ProposerSkipped("Gemini returned 429 (quota exhausted; the key is shared with the briefings)") \
                from None
        raise ProposerError(f"Gemini returned HTTP {e.code}") from None   # never echo the body: it can carry the key
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        raise ProposerError("Gemini is unreachable or timed out") from None


def gemini_proposals(spec: TargetSpec, summary: dict, k: int, model: str | None = None) -> list[dict]:
    model = model or gemini_model()
    key = os.getenv("GEMINI_API_KEY", "")
    if not key:
        raise ProposerError("GEMINI_API_KEY is not set (repo .env)")
    schema = {"type": "object", "required": ["proposals"], "properties": {"proposals": {
        "type": "array", "items": {"type": "object", "required": ["config", "rationale"], "properties": {
            "config": _strip(spec.config_schema), "rationale": {"type": "string"}}}}}}
    facts = {"target": spec.name, "how_many": k, "config_schema": spec.config_schema, "summary": summary}
    payload = {"model": model, "system_instruction": SYSTEM, "input": json.dumps(facts, default=str),
               "response_format": {"type": "text", "mime_type": "application/json", "schema": schema}}
    take_call()
    data = _post(payload, key)
    try:
        out = [st for st in data["steps"] if st.get("type") == "model_output"][-1]
        doc = json.loads("".join(c["text"] for c in out["content"] if c.get("type") == "text"))
        props = doc["proposals"]
    except (KeyError, IndexError, TypeError, ValueError):
        raise ProposerError("Gemini returned an unusable answer") from None
    clean = []
    for p in props[:k]:
        if not isinstance(p, dict):
            p = {"config": p, "rationale": ""}
        clean.append({"config": p.get("config"), "rationale": str(p.get("rationale", ""))[:MAX_RATIONALE]})
    return clean


def propose(spec: TargetSpec, summary: dict, k: int, round_: int, dry_run: bool) -> tuple[str, str, list[dict]]:
    """(proposer, source, proposals). proposer is the registry label (gemini | default); source names what made
    them (the Gemini model, or the dry-run list and why). Each proposal is {"config", "rationale"}; validate before
    running. A 429 or our daily cap falls back to the dry-run list instead of stopping the loop."""
    if dry_run:
        return "default", DRY_RUN_LABEL, dry_run_proposals(spec, k, round_)
    model = gemini_model()
    try:
        return "gemini", model, gemini_proposals(spec, summary, k, model)
    except ProposerSkipped as e:
        return "default", f"{DRY_RUN_LABEL} (fallback: {model} skipped: {e})", dry_run_proposals(spec, k, round_)
