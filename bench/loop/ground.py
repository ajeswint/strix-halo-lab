#!/usr/bin/env python3
"""CRAwDAD Grounding runner (docs/crawdad-ground-v1.md): small models grounded in execution feedback.

  ground.py --selftest                          protocol and loop against fake seats; CPU only, no server
  ground.py step --label L --set v10 [--tasks a,b] [--parallel 1] [--api URL]
                                                every reply the served model owes (run inside its llmctl session)
  ground.py status --label L                    each task's state and the seat to invite next; no server
  ground.py report --label L [--regrade]        results/L.ground.summary.json; --regrade re-grades final code

Protocol:
- Arms:
  - P (plain baseline): Turn 0 solo reply per (task, seat) at seed 5000 from debate.solo_prompt(task).
    Stored once and shared as candidate 0 for G and C so paired comparisons share turn-0 sampling noise.
  - G (grounded): From turn 0, self-written edge-case tests (seed 5050, seeing only prompt), static checks
    (compile, deny_check, AST entry points, pyflakes if available), visible tests from prompt examples
    (bench/loop/tasks_v10_visible.py), and test-and-fix revisions up to K=3 turns (seeds 5001-5003).
    Best-of-N selection across static, visible, and model tests (earliest turn wins ties).
  - C (matched control): From turn 0, up to K=3 self-revisions at seeds 5001-5003 with task prompt and
    previous code only (no execution feedback). Final code = last produced.
- Budget: B = 4 * MAX_TOKENS (24576 completion tokens) matched cap per (task, seat) for G and C.
- Hidden grading: fresh grade at FRESH_SEED 104729 once per (task, seat, arm) after the loop is over.
- The in-loop code path never accesses hidden tests or references.
"""
import argparse, ast, builtins, concurrent.futures as cf, hashlib, json, math, os, random, re, sys, tempfile, threading, time
import urllib.error, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import run               # grade, deny_check, extract, _tail, SAMPLING, served_model, server_info, load_set
import debate            # SEATS, ORDER, REASONING_BUDGET, MAX_TOKENS, BUDGET_MESSAGE, SOLO_SUFFIX, solo_prompt, request_body, server_ask, parse_response
import agent             # fresh_grade, FRESH_SEED
import memring           # FAMILIES
import tasks_v10_visible # VISIBLE_TESTS, NO_VISIBLE, CHECKS

SEATS = debate.SEATS     # {"qwen3-32b": "qwen32", "r1-distill-qwen-32b": "r1d32"}
ORDER = debate.ORDER     # ("qwen32", "r1d32")

# Seeds: 5000-5099 disjoint from run.py (0-15), loop (1000+), fix (2000+), plan (3000-3001), debate (4000+, 4100+, 4200+)
SEED_BASE = 5000
TEST_SEED = 5050
K_REVISIONS = 3
TASK_BUDGET = 4 * debate.MAX_TOKENS  # 24576 completion tokens per (task, seat)
T_NOISE = 9                          # Pinned net threshold from Stage V
T_SENSITIVITY = 12                   # Sensitivity line from cross-seed discordance

CHECK_ORDER = ("static", "visible", "model_tests")
SELECTION_KEY = ("static_pass", "visible_pass", "model_pass", "first_wins")

TEST_WRITE_SUFFIX = (
    "\n\nWrite a small suite of 3 to 5 distinct edge-case assertions (unit tests) for this task to verify a candidate solution.\n"
    "Standard library only. Output ONLY executable Python assertions in a single ```python code block.\n"
    "Each line should test a specific case with `assert <func>(...) == <expected>` or `try: <func>(...); assert False except ValueError: pass`.\n"
    "Do not define the solution functions, do not write example usage, no input()."
)

REVISION_SUFFIX = (
    "\n\nAnswer in this order: a short explanation of your correction (at most 150 words); one complete "
    "corrected Python 3 module in a single ```python code block (standard library only, no example usage, "
    "no tests, no input()); then a last line `CONFIDENCE: c`, c from 0.0 to 1.0, how likely your corrected module is correct."
)

CONTROL_SUFFIX = (
    "\n\nCarefully re-check your solution against all rules, constraints, edge cases, and types in the specification. "
    "If you find any flaws or missing requirements, provide a corrected complete module. "
    "If you are confident the module is already completely correct and requires no changes, you may output the identical module."
    + REVISION_SUFFIX
)


def ground_protocol(seed_base=SEED_BASE):
    visible_path = os.path.join(HERE, "tasks_v10_visible.py")
    if os.path.exists(visible_path):
        with open(visible_path, "rb") as f:
            vis_sha = hashlib.sha256(f.read()).hexdigest()
    else:
        vis_sha = ""
    payload = [
        debate.SOLO_SUFFIX,
        TEST_WRITE_SUFFIX,
        REVISION_SUFFIX,
        CONTROL_SUFFIX,
        debate.BUDGET_MESSAGE,
        debate.REASONING_BUDGET,
        debate.MAX_TOKENS,
        TASK_BUDGET,
        seed_base,
        TEST_SEED,
        K_REVISIONS,
        CHECK_ORDER,
        SELECTION_KEY,
        run.SAMPLING,
        agent.FRESH_SEED,
        vis_sha
    ]
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:12]


