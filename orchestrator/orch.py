#!/usr/bin/env python3
"""Orchestrator: DeepSeek review of new commits, with verdict memory in SQLite.

Stdlib only. Talks to llama-server's OpenAI-compatible API.

  orch.py review REPO_PATH           review commits since the last reviewed one
  orch.py findings [--all] [--repo PATH]
  orch.py verdict ID accepted|rejected REASON [--by NAME]
  orch.py runs [-n N]
"""
import argparse, hashlib, json, os, re, sqlite3, subprocess, sys, time, urllib.error, urllib.request
from pathlib import Path

DB = Path(os.environ.get("ORCH_DB", "/data/orch/orch.db"))
API = os.environ.get("ORCH_API", "http://127.0.0.1:8080")
MODEL = os.environ.get("ORCH_MODEL", "deepseek-v4-flash")
HERE = Path(__file__).resolve().parent

MAX_DIFF_CHARS = 100_000     # ~30k tokens; leaves room in the 64k context for context, memory, reasoning
MAX_FILE_DIFF_CHARS = 20_000  # bigger per-file diffs (logs, jsonl, lockfiles) are listed, not included
MAX_CONTEXT_CHARS = 24_000    # README + CLAUDE.md
SAMPLE_LINES, SAMPLE_LINE_CHARS = 3, 1500  # head sample of each file too large to diff
MEMORY_LIMIT = 30
REASONING_BUDGET = 6144      # server forces end-of-thinking here (llama.cpp reasoning_budget_tokens)
MAX_TOKENS = 12288           # reasoning + JSON answer; 8192 with no budget ran out mid-reasoning (run 1)
EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"

SYSTEM = """You are an adversarial code reviewer for a single-developer repository.
Report only real defects: bugs, wrong claims in docs, unsafe commands, broken reproducibility, security or data-loss risks.
Do not report style, naming, or missing features. Do not repeat issues that past verdicts rejected; their reasons are given.
Each finding: the file path as shown in the diff, the line in the new file (0 if unknown), severity
(high = breaks something or loses data, medium = wrong result or misleading doc, low = minor but real),
a title under 100 characters, and a detail that states the concrete failure scenario.
An empty findings list is a valid answer."""

SCHEMA = {
    "type": "object",
    "properties": {"findings": {"type": "array", "items": {
        "type": "object",
        "properties": {
            "file": {"type": "string"},
            "line": {"type": "integer"},
            "severity": {"type": "string", "enum": ["high", "medium", "low"]},
            "title": {"type": "string", "maxLength": 120},
            "detail": {"type": "string"},
        },
        "required": ["file", "line", "severity", "title", "detail"],
    }}},
    "required": ["findings"],
}


def connect():
    DB.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")
    if db.execute("PRAGMA user_version").fetchone()[0] < 1:
        with db:
            db.executescript((HERE / "schema.sql").read_text())
            db.execute("PRAGMA user_version=1")
    return db


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout


def build_diff(repo, base, head):
    """Per-file diff, skipping oversized files. Returns (text, chars, truncated, files)."""
    files = git(repo, "diff", "--name-only", base, head).split()
    parts, skipped, total, truncated = [], [], 0, False
    for f in files:
        d = git(repo, "diff", base, head, "--", f)
        if len(d) > MAX_FILE_DIFF_CHARS:
            # Show the data's shape so code that writes or reads it isn't judged blind (run 2 false positives).
            try:
                head_lines = git(repo, "show", f"{head}:{f}").splitlines()[:SAMPLE_LINES]
            except subprocess.CalledProcessError:
                head_lines = []
            sample = "".join(f"\n    | {l[:SAMPLE_LINE_CHARS]}" for l in head_lines)
            skipped.append(f"{f} ({len(d)} chars); first lines at HEAD:{sample}" if sample else f"{f} ({len(d)} chars)")
        elif total + len(d) > MAX_DIFF_CHARS:
            skipped.append(f"{f} (diff budget exhausted)")
            truncated = True
        else:
            parts.append(d)
            total += len(d)
    if skipped:
        parts.append("Not included (too large to diff; do not guess at their contents beyond the sample):\n"
                     + "\n".join("  " + s for s in skipped))
    return "\n".join(parts), total, truncated, files


