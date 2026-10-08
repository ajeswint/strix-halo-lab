#!/usr/bin/env python3
"""Tests for orchestrator/orch.py. No GPU, no model: every case runs `orch.py review` as a subprocess against a
throwaway git repo, a throwaway DB (ORCH_DB) and a stub llama-server on a random 127.0.0.1 port (ORCH_API).
The real DB and the real server on :8080 are never touched. Safe to run anytime, including with a model resident.
Usage: python3 orchestrator/test_orch.py

These are the hygiene fixtures written BEFORE the fixes (accord points 2-8, 10). Expected on the unfixed orch.py:
the control, the at-the-boundary allowance and the two Regression cases pass, everything else fails. Not written yet: the content of orchestrator/context.md (point 2). The review_paths design and the --path CLI were
approved by the user 2026-10-08.
"""
import json, os, sqlite3, subprocess, sys, tempfile, threading, unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ORCH = str(Path(__file__).resolve().parent / "orch.py")
MAX_TOKENS = 12288
GIT_ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
           "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null"}
V1_DDL = """-- Orchestrator memory, schema v1. Applied by orch.py when PRAGMA user_version < 1.
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
"""  # schema.sql as of 30c7f6b (user_version 1), frozen for the upgrade test
GOOD_FINDING = {"file": "a.py", "line": 1, "severity": "low", "title": "t", "detail": "d"}


class Stub:
    """Stub llama-server. Records every request; answers are set per test."""

    def __init__(self):
        self.requests = []                 # (path, parsed json body or None)
        self.n_ctx = 65536                 # None -> /props without the field
        self.input_tokens = 1000           # int, or None -> HTTP 500
        self.findings = [GOOD_FINDING]
        stub = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, code, obj):
                data = json.dumps(obj).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                stub.requests.append((self.path, None))
                if self.path == "/health":
                    return self._send(200, {"status": "ok"})
                if self.path == "/props":
                    gs = {} if stub.n_ctx is None else {"n_ctx": stub.n_ctx}
                    return self._send(200, {"default_generation_settings": gs})
                self._send(404, {"error": "no"})

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                stub.requests.append((self.path, body))
                if self.path == "/v1/chat/completions/input_tokens":
                    if stub.input_tokens is None:
                        return self._send(500, {"error": "boom"})
                    return self._send(200, {"input_tokens": stub.input_tokens})
                if self.path == "/v1/chat/completions":
                    return self._send(200, {
                        "choices": [{"message": {"content": json.dumps({"findings": stub.findings})},
                                     "finish_reason": "stop"}],
                        "usage": {"prompt_tokens": 1, "completion_tokens": 1}})
                self._send(404, {"error": "no"})

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()

    def chats(self):
        return [b for p, b in self.requests if p == "/v1/chat/completions"]

    def counts(self):
        return [b for p, b in self.requests if p == "/v1/chat/completions/input_tokens"]

    def prompt(self):
        """All message text of the first chat request ('' if none was sent)."""
        c = self.chats()
        return "\n".join(m["content"] for m in c[0]["messages"]) if c else ""


def sentinel(name, where):
    return f"SENTINEL-{where}-{name}"


