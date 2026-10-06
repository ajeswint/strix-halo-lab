#!/usr/bin/env python3
"""loop-v0 runner: N samples per task from the :8081 server, graded only by unit tests.

  run.py --selftest [--set v1]      refs must pass, empty solutions must fail (tests have teeth)
  run.py --label qwen-vk-np4 -n 4   generate + grade; writes results/<label>.jsonl and .summary.json
  --tasks id,id --seed-start 4      subset of the set, seeds 4..4+n-1 (extends an earlier run)

Grading runs each candidate in bwrap: no network, read-only /usr, only a scratch dir
writable, 4 GiB address-space cap, 60 s wall timeout. pass@1 = mean pass rate over all
samples (unbiased for k=1); best-of-N = share of tasks where any sample passes, i.e. the
tests pick the candidate (oracle selection, the loop's intended use of tests).

GTT: a thread samples mem_info_gtt_used every 1 s while candidates are in flight and stores
the maximum as gtt_peak_gib. The idle baseline is not measured here (the server is already
loaded when run.py starts); pass preflight's pre-load gtt_used with --gtt-baseline to get
gtt_baseline_gib and gtt_model_gib = peak - baseline in the summary.
"""
import argparse, concurrent.futures as cf, glob, json, os, re, resource, shutil, subprocess, sys, tempfile, threading, time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import importlib  # noqa: E402

SETS = {"v0": "tasks", "v1": "tasks_v1", "v2": "tasks_v2"}
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


def _limits():
    resource.setrlimit(resource.RLIMIT_AS, (4 << 30, 4 << 30))


def grade(code, tests, timeout=60):
    d = tempfile.mkdtemp(prefix="loopgrade-")
    try:
        with open(os.path.join(d, "solution.py"), "w") as f:
            f.write(code)
        with open(os.path.join(d, "test_solution.py"), "w") as f:
            f.write(PRELUDE + "from solution import *\n" + tests + "\n")
        cmd = BWRAP + ["--bind", d, "/w", "--chdir", "/w", "python3", "-E", "-s", "test_solution.py"]
        try:
            p = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, text=True,
                               timeout=timeout, preexec_fn=_limits)
        except subprocess.TimeoutExpired:
            return False, "timeout"
        return p.returncode == 0, (p.stderr or p.stdout)[-600:]
    finally:
        shutil.rmtree(d, ignore_errors=True)


def extract(content):
    blocks = re.findall(r"```(?:python|py)?[ \t]*\n(.*?)```", content or "", re.S)
    return blocks[-1] if blocks else None


def ask(model, prompt, seed):
    body = {"model": model, "messages": [{"role": "user", "content": prompt + SUFFIX}],
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


def selftest():
    ok = True
    for t in TASKS:
        good, err = grade(t["ref"], t["tests"])
        empty, _ = grade("", t["tests"])
        status = "ok" if good and not empty else "FAIL"
        ok &= status == "ok"
        print(f"{status:4} {t['id']:24} ref={'pass' if good else 'FAIL'} empty={'pass(!)' if empty else 'fail'}"
              + ("" if good else f"\n     {err.strip().splitlines()[-1] if err.strip() else err}"))
    print(f"{len(TASKS)} tasks, selftest {'OK' if ok else 'FAILED'}")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--set", default="v0", choices=sorted(SETS))
    ap.add_argument("--label")
    ap.add_argument("--model", default="qwen3.6-35b-a3b")
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
        "label": a.label, "set": a.set, "model": a.model, "tasks": len(TASKS), "n": a.n, "seeds": [seeds[0], seeds[-1]], "sampling": SAMPLING,
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
