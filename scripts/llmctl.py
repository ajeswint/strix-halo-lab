#!/usr/bin/env python3
"""llmctl: one controller for every model lifecycle, as sessions.

Usage: scripts/llmctl.py invite qwen|laguna|qwen32|r1d32|rag1|rag2|rerank [--backend vk|hip|cpu] [--ctx N] [--np N]
       scripts/llmctl.py invite deepseek
       scripts/llmctl.py bye
       scripts/llmctl.py swap <endpoint> [invite options]
       scripts/llmctl.py status
       scripts/llmctl.py run [--mem 8G] [--as 16G] -- <command ...>

Shape (SIP-like). An endpoint is a row in ENDPOINTS: a model behind a unit and a port. A session is one
endpoint resident in GPU memory: INVITE -> PREFLIGHT -> LOADING -> ACTIVE -> BYE -> ENDED, or FAILED
(ABORTED when the process vanished or the controller died mid-transition). One live session at a time,
enforced by a unique partial index in /data/orch/orch.db (orchestrator/schema.sql). State is reconciled
once per invocation; there is no polling and no watchdog.

Rules:
- invite runs scripts/preflight.sh on the model path (printed), starts the unit, waits a bounded time for
  /health. Any failure ends FAILED with the reason stored and the unit stopped.
- Fails closed: an unreadable mem_info_gtt_used refuses invite and swap (gpu-guard fails open; this does not).
- UNOWNED = a llama process, a registered unit or GTT above 16 GiB with no ACTIVE session. invite and swap
  refuse; `bye` ends a resident registered unit (no row needed) so the state can be cleaned up.
- Ending DeepSeek (bye, or swap away from it) needs an interactive TTY and the word yes.
- DeepSeek start/stop use `sudo -n systemctl start|stop llama-deepseek` (etc/sudoers.d/llmctl, installed by
  scripts/install-llmctl-sudoers.sh). Small models start through scripts/llm-serve.sh (its own preflight too).
- run wraps a client in a user scope with MemoryMax, MemorySwapMax=0 and RLIMIT_AS, only inside an ACTIVE
  session, and records the scope's memory.peak.

Exit codes: 0 ok, 1 failed, 2 usage, 3 refused (busy, unowned, GTT unreadable, no session, no TTY), 137 memory cap.
Test mode: LLMCTL_TEST_DIR=<dir> swaps in the test-only endpoints, <dir>/test.db and the fake GTT file
<dir>/gtt, and removes the real endpoints (see scripts/llmctl-test.py).
"""
import contextlib, glob, json, os, re, resource, signal, sqlite3, subprocess, sys, tempfile, time, urllib.request
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
GiB = 1 << 30
CUT = 16 * GiB                    # same cutoff as preflight.sh and gpu-guard.sh: above it a model is resident
DB_REAL = Path("/data/orch/orch.db")
SCHEMA = REPO / "orchestrator" / "schema.sql"
MARK = "-- llmctl:sessions"
SYSTEMCTL = "/usr/bin/systemctl"   # sudoers matches this exact path and these exact arguments
LIVE = ("INVITE", "PREFLIGHT", "LOADING", "ACTIVE", "BYE")
TEST_DIR = os.environ.get("LLMCTL_TEST_DIR")

TEST_SERVER = (
    "import http.server,sys\n"
    "class H(http.server.BaseHTTPRequestHandler):\n"
    "    def do_GET(s): s.send_response(200); s.end_headers(); s.wfile.write(b'ok')\n"
    "    def log_message(*a): pass\n"
    "http.server.HTTPServer(('127.0.0.1', int(sys.argv[1])), H).serve_forever()\n")


@dataclass(frozen=True)
class Endpoint:
    name: str
    kind: str                     # "user" (systemctl --user) or "system" (sudo -n systemctl)
    unit: str
    port: int
    model: str                    # model path (shard 1 of a split GGUF); preflight sizes it
    gtt_need: float               # GiB the model adds to GTT over the pre-invite baseline (measured); reported, not enforced
    serve: str = ""               # llm-serve.sh model name; empty = not started through llm-serve.sh
    confirm_end: bool = False     # ending it needs a TTY and the word yes
    health_wait: int = 180        # bounded seconds for /health after the start command returns
    test_only: bool = False
    preflight: tuple = ()         # test-only override of the preflight argv
    ctx: int = 32768              # default --ctx when invite does not give one (llm-serve.sh uses the same defaults)


