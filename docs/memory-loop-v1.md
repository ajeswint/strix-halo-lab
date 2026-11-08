# Verified coding-memory loop v1 (2026-11-07, no GPU)

AJ approved 2026-11-07 CT, after the CRAwDAD v8 baseline (archived read-only at
`/home/aj/lab-archive/crawdad-v8-baseline-2026-11-07`). A small learn-from-mistakes memory for the coding bench:
distill a short, generalizable lesson from a graded failure that was later fixed on a TRAINING task, keep it only with
the verdict that verified the fix, and inject the top-k lessons into prompts for new tasks behind `--memory on|off`.
Implementation only. Nothing here has been run on a model; the eval below is written and executable, not run.
There is no v9 (or later) task file; no held-out comparison can start until one is written (section 4).

**What "verified" means here, and only this:** a lesson is admitted only if the same model's trajectory on a train
task had a graded failure and then a later attempt that passed the visible tests and `agent.fresh_grade` (oracle seed
swapped), re-graded on CPU at distill time. It does not mean the lesson text was checked to cause the fix, that
the lesson helps on another task, or that it is free of leakage beyond the lexical checks in section 2.

## Split: train vs held-out

| Sets | Split | Why |
|---|---|---|
| v0-v8 | `train` (`run.TRAIN_SETS`, `memring.TRAIN_SETS`) | Every one has been shown to a model, used for prompt or design iteration, or both. v6-v8 were written as sealed held-out sets for *their own* runs; once run they are exposed. **v8 is not a valid unseen holdout** and `memring.require_held_out_eval_set("v8")` refuses it. |
| v9 and later, not in `run.SETS` | `held_out` (`set_split()` default) | Unseen by construction, see *Fresh held-out tasks* below. |

Every task carries a `split` tag. The v0-v8 task modules write `split="train"`; `run.load_set()` sets the set's split
on any task without a tag and **raises** if a task's tag disagrees with its set (a v9 file cannot tag a task `train`,
and v0-v8 can never be `held_out`). `check_tasks.py` checks the tag too, including on `--file` part files (the
`v<S>` id prefix names the set).

### Fresh held-out tasks: where they must come from

- A new `bench/loop/tasks_v9.py` (then v10, ...), written fresh under the same rules as v6-v8 (`check_tasks.py --file`
  clean: seed line, ref timing, ids and entry names unique against v0-v8), each task `split="held_out"` and an
  explicit `family` from `memring.KNOWN_FAMILIES` (retrieval ranks on it; the family is never guessed from text).
- `memring.require_held_out_eval_set` (called by `memory_eval.py`) refuses a set unless every task is tagged
  `held_out`, has an explicit known family, has an id prefixed `<set>_`, and has an id not already in v0-v8. That is a
  name/id check only: it does not detect a reskinned train task under a new id.
- Not added to `run.SETS` (that map is the train list; `load_set()` finds `tasks_v9` by name).
- Committed and pushed in a pre-run commit **before** any model sees any of it. No prompt iteration, no probe on it,
  no use as a few-shot example, and the writer does not consult the lesson export while writing (the tasks must not
  be shaped to the lessons).
- Not derived from v0-v8 tasks (no paraphrase or re-skin of an exposed task).
- One eval spends the set. Afterwards it moves to `run.SETS` / `TRAIN_SETS` and can feed lessons; the next eval needs
  v10.

## 1. Lesson store (`memring.py`, `lessons.db` under the Ring root)

- **Source.** A TRAINING task episode with a graded failure (a coded turn that failed `run.grade`) followed by a later
  attempt **in the same model's trajectory** that passed. Entry points: `agent.py --distill-lessons --memory-root R`
  (per task, live: first coded failure of the task, then the final pass, across episodes), and offline
  `memring.py lessons-distill RESULTS.jsonl [more...] --set vN --model ALIAS --root R --lessons-out L.json`.
  Offline pairing (`memring.trajectories` / `fix_pair`): rows are grouped by (task, model) and ordered by
  (episode, turn) for agent.py rows or by round for one debate.py seat; the pair is the first failure and the first
  later pass of that same trajectory, across episodes. `--model` is required (no default, never `"train"`); an
  agent.py jsonl needs its run summary next to it naming that model; rows of other models/seats are skipped and
  counted; a file whose rows have no episode/turn or seat/round (`run.py` samples, independent seeds) is refused.
  Both rows are re-graded with `agent.fresh_grade` on CPU and the export is not written on any mismatch.
- **Model namespace.** One string everywhere: the served alias (`qwen3-32b`, `r1-distill-qwen-32b`, or whatever
  `run.served_model` returns). `lessons-distill --model`, `agent.py --model` and `debate.py` (the served `alias`, not
  the seat id) all distill and retrieve under it; there is no fallback to another model's lessons.
