#!/usr/bin/env python3
"""Mechanical checks for a new task set, before it is committed (the v6 checks, as a script; v7 is the first set to use it).

  check_tasks.py --set v7              a set registered in run.SETS
  check_tasks.py --file PART.py        a writer's part file (same task() layout, defines TASKS)

Per task: id matches v<S>_<NN>_<name>; exactly one `random.seed(N)` line with N = 1000 x S + NN; the reference passes
the visible seed, the fresh seed 104729 and seeds 1-5 under the 512 MiB reference address-space cap; the empty
solution fails; the reference grades in <= 0.8 s at the visible seed; prompt 1,000-3,200 chars; reference <= 150
lines; the static tripwire passes the reference; no id and no entry-point name (a top-level def or class of the
reference that the tests mention) reused from another registered set or inside the file. Not checkable here, and
the writer's job: the oracle is built differently from the reference, and the prompt alone determines the answer.
Exit 0 when every task passes, 1 otherwise.
"""
import argparse, ast, importlib.util, os, re, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import run  # noqa: E402
import agent  # noqa: E402

ID_RE = re.compile(r"^v(\d+)_(\d\d)_[a-z][a-z0-9_]*$")
PROMPT_CHARS = (1000, 3200)
REF_LINES = 150
REF_SECONDS = 0.8


def entry_names(t):
    """Top-level def/class names of the reference that the tests mention."""
    tree = ast.parse(t["ref"])
    names = {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
    return {n for n in names if re.search(r"\b" + re.escape(n) + r"\b", t["tests"])}


def other_sets(exclude):
    ids, names = {}, {}
    for s, mod in run.SETS.items():
        if s == exclude:
            continue
        for t in run.load_set(s):
            ids[t["id"]] = s
            for n in entry_names(t):
                names.setdefault(n, s)
    return ids, names


def check(tasks, exclude):
    ids, names = other_sets(exclude)
    seen_ids, seen_names, bad = set(), {}, 0
    for t in tasks:
        errs = []
        m = ID_RE.match(t["id"])
        if not m:
            errs.append("id does not match v<S>_<NN>_<name>")
        seeds = agent.SEED_RE.findall(t["tests"])
        if len(seeds) != 1:
            errs.append(f"{len(seeds)} random.seed lines (need exactly 1)")
        elif m and seeds[0] != f"random.seed({1000 * int(m.group(1)) + int(m.group(2))})":
            errs.append(f"{seeds[0]} but the id needs random.seed({1000 * int(m.group(1)) + int(m.group(2))})")
        if len(seeds) == 1:
            run.AS_CAP = run.REF_AS_CAP
            try:
                t0 = time.monotonic()
                ok, err = run.grade(t["ref"], t["tests"])
                dt = time.monotonic() - t0
                if not ok:
                    errs.append("ref fails the visible seed: " + err.strip()[-200:])
                elif dt > REF_SECONDS:
                    errs.append(f"ref grades in {dt:.2f} s (limit {REF_SECONDS})")
                for s in (agent.FRESH_SEED, 1, 2, 3, 4, 5):
                    ok, err = run.grade(t["ref"], agent.SEED_RE.sub(f"random.seed({s})", t["tests"]))
                    if not ok:
                        errs.append(f"ref fails seed {s}: " + err.strip()[-200:])
            finally:
                run.AS_CAP = 1 << 30
        if run.grade("", t["tests"])[0]:
            errs.append("empty solution passes")
        n = len(t["prompt"])
        if not PROMPT_CHARS[0] <= n <= PROMPT_CHARS[1]:
            errs.append(f"prompt {n} chars (need {PROMPT_CHARS[0]}-{PROMPT_CHARS[1]})")
        lines = len(t["ref"].splitlines())
        if lines > REF_LINES:
            errs.append(f"ref {lines} lines (limit {REF_LINES})")
        why = run.deny_check(t["ref"])
        if why:
            errs.append("ref trips the static tripwire: " + why)
        if t["id"] in ids or t["id"] in seen_ids:
            errs.append(f"id reused ({ids.get(t['id'], 'this file')})")
        seen_ids.add(t["id"])
        try:
            en = entry_names(t)
        except SyntaxError as e:
            errs.append(f"ref does not parse: {e}")
            en = set()
        if not en:
            errs.append("no top-level def/class of the ref is mentioned in the tests")
        for nm in sorted(en):
            if nm in names:
                errs.append(f"entry-point name {nm} reused from {names[nm]}")
            elif nm in seen_names:
                errs.append(f"entry-point name {nm} reused from {seen_names[nm]} in this file")
            seen_names.setdefault(nm, t["id"])
        bad += bool(errs)
        print(f"{'ok' if not errs else 'FAIL':4} {t['id']:30} prompt={n} ref_lines={lines} entry={sorted(en)}")
        for e in errs:
            print("     " + e)
    print(f"{len(tasks)} tasks, {bad} failing")
    return 0 if bad == 0 and tasks else 1


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--set", choices=sorted(run.SETS))
    g.add_argument("--file", help="a part file with the task() layout that defines TASKS")
    a = ap.parse_args()
    if a.set:
        tasks, exclude = list(run.load_set(a.set)), a.set
    else:
        spec = importlib.util.spec_from_file_location("part", os.path.abspath(a.file))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        tasks, exclude = list(mod.TASKS), None
    return check(tasks, exclude)


if __name__ == "__main__":
    sys.exit(main())
