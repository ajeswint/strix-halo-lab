#!/usr/bin/env python3
"""Agentic loop (Roadmap 2): submit code -> tests run -> failure fed back -> retry.

  agent.py --selftest [--set v1]                       loop logic against a scripted fake model; no server
  agent.py --label L --set v1 --tasks id,id -k 4 -e 4  run against the :8081 server
  agent.py --regrade results/X.jsonl --set v1          fresh-seed regrade of a run.py result file
  agent.py --label L --set v3 --tasks id,id --fix-from results/X.jsonl -k 4 -e 2 --model M [--api URL]
                                                       fix mode: start every episode from a stored failure

One model, one action: write solution.py. The critic is the test file, run in run.py's
bwrap sandbox; the model never writes to it. Each turn is a fresh single message
(task + current code + latest failure), no chat history, so a turn fits one 16k slot.

Brakes per episode: at most K turns; stop when the tests pass, when an error message
repeats, or when the model resubmits code it already tried. Per task: at most E episodes
run one after another, stopping at the first episode whose code passes the tests, or
when the task's completion tokens reach --task-budget.

Plan mode (symbiosis probe): --make-plans asks the model once per task for an implementation plan, no code
(PLAN_SUFFIX, seed PLAN_SEED, one retry at PLAN_SEED + 1 if the reply is empty), and writes results/<label>.plans.jsonl.
--plan-from <plans.jsonl> runs the loop above with that plan appended to the task prompt (so every turn carries it)
and the plan's completion tokens counted against the task budget. A task whose plan is empty runs with no plan
appended and is flagged plan_empty.

Fix mode (--fix-from): a second model, or the same one, repairs a failure an earlier run left. Each
episode starts at turn 0 from the stored failure (the last code block and its test error from that
run's JSONL) instead of the bare task; the stored code counts as already tried for the repeat-code
stop, the stored error as the previous error for the repeat-error stop. Everything else is the loop
above: grading, fresh seed, stops, budget. Sampling seeds are FIX_SEED_BASE + 10 x episode + turn.

Ring (--ring ROOT --ring-slot N, measure-only): each finished task's coded turns are sealed from the grade this
process just ran and admitted to memring's buffer (family from memring.FAMILIES, never from the model); one
flush at the end of the run, summary["ring"]. Nothing is retrieved into prompts, so the model sees what it sees without it.

Fresh seed: the model sees failures from the tests' own random.seed(N). The episode's
final passing code is re-graded with that line replaced by random.seed(FRESH_SEED), a seed
no turn saw, so hard-coding a fed-back case does not count. solved = fresh pass. Tasks
whose tests have no single random.seed line (fixed cases only) are flagged no_fresh and
scored on the visible tests. --regrade applies the same fresh grade to run.py output so
best-of-N and the loop are scored the same way.
"""
import argparse, concurrent.futures as cf, hashlib, json, os, re, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import run  # noqa: E402  grade, extract, ask, load_set, GttPeak, sampling constants
import memring  # noqa: E402

FRESH_SEED = 104729
FIX_SEED_BASE = 2000   # fix-mode sampling seeds; disjoint from run.py's 0-15 and the loop's 1000-1033
PLAN_SEED = 3000       # plan-mode seed; disjoint from the above
PLAN_SUFFIX = ("\n\nDo not write code. Write an implementation plan for a colleague who will write the module: "
               "the algorithm and data structures, the order in which the rules apply, the edge cases the tests are "
               "likely to probe, and the complexity. Numbered steps, at most 600 words, no code blocks.")
PLAN_HEADER = "\n\nA colleague wrote this plan. Use it where it is right; the tests decide.\n\n<plan>\n{}\n</plan>"
SEED_RE = re.compile(r"^random\.seed\(\d+\)$", re.M)


def fresh_tests(tests):
    """tests with the oracle seed swapped for FRESH_SEED, or None if there is no single seed line."""
    if len(SEED_RE.findall(tests)) != 1:
        return None
    return SEED_RE.sub(f"random.seed({FRESH_SEED})", tests)