# gtt_need is a delta (absolute GTT carries the ~5.8 GiB non-llama client). Measured 2026-10-07 (invite, sampler max):
# qwen +22.4 at ctx 65536 np 4 (28.2 over 5.8; the stale Qwen ended earlier: 28.3), file 20.8; deepseek +85.5
# (91.1 over 5.8 now, 91.47 peak over 5.8 in the v3 fixer run), file 84.7; laguna +20.7 at ctx 32768 np 1 (21.17
# over 0.52 idle, 2026-10-05 smoke), file 19.1. KV cache and buffers grow with ctx and np.
ENDPOINTS = {e.name: e for e in (
    Endpoint("qwen", "user", "llm-8081", 8081, "/data/models/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf", 22.4, serve="qwen"),
    Endpoint("laguna", "user", "llm-8081", 8081, "/data/models/Laguna-XS-2.1-Q4_K_M.gguf", 20.7, serve="laguna"),
    # CRAwDAD pair + RAGs: measured 2026-10-15 by scripts/first-load.sh (invite note at /health, vk, default ctx,
    # np 1, baseline 7.3 GiB, llama.cpp v0.7.0): qwen32 +26.7, r1d32 +26.8 (ctx 32768), rag1 +2.3, rag2 +1.8,
    # rerank +7.3 (ctx 8192). The estimates were 27.9 / 28.0 / 2.0 / 1.0 / 6.6. rag2 --backend cpu adds +0.0 (RAM).
    # One sample at /health, not a sampler max; GTT after the probe's requests was within 0.07 GiB of it.
    Endpoint("qwen32", "user", "llm-8081", 8081, "/data/models/Qwen3-32B-Q4_K_M.gguf", 26.7, serve="qwen32"),
    Endpoint("r1d32", "user", "llm-8081", 8081, "/data/models/DeepSeek-R1-Distill-Qwen-32B-Q4_K_M.gguf", 26.8,
             serve="r1d32"),
    Endpoint("rag1", "user", "llm-8081", 8081, "/data/models/rag/Qwen3-Embedding-0.6B-Q8_0.gguf", 2.3,
             serve="rag1", ctx=8192),
    Endpoint("rag2", "user", "llm-8081", 8081, "/data/models/rag/embeddinggemma-2-Q8_0.gguf", 1.8,
             serve="rag2", ctx=8192),
    Endpoint("rerank", "user", "llm-8081", 8081, "/data/models/rag/Qwen3-Reranker-4B.Q8_0.gguf", 7.3,
             serve="rerank", ctx=8192),
    # health_wait is a first value: the load took 21 s (2026-10-07, page cache state not checked, probably warm); a cold-cache load is unmeasured.
    Endpoint("deepseek", "system", "llama-deepseek", 8080,
             "/data/models/UD-IQ2_M/DeepSeek-V4-Flash-0731-UD-IQ2_M-00001-of-00003.gguf", 85.5,
             confirm_end=True, health_wait=600),
)}
TEST_ENDPOINTS = {e.name: e for e in (
    Endpoint("test", "user", "llmctl-test", 18081, "-", 0, test_only=True, health_wait=15, preflight=("true",)),
    Endpoint("testconf", "user", "llmctl-test", 18081, "-", 0, test_only=True, health_wait=15, preflight=("true",),
             confirm_end=True),
    Endpoint("testbad", "user", "llmctl-test", 18081, "-", 0, test_only=True, health_wait=15,
             preflight=("sh", "-c", "echo NOT READY; echo '- test: forced'; exit 1")),
    Endpoint("teststartfail", "user", "llmctl-test", 18081, "-", 0, test_only=True, health_wait=2, preflight=("true",)),
)}
REGISTRY = TEST_ENDPOINTS if TEST_DIR else ENDPOINTS


def say(msg):
    print(f"llmctl: {msg}", flush=True)


# ---- system state --------------------------------------------------------------------------------------

def gtt_used():
    """Max mem_info_gtt_used in bytes over the cards, or None when unreadable (callers fail closed)."""
    paths = [os.path.join(TEST_DIR, "gtt")] if TEST_DIR else sorted(glob.glob("/sys/class/drm/card*/device/mem_info_gtt_used"))
    best = None
    for p in paths:
        try:
            with open(p) as f:
                v = int(f.read().strip())
        except (OSError, ValueError):
            continue
        best = v if best is None else max(best, v)
    return best


def gib(b):
    return f"{b / GiB:.1f} GiB"


