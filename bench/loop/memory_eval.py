#!/usr/bin/env python3
"""Held-out evaluation of the verified coding-memory loop v1: agent.py --memory off against --memory on, matched.
Design and the pre-registered read rule: docs/memory-loop-v1.md. Nothing here loads a model; `run` only talks to the
server llmctl already started.

  memory_eval.py check  --set v9 --model M --lessons L.json --label P   validate, write results/P.prereg.json, print the
                                                                         two arm commands (no server needed)
  memory_eval.py run    --label P                                        re-validate against the prereg, then run both
                                                                         arms (off first, then on), one after the other
  memory_eval.py report --label P                                        apply the read rule to both arm summaries

`run` is a long client: start it only inside an active llmctl session, under its cap, e.g.
  scripts/llmctl.py run -- python3 bench/loop/memory_eval.py run --label P

Matched budget: both arms get the same --set, --tasks, --model, -k, -e, --task-budget, --parallel and --api, and
agent.py's sampling seeds are fixed by (episode, turn) (1000 + 10 * episode + turn), so they match too. The arms
differ only by `--memory on --lessons L --memory-k K`. The prereg pins the lesson export, the task file and the
grader by sha256 / GRADER_VER, so a changed input is refused instead of measured.
"""
import argparse, hashlib, json, math, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import run  # noqa: E402
import memring  # noqa: E402

RESULTS = os.path.join(HERE, "results")   # agent.py writes its arms here too

READ_RULE_VERSION = "memloop-v1-rule-1"
NET_MIN_ABS, NET_MIN_FRAC = 3, 0.10   # KEEP needs net >= max(3, ceil(0.10 * N))
READ_RULE = (f"Paired per task on the held-out set (solved = agent.py summary per_task.solved, the fresh-seed grade). "
             f"gains = on solved and off not; losses = off solved and on not; net = gains - losses. "
             f"INVALID if the arms are not matched (set, tasks, model, k, e, task_budget, parallel, server build, "
             f"model file), the lesson export or task file sha256 differs from the prereg, an arm is incomplete, "
             f"or memory-on injected lessons on 0 rows. "
             f"KEEP if net >= max({NET_MIN_ABS}, ceil({NET_MIN_FRAC} * N)). DROP if net <= 0. "
             f"Otherwise INCONCLUSIVE (no keep; only a fresh held-out set can settle it, never a rerun of this one). "
             f"The exact two-sided sign test on gains vs losses is reported, not used for the verdict.")
MATCH_KEYS = ("set", "tasks", "model", "k", "e", "task_budget")


