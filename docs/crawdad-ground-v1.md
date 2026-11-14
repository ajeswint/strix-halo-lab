# CRAwDAD Grounding v1: Execution Feedback on v10 (pre-run)

Stated before any GPU session (2026-11-13 CT). For review before running; **no GPU session starts in this commit; the run waits for AJ's separate yes.**

## Context and Question

AJ cancelled CRAwDAD Stage V (memory retrieval on v10). Retrieval never reliably separated from noise: on `v8` (n=30), D scored 9/30 vs DR 12/30 (net +3), but an unretrieved rerun at another seed (`crawdad-v8-d3`) also scored 12/30, with 7/30 tasks discordant between d2 and d3.

This pre-run establishes a new direction: **GROUNDING** the two small coding models (`qwen32` = Qwen3-32B Q4_K_M, `r1d32` = DeepSeek-R1-Distill-Qwen-32B Q4_K_M, the CRAwDAD debate pair) in execution feedback rather than retrieved memory. Documentation lookup is out of scope (puzzle-style algorithmic tasks).

## The Critical Rule: Hidden Tests Never Steer Anything

The hidden grading tests (each task's `tests` string in `tasks_v10.py`, graded at `FRESH_SEED = 104729` exactly as `debate.py report` does) must **NEVER** be shown to the model and **NEVER** used for selection, retries, stopping, or any decision inside the loop.

### Why agent.py Cannot Be Reused

In `tasks_v10.py`, there is no separate visible test suite. Every one of the 90 tasks has a single `tests` string containing:
1. Verbatim prompt "Examples:" asserts;
2. Extra fixed asserts and rejection cases NOT in the prompt (e.g. `for bad in ...:` bounds and type checks);
3. A seeded oracle loop at `random.seed(10000 + NN)`.

While `agent.fresh_tests` swaps the seed line for `FRESH_SEED = 104729`, components (1) and (2) are identical between the visible seed and fresh grade. `agent.py`'s existing loop fed back failures from the full `tests` string at the visible seed, which directly leaked component (2) and the oracle loop structure into model prompts. **`agent.py` violates the rule and is NOT reused.**

### Deterministic Visible Split

Visible tests comprise **ONLY** the examples already written in each task's prompt "Examples:" block: lines of the form `- f(args) == value` and the `- ValueError: call, call, ...` rejection lists (handling `-> ValueError` and `raises ValueError` variants).

Extraction was executed deterministically on CPU from prompt text alone into `bench/loop/tasks_v10_visible.py` (`CHECKS` and `VISIBLE_TESTS`). Every visible check is verified to appear in the prompt text, and every task's reference implementation (`ref`) passes all its visible asserts in the `run.py` bwrap sandbox.

Per-family visible extraction statistics (724 total valid asserts):
- **formats** (23 tasks): 23/23 tasks with >=1 visible assert, 237 total asserts. `no_visible`: none.
- **number_theory** (22 tasks): 22/22 tasks with >=1 visible assert, 223 total asserts. `no_visible`: none.
- **graphs_geometry** (22 tasks): 21/22 tasks with >=1 visible assert, 140 total asserts. `no_visible`: 1 task (`v10_74_minkowski_sum_convex`).
- **simulation_dp** (23 tasks): 23/23 tasks with >=1 visible assert, 124 total asserts. `no_visible`: none.
- **Overall**: 89/90 tasks (98.9%) have visible asserts; 724 total asserts across the suite.

**Tasks with Filtered or Excluded Prompt Checks**:
- `v10_39_uuid_urn` and `v10_66_point_in_convex`: value examples in prompt depend on unbound variables (`b` and `poly`), so they keep only `ValueError` rejection asserts.
- `v10_74_minkowski_sum_convex`: all prompt examples depend on multi-line variable definitions (`poly1 = ...`, `poly2 = ...`). Since variable assignment blocks are not function calls or direct equality checks, it extracts 0 independent visible asserts. It falls back to static checks + model-written tests only, flagged `no_visible`.
- `v10_57_ramanujan_sum`, `v10_76_elevator_scan`, and `v10_81_turing_machine_1d`: excluded prompt example typos in expected return values.

### Enforced in Code

In `bench/loop/ground.py`, the in-loop task dictionary is prepared via `strip_hidden(task)` and contains strictly `id`, `prompt`, and `visible`. Keys `tests` and `ref` do not exist in the in-loop dictionary. A unit test in `bench/loop/test_ground.py` passes tasks wrapped in an exploding dictionary that raises `AssertionError` on any access to `tests` or `ref`; the full loop completes without triggering any hidden access. Hidden grading is an isolated function called strictly post-loop.

## Arms and Protocol

Unit of work: `(task, seat)`, 90 tasks x 2 seats = 180 units. Build, endpoints (`qwen32`, `r1d32`), model files, sampling (`temperature = 0.6`, `top_p = 0.95`, `top_k = 20`), `REASONING_BUDGET = 2048`, and `MAX_TOKENS = 6144` are imported from `debate.py`.

Reply seeds are in the new range **5000–5099**, verified disjoint from `run.py` (0–15), `loop` (1000–1033), `fix` (2000–2033), `plan` (3000–3001), and `debate` (4000–4004, 4100–4104, 4200–4204):
- Turn 0 (Arm P, shared): seed `5000` (`SEED_BASE + 0`)
- Model-written tests (Arm G): seed `5050` (`TEST_SEED`)
- Revision turns 1..K (Arms G and C): seeds `5001`, `5002`, `5003` (`SEED_BASE + turn`)

### Arm Definitions

1. **Shared Turn 0 = Arm P (Plain baseline, unmatched)**:
   - One solo reply per `(task, seat)` generated from `debate.solo_prompt(task)` at seed 5000.
   - Stored once and shared as candidate 0 of Arms G and C, ensuring the paired contrast between G and C does not inherit turn-0 sampling noise.
2. **Arm G (Grounded)**:
   - *Self-written tests*: One separate call per `(task, seat)` seeing ONLY the task prompt (no code) asks for 3–5 edge-case assertions at seed 5050. Test generation is part of Arm G's execution treatment and counts against Arm G's 24,576 completion-token budget. Arm C does not run test generation, reserving its budget for revisions.
   - *Static checks first*: `compile()` syntax check, `run.deny_check()` tripwire, and AST check that entry-point functions specified in prompt are defined. `pyflakes` remains optional and absent on this host; the active static tier on this machine is compile + `deny_check` + AST entry points. Static failures bypass the sandbox.
   - *Test-and-fix loop*: Evaluates candidate against static -> visible -> model tests in `run.py`'s bwrap sandbox (timeout 10 s). Stops early if all pass (`all_pass`). Otherwise feeds back the execution error traceback (truncated via `run._tail`) and asks for a full corrected module using the unified revision instruction. Up to $K=3$ revision turns (seeds 5001–5003). Early stops: `all_pass`, `repeat_code`, `no_code`, `budget`, `max_turns`.
   - *No-code revisions*: When a revision reply has no code block, Arm G records distinct stop reason `no_code` and retains the last non-empty module as its final program (never None).
   - *Primary Scoring & Secondary Best-of-N*: The PRIMARY contrast scores Arm G strictly on its **LAST non-empty module** (matching Arm C). Best-of-N selection across static, visible, and model tests (earliest turn wins ties) is logged and reported as a SECONDARY "package" result (G-best-of-N); no keep/drop verdict is derived from secondary results.
3. **Arm C (Matched control, no execution)**:
   - From shared turn 0, up to $K=3$ self-revision turns at seeds 5001–5003. Receives the identical revision instruction as Arm G ("Review your solution against all requirements and constraints in the specification, and write a corrected complete module."), differing ONLY by the absence of the execution error block.
   - *Matched stop rules*: Same stop rules as G (`repeat_code`, `no_code` preserving last non-empty module, `budget`, `max_turns`). C does not have an `all_pass` stop because it receives no execution feedback.
   - *Primary Scoring*: Scored strictly on its **LAST non-empty module**.
4. **Hard Token Cap**:
   - Per `(task, seat)`, G and C each receive the same completion-token cap $B = 4 \times \text{MAX\_TOKENS} = 24,576$ completion tokens. Before EVERY completion call in both arms (including test-writing in G and turn 0 accounting), if $\text{tokens\_so\_far} + \text{MAX\_TOKENS} > \text{TASK\_BUDGET}$ (24576), the call is skipped (stop reason `budget`). Total completion tokens per arm are guaranteed $\le 24,576$.
5. **Protocol Hash**:
   - `ground_protocol(seed_base=5000)` = **`a7efb2060615`**. Binds all prompt templates, seeds, budgets, check order, selection key, and the sha256 of `tasks_v10_visible.py`.

## Pass Bar

Primary unit: task ($n=90$). A task is solved by an arm if EITHER seat's final code passes the hidden fresh grade (`agent.fresh_grade` at `FRESH_SEED = 104729`, the union score $L_{\text{arm}}$).

Primary contrast: **Arm G vs Arm C**, paired over the 90 tasks with net gain $\text{net} = L_G - L_C$.

The evaluation bar reuses the Stage V partition from `docs/crawdad-v10-noise.md` verbatim in meaning:
- **No-room precondition**: If $L_C \ge 77/90$ (~85%) or $L_C \le 9/90$ (~10%), the task pool is saturated or uninformative; no verdict is rendered (`no_room`).
- **Keep**: $\text{net} \ge T_{\text{noise}}$ (pinned $T = 9$) **AND** exact one-sided paired sign test $p \le 0.05$. Both the noise floor and statistical significance are satisfied.
- **Drop**: $\text{net} \le 0$ **OR** $p > 0.10$.
- **Inconclusive**: $0 < \text{net}$ **AND** $p \le 0.10$ **AND NOT Keep**. Defaults to drop unless AJ approves expansion.

### Partition Table

| Net gain ($\text{net} = L_G - L_C$) | Exact sign test $p \le 0.05$ | Exact sign test $0.05 < p \le 0.10$ | Exact sign test $p > 0.10$ |
| :--- | :--- | :--- | :--- |
| $\text{net} \ge 9$ (pinned $T = 9$) | **Keep** | **Inconclusive** | **Drop** |
| $0 < \text{net} < 9$ | **Inconclusive** | **Inconclusive** | **Drop** |
| $\text{net} \le 0$ | **Drop** | **Drop** | **Drop** |

Worked examples for sign-test boundary ($k = \text{losses}, n_{\text{disc}} = \text{gains} + \text{losses}$):
- 9 gains, 0 losses: $p = 0.0020 \le 0.05$ (Keep)
- 10 gains, 1 loss: $p = 0.0059 \le 0.05$ (Keep)
- 11 gains, 2 losses: $p = 0.0112 \le 0.05$ (Keep)
- 7 gains, 1 loss ($\text{net} = +6 < 9$): $p = 0.0352 \le 0.05$ (Inconclusive)

### Noise Notes

The threshold $T = 9$ was derived from same-seed paired discordance $p_{\text{same}} = 1/7 \approx 0.143$, giving $\sigma_{\text{paired}} = \sqrt{90/7} \approx 3.586$ and $2.5 \times \sigma_{\text{paired}} \approx 8.96 \to 9$.

Stage N cross-seed noise on `v8` is larger: d2 (seed 4000) vs d3 (seed 4100) was discordant on 7/30 tasks (~0.233). If that cross-seed rate applied to $n=90$, $\sigma = \sqrt{90 \times 0.233} \approx 4.58$ and $2.5\sigma \approx 11.5 \to 12$. The shared-turn-0, same-seed paired design between G and C justifies keeping $T = 9$; results will also report whether $\text{net} \ge 12$ as an explicit sensitivity line.

#### Stage N Triad Placeholder (to be filled before run)
Stage N arm `crawdad-v8-d4` (seed base 4200) is currently running. Triad metrics across {d2, d3, d4}:
- Leaf totals: $L_2 = 9/30$, $L_3 = 12/30$, $L_4 = \text{[PLACEHOLDER: awaiting d4 completion]}$
- Pairwise discordant counts: $D_{23} = 7/30$, $D_{24} = \text{[PLACEHOLDER]}$, $D_{34} = \text{[PLACEHOLDER]}$
- Mean discordance $p_{\text{flip}} = \text{[PLACEHOLDER]}$, spread $\Delta_N = \text{[PLACEHOLDER]}$

## Expected GPU Hours

Estimates derived from measured figures in `docs/crawdad-v8.md` and `docs/crawdad-v10-noise.md` (`crawdad-v8-d2`: 4 sessions, 108 replies, decode 24,593 s, giving $24,593\text{ s} / 108 = 227.713\text{ s} \approx 227.7\text{ s}$ per reply; model swap $\approx 1.3$ min per load).

Arithmetic ($n=90$ tasks, 2 seats = 180 units of work):
- **Turn 0 pass rate baseline**: From measured v8 d2 solo pass rate (qwen32 9/30 + r1d32 4/30 = 13/60 $\approx 21.67\%$).
  Units expected to pass turn 0: $180 \times (13/60) = 39$ units.
  Units expected to fail turn 0: $180 \times (47/60) = 141$ units.
- **Turn 0 (Arm P)**: Exactly 180 replies.
  $180 \times 227.7\text{ s} = 40,986\text{ s} =$ **11.39 GPU hours** decode (both expected and worst case).
- **Arm G (Grounded)**:
  - Test-writing: 180 replies (short assertion lists, $\sim 75$ s expected $\implies 180 \times 75\text{ s} = 13,500\text{ s} =$ 3.75 GPU hours; budgeted conservatively up to full reply 227.7 s $\implies 180 \times 227.7\text{ s} = 40,986\text{ s} =$ 11.39 GPU hours).
  - Revisions: up to $3 \times 180 = 540$ revision replies.
    - *Worst case* (all 180 units run 3 revisions): $540 \times 227.7\text{ s} = 122,958\text{ s} =$ 34.16 GPU hours. Total G worst case = **45.54 GPU hours** (with 227.7 s test-write) or **37.91 GPU hours** (with 75 s test-write).
    - *Expected case*: Turn 0 passing units (39 units) pass all checks and stop on `all_pass` with 0 revisions. Turn 0 failing units (141 units) enter revisions. Assuming failing units average 1.4 revisions before stopping (`all_pass`, `repeat_code`, `no_code`, or max turns): $141 \times 1.4 = 197.4$ replies $\times 227.7\text{ s} = 44,948\text{ s} =$ 12.49 GPU hours. Total G expected = **16.24 GPU hours** (with 75 s test-write) or **23.88 GPU hours** (with 227.7 s test-write). *(Assumptions: 1.4 revisions per failing unit; 75 s test generation).*
- **Arm C (Control)**:
  - Shares turn 0. No test-writing call.
  - *Worst case*: $540 \times 227.7\text{ s} =$ **34.16 GPU hours**.
  - *Expected case*: Arm C receives no execution feedback, so all 180 units enter revision turn 1. Assuming units average 1.2 revisions before stopping on `repeat_code`, `no_code`, or max turns: $180 \times 1.2 = 216$ replies $\times 227.7\text{ s} = 49,183\text{ s} \approx$ **13.66 GPU hours**. *(Assumption: 1.2 revisions per unit; if units passing turn 0 repeat code on turn 1, $39 \times 1 + 141 \times 1.2 = 208.2$ replies $\times 227.7\text{ s} = 13.17\text{ h}$).*
- **Total GPU Hours**:
  - **Expected**: P (11.39 h) + G expected (16.24 h) + C expected (13.66 h) $\approx$ **41.29 GPU hours** decode (or 48.93 h with conservative 227.7 s test-write).
  - **Worst Case**: P (11.39 h) + G worst (45.54 h) + C worst (34.16 h) $=$ **91.09 GPU hours** decode (or 83.46 h with 75 s test-write).
  - **Model Swaps**: Exactly 2 sessions total (one per seat; each seat completes P, G, C for all 90 tasks in one session). Swap overhead $= 2 \times 1.3\text{ min} \approx 2.6\text{ minutes}$.

## Procedure and Exact Commands

**No GPU session starts in this commit. The run waits for AJ's separate yes.**

Before each invite, `scripts/preflight.sh` must report `READY` and `llama-deepseek.service` must be inactive.

### Session 1: qwen32 (all 90 tasks for Arm P, G, C)

```bash
scripts/llmctl.py invite qwen32 && { scripts/llmctl.py run -- python3 bench/loop/ground.py step --label crawdad-ground-v1 --set v10; scripts/llmctl.py bye; }
```

Check status between sessions (CPU only, no server):
```bash
python3 bench/loop/ground.py status --label crawdad-ground-v1
```
(Expected last line: `owed {'qwen32': 0, 'r1d32': 270}; next session: invite r1d32` — units are actions: 3 actions per task [turn0, arm_g, arm_c] $\times$ 90 tasks = 270 actions owed per seat)

### Session 2: r1d32 (all 90 tasks for Arm P, G, C)

```bash
scripts/llmctl.py invite r1d32 && { scripts/llmctl.py run -- python3 bench/loop/ground.py step --label crawdad-ground-v1; scripts/llmctl.py bye; }
```

Check final status (CPU only):
```bash
python3 bench/loop/ground.py status --label crawdad-ground-v1
```
(Expected last line: `done: 90/90 tasks complete across all arms (P, G, C)`)

### Reporting and Fresh Grading (CPU only)

```bash
python3 bench/loop/ground.py report --label crawdad-ground-v1 --regrade
```
Outputs `results/crawdad-ground-v1.ground.summary.json` containing union solve rates, G vs C primary sign test, G vs P secondary comparison, token totals, and CPU post-hoc ablations.