def ctl(ep):
    return ["systemctl", "--user"] if ep.kind == "user" else ["systemctl"]


def unit_active(ep):
    return subprocess.run(ctl(ep) + ["is-active", "-q", ep.unit]).returncode == 0


def main_pid(ep):
    r = subprocess.run(ctl(ep) + ["show", "-p", "MainPID", "--value", ep.unit], capture_output=True, text=True)
    try:
        return int(r.stdout.strip())
    except ValueError:
        return 0


def alive(pid):
    return bool(pid) and pid > 0 and os.path.exists(f"/proc/{pid}")


def owner_alive(pid):
    """The controller that wrote a transitional row is still running."""
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as f:
            return b"llmctl" in f.read()
    except OSError:
        return False


def llama_procs():
    if TEST_DIR:
        return []
    r = subprocess.run(["pgrep", "-a", "^llama-"], capture_output=True, text=True)
    return [l[:140] for l in r.stdout.splitlines() if l.strip()]


def stop_unit(ep):
    argv = ["systemctl", "--user", "stop", ep.unit] if ep.kind == "user" else ["sudo", "-n", SYSTEMCTL, "stop", ep.unit]
    return subprocess.run(argv, capture_output=True, text=True)


def health(ep, wait):
    """True once /health answers 200, within `wait` seconds and while the unit stays active."""
    end = time.monotonic() + wait
    while True:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{ep.port}/health", timeout=2) as r:
                if r.status == 200:
                    return True
        except Exception:
            pass
        if time.monotonic() >= end or not unit_active(ep):
            return False
        time.sleep(0.5)


# ---- session store -------------------------------------------------------------------------------------

def connect():
    path = Path(TEST_DIR) / "test.db" if TEST_DIR else DB_REAL
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    with db:
        db.executescript(SCHEMA.read_text().split(MARK, 1)[1])
    return db


def sset(db, sid, state=None, pid=None, note=None, end=False):
    with db:
        if state:
            db.execute("UPDATE sessions SET state=? WHERE id=?", (state, sid))
        if pid is not None:
            db.execute("UPDATE sessions SET pid=? WHERE id=?", (pid, sid))
        if note:
            db.execute("UPDATE sessions SET note=CASE WHEN note IS NULL OR note='' THEN ? ELSE note || '; ' || ? END WHERE id=?",
                       (note, note, sid))
        if end:
            db.execute("UPDATE sessions SET ended=strftime('%Y-%m-%dT%H:%M:%SZ','now') WHERE id=?", (sid,))


def live_row(db):
    return db.execute("SELECT * FROM sessions WHERE state IN (?,?,?,?,?) ORDER BY id DESC LIMIT 1", LIVE).fetchone()


def reconcile(db):
    """Once per invocation: a live row whose process is gone becomes ABORTED."""
    row = live_row(db)
    if not row:
        return
    ep = REGISTRY.get(row["endpoint"])
    if row["state"] == "ACTIVE":
        ok = ep is not None and unit_active(ep) and alive(row["pid"])
        why = "unit or process gone while ACTIVE" if ep else "endpoint not in the registry"
    else:
        ok = owner_alive(row["pid"])
        why = f"controller died in {row['state']}"
    if not ok:
        sset(db, row["id"], "ABORTED", note=why, end=True)
        say(f"session {row['id']} ({row['endpoint']}) ABORTED: {why}")


def residents():
    """What is in memory: llama processes, active registered units, GTT above the cutoff."""
    out = [f"process: {p}" for p in llama_procs()]
    seen = set()
    for ep in REGISTRY.values():
        if ep.unit not in seen and unit_active(ep):
            seen.add(ep.unit)
            out.append(f"unit active: {ep.unit}")
    g = gtt_used()
    if g is not None and g > CUT:
        out.append(f"GTT used {gib(g)} > 16 GiB")
    return out


# ---- helpers -------------------------------------------------------------------------------------------

def refuse(msg, rc=3):
    say(f"refused: {msg}")
    return rc


def preflight(ep):
    argv = list(ep.preflight) if ep.preflight else [str(HERE / "preflight.sh"), ep.model]
    r = subprocess.run(argv, capture_output=True, text=True)
    print(r.stdout, end="")
    if r.stderr:
        print(r.stderr, end="")
    return r.returncode == 0, " | ".join(l for l in r.stdout.splitlines() if l.startswith("-") or "NOT READY" in l)