def sha256_file(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def task_file(set_name):
    import importlib
    return importlib.import_module(run.SETS.get(set_name, f"tasks_{set_name}")).__file__


def paths(label):
    base = os.path.join(RESULTS, label)
    return {"prereg": base + ".prereg.json", "off": f"{label}-off", "on": f"{label}-on", "report": base + ".report.json"}


def validate(set_name, model, lessons, task_ids=None):
    """Refusal reason or None, plus the held-out tasks and the lesson bundle. No server, no model."""
    ok, why = memring.require_held_out_eval_set(set_name)
    if not ok:
        return why, None, None
    try:
        tasks = run.load_set(set_name)
    except (ImportError, ValueError) as e:
        return f"cannot load held-out set {set_name!r}: {e}", None, None
    if task_ids:
        unknown = set(task_ids) - {t["id"] for t in tasks}
        if unknown:
            return f"unknown task ids: {sorted(unknown)}", None, None
        tasks = [t for t in tasks if t["id"] in task_ids]
    ok, why = memring.require_held_out_eval_set(set_name, tasks)
    if not ok:
        return why, None, None
    try:
        bundle = memring.load_lesson_export(lessons, held_out_tasks=run.load_set(set_name))
    except (OSError, ValueError) as e:
        return f"lesson export refused: {e}", None, None
    if not any(l.get("model") == model for l in bundle["lessons"]):
        return f"lesson export has no lesson for model {model!r}; memory on would inject nothing", None, None
    return None, tasks, bundle


def arm_cmd(pr, arm):
    c = [sys.executable, os.path.join(HERE, "agent.py"), "--set", pr["set"], "--tasks", ",".join(pr["tasks"]),
         "--model", pr["model"], "-k", str(pr["k"]), "-e", str(pr["e"]), "--task-budget", str(pr["task_budget"]),
         "--parallel", str(pr["parallel"]), "--api", pr["api"], "--label", paths(pr["label"])[arm]]
    if arm == "on":
        c += ["--memory", "on", "--lessons", repo_path(pr["lessons"]), "--memory-k", str(pr["memory_k"])]
    return c


def build_prereg(a):
    why, tasks, bundle = validate(a.set, a.model, a.lessons, a.tasks.split(",") if a.tasks else None)
    if why:
        raise SystemExit(why)
    pr = {"label": a.label, "set": a.set, "split": memring.set_split(a.set), "tasks": [t["id"] for t in tasks],
          "task_file_sha256": sha256_file(task_file(a.set)), "model": a.model, "k": a.k, "e": a.e,
          "task_budget": a.task_budget, "parallel": a.parallel, "api": a.api,
          "lessons": os.path.relpath(os.path.abspath(a.lessons), os.path.dirname(os.path.dirname(HERE))),
          "lessons_sha256": sha256_file(a.lessons), "lessons_for_model": sum(l["model"] == a.model for l in bundle["lessons"]),
          "memory_k": a.memory_k, "grader": memring.GRADER_VER, "arm_order": ["off", "on"],
          "read_rule_version": READ_RULE_VERSION, "read_rule": READ_RULE}
    pr["commands"] = {arm: arm_cmd(pr, arm) for arm in pr["arm_order"]}
    return pr


def repo_path(rel):
    return os.path.join(os.path.dirname(os.path.dirname(HERE)), rel)


def load_prereg(label):
    p = paths(label)["prereg"]
    if not os.path.exists(p):
        raise SystemExit(f"{p}: no prereg; run `memory_eval.py check` and commit it first")
    with open(p) as f:
        return json.load(f)


def recheck(pr):
    """Re-validate a stored prereg against the files on disk now. Refusal reason or None."""
    why, tasks, _ = validate(pr["set"], pr["model"], repo_path(pr["lessons"]), pr["tasks"])
    if why:
        return why
    for k, want, got in (("task file", pr["task_file_sha256"], sha256_file(task_file(pr["set"]))),
                         ("lesson export", pr["lessons_sha256"], sha256_file(repo_path(pr["lessons"]))),
                         ("grader", pr["grader"], memring.GRADER_VER), ("read rule", pr["read_rule"], READ_RULE)):
        if want != got:
            return f"{k} changed since the prereg ({str(want)[:12]} -> {str(got)[:12]})"
    return None


def sign_test_p(gains, losses):
    n, x = gains + losses, min(gains, losses)
    if n == 0:
        return 1.0
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(x + 1)) / 2 ** n)


