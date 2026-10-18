#!/usr/bin/env python3
"""loop-v0 runner: N samples per task from the :8081 server, graded only by unit tests.

  run.py --selftest [--set v1]      refs must pass, empty solutions must fail (tests have teeth)
  run.py --label qwen-vk-np4 -n 4   generate + grade; writes results/<label>.jsonl and .summary.json
  --tasks id,id --seed-start 4      subset of the set, seeds 4..4+n-1 (extends an earlier run)

Grading runs each candidate in bwrap: no network, read-only /usr, only a scratch dir
writable, 1 GiB address-space cap, 60 s wall timeout. The oracle is not on disk: the harness
imports the solution, then reads the oracle from stdin; a static deny-list (deny_check) is a
tripwire, not isolation (README "Grader hardening"). pass@1 = mean pass rate over all
samples (unbiased for k=1); best-of-N = share of tasks where any sample passes, i.e. the
tests pick the candidate (oracle selection, the loop's intended use of tests).

GTT: a thread samples mem_info_gtt_used every 1 s while candidates are in flight and stores
the maximum as gtt_peak_gib. The idle baseline is not measured here (the server is already
loaded when run.py starts); pass preflight's pre-load gtt_used with --gtt-baseline to get
gtt_baseline_gib and gtt_model_gib = peak - baseline in the summary.
"""
import argparse, ast, concurrent.futures as cf, glob, json, os, re, resource, secrets, selectors, shutil, subprocess, symtable, sys, tempfile, threading, time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import importlib  # noqa: E402

SETS = {"v0": "tasks", "v1": "tasks_v1", "v2": "tasks_v2", "v3": "tasks_v3", "v4": "tasks_v4", "v5": "tasks_v5", "v6": "tasks_v6", "v7": "tasks_v7"}
TASKS = []  # filled by load_set()


def load_set(name):
    global TASKS
    TASKS = importlib.import_module(SETS[name]).TASKS
    return TASKS


# Prepended to every test file. _banned() fails the test if solution.py imports a listed
# module, references a listed name (eval, exec...), or uses a listed attribute (.decode...).
PRELUDE = '''import ast as _ast

def _banned(mods=(), names=(), attrs=()):
    _t = _ast.parse(open("solution.py").read())
    for _n in _ast.walk(_t):
        if isinstance(_n, _ast.Import):
            _m = [a.name.split(".")[0] for a in _n.names]
        elif isinstance(_n, _ast.ImportFrom):
            _m = [(_n.module or "").split(".")[0]]
        else:
            _m = []
        for _x in _m:
            assert _x not in mods, "banned import " + _x
        if isinstance(_n, _ast.Name):
            assert _n.id not in names, "banned name " + _n.id
        if isinstance(_n, _ast.Attribute):
            assert _n.attr not in attrs, "banned attribute " + _n.attr

'''

API = "http://127.0.0.1:8081"
# Sampling: Qwen3 thinking-mode recommendation (temperature 0.6, top_p 0.95, top_k 20).
SAMPLING = {"temperature": 0.6, "top_p": 0.95, "top_k": 20}
REASONING_BUDGET = 8192   # llama.cpp forces end-of-thinking here
MAX_TOKENS = 12288        # reasoning + answer; fits a 16k slot (ctx 65536, 4 slots)
SUFFIX = ("\n\nAnswer with one complete Python 3 module in a single ```python code block. "
          "Standard library only. No example usage, no tests, no input().")
BWRAP = ["bwrap", "--ro-bind", "/usr", "/usr", "--symlink", "usr/lib", "/lib", "--symlink", "usr/lib64", "/lib64",
         "--symlink", "usr/bin", "/bin", "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp",
         "--unshare-all", "--die-with-parent", "--new-session", "--clearenv", "--setenv", "PATH", "/usr/bin"]


def gtt_used():
    with open(sorted(glob.glob("/sys/class/drm/card*/device/mem_info_gtt_used"))[0]) as f:
        return int(f.read())


class GttPeak(threading.Thread):
    """Max of mem_info_gtt_used, sampled every `period` s until stop()."""
    def __init__(self, period=1.0):
        super().__init__(daemon=True)
        self.period, self.peak, self._stop_ev = period, gtt_used(), threading.Event()

    def run(self):
        while not self._stop_ev.wait(self.period):
            self.peak = max(self.peak, gtt_used())

    def stop(self):
        self._stop_ev.set(); self.join()
        self.peak = max(self.peak, gtt_used())
        return self.peak