def big_file(name, chars):
    """A source file of about `chars` characters, first and last line carry sentinels."""
    body = "".join(f"# {i:05d} " + "x" * 70 + "\n" for i in range(max(chars // 80 - 2, 0)))
    return f"# {sentinel(name, 'START')}\n{body}# {sentinel(name, 'END')}\n"


class OrchCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="orch-test-")
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name, "repo")
        self.repo.mkdir()
        self.db = Path(self.tmp.name, "orch.db")
        self.stub = Stub()
        self.addCleanup(self.stub.close)
        self.git("init", "-q")
        self.write("README.md", "readme\n")
        self.write("CLAUDE.md", "project rules\n")

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.repo), *args], check=True, capture_output=True, text=True,
                              env={**os.environ, **GIT_ENV}).stdout.strip()

    def write(self, name, text):
        p = self.repo / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)

    def commit(self, msg="c"):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", msg)
        return self.git("rev-parse", "HEAD")

    def review(self, api=None, *extra):
        env = {**os.environ, **GIT_ENV, "ORCH_DB": str(self.db), "ORCH_API": api or self.stub.url}
        r = subprocess.run([sys.executable, ORCH, "review", str(self.repo), *extra], env=env, capture_output=True,
                           text=True, timeout=120)
        return r.returncode, r.stdout + r.stderr

    def marker(self):
        with sqlite3.connect(self.db) as c:
            row = c.execute("SELECT last_reviewed_commit FROM repos WHERE path = ?",
                            (str(self.repo.resolve()),)).fetchone()
        return row[0] if row else None

    def dispositions(self, run_id=None):
        """{path: disposition} of the last run (or run_id)."""
        with sqlite3.connect(self.db) as c:
            rid = run_id or c.execute("SELECT max(id) FROM runs").fetchone()[0]
            return dict(c.execute("SELECT path, disposition FROM review_paths WHERE run_id = ?", (rid,)).fetchall())

    def runs(self):
        with sqlite3.connect(self.db) as c:
            return c.execute("SELECT status, note FROM runs ORDER BY id").fetchall()

    def assert_marker_invariant(self, head, names):
        """Accord point 4: the marker is at HEAD only if every file's diff was sent in full (END sentinel)."""
        if self.marker() == head:
            prompt = self.stub.prompt()
            missing = [n for n in names if sentinel(n, "END") not in prompt]
            self.assertEqual(missing, [], f"marker advanced to HEAD but these files were not sent in full: {missing}")

    def assert_refused(self, rc, head, why):
        """Refusal: no chat call, no 'ok' run, none left 'running', marker not advanced."""
        self.assertEqual(self.stub.chats(), [], f"{why}: the model was called")
        self.assertNotEqual(self.marker(), head, f"{why}: marker advanced")
        statuses = [s for s, _ in self.runs()]
        self.assertTrue(statuses, f"{why}: no run row recorded")
        self.assertNotIn("running", statuses, f"{why}: run left 'running'")
        self.assertNotIn("ok", statuses, f"{why}: run recorded ok")


class Control(OrchCase):
    def test_small_clean_review_completes(self):
        """Harness check; passes before and after the fixes."""
        self.write("a.py", "print(1)\n")
        head = self.commit()
        rc, out = self.review()
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.marker(), head)
        self.assertEqual([s for s, _ in self.runs()], ["ok"])
        self.assertIn("print(1)", self.stub.prompt())


class Context(OrchCase):
    def test_claude_md_reaches_the_reviewer_even_with_a_large_readme(self):
        """Point 2: repo_context() slices README+CLAUDE.md at 24,000 chars; CLAUDE.md is never sent."""
        self.write("README.md", "".join(f"readme line {i:05d} " + "r" * 60 + "\n" for i in range(340)))  # ~27,500 chars: over the old 24,000 slice, under the per-file cap
        self.write("CLAUDE.md", "RULE-SENTINEL-CLAUDE: do not propose Docker\n")
        self.commit("first")
        rc, out = self.review()
        self.assertEqual(rc, 0, out)
        # Second review: CLAUDE.md is not in this diff, so it can only arrive through the context slot.
        self.stub.requests.clear()
        self.write("a.py", "print(1)\n")
        self.commit("second")
        rc, out = self.review()
        self.assertEqual(rc, 0, out)
        self.assertIn("a.py", self.stub.prompt())
        self.assertNotIn("diff --git a/CLAUDE.md", self.stub.prompt())
        self.assertIn("RULE-SENTINEL-CLAUDE", self.stub.prompt())


