# Memory loop v1: v9 held-out eval protocol (2026-11-07, prep only, no GPU)

Builds on `docs/memory-loop-v1.md` (approved architecture, unchanged here) and spends nothing: no model was loaded, no
llmctl session ran, and neither evaluated model (`qwen3-32b`, `r1-distill-qwen-32b`) has seen any v9 prompt or answer.

**State: dataset frozen, prereg NOT written.** The prereg needs a same-model lesson export, and none can be built from
existing data (section 3). Everything a prereg pins except the export is fixed in
`bench/loop/memeval_v9_freeze.json` (checked by `test_tasks_v9.TestFreeze`).

## 1. Dataset (frozen)

`bench/loop/tasks_v9.py`: 30 tasks, ids `v9_01`-`v9_30`, `split="held_out"`, explicit `family` (formats 8,
number_theory 7, graphs_geometry 7, simulation_dp 8), one `random.seed(9000 + NN)` line each. Not in `run.SETS`;
`run.load_set("v9")` and `memring.require_held_out_eval_set("v9")` accept it. Novelty audit, grader checks and the
"unseen to the evaluated local models in this lab" claim with its limits: `docs/v9-novelty-audit.md`.

| file | sha256 |
|---|---|
| `bench/loop/tasks_v9.py` | `b797ea212824c456cdcf286a00e78c578bc0365a6021931b98179b8979d3b240` |
| `bench/loop/tasks_v9_mutants.py` | `09c948e772a3279aab321a630f29905d78e1e0bd2fee8ece6367d952350c9ce1` |
| `bench/loop/novelty_audit.py` | `e443e816a61e064cd838f04099db87470efcd4d11c9dcf2b8b38ea28e6f212a7` |

Grader `grade-65b662df4ba4`, read rule `memloop-v1-rule-2`. Any edit to these files after this commit is a new
dataset (v10), not a fix to v9, once a model has seen v9; before that, an edit needs a new freeze commit and review.

## 2. Harness changes in this step (flagged for review)

`memory_eval.py` only; the memory architecture (`memring.py`, `agent.py`, `run.py`, `debate.py`) is untouched.
- The prereg now pins `harness_sha256` of `agent.py`, `run.py`, `memring.py`, `memory_eval.py`; `run` refuses if any
  differs (closes the gap `docs/memory-loop-v1.md` section 4 stated: "a harness edit after `check` is not detected").
- The report adds `turns` and `wall_s` per arm next to `tokens` (cost tracking). The verdict logic is unchanged.

## 3. Learning corpus: BLOCKER

The approved path (`docs/memory-loop-v1.md` section 4) distills lessons only from stored v0-v8 **single-model agent.py
trajectories of the served alias** (no debate jsonl, no `run.py` samples, no `ask=` distiller), re-graded on CPU.

Inventory of the 33 tracked result jsonl files (`git ls-files bench/loop/results`), read-only, 2026-11-07:

| source | models | usable for the approved path |
|---|---|---|
| agent.py trajectories (episode/turn + summary model), 22 files | `qwen3.6-35b-a3b` 15, `deepseek-v4-flash` 4, `laguna-xs-2.1` 3 | none: no file for `qwen3-32b` or `r1-distill-qwen-32b` |
| debate.py jsonl (seat/round), 5 files | `qwen3-32b`, `r1-distill-qwen-32b` | excluded by the approved protocol; stored fix pairs (not re-graded): qwen3-32b 5, r1-distill 4 across v7/v8 |

A lesson from another model would violate the per-model namespace (no fallback across models), so **no lesson export
was produced and no lessons were written**. Using the debate fix pairs would change the approved protocol (a debate
round is not the K4E4 loop being evaluated; its fix follows a peer critique); that is a decision for AJ and the
reviewer, not taken here.