# Static tripwire over the solution source (README "Grader hardening"). Not isolation: the solution and
# the oracle share one process. Names are flagged only where symtable resolves them to the builtin.
DENY_MODULES = frozenset("""os posix io _io builtins inspect gc traceback linecache ctypes importlib runpy pickle marshal
    code codeop pdb bdb trace tracemalloc subprocess shutil pathlib socket signal __main__""".split())
DENY_NAMES = frozenset("""eval exec compile open getattr setattr delattr vars globals locals dir __import__ breakpoint
    input help exit quit""".split())
DENY_ATTRS = frozenset("""_getframe _current_frames currentframe f_back f_globals f_locals f_code f_builtins f_trace
    gi_frame gi_code cr_frame cr_code ag_frame ag_code tb_frame tb_next co_consts co_code co_names co_filename
    co_varnames __code__ __globals__ __closure__ __builtins__ __subclasses__ __bases__ __mro__ __dict__ __loader__
    __spec__ __getattribute__ __reduce__ __reduce_ex__ settrace setprofile gettrace getprofile get_objects
    get_referrers get_referents stdin __stdin__ modules""".split())
DENY_SUBSTR = tuple(sorted(a for a in DENY_ATTRS if "_" in a and len(a) >= 6)) + ("__import__",)


def _loads_denied(node):
    return any(isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and (n.id in DENY_NAMES or n.id == "__builtins__")
               for n in ast.walk(node))


def _builtin_refs(src):
    """Denied builtin names the source references without binding them itself (module or enclosing scope)."""
    top = symtable.symtable(src, "solution", "exec")
    mod_bound = {s.get_name() for s in top.get_symbols()
                 if s.is_assigned() or s.is_imported() or s.is_namespace() or s.is_parameter()}
    hits = set()

    def walk(t):
        for s in t.get_symbols():
            n = s.get_name()
            if n in DENY_NAMES and s.is_referenced():
                if t.get_type() == "module":
                    bound = n in mod_bound
                elif s.is_global():
                    bound = n in mod_bound or (s.is_declared_global() and s.is_assigned())
                else:
                    bound = True   # local, parameter, free or cell: the solution's own binding
                if not bound:
                    hits.add(n)
        for c in t.get_children():
            walk(c)
    walk(top)
    return hits