- **Lesson.** One to two sentences, a pattern / pitfall / technique, never the task's answer or code. v1 uses a
  deterministic distiller (`_distill_deterministic`): the failure's exception type picks the lesson first
  (timeout/recursion -> memoise; IndexError/KeyError/ZeroDivisionError -> empty and boundary cases; ValueError -> validate
  upfront; ...), code-diff features only refine an AssertionError-class failure, and the task family supplies the
  fallback. That is a fixed vocabulary of about ten lessons, and the store dedupes per model on normalised text, so a
  store holds at most about ten lessons per model. Dedupe keeps the first writer's `family` and `fail_exc` for a
  shared sentence. Train tasks with no family label (sets outside the `FAMILIES` map) are stored as `unlabeled`, which
  never earns the same-family bonus. `distill_lesson(..., ask=...)` takes an LLM distiller; no CLI wires
  one in v1, and anything it returns goes through the same leak guards.
- **Verification rule** (`VERIFICATION_RULES = {"fresh_grade_fix_pair"}`): the lesson is admitted only with a verdict
  showing `fail_passed is False` with an exception type, then `passed is True` and `fresh_pass is True` (the fix passes
  the tests with the oracle seed swapped for `agent.FRESH_SEED`; a task without a seed line falls back to `no_fresh`),
  under the current `GRADER_VER`. A stale grader version, a missing failure, a fix that fails the fresh grade, or an
  unknown rule is refused and logged in `lesson_refusals`. v1 does **not** implement "kept only if a later attempt using
  the lesson passed"; that rule is the obvious v2 and would need GPU runs.
- **Provenance** on every row: `task_id`, `task_set`, `split`, `family`, `arm`, `model`, `created_at` (UTC), `fail_exc`,
  `verdict_json` (the verdict above), `grader_ver`, the lesson's `hash`/`nhash`, and an HMAC-SHA256 `seal`
  (`memring.lesson_mac`) under the Ring's `seal.key` over task id, set, split, family, arm, model, `fail_exc`,
  `created_at`, lesson hash, verdict and grader version: every field that reaches the prompt or the ranker. The
  `fail_exc` column must also equal the sealed verdict's `fail_exc`. Rows are append-only (trigger). A row whose text
  or any sealed field was changed fails at retrieval and is skipped.
- **Seal trust model.** The seal gives integrity against accidental edits and edits made without `seal.key`, given
  that the key is trusted and private (mode 0600 under the Ring root). Anyone holding the key can mint a valid seal for
  any content, and the seal does not prove that the verdict's facts were checked: it binds what the writer recorded,
  not that the recording was true. The CPU re-grade at distill time is what checks the verdict.
- **Export.** `export_lessons` writes each lesson's `seal` and the export's `key_id` (first 16 hex of
  sha256(key)). `load_lesson_export(path, key=...)` requires the writer's key (`--lessons-key`, default
  `/data/ring/seal.key`), refuses a `key_id` mismatch, recomputes every seal, and refuses `fail_exc != verdict.fail_exc`.

## 2. Leak guards (`memring.leak_check`, enforced in code)

`leak_check` is a **lexical backstop**, not paraphrase protection. It catches exact ids, slugs with an underscore,
exact 6-word runs and lines, exact reference/test lines, entry-point names and *registered* feedback strings. A
paraphrase, a 6-gram with one word changed, the expected values restated, a single-token slug, or held-out feedback
that was never registered all pass it. v1 relies on it only because the deterministic distiller can emit just the ten
canned sentences (none contains a current v0-v8 entry-point name). An LLM distiller (`ask=`) is not wired to any CLI,
and wiring one would need a stronger guard than this.

Write side (`Ring.admit_lesson`, `distill_and_admit`, `distill_lesson`, `agent.distill_episode_lesson`):
- refuse any provenance that is not `split == "train"` with a set in `TRAIN_SETS`, whose task id is a registered
  held-out id, or whose id looks like v9+ (`v9_..`, `v10_..`);