PROTOCOL = ground_protocol(SEED_BASE)


def extract_entry_points(prompt):
    """Extract required entry-point function names from task prompt header."""
    first_part = prompt.split("Examples:")[0].split("Example:")[0]
    raw = sorted(set(re.findall(r"`([a-zA-Z_]\w*)\(", first_part)))
    return [f for f in raw if f not in dir(builtins)]


def static_checks(code, entry_points):
    """Run cheapest static checks first: compile, deny_check, AST entry points, pyflakes (if available).
    Returns (ok: bool, reason: str, checks_run: list[str]).
    """
    checks_run = ["compile", "deny_check", "entry_points"]
    if code is None or not code.strip():
        return False, "no code block", checks_run
    try:
        compile(code, "solution.py", "exec")
    except SyntaxError as e:
        return False, f"SyntaxError: {e}", checks_run

    why = run.deny_check(code)
    if why:
        return False, f"deny_check: {why}", checks_run

    try:
        tree = ast.parse(code)
        defined = {n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        for n in tree.body:
            if isinstance(n, ast.Assign):
                for t in n.targets:
                    if isinstance(t, ast.Name):
                        defined.add(t.id)
        for ep in entry_points:
            if ep not in defined:
                return False, f"missing required entry point: {ep}", checks_run
    except Exception as e:
        return False, f"ast_check: {e}", checks_run

    try:
        import pyflakes.api as pfa
        import pyflakes.reporter as pfr
        import io
        checks_run.append("pyflakes")
        buf = io.StringIO()
        rep = pfr.Reporter(buf, buf)
        pfa.check(code, "solution.py", rep)
    except ImportError:
        pass

    return True, "", checks_run


def extract_model_tests(content):
    """Extract test assertions from model test-writing reply."""
    code = run.extract(content)
    if not code:
        return None, "no code block in test response"
    # Cap length of test source to 4000 chars
    code = code[:4000]
    try:
        compile(code, "<model_tests>", "exec")
    except SyntaxError as e:
        return None, f"SyntaxError in model tests: {e}"
    return code, ""


def evaluate_candidate(code, entry_points, visible_tests, model_tests, timeout=10):
    """Run static -> visible -> model tests in order. Returns dict of evaluation results."""
    ok_st, err_st, checks_run = static_checks(code, entry_points)
    if not ok_st:
        return {"static_pass": False, "visible_pass": False, "model_pass": False,
                "err": err_st, "checks_run": checks_run}

    if visible_tests and visible_tests.strip():
        ok_vis, err_vis = run.grade(code, visible_tests, timeout=timeout)
        if not ok_vis:
            return {"static_pass": True, "visible_pass": False, "model_pass": False,
                    "err": run._tail(err_vis), "checks_run": checks_run}

    if model_tests and model_tests.strip():
        ok_m, err_m = run.grade(code, model_tests, timeout=timeout)
        if not ok_m:
            return {"static_pass": True, "visible_pass": True, "model_pass": False,
                    "err": run._tail(err_m), "checks_run": checks_run}

    return {"static_pass": True, "visible_pass": True, "model_pass": True,
            "err": "", "checks_run": checks_run}


def candidate_score(c):
    """Best-of-N selection key: ordered static, visible, model tests; ties broken by earliest turn."""
    return (int(bool(c.get("static_pass"))),
            int(bool(c.get("visible_pass"))),
            int(bool(c.get("model_pass"))),
            -c.get("turn", 0))


def select_best_candidate(candidates):
    return max(candidates, key=candidate_score)


def g_revision_prompt(task_prompt, code, err):
    if code is None:
        return (task_prompt + "\n\nYour previous answer contained no code block; it ran out of tokens "
                "before writing code. Keep the reasoning shorter and write the complete module." + REVISION_SUFFIX)
    return (task_prompt + f"\n\nYour previous solution:\n```python\n{code}\n```\n\n"
            f"It failed with:\n```\n{err.strip()}\n```\n\n"
            "Find the cause and write a corrected complete module." + REVISION_SUFFIX)


def c_revision_prompt(task_prompt, code):
    if code is None:
        return (task_prompt + "\n\nYour previous answer contained no code block; it ran out of tokens "
                "before writing code. Keep the reasoning shorter and write the complete module." + REVISION_SUFFIX)
    return (task_prompt + f"\n\nYour previous solution:\n```python\n{code}\n```\n\n" + CONTROL_SUFFIX)


def sign_test_p(gains, losses):
    """Exact one-sided paired sign test p-value under null p_0 = 0.5."""
    n = gains + losses
    if n == 0:
        return 1.0
    return sum(math.comb(n, j) * (0.5 ** n) for j in range(losses + 1))


def paths(root, label):
    b = os.path.join(root, label + ".ground")
    return b + ".meta.json", b + ".jsonl", b + ".summary.json"


def load_meta_and_rows(root, label):
    mp, rp, _ = paths(root, label)
    if not os.path.exists(mp):
        raise SystemExit(f"{mp}: no such run (first step creates it)")
    with open(mp) as f:
        meta = json.load(f)
    if os.path.exists(rp):
        with open(rp) as f:
            rows = [json.loads(line) for line in f]
    else:
        rows = []
    return meta, rows


def save_meta(path, meta):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(meta, f, indent=1)
    os.replace(tmp, path)


def build_index(rows):
    """Index rows by (task, seat).
    idx[(task, seat)] = {
        "turn0": row or None,
        "test_gen": row or None,
        "g_revisions": [rows],
        "c_revisions": [rows],
        "final_g": row or None,
        "final_c": row or None,
        "final_p": row or None,
    }
    """
    idx = {}
    for r in rows:
        key = (r["task"], r["seat"])
        entry = idx.setdefault(key, {
            "turn0": None, "test_gen": None,
            "g_revisions": [], "c_revisions": [],
            "final_g": None, "final_c": None, "final_p": None
        })
        kind = r.get("kind")
        arm = r.get("arm")
        if kind == "turn0":
            entry["turn0"] = r
        elif kind == "test_gen":
            entry["test_gen"] = r
        elif kind == "revision":
            if arm == "G":
                entry["g_revisions"].append(r)
            elif arm == "C":
                entry["c_revisions"].append(r)
        elif kind == "final":
            if arm == "G":
                entry["final_g"] = r
            elif arm == "C":
                entry["final_c"] = r
            elif arm == "P":
                entry["final_p"] = r
    # sort revisions by turn
    for entry in idx.values():
        entry["g_revisions"].sort(key=lambda x: x.get("turn", 0))
        entry["c_revisions"].sort(key=lambda x: x.get("turn", 0))
    return idx


def task_owed_for_seat(idx, task_id, seat):
    """Return list of action descriptions owed for (task_id, seat)."""
    entry = idx.get((task_id, seat), {
        "turn0": None, "test_gen": None, "g_revisions": [], "c_revisions": [],
        "final_g": None, "final_c": None, "final_p": None
    })
    owed = []
    if entry["turn0"] is None:
        owed.append("turn0")
    if entry["final_g"] is None:
        owed.append("arm_g")
    if entry["final_c"] is None:
        owed.append("arm_c")
    return owed


def count_owed(meta, idx, seat):
    return sum(len(task_owed_for_seat(idx, t, seat)) for t in meta["tasks"])


def strip_hidden(task, visible_tests_dict):
    """Enforce: in-loop task dictionary receives ONLY id, prompt, and visible. No tests, no ref."""
    tid = task["id"]
    return {
        "id": tid,
        "prompt": task["prompt"],
        "visible": visible_tests_dict.get(tid, "")
    }


def step(root, label, set_name, task_ids, alias, server, ask, parallel=1, log=print, seed_base=None):
    """Run every action the served seat owes."""
    if alias not in SEATS:
        raise SystemExit(f"served model {alias!r} is not a ground seat ({sorted(SEATS)})")
    seat = SEATS[alias]

    mp, rp, _ = paths(root, label)
    if os.path.exists(mp):
        meta, rows = load_meta_and_rows(root, label)
        for k, want in (("set", set_name), ("tasks", task_ids)):
            if want is not None and meta[k] != want:
                raise SystemExit(f"{mp}: {k} is {meta[k]}, this step asked for {want}")
        if seed_base is not None and seed_base != meta.get("seed_base"):
            raise SystemExit(f"{mp}: seed_base is {meta.get('seed_base')}, this step asked for {seed_base}")
        seed_base = meta.get("seed_base", SEED_BASE)
        if meta["protocol"] != ground_protocol(seed_base):
            raise SystemExit(f"{mp}: protocol {meta['protocol']} != current {ground_protocol(seed_base)}")
        if server and meta.get("build") and meta["build"] != server.get("build_info"):
            raise SystemExit(f"{mp}: build {meta['build']} != server {server.get('build_info')}")
    else:
        if set_name is None:
            raise SystemExit("the first step of a run needs --set")
        seed_base = seed_base or SEED_BASE
        all_tasks = run.load_set(set_name)
        all_ids = [t["id"] for t in all_tasks]
        task_ids = task_ids or all_ids
        unknown = set(task_ids) - set(all_ids)
        if unknown:
            raise SystemExit(f"unknown task ids: {sorted(unknown)}")
        with open(os.path.join(HERE, "tasks_v10_visible.py"), "rb") as f:
            visible_sha = hashlib.sha256(f.read()).hexdigest()
        meta = {
            "label": label, "set": set_name, "tasks": task_ids,
            "protocol": ground_protocol(seed_base),
            "seed_base": seed_base, "test_seed": TEST_SEED,
            "k_revisions": K_REVISIONS, "task_budget": TASK_BUDGET,
            "reasoning_budget": debate.REASONING_BUDGET, "max_tokens": debate.MAX_TOKENS,
            "sampling": run.SAMPLING, "fresh_seed": agent.FRESH_SEED,
            "visible_file_sha256": visible_sha,
            "build": server.get("build_info") if server else None,
            "seats": {}
        }
        rows = []

    if server:
        meta["seats"].setdefault(seat, {"model": alias, "model_path": server.get("model_path"),
                                        "build_info": server.get("build_info")})
    save_meta(mp, meta)

    raw_tasks = {t["id"]: t for t in run.load_set(meta["set"])}
    # In-loop tasks have NO 'tests' and NO 'ref'
    in_loop_tasks = {t["id"]: strip_hidden(t, tasks_v10_visible.VISIBLE_TESTS) for t in raw_tasks.values()}

    idx = build_index(rows)
    lock, dead = threading.Lock(), threading.Event()
    todo_tasks = [t for t in meta["tasks"] if task_owed_for_seat(idx, t, seat)]
    log(f"step {label}: {seat} owes work on {len(todo_tasks)} tasks")

    asked_count = 0

    def write_row(r):
        nonlocal asked_count
        with lock:
            with open(rp, "a") as f:
                f.write(json.dumps(r) + "\n")
            rows.append(r)
            build_index([r])  # update entry
            key = (r["task"], r["seat"])
            entry = idx.setdefault(key, {
                "turn0": None, "test_gen": None, "g_revisions": [], "c_revisions": [],
                "final_g": None, "final_c": None, "final_p": None
            })
            kind = r.get("kind")
            arm = r.get("arm")
            if kind == "turn0":
                entry["turn0"] = r
            elif kind == "test_gen":
                entry["test_gen"] = r
            elif kind == "revision":
                (entry["g_revisions"] if arm == "G" else entry["c_revisions"]).append(r)
            elif kind == "final":
                if arm == "G": entry["final_g"] = r
                elif arm == "C": entry["final_c"] = r
                elif arm == "P": entry["final_p"] = r

    def run_one_task(tid):
        nonlocal asked_count
        if dead.is_set():
            return 0
        task = in_loop_tasks[tid]
        task_prompt = task["prompt"]
        entry_points = extract_entry_points(task_prompt)
        vis_tests = task["visible"]

        task_asked = 0

        # Step 1: Turn 0 (Shared, Arm P)
        entry = idx.get((tid, seat), {})
        turn0 = entry.get("turn0")
        if turn0 is None:
            prompt = debate.solo_prompt(task)
            try:
                resp = ask(prompt, seed_base)
            except BaseException:
                dead.set()
                raise
            code = run.extract(resp.get("content"))
            tokens = (resp.get("usage") or {}).get("completion_tokens") or 0
            turn0 = {
                "kind": "turn0", "task": tid, "seat": seat, "arm": "P",
                "seed": seed_base, "content": resp.get("content", ""),
                "code": code, "completion_tokens": tokens,
                "gen_s": resp.get("gen_s", 0.0)
            }
            write_row(turn0)
            task_asked += 1
            # Record final for P
            final_p = {
                "kind": "final", "task": tid, "seat": seat, "arm": "P",
                "selected_turn": 0, "code": code, "stop_reason": "turn0",
                "total_tokens": tokens
            }
            write_row(final_p)

        c0_code = turn0["code"]
        c0_tokens = turn0["completion_tokens"]

        # Step 2: Arm G (Grounded)
        if entry.get("final_g") is None:
            # 2a. Model test generation
            test_gen = entry.get("test_gen")
            if test_gen is None:
                test_prompt = task_prompt + TEST_WRITE_SUFFIX
                try:
                    resp_test = ask(test_prompt, TEST_SEED)
                except BaseException:
                    dead.set()
                    raise
                m_code, m_err = extract_model_tests(resp_test.get("content", ""))
                test_tok = (resp_test.get("usage") or {}).get("completion_tokens") or 0
                test_gen = {
                    "kind": "test_gen", "task": tid, "seat": seat, "arm": "G",
                    "seed": TEST_SEED, "content": resp_test.get("content", ""),
                    "tests": m_code, "err": m_err,
                    "completion_tokens": test_tok, "gen_s": resp_test.get("gen_s", 0.0)
                }
                write_row(test_gen)
                task_asked += 1

            model_tests = test_gen.get("tests")
            g_tokens = c0_tokens + test_gen.get("completion_tokens", 0)

            # 2b. Evaluate candidate 0
            eval0 = evaluate_candidate(c0_code, entry_points, vis_tests, model_tests)
            cand0 = dict(turn=0, code=c0_code, tokens=c0_tokens, **eval0)
            candidates = [cand0]
            tried_codes = {c0_code} if c0_code is not None else set()
            prev_err = eval0["err"]
            stop_reason = None

            if eval0["static_pass"] and eval0["visible_pass"] and eval0["model_pass"]:
                stop_reason = "all_pass"

            # Check existing revisions in index if resuming
            existing_revs = entry.get("g_revisions", [])
            for rev in existing_revs:
                candidates.append(rev)
                g_tokens += rev.get("completion_tokens", 0)
                if rev.get("code") is not None:
                    tried_codes.add(rev["code"])
                prev_err = rev.get("err", "")
                if rev.get("static_pass") and rev.get("visible_pass") and rev.get("model_pass"):
                    stop_reason = "all_pass"

            cur_turn = len(candidates) - 1
            last_code = candidates[-1]["code"]

            while stop_reason is None and cur_turn < K_REVISIONS:
                cur_turn += 1
                if g_tokens >= TASK_BUDGET:
                    stop_reason = "budget"
                    break

                rev_prompt = g_revision_prompt(task_prompt, last_code, prev_err)
                try:
                    resp_rev = ask(rev_prompt, seed_base + cur_turn)
                except BaseException:
                    dead.set()
                    raise
                code_rev = run.extract(resp_rev.get("content"))
                tok_rev = (resp_rev.get("usage") or {}).get("completion_tokens") or 0
                g_tokens += tok_rev
                task_asked += 1

                # Repeat code check
                if code_rev is not None and code_rev in tried_codes:
                    eval_rev = evaluate_candidate(code_rev, entry_points, vis_tests, model_tests)
                    rev_row = dict(kind="revision", task=tid, seat=seat, arm="G",
                                   turn=cur_turn, seed=seed_base + cur_turn,
                                   content=resp_rev.get("content", ""), code=code_rev,
                                   completion_tokens=tok_rev, gen_s=resp_rev.get("gen_s", 0.0),
                                   **eval_rev)
                    write_row(rev_row)
                    candidates.append(rev_row)
                    stop_reason = "repeat_code"
                    break

                if code_rev is not None:
                    tried_codes.add(code_rev)

                eval_rev = evaluate_candidate(code_rev, entry_points, vis_tests, model_tests)
                rev_row = dict(kind="revision", task=tid, seat=seat, arm="G",
                               turn=cur_turn, seed=seed_base + cur_turn,
                               content=resp_rev.get("content", ""), code=code_rev,
                               completion_tokens=tok_rev, gen_s=resp_rev.get("gen_s", 0.0),
                               **eval_rev)
                write_row(rev_row)
                candidates.append(rev_row)

                if eval_rev["static_pass"] and eval_rev["visible_pass"] and eval_rev["model_pass"]:
                    stop_reason = "all_pass"
                    break
                if eval_rev["err"] == prev_err:
                    stop_reason = "repeat_error"
                    break
                if cur_turn >= K_REVISIONS:
                    stop_reason = "max_turns"
                    break
                prev_err = eval_rev["err"]
                last_code = code_rev

            if stop_reason is None:
                stop_reason = "max_turns"

            best = select_best_candidate(candidates)
            final_g = {
                "kind": "final", "task": tid, "seat": seat, "arm": "G",
                "selected_turn": best["turn"], "code": best["code"],
                "stop_reason": stop_reason, "total_tokens": g_tokens,
                "candidates_produced": len(candidates)
            }
            write_row(final_g)

        # Step 3: Arm C (Matched control, no execution)
        if entry.get("final_c") is None:
            c_tokens = c0_tokens
            c_candidates = [dict(turn=0, code=c0_code, tokens=c0_tokens)]
            tried_c_codes = {c0_code} if c0_code is not None else set()
            stop_reason_c = None

            existing_c_revs = entry.get("c_revisions", [])
            for rev in existing_c_revs:
                c_candidates.append(rev)
                c_tokens += rev.get("completion_tokens", 0)
                if rev.get("code") is not None:
                    tried_c_codes.add(rev["code"])

            cur_c_turn = len(c_candidates) - 1
            last_c_code = c_candidates[-1]["code"]

            while stop_reason_c is None and cur_c_turn < K_REVISIONS:
                cur_c_turn += 1
                if c_tokens >= TASK_BUDGET:
                    stop_reason_c = "budget"
                    break

                c_prompt = c_revision_prompt(task_prompt, last_c_code)
                try:
                    resp_c = ask(c_prompt, seed_base + cur_c_turn)
                except BaseException:
                    dead.set()
                    raise
                code_c = run.extract(resp_c.get("content"))
                tok_c = (resp_c.get("usage") or {}).get("completion_tokens") or 0
                c_tokens += tok_c
                task_asked += 1

                rev_row_c = {
                    "kind": "revision", "task": tid, "seat": seat, "arm": "C",
                    "turn": cur_c_turn, "seed": seed_base + cur_c_turn,
                    "content": resp_c.get("content", ""), "code": code_c,
                    "completion_tokens": tok_c, "gen_s": resp_c.get("gen_s", 0.0)
                }
                write_row(rev_row_c)
                c_candidates.append(rev_row_c)

                if code_c is None or code_c == last_c_code:
                    stop_reason_c = "no_changes"
                    break
                if code_c in tried_c_codes:
                    stop_reason_c = "repeat_code"
                    break
                tried_c_codes.add(code_c)
                last_c_code = code_c

            if stop_reason_c is None:
                stop_reason_c = "max_turns"

            final_c = {
                "kind": "final", "task": tid, "seat": seat, "arm": "C",
                "selected_turn": c_candidates[-1]["turn"], "code": c_candidates[-1]["code"],
                "stop_reason": stop_reason_c, "total_tokens": c_tokens,
                "candidates_produced": len(c_candidates)
            }
            write_row(final_c)

        return task_asked

    with cf.ThreadPoolExecutor(parallel) as ex:
        results = list(ex.map(run_one_task, todo_tasks))
    asked_count = sum(results)

    status_str = status_line(meta, idx)
    log(f"step {label}: {seat} asked {asked_count} actions; {status_str}")
    return asked_count


def status_line(meta, idx):
    owe = {s: count_owed(meta, idx, s) for s in ORDER}
    finished = sum(
        1 for t in meta["tasks"]
        if all(
            idx.get((t, s), {}).get("final_g") is not None
            and idx.get((t, s), {}).get("final_c") is not None
            and idx.get((t, s), {}).get("final_p") is not None
            for s in ORDER
        )
    )
    if not any(owe.values()):
        return f"done: {finished}/{len(meta['tasks'])} tasks complete across all arms (P, G, C)"
    nxt = max(ORDER, key=lambda s: (owe[s], s == ORDER[0]))
    return f"owed {owe}; next session: invite {nxt}"


def status(root, label, log=print):
    meta, rows = load_meta_and_rows(root, label)
    idx = build_index(rows)
    for t in meta["tasks"]:
        states = []
        for s in ORDER:
            entry = idx.get((t, s), {})
            p_done = "P" if entry.get("final_p") else "-"
            g_done = f"G({entry['final_g']['selected_turn']})" if entry.get("final_g") else "-"
            c_done = f"C({entry['final_c']['selected_turn']})" if entry.get("final_c") else "-"
            states.append(f"{s}:[{p_done},{g_done},{c_done}]")
        log(f"{t:32} {' '.join(states)}")
    line = status_line(meta, idx)
    log(line)
    return line


def report(root, label, regrade=False, log=print):
    """Hidden fresh grade on final code and compute statistical tests."""
    meta, rows = load_meta_and_rows(root, label)
    tasks = {t["id"]: t for t in run.load_set(meta["set"])}
    idx = build_index(rows)

    mp, rp, sp = paths(root, label)

    # Grading map: (task, seat, arm) -> fresh_pass (bool)
    grades = {}
    tokens_by_arm = {"P": 0, "G": 0, "C": 0}
    tokens_by_seat = {s: {"P": 0, "G": 0, "C": 0} for s in ORDER}

    for t in meta["tasks"]:
        for s in ORDER:
            entry = idx.get((t, s), {})
            for arm in ("P", "G", "C"):
                fin = entry.get(f"final_{arm.lower()}")
                if fin is None:
                    continue
                code = fin.get("code")
                tok = fin.get("total_tokens", 0)
                tokens_by_arm[arm] += tok
                tokens_by_seat[s][arm] += tok

                stored_grade = fin.get("fresh_pass")
                if stored_grade is None or regrade:
                    if code is not None:
                        passed, err, _ = agent.fresh_grade(code, tasks[t]["tests"])
                    else:
                        passed, err = False, "no code"
                    grades[(t, s, arm)] = passed
                else:
                    grades[(t, s, arm)] = bool(stored_grade)

    # Task-level union solve: a task is solved by an arm if EITHER seat passes
    solved_by_arm = {"P": {}, "G": {}, "C": {}}
    for t in meta["tasks"]:
        for arm in ("P", "G", "C"):
            sp = any(grades.get((t, s, arm), False) for s in ORDER)
            solved_by_arm[arm][t] = sp

    l_p = sum(solved_by_arm["P"].values())
    l_g = sum(solved_by_arm["G"].values())
    l_c = sum(solved_by_arm["C"].values())
    n_tasks = len(meta["tasks"])

    # Primary contrast: G vs C
    net_gc = l_g - l_c
    gains_gc = sum(1 for t in meta["tasks"] if solved_by_arm["G"][t] and not solved_by_arm["C"][t])
    losses_gc = sum(1 for t in meta["tasks"] if not solved_by_arm["G"][t] and solved_by_arm["C"][t])
    ties_gc = n_tasks - (gains_gc + losses_gc)
    p_gc = sign_test_p(gains_gc, losses_gc)

    # Primary Verdict (Stage V bar partition)
    # Precondition (no-room rule): if L_C >= 77/90 (~85%) or L_C <= 9/90 (~10%)
    no_room = (l_c >= 77 or l_c <= 9)
    if no_room:
        verdict = "no_room"
    elif net_gc >= T_NOISE and p_gc <= 0.05:
        verdict = "keep"
    elif net_gc <= 0 or p_gc > 0.10:
        verdict = "drop"
    else:
        verdict = "inconclusive"

    # Sensitivity line: net >= 12
    meets_sensitivity = (net_gc >= T_SENSITIVITY)

    # Secondary contrast: G vs P
    net_gp = l_g - l_p
    gains_gp = sum(1 for t in meta["tasks"] if solved_by_arm["G"][t] and not solved_by_arm["P"][t])
    losses_gp = sum(1 for t in meta["tasks"] if not solved_by_arm["G"][t] and solved_by_arm["P"][t])
    p_gp = sign_test_p(gains_gp, losses_gp)

    # Exploratory ablations (computed post hoc on CPU from logged candidates)
    # Ablation 1: selection on static + visible only (ignoring model tests in score)
    # Ablation 2: stop at first visible pass
    ablation_static_vis = {}
    for t in meta["tasks"]:
        for s in ORDER:
            entry = idx.get((t, s), {})
            cand_rows = [entry.get("turn0")] + entry.get("g_revisions", [])
            valid_cands = [c for c in cand_rows if c is not None and "static_pass" in c]
            if valid_cands:
                # Score key without model_pass: (int(static_pass), int(visible_pass), -turn)
                b = max(valid_cands, key=lambda c: (int(bool(c.get("static_pass"))),
                                                   int(bool(c.get("visible_pass"))),
                                                   -c.get("turn", 0)))
                code = b.get("code")
                p, _, _ = agent.fresh_grade(code, tasks[t]["tests"]) if code else (False, "", None)
                ablation_static_vis[(t, s)] = p
    l_ablation_sv = sum(1 for t in meta["tasks"] if any(ablation_static_vis.get((t, s), False) for s in ORDER))

    summary = {
        "label": label, "set": meta["set"], "tasks": n_tasks,
        "protocol": meta["protocol"],
        "solved": {"P": l_p, "G": l_g, "C": l_c},
        "primary_contrast_G_vs_C": {
            "net": net_gc, "gains": gains_gc, "losses": losses_gc, "ties": ties_gc,
            "sign_test_p": round(p_gc, 4), "t_noise": T_NOISE,
            "t_sensitivity": T_SENSITIVITY, "meets_sensitivity": meets_sensitivity,
            "no_room": no_room, "verdict": verdict
        },
        "secondary_contrast_G_vs_P": {
            "net": net_gp, "gains": gains_gp, "losses": losses_gp,
            "sign_test_p": round(p_gp, 4)
        },
        "completion_tokens": {
            "by_arm": tokens_by_arm,
            "by_seat": tokens_by_seat
        },
        "exploratory_ablations": {
            "selection_static_visible_only": {"solved": l_ablation_sv, "net_vs_C": l_ablation_sv - l_c}
        }
    }

    with open(sp, "w") as f:
        json.dump(summary, f, indent=1)

    log(f"--- CRAwDAD Grounding Report: {label} ---")
    log(f"Tasks solved (union): P={l_p}/{n_tasks}, G={l_g}/{n_tasks}, C={l_c}/{n_tasks}")
    log(f"Primary (G vs C): net={net_gc:+d} (gains={gains_gc}, losses={losses_gc}, ties={ties_gc}), "
        f"sign test p={p_gc:.4f} -> VERDICT: {verdict.upper()}" +
        (f" (meets sensitivity >= {T_SENSITIVITY})" if meets_sensitivity else ""))
    log(f"Secondary (G vs P): net={net_gp:+d}, sign test p={p_gp:.4f}")
    log(f"Tokens: P={tokens_by_arm['P']}, G={tokens_by_arm['G']}, C={tokens_by_arm['C']}")
    log(f"Ablation (static+visible only): solved={l_ablation_sv}/{n_tasks} (net vs C: {l_ablation_sv - l_c:+d})")

    return summary, 0 if verdict == "keep" else 1


def selftest():
    """Selftest on CPU against fake models and the real sandbox."""
    ok = True
    def check(name, cond):
        nonlocal ok
        ok &= bool(cond)
        print(f"{'ok' if cond else 'FAIL':4} {name}")

    print("Running ground.py selftest...")

    # 1. Disjointness check
    reserved_ranges = [
        ("run.py", range(0, 16)),
        ("loop", range(1000, 1034)),
        ("fix", range(2000, 2034)),
        ("plan", range(3000, 3002)),
        ("debate_default", range(4000, 4005)),
        ("debate_d3", range(4100, 4105)),
        ("debate_d4", range(4200, 4205))
    ]
    ground_range = range(SEED_BASE, SEED_BASE + 100)
    collisions = []
    for name, r in reserved_ranges:
        overlap = set(ground_range) & set(r)
        if overlap:
            collisions.append((name, overlap))
    check("seed range 5000-5099 is disjoint from all existing suites", len(collisions) == 0)

    # 2. Protocol hash check
    p1 = ground_protocol(5000)
    p2 = ground_protocol(5001)
    check("protocol hash binds seed_base", p1 != p2)
    check("default protocol hash is 12 hex chars", len(p1) == 12)

    # 3. Static checks
    entry_pts = ["parse_mac", "format_mac"]
    ok_s, err_s, _ = static_checks("def parse_mac(): pass\ndef format_mac(): pass", entry_pts)
    check("static checks pass valid definitions", ok_s and err_s == "")

    ok_syn, err_syn, _ = static_checks("def parse_mac(:", entry_pts)
    check("static checks catch syntax error", not ok_syn and "SyntaxError" in err_syn)

    ok_deny, err_deny, _ = static_checks("import os\ndef parse_mac(): pass\ndef format_mac(): pass", entry_pts)
    check("static checks catch deny-list import", not ok_deny and "deny_check" in err_deny)

    ok_ep, err_ep, _ = static_checks("def parse_mac(): pass", entry_pts)
    check("static checks catch missing entry point", not ok_ep and "missing required entry point: format_mac" in err_ep)

    # 4. Sign test p-value against spec worked examples
    check("sign test 9-0 -> p=0.002", round(sign_test_p(9, 0), 3) == 0.002)
    check("sign test 10-1 -> p=0.006", round(sign_test_p(10, 1), 3) == 0.006)
    check("sign test 11-2 -> p=0.011", round(sign_test_p(11, 2), 3) == 0.011)
    check("sign test 7-1 -> p=0.035", round(sign_test_p(7, 1), 3) == 0.035)

    # 5. Candidate selection & tie break
    c0 = {"turn": 0, "static_pass": True, "visible_pass": True, "model_pass": True}
    c1 = {"turn": 1, "static_pass": True, "visible_pass": True, "model_pass": True}
    check("selection tie-break: earliest turn wins", select_best_candidate([c0, c1])["turn"] == 0)

    c0_fail = {"turn": 0, "static_pass": True, "visible_pass": False, "model_pass": False}
    c1_pass = {"turn": 1, "static_pass": True, "visible_pass": True, "model_pass": False}
    check("selection prefers visible pass over visible fail", select_best_candidate([c0_fail, c1_pass])["turn"] == 1)

    print(f"\nSelftest {'PASSED' if ok else 'FAILED'}")
    return 0 if ok else 1


def main():
    parser = argparse.ArgumentParser(description="CRAwDAD Grounding Runner")
    parser.add_argument("--selftest", action="store_true", help="run self tests")
    sub = parser.add_subparsers(dest="cmd")

    p_step = sub.add_parser("step")
    p_step.add_argument("--label", required=True, help="run label")
    p_step.add_argument("--set", default="v10", help="task set (default v10)")
    p_step.add_argument("--tasks", help="comma-separated task IDs")
    p_step.add_argument("--parallel", type=int, default=1, help="concurrency")
    p_step.add_argument("--api", default=run.API, help="server URL")
    p_step.add_argument("--seed-base", type=int, default=None, help="override seed base (first step only)")

    p_stat = sub.add_parser("status")
    p_stat.add_argument("--label", required=True, help="run label")

    p_rep = sub.add_parser("report")
    p_rep.add_argument("--label", required=True, help="run label")
    p_rep.add_argument("--regrade", action="store_true", help="regrade final modules on fresh seed")

    args = parser.parse_args()
    if args.selftest:
        sys.exit(selftest())

    root = os.path.join(HERE, "results")
    os.makedirs(root, exist_ok=True)

    if args.cmd == "step":
        alias = run.served_model(api=args.api)
        server = run.server_info(api=args.api)
        ask = debate.server_ask(alias, args.api)
        tasks_list = args.tasks.split(",") if args.tasks else None
        step(root, args.label, args.set, tasks_list, alias, server, ask,
             parallel=args.parallel, seed_base=args.seed_base)
    elif args.cmd == "status":
        status(root, args.label)
    elif args.cmd == "report":
        _, rc = report(root, args.label, regrade=args.regrade)
        sys.exit(rc)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