**What unblocks it (GPU, train-only, needs AJ's go):** one agent.py K4E4 run per evaluated model on a train set with
the four v9 families, same loop configuration as the eval arms, memory off:

- set `v8` (30 tasks, families from `memring.FAMILIES["v8"]`, exposed and train since 2026-11-07), `-k 4 -e 4`,
  `--task-budget 196608`, `--parallel 4`, server `--ctx 65536 --np 4`, `--model` = the served alias;
- then, on CPU: `agent.py --regrade`, `memring.py lessons-distill --model ALIAS --root /data/ring-memloop-v9
  --lessons-out ...` (fresh ring, its own `seal.key`), commit the exports.
A model whose run yields no verified fix pair has no export; `memory_eval.py check` then refuses it ("no lesson for
model") and that model has no eval. No fallback.

## 4. Pre-registration (written by `memory_eval.py check` once the exports exist)

One prereg per model, labels `memeval-v9-qwen3-32b` and `memeval-v9-r1-distill-qwen-32b`:

| field | value |
|---|---|
| set / tasks | `v9`, all 30 |
| arms | `agent.py --memory off` then `--memory on --lessons L --lessons-key /data/ring-memloop-v9/seal.key --memory-k 3`, one llmctl session per model |
| loop | `-k 4 -e 4`, `--task-budget 196608` (16 x `MAX_TOKENS` 12288), `--parallel 4`, `--api http://127.0.0.1:8081` |
| per turn | `MAX_TOKENS` 12288, `REASONING_BUDGET` 8192, temperature 0.6, top_p 0.95, top_k 20 (run.py constants) |
| seeds | `1000 + 10*episode + turn` in both arms; fresh grade seed 104729 |
| lessons | `bench/loop/results/lessons-v8-qwen3-32b.json` / `lessons-v8-r1-distill-qwen-32b.json` |
| pinned by sha256 | task file, lesson export, harness (`agent.py`, `run.py`, `memring.py`, `memory_eval.py`); grader version and read rule text |
| server | llama.cpp build and model file recorded per arm; `read` marks a mismatch INVALID |

`check` validates: held-out gate, export seals under the key, leak guards against all of v9, at least one lesson for
the model. It writes `results/LABEL.prereg.json` once; both preregs and both exports are committed and pushed before
any eval session.

**Read rule** (unchanged, `memory_eval.READ_RULE`): paired per task on fresh-seed `solved`; net = gains - losses;
KEEP if net >= 3, DROP if net <= 0, else INCONCLUSIVE (settled only by a fresh v10, never a rerun of v9); INVALID on
any mismatch (set, tasks, model, k, e, budget, parallel, api, server build, model file, seeds, export, task file,
harness, incomplete arm, memory in the off arm, 0 rows with lessons in the on arm). Each model is read on its own; no
pooling across models.

**Token / cost tracking.** Each arm summary carries `completion_tokens_total`, `turns_total`, `wall_s` and the GTT peak;
the report copies tokens, turns and wall time per arm. The budget caps completion tokens; the on arm's prompts are
longer by the lesson block (3 lines), which is reported, not capped.

**Uncertainties, stated before any run.**
- Power at N = 30 (exact trinomial, per-task gain and loss probabilities pg, pl):

  | pg, pl | E[net] | P(KEEP) | P(DROP) | P(INCONCLUSIVE) |
  |---|---|---|---|---|
  | 0.05, 0.05 (no effect) | 0 | 0.07 | 0.62 | 0.31 |
  | 0.10, 0.10 (no effect, more churn) | 0 | 0.15 | 0.58 | 0.27 |
  | 0.10, 0.05 | +1.5 | 0.31 | 0.32 | 0.37 |
  | 0.15, 0.05 | +3 | 0.58 | 0.14 | 0.28 |
  | 0.20, 0.05 | +4.5 | 0.78 | 0.06 | 0.16 |

  A null effect still reads KEEP 7-15% of the time per model; two models give two chances. A KEEP is a lead for v10,
  not a settled effect; a DROP does not show the lessons are useless.
- Order and cache: off runs first in the same session. The lesson block is prepended, so on-arm prompts share no prefix
  with off-arm prompts; within an arm, later turns reuse their task's prefix in both arms. With 4 slots batching,
  llama.cpp output is not bit-reproducible for a fixed seed (batch composition changes numerics; R1-Distill was not
  reproducible across request order in crawdad-v7-30), so the arms differ by noise as well as by the block.
- What is tested: prepending at most 3 of about 10 canned, generic sentences selected by family and error type. It is
  not continuous learning and not transfer of task-specific knowledge; a KEEP would show that this prompt prefix helped
  on these 30 tasks, nothing more.
- Lessons come from one train run per model; a different train run could admit different sentences.

## 5. GPU session plan (written, not run; each session needs AJ's go)

Serial on the MAX, one model loaded at a time, never beside DeepSeek (ask AJ to stop it first if it is up). Each
session is one background chain from the repo root: gpu-guard denies `run`, `bye` and `python3` while a model is
resident, so nothing is added mid-session. `scripts/preflight.sh` with the model path runs right before each invite;
NOT READY stops the chain before any load. `bye` sits in the group after a successful invite.

**S1, train run, Qwen3-32B** (writes `bench/loop/results/agent-v8-qwen3-32b-k4e4-np4.{jsonl,summary.json}`):

```
scripts/preflight.sh /data/models/Qwen3-32B-Q4_K_M.gguf && scripts/llmctl.py invite qwen32 --ctx 65536 --np 4 && { scripts/llmctl.py run -- python3 bench/loop/agent.py --set v8 -k 4 -e 4 --task-budget 196608 --parallel 4 --model qwen3-32b --label agent-v8-qwen3-32b-k4e4-np4; scripts/llmctl.py bye; }
```

**S2, train run, R1-Distill-Qwen-32B:**

```
scripts/preflight.sh /data/models/DeepSeek-R1-Distill-Qwen-32B-Q4_K_M.gguf && scripts/llmctl.py invite r1d32 --ctx 65536 --np 4 && { scripts/llmctl.py run -- python3 bench/loop/agent.py --set v8 -k 4 -e 4 --task-budget 196608 --parallel 4 --model r1-distill-qwen-32b --label agent-v8-r1-distill-qwen-32b-k4e4-np4; scripts/llmctl.py bye; }
```

**C1, CPU, no server** (regrade, distill, export, prereg; then commit, push, review):

```
python3 bench/loop/agent.py --regrade bench/loop/results/agent-v8-qwen3-32b-k4e4-np4.jsonl --set v8 > bench/loop/results/agent-v8-qwen3-32b-k4e4-np4.regrade.txt
python3 bench/loop/agent.py --regrade bench/loop/results/agent-v8-r1-distill-qwen-32b-k4e4-np4.jsonl --set v8 > bench/loop/results/agent-v8-r1-distill-qwen-32b-k4e4-np4.regrade.txt
python3 bench/loop/memring.py lessons-distill bench/loop/results/agent-v8-qwen3-32b-k4e4-np4.jsonl --set v8 --model qwen3-32b --root /data/ring-memloop-v9 --lessons-out bench/loop/results/lessons-v8-qwen3-32b.json --out bench/loop/results/lessons-v8-qwen3-32b.distill.json
python3 bench/loop/memring.py lessons-distill bench/loop/results/agent-v8-r1-distill-qwen-32b-k4e4-np4.jsonl --set v8 --model r1-distill-qwen-32b --root /data/ring-memloop-v9 --lessons-out bench/loop/results/lessons-v8-r1-distill-qwen-32b.json --out bench/loop/results/lessons-v8-r1-distill-qwen-32b.distill.json
python3 bench/loop/memory_eval.py check --set v9 --model qwen3-32b --lessons bench/loop/results/lessons-v8-qwen3-32b.json --lessons-key /data/ring-memloop-v9/seal.key --label memeval-v9-qwen3-32b
python3 bench/loop/memory_eval.py check --set v9 --model r1-distill-qwen-32b --lessons bench/loop/results/lessons-v8-r1-distill-qwen-32b.json --lessons-key /data/ring-memloop-v9/seal.key --label memeval-v9-r1-distill-qwen-32b
```

A `lessons-distill` exit 2 (re-grade mismatch) writes no export: stop and report. A `check` refusal: stop for that
model.

**S3, eval, Qwen3-32B** (both arms, off then on; writes `memeval-v9-qwen3-32b-{off,on}.*` and the report):

```
scripts/preflight.sh /data/models/Qwen3-32B-Q4_K_M.gguf && scripts/llmctl.py invite qwen32 --ctx 65536 --np 4 && { scripts/llmctl.py run -- python3 bench/loop/memory_eval.py run --label memeval-v9-qwen3-32b; scripts/llmctl.py bye; }
```

**S4, eval, R1-Distill-Qwen-32B:**

```
scripts/preflight.sh /data/models/DeepSeek-R1-Distill-Qwen-32B-Q4_K_M.gguf && scripts/llmctl.py invite r1d32 --ctx 65536 --np 4 && { scripts/llmctl.py run -- python3 bench/loop/memory_eval.py run --label memeval-v9-r1-distill-qwen-32b; scripts/llmctl.py bye; }
```

**C2, CPU:** `python3 bench/loop/memory_eval.py report --label memeval-v9-qwen3-32b` and the same for
`memeval-v9-r1-distill-qwen-32b`; commit the arm files and reports.

**Status and resume.** Between sessions: `scripts/llmctl.py status`. A train run that dies leaves a jsonl without a
summary; `lessons-distill` refuses it (no summary names the model); rerun under a new label (agent.py overwrites an
existing label's files). An eval arm is never resumed: `memory_eval.py run` refuses when an arm's jsonl exists, so a
crash spends that label and the prereg; a new plan needs a new label and a new review, and v9 stays spent only once a
model has seen it (a crashed off arm has already shown v9 to the model, so a rerun is a v10 question).

**Resources (estimates, not measurements).**
- Memory: registry +26.7 GiB GTT for qwen32 / +26.8 for r1d32 at ctx 32768, np 1 (measured 2026-10-15). At ctx 65536
  the f16 KV cache grows by about 8 GiB (64 layers x 8 KV heads x 128 x 2 x 2 B = 256 KiB per token), so about 35 GiB;
  preflight's file + 16 GiB margin decides. Client cap: llmctl defaults (8G, RLIMIT_AS 16G); grader peak ~0.92 GiB
  per process.
- Throughput: measured 11.1 tok/s per stream for both models (crawdad-v8-d, vk, np 1). Aggregate at np 4 is not
  measured on dense 32B; assumed 17-33 tok/s.
- Tokens per arm: about 320 turns (about 18 unsolved tasks x 16 turns + solved tasks x ~3) x 4-9k tokens =
  1.3-2.9M; hard cap 30 x 196608 = 5.9M.
- Wall time per arm: about 11-47 h (cap: about 96 h at 17 tok/s). S1, S2: one arm each. S3, S4: two arms each.
  Total for S1-S4: about 66-280 GPU hours. S1's first rows give the real aggregate tok/s and tokens per turn; report
  them before S2.
- No silent budget widening: k, e, task budget, per-turn caps, parallel and the task list are fixed above and in the
  prereg. A cheaper plan (fewer train tasks, `-e 2`, smaller per-turn caps) is a new plan with a new freeze and review,
  never a mid-run change.
