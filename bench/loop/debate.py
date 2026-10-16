#!/usr/bin/env python3
"""CRAwDAD debate runner (docs/diagrams/crawdad-qd-v2.drawio, docs/crawdad-notes.md): two models, one coding task, a
coin picks who answers first, at most 4 replies, graded only at the leaf.

  debate.py --selftest                          the protocol against scripted fake seats and the real grader; no server
  debate.py step --label L --set v7 [--tasks a,b] [--parallel 1] [--api URL]
                                                every reply the served model owes (run inside its llmctl session)
  debate.py status --label L                    each task's state and the seat to invite next; no server
  debate.py report --label L [--regrade]        results/L.debate.summary.json from the replies; --regrade re-grades
                                                every coded reply and exits 2 on a mismatch; no server

Protocol (rounds R1-R4 = the paper code's rounds 0-3):
- R1: the first speaker's own answer: short rationale, solution.py, CONFIDENCE. Every task gets a solo R1 from BOTH
  seats (the exclusive-solve check the paper never runs); the debate's R1 is the coin's seat's solo reply, not asked twice.
- R2: the other seat as critic (appendix C), not forced to find a flaw. R3: the first speaker defends or is persuaded
  (the code's even-round prompt). R4: the critic has the last word.
- Each R2-R4 reply ends with VERDICT: accept (the opponent's latest module stands; no code) or VERDICT: reject plus
  the replier's complete module. accept ends the debate (agreement). A reject at R4 ends it with the R4 module.
- Leaf code = the module standing when the debate ends. Every coded reply is graded once, on the fresh seed
  (agent.fresh_grade); the leaf's grade is its standing reply's. No grade, test or error is ever shown to a model.
- Failures are failures, never coin flips (crawdad-notes defects 2-3): an R1 without a code block ends the task with no
  code (unsolved); an R2-R4 reply with no verdict line, or a reject without a code block, ends it as parse_fail with
  the module standing before it.
- History: every earlier reply of the debate, in order, fenced with ==========, labelled from the speaker's side
  ("Your original answer:", "Your response:", "Opponent's response:"). Each entry is the reply's visible content in
  full; reasoning_content is never stored or passed (the trace is withheld). The second seat's solo R1 is not part of
  the debate and never appears in it. Each request is one fresh user message, so the server's --reasoning-preserve
  (it keeps traces of earlier assistant turns) has nothing to act on.
- Deliberate deviations from the paper code: a balanced coin (a seeded shuffle, first half Qwen first) instead of one
  flip per task; top_k 20 (Qwen3 thinking recommendation, as in our earlier runs) instead of Ollama's 40; a seed per
  reply (SEED_BASE + round); thinking capped at REASONING_BUDGET tokens by llama.cpp with BUDGET_MESSAGE, inside
  MAX_TOKENS; slot context >= SLOT_MIN instead of 2048 x (round + 1); the extractor is a code-block and verdict-line
  parser (no Granite model); the causal "no trick questions" line is dropped; confidence is recorded, never used.

Sessions. One model is resident at a time (llmctl, gpu-guard), so the runner never swaps models. `step` runs inside an
llmctl session of one seat and asks every reply that seat owes: its solo R1 on each task, then each debate reply whose
speaker it is and whose previous round exists. A set takes five sessions, alternating seats (`status` names the next).
results/L.debate.jsonl (one row per reply, flushed as it lands) is the state: a step resumes where the last one
stopped and never asks a reply twice. results/L.debate.meta.json fixes the run at its first step (set, tasks, coin,
constants, prompt hash, server build); a later step that differs in any of them is refused.
"""
import argparse, concurrent.futures as cf, hashlib, json, os, random, re, sys, tempfile, threading, time
import urllib.error, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import run  # noqa: E402  grade, extract, load_set, SAMPLING, served_model
import agent  # noqa: E402  fresh_grade, FRESH_SEED

SEATS = {"qwen3-32b": "qwen32", "r1-distill-qwen-32b": "r1d32"}   # served alias (llm-serve.sh --alias) -> llmctl endpoint
ORDER = ("qwen32", "r1d32")
COIN_SEED = 42            # the paper code's coin seed
SEED_BASE = 4000          # reply seed = SEED_BASE + round; disjoint from run.py 0-15, loop 1000+, fix 2000+, plan 3000-3001
REASONING_BUDGET = 2048   # user, 2026-10-15
MAX_TOKENS = 6144         # thinking + visible answer
BUDGET_MESSAGE = "Reasoning budget reached. Write the answer now."
SLOT_MIN = 2048 + 4 * MAX_TOKENS   # task prompt and instructions + 3 history entries (each <= MAX_TOKENS) + the reply

SOLO_SUFFIX = ("\n\nAnswer in this order: a short rationale for your approach (at most 150 words); one complete "
               "Python 3 module in a single ```python code block (standard library only, no example usage, no tests, "
               "no input()); then a last line `CONFIDENCE: c`, c from 0.0 to 1.0, how likely your module is correct.")