- refuse lesson text containing: a task id (any `vN_NN_` form), a held-out id or slug, a 6-word run or line of
  held-out prompt text, a line of any registered task's reference solution or tests, an entry-point identifier of any
  registered task, held-out grader feedback (registered via `register_tasks(held_out_feedbacks=...)` or a held-out
  task's `grader_feedback`/`err`), oracle/traceback markers, code lines or fences, instruction-like text
  (`INJECTION_RE`), or more than 600 chars / 6 lines.

Read side: `Ring.retrieve_lessons` and `retrieve_from_export` re-run `leak_check` and the verdict check on every row
against the held-out tasks known *now* (plus the target task if it is held-out), so a lesson admitted before a
held-out set existed is still refused if it collides with it. `load_lesson_export` refuses the whole export file on
any bad row (held-out provenance, leak, stale grader, hash mismatch). A lesson from the target task itself is never
retrieved. `debate.py` also refuses an export holding a lesson from the set being measured.

## 3. Retrieval and `--memory on|off`

- `--memory off` (the default in `run.py`, `agent.py`; `debate.py` default `None` = off) returns the prompt untouched.
  `test_memory_loop.TestMainParity` checks it **byte for byte against main `01c02e2`**: it extracts main's
  `bench/loop/*.py` with `git show`, runs one harness under both trees, and compares every v0-v8 `run.py` task prompt,
  `agent.turn_prompt` in all three branches plus plan mode, a scripted `agent.solve_task` (loop and fix mode, with a
  lesson retriever passed but memory off) and a scripted two-seat `debate.py step` sequence, plus `debate.protocol`.
- `--memory on` prepends one block: `LESSON_HEAD` then `- [family / exc] lesson` lines, then the unchanged prompt.
  No lessons, no block. Top-k (`--memory-k`, default 3) by `score_lesson`: +2 same family (only when the target's
  family is known: the `FAMILIES` map or the task's explicit `family`; unknown earns nothing), +1.5 same exception type as
  the current error (agent turns after a failure), plus 3x token cosine between prompt+error and the lesson; at most
  one lesson per source task; deterministic tie-break by task id, row id.
- Sources: a live `--memory-root` or a frozen `--lessons` export. With `--memory-root`, agent.py snapshots the
  seal-verified lessons of `--model` on the main thread before the task pool starts (sqlite connections are
  thread-bound); per-turn ranking with the turn's error then runs on that snapshot, and lessons distilled later in
  the same run are not retrieved.
  Evals use the frozen export: its sha256 goes into the agent summary (`memory.lessons_sha256`) and the debate meta
  (part of the protocol hash), and rows log `lessons_retrieved`.

## 4. Held-out eval plan (written, not run): `bench/loop/memory_eval.py`

Question: on unseen tasks, does injecting verified training lessons make the K4E4 loop solve more tasks than the same
loop without them, at the same budget?

- **Arms.** `agent.py --memory off` vs `agent.py --memory on --lessons L.json --memory-k 3`, same `--set v9`,
  `--tasks` (all), `--model`, `-k 4 -e 4`, `--task-budget` (default 16 x MAX_TOKENS), `--parallel`, `--api`, same server
  build and model file. Sampling seeds are fixed by (episode, turn) in `agent.episode` (1000 + 10 x episode + turn), so
  both arms ask with identical seeds; the fresh grade uses `FRESH_SEED`. Order: off, then on, in one llmctl session.
- **Lessons.** Distilled from stored v0-v8 single-model agent.py trajectories only (`memring.py lessons-distill
  --model` = the served alias; no debate jsonl, no `run.py` samples, no `ask=` distiller), exported once, committed with
  the prereg; `memory_eval.py` refuses an export with no lesson for `--model` (the on arm would equal the off arm).
- **Pre-registration.** `memory_eval.py check --set v9 --model M --lessons L.json --label P` validates (held-out set,
  every task tagged held-out, export passes the leak guards against the whole v9 set) and writes
  `results/P.prereg.json`: tasks, task-file sha256, lessons sha256, seal key path and `key_id`, grader version, budget,
  arm order, both exact commands, and the read rule text. It does not hash `agent.py`/`memring.py`/`memory_eval.py`:
  a harness edit after `check` is not detected. Commit and push it before any GPU stage. Written once; a new plan needs a new label.
- **Run** (needs AJ's separate yes; preflight first; inside an llmctl session):
  `scripts/llmctl.py run -- python3 bench/loop/memory_eval.py run --label P`. It re-checks every sha256 and the read rule
  against the prereg and refuses on any change, refuses if an arm's results already exist, then runs both arms and
  writes `results/P.report.json`.
- **Read rule** (`READ_RULE`, version `memloop-v1-rule-2`, fixed before any run). Paired per task, solved = the
  agent summary's `per_task.solved` (fresh-seed grade). gains = on solved and off not; losses = the reverse;
  net = gains - losses.
  - INVALID if the arms are not matched (set, tasks, model, k, e, task budget, parallel, api, server build / model
    file), either arm ran fix or plan mode, any row of either arm's jsonl has `seed != 1000 + 10*episode + turn` (or
    the jsonl is missing), the lesson export or task file changed, an arm is incomplete, the off arm carried memory,
    or the on arm injected lessons on 0 rows.
  - The budget is a completion-token cap; the on arm's prompt is longer by the lesson block, and token totals are
    reported, not required equal. Off runs first, so any prefix-cache warmup favours the on arm; report it with the
    token totals. A crashed on arm leaves the off jsonl and the write-once prereg in place, so that label cannot be
    resumed.
  - **KEEP** if net >= max(3, ceil(0.10 x N)) (N = 30 -> 3, the lab's usual line).
  - **DROP** if net <= 0.
  - Otherwise **INCONCLUSIVE**: no keep; only a fresh held-out set (v10) can settle it, never a rerun of v9.
  - The exact two-sided sign test on gains vs losses is reported, not used for the verdict. With N = 30 a net of +3 is
    thin (see `size-runs-by-question`); a keep is a lead for v10, not a settled effect.
- **What would change the plan:** nothing from the run itself. Bars, k and lessons are fixed by the prereg.

## 5. Tests (CPU only)

`python3 bench/loop/test_memory_loop.py -v` (40 tests, about 3 s; `TestMainParity` and the agent episode test need
`bwrap`) plus the module selftests
(`run.py`, `agent.py`, `memring.py`, `debate.py --selftest`). Stub models only; grading goes through `run.grade`'s
sandbox as in every selftest.