def read(pr, off, on):
    """Apply the pre-registered rule to two agent.py summaries. Returns the verdict record."""
    bad = []
    for name, s in (("off", off), ("on", on)):
        if s is None:
            bad.append(f"{name} summary missing")
    if bad:
        return {"verdict": "INVALID", "why": bad}
    want = {"set": pr["set"], "tasks": len(pr["tasks"]), "model": pr["model"], "k": pr["k"], "e": pr["e"],
            "task_budget": pr["task_budget"]}
    for name, s in (("off", off), ("on", on)):
        for k in MATCH_KEYS:
            if s.get(k) != want[k]:
                bad.append(f"{name}: {k}={s.get(k)!r}, prereg {want[k]!r}")
        if sorted(t["task"] for t in s.get("per_task", ())) != sorted(pr["tasks"]):
            bad.append(f"{name}: per_task does not cover the prereg tasks")
    if (off.get("server") or {}) != (on.get("server") or {}):
        bad.append("server build / model file differs between arms")
    if "memory" in off:
        bad.append("off arm ran with memory")
    mem = on.get("memory") or {}
    if mem.get("lessons_sha256") != pr["lessons_sha256"] or mem.get("k") != pr["memory_k"]:
        bad.append("on arm lesson export or k differs from the prereg")
    if not mem.get("rows_with_lessons"):
        bad.append("on arm injected lessons on 0 rows")
    if bad:
        return {"verdict": "INVALID", "why": bad}
    so = {t["task"]: bool(t["solved"]) for t in off["per_task"]}
    sn = {t["task"]: bool(t["solved"]) for t in on["per_task"]}
    gains = sorted(t for t in pr["tasks"] if sn[t] and not so[t])
    losses = sorted(t for t in pr["tasks"] if so[t] and not sn[t])
    n, net = len(pr["tasks"]), len(gains) - len(losses)
    line = max(NET_MIN_ABS, math.ceil(NET_MIN_FRAC * n))
    verdict = "KEEP" if net >= line else "DROP" if net <= 0 else "INCONCLUSIVE"
    return {"verdict": verdict, "n": n, "off_solved": sum(so.values()), "on_solved": sum(sn.values()),
            "gains": gains, "losses": losses, "net": net, "keep_line": line,
            "sign_test_p": round(sign_test_p(len(gains), len(losses)), 4),
            "tokens": {"off": off.get("completion_tokens_total"), "on": on.get("completion_tokens_total")},
            "read_rule_version": pr["read_rule_version"]}


def load_summary(label):
    p = os.path.join(RESULTS, label + ".summary.json")
    if not os.path.exists(p):
        return None
    with open(p) as f:
        return json.load(f)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=("check", "run", "report"))
    ap.add_argument("--label", required=True)
    ap.add_argument("--set")
    ap.add_argument("--tasks", help="comma-separated held-out task ids; default all")
    ap.add_argument("--model")
    ap.add_argument("--lessons", help="frozen lesson export (memring.py lessons-distill --lessons-out)")
    ap.add_argument("-k", type=int, default=4)
    ap.add_argument("-e", type=int, default=4)
    ap.add_argument("--task-budget", type=int, default=16 * run.MAX_TOKENS)
    ap.add_argument("--parallel", type=int, default=4)
    ap.add_argument("--api", default=run.API)
    ap.add_argument("--memory-k", type=int, default=memring.LESSON_K)
    a = ap.parse_args(argv)
    P = paths(a.label)
    if a.cmd == "check":
        if not (a.set and a.model and a.lessons):
            ap.error("check needs --set, --model and --lessons")
        if os.path.exists(P["prereg"]):
            raise SystemExit(f"{P['prereg']} exists; a prereg is written once (new label for a new plan)")
        pr = build_prereg(a)
        os.makedirs(os.path.dirname(P["prereg"]), exist_ok=True)
        with open(P["prereg"], "w") as f:
            json.dump(pr, f, indent=1)
        print(f"prereg written: {P['prereg']}")
        for arm in pr["arm_order"]:
            print(f"{arm}: " + " ".join(pr["commands"][arm]))
        return 0
    pr = load_prereg(a.label)
    if a.cmd == "run":
        why = recheck(pr)
        if why:
            raise SystemExit(f"refused: {why}")
        for arm in pr["arm_order"]:
            if os.path.exists(os.path.join(RESULTS, P[arm] + ".jsonl")):
                raise SystemExit(f"results/{P[arm]}.jsonl exists; an arm is never rerun into the same label")
        for arm in pr["arm_order"]:
            rc = subprocess.call(arm_cmd(pr, arm))
            if rc:
                raise SystemExit(f"{arm} arm exited {rc}; no report")
    rec = read(pr, load_summary(P["off"]), load_summary(P["on"]))
    with open(P["report"], "w") as f:
        json.dump(rec, f, indent=1)
    print(json.dumps(rec, indent=1))
    return 0 if rec["verdict"] != "INVALID" else 2


if __name__ == "__main__":
    sys.exit(main())