DEBATE_HEAD = ("You and another LLM are being asked to write the same Python module. I believe two heads are better "
               "than one, so I ask that you debate with the other LLM to reach a consensus on the code.\n\nThe task:\n\n")
CRITIC = ("Carefully read the task, then scrutinize your opponent's latest solution. If you identify any flaws in their "
          "reasoning or errors in their code, point them out and suggest corrections. Make explicit references to your "
          "opponent's response. You are not required to find a flaw: if their module is correct as written, accept it.")
DEFENDER = ("Consider your opponent's response. Defend your previous answer or be persuaded by your opponent, making "
            "explicit references to your opponent's response.")
VERDICT_RULES = ("\n\nThen end your reply with two lines. First `VERDICT: accept` or `VERDICT: reject`. accept: your "
                 "opponent's latest module is correct as written; write no code. reject: it is not; before the verdict "
                 "line give your complete module (corrected, or your earlier one if you stand by it) in a single "
                 "```python code block, standard library only, no example usage, no tests, no input(). Last, "
                 "`CONFIDENCE: c`, c from 0.0 to 1.0, how likely the module that stands after your reply is correct.")
FENCE = "=========="
PROTOCOL = hashlib.sha256(json.dumps([SOLO_SUFFIX, DEBATE_HEAD, CRITIC, DEFENDER, VERDICT_RULES, FENCE, BUDGET_MESSAGE,
                                      REASONING_BUDGET, MAX_TOKENS, SEED_BASE, COIN_SEED, run.SAMPLING,
                                      agent.FRESH_SEED]).encode()).hexdigest()[:12]

CODE_BLOCK = re.compile(r"```.*?(?:```|\Z)", re.S)
VERDICT_RE = re.compile(r"^[\W_]*verdict[\W_]*(accept|reject)\b", re.I | re.M)
CONF_RE = re.compile(r"^[\W_]*confidence[^\w.]*(\d*\.?\d+)", re.I | re.M)   # the separator never eats the "." of .9


def visible(content):
    """The reply after the last </think> (a template leak would put the trace in content)."""
    return (content or "").rsplit("</think>", 1)[-1].strip()


def parse(content):
    """(code, verdict, confidence) of a reply. The verdict and confidence lines are read outside code blocks; the
    last of each counts. A confidence outside 0-1 is None, as is a missing one (the paper code used 0.6)."""
    text = visible(content)
    prose = CODE_BLOCK.sub("", text)
    v, c = VERDICT_RE.findall(prose), CONF_RE.findall(prose)
    conf = float(c[-1]) if c else None
    return run.extract(text), (v[-1].lower() if v else None), (conf if conf is not None and conf <= 1.0 else None)


def coin(task_ids):
    """Balanced first speaker: a seeded shuffle of the sorted ids, first half ORDER[0]. Independent of input order."""
    ids = sorted(task_ids)
    random.Random(COIN_SEED).shuffle(ids)
    half = (len(ids) + 1) // 2
    return {t: ORDER[0] if i < half else ORDER[1] for i, t in enumerate(ids)}


def other(seat):
    return ORDER[1] if seat == ORDER[0] else ORDER[0]


def walk(first, solo, deb):
    """One task's state. solo: {seat: R1 row}, deb: {round: R2-R4 row}. Returns {leaf, round, stop, standing} at a leaf,
    else {leaf: False, next: (seat, round), standing}. standing = the row whose module currently stands (or None)."""
    seq = {1: first, 2: other(first), 3: first, 4: other(first)}
    r1 = solo.get(first)
    if r1 is None:
        return {"leaf": False, "next": (first, 1), "standing": None}
    if r1["code"] is None:
        return {"leaf": True, "round": 1, "stop": "no_code", "standing": None}
    standing = r1
    for rnd in (2, 3, 4):
        row = deb.get(rnd)
        if row is None:
            return {"leaf": False, "next": (seq[rnd], rnd), "standing": standing}
        if row["verdict"] == "accept":
            return {"leaf": True, "round": rnd, "stop": "accept", "standing": standing}
        if row["verdict"] != "reject" or row["code"] is None:
            return {"leaf": True, "round": rnd, "stop": "parse_fail", "standing": standing}
        standing = row
    return {"leaf": True, "round": 4, "stop": "max_rounds", "standing": standing}


def history(speaker, entries):
    out = []
    for row in entries:
        label = ("Opponent's response:" if row["seat"] != speaker
                 else "Your original answer:" if row["round"] == 1 else "Your response:")
        out.append(f"{FENCE}\n{label}\n{visible(row['content'])}")
    return "\n".join(out) + f"\n{FENCE}"


def solo_prompt(task):
    return task["prompt"] + SOLO_SUFFIX


def debate_prompt(task, speaker, rnd, entries):
    role = CRITIC if rnd % 2 == 0 else DEFENDER
    return (DEBATE_HEAD + task["prompt"] + "\n\nThe debate so far:\n\n" + history(speaker, entries) + "\n\n"
            + role + VERDICT_RULES)