def fresh_grade(code, tests):
    """(passed, err, no_fresh). Without a seed line this is the visible grade."""
    ft = fresh_tests(tests)
    passed, err = run.grade(code, ft if ft is not None else tests)
    return passed, err, ft is None


def turn_prompt(task_prompt, code, err):
    if code is None and err is None:
        return task_prompt
    if code is None:
        return (task_prompt + "\n\nYour previous answer contained no code block; it ran out of tokens "
                "before writing code. Keep the reasoning shorter and write the complete module.")
    return (task_prompt + "\n\nYour previous solution:\n```python\n" + code + "\n```\n\n"
            "It failed the tests with:\n```\n" + err.strip() + "\n```\n\n"
            "Find the cause and write a corrected complete module.")


def stored_failure(path, task_id):
    """(code, err) of the last turn of task_id in a loop jsonl that has a code block; it must have failed."""
    last = None
    for line in open(path):
        r = json.loads(line)
        if r["task"] == task_id and r["code"] is not None:
            last = r
    if last is None:
        raise SystemExit(f"{path}: no turn with code for {task_id}")
    if last["passed"]:
        raise SystemExit(f"{path}: the last coded turn of {task_id} passed; it is not a stored failure")
    return last["code"], last["err"]


def episode(task, ep, k, ask, start=None):
    """Up to k turns. start = (code, err) of a stored failure (fix mode). Returns (turn rows, stop reason)."""
    code, err = start if start else (None, None)
    seen_code, rows = set(), []
    if code is not None:
        seen_code.add(hashlib.sha256(code.encode()).hexdigest())
    seed0 = FIX_SEED_BASE if start else 1000   # loop seeds are disjoint from run.py's 0-15
    for turn in range(k):
        seed = seed0 + ep * 10 + turn
        r = ask(turn_prompt(task["prompt"], code, err), seed)
        new = run.extract(r["content"])
        passed, new_err = run.grade(new, task["tests"]) if new else (False, "no code block")
        rows.append({"task": task["id"], "episode": ep, "turn": turn, "seed": seed, "passed": passed,
                     "err": "" if passed else new_err, "finish": r["finish"],
                     "completion_tokens": r["usage"].get("completion_tokens"),
                     "prompt_tokens": r["usage"].get("prompt_tokens"), "reasoning_chars": r["reasoning_chars"],
                     "gen_s": r["gen_s"], "code": new})
        if passed:
            return rows, "pass"
        h = hashlib.sha256((new or "").encode()).hexdigest()
        if new is not None and h in seen_code:
            return rows, "repeat_code"
        if new is not None:
            seen_code.add(h)
        if new is not None and err is not None and new_err.strip() == err.strip():
            return rows, "repeat_error"
        code, err = new, new_err   # no code block -> next turn gets the "ran out of tokens" prompt
    return rows, "max_turns"


def with_plan(task, plan):
    """The task with the plan appended to its prompt; unchanged when the plan is empty."""
    return dict(task, prompt=task["prompt"] + PLAN_HEADER.format(plan.strip())) if plan.strip() else task


def make_plans(tasks, plan_ask, path, parallel):
    """One plan per task; returns the rows written to path."""
    def one(t):
        r = plan_ask(t["prompt"], PLAN_SEED)
        tries = [r]
        if not r["content"].strip():
            r = plan_ask(t["prompt"], PLAN_SEED + 1)
            tries.append(r)
        return {"task": t["id"], "plan": r["content"], "tries": len(tries),
                "completion_tokens": sum(x["usage"].get("completion_tokens") or 0 for x in tries),
                "reasoning_chars": sum(x["reasoning_chars"] for x in tries),
                "finish": [x["finish"] for x in tries], "gen_s": round(sum(x["gen_s"] for x in tries), 1)}
    with open(path, "w") as f, cf.ThreadPoolExecutor(parallel) as ex:
        out = []
        for row in ex.map(one, tasks):
            f.write(json.dumps(row) + "\n")
            f.flush()
            out.append(row)
            print(f"{row['task']:24} plan chars={len(row['plan'])} tok={row['completion_tokens']} tries={row['tries']}", flush=True)
    return out


