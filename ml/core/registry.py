"""Model interface, artifacts and the run registry (`model_runs`, plus `model_proposals`).

Registry backends: a local Postgres/TimescaleDB (`postgresql://...`, the normal case) or a directory of JSON files
(for tests and machines without a database). Tiger is refused: it is written only by the deployed backend.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import secrets
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pandas as pd

from ml import REPO

DEFAULT_ARTIFACTS = Path(os.getenv("ML_ARTIFACTS") or Path(os.environ.get("POSEIDON_DATA", "/home/aiden/data/poseidon")) / "models")
STATUSES = ("candidate", "champion", "rejected", "retired")   # retired: a former champion that was replaced
PROPOSERS = ("human", "gemini", "default")


# ---------------------------------------------------------------- the model interface

class Model:
    """What every model implements. Predictions are long: one row per case and horizon, `case_id, horizon_s` plus the
    target's outputs (route: pred_lat, pred_lon, radius_m_80, radius_m_95; godark: p).

    `save(dir)` writes the model's own files (LightGBM text dumps, JSON tables; never pickles) and returns the
    fields it adds to model.json, at least {"features": [...], "horizons_s": [...]}. `load(dir)` reads them back.
    """
    name: str = ""
    target: str = ""

    def fit(self, train_df: pd.DataFrame, cfg: dict) -> "Model":
        raise NotImplementedError

    def predict(self, df: pd.DataFrame) -> pd.DataFrame:
        raise NotImplementedError

    def save(self, dir: Path) -> dict:
        raise NotImplementedError

    @classmethod
    def load(cls, dir: Path) -> "Model":
        raise NotImplementedError


FORBIDDEN_SUFFIXES = (".pkl", ".pickle", ".joblib", ".dill")


def save_artifact(model: Model, dir: Path, meta: dict) -> Path:
    """Write the model's files and model.json into `dir` (created fresh). Refuses pickles."""
    if dir.exists():
        shutil.rmtree(dir)
    dir.mkdir(parents=True)
    extra = model.save(dir) or {}
    bad = [p.name for p in dir.rglob("*") if p.suffix.lower() in FORBIDDEN_SUFFIXES]
    if bad:
        shutil.rmtree(dir)
        raise ValueError(f"artifact contains pickles {bad}: save LightGBM text dumps or JSON instead")
    for key in ("features", "horizons_s"):
        if key not in extra:
            raise ValueError(f"{model.name}.save() must return {key!r} for model.json")
    files = sorted(str(p.relative_to(dir)) for p in dir.rglob("*") if p.is_file())
    doc = {"target": model.target, "model": model.name, **meta, **extra, "files": files}
    (dir / "model.json").write_text(json.dumps(doc, indent=2, default=str))
    return dir


def load_artifact(dir: str | Path, models: dict[str, type]) -> tuple[Model, dict]:
    dir = Path(dir)
    meta = json.loads((dir / "model.json").read_text())
    return models[meta["model"]].load(dir), meta


# ---------------------------------------------------------------- helpers

def new_run_id(target: str) -> str:
    return f"{target}-{datetime.now(timezone.utc):%Y%m%dT%H%M%S}-{secrets.token_hex(3)}"


def data_hash(df: pd.DataFrame) -> str:
    """Hash of the examples a run saw (all columns, row order fixed by case_id)."""
    d = df.sort_values("case_id").reset_index(drop=True)
    h = hashlib.sha256(pd.util.hash_pandas_object(d, index=False).values.tobytes())
    h.update(",".join(map(str, d.columns)).encode())
    return h.hexdigest()[:16]


def git_sha() -> str | None:
    try:
        return subprocess.run(["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"], capture_output=True,
                              text=True, timeout=5).stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _refuse_tiger(url: str) -> None:
    host = urlparse(url).hostname or ""
    tiger = urlparse(os.getenv("TIGER_DATABASE_URL", "")).hostname or "\0"
    if host == tiger or "tsdb.cloud.timescale.com" in host:
        raise SystemExit("refusing to use Tiger as the training registry: point ML_DATABASE_URL at a local database")


# ---------------------------------------------------------------- registry backends

RUN_COLS = ["run_id", "target", "model", "config", "data_hash", "train_from", "train_to", "metrics", "artifact",
            "proposer", "parent_run", "status", "created_at", "loop_id", "round", "git_sha"]