class Omissions(OrchCase):
    def test_per_file_skip_blocks_the_marker(self):
        """Points 3-4: a source diff over the per-file cap is replaced by a 3-line sample; the run is stored
        not-truncated and the marker advances, so the file is never reviewed."""
        self.write("small.py", big_file("small", 500))
        self.write("huge.py", big_file("huge", 40_000))
        head = self.commit()
        rc, out = self.review()
        self.assert_marker_invariant(head, ["small", "huge"])

    def test_budget_exhaustion_blocks_the_marker(self):
        """Points 3-4: files past the aggregate diff budget are dropped; the marker still advances."""
        names = [f"f{i:02d}" for i in range(12)]
        for n in names:
            self.write(f"{n}.py", big_file(n, 15_000))
        head = self.commit()
        rc, out = self.review()
        self.assert_marker_invariant(head, names)

    def test_filename_with_spaces_is_reviewed(self):
        """Point 8: `git diff --name-only` + .split() turns 'my notes.py' into 'my' and 'notes.py'."""
        self.write("my notes.py", big_file("spaced", 500))
        head = self.commit()
        rc, out = self.review()
        self.assertIn(sentinel("spaced", "END"), self.stub.prompt())
        self.assert_marker_invariant(head, ["spaced"])


class Caps(OrchCase):
    """Points 5-6: 32,000 per-file cap for source, 20,000 for results/ and .jsonl; the aggregate character budget
    stops binding and the token guard decides."""

    def test_source_file_under_32000_is_sent(self):
        self.write("big.py", big_file("big", 30_000))
        head = self.commit()
        rc, out = self.review()
        self.assertEqual(rc, 0, out)
        self.assertIn(sentinel("big", "END"), self.stub.prompt())
        self.assertEqual(self.marker(), head)

    def test_source_file_over_32000_is_refused(self):
        self.write("tasks.py", big_file("tasks", 33_000))
        head = self.commit()
        rc, out = self.review()
        self.assert_refused(rc, head, "source diff over 32,000")

    def test_results_file_over_20000_is_refused(self):
        self.write("bench/loop/results/x.summary.json", big_file("summary", 24_000))
        head = self.commit()
        rc, out = self.review()
        self.assert_refused(rc, head, "results/ diff over 20,000")

    def test_diff_over_100000_chars_is_sent_when_tokens_fit(self):
        names = [f"g{i:02d}" for i in range(10)]
        for n in names:
            self.write(f"{n}.py", big_file(n, 12_000))
        head = self.commit()
        self.stub.input_tokens = 20_000
        rc, out = self.review()
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.marker(), head)
        missing = [n for n in names if sentinel(n, "END") not in self.stub.prompt()]
        self.assertEqual(missing, [])


class Regression(OrchCase):
    """Behaviour that holds before and after the fixes; they must not break."""

    def test_server_down_skips_and_leaves_the_marker(self):
        self.write("a.py", "print(1)\n")
        head = self.commit()
        rc, out = self.review(api="http://127.0.0.1:1")
        self.assertEqual(rc, 0, out)
        self.assertEqual([s for s, _ in self.runs()], ["skipped"])
        self.assertNotEqual(self.marker(), head)

    def test_duplicate_finding_is_still_deduplicated(self):
        """INSERT OR IGNORE has one legitimate use: UNIQUE (repo_id, fingerprint). The severity CHECK is not it."""
        self.write("a.py", "print(1)\n")
        self.commit("one")
        self.assertEqual(self.review()[0], 0)
        self.write("b.py", "print(2)\n")
        head = self.commit("two")
        rc, out = self.review()
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.marker(), head)
        with sqlite3.connect(self.db) as c:
            self.assertEqual(c.execute("SELECT count(*) FROM findings").fetchone()[0], 1)
        self.assertEqual([s for s, _ in self.runs()], ["ok", "ok"])