def request_body(model, prompt, seed):
    return {"model": model, "messages": [{"role": "user", "content": prompt}], "max_tokens": MAX_TOKENS,
            "reasoning_budget_tokens": REASONING_BUDGET, "reasoning_budget_message": BUDGET_MESSAGE,
            "seed": seed, **run.SAMPLING}


def parse_response(resp, gen_s):
    """The fields a row keeps from a chat completion. reasoning_content is reduced to its length."""
    ch = resp["choices"][0]
    tm = resp.get("timings") or {}
    return {"content": ch["message"].get("content") or "",
            "reasoning_chars": len(ch["message"].get("reasoning_content") or ""),
            "finish": ch.get("finish_reason"), "usage": resp.get("usage", {}), "gen_s": gen_s,
            "prompt_n": tm.get("prompt_n"), "tg_tps": tm.get("predicted_per_second")}


def server_ask(model, api):
    def ask(prompt, seed):
        req = urllib.request.Request(f"{api}/v1/chat/completions", json.dumps(request_body(model, prompt, seed)).encode(),
                                     {"Content-Type": "application/json"})
        t = time.time()
        try:
            with urllib.request.urlopen(req, timeout=3600) as r:
                resp = json.load(r)
        except urllib.error.HTTPError as e:
            raise SystemExit(f"HTTP {e.code} from {api}: {e.read()[:300]!r}; nothing written for this reply")
        return parse_response(resp, round(time.time() - t, 1))
    return ask


def server_props(api):
    with urllib.request.urlopen(f"{api}/props", timeout=10) as r:
        p = json.load(r)
    return {"build_info": p.get("build_info"), "model_path": p.get("model_path"), "model_alias": p.get("model_alias"),
            "n_ctx": (p.get("default_generation_settings") or {}).get("n_ctx"), "total_slots": p.get("total_slots")}


def paths(root, label):
    b = os.path.join(root, label + ".debate")
    return b + ".meta.json", b + ".jsonl", b + ".summary.json"


def load(root, label):
    mp, rp, _ = paths(root, label)
    if not os.path.exists(mp):
        raise SystemExit(f"{mp}: no such run (the first step writes it)")
    meta = json.load(open(mp))
    rows = [json.loads(l) for l in open(rp)] if os.path.exists(rp) else []
    return meta, rows


def save_meta(path, meta):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(meta, f, indent=1)
    os.replace(tmp, path)


def index(rows):
    """{task: (solo {seat: row}, deb {round: row})}; a duplicate key is an error (a reply is never asked twice)."""
    out = {}
    for r in rows:
        solo, deb = out.setdefault(r["task"], ({}, {}))
        d, k = (solo, r["seat"]) if r["round"] == 1 else (deb, r["round"])
        if k in d:
            raise SystemExit(f"duplicate reply {r['task']} {r['seat']} R{r['round']}")
        d[k] = r
    return out


def owed(meta, idx, seat):
    """Replies `seat` can ask now: [(task, round)], solo R1 first."""
    out = []
    for t in meta["tasks"]:
        solo, deb = idx.get(t, ({}, {}))
        if seat not in solo:
            out.append((t, 1))
            solo = dict(solo, **{seat: {"seat": seat, "round": 1, "code": "pending", "verdict": None}})
        st = walk(meta["first"][t], solo, deb)
        if not st["leaf"] and st["next"][0] == seat and st["next"][1] > 1:
            out.append((t, st["next"][1]))
    return out