def deny_check(code):
    """None if the source passes the tripwire, else a short reason. A syntax error passes: the sandbox reports it."""
    try:
        tree = ast.parse(code)
        refs = _builtin_refs(code)
    except (SyntaxError, ValueError, RecursionError):
        return None
    for n in ast.walk(tree):
        line = getattr(n, "lineno", "?")
        if isinstance(n, ast.Import):
            for a in n.names:
                if a.name.split(".")[0] in DENY_MODULES:
                    return f"forbidden import {a.name} (line {line})"
        elif isinstance(n, ast.ImportFrom):
            if (n.module or "").split(".")[0] in DENY_MODULES:
                return f"forbidden import from {n.module} (line {line})"
            for a in n.names:
                if a.name in DENY_ATTRS or a.name in DENY_NAMES:
                    return f"forbidden import of {a.name} (line {line})"
        elif isinstance(n, ast.Attribute) and n.attr in DENY_ATTRS:
            return f"forbidden attribute .{n.attr} (line {line})"
        elif isinstance(n, ast.Name):
            if n.id == "__builtins__":
                return f"forbidden name __builtins__ (line {line})"
            if n.id in refs and isinstance(n.ctx, ast.Load):
                return f"forbidden builtin {n.id} (line {line})"
        elif isinstance(n, ast.Constant) and isinstance(n.value, str):
            if n.value in DENY_ATTRS or any(t in n.value for t in DENY_SUBSTR):
                return f"forbidden string {n.value[:40]!r} (line {line})"
        elif isinstance(n, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
            targets = n.targets if isinstance(n, ast.Assign) else [n.target]
            names = {t.id for tg in targets for t in ast.walk(tg) if isinstance(t, ast.Name)}
            if names & DENY_NAMES and n.value is not None and _loads_denied(n.value):
                return f"forbidden rebinding of a builtin name (line {line})"
    return None


# Runs inside the sandbox via `python3 -E -s -c`. The solution is imported before the oracle exists in the
# process; the oracle arrives on stdin only after the ready line. Pass = exit 0 and the parent's nonce on stdout.
READY = b"@@loopgrade-ready@@\n"
HARNESS = r"""
import sys
def _main():
    import os, traceback
    rd, wr, ex = os.read, os.write, sys.exit
    def fail(e):
        sys.stdout.flush()
        traceback.print_exception(type(e), e, e.__traceback__.tb_next if e.__traceback__ else None)
        return 1
    try:
        import solution
        ns = {"__name__": "__main__"}
        exec("from solution import *", ns)
    except BaseException as e:
        return fail(e)
    wr(1, b"@@loopgrade-ready@@\n")
    buf = b""
    while True:
        c = rd(0, 1 << 16)
        if not c:
            break
        buf += c
    nonce, _, src = buf.partition(b"\n")
    if not nonce or not src:
        print("grader: no oracle received (the solution consumed stdin or exited early)", file=sys.stderr)
        return 1
    src = src.decode()
    import linecache
    linecache.cache["<oracle>"] = (len(src), None, src.splitlines(True), "<oracle>")
    code = compile(src, "<oracle>", "exec")
    del buf, src
    try:
        exec(code, ns)
    except BaseException as e:
        return fail(e)
    sys.stdout.write(nonce.decode()); sys.stdout.flush()
    return 0
ex = sys.exit
ex(_main())
"""


AS_CAP = 1 << 30
REF_AS_CAP = 512 << 20  # every reference must pass under this; headroom measured 2026-10-08: all 150 refs pass at 256 MiB


def _limits():
    resource.setrlimit(resource.RLIMIT_AS, (AS_CAP, AS_CAP))


def _sandbox(code, tests, timeout):
    """(rc, stdout, stderr, nonce) or (None, ...) on timeout; the oracle is sent only after the ready line."""
    d = tempfile.mkdtemp(prefix="loopgrade-")
    try:
        with open(os.path.join(d, "solution.py"), "w") as f:
            f.write(code)
        nonce = secrets.token_hex(16)
        payload = (nonce + "\n" + PRELUDE + tests + "\n").encode()
        cmd = BWRAP + ["--bind", d, "/w", "--chdir", "/w", "python3", "-E", "-s", "-c", HARNESS]
        p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, preexec_fn=_limits)
        out, err, sent = b"", b"", False
        deadline = time.monotonic() + timeout
        sel = selectors.DefaultSelector()
        sel.register(p.stdout, selectors.EVENT_READ, "out")
        sel.register(p.stderr, selectors.EVENT_READ, "err")
        timed_out = False
        while sel.get_map():
            left = deadline - time.monotonic()
            if left <= 0:
                timed_out = True
                break
            for key, _ in sel.select(left):
                chunk = os.read(key.fileobj.fileno(), 1 << 16)
                if not chunk:
                    sel.unregister(key.fileobj)
                elif key.data == "out":
                    out += chunk
                else:
                    err += chunk
            if not sent and READY in out:
                sent = True
                try:
                    p.stdin.write(payload); p.stdin.close()
                except BrokenPipeError:
                    pass
        if timed_out:
            p.kill()
        try:
            p.wait(max(0.1, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            p.kill(); p.wait(); timed_out = True
        try:
            p.stdin.close()
        except OSError:
            pass
        return (None if timed_out else p.returncode), out.replace(READY, b"").decode(errors="replace"), err.decode(errors="replace"), nonce
    finally:
        shutil.rmtree(d, ignore_errors=True)


EXC_LINE = re.compile(r"([A-Za-z_][\w.]*(?:Error|Exception|Exit|Interrupt|Iteration))\b")   # memring.exc_type's line test
ERR_TAIL = 600


def _tail(s):
    """The last ERR_TAIL chars, unless the last line EXC_LINE matches at column 0 starts before them: then the
    ERR_TAIL chars from that line's start, so the exception's type name is in the returned text."""
    start, pos = None, 0
    for line in s.splitlines(keepends=True):
        if EXC_LINE.match(line):
            start = pos
        pos += len(line)
    if start is None or start >= len(s) - ERR_TAIL:
        return s[-ERR_TAIL:]
    return s[start:start + ERR_TAIL]


def grade(code, tests, timeout=60, static=True):
    if static:
        why = deny_check(code)
        if why:
            return False, "grader: " + why
    rc, out, err, nonce = _sandbox(code, tests, timeout)
    if rc is None:
        return False, "timeout"
    if rc == 0 and nonce in out:
        return True, ""
    if rc == 0:
        err = err or "grader: the program exited 0 without finishing the oracle"
    return False, _tail(err or out)


def extract(content):
    blocks = re.findall(r"```(?:python|py)?[ \t]*\n(.*?)```", content or "", re.S)
    return blocks[-1] if blocks else None


def served_model(requested=None, api=None):
    """The one model the server serves (GET /v1/models; llama-server reports its --alias). A --model that differs
    is refused, so a results summary can only name the model that was actually loaded (2026-10-15: the old
    fixed default qwen3.6-35b-a3b would have mislabelled a run on another model)."""
    api = api or API
    with urllib.request.urlopen(f"{api}/v1/models", timeout=10) as r:
        ids = [m["id"] for m in json.load(r)["data"]]
    if len(ids) != 1:
        raise SystemExit(f"expected exactly one served model at {api}, got {ids}")
    if requested and requested != ids[0]:
        raise SystemExit(f"--model {requested} but {api} serves {ids[0]}")
    return ids[0]


def server_info(api=None):
    """llama-server build and model file (GET /props), recorded in every summary: results from llama.cpp 836d57176
    and v0.7.0 (rebuilt 2026-10-15) must stay distinguishable. None for a field the server does not report."""
    with urllib.request.urlopen(f"{api or API}/props", timeout=10) as r:
        p = json.load(r)
    return {k: p.get(k) for k in ("build_info", "model_path", "model_alias")}


def ask(model, prompt, seed, suffix=SUFFIX):
    body = {"model": model, "messages": [{"role": "user", "content": prompt + suffix}],
            "max_tokens": MAX_TOKENS, "reasoning_budget_tokens": REASONING_BUDGET,
            "reasoning_budget_message": "Reasoning budget reached. Write the code block now.",
            "seed": seed, **SAMPLING}
    req = urllib.request.Request(f"{API}/v1/chat/completions", json.dumps(body).encode(),
                                 {"Content-Type": "application/json"})
    t = time.time()
    with urllib.request.urlopen(req, timeout=3600) as r:
        resp = json.load(r)
    ch = resp["choices"][0]
    return {"content": ch["message"].get("content") or "",
            "reasoning_chars": len(ch["message"].get("reasoning_content") or ""),
            "finish": ch.get("finish_reason"), "usage": resp.get("usage", {}),
            "gen_s": round(time.time() - t, 1)}


SENTINEL = "ORACLE-SENTINEL-7f3a91c2"

# Attack probes: reference + a payload that would pass if the grader let it through. Each must fail with a
# "grader: forbidden" reason (static tripwire). Name -> payload run at import.
STATIC_PROBES = {
    "open() of the oracle path": 'print(open("test_solution.py").read())',
    "os.listdir of cwd": 'import os\nprint(os.listdir("."))',
    "sys._getframe": 'import sys\nf = sys._getframe(1)',
    "inspect frame walk": 'import inspect\nf = inspect.stack()',
    "frame walk via __import__": 'f = __import__("sys")._getframe(1)',
    "getattr string lookup": 'import sys\nf = getattr(sys, "_getframe")',
    "vars lookup": 'import sys\nm = vars(sys)',
    "globals lookup": 'g = globals()["__builtins__"]',
    "__builtins__ name": 'b = __builtins__',
    "format-string attribute walk": 'x = "{0.f_back}".format(None)',
    "attrgetter string": 'import operator\nget = operator.attrgetter("f_back")',
    "from sys import modules": 'from sys import modules',
    "sys.modules": 'import sys\nm = sys.modules',
    "sys.stdin": 'import sys\nd = sys.stdin',
    "input()": 'd = input()',
    "builtin rebinding vars = vars": 'vars = vars',
    "builtin rebinding via a function default": 'import sys\ndef _f(getattr=getattr): pass',
    "sys.exit(0) at import": 'import sys\nsys.exit(0)',
    "eval": 'x = eval("1")',
    "__subclasses__": 'x = object.__subclasses__()',
}
# Raw probes: static check off, 5 s timeout. The sandbox itself must not leak the oracle or fail open.
DUMP = r"""
import os, sys
seen = []
for base in ("/w", "/tmp"):
    for root, _, files in os.walk(base):
        for fn in files:
            p = os.path.join(root, fn)
            seen.append(p)
            try: seen.append(open(p, errors="replace").read())
            except OSError: pass
for p in ("/proc/self/cmdline", "/proc/self/environ"):
    seen.append(open(p, errors="replace").read())
try:
    open("test_solution.py")
    nofile = "FOUND"
except FileNotFoundError:
    nofile = "NOFILE"
needle = "".join(["ORACLE-SENT", "INEL-", "%s"])   # joined at run time: a literal would be folded into the pyc
leak = "LEAK" if any(needle in x for x in seen) else "CLEAN"
print(leak, nofile, sorted(f for f in os.listdir(".") if f != "__pycache__"), file=sys.stderr)
raise SystemExit(1)
""" % SENTINEL.split("-")[-1]
RAW_PROBES = {
    "stdin read at import gets nothing": "import sys\nsys.stdin.read()",
    "os._exit(0) at import": "import os\nos._exit(0)",
    "exit 0 after printing the ready line": 'import sys\nprint("@@loopgrade-ready@@")\nsys.stdout.flush()\nsys.exit(0)',
}


def probe_selftest(t):
    ok = True

    def check(name, cond, extra=""):
        nonlocal ok
        ok &= bool(cond)
        print(f"{'ok' if cond else 'FAIL':4} probe: {name}" + (f"  [{extra}]" if extra and not cond else ""))

    ref = t["ref"]
    for name, payload in STATIC_PROBES.items():
        passed, err = grade(payload + "\n" + ref, t["tests"], timeout=10)
        want = not name.startswith("sys.exit")
        check(name + " fails" + (" (forbidden)" if want else ""), not passed and (err.startswith("grader: forbidden") or not want), err[-120:])
    for name, payload in RAW_PROBES.items():
        passed, err = grade(payload + "\n" + ref, t["tests"], timeout=5, static=False)
        check("raw: " + name + " fails", not passed, err[-120:])
    # old leak closed: the sandbox dir has no test file, the oracle text is not in the dir, cmdline or environ
    passed, err = grade(DUMP + "\n" + ref, t["tests"] + "\n# " + SENTINEL, timeout=10, static=False)
    check("raw: no test_solution.py, oracle sentinel unreachable", "CLEAN NOFILE ['solution.py']" in err, err[-200:])
    # no over-blocking: sys.setrecursionlimit, and builtin names the solution binds itself
    for name, payload in {"sys.setrecursionlimit": "import sys\nsys.setrecursionlimit(5000)",
                          "own variables named vars, compile, builtins": "vars = set()\nbuiltins = {}\ndef compile(x):\n    return x\ncompile(1)",
                          "own parameter named getattr": "def _g(getattr):\n    return getattr\n_g(1)"}.items():
        passed, err = grade(payload + "\n" + ref, t["tests"], timeout=10)
        check("control passes: " + name, passed, err[-120:])
    return ok


def selftest():
    global AS_CAP
    ok = True
    for t in TASKS:
        AS_CAP = REF_AS_CAP
        try:
            good, err = grade(t["ref"], t["tests"])
        finally:
            AS_CAP = 1 << 30
        empty, _ = grade("", t["tests"])
        status = "ok" if good and not empty else "FAIL"
        ok &= status == "ok"
        print(f"{status:4} {t['id']:24} ref={'pass' if good else 'FAIL'} empty={'pass(!)' if empty else 'fail'}"
              + ("" if good else f"\n     {err.strip().splitlines()[-1] if err.strip() else err}"))
    long_line = "Traceback (most recent call last):\n  File \"t.py\", line 1\nAssertionError: " + "x" * 900 + "\n"
    after = "Traceback:\nValueError: bad\n" + "y" * 700
    tails = [_tail("short\nNameError: f\n"), _tail(long_line), _tail(after), _tail("z" * 900)]
    tail_ok = (tails[0] == "short\nNameError: f\n" and tails[1].startswith("AssertionError: ") and len(tails[1]) == ERR_TAIL
               and tails[2].startswith("ValueError: bad") and len(tails[2]) == ERR_TAIL and tails[3] == "z" * ERR_TAIL)
    print(f"{'ok' if tail_ok else 'FAIL':4} err tail keeps the last exception line's type name")
    ok &= tail_ok
    ok &= probe_selftest(TASKS[0])
    print(f"{len(TASKS)} tasks, selftest {'OK' if ok else 'FAILED'}")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--set", default="v0", choices=sorted(SETS))
    ap.add_argument("--label")
    ap.add_argument("--model", help="default: the one model the server serves; a different name is refused")
    ap.add_argument("-n", type=int, default=4)
    ap.add_argument("--seed-start", type=int, default=0, help="seeds are seed-start .. seed-start+n-1")
    ap.add_argument("--tasks", help="comma-separated task ids; default all tasks in the set")
    ap.add_argument("--parallel", type=int, default=4, help="concurrent requests; match the server's -np")
    ap.add_argument("--gtt-baseline", type=float, help="idle GTT used in GiB, from preflight before the server started")
    a = ap.parse_args()
    load_set(a.set)
    if a.tasks:
        want = a.tasks.split(",")
        unknown = set(want) - {t["id"] for t in TASKS}
        if unknown:
            ap.error(f"unknown task ids: {sorted(unknown)}")
        TASKS[:] = [t for t in TASKS if t["id"] in want]
    if a.selftest:
        return selftest()
    if not a.label:
        ap.error("--label required")
    a.model = served_model(a.model)
    server = server_info()
    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    out = os.path.join(HERE, "results", f"{a.label}.jsonl")
    seeds = range(a.seed_start, a.seed_start + a.n)
    jobs = [(t, s) for t in TASKS for s in seeds]
    t0 = time.time()
    rows = []
    gtt = GttPeak(); gtt.start()

    def one(job):
        t, seed = job
        r = ask(a.model, t["prompt"], seed)
        code = extract(r["content"])
        passed, err = grade(code, t["tests"]) if code else (False, "no code block")
        return {"task": t["id"], "seed": seed, "passed": passed, "err": "" if passed else err,
                "finish": r["finish"], "completion_tokens": r["usage"].get("completion_tokens"),
                "prompt_tokens": r["usage"].get("prompt_tokens"), "reasoning_chars": r["reasoning_chars"],
                "gen_s": r["gen_s"], "code": code}

    with open(out, "w") as f, cf.ThreadPoolExecutor(a.parallel) as ex:
        for row in ex.map(one, jobs):
            rows.append(row)
            f.write(json.dumps(row) + "\n"); f.flush()
            print(f"{row['task']:24} seed={row['seed']} {'PASS' if row['passed'] else 'fail'} "
                  f"tok={row['completion_tokens']} {row['gen_s']}s", flush=True)
    wall = time.time() - t0
    gtt_peak = gtt.stop() / (1 << 30)

    by_task = {}
    for r in rows:
        by_task.setdefault(r["task"], []).append(r)
    per_seed = [sum(r["passed"] for r in rows if r["seed"] == s) / len(TASKS) for s in seeds]
    norm = lambda c: re.sub(r"\s+", "", c or "")
    summary = {
        "label": a.label, "set": a.set, "model": a.model, "server": server, "tasks": len(TASKS), "n": a.n, "seeds": [seeds[0], seeds[-1]], "sampling": SAMPLING,
        "reasoning_budget": REASONING_BUDGET, "max_tokens": MAX_TOKENS, "parallel": a.parallel,
        "pass_at_1": round(sum(r["passed"] for r in rows) / len(rows), 4),
        "pass_at_1_per_seed": [round(x, 4) for x in per_seed],
        "best_of_n": round(sum(any(r["passed"] for r in v) for v in by_task.values()) / len(TASKS), 4),
        "per_task_passes": {k: sum(r["passed"] for r in v) for k, v in sorted(by_task.items())},
        "distinct_passing_solutions": {k: len({norm(r["code"]) for r in v if r["passed"]}) for k, v in sorted(by_task.items())},
        "no_code_block": sum(r["code"] is None for r in rows),
        "finish_length": sum(r["finish"] == "length" for r in rows),
        "completion_tokens_total": sum(r["completion_tokens"] or 0 for r in rows),
        "wall_s": round(wall, 1),
        "gtt_peak_gib": round(gtt_peak, 2),
    }
    if a.gtt_baseline is not None:
        summary["gtt_baseline_gib"] = a.gtt_baseline
        summary["gtt_model_gib"] = round(gtt_peak - a.gtt_baseline, 2)
    with open(os.path.join(HERE, "results", f"{a.label}.summary.json"), "w") as f:
        json.dump(summary, f, indent=1)
    print(json.dumps({k: v for k, v in summary.items() if k not in ("per_task_passes", "distinct_passing_solutions")}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
