#!/usr/bin/env python3
"""Orchestrator: DeepSeek review of new commits, with verdict memory in SQLite.

Stdlib only. Talks to llama-server's OpenAI-compatible API.

  orch.py review REPO_PATH [--path P ...]   review commits since the last reviewed one (--path: scoped review)
  orch.py baseline REPO_PATH COMMIT  set the reviewed marker without a review (no model); records what it waived
  orch.py findings [--all] [--repo PATH]
  orch.py verdict ID accepted|rejected REASON [--by NAME]
  orch.py runs [-n N]
"""
import argparse, fnmatch, getpass, hashlib, json, os, re, sqlite3, subprocess, sys, time, urllib.error, urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

DB = Path(os.environ.get("ORCH_DB", "/data/orch/orch.db"))
API = os.environ.get("ORCH_API", "http://127.0.0.1:8080")
MODEL = os.environ.get("ORCH_MODEL", "deepseek-v4-flash")
HERE = Path(__file__).resolve().parent

# Size rules. A path over its cap or past the ceiling is recorded in review_paths and the review is refused; nothing is
# sent partly. The token guard (below) is the limit that binds; the ceiling only keeps a whole-tree diff from being
# built and posted to /input_tokens.
MAX_FILE_DIFF_CHARS = 32_000  # per-file diff cap for source
MAX_DATA_DIFF_CHARS = 20_000  # per-file diff cap for results/ and .jsonl
MAX_DIFF_CHARS = 300_000      # loose ceiling, far above what fits the 64k context
CONTEXT_FILES = ("orchestrator/context.md", "CLAUDE.md")  # the context slot; README.md is not sent whole
SCOPE_FILE = "orchestrator/scope.txt"  # fnmatch globs (one per line, # comments) of paths excluded from review
SAMPLE_LINES, SAMPLE_LINE_CHARS = 3, 1500  # head sample of each excluded file that changed
SAMPLE_TOTAL_CHARS = 13_500   # all samples together: three files at the per-file maximum (run 4: 38 files, 72,502 chars)
SAMPLE_NAMES_MAX = 50         # past the budget excluded paths are only listed, at most this many, then a count
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
    version = db.execute("PRAGMA user_version").fetchone()[0]
    if version < 2:
        schema = (HERE / "schema.sql").read_text()
        # user_version 0: the whole file. 1: only the v2 block, which is idempotent.
        db.executescript(schema if version < 1 else
                         "-- schema:v2" + schema.split("-- schema:v2", 1)[1].split("-- llmctl:sessions", 1)[0])
        db.execute("PRAGMA user_version=2")
    return db


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout


def load_scope(repo, ref):
    """(blob id, globs) of SCOPE_FILE as committed at ref; (None, []) if the repo has none."""
    try:
        blob = git(repo, "rev-parse", f"{ref}:{SCOPE_FILE}").strip()
        text = git(repo, "show", f"{ref}:{SCOPE_FILE}")
    except subprocess.CalledProcessError:
        return None, []
    return blob, [l.strip() for l in text.splitlines() if l.strip() and not l.strip().startswith("#")]


def is_excluded(path, globs):
    return any(fnmatch.fnmatchcase(path, g) for g in globs)


def in_scope(path, scope):
    return not scope or any(path == p or path.startswith(p + "/") for p in scope)


def file_cap(path):
    return MAX_DATA_DIFF_CHARS if path.endswith(".jsonl") or "/results/" in "/" + path else MAX_FILE_DIFF_CHARS


def changed_files(repo, base, head):
    return [f for f in git(repo, "diff", "--name-only", "-z", base, head).split("\0") if f]