def start_argv(ep, opts):
    if ep.test_only:
        if ep.name == "teststartfail":
            return ["false"]
        return ["systemd-run", "--user", "-q", f"--unit={ep.unit}", "--collect", "--property=Restart=no",
                "python3", "-I", "-c", TEST_SERVER, str(ep.port)]
    if ep.serve:
        ctx = opts["ctx"] if opts["ctx"] is not None else ep.ctx
        return [str(HERE / "llm-serve.sh"), "start", ep.serve, opts["backend"], str(ctx), str(opts["np"])]
    return ["sudo", "-n", SYSTEMCTL, "start", ep.unit]


def confirm_end(ep, what):
    """Ending DeepSeek needs a human at a terminal. Returns None when ok, else the refusal message."""
    if not ep.confirm_end:
        return None
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        return f"{what} needs an interactive terminal and the word yes; run it yourself"
    try:
        ans = input(f"llmctl: {what}. Type yes to continue: ")
    except EOFError:
        ans = ""
    return None if ans.strip() == "yes" else f"{what} not confirmed"


def stop_and_verify(db, sid, ep):
    """Stop the unit, then check GTT is back under the cutoff (bounded 30 s). Returns (ok, note)."""
    r = stop_unit(ep)
    if r.returncode != 0:
        return False, f"stop failed: {(r.stderr or r.stdout).strip()[:200]}"
    for _ in range(30):
        g = gtt_used()
        if g is not None and g <= CUT:
            return True, f"GTT after stop {gib(g)}"
        time.sleep(1)
    g = gtt_used()
    return False, f"GTT not released: {gib(g) if g is not None else 'unreadable'}"


def parse_opts(args):
    opts = {"backend": "vk", "ctx": None, "np": 1}     # ctx None = the endpoint's default (Endpoint.ctx)
    i = 0
    while i < len(args):
        a = args[i]
        if a in ("--backend", "--ctx", "--np") and i + 1 < len(args):
            v = args[i + 1]
            if a == "--backend":
                if v not in ("hip", "vk", "cpu"):
                    raise ValueError("backend must be hip, vk or cpu")
                opts["backend"] = v
            else:
                opts[a[2:]] = int(v)
            i += 2
        else:
            raise ValueError(f"unknown option {a}")
    return opts


# ---- commands ------------------------------------------------------------------------------------------

def do_invite(db, name, opts, note=None):
    ep = REGISTRY.get(name)
    if not ep:
        say(f"unknown endpoint {name!r}; known: {', '.join(REGISTRY)}")
        return 2
    g0 = gtt_used()
    if g0 is None:
        return refuse("mem_info_gtt_used is unreadable; failing closed")
    row = live_row(db)
    if row:
        return refuse(f"session {row['id']} ({row['endpoint']}) is {row['state']}; bye or swap first")
    res = residents()
    if res:
        return refuse("UNOWNED residents with no session: " + "; ".join(res) + ". End them with: scripts/llmctl.py bye")
    try:
        with db:
            cur = db.execute("INSERT INTO sessions (endpoint, state, pid, note) VALUES (?, 'INVITE', ?, ?)",
                             (name, os.getpid(), note))
    except sqlite3.IntegrityError:
        return refuse("another session went live first")
    sid = cur.lastrowid
    say(f"session {sid}: INVITE {name}")
    try:
        sset(db, sid, "PREFLIGHT")
        ok, why = preflight(ep)
        if not ok:
            sset(db, sid, "FAILED", note=f"preflight NOT READY: {why}", end=True)
            say(f"session {sid} FAILED: preflight NOT READY")
            return 1
        sset(db, sid, "LOADING")
        r = subprocess.run(start_argv(ep, opts))
        if r.returncode != 0:
            raise RuntimeError(f"start command exited {r.returncode}"
                               + (" (is the sudoers drop-in installed? scripts/install-llmctl-sudoers.sh)" if ep.kind == "system" else ""))
        if not health(ep, ep.health_wait):
            raise RuntimeError(f"no /health on :{ep.port} within {ep.health_wait} s or unit exited")
        g = gtt_used()
        sset(db, sid, "ACTIVE", pid=main_pid(ep), note=f"GTT {gib(g) if g is not None else '?'}, {f'+{(g - g0) / GiB:.1f}' if g is not None else '?'} over the {gib(g0)} before (expected +{ep.gtt_need:g} GiB)")
        say(f"session {sid}: ACTIVE {name} on :{ep.port}, GTT {gib(g) if g is not None else '?'}")
        return 0
    except BaseException as e:   # includes KeyboardInterrupt: nothing may stay resident under a FAILED row
        stop_unit(ep)
        sset(db, sid, "FAILED", pid=os.getpid(), note=f"{type(e).__name__}: {e}"[:300], end=True)
        say(f"session {sid} FAILED: {e}")
        return 1


