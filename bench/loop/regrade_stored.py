#!/usr/bin/env python3
"""Regrade every stored results/*.jsonl with the current run.grade and compare with what was stored.

  regrade_stored.py [results/x.jsonl ...]     default: all results/*.jsonl

Per file: rows with code are graded against the task's visible tests; rows that pass are also graded on
the fresh seed (agent.fresh_grade). Compared with the stored `passed` per row, and for loop files with the
summary's `solved` and per-task fresh result. Exit 0 only if nothing flipped. Flips are listed in full.
"""
import concurrent.futures as cf, glob, hashlib, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import agent, run  # noqa: E402


def load(path):
    rows = [json.loads(l) for l in open(path)]
    sm = json.load(open(path[:-len(".jsonl")] + ".summary.json"))
    return rows, sm


def regrade(path, workers):
    rows, sm = load(path)
    run.load_set(sm.get("set") or "v0")
    tests = {t["id"]: t for t in run.TASKS}
    todo = [i for i, r in enumerate(rows) if r["code"] is not None]

    def one(i):
        r = rows[i]
        t = tests[r["task"]]
        vis, err = run.grade(r["code"], t["tests"])
        fresh = agent.fresh_grade(r["code"], t["tests"])[0] if vis else None
        return i, vis, err, fresh

    with cf.ThreadPoolExecutor(workers) as ex:
        res = {i: (vis, err, fresh) for i, vis, err, fresh in ex.map(one, todo)}
    flips = []
    new_pass = 0
    for i, r in enumerate(rows):
        vis = res[i][0] if i in res else False   # no code block: failed before and now
        new_pass += vis
        if vis != r["passed"]:
            flips.append({"row": i, "task": r["task"], "seed": r["seed"], "turn": r.get("turn"), "old": r["passed"],
                          "new": vis, "reason": res[i][1][-300:] if i in res else "", "code_sha": hashlib.sha256(r["code"].encode()).hexdigest()[:12],
                          "code": r["code"]})
    out = {"file": os.path.basename(path), "set": sm.get("set") or "v0", "rows": len(rows), "with_code": len(todo),
           "old_pass": sum(r["passed"] for r in rows), "new_pass": new_pass, "flips": flips}
    if "episode" in rows[0]:   # loop file: solved = the passing turn also passes the fresh seed
        new_solved, fresh_flips = 0, []
        old_fresh = {p["task"]: [e.get("fresh_pass") for e in p["episodes"] if "fresh_pass" in e]
                     for p in sm["per_task"]}
        for tid in tests:
            idx = [i for i, r in enumerate(rows) if r["task"] == tid and r["passed"]]
            fp = bool(idx) and bool(res.get(idx[-1], (0, 0, None))[2])
            new_solved += fp
            was = bool(old_fresh.get(tid)) and old_fresh[tid][-1]
            if fp != was:
                fresh_flips.append({"task": tid, "old": was, "new": fp})
        out.update(old_solved=sm["solved"], new_solved=new_solved, fresh_flips=fresh_flips)
    else:   # run.py file: pass@1 and best-of-n from the new row grades
        by = {}
        for i, r in enumerate(rows):
            by.setdefault(r["task"], []).append(res[i][0] if i in res else False)
        out.update(old_p1=sm["pass_at_1"], new_p1=round(new_pass / len(rows), 4), old_bon=sm["best_of_n"],
                   new_bon=round(sum(any(v) for v in by.values()) / len(sm_tasks(sm)), 4))
    return out


def sm_tasks(sm):
    return range(sm["tasks"])


def main():
    paths = sys.argv[1:] or sorted(glob.glob(os.path.join(HERE, "results", "*.jsonl")))
    bad = 0
    print(f"{'file':52} {'set':3} {'rows':>4} {'code':>4} {'old':>4} {'new':>4} {'flips':>5}  solved old/new | p@1 old/new, bo-n old/new")
    for p in paths:
        o = regrade(p, 8)
        bad += len(o["flips"]) + len(o.get("fresh_flips", []))
        if "old_solved" in o:
            tail = f"{o['old_solved']}/{o['new_solved']}"
            bad += o["old_solved"] != o["new_solved"]
        else:
            tail = f"{o['old_p1']}/{o['new_p1']}, {o['old_bon']}/{o['new_bon']}"
            bad += (o["old_p1"], o["old_bon"]) != (o["new_p1"], o["new_bon"])
        print(f"{o['file']:52} {o['set']:3} {o['rows']:4} {o['with_code']:4} {o['old_pass']:4} {o['new_pass']:4} {len(o['flips']):5}  {tail}", flush=True)
        for f in o["flips"]:
            print("  FLIP", json.dumps({k: v for k, v in f.items() if k != "code"}))
            print("  ---- solution ----\n" + f["code"] + "\n  ------------------")
        for f in o.get("fresh_flips", []):
            print("  FRESH FLIP", json.dumps(f))
    print("regrade", "OK: no row or count changed" if not bad else f"FLIPS: {bad}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