def build_diff(repo, base, head, scope=(), globs=()):
    """Per-file diff of base..head. Returns (text, dispositions, sampled): path -> sent | oversize | budget |
    out_of_scope | excluded (the review_paths values). Only 'sent' paths are diffed in the text. A changed excluded path
    that still exists at head contributes its first lines, so code that reads it is not judged blind (run 2), until
    SAMPLE_TOTAL_CHARS is used up; the rest are listed by name only (at most SAMPLE_NAMES_MAX, then a count). `sampled`
    is the set of excluded paths whose sample went in. Nothing here refuses: the token guard is the hard stop."""
    parts, samples, names, disp, sampled, total, used = [], [], [], {}, set(), 0, 0
    for f in changed_files(repo, base, head):
        if is_excluded(f, globs):
            disp[f] = "excluded"
            try:
                lines = [l[:SAMPLE_LINE_CHARS] for l in git(repo, "show", f"{head}:{f}").splitlines()[:SAMPLE_LINES]]
            except subprocess.CalledProcessError:
                lines = []
            body = sum(len(l) for l in lines)
            if lines and used + body <= SAMPLE_TOTAL_CHARS:
                used += body
                sampled.add(f)
                samples.append(f"  {f}" + "".join(f"\n    | {l}" for l in lines))
            else:
                names.append(f)
            continue
        if not in_scope(f, scope):
            disp[f] = "out_of_scope"
            continue
        d = git(repo, "diff", base, head, "--", f)
        if len(d) > file_cap(f):
            disp[f] = "oversize"
        elif total + len(d) > MAX_DIFF_CHARS:
            disp[f] = "budget"
        else:
            disp[f] = "sent"
            parts.append(d)
            total += len(d)
    if samples:
        parts.append("Excluded from review by orchestrator/scope.txt (changed, not diffed; first lines at HEAD):\n"
                     + "\n".join(samples))
    if names:
        shown = ", ".join(names[:SAMPLE_NAMES_MAX]) + (f", and {len(names) - SAMPLE_NAMES_MAX} more excluded"
                                                       if len(names) > SAMPLE_NAMES_MAX else "")
        parts.append(f"Also excluded, no sample (sample budget {SAMPLE_TOTAL_CHARS} chars used or file gone): {shown}")
    return "\n".join(parts), disp, sampled


def repo_context(repo):
    out = []
    for name in CONTEXT_FILES:
        p = Path(repo) / name
        if p.exists():
            out.append(f"===== {name} =====\n{p.read_text()}")
    return "\n\n".join(out)


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


def chat_body(messages):
    return {"model": MODEL, "messages": messages, "temperature": 0.2, "max_tokens": MAX_TOKENS,
            "reasoning_budget_tokens": REASONING_BUDGET,
            "reasoning_budget_message": "Reasoning budget reached. Write the JSON answer now.",
            "response_format": {"type": "json_schema", "json_schema": {"name": "review", "schema": SCHEMA}}}