def step(root, label, set_name, task_ids, alias, server, ask, parallel=1, log=print):
    """Ask every reply the served seat owes. Returns the number of replies asked."""
    if alias not in SEATS:
        raise SystemExit(f"served model {alias!r} is not a debate seat ({sorted(SEATS)})")
    seat = SEATS[alias]
    if not server.get("n_ctx") or server["n_ctx"] < SLOT_MIN:
        raise SystemExit(f"slot context {server.get('n_ctx')} < SLOT_MIN {SLOT_MIN}: invite with a larger --ctx per slot")
    if parallel > (server.get("total_slots") or 1):
        raise SystemExit(f"--parallel {parallel} > the server's {server.get('total_slots')} slots")
    mp, rp, _ = paths(root, label)
    if os.path.exists(mp):
        meta, rows = load(root, label)
        for k, want in (("set", set_name), ("tasks", task_ids)):
            if want is not None and meta[k] != want:
                raise SystemExit(f"{mp}: {k} is {meta[k]}, this step asked for {want}")
        if meta["protocol"] != PROTOCOL:
            raise SystemExit(f"{mp}: protocol {meta['protocol']}, this code is {PROTOCOL} (prompts or constants changed mid-run)")
        if meta["build"] != server.get("build_info"):
            raise SystemExit(f"{mp}: server build {meta['build']}, the served one is {server.get('build_info')}")
        prev = meta["seats"].get(seat)
        if prev and prev["model_path"] != server.get("model_path"):
            raise SystemExit(f"{mp}: {seat} was {prev['model_path']}, now {server.get('model_path')}")
    else:
        if set_name is None:
            raise SystemExit("the first step of a run needs --set")
        all_ids = [t["id"] for t in run.load_set(set_name)]
        task_ids = task_ids or all_ids
        unknown = set(task_ids) - set(all_ids)
        if unknown:
            raise SystemExit(f"unknown task ids: {sorted(unknown)}")
        meta = {"label": label, "set": set_name, "tasks": task_ids, "first": coin(task_ids), "coin_seed": COIN_SEED,
                "protocol": PROTOCOL, "reasoning_budget": REASONING_BUDGET, "max_tokens": MAX_TOKENS,
                "sampling": run.SAMPLING, "seed_base": SEED_BASE, "fresh_seed": agent.FRESH_SEED,
                "build": server.get("build_info"), "seats": {}}
        rows = []
    meta["seats"].setdefault(seat, {"model": alias, "model_path": server.get("model_path"), "n_ctx": server.get("n_ctx")})
    save_meta(mp, meta)
    tasks = {t["id"]: t for t in run.load_set(meta["set"])}
    idx = index(rows)
    lock, dead = threading.Lock(), threading.Event()
    todo = sorted({t for t, _ in owed(meta, idx, seat)}, key=meta["tasks"].index)
    log(f"step {label}: {seat} owes {len(owed(meta, idx, seat))} replies on {len(todo)} tasks")

    def one(tid):
        task, n = tasks[tid], 0
        while not dead.is_set():   # after a failed request no new one starts; the rows so far stay
            with lock:
                solo, deb = idx.get(tid, ({}, {}))
                if seat not in solo:
                    rnd, role, prompt = 1, "solo", solo_prompt(task)
                else:
                    st = walk(meta["first"][tid], solo, deb)
                    if st["leaf"] or st["next"][0] != seat or st["next"][1] == 1:
                        return n
                    rnd = st["next"][1]
                    role = "critic" if rnd % 2 == 0 else "defender"
                    entries = [solo[meta["first"][tid]]] + [deb[k] for k in range(2, rnd)]
                    prompt = debate_prompt(task, seat, rnd, entries)
            try:
                r = ask(prompt, SEED_BASE + rnd)
            except BaseException:
                dead.set()
                raise
            code, verdict, conf = parse(r["content"])
            row = {"task": tid, "seat": seat, "model": alias, "round": rnd, "role": role, "seed": SEED_BASE + rnd,
                   "content": r["content"], "reasoning_chars": r["reasoning_chars"], "finish": r["finish"],
                   "completion_tokens": r["usage"].get("completion_tokens"),
                   "prompt_tokens": r["usage"].get("prompt_tokens"), "prompt_n": r.get("prompt_n"),
                   "tg_tps": r.get("tg_tps"), "gen_s": r["gen_s"], "code": code, "verdict": verdict,
                   "confidence": conf, "think_leak": "</think>" in (r["content"] or "")}
            if code is not None:
                t0 = time.monotonic()
                fp, ferr, nf = agent.fresh_grade(code, task["tests"])
                row.update(fresh_pass=fp, fresh_err="" if fp else ferr, no_fresh=nf,
                           grade_s=round(time.monotonic() - t0, 2))
            else:
                row.update(fresh_pass=False, fresh_err="no code block", no_fresh=None, grade_s=0.0)
            with lock:
                with open(rp, "a") as f:
                    f.write(json.dumps(row) + "\n")
                solo, deb = idx.setdefault(tid, ({}, {}))
                (solo if rnd == 1 else deb)[seat if rnd == 1 else rnd] = row
            n += 1
            log(f"{tid:28} {seat} R{rnd} {role:8} {'pass' if row['fresh_pass'] else 'fail'} verdict={verdict} "
                f"tok={row['completion_tokens']} {row['gen_s']}s")
        return n

    with cf.ThreadPoolExecutor(parallel) as ex:
        asked = sum(ex.map(one, todo))
    log(f"step {label}: {seat} asked {asked}; " + status_line(meta, idx))
    return asked


def status_line(meta, idx):
    owe = {s: len(owed(meta, idx, s)) for s in ORDER}
    leaves = sum(walk(meta["first"][t], *idx.get(t, ({}, {})))["leaf"] for t in meta["tasks"])
    if not any(owe.values()):
        return f"done: {leaves}/{len(meta['tasks'])} tasks at a leaf, both solos complete"
    nxt = max(ORDER, key=lambda s: (owe[s], s == ORDER[0]))
    return f"owed {owe}; next session: invite {nxt}"