def end_active(db, row, why):
    """BYE for the ACTIVE row. Returns rc."""
    ep = REGISTRY[row["endpoint"]]
    msg = confirm_end(ep, f"end {ep.name} (session {row['id']}, +{ep.gtt_need:g} GiB GTT)")
    if msg:
        return refuse(msg)
    sset(db, row["id"], "BYE", pid=os.getpid())
    ok, note = stop_and_verify(db, row["id"], ep)
    if ok:
        sset(db, row["id"], "ENDED", note=f"{why}; {note}" if why else note, end=True)
        say(f"session {row['id']}: ENDED {ep.name}; {note}")
        return 0
    sset(db, row["id"], "FAILED", note=note, end=True)
    say(f"session {row['id']} FAILED to end cleanly: {note}")
    return 1


def do_bye(db, why=None):
    row = live_row(db)
    if row and row["state"] == "ACTIVE":
        return end_active(db, row, why)
    if row:
        return refuse(f"session {row['id']} is {row['state']}; another llmctl is mid-transition")
    # no live session: end a resident registered unit, if any
    seen, rc = set(), 0
    for ep in REGISTRY.values():
        if ep.unit in seen or not unit_active(ep):
            continue
        seen.add(ep.unit)
        msg = confirm_end(ep, f"end UNOWNED unit {ep.unit}")
        if msg:
            return refuse(msg)
        with db:
            sid = db.execute("INSERT INTO sessions (endpoint, state, pid, note) VALUES (?, 'BYE', ?, 'unowned unit ended by bye')",
                             (f"unowned:{ep.unit}", os.getpid())).lastrowid
        ok, note = stop_and_verify(db, sid, ep)
        sset(db, sid, "ENDED" if ok else "FAILED", note=note, end=True)
        say(f"session {sid}: {'ENDED' if ok else 'FAILED'} unowned:{ep.unit}; {note}")
        rc = rc or (0 if ok else 1)
    left = llama_procs()
    if left:
        return refuse("llama processes outside any registered unit: " + "; ".join(left) + ". End them by hand")
    if not seen:
        g = gtt_used()
        if g is not None and g > CUT:
            return refuse(f"GTT used {gib(g)} but no registered unit is active; find the holder by hand")
        say("nothing resident")
    return rc


def do_swap(db, name, opts):
    if name not in REGISTRY:
        say(f"unknown endpoint {name!r}; known: {', '.join(REGISTRY)}")
        return 2
    if gtt_used() is None:
        return refuse("mem_info_gtt_used is unreadable; failing closed")
    row = live_row(db)
    if row and row["state"] != "ACTIVE":
        return refuse(f"session {row['id']} is {row['state']}; another llmctl is mid-transition")
    prior = None
    if row:
        prior = row["id"]
        rc = end_active(db, row, f"swap -> {name}")
        if rc:
            return rc
    elif residents():
        return refuse("UNOWNED residents with no session: " + "; ".join(residents()) + ". End them with: scripts/llmctl.py bye")
    return do_invite(db, name, opts, note=f"swap from session {prior}" if prior else None)


def do_status(db):
    row = live_row(db)
    g = gtt_used()
    print(f"gtt_used: {gib(g) if g is not None else 'UNREADABLE'}")
    for u in dict.fromkeys(e.unit for e in REGISTRY.values()):
        ep = next(e for e in REGISTRY.values() if e.unit == u)
        print(f"unit {u}: {'active' if unit_active(ep) else 'inactive'}")
    last = db.execute("SELECT * FROM sessions ORDER BY id DESC LIMIT 3").fetchall()
    for r in reversed(last):
        print(f"session {r['id']}: {r['endpoint']} {r['state']} started {r['started']}"
              + (f" ended {r['ended']}" if r["ended"] else "") + (f" | {r['note']}" if r["note"] else ""))
    if g is None:
        print("state: GTT unreadable (invite and swap refuse)")
        return 3
    if row:
        print(f"state: {row['state']} {row['endpoint']} (session {row['id']})")
        return 0
    res = residents()
    if res:
        print("state: UNOWNED - " + "; ".join(res))
        return 3
    print("state: idle")
    return 0