class ReviewPaths(OrchCase):
    """Approved design: table review_paths(run_id, path, disposition) in user_version 2. 'sent' = in the prompt of a
    run that went out; 'oversize' = over the per-file cap; 'budget' = dropped by the character ceiling or by a token
    guard refusal; 'out_of_scope' = filtered by --path. The marker moves only when every path is 'sent'."""

    def test_fresh_db_is_version_2_and_records_every_path(self):
        self.write("a.py", "print(1)\n")
        self.commit()
        rc, out = self.review()
        self.assertEqual(rc, 0, out)
        with sqlite3.connect(self.db) as c:
            self.assertEqual(c.execute("PRAGMA user_version").fetchone()[0], 2)
        self.assertEqual(self.dispositions(), {"README.md": "sent", "CLAUDE.md": "sent", "a.py": "sent"})

    def test_v1_database_is_upgraded_and_keeps_its_rows(self):
        with sqlite3.connect(self.db) as c:
            c.executescript(V1_DDL)
            c.execute("PRAGMA user_version=1")
            c.execute("INSERT INTO repos (path, name, last_reviewed_commit) VALUES ('/old', 'old', 'abc')")
            c.execute("INSERT INTO runs (repo_id, kind, status) VALUES (1, 'review', 'ok')")
            c.execute("INSERT INTO findings (run_id, repo_id, fingerprint, file, severity, title, detail) "
                      "VALUES (1, 1, 'fp', 'f.py', 'low', 't', 'd')")
            c.execute("INSERT INTO verdicts (finding_id, verdict, reason, decided_by) VALUES (1, 'rejected', 'r', 'aj')")
        self.write("a.py", "print(1)\n")
        head = self.commit()
        rc, out = self.review()
        self.assertEqual(rc, 0, out)
        with sqlite3.connect(self.db) as c:
            self.assertEqual(c.execute("PRAGMA user_version").fetchone()[0], 2)
            self.assertEqual(c.execute("SELECT count(*) FROM review_paths WHERE run_id = 1").fetchone()[0], 0)
            self.assertEqual(c.execute("SELECT last_reviewed_commit FROM repos WHERE id = 1").fetchone()[0], "abc")
            self.assertEqual(c.execute("SELECT verdict FROM verdicts").fetchone()[0], "rejected")
        self.assertEqual(self.marker(), head)

    def test_disposition_check_rejects_unknown_values(self):
        self.write("a.py", "print(1)\n")
        self.commit()
        self.assertEqual(self.review()[0], 0)
        with sqlite3.connect(self.db) as c:
            with self.assertRaises(sqlite3.IntegrityError):
                c.execute("INSERT INTO review_paths (run_id, path, disposition) VALUES (1, 'x', 'bogus')")

    def test_oversize_path_is_recorded_and_blocks_the_marker(self):
        self.write("small.py", big_file("small", 500))
        self.write("my huge.py", big_file("huge", 40_000))
        head = self.commit()
        rc, out = self.review()
        self.assert_refused(rc, head, "oversize path")
        d = self.dispositions()
        self.assertEqual(d["my huge.py"], "oversize")
        self.assertEqual(d["small.py"], "sent")

    def test_character_ceiling_records_budget_and_refuses(self):
        for i in range(30):
            self.write(f"h{i:02d}.py", big_file(f"h{i:02d}", 12_000))
        head = self.commit()
        rc, out = self.review()
        self.assert_refused(rc, head, "diff over the character ceiling")
        self.assertIn("budget", self.dispositions().values())

    def test_token_guard_refusal_records_budget_not_sent(self):
        self.write("a.py", "print(1)\n")
        head = self.commit()
        self.stub.input_tokens = 60_000
        rc, out = self.review()
        self.assert_refused(rc, head, "guard refusal")
        self.assertEqual(set(self.dispositions().values()), {"budget"})

    def test_scoped_review_runs_but_does_not_move_the_marker(self):
        self.write("src/a.py", "print(1)\n")
        self.write("docs/b.md", "doc B-ONLY-SENTINEL\n")
        head = self.commit()
        rc, out = self.review(None, "--path", "src")
        self.assertEqual(rc, 0, out)
        self.assertEqual([s for s, _ in self.runs()], ["ok"])
        self.assertIn("print(1)", self.stub.prompt())
        self.assertNotIn("B-ONLY-SENTINEL", self.stub.prompt())
        self.assertEqual(self.dispositions(), {"src/a.py": "sent", "docs/b.md": "out_of_scope",
                                               "README.md": "out_of_scope", "CLAUDE.md": "out_of_scope"})
        self.assertNotEqual(self.marker(), head)

    def test_scoped_review_that_covers_every_path_moves_the_marker(self):
        self.write("src/a.py", "print(1)\n")
        head = self.commit()
        rc, out = self.review(None, "--path", "src", "--path", "README.md", "--path", "CLAUDE.md")
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.marker(), head)

    def test_full_review_after_a_scoped_one_still_covers_everything(self):
        self.write("src/a.py", "print(1)\n")
        self.write("docs/b.md", "doc B-ONLY-SENTINEL\n")
        head = self.commit()
        self.assertEqual(self.review(None, "--path", "src")[0], 0)
        self.stub.requests.clear()
        rc, out = self.review()
        self.assertEqual(rc, 0, out)
        self.assertIn("B-ONLY-SENTINEL", self.stub.prompt())
        self.assertEqual(self.marker(), head)


