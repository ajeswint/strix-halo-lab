"""Gate between the Qwen loop and the optional DeepSeek fix stage (llm-serve skill, "Loop + DeepSeek fix
stage"; KEPT 2026-10-15 on v6, README "v6 pipeline"). Same rules as select_v6.py, which stays frozen as the
record of that run; here the output names carry --tag and --min-u defaults to 1. No model, no grading.

check LABEL          results/LABEL.summary.json against results/LABEL.regrade.txt (agent.py --regrade output;
                     lines starting "llmctl:" are skipped). Solved per task must equal regrade fresh > 0.
select LABEL --tag T check, then pick fix inputs by rule: unsolved tasks whose last coded row failed the
                     visible tests (agent.stored_failure refuses any other). Writes
                     results/fix-T-stored.jsonl (those tasks' rows) and results/fix-T-tasks.txt (comma list).

Exit 0 ok; 2 invalid (regrade != summary, missing or unreadable input); 3 nothing to fix (U < --min-u,
nothing written). Any non-zero exit means: do not invite DeepSeek.
"""
import argparse
import json
import os
import sys


def load(results, label):
    summ = json.load(open(os.path.join(results, label + ".summary.json")))
    rg = "".join(l for l in open(os.path.join(results, label + ".regrade.txt")) if not l.startswith("llmctl:"))
    return summ, json.loads(rg)


def check(results, label):
    try:
        summ, rg = load(results, label)
    except (OSError, ValueError) as e:
        print(f"INVALID {label}: {e}")
        return None
    solved = {t["task"] for t in summ["per_task"] if t["solved"]}
    fresh = {t for t, d in rg.items() if d["fresh"] > 0}
    tasks = {t["task"] for t in summ["per_task"]}
    if solved != fresh or not set(rg) <= tasks:
        print(f"INVALID {label}: summary solved {sorted(solved)} != regrade fresh {sorted(fresh)}")
        return None
    print(f"regrade ok {label}: {len(solved)}/{len(tasks)} solved")
    return summ


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["check", "select"])
    ap.add_argument("label")
    ap.add_argument("--tag", help="output name part, fix-TAG-*; required for select")
    ap.add_argument("--results", default="bench/loop/results")
    ap.add_argument("--min-u", type=int, default=1)
    a = ap.parse_args()
    if a.mode == "select" and not a.tag:
        ap.error("select needs --tag")
    summ = check(a.results, a.label)
    if summ is None:
        return 2
    if a.mode == "check":
        return 0
    rows = [json.loads(l) for l in open(os.path.join(a.results, a.label + ".jsonl"))]
    last = {}                                # last coded row per task: what agent.stored_failure starts from
    for r in rows:
        if r["code"] is not None:
            last[r["task"]] = r
    unsolved = [t["task"] for t in summ["per_task"] if not t["solved"]]
    # usable = stored_failure will accept it: a coded row exists and the last one failed the visible tests
    # (a visible pass that failed the fresh seed is unsolved but refused by fix mode)
    usable = [t for t in unsolved if t in last and not last[t]["passed"]]
    print("unsolved", len(unsolved), "usable", len(usable),
          "no coded turn", sorted(t for t in unsolved if t not in last),
          "last coded turn passed visible", sorted(t for t in unsolved if t in last and last[t]["passed"]))
    print("usable ids", ",".join(usable))
    if len(usable) < a.min_u:
        print(f"NOTHING TO FIX: U = {len(usable)} < {a.min_u}; do not invite DeepSeek")
        return 3
    with open(os.path.join(a.results, f"fix-{a.tag}-stored.jsonl"), "w") as f:
        for r in rows:
            if r["task"] in usable:
                f.write(json.dumps(r) + "\n")
    with open(os.path.join(a.results, f"fix-{a.tag}-tasks.txt"), "w") as f:
        f.write(",".join(usable))
    return 0


if __name__ == "__main__":
    sys.exit(main())
