#!/usr/bin/env python3
"""add_duration has fixed-case tests only (no random.seed line), so agent.py cannot give it a
fresh-seed grade. This compares a result file's passing add_duration code against the task's
reference on 3,000 random inputs (seed 777) in run.py's bwrap sandbox, errors included.

  oracle_add_duration.py results/qwen-v1-weak12-agent-k4e4-vk-np4.jsonl
"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import run, tasks_v1  # noqa: E402

CHECK = r'''
import random
random.seed(777)
def comp(v, u): return (str(v) + u) if v else ""
for _ in range(3000):
    dt = "%04d-%02d-%02dT%02d:%02d:%02d" % (random.randint(1, 9998), random.randint(1, 12), random.randint(1, 31),
                                            random.randint(0, 23), random.randint(0, 59), random.randint(0, 59))
    Y, M, W, D, H, Mi, S = [random.choice([0, 0, 1, 2, 11, 13, 31, 59, 400]) for _ in range(7)]
    date = comp(Y, "Y") + comp(M, "M") + comp(W, "W") + comp(D, "D")
    tm = comp(H, "H") + comp(Mi, "M") + comp(S, "S")
    dur = ("-" if random.random() < 0.4 else "") + "P" + date + ("T" + tm if tm else "")
    if dur.endswith("P"):
        dur += "0D"
    try: exp = _ref_add_duration(dt, dur)
    except (ValueError, OverflowError): exp = "ERR"
    try: got = add_duration(dt, dur)
    except (ValueError, OverflowError): got = "ERR"
    assert got == exp, (dt, dur, got, exp)
'''


def main():
    task = next(t for t in tasks_v1.TASKS if t["id"] == "v1_24_add_duration")
    tests = task["ref"].replace("def add_duration(", "def _ref_add_duration(") + "\n" + CHECK
    ok, _ = run.grade(task["ref"], tests)
    print(f"reference vs itself: {'pass' if ok else 'FAIL'}")
    rc = 0 if ok else 1
    for line in open(sys.argv[1]):
        r = json.loads(line)
        if r["task"] == "v1_24_add_duration" and r["passed"]:
            ok, err = run.grade(r["code"], tests)
            print(f"episode {r.get('episode')} turn {r.get('turn')} seed {r['seed']}: "
                  f"{'agrees on 3000 inputs' if ok else 'DISAGREES: ' + err.strip().splitlines()[-1]}")
            rc |= 0 if ok else 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