def status(root, label, log=print):
    meta, rows = load(root, label)
    idx = index(rows)
    for t in meta["tasks"]:
        solo, deb = idx.get(t, ({}, {}))
        st = walk(meta["first"][t], solo, deb)
        state = f"leaf R{st['round']} {st['stop']}" if st["leaf"] else f"next {st['next'][0]} R{st['next'][1]}"
        log(f"{t:28} first={meta['first'][t]:7} solos={sorted(solo)} rounds={sorted(deb)} {state}")
    line = status_line(meta, idx)
    log(line)
    return line


def report(root, label, regrade=False, log=print):
    meta, rows = load(root, label)
    idx = index(rows)
    tasks = {t["id"]: t for t in run.load_set(meta["set"])}
    mismatch = []
    if regrade:
        for r in rows:
            if r["code"] is not None and agent.fresh_grade(r["code"], tasks[r["task"]]["tests"])[0] != r["fresh_pass"]:
                mismatch.append(f"{r['task']} {r['seat']} R{r['round']}")
    per, solo_pass = [], {s: 0 for s in ORDER}
    excl = {"both": 0, "neither": 0, **{f"{s}_only": 0 for s in ORDER}}
    leaves, stops, flips = {}, {}, {"pass_pass": 0, "fail_pass": 0, "pass_fail": 0, "fail_fail": 0}
    by_first = {s: {"tasks": 0, "first_solo": 0, "leaf": 0} for s in ORDER}
    complete = True
    for t in meta["tasks"]:
        solo, deb = idx.get(t, ({}, {}))
        first = meta["first"][t]
        st = walk(first, solo, deb)
        sp = {s: bool(solo.get(s, {}).get("fresh_pass")) for s in ORDER}
        complete &= st["leaf"] and all(s in solo for s in ORDER)
        for s in ORDER:
            solo_pass[s] += sp[s]
        if sp[ORDER[0]] and sp[ORDER[1]]:
            excl["both"] += 1
        elif sp[ORDER[0]] or sp[ORDER[1]]:
            excl[f"{ORDER[0] if sp[ORDER[0]] else ORDER[1]}_only"] += 1
        else:
            excl["neither"] += 1
        rec = {"task": t, "first": first, "solo": sp, "leaf": st["leaf"]}
        if st["leaf"]:
            lp = bool(st["standing"] and st["standing"]["fresh_pass"])
            leaves[f"R{st['round']}"] = leaves.get(f"R{st['round']}", 0) + 1
            stops[st["stop"]] = stops.get(st["stop"], 0) + 1
            flips[f"{'pass' if sp[first] else 'fail'}_{'pass' if lp else 'fail'}"] += 1
            by_first[first]["tasks"] += 1
            by_first[first]["first_solo"] += sp[first]
            by_first[first]["leaf"] += lp
            rec.update(round=st["round"], stop=st["stop"], leaf_pass=lp,
                       standing=(st["standing"]["seat"], st["standing"]["round"]) if st["standing"] else None)
        per.append(rec)

    def seat_stats(s):
        rs = [r for r in rows if r["seat"] == s]
        by_round = {}
        for r in rs:
            d = by_round.setdefault(f"R{r['round']}", {"replies": 0, "prompt_tokens": 0, "tps": []})
            d["replies"] += 1
            d["prompt_tokens"] += r["prompt_tokens"] or 0
            if r["tg_tps"]:
                d["tps"].append(r["tg_tps"])
        return {"replies": len(rs), "completion_tokens": sum(r["completion_tokens"] or 0 for r in rs),
                "gen_s": round(sum(r["gen_s"] or 0 for r in rs), 1),
                "finish_length": sum(r["finish"] == "length" for r in rs),
                "solo_no_code": sum(r["round"] == 1 and r["code"] is None for r in rs),
                "no_verdict": sum(r["round"] > 1 and r["verdict"] is None for r in rs),
                "reject_no_code": sum(r["verdict"] == "reject" and r["code"] is None for r in rs),
                "think_leak": sum(bool(r.get("think_leak")) for r in rs),
                "accept_with_code": sum(r["verdict"] == "accept" and r["code"] is not None for r in rs),
                "by_round": {k: {"replies": d["replies"], "mean_prompt_tokens": round(d["prompt_tokens"] / d["replies"]),
                                 "mean_tg_tps": round(sum(d["tps"]) / len(d["tps"]), 2) if d["tps"] else None}
                             for k, d in sorted(by_round.items())}}

    summary = {"label": label, "set": meta["set"], "tasks": len(meta["tasks"]), "complete": complete,
               "protocol": meta["protocol"], "build": meta["build"], "seats": meta["seats"],
               "reasoning_budget": meta["reasoning_budget"], "max_tokens": meta["max_tokens"],
               "sampling": meta["sampling"], "fresh_seed": meta["fresh_seed"],
               "first_counts": {s: sum(v == s for v in meta["first"].values()) for s in ORDER},
               "solo_solved": solo_pass, "solo_union": len(meta["tasks"]) - excl["neither"], "exclusive": excl,
               "debate_solved": sum(r.get("leaf_pass", False) for r in per), "leaves": leaves, "stops": stops,
               "first_solo_to_leaf": flips, "by_first_speaker": by_first,
               "per_seat": {s: seat_stats(s) for s in ORDER}, "replies": len(rows),
               "regrade": ("ok" if not mismatch else mismatch) if regrade else None, "per_task": per}
    _, _, sp_ = paths(root, label)
    with open(sp_, "w") as f:
        json.dump(summary, f, indent=1)
    log(json.dumps({k: v for k, v in summary.items() if k not in ("per_task", "per_seat")}, indent=1))
    return summary, (2 if mismatch else 0)


