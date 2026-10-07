-- Orchestrator memory, schema v1. Applied by orch.py when PRAGMA user_version < 1.
-- The sessions table after the marker at the end is idempotent (IF NOT EXISTS): orch.py creates it on a fresh DB,
-- scripts/llmctl.py creates it on the existing one. user_version stays 1 by design.
-- One writer process at a time (the review job or a verdict command); WAL lets readers run alongside.

CREATE TABLE repos (
  id                   INTEGER PRIMARY KEY,
  path                 TEXT NOT NULL UNIQUE,
  name                 TEXT NOT NULL,
  last_reviewed_commit TEXT              -- HEAD of the last successful review; NULL = never reviewed
);

CREATE TABLE runs (
  id                INTEGER PRIMARY KEY,
  repo_id           INTEGER NOT NULL REFERENCES repos(id),
  kind              TEXT NOT NULL CHECK (kind IN ('review')),
  model             TEXT,
  base_commit       TEXT,              -- NULL on a first review (whole tree)
  head_commit       TEXT,
  status            TEXT NOT NULL CHECK (status IN ('running', 'ok', 'skipped', 'error')),
  note              TEXT,              -- why skipped, or the error
  started_at        TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  finished_at       TEXT,
  seconds           REAL,
  diff_chars        INTEGER,
  truncated         INTEGER NOT NULL DEFAULT 0,
  prompt_tokens     INTEGER,
  cached_tokens     INTEGER,
  completion_tokens INTEGER,
  raw_response      TEXT               -- model's JSON content, kept for audit
);

CREATE TABLE findings (
  id          INTEGER PRIMARY KEY,
  run_id      INTEGER NOT NULL REFERENCES runs(id),
  repo_id     INTEGER NOT NULL REFERENCES repos(id),
  fingerprint TEXT NOT NULL,           -- sha1(file + normalised title); same issue reported twice is stored once
  file        TEXT NOT NULL,
  line        INTEGER,                 -- NULL when the model gives 0 / unknown
  severity    TEXT NOT NULL CHECK (severity IN ('high', 'medium', 'low')),
  title       TEXT NOT NULL,
  detail      TEXT NOT NULL,
  created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  UNIQUE (repo_id, fingerprint)
);
CREATE INDEX findings_file ON findings (repo_id, file);

-- One verdict per finding; re-deciding overwrites. A finding with no row here is open.
CREATE TABLE verdicts (
  finding_id INTEGER PRIMARY KEY REFERENCES findings(id),
  verdict    TEXT NOT NULL CHECK (verdict IN ('accepted', 'rejected')),
  reason     TEXT NOT NULL,
  decided_by TEXT NOT NULL,            -- 'aj', 'claude', 'grok', ...
  decided_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- sessions: scripts/llmctl.py (one model resident at a time). Everything below the marker line is run by llmctl.py
-- on every connect; keep it idempotent.
-- llmctl:sessions
-- pid: llmctl's own pid while INVITE/PREFLIGHT/LOADING/BYE (so a dead controller is detectable), the server's
-- MainPID while ACTIVE. The unique partial index allows one live session at a time.
CREATE TABLE IF NOT EXISTS sessions (
  id       INTEGER PRIMARY KEY,
  endpoint TEXT NOT NULL,              -- registry name, or 'unowned:<unit>' for a resident model llmctl did not start
  state    TEXT NOT NULL CHECK (state IN ('INVITE', 'PREFLIGHT', 'LOADING', 'ACTIVE', 'BYE', 'ENDED', 'FAILED', 'ABORTED')),
  started  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  ended    TEXT,
  pid      INTEGER,
  note     TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS sessions_one_live ON sessions ((1))
  WHERE state IN ('INVITE', 'PREFLIGHT', 'LOADING', 'ACTIVE', 'BYE');