def repo_context(repo):
    out = []
    for name in ("README.md", "CLAUDE.md"):
        p = Path(repo) / name
        if p.exists():
            out.append(f"===== {name} =====\n{p.read_text()}")
    return "\n\n".join(out)[:MAX_CONTEXT_CHARS]


def memory(db, repo_id, files):
    """Past decided findings: those on files in this diff first, then the most recent others."""
    q = """SELECT f.file, f.title, v.verdict, v.reason FROM findings f JOIN verdicts v ON v.finding_id = f.id
           WHERE f.repo_id = ? {} ORDER BY v.decided_at DESC LIMIT ?"""
    marks = ",".join("?" * len(files))
    rows = db.execute(q.format(f"AND f.file IN ({marks})"), (repo_id, *files, MEMORY_LIMIT)).fetchall() if files else []
    if len(rows) < MEMORY_LIMIT:
        seen = {(r["file"], r["title"]) for r in rows}
        rows += [r for r in db.execute(q.format(""), (repo_id, MEMORY_LIMIT)).fetchall()
                 if (r["file"], r["title"]) not in seen][: MEMORY_LIMIT - len(rows)]
    if not rows:
        return "No past verdicts yet."
    return "\n".join(f"- [{r['verdict']}] {r['file']}: {r['title']} -- reason: {r['reason']}" for r in rows)


def chat(messages):
    body = {"model": MODEL, "messages": messages, "temperature": 0.2, "max_tokens": MAX_TOKENS,
            "reasoning_budget_tokens": REASONING_BUDGET,
            "reasoning_budget_message": "Reasoning budget reached. Write the JSON answer now.",
            "response_format": {"type": "json_schema", "json_schema": {"name": "review", "schema": SCHEMA}}}
    req = urllib.request.Request(f"{API}/v1/chat/completions", json.dumps(body).encode(),
                                 {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=3600) as r:
        return json.load(r)


def server_up():
    try:
        with urllib.request.urlopen(f"{API}/health", timeout=5) as r:
            return r.status == 200
    except (urllib.error.URLError, OSError):
        return False


def fingerprint(file, title):
    norm = re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()
    return hashlib.sha1(f"{file}\0{norm}".encode()).hexdigest()


def finish(db, run_id, status, note=None, **cols):
    sets = ", ".join(f"{k} = ?" for k in cols)
    with db:
        db.execute(f"""UPDATE runs SET status = ?, note = ?, finished_at = strftime('%Y-%m-%dT%H:%M:%SZ','now')
                       {', ' + sets if sets else ''} WHERE id = ?""", (status, note, *cols.values(), run_id))


def cmd_review(a):
    repo = Path(a.repo).resolve()
    head = git(repo, "rev-parse", "HEAD").strip()
    db = connect()
    with db:
        db.execute("INSERT OR IGNORE INTO repos (path, name) VALUES (?, ?)", (str(repo), repo.name))
    r = db.execute("SELECT * FROM repos WHERE path = ?", (str(repo),)).fetchone()
    base = r["last_reviewed_commit"]
    with db:
        run_id = db.execute("INSERT INTO runs (repo_id, kind, model, base_commit, head_commit, status) "
                            "VALUES (?, 'review', ?, ?, ?, 'running')", (r["id"], MODEL, base, head)).lastrowid
    if base == head:
        finish(db, run_id, "skipped", "no new commits")
        return print("skipped: no new commits")
    if not server_up():
        finish(db, run_id, "skipped", f"server not reachable at {API}")
        return print("skipped: server down")

    diff, chars, truncated, files = build_diff(repo, base or EMPTY_TREE, head)
    log = git(repo, "log", "--oneline", f"{base}..{head}" if base else head).strip()
    # Order: static -> slow-changing -> per-run, so llama-server's prompt cache reuses the longest prefix.
    user = (f"Repository: {repo.name}\n\n{repo_context(repo)}\n\n"
            f"===== Past verdicts =====\n{memory(db, r['id'], files)}\n\n"
            f"===== Commits under review =====\n{log}\n\n===== Diff =====\n{diff}")
    t = time.time()
    resp = None
    try:
        resp = chat([{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}])
        choice = resp["choices"][0]
        content = choice["message"]["content"]
        found = json.loads(content)["findings"]
    except Exception as e:
        note = f"{type(e).__name__}: {e}"
        if resp:
            note += f" (finish_reason={resp['choices'][0].get('finish_reason')})"
        finish(db, run_id, "error", note, seconds=round(time.time() - t, 1), diff_chars=chars,
               truncated=int(truncated), raw_response=json.dumps(resp) if resp else None)
        sys.exit(f"error: {note}")
    u = resp.get("usage", {})
    new = 0
    with db:
        for f in found:
            cur = db.execute("INSERT OR IGNORE INTO findings (run_id, repo_id, fingerprint, file, line, severity, "
                             "title, detail) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                             (run_id, r["id"], fingerprint(f["file"], f["title"]), f["file"], f["line"] or None,
                              f["severity"], f["title"], f["detail"]))
            new += cur.rowcount
        db.execute("UPDATE repos SET last_reviewed_commit = ? WHERE id = ?", (head, r["id"]))
    finish(db, run_id, "ok", f"{len(found)} reported, {new} new", seconds=round(time.time() - t, 1),
           diff_chars=chars, truncated=int(truncated), raw_response=content,
           prompt_tokens=u.get("prompt_tokens"), completion_tokens=u.get("completion_tokens"),
           cached_tokens=(u.get("prompt_tokens_details") or {}).get("cached_tokens"))
    print(f"run {run_id}: {len(found)} findings ({new} new) in {time.time() - t:.0f}s")