def selftest():
    ok = True

    def check(name, cond):
        nonlocal ok
        ok &= bool(cond)
        print(f"{'ok' if cond else 'FAIL':4} {name}")

    # parsing
    check("verdict: markdown bold, case-insensitive", parse("fine\n**VERDICT:** Accept\nCONFIDENCE: 0.9")[1:] == ("accept", 0.9))
    check("verdict: the last line counts", parse("VERDICT: reject\nchanged my mind\nVERDICT: accept")[1] == "accept")
    check("verdict: a line inside a code block is ignored",
          parse("```python\n# VERDICT: accept\nx = 1\n```\nVERDICT: reject")[1] == "reject")
    check("verdict: 'Verdict accepted' is not a verdict", parse("Verdict accepted by all.")[1] is None)
    check("confidence: .9 parses, 85 is out of range", parse("CONFIDENCE: .9")[2] == 0.9 and parse("CONFIDENCE: 85")[2] is None)
    check("visible: a leaked trace before </think> is cut", visible("<think>TRACE</think>\nanswer") == "answer")
    resp = {"choices": [{"message": {"content": "c", "reasoning_content": "TRACE-MARKER " * 10}, "finish_reason": "stop"}],
            "usage": {"completion_tokens": 7}, "timings": {"prompt_n": 5, "predicted_per_second": 11.1}}
    pr = parse_response(resp, 1.0)
    check("parse_response keeps the trace's length only", "TRACE-MARKER" not in json.dumps(pr)
          and pr["reasoning_chars"] == 130 and pr["tg_tps"] == 11.1)
    b = request_body("m", "p", 4002)
    check("request: budget 2048 + message inside max_tokens 6144, seed, sampling",
          b["reasoning_budget_tokens"] == 2048 and b["reasoning_budget_message"] == BUDGET_MESSAGE
          and b["max_tokens"] == 6144 and b["seed"] == 4002 and b["top_k"] == 20 and b["messages"][0]["content"] == "p")
    # walk: a reject without code is a parse failure; the module standing before it stays
    r1 = {"seat": "qwen32", "round": 1, "code": "A", "verdict": None}
    st = walk("qwen32", {"qwen32": r1}, {2: {"seat": "r1d32", "round": 2, "code": None, "verdict": "reject"}})
    check("walk: reject without code -> parse_fail, R1 stands", st["leaf"] and st["stop"] == "parse_fail" and st["standing"] is r1)

    # the protocol end to end: six v1 tasks, scripted seats, the real grader
    tasks = run.load_set("v1")[:6]
    ids = [t["id"] for t in tasks]
    first = coin(ids)
    check("coin: balanced 3/3 and independent of input order",
          sorted(first.values()).count("qwen32") == 3 and coin(list(reversed(ids))) == first)
    good = {t["id"]: t["ref"] for t in tasks}
    bad = {t["id"]: "def " + t["ref"].split("def ", 1)[1].split("(", 1)[0] + "(*a, **k):\n    return None\n" for t in tasks}

    def code(c, note="Rationale."):
        return f"{note}\n```python\n{c}\n```\nCONFIDENCE: 0.8"

    def reject(c):
        return f"Their module has a bug.\n```python\n{c}\n```\nVERDICT: reject\nCONFIDENCE: 0.7"

    ACC = "Their module is correct.\nVERDICT: accept\nCONFIDENCE: 0.9"
    A, B, C, D, E, F = ids
    MARK = "# SOLO-SECOND-MARKER"
    script = {
        A: {"s1": code(good[A]), "s2": code(good[A] + "\n" + MARK), 2: ACC},
        B: {"s1": code(bad[B]), "s2": code(good[B] + "\n" + MARK), 2: reject(good[B]), 3: ACC},
        C: {"s1": code(good[C]), "s2": code(bad[C] + "\n" + MARK), 2: reject(bad[C]), 3: reject(good[C]), 4: ACC},
        D: {"s1": code(good[D]), "s2": code(bad[D] + "\n" + MARK), 2: reject(bad[D]), 3: reject(good[D]), 4: reject(bad[D])},
        E: {"s1": "I ran out of room before the code.", "s2": code(good[E] + "\n" + MARK)},
        F: {"s1": "<think>SECRET-TRACE</think>\n" + code(good[F]), "s2": code(good[F] + "\n" + MARK), 2: "I agree with them."},
    }
    calls, flock = [], threading.Lock()

    def fake(seat, fail_at=None):
        def ask(prompt, seed):
            with flock:   # the count and the append are one step across threads
                return locked(prompt, seed)

        def locked(prompt, seed):
            if fail_at is not None and len(calls) + 1 == fail_at:
                calls.append((seat, None, None, prompt))
                raise RuntimeError("server died")
            tid = next(t["id"] for t in tasks if t["prompt"] in prompt)
            rnd = seed - SEED_BASE
            key = ("s1" if first[tid] == seat else "s2") if rnd == 1 else rnd
            calls.append((seat, tid, rnd, prompt))
            if key not in script[tid]:
                raise AssertionError(f"unexpected request {tid} {seat} R{rnd}")
            return {"content": script[tid][key], "reasoning_chars": 3, "finish": "stop",
                    "usage": {"completion_tokens": 100, "prompt_tokens": 50}, "gen_s": 0.0, "prompt_n": 50, "tg_tps": 11.0}
        return ask

    alias = {v: k for k, v in SEATS.items()}
    srv = {"build_info": "b-test", "model_path": "/m", "model_alias": "x", "n_ctx": SLOT_MIN, "total_slots": 4}
    quiet = lambda *a: None
    with tempfile.TemporaryDirectory() as root:
        # five alternating sessions finish the set; the first session's seat is status's suggestion (qwen32 on a tie)
        n_by_step, seat = [], "qwen32"
        for i in range(5):
            n_by_step.append(step(root, "t", "v1" if i == 0 else None, ids if i == 0 else None, alias[seat],
                                  dict(srv, model_path="/m/" + seat), fake(seat), parallel=3, log=quiet))
            seat = other(seat)
        line = status(root, "t", log=quiet)
        check(f"five alternating steps complete the set (replies per step {n_by_step})",
              line.startswith("done: 6/6") and sum(n_by_step) == 22)
        check("a sixth step asks nothing", step(root, "t", None, None, alias[seat], dict(srv, model_path="/m/" + seat),
                                                 fake(seat), log=quiet) == 0)
        summ, rc = report(root, "t", regrade=True, log=quiet)
        first_ok, second_ok = {A, C, D, F}, {A, B, E, F}   # whose solo module is the ref, by role
        want = {s: sum((t in first_ok) if first[t] == s else (t in second_ok) for t in ids) for s in ORDER}
        check(f"report: solo solved per seat {want}, union 6, exclusive 2 both / 4 one-seat / 0 neither",
              summ["solo_solved"] == want and summ["solo_union"] == 6 and summ["exclusive"]["both"] == 2
              and summ["exclusive"]["neither"] == 0)
        check("report: one leaked trace, one parse failure without a verdict, one solo without code",
              sum(summ["per_seat"][s]["think_leak"] for s in ORDER) == 1
              and sum(summ["per_seat"][s]["no_verdict"] for s in ORDER) == 1
              and sum(summ["per_seat"][s]["solo_no_code"] for s in ORDER) == 1)
        check("report: debate 4/6; leaves R1 1, R2 2, R3 1, R4 2",
              summ["debate_solved"] == 4 and summ["leaves"] == {"R1": 1, "R2": 2, "R3": 1, "R4": 2})
        check("report: stops accept 3, max_rounds 1, no_code 1, parse_fail 1",
              summ["stops"] == {"accept": 3, "max_rounds": 1, "no_code": 1, "parse_fail": 1})
        check("report: first solo -> leaf: helpful 1 (B), harmful 1 (D)",
              summ["first_solo_to_leaf"] == {"pass_pass": 3, "fail_pass": 1, "pass_fail": 1, "fail_fail": 1})
        check("report: --regrade matches every stored grade, complete, 22 replies",
              rc == 0 and summ["regrade"] == "ok" and summ["complete"] and summ["replies"] == 22)
        per = {p["task"]: p for p in summ["per_task"]}
        check("leaf modules: B stands on R2, C on R3, D on R4, F on R1",
              per[B]["standing"][1] == 2 and per[C]["standing"][1] == 3 and per[D]["standing"][1] == 4
              and per[F]["standing"][1] == 1 and per[E]["standing"] is None)
        prompts = {(tid, rnd): p for s, tid, rnd, p in calls}
        p3 = prompts[(C, 3)]
        i1, i2 = p3.find("Your original answer:\n" + visible(script[C]["s1"])), p3.find("Opponent's response:\n" + visible(script[C][2]))
        check("R3 prompt: own R1 then the critic's R2, labelled and fenced, defender role",
              0 < i1 < i2 and p3.count(FENCE) == 3 and DEFENDER in p3 and CRITIC not in p3)
        p4 = prompts[(C, 4)]
        check("R4 prompt: Opponent / Your response / Opponent, critic role",
              p4.find("Opponent's response:") < p4.find("Your response:") < p4.rfind("Opponent's response:")
              and p4.count(FENCE) == 4 and CRITIC in p4)
        debate_prompts = [p for s, tid, rnd, p in calls if rnd and rnd > 1]
        check("the second seat's solo R1 never enters a debate prompt", not any(MARK in p for p in debate_prompts))
        check("a leaked trace never enters a later prompt", "SECRET-TRACE" not in prompts[(F, 2)]
              and visible(script[F]["s1"]) in prompts[(F, 2)])
        check("R1 without code: no R2 is asked", (E, 2) not in prompts)
        check("solo prompt is the task prompt + SOLO_SUFFIX",
              prompts[(A, 1)] == next(t for t in tasks if t["id"] == A)["prompt"] + SOLO_SUFFIX)
        # guards
        def refused(fn):
            try:
                fn()
            except SystemExit:
                return True
            return False
        check("refused: a served model that is not a seat",
              refused(lambda: step(root, "t", None, None, "qwen3.6-35b-a3b", srv, fake("qwen32"), log=quiet)))
        check("refused: slot context below SLOT_MIN",
              refused(lambda: step(root, "u", "v1", ids, alias["qwen32"], dict(srv, n_ctx=16384), fake("qwen32"), log=quiet)))
        check("refused: --parallel above the server's slots",
              refused(lambda: step(root, "u", "v1", ids, alias["qwen32"], dict(srv, total_slots=1), fake("qwen32"), parallel=2, log=quiet)))
        check("refused: other tasks than the run's",
              refused(lambda: step(root, "t", None, ids[:2], alias["qwen32"], dict(srv, model_path="/m/qwen32"), fake("qwen32"), log=quiet)))
        check("refused: another server build",
              refused(lambda: step(root, "t", None, None, alias["qwen32"], dict(srv, build_info="b-other", model_path="/m/qwen32"), fake("qwen32"), log=quiet)))
        check("refused: the same seat on another model file",
              refused(lambda: step(root, "t", None, None, alias["qwen32"], dict(srv, model_path="/m/other"), fake("qwen32"), log=quiet)))
        mp = paths(root, "t")[0]
        m = json.load(open(mp)); m["protocol"] = "000000000000"; save_meta(mp, m)
        check("refused: a protocol hash that is not this code's",
              refused(lambda: step(root, "t", None, None, alias["qwen32"], dict(srv, model_path="/m/qwen32"), fake("qwen32"), log=quiet)))
    with tempfile.TemporaryDirectory() as root:
        # resume, with r1d32 as the first session: the server dies on the 4th request (2 slots, 2 tasks in flight);
        # no request starts after it, and the rerun asks only what is missing
        calls.clear()
        try:
            step(root, "r", "v1", ids, alias["r1d32"], srv, fake("r1d32", fail_at=4), parallel=2, log=quiet)
            died = False
        except RuntimeError:
            died = True
        n_rows, n_calls = len(load(root, "r")[1]), len(calls)
        step(root, "r", None, None, alias["r1d32"], srv, fake("r1d32"), log=quiet)
        meta, rows = load(root, "r")
        index(rows)   # raises on a duplicate reply
        check(f"resume: {n_rows} rows from {n_calls} requests before the failure, 6 r1d32 solos after the rerun, "
              "every request but the failed one wrote a row",
              died and n_calls <= 5 and n_rows == n_calls - 1 and len(rows) == 6 and len(calls) == n_calls + 6 - n_rows)
        seat, n = "qwen32", []
        for _ in range(4):
            n.append(step(root, "r", None, None, alias[seat], srv, fake(seat), log=quiet))
            seat = other(seat)
        check(f"r1d32 as the first session also finishes in five (replies after the solos {n})",
              status(root, "r", log=quiet).startswith("done: 6/6") and len(load(root, "r")[1]) == 22)
    print(f"selftest {'OK' if ok else 'FAILED'} (protocol {PROTOCOL})")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("cmd", nargs="?", choices=("step", "status", "report"))
    ap.add_argument("--label")
    ap.add_argument("--set", choices=sorted(run.SETS))
    ap.add_argument("--tasks", help="comma-separated task ids (first step only; default all tasks of the set)")
    ap.add_argument("--parallel", type=int, default=1, help="tasks in flight; at most the server's slots")
    ap.add_argument("--api", default=run.API)
    ap.add_argument("--regrade", action="store_true", help="report: re-grade every coded reply, exit 2 on a mismatch")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if not a.cmd or not a.label:
        ap.error("step|status|report and --label are required (or --selftest)")
    root = os.path.join(HERE, "results")
    if a.cmd == "status":
        status(root, a.label)
        return 0
    if a.cmd == "report":
        return report(root, a.label, a.regrade)[1]
    os.makedirs(root, exist_ok=True)
    alias = run.served_model(api=a.api)
    step(root, a.label, a.set, a.tasks.split(",") if a.tasks else None, alias, server_props(a.api),
         server_ask(alias, a.api), a.parallel)
    return 0


if __name__ == "__main__":
    sys.exit(main())