def load_plans(path):
    return {r["task"]: r for r in map(json.loads, open(path))}


def solve_task(task, k, e, budget, ask, start=None, tokens0=0):
    rows, eps, tokens = [], [], tokens0
    for ep in range(e):
        if tokens >= budget:
            eps.append({"episode": ep, "stop": "task_budget"})
            break
        er, stop = episode(task, ep, k, ask, start)
        rows += er
        tokens += sum(r["completion_tokens"] or 0 for r in er)
        rec = {"episode": ep, "turns": len(er), "stop": stop, "tokens": sum(r["completion_tokens"] or 0 for r in er)}
        if stop == "pass":
            fp, ferr, nf = fresh_grade(er[-1]["code"], task["tests"])
            rec.update(fresh_pass=fp, fresh_err="" if fp else ferr, no_fresh=nf)
            eps.append(rec)
            break   # in use the loop stops at the first green test run, fresh result or not
        eps.append(rec)
    solved = bool(eps) and eps[-1].get("fresh_pass", False)
    return rows, {"task": task["id"], "solved": solved, "visible_pass": any(x["stop"] == "pass" for x in eps),
                  "episodes": eps, "turns": len(rows), "completion_tokens": tokens,
                  "no_fresh": fresh_tests(task["tests"]) is None}


def server_ask(model):
    def ask(prompt, seed):
        return run.ask(model, prompt, seed)
    return ask


def regrade(path):
    """Fresh-seed grade of every passing sample in a run.py jsonl; prints per-task counts."""
    by_id = {t["id"]: t for t in run.TASKS}
    out = {}
    for line in open(path):
        r = json.loads(line)
        t = by_id[r["task"]]
        d = out.setdefault(r["task"], {"samples": 0, "visible": 0, "fresh": 0, "no_fresh": fresh_tests(t["tests"]) is None})
        d["samples"] += 1
        if r["passed"]:
            d["visible"] += 1
            d["fresh"] += fresh_grade(r["code"], t["tests"])[0]
    print(json.dumps(out, indent=1))
    return 0


