"""Model Lab tables (docs/handoffs/lab.md): additive only.

- `model_runs` (dvm/predict/schema.py) gains the run record's loop_id, round, git_sha and source (pc-aiden,
  desktop-hamish, server). Rows written before have them null; the routes fill them from any row of the same run.
- `ml_proposals`: every proposal the improvement loop logged (invalid and duplicate ones included), keyed by a
  stable id the importer derives, so a re-import updates instead of duplicating.
- `ml_events`: the Lab timeline (trained, promoted, rejected, recalibrated, deployed, proposal), keyed by a hash of
  (ts, target, kind, run_id, version).
"""
from __future__ import annotations

import asyncpg

SCHEMA = """
ALTER TABLE IF EXISTS model_runs ADD COLUMN IF NOT EXISTS loop_id text;
ALTER TABLE IF EXISTS model_runs ADD COLUMN IF NOT EXISTS round integer;
ALTER TABLE IF EXISTS model_runs ADD COLUMN IF NOT EXISTS git_sha text;
ALTER TABLE IF EXISTS model_runs ADD COLUMN IF NOT EXISTS source text;

CREATE TABLE IF NOT EXISTS ml_proposals (
  id text PRIMARY KEY, target text NOT NULL, loop_id text, round integer, proposer text, created_at bigint,
  proposal jsonb, valid boolean NOT NULL DEFAULT true, errors jsonb NOT NULL DEFAULT '[]', rationale text,
  source text, run_id text, outcome text, recorded_at bigint NOT NULL
);
CREATE INDEX IF NOT EXISTS ml_proposals_target_created ON ml_proposals (target, created_at DESC);
CREATE INDEX IF NOT EXISTS ml_proposals_run ON ml_proposals (run_id) WHERE run_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS ml_events (
  id text PRIMARY KEY, ts bigint NOT NULL, target text NOT NULL, kind text NOT NULL, run_id text, version text,
  label text, detail jsonb NOT NULL DEFAULT '{}', recorded_at bigint NOT NULL
);
CREATE INDEX IF NOT EXISTS ml_events_ts ON ml_events (ts);
CREATE INDEX IF NOT EXISTS ml_events_target_ts ON ml_events (target, ts);
"""

RUN_EXTRA = ["loop_id", "round", "git_sha", "source"]
PROPOSAL_COLS = ["id", "target", "loop_id", "round", "proposer", "created_at", "proposal", "valid", "errors",
                 "rationale", "source", "run_id", "outcome", "recorded_at"]
EVENT_COLS = ["id", "ts", "target", "kind", "run_id", "version", "label", "detail", "recorded_at"]


def _params(cols: list[str]) -> str:
    return ", ".join(f"${i}" for i in range(1, len(cols) + 1))


PROPOSAL_UPSERT = (f"INSERT INTO ml_proposals ({', '.join(PROPOSAL_COLS)}) VALUES ({_params(PROPOSAL_COLS)}) "
                   "ON CONFLICT (id) DO UPDATE SET run_id = coalesce(EXCLUDED.run_id, ml_proposals.run_id), "
                   "outcome = coalesce(EXCLUDED.outcome, ml_proposals.outcome), "
                   "rationale = coalesce(EXCLUDED.rationale, ml_proposals.rationale), "
                   "source = coalesce(EXCLUDED.source, ml_proposals.source)")
EVENT_INSERT = (f"INSERT INTO ml_events ({', '.join(EVENT_COLS)}) VALUES ({_params(EVENT_COLS)}) "
                "ON CONFLICT (id) DO NOTHING")


async def setup(con: asyncpg.Connection) -> None:
    """Create the Lab tables and model_runs columns. Idempotent; run after dvm.predict.schema.setup."""
    await con.execute(SCHEMA)