class InsertFailure(OrchCase):
    def test_finding_missing_a_field_marks_the_run_error(self):
        """Point 7: the finding loop is outside the try block; a missing field raises KeyError there, finish() is
        never called and the run row stays 'running'."""
        self.stub.findings = [{k: v for k, v in GOOD_FINDING.items() if k != "line"}]
        self.write("a.py", "print(1)\n")
        head = self.commit()
        rc, out = self.review()
        self.assertNotEqual(rc, 0)
        self.assertEqual([s for s, _ in self.runs()], ["error"], out)
        self.assertNotEqual(self.marker(), head)

    def test_finding_with_a_bad_severity_is_not_dropped_silently(self):
        """Point 7 (found by this fixture): INSERT OR IGNORE swallows a CHECK violation too, so a finding with
        severity 'critical' is dropped, the run is recorded ok and the marker advances."""
        self.stub.findings = [{**GOOD_FINDING, "severity": "critical"}]
        self.write("a.py", "print(1)\n")
        head = self.commit()
        rc, out = self.review()
        self.assertNotEqual(rc, 0, out)
        self.assertEqual([s for s, _ in self.runs()], ["error"], out)
        self.assertNotEqual(self.marker(), head)


class TokenGuard(OrchCase):
    """Point 6: input_tokens + 12,288 must fit the live slot size from /props; any failure to measure refuses."""

    def setUp(self):
        super().setUp()
        self.write("a.py", "print(1)\n")
        self.head = self.commit()

    def test_guard_measures_the_exact_review_body(self):
        rc, out = self.review()
        self.assertEqual(rc, 0, out)
        self.assertEqual(len(self.stub.counts()), 1, "input_tokens was not called once")
        self.assertEqual(self.stub.counts()[0]["messages"], self.stub.chats()[0]["messages"])
        self.assertTrue(any(p == "/props" for p, _ in self.stub.requests), "/props was not read")

    def test_over_the_line_is_refused(self):
        self.stub.input_tokens = 60_000
        rc, out = self.review()
        self.assert_refused(rc, self.head, "60,000 + 12,288 > 65,536")

    def test_one_over_the_boundary_is_refused(self):
        self.stub.input_tokens = 65536 - MAX_TOKENS + 1
        rc, out = self.review()
        self.assert_refused(rc, self.head, "boundary + 1")

    def test_exactly_at_the_boundary_is_allowed(self):
        self.stub.input_tokens = 65536 - MAX_TOKENS
        rc, out = self.review()
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.marker(), self.head)

    def test_slot_size_is_read_live(self):
        self.stub.n_ctx = 32768
        self.stub.input_tokens = 30_000
        rc, out = self.review()
        self.assert_refused(rc, self.head, "30,000 + 12,288 > 32,768 (a hardcoded 65,536 would allow it)")

    def test_input_tokens_failure_refuses(self):
        self.stub.input_tokens = None
        rc, out = self.review()
        self.assert_refused(rc, self.head, "input_tokens HTTP 500")

    def test_props_without_n_ctx_refuses(self):
        self.stub.n_ctx = None
        rc, out = self.review()
        self.assert_refused(rc, self.head, "/props has no n_ctx")


if __name__ == "__main__":
    unittest.main(verbosity=2)