def cmd_findings(a):
    db = connect()
    q = """SELECT f.id, f.severity, f.file, f.line, f.title, v.verdict FROM findings f
           JOIN repos r ON r.id = f.repo_id LEFT JOIN verdicts v ON v.finding_id = f.id WHERE 1=1"""
    args = []
    if not a.all:
        q += " AND v.verdict IS NULL"
    if a.repo:
        q += " AND r.path = ?"
        args.append(str(Path(a.repo).resolve()))
    q += " ORDER BY CASE f.severity WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, f.id"
    for f in db.execute(q, args):
        loc = f"{f['file']}:{f['line']}" if f["line"] else f["file"]
        print(f"#{f['id']:<4} {f['severity']:<6} {f['verdict'] or 'open':<8} {loc}  {f['title']}")
    if a.detail:
        row = db.execute("SELECT detail FROM findings WHERE id = ?", (a.detail,)).fetchone()
        print(row["detail"] if row else "no such finding")


def cmd_verdict(a):
    db = connect()
    if not db.execute("SELECT 1 FROM findings WHERE id = ?", (a.id,)).fetchone():
        sys.exit(f"no finding #{a.id}")
    with db:
        db.execute("INSERT INTO verdicts (finding_id, verdict, reason, decided_by) VALUES (?, ?, ?, ?) "
                   "ON CONFLICT (finding_id) DO UPDATE SET verdict = excluded.verdict, reason = excluded.reason, "
                   "decided_by = excluded.decided_by, decided_at = strftime('%Y-%m-%dT%H:%M:%SZ','now')",
                   (a.id, a.verdict, a.reason, a.by))
    print(f"#{a.id} {a.verdict}")


def cmd_runs(a):
    db = connect()
    for r in db.execute("SELECT r.*, p.name FROM runs r JOIN repos p ON p.id = r.repo_id ORDER BY r.id DESC LIMIT ?",
                        (a.n,)):
        print(f"{r['id']:<4} {r['started_at']} {r['name']:<20} {r['status']:<8} "
              f"{(r['seconds'] or 0):>6.0f}s p={r['prompt_tokens']} cached={r['cached_tokens']} "
              f"c={r['completion_tokens']}  {r['note'] or ''}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    s = p.add_subparsers(dest="cmd", required=True)
    x = s.add_parser("review"); x.add_argument("repo"); x.set_defaults(fn=cmd_review)
    x = s.add_parser("findings"); x.add_argument("--all", action="store_true"); x.add_argument("--repo")
    x.add_argument("--detail", type=int, metavar="ID"); x.set_defaults(fn=cmd_findings)
    x = s.add_parser("verdict"); x.add_argument("id", type=int)
    x.add_argument("verdict", choices=["accepted", "rejected"]); x.add_argument("reason")
    x.add_argument("--by", default="aj"); x.set_defaults(fn=cmd_verdict)
    x = s.add_parser("runs"); x.add_argument("-n", type=int, default=10); x.set_defaults(fn=cmd_runs)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