JSON_COLS = {"config", "metrics"}

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS model_runs (
  run_id text PRIMARY KEY, target text NOT NULL, model text NOT NULL, config jsonb NOT NULL, data_hash text,
  train_from bigint, train_to bigint, metrics jsonb, artifact text,
  proposer text NOT NULL CHECK (proposer IN ('human','gemini','default')), parent_run text,
  status text NOT NULL CHECK (status IN ('candidate','champion','rejected','retired')),
  created_at timestamptz NOT NULL DEFAULT now(), loop_id text, round int, git_sha text);
CREATE UNIQUE INDEX IF NOT EXISTS model_runs_one_champion ON model_runs (target) WHERE status = 'champion';
CREATE TABLE IF NOT EXISTS model_proposals (
  id bigserial PRIMARY KEY, target text NOT NULL, loop_id text, round int, proposer text NOT NULL,
  proposal jsonb NOT NULL, valid boolean NOT NULL, errors jsonb, run_id text, rationale text,
  created_at timestamptz NOT NULL DEFAULT now());
-- source: what made the proposal (the Gemini model, or the dry-run list and why it was used)
ALTER TABLE model_proposals ADD COLUMN IF NOT EXISTS source text;
"""


class Registry:
    def create_run(self, row: dict) -> None: ...
    def update_run(self, run_id: str, **fields) -> None: ...
    def get_run(self, run_id: str) -> dict | None: ...
    def list_runs(self, target: str) -> list[dict]: ...
    def set_champion(self, target: str, run_id: str) -> None: ...
    def log_proposal(self, row: dict) -> int: ...
    def list_proposals(self, target: str) -> list[dict]: ...

    def champion(self, target: str) -> dict | None:
        return next((r for r in self.list_runs(target) if r["status"] == "champion"), None)


class FileRegistry(Registry):
    """One JSON file per run and per proposal under `root/<target>/`. Same semantics as the SQL registry."""

    def __init__(self, root: str | Path):
        self.root = Path(root)

    def _runs(self, target: str) -> Path:
        p = self.root / target / "runs"
        p.mkdir(parents=True, exist_ok=True)
        return p

    def create_run(self, row: dict) -> None:
        row = {c: row.get(c) for c in RUN_COLS}
        row["created_at"] = row["created_at"] or _now()
        _check_row(row)
        path = self._runs(row["target"]) / f"{row['run_id']}.json"
        if path.exists():
            raise ValueError(f"run {row['run_id']} exists")
        path.write_text(json.dumps(row, default=str))

    def _find(self, run_id: str) -> Path | None:
        return next(iter(self.root.glob(f"*/runs/{run_id}.json")), None)

    def get_run(self, run_id: str) -> dict | None:
        p = self._find(run_id)
        return json.loads(p.read_text()) if p else None

    def update_run(self, run_id: str, **fields) -> None:
        p = self._find(run_id)
        row = json.loads(p.read_text()) | fields
        _check_row(row)
        p.write_text(json.dumps(row, default=str))

    def list_runs(self, target: str) -> list[dict]:
        rows = [json.loads(p.read_text()) for p in self._runs(target).glob("*.json")]
        return sorted(rows, key=lambda r: (r["created_at"], r["run_id"]))

    def set_champion(self, target: str, run_id: str) -> None:
        for r in self.list_runs(target):
            if r["status"] == "champion" and r["run_id"] != run_id:
                self.update_run(r["run_id"], status="retired")
        self.update_run(run_id, status="champion")

    def log_proposal(self, row: dict) -> int:
        d = self.root / row["target"] / "proposals"
        d.mkdir(parents=True, exist_ok=True)
        pid = len(list(d.glob("*.json"))) + 1
        (d / f"{pid:06d}.json").write_text(json.dumps({"id": pid, "created_at": _now(), **row}, default=str))
        return pid

    def list_proposals(self, target: str) -> list[dict]:
        d = self.root / target / "proposals"
        return [json.loads(p.read_text()) for p in sorted(d.glob("*.json"))] if d.exists() else []


class SqlRegistry(Registry):
    """`model_runs` and `model_proposals` in a local Postgres/TimescaleDB. Short-lived connections: the loop makes a
    handful of calls per run, so pooling would only add state."""

    def __init__(self, url: str):
        _refuse_tiger(url)
        self.url = url
        self._q(lambda c: c.execute(SCHEMA_SQL))

    def _q(self, fn):
        import asyncpg

        async def go():
            con = await asyncpg.connect(self.url)
            try:
                return await fn(con)
            finally:
                await con.close()
        return asyncio.run(go())

    @staticmethod
    def _row(rec) -> dict:
        d = dict(rec)
        for k in JSON_COLS | {"errors", "proposal"}:
            if isinstance(d.get(k), str):
                d[k] = json.loads(d[k])
        if isinstance(d.get("created_at"), datetime):
            d["created_at"] = d["created_at"].isoformat(timespec="seconds")
        return d

    def create_run(self, row: dict) -> None:
        row = {c: row.get(c) for c in RUN_COLS if c != "created_at"}
        _check_row(row)
        cols = list(row)
        vals = [json.dumps(row[c], default=str) if c in JSON_COLS else row[c] for c in cols]
        sql = f"INSERT INTO model_runs ({','.join(cols)}) VALUES ({','.join(f'${i + 1}' for i in range(len(cols)))})"
        self._q(lambda c: c.execute(sql, *vals))

    def update_run(self, run_id: str, **fields) -> None:
        if "status" in fields:
            _check_row({"status": fields["status"]})
        cols = list(fields)
        vals = [json.dumps(fields[c], default=str) if c in JSON_COLS else fields[c] for c in cols]
        sets = ",".join(f"{c}=${i + 2}" for i, c in enumerate(cols))
        self._q(lambda c: c.execute(f"UPDATE model_runs SET {sets} WHERE run_id=$1", run_id, *vals))

    def get_run(self, run_id: str) -> dict | None:
        rec = self._q(lambda c: c.fetchrow("SELECT * FROM model_runs WHERE run_id=$1", run_id))
        return self._row(rec) if rec else None

    def list_runs(self, target: str) -> list[dict]:
        recs = self._q(lambda c: c.fetch(
            "SELECT * FROM model_runs WHERE target=$1 ORDER BY created_at, run_id", target))
        return [self._row(r) for r in recs]

    def set_champion(self, target: str, run_id: str) -> None:
        async def flip(c):
            async with c.transaction():   # one champion per target, enforced by the partial unique index too
                await c.execute("UPDATE model_runs SET status='retired' WHERE target=$1 AND status='champion' "
                                "AND run_id<>$2", target, run_id)
                await c.execute("UPDATE model_runs SET status='champion' WHERE run_id=$1", run_id)
        self._q(flip)

    def log_proposal(self, row: dict) -> int:
        return self._q(lambda c: c.fetchval(
            "INSERT INTO model_proposals (target, loop_id, round, proposer, proposal, valid, errors, run_id, "
            "rationale, source) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10) RETURNING id",
            row["target"], row.get("loop_id"), row.get("round"), row["proposer"],
            json.dumps(row["proposal"], default=str), row["valid"], json.dumps(row.get("errors") or []),
            row.get("run_id"), row.get("rationale"), row.get("source")))

    def list_proposals(self, target: str) -> list[dict]:
        recs = self._q(lambda c: c.fetch("SELECT * FROM model_proposals WHERE target=$1 ORDER BY id", target))
        return [self._row(r) for r in recs]


def _check_row(row: dict) -> None:
    if "status" in row and row["status"] not in STATUSES:
        raise ValueError(f"status {row['status']!r} not in {STATUSES}")
    if row.get("proposer") is not None and row["proposer"] not in PROPOSERS:
        raise ValueError(f"proposer {row['proposer']!r} not in {PROPOSERS}")


def open_registry(where: str | None = None) -> Registry:
    """`postgresql://...` -> SqlRegistry; a path -> FileRegistry. Default: ML_DATABASE_URL, else
    /home/aiden/data/poseidon/registry."""
    where = where or os.getenv("ML_DATABASE_URL") or str(DEFAULT_ARTIFACTS.parent / "registry")
    if where.startswith(("postgres://", "postgresql://")):
        return SqlRegistry(where)
    return FileRegistry(where)


def elapsed(t0: float) -> float:
    return round(time.monotonic() - t0, 2)
