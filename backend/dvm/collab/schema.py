"""Collaboration tables (issue #100): plain Postgres tables, created idempotently at start-up like dvm/store.py.

Presence is never stored (it lives in memory in dvm/collab/live.py). Documents and activity are append-only.
"""
from __future__ import annotations

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  auth0_sub text NOT NULL UNIQUE,              -- the identity: the verified access token's sub, never client input
  display_name text, picture_url text,         -- display only, posted by the client from its Auth0 profile
  created_at timestamptz NOT NULL DEFAULT now(), seen_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS collab_sessions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  title text NOT NULL, created_by uuid NOT NULL REFERENCES users(id), created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS collab_members (
  session_id uuid NOT NULL REFERENCES collab_sessions(id), user_id uuid NOT NULL REFERENCES users(id),
  role text NOT NULL CHECK (role IN ('owner', 'member')),
  joined_at timestamptz NOT NULL DEFAULT now(), last_active_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (session_id, user_id)
);
CREATE INDEX IF NOT EXISTS collab_members_user_active ON collab_members (user_id, last_active_at DESC);

-- One-time invite links: only the SHA-256 of the token is stored.
CREATE TABLE IF NOT EXISTS collab_invites (
  token_hash text PRIMARY KEY, session_id uuid NOT NULL REFERENCES collab_sessions(id),
  created_by uuid NOT NULL REFERENCES users(id), created_at timestamptz NOT NULL DEFAULT now(),
  expires_at timestamptz NOT NULL, used_at timestamptz, used_by uuid REFERENCES users(id)
);

-- The shared tracking list: one row per ship per session.
CREATE TABLE IF NOT EXISTS collab_list (
  session_id uuid NOT NULL REFERENCES collab_sessions(id), mmsi integer NOT NULL,
  status text NOT NULL CHECK (status IN ('open', 'reviewed', 'no_action')),
  added_by uuid NOT NULL REFERENCES users(id), added_at timestamptz NOT NULL DEFAULT now(),
  updated_by uuid NOT NULL REFERENCES users(id), updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (session_id, mmsi)
);

CREATE TABLE IF NOT EXISTS collab_documents (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, session_id uuid NOT NULL REFERENCES collab_sessions(id),
  mmsi integer, author_id uuid NOT NULL REFERENCES users(id),
  body text NOT NULL CHECK (length(body) BETWEEN 1 AND 4000), created_at timestamptz NOT NULL DEFAULT now()
);
-- kind: a note, a saved Brief me result (mmsis = the ships it covers) or the end-of-session summary.
ALTER TABLE collab_documents ADD COLUMN IF NOT EXISTS kind text NOT NULL DEFAULT 'note';
ALTER TABLE collab_documents ADD COLUMN IF NOT EXISTS mmsis integer[] NOT NULL DEFAULT '{}';
CREATE INDEX IF NOT EXISTS collab_documents_session ON collab_documents (session_id, created_at);

CREATE TABLE IF NOT EXISTS collab_activity (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, session_id uuid NOT NULL REFERENCES collab_sessions(id),
  actor_id uuid NOT NULL REFERENCES users(id), kind text NOT NULL, mmsi integer,
  at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS collab_activity_session_at ON collab_activity (session_id, at DESC);

-- dvm_append_only() comes from dvm/store.py, whose set-up has run before the store's pool exists.
CREATE OR REPLACE TRIGGER collab_documents_append_only BEFORE UPDATE OR DELETE ON collab_documents
  FOR EACH ROW EXECUTE FUNCTION dvm_append_only();
CREATE OR REPLACE TRIGGER collab_activity_append_only BEFORE UPDATE OR DELETE ON collab_activity
  FOR EACH ROW EXECUTE FUNCTION dvm_append_only();
"""


async def setup(con) -> None:
    await con.execute(SCHEMA)
