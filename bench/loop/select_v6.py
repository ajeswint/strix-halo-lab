"""v6 pipeline gate between stages (README "v6 pipeline, refreshed pre-run"). No model, no grading.

check LABEL   results/LABEL.summary.json against results/LABEL.regrade.txt (agent.py --regrade output;
              lines starting "llmctl:" are skipped). Solved per task must equal regrade fresh > 0.
select LABEL  check, then pick stage 2 inputs by rule: unsolved tasks with a coded row. Writes
              results/fix-v6-stored.jsonl (those tasks' rows) and results/fix-v6-tasks.txt (comma list).

Exit 0 ok; 2 invalid (regrade != summary, missing or unreadable input); 3 thin (U < --min-u, nothing written).
The chain stops on any non-zero exit, so a thin or invalid stage 1 never reaches the control or DeepSeek.
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
    ap.add_argument("--results", default="bench/loop/results")
    ap.add_argument("--min-u", type=int, default=6)
    a = ap.parse_args()
    summ = check(a.results, a.label)
    if summ is None:
        return 2
    if a.mode == "check":
        return 0
    rows = [json.loads(l) for l in open(os.path.join(a.results, a.label + ".jsonl"))]
    coded = {r["task"] for r in rows if r["code"] is not None}
    unsolved = [t["task"] for t in summ["per_task"] if not t["solved"]]
    usable = [t for t in unsolved if t in coded]
    print("unsolved", len(unsolved), "usable", len(usable), "not usable", sorted(set(unsolved) - set(usable)))
    print("usable ids", ",".join(usable))
    if len(usable) < a.min_u:
        print(f"THIN: U = {len(usable)} < {a.min_u}; stage 2 and the control do not run")
        return 3
    with open(os.path.join(a.results, "fix-v6-stored.jsonl"), "w") as f:
        for r in rows:
            if r["task"] in usable:
                f.write(json.dumps(r) + "\n")
    with open(os.path.join(a.results, "fix-v6-tasks.txt"), "w") as f:
        f.write(",".join(usable))
    return 0


if __name__ == "__main__":
    sys.exit(main())