def api(path, body=None, timeout=3600):
    req = urllib.request.Request(f"{API}{path}", None if body is None else json.dumps(body).encode(),
                                 {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def chat(messages):
    return api("/v1/chat/completions", chat_body(messages))


def token_guard(messages):
    """The review's own rule, stricter than the server's (which only rejects prompt >= slot): the prompt plus the
    full completion must fit the slot. Measured by the server on the exact body: /input_tokens renders the chat
    template and tokenizes as /v1/chat/completions does; the slot size is /props default_generation_settings.n_ctx.
    Returns None if it fits, else the reason; any failure to measure is a refusal."""
    try:
        n_ctx = int(api("/props", timeout=30)["default_generation_settings"]["n_ctx"])
        tokens = int(api("/v1/chat/completions/input_tokens", chat_body(messages), timeout=300)["input_tokens"])
    except (urllib.error.URLError, OSError, ValueError, KeyError, TypeError) as e:
        return f"cannot measure the prompt ({type(e).__name__}: {e})"
    if tokens + MAX_TOKENS > n_ctx:
        return f"prompt {tokens} tokens + completion {MAX_TOKENS} > slot {n_ctx}"
    return None


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


def record_paths(db, run_id, disp):
    with db:
        db.executemany("INSERT INTO review_paths (run_id, path, disposition) VALUES (?, ?, ?)",
                       [(run_id, path, d) for path, d in disp.items()])


def cmd_review(a):
    repo = Path(a.repo).resolve()
    scope = tuple(p.strip("/") for p in a.path)
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

    def refuse(note, chars=None):
        record_paths(db, run_id, disp)
        finish(db, run_id, "error", f"refused: {note}", diff_chars=chars, truncated=1)
        sys.exit(f"refused: {note}")

    _, globs = load_scope(repo, head)
    diff, disp, sampled = build_diff(repo, base or EMPTY_TREE, head, scope, globs)
    chars = len(diff)  # the whole diff text the model gets, samples included (run 4 stored only the sent diffs)
    omitted = sorted(p for p, d in disp.items() if d in ("oversize", "budget"))
    if omitted:
        shown = ", ".join(f"{p} ({disp[p]})" for p in omitted[:10]) + (" ..." if len(omitted) > 10 else "")
        refuse(f"{len(omitted)} path(s) not sent in full: {shown}", chars)
    if "sent" not in disp.values():
        # Nothing in scope changed (only excluded or --path-filtered paths). No model call, and the marker stays: the
        # next real change is reviewed together with this range, so nothing is claimed that was not looked at.
        record_paths(db, run_id, disp)
        counts = ", ".join(f"{n} {d}" for d, n in sorted(Counter(disp.values()).items())) or "no files"
        finish(db, run_id, "skipped", f"nothing reviewable in range ({counts}); marker unchanged", diff_chars=0)
        return print(f"skipped: nothing reviewable in range ({counts}); marker unchanged")
    log = git(repo, "log", "--oneline", f"{base}..{head}" if base else head).strip()
    # Order: static -> slow-changing -> per-run, so llama-server's prompt cache reuses the longest prefix.
    user = (f"Repository: {repo.name}\n\n{repo_context(repo)}\n\n"
            f"===== Past verdicts =====\n{memory(db, r['id'], [p for p, d in disp.items() if d == "sent" or p in sampled])}\n\n"
            f"===== Commits under review =====\n{log}\n\n"
            + (f"===== Scope =====\nOnly these paths are included: {', '.join(scope)}\n\n" if scope else "")
            + f"===== Diff =====\n{diff}")
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]
    why = token_guard(messages)
    if why:
        disp = {p: "budget" if d == "sent" else d for p, d in disp.items()}
        refuse(why, chars)
    record_paths(db, run_id, disp)
    t = time.time()
    resp = None
    try:
        resp = chat(messages)
        choice = resp["choices"][0]
        content = choice["message"]["content"]
        found = json.loads(content)["findings"]
        new = 0
        with db:  # findings and marker commit together or not at all
            for f in found:
                # ON CONFLICT only covers the (repo_id, fingerprint) dedup; a CHECK failure must still raise
                cur = db.execute("INSERT INTO findings (run_id, repo_id, fingerprint, file, line, severity, "
                                 "title, detail) VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
                                 "ON CONFLICT (repo_id, fingerprint) DO NOTHING",
                                 (run_id, r["id"], fingerprint(f["file"], f["title"]), f["file"], f["line"] or None,
                                  f["severity"], f["title"], f["detail"]))
                new += cur.rowcount
            if all(d in ("sent", "excluded") for d in disp.values()):  # a scoped review never moves the marker
                db.execute("UPDATE repos SET last_reviewed_commit = ? WHERE id = ?", (head, r["id"]))
    except Exception as e:
        note = f"{type(e).__name__}: {e}"
        if resp:
            note += f" (finish_reason={resp['choices'][0].get('finish_reason')})"
        finish(db, run_id, "error", note, seconds=round(time.time() - t, 1), diff_chars=chars,
               raw_response=json.dumps(resp) if resp else None)
        sys.exit(f"error: {note}")
    u = resp.get("usage", {})
    finish(db, run_id, "ok", f"{len(found)} reported, {new} new", seconds=round(time.time() - t, 1),
           diff_chars=chars, raw_response=content,
           prompt_tokens=u.get("prompt_tokens"), completion_tokens=u.get("completion_tokens"),
           cached_tokens=(u.get("prompt_tokens_details") or {}).get("cached_tokens"))
    print(f"run {run_id}: {len(found)} findings ({new} new) in {time.time() - t:.0f}s")


def is_ancestor(repo, a, b):
    return subprocess.run(["git", "-C", str(repo), "merge-base", "--is-ancestor", a, b],
                          capture_output=True).returncode == 0


def cmd_baseline(a):
    """Set the reviewed marker to COMMIT without reviewing: the way to start a repo whose empty-tree diff can never be
    sent in full. No model, no server. The run is kind 'review' (runs.kind has a CHECK), status 'skipped', and its
    note says what was waived; review_paths holds one row per path of the waived range."""
    repo = Path(a.repo).resolve()
    try:
        commit = git(repo, "rev-parse", "--verify", "--quiet", f"{a.commit}^{{commit}}").strip()
    except subprocess.CalledProcessError:
        sys.exit(f"refused: unknown commit {a.commit}")
    head = git(repo, "rev-parse", "HEAD").strip()
    if not is_ancestor(repo, commit, head):
        sys.exit(f"refused: {commit[:12]} is not HEAD or an ancestor of HEAD")
    db = connect()
    with db:
        db.execute("INSERT OR IGNORE INTO repos (path, name) VALUES (?, ?)", (str(repo), repo.name))
    r = db.execute("SELECT * FROM repos WHERE path = ?", (str(repo),)).fetchone()
    marker = r["last_reviewed_commit"]
    if marker:  # a second stamp would waive the commits since the first one without a review
        sys.exit(f"refused: a marker already exists ({marker[:12]}); a baseline only initialises, review instead")
    blob, globs = load_scope(repo, commit)
    disp = {f: "excluded" if is_excluded(f, globs) else "out_of_scope" for f in changed_files(repo, EMPTY_TREE, commit)}
    if "out_of_scope" not in disp.values():  # every path excluded (or no files): the baseline would waive nothing real
        sys.exit("refused: no path is left in scope, a baseline over this tree would be vacuous")
    with db:  # run, rows, note and marker commit together or not at all
        run_id = db.execute("INSERT INTO runs (repo_id, kind, model, base_commit, head_commit, status) "
                            "VALUES (?, 'review', NULL, NULL, ?, 'skipped')", (r["id"], commit)).lastrowid
        note = {"baseline": True, "commit": commit, "user": getpass.getuser(),
                "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "scope_blob": blob, "globs": globs,
                "statement": "no model ran; no findings produced; paths not sent are not reviewed", "run_id": run_id}
        db.execute("UPDATE runs SET note = ?, finished_at = strftime('%Y-%m-%dT%H:%M:%SZ','now') WHERE id = ?",
                   (json.dumps(note), run_id))
        db.executemany("INSERT INTO review_paths (run_id, path, disposition) VALUES (?, ?, ?)",
                       [(run_id, path, d) for path, d in disp.items()])
        db.execute("UPDATE repos SET last_reviewed_commit = ? WHERE id = ?", (commit, r["id"]))
    n_ex = sum(d == "excluded" for d in disp.values())
    print(f"baseline run {run_id}: marker {commit[:12]}; {len(disp)} paths recorded "
          f"({n_ex} excluded, {len(disp) - n_ex} out_of_scope); no model ran")


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
        status = "BASELINE" if r["kind"] == "review" and r["status"] == "skipped" and r["model"] is None else r["status"]
        print(f"{r['id']:<4} {r['started_at']} {r['name']:<20} {status:<8} "
              f"{(r['seconds'] or 0):>6.0f}s p={r['prompt_tokens']} cached={r['cached_tokens']} "
              f"c={r['completion_tokens']}  {r['note'] or ''}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    s = p.add_subparsers(dest="cmd", required=True)
    x = s.add_parser("review"); x.add_argument("repo")
    x.add_argument("--path", action="append", default=[], help="scoped review: only this file or directory (repeatable)")
    x.set_defaults(fn=cmd_review)
    x = s.add_parser("baseline"); x.add_argument("repo"); x.add_argument("commit"); x.set_defaults(fn=cmd_baseline)
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