def selftest():
    """Loop mechanics without a server: a scripted fake model replays fixed answers."""
    ok = True
    def check(name, cond):
        nonlocal ok
        ok &= bool(cond)
        print(f"{'ok' if cond else 'FAIL':4} {name}")

    # 1. fresh seed: every reference passes it; tasks without a seed line are flagged
    flagged = []
    for t in run.TASKS:
        ft = fresh_tests(t["tests"])
        if ft is None:
            flagged.append(t["id"])
            continue
        good, err = run.grade(t["ref"], ft)
        check(f"fresh seed: ref passes {t['id']}", good)
        if not good:
            print("     ", err.strip().splitlines()[-1] if err.strip() else err)
    print(f"     no_fresh (fixed cases only): {flagged}")

    t = run.TASKS[0]
    bad = "def " + t["ref"].split("def ", 1)[1].split("(", 1)[0] + "(*a, **k):\n    return None\n"

    def fake(answers):
        it = iter(answers)
        def ask(prompt, seed):
            c = next(it)
            fake.prompts.append(prompt)
            return {"content": "" if c is None else f"```python\n{c}\n```", "reasoning_chars": 0,
                    "finish": "length" if c is None else "stop",
                    "usage": {"completion_tokens": 100, "prompt_tokens": 10}, "gen_s": 0.0}
        fake.prompts = []
        return ask

    # 2. fail then fix: turn 2 sees turn 1's code and error, passes, fresh grade runs
    rows, s = solve_task(t, 4, 4, 10**9, fake([bad, t["ref"]]))
    check("fail -> feedback -> pass in 2 turns", s["solved"] and s["turns"] == 2)
    check("turn 2 prompt carries code and error", bad.strip() in fake.prompts[1] and "failed the tests" in fake.prompts[1])
    # 3. same code twice ends the episode; next episode starts from the bare task
    rows, s = solve_task(t, 4, 2, 10**9, fake([bad, bad, t["ref"]]))
    check("repeat code stops episode 0, episode 1 solves", s["episodes"][0]["stop"] in ("repeat_code", "repeat_error")
          and s["solved"] and fake.prompts[2] == t["prompt"])
    # 4. no code block: told it ran out of tokens; K caps the episode
    rows, s = solve_task(t, 4, 1, 10**9, fake([None, None, None, None]))
    check("no-code turns hit max_turns at K=4", s["episodes"][0]["stop"] == "max_turns" and s["turns"] == 4
          and "no code block" in fake.prompts[1])
    # 5. task budget stops new episodes
    rows, s = solve_task(t, 1, 4, 150, fake([bad, bad, bad, bad]))
    check("task budget stops after 2 episodes", s["turns"] == 2 and s["episodes"][-1]["stop"] == "task_budget")
    # 6. fix mode: every episode starts from the stored failure, not the bare task; the stored code counts as tried
    stored = (run.extract(f"```python\n{bad}\n```"), "AssertionError: stored failure marker")   # code as stored: extracted
    rows, s = solve_task(t, 4, 2, 10**9, fake([t["ref"]]), stored)
    check("fix mode: turn 0 prompt carries stored code and error",
          stored[0].strip() in fake.prompts[0] and "stored failure marker" in fake.prompts[0]
          and "failed the tests" in fake.prompts[0] and s["solved"] and s["turns"] == 1)
    rows, s = solve_task(t, 4, 2, 10**9, fake([bad, t["ref"]]), stored)
    check("fix mode: resubmitting the stored code ends episode 0; episode 1 restarts from the stored failure",
          s["episodes"][0]["stop"] == "repeat_code" and s["solved"] and fake.prompts[1] == fake.prompts[0]
          and fake.prompts[1] != t["prompt"])
    check("fix mode: seeds 2000 + 10 x episode + turn", [r["seed"] for r in rows] == [2000, 2010])
    rows, s = solve_task(t, 4, 1, 10**9, fake([t["ref"]]))
    check("loop mode keeps seeds 1000 + 10 x episode + turn", [r["seed"] for r in rows] == [1000])
    # stored_failure reads the last coded turn of a task from a jsonl and refuses a passing one
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        fp = os.path.join(d, "x.jsonl")
        with open(fp, "w") as f:
            for r in ({"task": "a", "passed": False, "err": "e1", "code": "c1"},
                      {"task": "a", "passed": False, "err": "no code block", "code": None},
                      {"task": "b", "passed": False, "err": "eb", "code": "cb"},
                      {"task": "a", "passed": False, "err": "e2", "code": "c2"},
                      {"task": "c", "passed": True, "err": "", "code": "cc"}):
                f.write(json.dumps(r) + "\n")
        check("stored_failure takes the last turn with code", stored_failure(fp, "a") == ("c2", "e2"))
        try:
            stored_failure(fp, "c"); passed_refused = False
        except SystemExit:
            passed_refused = True
        check("stored_failure refuses a task whose last coded turn passed", passed_refused)
    # 7. plan mode: the plan rides in every turn's prompt, its tokens count against the budget, empty plan = no plan
    pt = with_plan(t, "1. MARKER-PLAN step")
    rows, s = solve_task(pt, 4, 1, 10**9, fake([bad, t["ref"]]), None, 500)
    check("plan mode: plan in turn 0 and in the feedback turn",
          all("MARKER-PLAN" in p and "<plan>" in p for p in fake.prompts) and s["solved"])
    check("plan mode: plan tokens count toward the task total", s["completion_tokens"] == 500 + 200)
    rows, s = solve_task(t, 1, 4, 150, fake([bad, bad]), None, 100)
    check("plan mode: plan tokens can exhaust the budget", s["turns"] == 1 and s["episodes"][-1]["stop"] == "task_budget")
    check("plan mode: an empty plan leaves the task unchanged", with_plan(t, "  \n") is t)
    with tempfile.TemporaryDirectory() as d:
        fp = os.path.join(d, "p.plans.jsonl")
        replies = iter(["", "the plan"])
        def plan_fake(prompt, seed):
            plan_fake.seeds.append(seed)
            return {"content": next(replies), "reasoning_chars": 5, "finish": "stop",
                    "usage": {"completion_tokens": 40}, "gen_s": 0.0}
        plan_fake.seeds = []
        out = make_plans([t], plan_fake, fp, 1)
        check("make_plans retries an empty plan once at PLAN_SEED + 1, sums tokens",
              plan_fake.seeds == [PLAN_SEED, PLAN_SEED + 1] and out[0]["plan"] == "the plan"
              and out[0]["completion_tokens"] == 80 and load_plans(fp)[t["id"]]["tries"] == 2)
    # 8. ring (measure-only): coded turns are admitted with the loop's own verdicts, no-code turns skipped
    rows, s = solve_task(t, 4, 1, 10**9, fake([None, bad, t["ref"]]))
    with tempfile.TemporaryDirectory() as d:
        ring = memring.Ring(d)
        got = ring.ingest(1, lambda tid: "fam", rows, [(r["passed"], r["err"]) for r in rows])
        kinds = [r[0] for r in ring.buf.execute("SELECT kind FROM buffer ORDER BY id")]
        check("ring: 2 coded turns admitted as fail then pass, the no-code turn skipped",
              got == {"admitted": 2, "skipped_no_code": 1, "refused": {}} and kinds == ["fail", "pass"])
    print(f"selftest {'OK' if ok else 'FAILED'}")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--regrade", metavar="JSONL")
    ap.add_argument("--set", default="v1", choices=sorted(run.SETS))
    ap.add_argument("--tasks", help="comma-separated task ids; default all")
    ap.add_argument("--label")
    ap.add_argument("--model", default="qwen3.6-35b-a3b")
    ap.add_argument("-k", type=int, default=4, help="max turns per episode")
    ap.add_argument("-e", type=int, default=4, help="max episodes per task")
    ap.add_argument("--task-budget", type=int, default=16 * run.MAX_TOKENS,
                    help="completion tokens per task before no new episode starts (default: best-of-16 hard cap)")
    ap.add_argument("--parallel", type=int, default=4, help="tasks in flight; match the server's -np")
    ap.add_argument("--gtt-baseline", type=float)
    ap.add_argument("--api", default=run.API, help="server base URL (default :8081; llama-deepseek is on :8080)")
    ap.add_argument("--fix-from", metavar="JSONL", help="fix mode: start each episode from the stored failure of each task in this loop jsonl")
    ap.add_argument("--make-plans", action="store_true", help="plan mode: write results/<label>.plans.jsonl, no loop")
    ap.add_argument("--plan-from", metavar="PLANS_JSONL", help="plan mode: append each task's plan to its prompt; plan tokens count against the budget")
    ap.add_argument("--ring", metavar="ROOT", help="measure-only memring: admit every coded turn, flush once at the end")
    ap.add_argument("--ring-slot", type=int, help="slot of the model writing (with --ring)")
    a = ap.parse_args()
    if a.ring and (a.ring_slot is None or a.set not in memring.FAMILIES):
        ap.error("--ring needs --ring-slot and a set with a family map in memring.FAMILIES")
    run.load_set(a.set)
    run.API = a.api
    if a.fix_from and not a.tasks:
        ap.error("--fix-from needs --tasks")
    if a.plan_from and a.fix_from:
        ap.error("--plan-from and --fix-from are separate modes")
    if a.tasks:
        want = a.tasks.split(",")
        unknown = set(want) - {t["id"] for t in run.TASKS}
        if unknown:
            ap.error(f"unknown task ids: {sorted(unknown)}")
        run.TASKS[:] = [t for t in run.TASKS if t["id"] in want]
    if a.selftest:
        return selftest()
    if a.regrade:
        return regrade(a.regrade)
    if not a.label:
        ap.error("--label required")

    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    base = os.path.join(HERE, "results", a.label)
    ask = server_ask(a.model)
    if a.make_plans:
        t0 = time.time()
        rows = make_plans(run.TASKS, lambda p, seed: run.ask(a.model, p, seed, PLAN_SUFFIX), base + ".plans.jsonl", a.parallel)
        print(f"plans: {len(rows)} tasks, {sum(not r['plan'].strip() for r in rows)} empty, "
              f"{sum(r['completion_tokens'] for r in rows)} tokens, {time.time() - t0:.0f} s")
        return 0
    plans = load_plans(a.plan_from) if a.plan_from else {}
    if a.plan_from:
        missing = {t["id"] for t in run.TASKS} - set(plans)
        if missing:
            ap.error(f"{a.plan_from}: no plan for {sorted(missing)}")
    starts = {t["id"]: stored_failure(a.fix_from, t["id"]) for t in run.TASKS} if a.fix_from else {}
    tests_by_id = {t["id"]: t["tests"] for t in run.TASKS}
    ring = memring.Ring(a.ring, regrade=lambda items: [run.grade(c, tests_by_id[tid]) for tid, c in items]) if a.ring else None
    ring_in = {"admitted": 0, "skipped_no_code": 0, "refused": {}}
    t0 = time.time()
    gtt = run.GttPeak(); gtt.start()
    tasks_out = []
    with open(base + ".jsonl", "w") as f, cf.ThreadPoolExecutor(a.parallel) as ex:
        def go(t):
            p = plans.get(t["id"])
            rows, s = solve_task(with_plan(t, p["plan"]) if p else t, a.k, a.e, a.task_budget, ask, starts.get(t["id"]),
                                 p["completion_tokens"] if p else 0)
            if p:
                s.update(plan_tokens=p["completion_tokens"], plan_empty=not p["plan"].strip())
            return rows, s
        for rows, s in ex.map(go, run.TASKS):
            for r in rows:
                f.write(json.dumps(r) + "\n")
            f.flush()
            if ring:   # passed/err are this process's run.grade results for exactly this code
                got = ring.ingest(a.ring_slot, memring.FAMILIES[a.set].__getitem__, rows,
                                  [(r["passed"], r["err"]) for r in rows])
                ring_in["admitted"] += got["admitted"]
                ring_in["skipped_no_code"] += got["skipped_no_code"]
                for k, n in got["refused"].items():
                    ring_in["refused"][k] = ring_in["refused"].get(k, 0) + n
            tasks_out.append(s)
            print(f"{s['task']:24} {'SOLVED' if s['solved'] else 'fail':6} turns={s['turns']} "
                  f"tok={s['completion_tokens']} stops={[x['stop'] for x in s['episodes']]}", flush=True)
    gtt_peak = gtt.stop() / (1 << 30)
    summary = {
        "label": a.label, "set": a.set, "model": a.model, "tasks": len(run.TASKS), "k": a.k, "e": a.e,
        "task_budget": a.task_budget, "fresh_seed": FRESH_SEED, "sampling": run.SAMPLING,
        "api": a.api, "fix_from": os.path.basename(a.fix_from) if a.fix_from else None,
        "plan_from": os.path.basename(a.plan_from) if a.plan_from else None,
        "reasoning_budget": run.REASONING_BUDGET, "max_tokens": run.MAX_TOKENS, "parallel": a.parallel,
        "solved": sum(s["solved"] for s in tasks_out), "visible_pass": sum(s["visible_pass"] for s in tasks_out),
        "completion_tokens_total": sum(s["completion_tokens"] for s in tasks_out),
        "turns_total": sum(s["turns"] for s in tasks_out),
        "wall_s": round(time.time() - t0, 1), "gtt_peak_gib": round(gtt_peak, 2),
        "per_task": sorted(tasks_out, key=lambda s: s["task"]),
    }
    if ring:
        summary["ring"] = {"root": a.ring, "slot": a.ring_slot, "ingest": ring_in, "flush": ring.flush()}
    if a.gtt_baseline is not None:
        summary["gtt_baseline_gib"] = a.gtt_baseline
        summary["gtt_model_gib"] = round(gtt_peak - a.gtt_baseline, 2)
    with open(base + ".summary.json", "w") as f:
        json.dump(summary, f, indent=1)
    print(json.dumps({k: v for k, v in summary.items() if k != "per_task"}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