def parse_size(s):
    m = re.fullmatch(r"(\d+)([KMG])?", s.upper())
    if not m:
        raise ValueError(f"bad size {s!r}")
    return int(m.group(1)) * {"K": 1 << 10, "M": 1 << 20, "G": 1 << 30, None: 1}[m.group(2)]


def do_run(db, args):
    if "--" not in args:
        say("usage: run [--mem 8G] [--as 16G] -- <command ...>")
        return 2
    i = args.index("--")
    flags, cmd = args[:i], args[i + 1:]
    mem, as_ = "8G", "16G"
    j = 0
    try:
        while j < len(flags):
            if flags[j] == "--mem" and j + 1 < len(flags):
                mem = flags[j + 1]
            elif flags[j] == "--as" and j + 1 < len(flags):
                as_ = flags[j + 1]
            else:
                raise ValueError(f"unknown option {flags[j]}")
            j += 2
        mem_b, as_b = parse_size(mem), parse_size(as_)
    except ValueError as e:
        say(str(e))
        return 2
    if not cmd:
        say("usage: run [--mem 8G] [--as 16G] -- <command ...>")
        return 2
    row = live_row(db)
    if not row or row["state"] != "ACTIVE":
        return refuse("run needs an ACTIVE session; invite first")
    fd, out = tempfile.mkstemp(prefix="llmctl-run-")
    os.close(fd)
    argv = ["systemd-run", "--user", "--scope", "-q", "-p", f"MemoryMax={mem_b}", "-p", "MemorySwapMax=0",
            "-p", "OOMPolicy=continue", sys.executable, "-I", str(Path(__file__).resolve()), "_inner", out, str(as_b), "--", *cmd]
    rc = subprocess.run(argv).returncode
    try:
        res = json.loads(Path(out).read_text() or "{}")
    except (OSError, ValueError):
        res = {}
    finally:
        with contextlib.suppress(OSError):
            os.unlink(out)
    peak = res.get("peak")
    oom = res.get("oom_kill", 0)
    line = (f"run {os.path.basename(cmd[0])} rc={rc} memory.peak={peak >> 20 if peak is not None else '?'} MiB "
            f"cap={mem_b >> 20} MiB as={as_b >> 20} MiB")
    say(line)
    sset(db, row["id"], note=line[:200])
    if oom and rc != 0:
        say(f"memory cap: the command was killed at MemoryMax={mem_b >> 20} MiB (oom_kill={oom}); session {row['id']} stays ACTIVE")
        return 137
    return rc


def inner(out, as_b, cmd):
    """Runs inside the scope: apply RLIMIT_AS, run the command, then read this cgroup's memory.peak/events."""
    def limits():
        resource.setrlimit(resource.RLIMIT_AS, (as_b, as_b))
    p = subprocess.Popen(cmd, preexec_fn=limits)
    for s in (signal.SIGINT, signal.SIGTERM):
        signal.signal(s, lambda n, f: p.send_signal(n))
    rc = p.wait()
    rc = 128 - rc if rc < 0 else rc
    res = {"rc": rc}
    try:
        cg = "/sys/fs/cgroup" + open("/proc/self/cgroup").read().strip().split("::", 1)[1]
        res["peak"] = int(open(cg + "/memory.peak").read())
        ev = dict(l.split() for l in open(cg + "/memory.events").read().splitlines())
        res["oom_kill"] = int(ev.get("oom_kill", 0))
    except (OSError, ValueError, IndexError):
        pass
    Path(out).write_text(json.dumps(res))
    return rc


def main(argv):
    if len(argv) >= 2 and argv[0] == "_inner":
        rest = argv[1:]
        k = rest.index("--")
        return inner(rest[0], int(rest[1]), rest[k + 1:])
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 2
    cmd, rest = argv[0], argv[1:]
    if cmd not in ("invite", "bye", "swap", "status", "run"):
        say(f"unknown command {cmd!r}")
        return 2
    db = connect()
    reconcile(db)
    try:
        if cmd == "status":
            return do_status(db)
        if cmd == "bye":
            return do_bye(db)
        if cmd == "run":
            return do_run(db, rest)
        if not rest:
            say(f"usage: {cmd} <endpoint> [--backend vk|hip|cpu] [--ctx N] [--np N]")
            return 2
        opts = parse_opts(rest[1:])
        return do_invite(db, rest[0], opts) if cmd == "invite" else do_swap(db, rest[0], opts)
    except ValueError as e:
        say(str(e))
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
