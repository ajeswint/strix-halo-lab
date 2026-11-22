# Item 6 Pilot: Real-PR Test Pre-Registration (pre-run)

Stated before any GPU session (2026-11-17 CT). Pre-registered protocol for Roadmap Item 6 pilot.
**No GPU session starts in this commit; the run waits for AJ's separate yes.**

## 1. Context and Question

- **Question**: Does the kept local small-model agentic loop (single Qwen3.6-35B-A3B with execution test feedback, without DeepSeek) produce mergeable, reviewer-approved solutions on real repository pull requests from this repo's history at quality and human-effort levels justifying a full-scale benchmark?
- **Context**: Roadmap Item 6 (`docs/roadmap.md`). Across Roadmap Item 2, Qwen3.6-35B-A3B agentic loops achieved 24/30 to 29/30 on synthetic coding puzzles with hard test feedback (`bench/loop/agent.py`). However, synthetic puzzles do not test repo-wide awareness, multi-file edits, git workflows, or documentation/rules maintenance. The gap between synthetic tasks and real work is the largest unknown.
- **DeepSeek Status**: NO DeepSeek arm. AJ explicitly dropped DeepSeek for Item 6 pilot (2026-11-17); the local arm is strictly the single-model Qwen3.6-35B-A3B loop.

## 2. Baseline

The baseline is the existing cloud seats' outcome on the identical batch of real PRs from this repository's history, as recorded on GitHub:
- **Cloud Seats**: Google Antigravity (Gemini 3.8 Flash / Gemini 4 Argon, reasoning effort high) as code-writer; Grok 4.7 high as adversarial-reviewer.
- **Batch Outcome on the 7 Selected PRs** (PRs #6, #8, #13, #14, #15, #16, #20):
  - **First-Pass Approval Rate**: 3/7 (42.9%) (PR #6, PR #8, PR #14 approved on first pass; PR #13, #15, #16, #20 received `REQUEST-CHANGES` or nit iterations).
  - **Final Approval Rate**: 7/7 (100.0%) merged to `main` within $\le 2$ review rounds.
  - **Human Hand-Fix Amount**: 0 lines of code hand-fixed by AJ to make the PR mergeable (clean automation).
  - **Review Rounds**: Average 1.86 rounds per PR (range 1–3).

## 3. Local Model and Serving Configuration

- **Model**: `Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf` (22.4 GiB GTT), served via `scripts/llmctl.py invite qwen --ctx 65536 --np 2`.
- **Backend**: Vulkan `build-vk` on AMD Radeon 8060S gfx1151 (Strix Halo unified memory, 108 GiB GTT).
- **Concurrency**: `--ctx 65536 --np 2` (2 parallel slots x 32,768 context per slot), verified by timing probe (PR #18, 46.5% step wall reduction) and quality check (PR #19, PASS).
- **Sampling Parameters**:
  - `temperature`: 0.6
  - `top_p`: 0.95
  - `top_k`: 20
  - `REASONING_BUDGET`: 4096 tokens
  - `MAX_TOKENS`: 8192 tokens per completion
  - `TASK_BUDGET`: 32,768 completion tokens per task
- **Agentic Loop**: Single-model loop with test feedback (`bench/loop/pilot_pr.py`, lineage of `bench/loop/agent.py`):
  - Up to $K = 4$ turns per task.
  - Turn 0: Task prompt with repository instructions, target files, task requirements, and test commands.
  - Turns 1..$K$: On test failure, test traceback/error output is fed back. Model produces corrected files.
  - Early stop conditions:
    - `pass`: all automated checks/tests pass.
    - `repeat_code`: model resubmits identical code/diff hash already tried.
    - `repeat_error`: test failure output is identical to previous turn.
    - `budget`: accumulated completion tokens exceed `TASK_BUDGET`.
    - `max_turns`: reached $K=4$ turns.

## 4. PR Selection Rule (Mechanical, fixed before the run)

The pilot batch must be selected mechanically from repository history before running any model (`tasks_item6.enumerate_and_filter_prs()`). The selection filter is:
1. **Repository & History**: First-parent merge commits on `main` up to commit `dbf6a2cb442188dd8ad41811f548541130ae6320` (PR #20) matching `Merge (pull request|PR) #<N>`.
2. **Date Range**: Merge commit timestamp (`%cI` converted to UTC) between `2026-11-06T00:00:00Z` and `2026-11-18T05:00:00Z` (15 merged PRs: #4, #5, #6, #7, #8, #9, #10, #13, #14, #15, #16, #17, #18, #19, #20).
3. **Mechanical Exclusions**:
   - **Pre-Antigravity dual-Claude seat setup / soft-nit chase**: Exclude PRs where `docs/antigravity-writer.md` does not yet exist in the merged commit (`! git cat-file -e <merged>:docs/antigravity-writer.md`) AND `tools/lab-seats/launch.sh` is among the modified files. This mechanically excludes **PR #4** (merged `2026-11-06T04:24:14Z`, which bootstrapped the retired dual-Claude Sonnet writer/reviewer seats) and **PR #5** (merged `2026-11-06T05:00:59Z`, soft-nit chase on PR #4's dual-Claude seat docs), while retaining PR #6 (parser fix, does not touch `launch.sh`) and PR #8 (creates `docs/antigravity-writer.md` and establishes the standing Antigravity writer seat).
   - **GPU benchmark run result check-ins**: Exclude PRs where $> 50\%$ of modified files are under `bench/loop/results/` or `bench/loop/runs/`. This mechanically excludes **PR #17** (54/54 files), **PR #18** (11/11 files), and **PR #19** (15/15 files).
   - **Single-file `README.md`-only note/nit updates**: Exclude PRs whose modified file list is strictly `["README.md"]`. This mechanically excludes **PR #7** (+4/-4), **PR #9** (+63/-1), and **PR #10** (+8/-5).
4. **Batch Size**: Exactly $N = 7$ pull requests meet all criteria: **PRs #6, #8, #13, #14, #15, #16, #20**. Verified by CPU test `test_mechanical_pr_selection_rule` in `bench/loop/test_pilot_pr.py`.

### Fixed Batch Specification

| Task ID | PR # | Title | Base Commit | Testable? (`has_tests`) | Test / Check Command (`test_cmd`) | Target Files |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `item6_pr06` | #6 | debate.py: recover VERDICT/CONFIDENCE inside closing code fence | `7a9f1d75c39f29d05ed92ce0671bb625ff143981` | Yes | `python3 bench/loop/debate.py --selftest` | `bench/loop/debate.py`, `README.md` |
| `item6_pr08` | #8 | Seats: writer is Google Antigravity (Gemini 4 Argon, effort high) | `3ab57123b11fdd945f411bbd992fec08262c6ac8` | Yes | `bash tools/lab-seats/test.sh` | `tools/lab-seats/*`, `AGENTS.md`, `CLAUDE.md`, docs |
| `item6_pr13` | #13 | CRAwDAD noise floor + v10 retrieval retest (pre-run, no GPU) | `01c02e2b1527cb902a4a2728bd7d3aa92c68b3f2` | Yes | `python3 -m unittest bench/loop/test_tasks_v10.py && python3 bench/loop/tasks_v10.py` | `bench/loop/tasks_v10.py`, `test_tasks_v10.py`, docs |
| `item6_pr14` | #14 | README split (move-only) to cut agent token burn | `74d35557c15931850945bf519426d6aaa55af41b` | Yes | Move-only file existence check (`docs/*.md`) | `README.md`, `docs/*`, `CLAUDE.md` |
| `item6_pr15` | #15 | Stale-line fixes + writer roster update | `af2b1a5c4ca765fd411f9e9f9d48c2d099420722` | No | `""` (empty; `run_tests` is not run) | `.claude/agents/*`, `docs/*`, `scripts/preflight.sh` |
| `item6_pr16` | #16 | crawdad-ground-v1: pre-run spec + grounded test-and-fix loop on v10 | `6c56cc09eaafb2376422e73515b39f8193893740` | Yes | `python3 -m unittest bench/loop/test_ground.py && python3 bench/loop/ground.py --selftest` | `bench/loop/ground.py`, `test_ground.py`, docs |
| `item6_pr20` | #20 | Launcher guard: prereg must be committed and pushed before launch | `2bf58003ed4c138b20d0063dd5eab1bd4ddae637` | Yes | `bash scripts/test-prereg-guard.sh` | `scripts/prereg-guard.sh`, `test-prereg-guard.sh`, launcher |

- **Testable Tasks**: 6 of 7 tasks (85.7%) have automated, deterministic CPU test suites (`has_tests = true`).
- **Non-testable Tasks**: 1 of 7 tasks (14.3%) is documentation/config maintenance (`has_tests = false`, `test_cmd = ""`; `run_tests` is skipped and the loop completes after applying the Turn 0 edit).

## 5. Task Formulation & Information Isolation

To prevent leakage and ensure clean measurement:
1. **Standalone Scratch Repository (`create_isolated_scratch_repo`)**:
   - Each PR task is evaluated in a fresh, standalone directory populated strictly from `base_commit` via `git archive --format=tar <base_commit> | tar -x`, followed by `git init` and a single base commit.
   - It does **not** use `git worktree add`, does not share the main repository's `.git` object store, and writes nothing into `.git/worktrees`. Consequently, `merged_commit` and all later history do not exist in the scratch repo's object store (`git show <merged_commit>` fails), preventing any in-loop script from reading the merged answer.
   - All file edits and unified patches applied by `apply_updates` are strictly path-confined to the scratch root (`resolve_confined_path`, `validate_patch_paths`), rejecting absolute paths, `..` traversal, `.git` modifications, and symlink escapes (including mode `120000` patches).
2. **Task Prompt Input**:
   - Repository background and working rules (no GPU load, stage named paths, measured numbers).
   - Task requirements extracted from original PR issue / title / instructions.
   - List of expected files to edit or add, plus their base contents at `base_commit` (with the literal fresh-grading seed `104729` redacted to `<REDACTED_SEED>`).
   - Verification commands to run (only when `has_tests = true`).
3. **Hidden Information Isolation (Leak Prevention)**:
   - The merged diff (`hidden_diff`), commit log after `base_commit`, merge commit SHA (`merged_commit`), and literal grading seed `104729` are strictly held out from prompts.
   - Task definitions strip hidden fields (`strip_hidden(task)`) before passing to the loop runner.
   - A prompt leak tripwire (`check_prompt_leak(prompt, task)`) runs on **every** prompt right before it is sent to the model inside `run_task_loop`, raising `AssertionError` if any hidden field, sentinel, or literal `104729` appears.
   - An exploding dictionary tripwire test (`bench/loop/test_pilot_pr.py`) enforces that accessing `hidden_diff` or `merged_commit` during prompt construction or in-loop execution immediately raises `AssertionError`.
   - Hidden diffs and `merged_commit` test files are read solely by the post-loop offline `grade` subcommand.

## 6. Output Evaluation & Review Gate

The output of the local loop is judged through the standing repository quality gate:
1. **Worktree Diff Capture (Uncommitted & New Files Included)**:
   - At the end of each task's loop (before removing the standalone scratch directory), the runner marks any untracked new files with intent-to-add (`git add -N .`) and records `git diff` against the base commit.
   - The per-PR diff is saved to `bench/loop/results/<label>.diffs/<task_id>.diff` and stored in `bench/loop/results/<label>.jsonl`.
2. **Tier 1: Automated Test Gate & Anti-Self-Grading (`regrade_task_diff`, `_run_harness_grade_spec`)**:
   - **In-loop feedback vs. authoritative graded tests**: Inside the loop (`pilot_pr.py run`), `test_cmd` runs whatever test files exist in the task's scratch tree at `base_commit` (plus the model's in-loop edits) purely to give execution feedback. However, the loop's own `passed` flag and bare exit code `0` are **not** trusted for scoring, because a model could modify a test file or insert `sys.exit(0)` / `os._exit(0)` at module import time.
   - **Authoritative graded tests & isolated Python/bwrap sandbox**: During both in-loop `run_tests` and offline grading (`pilot_pr.py grade`), every model-touching subprocess executes inside an outer `/usr/bin/bwrap` (bubblewrap) namespace sandbox (`build_outer_bwrap_cmd`).
     - **Outer `/usr/bin/bwrap` sandbox layout**: Always invokes the installed `/usr/bin/bwrap` directly (never copies the binary) so the host AppArmor profile stays attached. Read-only binds `/usr`, `/bin`, `/lib`, `/lib64`, `/etc`; mounts fresh `--dev /dev` and `--proc /proc` with `--unshare-user`, `--unshare-pid`, `--unshare-net`, `--unshare-ipc`, `--unshare-uts`, `--die-with-parent`, and `--clearenv`; mounts fresh `--tmpfs` over `/tmp`, `/home`, and `/data`; and writable-binds the task's standalone scratch tree (at `/work`, `--chdir /work`), its fresh per-task `HOME` (at `/home/pilot`), and its fresh per-task `TMPDIR` (at `/tmp`).
     - **Host-side trusted grader & read-only test file mounts**: The trusted grader runs entirely on the host side, outside the sandbox, and never imports or runs anything from the scratch tree. It decides only from the sandbox's exit code and output plus its own count of tests run. No token, no grade script, and no grader process live inside the sandbox. During `grade`, restored `merged_commit` test files (`test_files`) are mounted read-only via `--ro-bind` over `/work` after the candidate's edits are applied, making test ground truth immutable and immune to deletion.
     - **Inner `bwrap` wrapper & unexercised `run.py` properties**: Under Ubuntu AppArmor (`kernel.apparmor_restrict_unprivileged_userns = 1`), `/usr/bin/bwrap` transitions children into `bwrap//&unpriv_bwrap` (`CapEff=0`, `NoNewPrivs=1`), which prohibits nested `unshare(CLONE_NEWNS | CLONE_NEWPID)` without privileges. The inner wrapper `/pilot_shim/bwrap` validates that outer sandbox isolation is active (`/pilot_shim` exists), checks that standard paths (`/usr`, `/proc`, `/dev`, `/tmp`) and bind sources exist, maps `--chdir` to candidate scratch directories, applies environment changes, and execs the payload, failing closed (`exit 1`) on any missing path.
       Because a second nested user/mount namespace cannot be created without privileges, the following `run.py` isolation properties are **not exercised** under the inner wrapper for PRs #6, #13, and #16:
       1. *Nested Mount Namespace*: `run.py`'s requested `--tmpfs /tmp` / private mount layout is not created; `/work` remains visible from the outer sandbox mount table (protected against writes on test files by read-only bind mounts).
       2. *Nested PID Namespace*: `run.py`'s requested `--unshare-all` does not spawn a new nested PID namespace; child processes share the outer sandbox PID namespace (which already isolates against host processes).
       3. *Nested Network Namespace*: `run.py`'s `--unshare-all` network isolation relies on the outer sandbox's existing `--unshare-net`.
       4. *Inner `--die-with-parent`*: `run.py`'s requested `--die-with-parent` is not applied by the inner wrapper (the outer sandbox still enforces `--die-with-parent` at the sandbox boundary).
       (Note that `RLIMIT_AS` 1 GiB address-space limit via `preexec_fn=_limits` in `run.py` remains active).
     - **Python isolated mode (`python3 -I -B`)**: Inside the sandbox, every Python process runs with `-I -B` (no user-site directory, no `PYTHON*` env vars, no automatic cwd on `sys.path`), fresh empty `HOME` and `TMPDIR` recreated empty before `grade`, and fixed `PATH="/pilot_shim:/usr/local/bin:/usr/bin:/bin"`.
   - **Accepted Limits**:
     - Code under test runs in the same process as the tests that import it, so it can forge test results or read files those tests import (for example `tasks_v10_mutants.py` for #13). The test-pass leg of KEEP therefore rests on the blind per-task Grok tamper review (`tamper: true` = FAIL), not on the harness alone. Make no other change to the KEEP/DROP bars.
   - For tasks with `has_tests = false` (`item6_pr15`): `test_cmd` is `""` and `run_tests` is not executed; evaluation relies on Tier 2 and Tier 3.
3. **Tier 2: Offline Adversarial Reviewer & Hand-Fix Gate (Grok 4.7 high, outside the GPU run)**:
   - After the GPU session ends (`scripts/llmctl.py bye`), the per-PR diffs in `bench/loop/results/<label>.diffs/<task_id>.diff` are reviewed offline by the standing `adversarial-reviewer` seat (Grok 4.7 high, `.claude/agents/adversarial-reviewer.md`).
   - **Blind Review Protocol & Fresh Per-Task Session**: Each task's Tier 2 review uses a **fresh Grok 4.7 context/session** given **only** the items listed here: the task prompt (`prompt`, `title`, target `files`), the Automated Test Gate result from Tier 1, and the model's candidate diff (`<label>.diffs/<task_id>.diff`), **without seeing the merged PR or `hidden_diff`**. Each review record in `<label>.reviews.json` states that it used a fresh session (`"fresh_session": true`).
   - **Known Limit (GitHub Reachability)**: In its runtime environment, the reviewer seat may have tool/network ability to look up the repository or merged PRs on GitHub (notably PR #20, which the same reviewer seat reviewed earlier); the orchestrator explicitly instructs the reviewer not to look up or access GitHub, git history, or any external context beyond the provided prompt and diff.
   - **Tampering Fails Both the Test Bar and Review (`"tamper": true/false`)**: The Tier 2 blind Grok review checks for any tampering with the test runner, `unittest`, `builtins`, `exec`, `sys.stdout`, `atexit`, stack frame inspection (`sys._getframe`, `inspect`), or `/proc` in a candidate diff. Every review record in `<label>.reviews.json` includes a required boolean `"tamper": true` or `"tamper": false`. If `"tamper": true`, `pilot_pr.py grade` counts that task's test result as **FAIL** (`test_passed = False`, excluded from `testable_passed`) in addition to non-approval (`approved = False`).
   - **Reviewer Outputs**: The reviewer outputs for each task:
     1. `verdict`: `APPROVE`, `APPROVE-WITH-NITS`, or `REQUEST-CHANGES` (where `APPROVE` and `APPROVE-WITH-NITS` count as approved only when `tamper` is `false`).
     2. `hand_fix_lines` (integer, required): the number of lines (added + deleted/changed) that would need to be changed by hand to make the candidate diff acceptable to merge.
     3. `tamper` (boolean, required): `true` if any test-runner/harness tampering is present in the diff, else `false`.
     4. `fresh_session` (boolean): `true`, recording that the review ran in a fresh context containing only the blind inputs.
   - **Verbatim Storage**: The reviewer's outputs are stored verbatim in `bench/loop/results/<label>.reviews.json` (keyed by `task_id` with `verdict`, `hand_fix_lines`, `tamper`, `fresh_session`, and raw `review_text`); the orchestrator / harness never edits or filters them.
   - **No Review-Repair Turn**: There is no post-review repair turn on the local model in the pilot. The model's final diff from the $K \le 4$ test-feedback loop is the single diff judged by the reviewer.
4. **Tier 3: Offline Grading & Keep/Drop Computation (`pilot_pr.py grade`)**:
   - After the GPU run ends (`scripts/llmctl.py bye`) and `<label>.reviews.json` is written, `python3 bench/loop/pilot_pr.py grade --label <label> [--reviews-file <path>]` re-runs the authoritative `merged_commit` tests on a clean tree per testable PR ($S_{\text{test}} / N_{\text{test}}$), computes diff overlap against `hidden_diff`, reads `<label>.reviews.json` to compute the reviewer approval rate ($A / N$) and average hand-fix lines per approved PR, and outputs the pre-registered keep/drop verdict (`KEEP`, `DROP`, `INCONCLUSIVE`, or `PENDING_REVIEW` if `<label>.reviews.json` is not yet present) to `bench/loop/results/<label>.grade.json`.

## 7. Metrics

1. **Authoritative Test Pass Rate ($S_{\text{test}} / N_{\text{test}}$)**:
   - Fraction of testable tasks ($N_{\text{test}} = 6$) passing the authoritative `merged_commit` test suite in `pilot_pr.py grade` (with model edits to test files ignored).
2. **Reviewer Approve Rate ($A / N$)**:
   - Fraction of tasks ($N = 7$) receiving `APPROVE` or `APPROVE-WITH-NITS` from the blind Grok 4.7 `adversarial-reviewer` pass on the loop's final diff.
3. **Accepted-Findings Rate**:
   - Ratio of valid reviewer findings to total reviewer findings across the 7 diffs.
4. **Wall Time per PR**:
   - Generation seconds, prompt evaluation seconds, test execution seconds, and clock wall time.
5. **Hand-Fix Line Count (`hand_fix_lines`)**:
   - Number of lines the Grok 4.7 reviewer reports would need to be changed by hand to make an approved diff acceptable (averaged across approved PRs).

## 8. GPU Time and Resource Estimate

- **Hardware**: Framework Desktop, Ryzen AI Max+ 395, Radeon 8060S gfx1151 (108 GiB GTT).
- **Memory Footprint & Preflight**:
  - `Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf` file size is 20.8 GiB (`scripts/llmctl.py` records `gtt_need = 22.4` GiB delta from the 4-slot `--ctx 65536 --np 4` measurement: 28.2 GiB total over 5.8 GiB baseline).
  - The launcher (`bench/loop/runs/item6-pilot/run.sh`) invokes `bash scripts/preflight.sh /data/models/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf`, which enforces `llama-deepseek=inactive`, `gtt_used <= 16.0 GiB`, and both `MemAvailable` and `gtt_free >= 36.8 GiB` (20.8 GiB model + 16.0 GiB KV/buffer margin, which comfortably covers the `--ctx 65536 --np 2` KV cache). Because `llmctl.py` stores a single `gtt_need` figure (22.4 GiB at `--np 4`) rather than a separate 2-slot entry, `preflight.sh` and `llmctl invite qwen --ctx 65536 --np 2` will log the measured GTT delta at load time without modifying `llmctl.py`'s serving code. *(Amended 2026-11-20, Section 11: `scripts/llmctl.py` was subsequently updated to set `Endpoint("qwen").ctx = 65536` and record measured `--ctx 65536 --np 2` GTT deltas via `gtt_by_ctx_np` / `expected_gtt`.)*
- **Model Speed**:
  - Generation speed: ~35 tokens/s.
  - Prompt processing: ~500 tokens/s.
- **Turn Breakdown**:
  - Prompt eval: ~4,000–8,000 prompt tokens / 500 tok/s $\approx$ 12 s.
  - Generation: ~2,000 completion tokens / 35 tok/s $\approx$ 57 s.
  - CPU test execution: ~5–15 s.
  - Total per turn $\approx 80$ s.
- **Expected Workload**:
  - Expected turns per PR: ~2.5 turns (average 200 s).
  - Expected GPU time for 7 PRs: $7 \times 200 \text{ s} \approx 1,400 \text{ s} \approx 23.3 \text{ minutes} \approx \mathbf{0.39\text{ GPU-hours}}$.
- **Worst-Case Ceiling & Hard Cutoff (`CEILING_SECONDS=4320`)**:
  - Max $K=4$ turns per task (no post-review repair turn).
  - Worst-case GPU time for 7 PRs: $7 \times 4 \times 80 \text{ s} \approx 2,240 \text{ s} \approx 37.3 \text{ minutes} \approx \mathbf{0.62\text{ GPU-hours}}$.
  - Conservative ceiling: $< \mathbf{1.2\text{ GPU-hours}}$ ($4,320\text{ s}$).
  - **Ceiling Enforcement in `run.sh`**: `bench/loop/runs/item6-pilot/run.sh` tracks elapsed GPU session wall time against `CEILING_SECONDS=4320` ($1.2\text{ h}$) and wraps each task step in `timeout --kill-after=30 <remaining_seconds>`. If the GPU run reaches the $1.2\text{ h}$ ceiling, `run.sh` stops the run immediately, ends the model session via its `EXIT` trap (`scripts/llmctl.py bye`), records `incomplete ceiling_exceeded ...` in `run.status`, logs the ceiling abort in `run.log`, and exits non-zero (`124`).

## 9. Keep / Drop Bars (Worth Scaling to Full Test)

The pilot's purpose is to decide whether local agentic loops on real PRs justify scaling to a larger, full-scale test (e.g. 20–30 PRs).

### Decision Partition

| Outcome | Criteria | Decision |
| :--- | :--- | :--- |
| **KEEP** (Scale to Full Test) | - Test Pass Rate on testable PRs $\ge 3/6$ ($50.0\%$); **AND**<br>- Reviewer Approval $\ge 3/7$ ($42.9\%$); **AND**<br>- Average Grok reviewer `hand_fix_lines` $\le 20$ lines per approved PR. | Scale to full Roadmap Item 6 test. Local small model is viable for real repo tasks with execution feedback. |
| **DROP** (Do Not Scale) | - Test Pass Rate on testable PRs $< 2/6$ ($< 33.3\%$); **OR**<br>- Reviewer Approval $< 2/7$ ($< 28.6\%$). | Drop real-PR test line. The small model cannot generalize from synthetic puzzles to repo engineering. |
| **INCONCLUSIVE** | Intermediate result (e.g. exactly 2/6 test passes or 2/7 approvals, or average `hand_fix_lines` $> 20$). | Defaults to **DROP** per `measure` skill, unless AJ explicitly approves a bounded extension. |

### Worked Examples
- 4/6 tests pass, 4/7 approved, 0 reviewer `hand_fix_lines` $\rightarrow$ **KEEP**
- 3/6 tests pass, 3/7 approved, 15 reviewer `hand_fix_lines` $\rightarrow$ **KEEP**
- 1/6 tests pass, 2/7 approved $\rightarrow$ **DROP** (fails test pass threshold)
- 3/6 tests pass, 1/7 approved $\rightarrow$ **DROP** (fails reviewer threshold)
- 2/6 tests pass, 2/7 approved $\rightarrow$ **INCONCLUSIVE** (defaults to DROP)

## 10. Amendment, Nov 18 2026, after partial results

- **Timing & Context**: This amendment was recorded after 4 of 7 task records were written (`item6_pr06`, `item6_pr08`, `item6_pr13`, `item6_pr14`), all with loop `passed=False` (`stop_reason`: `repeat_error`, `max_turns`, `repeat_error`, `repeat_error`).
- **Prompt Size Observation**: The per-turn prompt estimate of 4,000–8,000 tokens (Section 8, line 150) was badly off: on `item6_pr15`, the first turn request reached 38,364 tokens, exceeding llama-server's per-slot context size of 32,768 tokens (`--ctx 65536 --np 2`), triggering an HTTP 400 error (`request (38364 tokens) exceeds the available context size (32768 tokens)`).
- **Stop Reasons**: Added stop reasons `context_overflow` (for context-size overflow errors) and `request_error` (for other HTTP request failures), meaning the task failed with no diff (`final_diff = ""`).
- **Empty Diff & Review Gate**: A task with an empty diff (including `context_overflow`, and `item6_pr13`'s empty diff) is an automatic non-approval with no Grok review. In offline grading (`pilot_pr.py grade`), `hand_fix_lines` is n/a (`None`) and excluded from the hand-fix average. The same rule applies if `item6_pr16` or `item6_pr20` overflow.
- **Run Provenance**:
  - Run 1 (tasks pr06, pr08, pr13, pr14) was executed at commit `86cbbe8` and ran for 1,669 s before the uncaught exception on pr15 aborted the run. Those four run-1 records came from pre-change code and are frozen unmodified.
  - The resume run will execute at this PR's merge head with `RESUME=1` and `CEILING_SECONDS=2651` (4,320 s - 1,669 s), so the total pilot GPU time remains strictly under 1.2 GPU-hours (4,320 s).
- **Bars & Invariants**: No change to the KEEP/DROP bars (Section 9), mechanical task selection (Section 4), or grading.

## 11. Amendment, Nov 20 2026: Item 6 Pilot v2 (Harness Confound Fix, Pre-Run)

Stated before any v2 GPU session (2026-11-20 CT). **No GPU session starts in this commit.** AJ's go-ahead is on the record (AJ, 2026-11-20 2:41 PM CST): *"continue with the harness fix and rerun the pilot."*

- **Freeze of v1 Results & Exact Editorial Changes to v1 Write-Up**:
  - All v1 result data artifacts under `bench/loop/results/item6-pilot.*` (`item6-pilot.jsonl`, `item6-pilot.diffs/`, `item6-pilot.reviews.json`, `item6-pilot.grade.json`, `item6-pilot.run1/`, `item6-pilot.tier2/`) stay strictly frozen and byte-identical (official verdict **DROP**, 0/6 tests, 0/7 approvals, merged in PR #23 at `82330b6`). v2 never overwrites any v1 artifact; `bench/loop/runs/item6-pilot/run.sh` defaults to `LABEL=item6-pilot-v2` and explicitly refuses `LABEL=item6-pilot`.
  - `docs/item6-pilot-results.md` received three editorial nit fixes from PR #23: (1) replacing the four `file:///tmp/wt-item6-results/...` links with repo-relative `../bench/...` paths, (2) correcting Attempt 1 wording so `item6_pr14` is recorded as exiting `rc=126` (`/usr/bin/timeout: Argument list too long`) rather than exit 1, and (3) noting that the v2 grader emits `null` for zero-approved hand-fix averages while the frozen v1 `item6-pilot.grade.json` retains `0.0`. All v1 DROP numbers, counts, and verdicts in `docs/item6-pilot-results.md` are byte-identical to PR #23.
- **Development-Set Caveat (Re-Test on the Same 7 PRs)**: v2 reruns the exact same 7 PRs whose v1 failures shaped these harness fixes, so it is a re-test on a development set rather than an unseen evaluation set. A v2 **KEEP** only licenses scaling to a full benchmark on unseen PRs (as Section 9's KEEP definition already states); it is **not** evidence of general fitness, and the v2 post-run write-up must repeat this caveat.
- **New Run Label**: `item6-pilot-v2` (outputs written to `bench/loop/results/item6-pilot-v2.{jsonl,diffs/,reviews.json,grade.json}` and logs to `/tmp/lab-seats/item6-pilot-v2/`).
- **Motivation (Confounded v1 Harness Failures)**: v1 results were confounded by two harness-level defects:
  1. Serving `Qwen3.6-35B-A3B` with `--ctx 65536 --np 2` gave only 32,768 tokens per slot, causing `item6_pr15`'s Turn-0 prompt (38,364 tokens after dumping 19 base files) to overflow with HTTP 400 and abort run 1.
  2. Requiring raw unified diffs or full-file markdown blocks led to repeated patch-apply failures, empty diffs (`item6_pr13`), and destructive whole-file rewrites (718–1,909 diff lines on `item6_pr06`, `item6_pr08`, `item6_pr14`).
- **Exact Harness Changes for v2**:
  1. **1-Slot 64k Serving**: Serve `Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf` with `scripts/llmctl.py invite qwen --ctx 65536 --np 1` (1 parallel slot $\times$ 65,536 context tokens per slot; `scripts/llmctl.py` `Endpoint("qwen")` default `ctx = 65536` and `gtt_by_ctx_np` / `expected_gtt` entries for measured `--ctx 65536 --np 2` shapes; launcher `check_props` verifies `total_slots 1 n_ctx 65536`). Memory footprint uses the same 65,536-token total KV pool (measured +22.3 GiB at `--ctx 65536 --np 2` in v1 run 1, +22.4 GiB at `--ctx 65536 --np 4`; `preflight.sh` checks 20.8 GiB model + 16.0 GiB margin = 36.8 GiB).
  2. **Prompt-Size Preflight & Per-Task Fault Isolation**: Before every model request, `pilot_pr.py` measures prompt tokens via `POST /tokenize` on the served endpoint (falling back to a conservative `ceil(chars / 3.0) + framing` estimator when `/tokenize` is unavailable, calibrated against the measured 3.191 chars/token on v1 `item6_pr15`). If `prompt_tokens > slot_ctx - RESERVED_OUTPUT_TOKENS` (`65,536 - 8,192 = 57,344` tokens), the request is not sent and the task is recorded cleanly as `stop_reason = "context_overflow"` with `final_diff = ""`. HTTP 400 context-overflow handling remains as defense-in-depth, and `run_subcommand` isolates unexpected per-task errors so one task's failure never aborts the remaining tasks.
  3. **Structured Edit Tools & Truncation/Stub Guard**: Turn 0 sends a compact target-file manifest (paths + line counts, not full file dumps) and exposes harness-applied JSON tool operations inside ```` ```json ```` / ```` ```tool ```` blocks:
     - `list_files(path, glob)`: lists confined files under `worktree_dir` (skipping `.git` and symlinks, capped at 200 entries).
     - `grep(pattern, path, max_matches)`: searches confined text files (skipping `.git`/binary/symlinks, redacting `104729`, capped at 50 matches).
     - `read_file(path, start, end)`: reads confined 1-indexed line windows (capped at 250 lines per call, redacting `104729`).
     - `search_replace(path, old, new)`: exact-unique-match replacement on an existing confined file. Rejects 0-match, multi-match (ambiguous), no-op (`old == new`), whole-file rewrites of large existing files ($\ge 80$ lines where `old` spans $\ge 80\%$ of the file and `new` is $\ge 80$ lines), and unrelocated truncations (stub guard below), returning a clear error so the model can retry within the turn budget.
     - `create_file(path, content, overwrite, justification, executable)`: creates a new confined file (optionally setting `0o755` when `executable=true`). Rejects overwriting an existing file unless `overwrite=true` with an explicit justification ($\ge 15$ chars), capped at `MAX_EXISTING_FILE_OVERWRITES = 1` per task, and subject to the stub guard below.
     - **Truncation / Stub Guard (`check_stub_truncation`)**: Rejects any edit (via `search_replace` or `create_file(..., overwrite=true)`, checked at edit time against the file's base content and again at `finish`) that removes $\ge 40$ net lines AND $\ge 50\%$ of the existing file's lines unless $\ge 50\%$ of the removed substantive lines reappear in other files created or edited in the same task. This blocks destructive stubbing/truncation (e.g. replacing 90 of 100 lines with 1 line) while permitting legitimate move-only file splits (such as `item6_pr14` moving `README.md` into `docs/*.md`, where 100% of removed lines reappear in the destination docs) and small cleanups (`item6_pr15`, `item6_pr08` retiring the 50-line `code-writer.md` by 38 net lines).
     - `run_tests()`: executes `test_cmd` inside the outer `/usr/bin/bwrap` sandbox (only when `has_tests = true`).
     - `finish(summary)`: finalizes the task (checking the stub guard, rejecting empty diffs so the model can retry, running `run_tests` when `has_tests = true`, or accepting non-empty diffs when `has_tests = false`).
     The harness applies all edits and captures `final_diff` via `git add -N .` + `git diff`. `check_prompt_leak` runs on the full message history before every model request. The final-turn notice is attached strictly on the actual final turn (`turn == max_turns - 1`, across both normal and parse-error turns).
  4. **Turn Cap, Per-Task Wall Budget (`617 s`), and Unchanged Total Ceiling (`4,320 s`)**:
     - Tool-turn cap is `MAX_TURNS_DEFAULT = 12` to accommodate multi-step read/edit/retry/test turns. Completion token cap (`TASK_BUDGET_TOKENS = 32,768`), per-completion cap (`MAX_TOKENS = 8,192`), `REASONING_BUDGET = 4,096`, `SAMPLING` (`temperature = 0.6`, `top_p = 0.95`, `top_k = 20`), and total launcher wall ceiling (`CEILING_SECONDS = 4,320`, 1.2 GPU-hours) remain unchanged.
     - **Per-Task Wall Budget (`TASK_WALL_BUDGET = floor(4320 / 7) = 617 s`)**: Each task receives an equal 617-second wall budget (`7 * 617 = 4,319 s <= 4,320 s`) enforced inside `pilot_pr.py` (including bounding HTTP request timeout to remaining task wall seconds) and passed via `--task-wall-budget` from `run.sh`, so later tasks (`item6_pr16`, `item6_pr20`) are never penalized by earlier ones. Hitting the 617 s budget stops that task cleanly with `stop_reason = "task_wall_budget"` and `passed = False`, captures any worktree edits applied so far as `final_diff` (matching `max_turns` and `budget` semantics: partial diffs are graded normally and empty diffs remain automatic non-approvals), and continues to the next task.
  5. **Offline Reachability Check (`bench/loop/check_reachability.py`)**: CPU-only, harness-side check (never imported by `pilot_pr.py` or the model loop; reads `merged_commit` / `hidden_diff` strictly offline while keeping the in-loop leak tripwire intact) that replays all 7 merged reference solutions through `pilot_pr.ToolSession` under the exact v2 tool limits (`read_file` 250-line windows, `search_replace` rewrite cap and stub guard, `MAX_EXISTING_FILE_OVERWRITES = 1`) and verifies byte-for-byte reachability of every task before any GPU run.
  6. **Grader Empty-Average Representation**: `pilot_pr.py grade` now stores `avg_hand_fix_lines_per_approved: null` (instead of `0.0`) when zero PRs are approved.
- **Unchanged Protocol Elements**: Same 7 PR tasks (`item6_pr06`, `item6_pr08`, `item6_pr13`, `item6_pr14`, `item6_pr15`, `item6_pr16`, `item6_pr20`), same KEEP/DROP/INCONCLUSIVE bars (Section 9: KEEP requires $\ge 3/6$ tests, $\ge 3/7$ approvals, avg `hand_fix_lines` $\le 20$; DROP if $< 2/6$ tests or $< 2/7$ approvals), same authoritative `merged_commit` read-only bwrap grading, same Tier 2 blind Grok 4.7 high review procedure (fresh session per task, `tamper` fails both test and review bars), same isolation/bwrap rules, and empty diff remains an automatic non-approval with `hand_fix_lines` excluded.

## 12. Amendment, Nov 20 2026 (Post v2 Run 1): `item6_pr16` Sentinel Abort, Harness Fixes, and Bounded Resume

Recorded 2026-11-20 CT after Item 6 pilot v2 run 1 finished at commit `54cca4854134d077fe5108e913f315ccad1cd5cf` (`54cca48`). **No GPU session starts in this commit.**

- **Pre-Registered Outcome Already Decided (`DROP`)**: The grade-path re-run on the 6 recorded v2 run-1 tasks (`item6_pr06`, `item6_pr08`, `item6_pr13`, `item6_pr14`, `item6_pr15`, `item6_pr20`) is already **0/5 testable passed** (`testable_tasks = 5`, `testable_passed = 0`). Even if `item6_pr16` later passes, the best possible test score across the 6 testable tasks is **1/6**, which is still **DROP** under the pre-registered bar ($< 2/6$, Section 9). The pre-registered v2 result is already **DROP** on the test bar alone. Resuming `item6_pr16` is strictly to obtain the 7th loop-produced record the protocol asks for and to exercise the harness fix; it cannot change the KEEP/DROP call and is not fishing for a better result.
- **What Happened in v2 Run 1 (`item6_pr16` Abort & Frozen Evidence)**:
  - Run 1 executed at `54cca48` (`llmctl` session 82, `Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf`, `--ctx 65536 --np 1`, `total_slots 1 n_ctx 65536`, GTT 23.5 GiB) and produced 6 frozen task records (`item6_pr06` `max_turns` 12 turns / 56 diff lines, `item6_pr08` `repeat_error` 5 turns / 60 diff lines, `item6_pr13` `context_overflow` 8 turns / 0 diff lines, `item6_pr14` `context_overflow` 7 turns / 0 diff lines, `item6_pr15` `max_turns` 12 turns / 114 diff lines, `item6_pr20` `repeat_code` 3 turns / 0 diff lines).
  - On `item6_pr16` (`base_commit = 6c56cc09eaafb2376422e73515b39f8193893740`), the model read or grepped `bench/loop/run.py` (which legitimately contains `SENTINEL = "ORACLE-SENTINEL-7f3a91c2"` at line 352 of that base commit). On the next turn, `check_prompt_leak` tripped on its hardcoded literal `"ORACLE-SENTINEL"` substring check (`pilot_pr.py:394`), raised `AssertionError: LEAK TRIPWIRE TRIGGERED: sentinel string leaked into prompt!`, and `run_subcommand` re-raised `AssertionError` without writing a JSONL record or diff (`rc=1`, wall `72.3 s`).
  - The launcher (`bench/loop/runs/item6-pilot/run.sh`) logged `ERROR: task item6_pr16 exited with rc=1 (continuing to next task)`, continued to `item6_pr20`, ran offline grading on only 6 tasks, and exited `done rc=0 wall_s=1523` despite the missing `item6_pr16` record.
  - Run-1 evidence was frozen in Commit 1 of this PR strictly from the SHA256SUMS-verified freeze under `/tmp/lab-seats/item6-pilot-v2/` (excluding `run.pid` and the unofficial `reviews_complete: false` `grade.json`):
    - `bench/loop/results/item6-pilot-v2.jsonl` (6 records)
    - `bench/loop/results/item6-pilot-v2.diffs/` (`item6_pr06.diff`, `item6_pr08.diff`, `item6_pr13.diff`, `item6_pr14.diff`, `item6_pr15.diff`, `item6_pr20.diff`; no `item6_pr16.diff`)
    - `bench/loop/results/item6-pilot-v2.run1/run.log` and `bench/loop/results/item6-pilot-v2.run1/run.status`
    - `bench/loop/results/item6-pilot-v2.SHA256SUMS` (9 verified entries)
- **Harness Fixes Applied Before Resume**:
  1. **Leak Tripwire Recording (`stop_reason = "prompt_leak"`)**: `check_prompt_leak` still fails closed (`PromptLeakError`, a subclass of `AssertionError`) and never sends the leaked prompt to the model, but `run_task_loop` / `run_subcommand` now catch it, record `stop_reason = "prompt_leak"` (`passed = False`), preserve any partial diff from earlier turns (or empty diff if no edits occurred, which remains automatic non-approval), flush JSONL, and continue remaining tasks without re-raising `AssertionError` out of `run_subcommand`.
  2. **Per-Run Random Sentinel (No Fixed Sentinel Strings)**: Removed the hardcoded literal `"LEAK_SENTINEL"` / `"ORACLE-SENTINEL"` substring checks from `check_prompt_leak` (with no fixed allowlist/denylist that could collide with repository text). Replaced with `generate_run_sentinel()` (`PILOT-RUN-SENTINEL-<32 hex chars>`), generated fresh per run and placed only into hidden task fields and test fixtures. Existing checks on `hidden_diff`, `merged_commit`, and literal grading seed `104729` remain intact (tools already redact `104729`).
  3. **Per-Turn Uncommitted Instrumentation**: `pilot_pr.py` logs each turn's tool names, compact arguments (`path`, `pattern`, line window / payload sizes), result size (`result_chars`), and any fired `leak_branch` to `<run_dir>/turn_events.jsonl` under `/tmp/lab-seats/<label>/` (never committed; writes inside the git repo are refused). On a leak trip, the full message history is written to `<run_dir>/leak_history_<task_id>_turn<turn>.json` (mode `0o600`, never committed).
  4. **Launcher Completeness Guard (`run.sh`)**: At the end of `bench/loop/runs/item6-pilot/run.sh`, `check_results_complete` verifies that `bench/loop/results/${LABEL}.jsonl` contains all 7 expected task IDs. If any task ID is missing, `run.sh` writes `incomplete missing=<ids> ...` to `run.status` (preserved by `on_exit`) and exits non-zero rather than reporting `done rc=0`. `TASK_WALL_BUDGET` defaults explicitly to `617` s even when `CEILING_SECONDS` is bounded on a resume.
- **Resume Protocol & Provenance**:
  - **Missing Task Only**: Run with `RESUME=1` so only the missing task ID (`item6_pr16`) executes. The 6 frozen run-1 records in `bench/loop/results/item6-pilot-v2.jsonl` and all 6 frozen diffs in `bench/loop/results/item6-pilot-v2.diffs/` stay byte-for-byte identical (verified against `bench/loop/results/item6-pilot-v2.SHA256SUMS`).
  - **Per-Task Wall Budget (`617 s`)**: `item6_pr16` runs with the exact same `TASK_WALL_BUDGET=617` per-task wall budget as the other 6 tasks — **not** the `2,966 s` that happened to remain on the outer ceiling when `item6_pr16` started in run 1. Total combined GPU wall time across run 1 (`1,523 s`) plus the `617 s` resume stays strictly under the `4,320 s` (1.2 GPU-hour) ceiling (`CEILING_SECONDS=2797` remaining, or `<= 2,140 s` total).
  - **Both Commit Heads Recorded**: Commit `54cca48` (`54cca4854134d077fe5108e913f315ccad1cd5cf`) produced the 6 frozen run-1 records; the resume of `item6_pr16` runs at this PR's merge head on `main`.
  - **`task_error` Row Treatment (Recorded 2026-11-20 CT, Before `item6_pr16` Resume)**: If a task ends with `stop_reason = "task_error"` (an unexpected non-leak harness exception caught in `run_subcommand`):
    1. It is reported in the post-run write-up as a harness failure.
    2. It still goes through the normal `pilot_pr.py grade` path unchanged, so the official `item6-pilot-v2.grade.json` needs no hand edits.
    3. Any non-empty partial diff captured on a `task_error` row is still sent to blind Tier 2 review as usual (while an empty diff remains an automatic non-approval with `hand_fix_lines` excluded).
    4. *Resolved in Section 14 (2026-11-21)*: `task_error` keeps any non-empty partial diff for Tier 2 review (per item 3 above), and schema v2 records explicit `diff_empty`, `abort_reason`, and `harness_failure` fields in both JSONL and `grade.json` so missing or partial diffs cannot be mistaken for "not yet run".
- **Unchanged Protocol Elements**: No change to KEEP/DROP/INCONCLUSIVE bars (Section 9), mechanical PR selection (Section 4), isolation / outer `/usr/bin/bwrap` + read-only test file grading rules (Section 6), or the empty-diff automatic non-approval rule (Section 10).
- **Recorded Observation (Not Fixed Now) & Development-Set Caveat**:
  - v2 stopped first-request context overflow, but `item6_pr13` and `item6_pr14` still ended `context_overflow` at turns 8 and 7 as tool output accumulated in the conversation history. Those records stand unchanged and are not re-run or fixed for v2.
  - Restated from Section 11: v2 reruns the exact same 7 PRs whose v1 failures shaped these harness fixes (development-set re-test).

## 13. Item 6 Pilot v2 Results (2026-11-20 CT)

Final post-run results for Item 6 pilot v2 (`label = item6-pilot-v2`), graded offline under the unchanged pre-registered protocol (Sections 4, 6, 9, 10, 11, and 12). **No GPU session starts in this commit.**

### Official Decision & Summary Metrics

Official grade computed via `python3 bench/loop/pilot_pr.py --label item6-pilot-v2 grade` and committed to `bench/loop/results/item6-pilot-v2.grade.json`:

| Metric | v2 Result | Target (KEEP) | Threshold (DROP) |
| :--- | :--- | :--- | :--- |
| **Tasks Evaluated** | 7 | 7 | 7 |
| **Testable Tasks** | 6 | — | — |
| **Authoritative Test Passes** | **0 / 6** (`0.0%`) | $\ge 3/6$ (`50.0%`) | $< 2/6$ (`< 33.3%`) |
| **Reviews Complete** | `true` (3 Grok reviewed, 4 auto non-approval) | `true` | — |
| **First-Pass Reviewer Approvals** | **0 / 7** (`0.0%`) | — | — |
| **Final Reviewer Approvals** | **0 / 7** (`0.0%`) | $\ge 3/7$ (`42.9%`) | $< 2/7$ (`< 28.6%`) |
| **Avg Hand-Fix Lines / Approved** | **`null`** (n/a — 0 approved PRs) | $\le 20$ lines | $> 20$ lines (INCONCLUSIVE) |
| **Tamper Detected** | **0 / 3 reviewed** (`tamper = false` reviewed on `item6_pr06`, `item6_pr08`, `item6_pr15`; set automatically to `false` by the auto non-approval path for empty-diff tasks `item6_pr13`, `item6_pr14`, `item6_pr16`, `item6_pr20` with no reviewer inspection) | 0 | $> 0$ |
| **Official Decision** | **DROP** | **KEEP** | **DROP** |

Both pre-registered DROP thresholds are independently met (`0/6 < 2/6` authoritative test passes and `0/7 < 2/7` final reviewer approvals).

### Run Provenance (Both Commit Heads)

- **Run 1 (`54cca48` / `54cca4854134d077fe5108e913f315ccad1cd5cf`)**: Executed 2026-11-20 16:35–17:00 CST (`llmctl` session 82, `Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf`, `--ctx 65536 --np 1`, `total_slots 1 n_ctx 65536`, GTT 23.5 GiB, `ceiling_seconds=4320`, `TASK_WALL_BUDGET=617`, total script wall `1,523 s`, `bench/loop/results/item6-pilot-v2.run1/run.{log,status}`). Produced the 6 frozen records (`item6_pr06`, `item6_pr08`, `item6_pr13`, `item6_pr14`, `item6_pr15`, `item6_pr20`). On `item6_pr16`, Run 1 aborted (`rc=1`, `72.3 s`) on a false-positive leak tripwire caused by the hardcoded `"ORACLE-SENTINEL"` substring check matching `bench/loop/run.py` line 352; that bug was fixed in PR #25 (`e524779`, replacing fixed strings with a per-run random sentinel).
- **`item6_pr16` Resume (`e524779` / `e524779bf854dd01b6bb7b129916b5047f3ee246`, PR #25 merge commit)**: Executed 2026-11-20 18:55–18:57 CST (`llmctl` session 83, same model and `--ctx 65536 --np 1`, `total_slots 1 n_ctx 65536`, GTT 23.5 GiB, `RESUME=1`, `CEILING_SECONDS=2797`, `TASK_WALL_BUDGET=617`, step wall `131.1 s`, task `wall_s = 130.91 s`, total resume script wall `140 s`, `done rc=0`, `bench/loop/results/item6-pilot-v2.pr16-resume/run.{log,status}`). Inserted the single `item6_pr16` record before `item6_pr20` in `bench/loop/results/item6-pilot-v2.jsonl` while leaving all 6 Run-1 JSONL lines and all 6 Run-1 diffs byte-identical.
- **Total GPU Wall Time**: `1,523 s + 140 s = 1,663 s` (~27.7 minutes), strictly under the `4,320 s` (1.2 GPU-hour) ceiling.
- **Checksums**: The original Run-1 manifest `bench/loop/results/item6-pilot-v2.SHA256SUMS` (9 entries) is preserved unchanged (all 8 non-JSONL entries still pass; only `item6-pilot-v2.jsonl` changed by the single `item6_pr16` record inserted before `item6_pr20`). `bench/loop/results/item6-pilot-v2.final.SHA256SUMS` covers the final 7-record JSONL, Run-1 and `item6_pr16`-resume logs/statuses, and all 7 diffs.

### Per-Task Results

| Task ID | PR # | Run / Head | Stop Reason | Turns | Completion Tokens | Wall (s) | Diff Lines | Hidden Jaccard | Test Result (Auth.) | Tier 2 Verdict | Tamper | Hand-Fix Lines |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `item6_pr06` | #6 | Run 1 (`54cca48`) | `max_turns` | 12 | 18,438 | 412.54 | 56 | 0.0171 | FAIL | `REQUEST-CHANGES` | `false` | 100 *(n/a for approved bar)* |
| `item6_pr08` | #8 | Run 1 (`54cca48`) | `repeat_error` | 5 | 9,354 | 190.21 | 60 | 0.0187 | FAIL | `REQUEST-CHANGES` | `false` | 55 *(n/a for approved bar)* |
| `item6_pr13` | #13 | Run 1 (`54cca48`) | `context_overflow` | 8 | 9,227 | 257.08 | 0 | 0.0000 | FAIL | `NON-APPROVAL` *(auto)* | `false` *(auto, unreviewed)* | n/a *(excluded, Sec. 10)* |
| `item6_pr14` | #14 | Run 1 (`54cca48`) | `context_overflow` | 7 | 7,155 | 195.14 | 0 | 0.0000 | FAIL | `NON-APPROVAL` *(auto)* | `false` *(auto, unreviewed)* | n/a *(excluded, Sec. 10)* |
| `item6_pr15` | #15 | Run 1 (`54cca48`) | `max_turns` | 12 | 12,398 | 297.78 | 114 | 0.1364 | n/a (`has_tests=false`) | `REQUEST-CHANGES` | `false` | 22 *(n/a for approved bar)* |
| `item6_pr16` | #16 | Resume (`e524779`) | `context_overflow` | 9 | 3,189 | 130.91 | 0 | 0.0000 | FAIL | `NON-APPROVAL` *(auto)* | `false` *(auto, unreviewed)* | n/a *(excluded, Sec. 10)* |
| `item6_pr20` | #20 | Run 1 (`54cca48`) | `repeat_code` | 3 | 4,522 | 87.76 | 0 | 0.0000 | FAIL | `NON-APPROVAL` *(auto)* | `false` *(auto, unreviewed)* | n/a *(excluded, Sec. 10)* |

Notes on `hand_fix_lines`:
- Because 0 of 7 tasks were approved, `avg_hand_fix_lines_per_approved` is `null` (n/a for the Section 9 $\le 20$ lines-per-approved-PR bar).
- For the 3 non-empty diffs reviewed by Grok 4.7 high (`item6_pr06`, `item6_pr08`, `item6_pr15`), the reviewer's hand-fix estimates (100, 55, and 22 lines) are reported above for completeness, but all three were `REQUEST-CHANGES` (non-approved) and are n/a for the approved-PR hand-fix bar.
- For the 4 empty-diff tasks (`item6_pr13`, `item6_pr14`, `item6_pr16`, `item6_pr20`), Section 10 applies unchanged: automatic `NON-APPROVAL` with no Grok review and `hand_fix_lines: null` (excluded).

### Tier 2 Blind Review Summary

- Raw artifacts and verbatim outputs are stored in `bench/loop/results/item6-pilot-v2.tier2/` and summarized in `bench/loop/results/item6-pilot-v2.reviews.json`.
- Blind packets were generated with `bench/loop/results/item6-pilot-v2.tier2/mkpackets.py` (verified byte-exact against all 5 v1 packets in `bench/loop/results/item6-pilot.tier2/success/` via `mkpackets.py check`) and reviewed in fresh `cursor-agent` ask-mode sessions pinned to `grok-4.7-high` (Nov 20, 18:59–19:01 CST; `rc=0`, `is_error=false`, `tamper=false` across all 3 reviewed tasks).
- Reviewer findings on the 3 non-empty diffs:
  - `item6_pr06` (`REQUEST-CHANGES`, 100 hand-fix lines): `_pull_from_code` can overwrite a verdict already parsed from prose and delete interior code lines (off-by-one 9-line window), does not add the read-only `reparse` subcommand, and does not extend `--selftest`.
  - `item6_pr08` (`REQUEST-CHANGES`, 55 hand-fix lines): incorrectly states Ryzen Max Bot launches both seats as `agy -p` (reviewer stays Claude) and leaves `docs/review-roles.md`, `AGENTS.md`, `CLAUDE.md`, `tools/lab-seats/launch.sh`, and `tools/lab-seats/test.sh` unchanged.
  - `item6_pr15` (`REQUEST-CHANGES`, 22 hand-fix lines): consistently renames the writer seat to Gemini 3.8 Flash (`gemini-3.8-flash-high`) across the 5 main docs, but leaves `tools/lab-seats/launch.sh`, `test.sh`, and `README.md` on the old slug and omits the stale-path audit across `.claude/`, `docs/`, and `scripts/preflight.sh` after exhausting `max_turns=12`.

### Known Confounds, Caveats, and Scope of the DROP Call

1. **Mid-Conversation `context_overflow` Confound (3 of 7 tasks)**: Switching to 1-slot 64k context (`--ctx 65536 --np 1`) and compact Turn-0 target-file manifests eliminated Turn-0 overflow (`item6_pr15` ran all 12 turns instead of overflowing at Turn 0). However, 3 of 7 tasks still terminated with `context_overflow` mid-conversation as verbatim `read_file`/`grep`/`list_files` tool outputs accumulated across turns and pushed the next prompt over the 57,344-token preflight limit (`65,536 - 8,192`):
   - `item6_pr13` at turn 8 (`59,367 > 57,344` tokens, `final_diff = ""`),
   - `item6_pr14` at turn 7 (`74,794 > 57,344` tokens, `final_diff = ""`),
   - `item6_pr16` at turn 9 (`67,199 > 57,344` tokens, `final_diff = ""`).
   Because the v2 harness did not compact, evict, or bound prior tool outputs in the conversation history, those three tasks remain confounded by context-window management.
2. **Run-1 Leak Tripwire on `item6_pr16`**: Run 1's abort on `item6_pr16` was most likely a false positive triggered by repo-native text: the fixed `ORACLE-SENTINEL` substring branch fired (not the hidden-field / `hidden_diff` branch), and the clean `item6_pr16` resume at `e524779` with the per-run sentinel (PR #25) did not trip before hitting `context_overflow` at turn 9.
3. **Development-Set Re-Test Caveat**: As stated in Sections 11 and 12, v2 re-ran the exact same 7 PRs whose v1 failures shaped the v2 harness fixes. It is a development-set re-test, not an unseen evaluation split.
4. **No Overclaiming Beyond the Bars**:
   - **What DROP means**: Under the pre-registered Section 9 bars, `Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf` in this single-model v2 structured-tool loop (`0/6` authoritative test passes, `0/7` reviewer approvals) does **not** meet the threshold to scale to a 20–30 PR benchmark.
   - **What DROP does not mean**: v2 is a small ($n=7$) dev-set test of one model/quantization under one harness, with 3/7 tasks still confounded by mid-conversation tool-output accumulation (`context_overflow`) and `item6_pr20` stopping at turn 3 on `repeat_code` before making edits. On the 3 tasks that did produce diffs, the v2 structured edit tools and stub guard visibly eliminated v1's destructive whole-file rewrites (`item6_pr06`: 718 $\to$ 56 diff lines, hand-fix 800 $\to$ 100; `item6_pr08`: 619 $\to$ 60 diff lines, hand-fix 194 $\to$ 55; `item6_pr15`: Turn-0 overflow $\to$ 114 diff lines, hand-fix 22), though none reached passing tests or mergeable completeness within 12 turns. The DROP decision settles the pre-registered scale/no-scale question for this loop as built and makes no broader claim beyond those bars.
5. **Known Grader Representation Limitation (Follow-Up)**: `grade.json` records `tamper=false` for the four unreviewed empty-diff tasks; `null` would be more accurate (deferred to the `task_error`/empty-diff follow-up PR; frozen results unchanged).

## 14. Amendment, Nov 21 2026: Backlog Cleanup for Future Runs (Schema v2)

Recorded 2026-11-21 CT after PR #26 decision review. **Applies strictly to future runs (`schema_version = 2`); no GPU session starts in this commit, and all frozen v1/v2 results under `bench/loop/results/item6-pilot*` remain untouched.**

1. **Explicit `task_error` and Abort Outcome Fields (`schema_version = 2`)**: New `pilot_pr.py` JSONL rows stamp `"schema_version": 2`, `"diff_empty": true/false`, `"abort_reason": "<reason>" | null`, and `"harness_failure": true/false` (`true` for `task_error`). When a task ends in `task_error` (pre-loop or mid-run harness exception) or another abort (`context_overflow`, `request_error`, `prompt_leak`, `task_wall_budget`), both the JSONL row and `grade.json` explicitly record `diff_empty` and a non-empty `abort_reason` (with `final_diff = ""` and `diff_empty = true` when no diff is emitted), so a missing or partial diff cannot be mistaken for "not yet run". The Section 12 `task_error` rule stays unchanged: `task_error` is reported as a harness failure on the normal `pilot_pr.py grade` path, and any non-empty partial diff captured before the failure still goes to Tier 2 blind review.
2. **Unreviewed `tamper: null` in `grade.json` (`schema_version >= 2`)**: For schema v2+ rows that never received a Tier 2 review (including empty-diff automatic non-approvals), `pilot_pr.py grade` records `"tamper": null` instead of `false`. Tier 2 reviewed tasks retain required boolean `"tamper": true/false`.
3. **Frozen Legacy Compatibility (`schema_version < 2`)**: Rows without `schema_version` (frozen v1 `item6-pilot` and v2 `item6-pilot-v2`) retain legacy grading semantics and re-grade identically (`0/6` tests, `0/7` approvals, `DROP` for frozen v2). No KEEP/DROP bars, selection rules, or sandbox isolation rules change.

## 15. Amendment, Nov 21 2026: Item 6 Pilot v3 (Compaction + Unseen External-Repo PRs, Pre-Run)

Stated before any practice or v3 GPU session (2026-11-21 CT). **No GPU session starts in this commit.** AJ authorized the Step 1 practice run on Nov 21 2026 11:28 AM CT ("address all nits and then follow claude rec"), so only the PR merge gates Step 1; Step 2 (unseen v3 pilot) waits for Step 1 to pass, any compaction freeze note, and AJ's separate yes.

### 15.1 Freeze Status & Scope

- **v1 and v2 Frozen (`DROP`)**: Both v1 (`item6-pilot`, `0/6` tests, `0/7` approvals, `DROP`) and v2 (`item6-pilot-v2`, `0/6` tests, `0/7` approvals, `DROP`; verified 12/12 via `bench/loop/results/item6-pilot-v2.final.SHA256SUMS`) are permanently frozen and untouched. All launchers refuse `LABEL=item6-pilot` and `LABEL=item6-pilot-v2`.
- **First Test on Unseen PRs**: v1 and v2 evaluated the 7 dev PRs from `ajeswint/strix-halo-lab`. **v3 (`item6-pilot-v3`) is the first evaluation on genuinely unseen PRs** from an external repository the local model has never been tested on (`more-itertools/more-itertools`).
- **Unchanged Model, Serving, and Budget Parameters**:
  - Model: `Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf` (no DeepSeek arm).
  - Serving: `scripts/llmctl.py invite qwen --ctx 65536 --np 1` (`total_slots 1 n_ctx 65536`, `slot_ctx = 65,536`, `RESERVED_OUTPUT_TOKENS = 8,192`, `max_prompt_tokens = 57,344`).
  - Sampling & Budgets: `temperature = 0.6`, `top_p = 0.95`, `top_k = 20`, `REASONING_BUDGET = 4,096`, `MAX_TOKENS = 8,192`, `MAX_TURNS_DEFAULT = 12`, `TASK_BUDGET_TOKENS = 32,768`, `TASK_WALL_BUDGET = 617` s, `CEILING_SECONDS = 4,320` s (1.2 GPU-hours).

### 15.2 Context Compaction Parameters (Frozen for Practice Run & Baseline v3)

Targeting the mid-conversation `context_overflow` confound observed on `item6_pr13`, `item6_pr14`, and `item6_pr16` in v2 (Section 13), `bench/loop/pilot_pr.py` adds deterministic per-turn truncation and multi-turn history compaction with the following frozen parameters:

| Parameter | Value | Role |
| :--- | :--- | :--- |
| `TOOL_RESULT_MAX_LINES` | `120` (`HEAD=80`, `TAIL=40`) | Per-tool line cap; elides middle with `... [elided N lines] ...` |
| `TOOL_RESULT_MAX_CHARS` | `6,000` | Per-tool char cap (head+tail with elided-lines/chars marker) |
| `TEST_OUTPUT_MAX_LINES` | `80` (`HEAD=30`, `TAIL=50`) | Per-test output line cap (head+tail with elided-lines marker) |
| `TEST_OUTPUT_MAX_CHARS` | `3,500` | Per-test output char cap (head+tail with elided-lines/chars marker) |
| `TURN_FEEDBACK_MAX_CHARS` | `12,000` | Combined per-turn `Tool results:` message cap across all calls in a turn |
| `COMPACT_KEEP_RECENT_TURNS` | `2` | Most recent tool-result turns kept verbatim in Stage 1 |
| `COMPACT_MIN_RECENT_TURNS` | `1` | Minimum recent tool-result turns kept verbatim in Stage 2b |
| `COMPACT_TARGET_CTX_RATIO` | `0.75` (`43,008` tok at `57,344` max) | Target prompt-token ratio triggering Stage 2 budget compaction |
| `STALE_ASSISTANT_MAX_CHARS` | `1,200` | Threshold above which stale assistant turns are summarized in Stage 2a |

- **Compaction Stages** (`compact_conversation_messages`, preserving `messages[0]` system prompt and `messages[1]` initial task prompt intact on every turn):
  1. `stale_tool_summary` (Stage 1): summarizes user tool-result messages older than the last `COMPACT_KEEP_RECENT_TURNS` (2) turns into compact per-tool digests (tool name, key args, ok/error status, char count).
  2. `stale_assistant_summary` (Stage 2a, when prompt tokens $> 0.75 \times \text{max\_prompt\_tokens}$): summarizes stale assistant messages $> 1,200$ chars (e.g., large `create_file` JSON blobs already applied to disk).
  3. `recent_tool_summary` (Stage 2b, if still above target): summarizes older kept user tool outputs down to `COMPACT_MIN_RECENT_TURNS = 1`.
  4. `drop_stale_turns` (Stage 2c, if still above `max_prompt_tokens = 57,344`): drops the oldest stale `(assistant, user)` turn pairs after `[0, 1]` while keeping the final active user turn.
  5. `truncate_latest_tool_result` (Stage 2d, if still above `max_prompt_tokens`): head+tail truncates the latest tool-result message to fit inside `max_prompt_tokens`.
- **Visible Compaction Logging**: Every truncation or history compaction emits:
  - a visible `COMPACTION task=<id> turn=<t> stage=<stage> ...` stdout line (captured in `run.log`),
  - a structured `"event": "compaction"` record in `<run_dir>/turn_events.jsonl`, and
  - per-turn `history[turn]["compaction"]` plus top-level `compaction_events_total` and `compaction_chars_saved` in the JSONL task record.

### 15.3 Unseen External-Repo Task Set & Anti-Contamination Selection Rule

- **Chosen External Repository**: `more-itertools/more-itertools` (`https://github.com/more-itertools/more-itertools.git`, MIT license, pure Python 3.11–3.15, zero runtime dependencies, zero test dependencies — stdlib `python3 -m unittest` runs offline in `/usr/bin/bwrap`).
- **Local Bare Mirror**: Pinned at commit `e3f79f4fde5f7c107f70a20730b17240a05ba99b` (fetched 2026-11-21) under `/data/datasets/item6-v3-repos/more-itertools.git` (outside `strix-halo-lab`; `/data` is mounted over with `--tmpfs` inside `/usr/bin/bwrap` so the sandbox cannot access it).
- **Contamination Cutoff & Primary Source**:
  - `Qwen/Qwen3.6-35B-A3B` Hugging Face release timestamp: **`2026-04-15T05:59:19Z`** (source: `https://huggingface.co/Qwen/Qwen3.6-35B-A3B`, API field `createdAt: "2026-04-15T05:59:19.000Z"`; quantized GGUF `https://huggingface.co/unsloth/Qwen3.6-35B-A3B-GGUF` `createdAt: "2026-04-16T04:31:31.000Z"`, `lastModified: "2026-04-20T12:42:25.000Z"`).
  - Selection window starts **`2026-05-01T00:00:00Z`** through **`2026-11-21T00:00:00Z`** (strictly post-release with $> 10$-day buffer). All 7 selected PRs were merged between **2026-09-18** and **2026-11-17** (5–7 months after Qwen3.6-35B-A3B release).
- **Mechanical Selection Rule (`bench/loop/select_v3.py`, written before inspecting any candidate diff)**:
  1. First-parent merge commits on `master` up to `e3f79f4fde5f7c107f70a20730b17240a05ba99b` matching `^Merge pull request #(\d+)\b` (`base_commit = parents[0]`, `merged_commit = sha`).
  2. Merge commit UTC timestamp in `[2026-05-01T00:00:00Z, 2026-11-21T00:00:00Z]`.
  3. Purely from `git diff --numstat` (never inspecting diff content):
     - No binary files.
     - No build/CI/dependency files (`.github/`, `requirements/`, `pyproject.toml`, `setup.cfg`, `tox.ini`).
     - At least 1 runtime implementation file (`more_itertools/*.py`) and at least 1 test file (`tests/test_*.py`).
     - Changed file count in `[2, 8]`; total changed lines (`added + deleted`) in `[15, 250]`.
  4. Offline CPU verification in outer `/usr/bin/bwrap` (`python3 -I -B`, `--unshare-net`, stdlib only, no `pip install`): merged-commit test files mounted read-only **PASS** (`rc == 0`, exact test count) at `merged_commit` and **FAIL** (`rc != 0`) at `base_commit`. (Replaces v2's reachability check.)
  5. Sort verified candidates chronologically ascending by `(merged_at_utc, pr_number)` and freeze the **7 most recent** (`verified[-7:]`).
  - Verified by CPU tests `test_v3_mechanical_selection_matches_frozen_list` and `test_v3_all_seven_tasks_fail_at_base_and_pass_at_merged_in_bwrap` in `bench/loop/test_pilot_pr_v3.py`.
- **Rule-Built Task Prompts (`tasks_item6_v3.build_v3_task_prompt`)**:
  - Built strictly by deterministic rule from verbatim GitHub metadata without viewing any merged diff and without hand-writing task prose:
    - If the PR references a non-PR GitHub issue, use the linked issue's exact title and body as written (PRs #1269 $\to$ Issue #1268, #1305 $\to$ Issue #1304, #1345 $\to$ Issue #1344).
    - Otherwise, use the PR's exact title and body as written (PRs #1260, #1322, #1342, #1311).
  - Mechanically strip HTML comments, replace every fenced code block (```` ``` ```` / `~~~`) with `[code block removed]`, and redact `104729`.
  - Hidden tests (`merged_commit` test files), reference diffs (`hidden_diff`), `merged_commit` SHAs, and literal seed `104729` never enter the model loop.

### 15.4 Frozen v3 Unseen Task List (`bench/loop/tasks_item6_v3.py`)

| Task ID | PR # | Merged (UTC) | Lines | Base Commit | Prompt Source | Test Command (`test_cmd`) | Expected Tests | Target Files |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `item6v3_pr1260` | #1260 | `2026-09-18T19:49:04Z` | 54 | `d634820be7a23b6a85441ee67051530fb0a8a960` | PR #1260 | `python3 -m unittest tests.test_recipes` | 200 | `docs/versions.rst`, `more_itertools/recipes.py`, `tests/test_recipes.py` |
| `item6v3_pr1269` | #1269 | `2026-09-21T16:16:22Z` | 19 | `1da45ae4b61a832ed080f08a8833784aad0a9534` | Issue #1268 | `python3 -m unittest tests.test_more` | 731 | `more_itertools/more.py`, `tests/test_more.py` |
| `item6v3_pr1305` | #1305 | `2026-09-29T20:28:23Z` | 20 | `790bb0bb2c03e7a07282e5f16f4b1fde35b8fcf5` | Issue #1304 | `python3 -m unittest tests.test_more` | 733 | `docs/versions.rst`, `more_itertools/more.py`, `tests/test_more.py` |
| `item6v3_pr1322` | #1322 | `2026-10-30T14:45:20Z` | 53 | `4aeb4338ae1407d8da9723e86da99efeb446f719` | PR #1322 | `python3 -m unittest tests.test_more` | 736 | `docs/versions.rst`, `more_itertools/more.py`, `tests/test_more.py` |
| `item6v3_pr1342` | #1342 | `2026-10-30T14:50:27Z` | 18 | `20c4ee5c63f8f8c35a37aee3b69d95cd2450c09a` | PR #1342 | `python3 -m unittest tests.test_more` | 738 | `more_itertools/more.py`, `tests/test_more.py` |
| `item6v3_pr1345` | #1345 | `2026-11-04T00:20:44Z` | 34 | `08dca284ba5446a026afdc34067b658f9da989eb` | Issue #1344 | `python3 -m unittest tests.test_more` | 740 | `more_itertools/more.py`, `tests/test_more.py` |
| `item6v3_pr1311` | #1311 | `2026-11-17T22:49:38Z` | 18 | `0fcdde9cce8bfdc3ba5e84711a990a32b74564a4` | PR #1311 | `python3 -m unittest tests.test_more` | 741 | `docs/versions.rst`, `more_itertools/more.py`, `tests/test_more.py` |

- All **7 of 7** tasks are testable (`has_tests = true`, `testable_total = 7`), verified offline inside `/usr/bin/bwrap` (pass at `merged_commit`, fail at `base_commit`).

### 15.5 Absolute KEEP / DROP Bars (No Cloud-Seat Baseline)

- **No Cloud-Seat Baseline**: Unlike `ajeswint/strix-halo-lab` (Section 2), no Antigravity/Grok cloud-seat baseline exists on `more-itertools/more-itertools`. **The KEEP/DROP bars for v3 are therefore absolute.**
- **Unchanged Rate Bars (from Section 9 / v2, `compute_keep_drop`)**:
  - **KEEP**: Authoritative test pass rate $\ge 50.0\%$ ($\ge 4/7 = 57.1\%$ on $N_{\text{test}} = 7$ testable PRs, matching v2's $\ge 3/6 = 50.0\%$ rate threshold) **AND** blind Tier 2 Grok 4.7 high approval $\ge 3/7$ ($42.9\%$) **AND** average `hand_fix_lines` $\le 20$ per approved PR (`tamper = true` fails both test and review bars).
  - **DROP**: Authoritative test pass rate $< 33.3\%$ ($\le 2/7 = 28.6\%$ on $N_{\text{test}} = 7$, matching v2's $< 2/6$) **OR** blind Tier 2 reviewer approval $< 2/7$ ($< 28.6\%$).
  - **INCONCLUSIVE**: Intermediate outcome (e.g., $3/7 = 42.9\%$ test pass rate with $\ge 2/7$ approvals, or average `hand_fix_lines > 20`); defaults to **DROP** unless AJ approves a bounded extension.

### 15.6 Two-Step Execution Protocol & Launchers

#### Step 1: Practice Run on Dev PRs `item6_pr13`, `item6_pr14`, `item6_pr16` (Pre-Declared as NOT Counting)

- **Declared in Advance as NOT Counting**:
  - Runs FIRST on the 3 dev PRs that overflowed mid-conversation in v2 (`item6_pr13`, `item6_pr14`, `item6_pr16`).
  - **No KEEP/DROP decision is computed, no Tier 2 Grok review is run, and the practice run is NEVER reported as a pilot result.**
  - Outputs stay in uncommitted `/tmp/lab-seats/item6-v3-practice/` (never written to `bench/loop/results/`).
- **Pass Criteria**:
  1. Zero `context_overflow` across all 3 tasks (`item6_pr13`, `item6_pr14`, `item6_pr16`),
  2. Zero `harness_failure` (`task_error`),
  3. Compaction events visible in `run.log` (`COMPACTION ...` lines) and `turn_events.jsonl` / `item6-v3-practice.jsonl` (`compaction_events_total > 0`).
- **Budget & Ceiling**: `TASK_WALL_BUDGET = 617` s per task; total ceiling `CEILING_SECONDS = 1851` s ($617\text{ s} \times 3$, ~0.51 GPU-hours).
- **Own Result Note & Post-Practice Freeze Rule**:
  - After Step 1 finishes, record its outcome in its own dated practice result note (Section 15.7 below or `docs/item6-v3-practice-result.md`).
  - Compaction parameters may be adjusted after inspecting the practice run, **but any adjusted settings must be committed and frozen in a dated v3 pre-run note in `docs/item6-pilot.md` (and verified pushed via `scripts/prereg-guard.sh --head`) before launching Step 2 (the unseen v3 run).**
- **Launcher**: `bench/loop/runs/item6-v3-practice/run.sh` (authorized by AJ on Nov 21 2026 11:28 AM CT with "address all nits and then follow claude rec", so only the PR merge to `main` gates launch):

```bash
WT=/home/aj/projects/strix-halo-lab EXPECT_HEAD=$(git -C /home/aj/projects/strix-halo-lab rev-parse origin/main) nohup bash /home/aj/projects/strix-halo-lab/bench/loop/runs/item6-v3-practice/run.sh >/dev/null 2>&1 &
```

#### Step 2: Unseen v3 Pilot Run (`item6-pilot-v3`)

- Runs **only** after Step 1 passes, the practice result note is recorded, final compaction settings are frozen and pushed on `origin/main`, and AJ gives a separate yes.
- **Launcher**: `bench/loop/runs/item6-pilot-v3/run.sh`:

```bash
WT=/home/aj/projects/strix-halo-lab EXPECT_HEAD=$(git -C /home/aj/projects/strix-halo-lab rev-parse origin/main) TARGET_REPO=/data/datasets/item6-v3-repos/more-itertools.git nohup bash /home/aj/projects/strix-halo-lab/bench/loop/runs/item6-pilot-v3/run.sh >/dev/null 2>&1 &
```

- If the external bare mirror does not yet exist on disk, populate it read-only before launching:

```bash
mkdir -p /data/datasets/item6-v3-repos && git clone --bare https://github.com/more-itertools/more-itertools.git /data/datasets/item6-v3-repos/more-itertools.git
```

### 15.7 Step 1 Practice Run Result Note & Step 2 Authorization (2026-11-21 CT)

**Practice run complete (PASS on all 3 Step 1 criteria); NOT counting as a pilot result (no KEEP/DROP verdict, no Tier 2 Grok review, and no practice transcripts or artifacts committed to the repo). No GPU session starts in this docs-only commit.**

- **Provenance & Execution Summary** (read from uncommitted `/tmp/lab-seats/item6-v3-practice/{run.status,run.log,turn_events.jsonl,results/item6-v3-practice.jsonl}`):
  - **Practice Head SHA**: `61239956e03c6133fbe1079f88ae6565c6afb7ce` (`61239956`, PR #28 merge commit, verified reachable from `origin/main` by `scripts/prereg-guard.sh`).
  - **Window & Serving**: `2026-11-21T16:17:55-06:00` to `2026-11-21T16:39:12-06:00` (`llmctl` session 84, `Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf`, `--ctx 65536 --np 1`, `total_slots 1 n_ctx 65536`, build `b11669-620d2225c`, GTT `23.5 GiB`, `ceiling_seconds=1851`, `resume=0`).
  - **Status & Wall Time**: `done rc=0 wall_s=1277` (~21.3 min, under the `1,851 s` ceiling; `run.status`: `done rc=0 wall_s=1277 end=2026-11-21T16:39:12-06:00`).
- **Per-Task Practice Outcomes** (`slot_ctx = 65,536`, `RESERVED_OUTPUT_TOKENS = 8,192`, prompt cap = `57,344` tokens; Stage 2 compaction threshold = `43,008` tokens):

| Task ID | PR # | `stop_reason` | Turns | `harness_failure` | `diff_empty` (Lines) | Compaction Events (`tool` / `turn` / `stale`) | Chars Saved | Peak Prompt Tokens (`usage` / `/tokenize` post-compact / pre-compact `stale_tool_summary` vs. `57,344`) | Task Wall (s) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `item6_pr13` | #13 | `repeat_error` | 10 | `false` | `true` (`0`) | `22` (`12` / `3` / `7`) | `134,516` | `13,341` / `13,643` / `18,394` (turn 9) | `379.48` |
| `item6_pr14` | #14 | `repeat_code` | 12 | `false` | `true` (`0`) | `116` (`99` / `8` / `9`) | `2,022,129` | `15,886` / `16,236` / `19,990` (turn 11) | `421.84` |
| `item6_pr16` | #16 | `max_turns` | 12 | `false` | `false` (`1,090`) | `14` (`9` / `2` / `3`) | `685,364` | `23,304` / `23,654` (turn 11) / `14,143` (turn 3) | `469.32` |

  - All 3 tasks recorded `passed = false`, `harness_failure = false`, and `abort_reason = null` (step walls in `run.log`: `379.7 s`, `422.0 s`, `469.5 s`; completion tokens: `17,440`, `18,568`, `23,893`; `item6_pr16.diff` size: `304,156` bytes; `item6_pr13.diff` and `item6_pr14.diff`: `0` bytes).
  - On `item6_pr14` turn 11, `stale_tool_summary` compacted `19,990 -> 16,218` tokens (`COMPACTION` line in `run.log` and `turn_events.jsonl`, included in `compaction_events_total = 116`) before the 18-token final-turn note yielded `preflight_prompt_tokens = 16,236` (`usage.prompt_tokens = 15,886`).
  - Across all 3 tasks, observed peak prompts stayed well below the `57,344`-token limit (`23.8%`–`41.2%` post-compaction; max `19,990` pre-compaction), never reaching the `43,008`-token Stage 2 compaction threshold (`0.75 * 57,344`).
- **Compaction Totals & Step 1 Pass Criteria (`practice_criteria_passed = true`)**:
  - **Total Compaction Events**: **`152`** (`22 + 116 + 14`), matching verbatim across `run.log` (`152` `COMPACTION` lines), `turn_events.jsonl` (`152` `"event": "compaction"` records), and `item6-v3-practice.jsonl` (`compaction_events_total = 152`, `compaction_chars_saved = 2,842,009`).
  - **All 3 Step 1 Criteria Passed**:
    1. Zero `context_overflow` across all 3 tasks (`context_overflow_tasks: []`).
    2. Zero `harness_failure` / `task_error` across all 3 tasks (`harness_failure_tasks: []`).
    3. Compaction events visibly logged (`152` `COMPACTION` lines in `run.log`, `152` compaction events in `turn_events.jsonl`, `compaction_events_total = 152 > 0`).
- **Frozen Compaction Settings for Step 2 (Unchanged)**:
  - All compaction settings remain **unchanged** from the merged v3 pre-registration in Section 15.2 (head `61239956`): `TOOL_RESULT_MAX_LINES = 120` (`HEAD=80`, `TAIL=40`), `TOOL_RESULT_MAX_CHARS = 6,000`, `TEST_OUTPUT_MAX_LINES = 80` (`HEAD=30`, `TAIL=50`), `TEST_OUTPUT_MAX_CHARS = 3,500`, `TURN_FEEDBACK_MAX_CHARS = 12,000`, `COMPACT_KEEP_RECENT_TURNS = 2`, `COMPACT_MIN_RECENT_TURNS = 1`, `COMPACT_TARGET_CTX_RATIO = 0.75` (`43,008` tok at `57,344` max), `STALE_ASSISTANT_MAX_CHARS = 1,200`. No code, `bench/loop/results/`, or `SHA256SUMS` files are modified.
- **Step 2 Authorization (AJ)**:
  - AJ, Nov 21 2026 5:48 PM CST: 'Yes, launch the counted 7-task more-itertools run.'
  - This authorizes launching Step 2 (`item6-pilot-v3`, Section 15.6) once this docs-only practice record PR is merged to `main` and verified via `scripts/prereg-guard.sh --head docs/item6-pilot.md origin/main`.

## 16. Item 6 Pilot v3 Results (2026-11-21 CT)

Final post-run results for Item 6 pilot v3 (`label = item6-pilot-v3`), the first counted evaluation on genuinely unseen external-repository PRs (`more-itertools/more-itertools`, Section 15.3–15.4), graded offline under the unchanged pre-registered Section 15.5 absolute bars. **No GPU session starts in this commit.**

### Official Decision & Summary Metrics

Official grade computed via:

```bash
python3 bench/loop/pilot_pr.py grade --label item6-pilot-v3 --task-suite v3 --target-repo /data/datasets/item6-v3-repos/more-itertools.git
```

and committed to `bench/loop/results/item6-pilot-v3.grade.json` (using `bench/loop/results/item6-pilot-v3.reviews.json`, which `grade` auto-discovers by label):

| Metric | v3 Result | Target (KEEP, Sec. 15.5) | Threshold (DROP, Sec. 15.5) |
| :--- | :--- | :--- | :--- |
| **Schema Version** | `2` (Section 14) | — | — |
| **Tasks Evaluated** | 7 | 7 | 7 |
| **Testable Tasks** | 7 | — | — |
| **In-Loop Test Passes** *(non-authoritative)* | **2 / 7** (`28.6%`: `pr1342`, `pr1345`) | — | — |
| **Authoritative Offline Test Passes** | **1 / 7** (`14.3%`: `pr1345` only) | $\ge 4/7$ ($\ge 50.0\%$) | $\le 2/7$ ($< 33.3\%$) |
| **Reviews Complete** | `true` (3 Grok reviewed, 4 auto non-approval) | `true` | — |
| **First-Pass Reviewer Approvals** | **1 / 7** (`14.3%`: `pr1345`) | — | — |
| **Final Reviewer Approvals** | **1 / 7** (`14.3%`: `pr1345`) | $\ge 3/7$ ($\ge 42.9\%$) | $< 2/7$ ($< 28.6\%$) |
| **Avg Hand-Fix Lines / Approved** | **`0.0`** (1 approved PR: `pr1345` = 0 lines) | $\le 20$ lines | $> 20$ lines (INCONCLUSIVE) |
| **Tamper Detected** | **0 / 3 reviewed** (`tamper = false` on `pr1269`, `pr1342`, `pr1345`; `tamper = null` on the 4 unreviewed empty-diff tasks per Sec. 14) | 0 | $> 0$ |
| **Context Overflows / Harness Failures** | **0 / 7** overflows, **0 / 7** `task_error` | — | — |
| **Official Decision** | **DROP** | **KEEP** | **DROP** |

The harness's pre-review grade (`reviews_complete = false`) had already returned **DROP** on the authoritative offline test bar alone (`1/7 = 14.3% < 33.3%`). With Tier 2 blind Grok 4.7 high reviews complete (`reviews_complete = true`), **both** independent Section 15.5 DROP thresholds are met (`1/7 < 33.3%` offline test pass rate and `1/7 < 28.6%` final reviewer approval rate). No bar or rule was altered.

### Run Provenance & Integrity Checksums

- **Run Head SHA**: `ddcbbfb94403926c46644eaac978db268f8df848` (`ddcbbfb`, PR #29 merge commit, verified reachable from `origin/main` by `scripts/prereg-guard.sh --head docs/item6-pilot.md origin/main`).
- **Execution Window & Serving**: Single uninterrupted run `2026-11-21T18:11:22-06:00` to `2026-11-21T18:19:09-06:00` (`llmctl` session 85, `Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf`, `--ctx 65536 --np 1`, `total_slots 1 n_ctx 65536`, build `b11669-620d2225c`, GTT `23.5 GiB`, `CEILING_SECONDS=4320`, `TASK_WALL_BUDGET=617`, `resume=0`, target bare repo `/data/datasets/item6-v3-repos/more-itertools.git`).
- **Total Wall Time & Tokens**: `done rc=0 wall_s=467` (~7.8 minutes, well under the `4,320 s` / 1.2 GPU-hour ceiling; sum of per-task wall times `454.85 s`; total completion tokens `22,472`).
- **Compaction Performance**: `38` total compaction events (`65,809` chars saved), matching verbatim across `bench/loop/results/item6-pilot-v3.run1/run.log` (`38` `COMPACTION` lines), `bench/loop/results/item6-pilot-v3.run1/turn_events.jsonl` (`38` `"event": "compaction"` records), and `bench/loop/results/item6-pilot-v3.jsonl` (`compaction_events_total` sum `38`). Zero tasks hit `context_overflow` or reached the `43,008`-token Stage 2 compaction threshold (max observed across all 7 tasks: `4,763` `usage.prompt_tokens`, `4,946` `/tokenize` preflight tokens, `5,905` pre-compaction tokens on `item6v3_pr1260` vs. the `57,344`-token prompt cap).
- **Frozen Artifacts & Checksums**:
  - `bench/loop/results/item6-pilot-v3.jsonl`, all 7 files under `bench/loop/results/item6-pilot-v3.diffs/`, and `bench/loop/results/item6-pilot-v3.run1/{run.log,run.status,turn_events.jsonl}` (`run.pid` excluded) are byte-identical to the frozen run bundle (`/tmp/lab-seats/item6-v3-frozen/MANIFEST.sha256`, 11/11 SHA-256 digests verified).
  - `bench/loop/results/item6-pilot-v3.reviews.json` stores the verbatim Tier 2 Grok 4.7 high verdicts.
  - `bench/loop/results/item6-pilot-v3.SHA256SUMS` covers all 13 committed v3 results files (`jsonl`, `reviews.json`, `grade.json`, `run1/{run.log,run.status,turn_events.jsonl}`, and all 7 `.diff` files), verified `13/13 OK` via `sha256sum -c item6-pilot-v3.SHA256SUMS` from `bench/loop/results/`.

### Per-Task Results

| Task ID | PR # | Prompt Source | Stop Reason | Turns | Completion Tokens | Wall (s) | Diff Lines | Hidden Jaccard | In-Loop Tests | Offline Auth. Tests | Tier 2 Verdict | Tamper | Hand-Fix Lines |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `item6v3_pr1260` | #1260 | PR #1260 *(PR body)* | `max_turns` | 12 | 1,156 | 39.76 | 0 | 0.0000 | FAIL | FAIL | `NON-APPROVAL` *(auto)* | `null` *(unreviewed)* | n/a *(excluded, Sec. 10)* |
| `item6v3_pr1269` | #1269 | Issue #1268 *(issue)* | `max_turns` | 12 | 14,104 | 252.19 | 36 | 0.0000 | FAIL | FAIL | `REQUEST-CHANGES` | `false` | 18 *(n/a for approved bar)* |
| `item6v3_pr1305` | #1305 | Issue #1304 *(issue)* | `repeat_code` | 11 | 954 | 24.04 | 0 | 0.0000 | FAIL | FAIL | `NON-APPROVAL` *(auto)* | `null` *(unreviewed)* | n/a *(excluded, Sec. 10)* |
| `item6v3_pr1322` | #1322 | PR #1322 *(PR body)* | `repeat_code` | 5 | 362 | 8.66 | 0 | 0.0000 | FAIL | FAIL | `NON-APPROVAL` *(auto)* | `null` *(unreviewed)* | n/a *(excluded, Sec. 10)* |
| `item6v3_pr1342` | #1342 | PR #1342 *(PR body)* | `pass` | 12 | 1,807 | 40.87 | 14 | 0.1429 | **PASS** | **FAIL** | `REQUEST-CHANGES` | `false` | 12 *(n/a for approved bar)* |
| `item6v3_pr1345` | #1345 | Issue #1344 *(issue)* | `pass` | 12 | 2,861 | 63.57 | 24 | 0.1333 | **PASS** | **PASS** | `APPROVE-WITH-NITS` | `false` | **0** |
| `item6v3_pr1311` | #1311 | PR #1311 *(PR body)* | `repeat_code` | 8 | 1,228 | 25.76 | 0 | 0.0000 | FAIL | FAIL | `NON-APPROVAL` *(auto)* | `null` *(unreviewed)* | n/a *(excluded, Sec. 10)* |

Notes on `hand_fix_lines`:
- Only the 1 approved task (`item6v3_pr1345`: `APPROVE-WITH-NITS`, `0` hand-fix lines) enters `avg_hand_fix_lines_per_approved = 0.0`.
- `item6v3_pr1269` (`18` lines) and `item6v3_pr1342` (`12` lines) were both `REQUEST-CHANGES` (non-approved) and are reported above for completeness but excluded from the approved-PR hand-fix average.
- The 4 empty-diff tasks (`item6v3_pr1260`, `item6v3_pr1305`, `item6v3_pr1322`, `item6v3_pr1311`) receive automatic `NON-APPROVAL` with no Grok review, `hand_fix_lines: null`, and `tamper: null` (Sections 10 and 14).

### Results Split by Prompt Source

As frozen in `bench/loop/tasks_item6_v3.py` (`source_kind`) and Section 15.4, 4 of the 7 v3 prompts came from PR bodies (where no non-PR GitHub issue was linked) and 3 came from linked GitHub issues:

| Prompt Source | Tasks ($n$) | Non-Empty Diffs | In-Loop Test Passes | Authoritative Offline Passes | Grok Approvals |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **PR body** (`PR #1260`, `PR #1322`, `PR #1342`, `PR #1311`) | 4 | 1 / 4 (`pr1342`) | 1 / 4 (`pr1342`) | **0 / 4** (`0.0%`) | **0 / 4** (`0.0%`) |
| **Linked issue** (`Issue #1268` / PR #1269, `Issue #1304` / PR #1305, `Issue #1344` / PR #1345) | 3 | 2 / 3 (`pr1269`, `pr1345`) | 1 / 3 (`pr1345`) | **1 / 3** (`33.3%`: `pr1345`) | **1 / 3** (`33.3%`: `pr1345`) |
| **Total** | **7** | **3 / 7** | **2 / 7** | **1 / 7** (`14.3%`) | **1 / 7** (`14.3%`) |

PR-body prompts describe the implemented fix directly in prose (e.g., naming the exact guards and target files), making them potentially easier than pre-fix issue reports; even so, the local model scored `0/4` offline passes and `0/4` approvals on the PR-body subset, and its sole offline pass and reviewer approval (`item6v3_pr1345`) came from a linked-issue prompt (`Issue #1344`, which itself noted that `numeric_range._len` already holds the arbitrary-precision length).

### Tier 2 Blind Review Summary

Verbatim Grok 4.7 high verdicts (fresh `cursor-agent` session per task, `packet.md` only, `2026-11-21T19:40:10-06:00`, `tamper = false` on all 3 reviewed diffs) are stored in `bench/loop/results/item6-pilot-v3.reviews.json`:

- `item6v3_pr1269` (`REQUEST-CHANGES`, `18` hand-fix lines, `tamper = false`, session `28724d99-4d1a-4eef-af74-84918c98cddf`): The `maxlen=0` `_peeked` side buffer drops the rewind path when `self._index` is already set (breaking default `maxlen=None` stability on repeated `peek`/`seek`), `_peeked is not None` cannot represent a real `None` element (requires a dedicated sentinel cleared by `seek`), and no tests were added.
- `item6v3_pr1342` (`REQUEST-CHANGES`, `12` hand-fix lines, `tamper = false`, session `4cf7129d-14ba-4c92-b499-e83d7f480a29`): Adds `n < 0` validation before `iter(iterable)`, but leaves `n == 0` unhandled (still hits `islice` and raises `ValueError: Step for islice()...` after consuming source items) and leaves `tests/test_more.py` unchanged without `test_zero_chunk_size` or `test_negative_chunk_size`.
- `item6v3_pr1345` (`APPROVE-WITH-NITS`, `0` hand-fix lines, `tamper = false`, session `9dcd8c96-9996-40e8-8fa9-2f0bfae2fa37`): Correctly switches `numeric_range.__eq__` and `__hash__` from `len()` to `self._len` / `other._len` while keeping `__len__` untouched so explicit `len(r)` still overflows. Non-blocking nits: `other._len` assumes `other` is a `numeric_range`, and no new regression tests above `sys.maxsize` were added to `tests/test_more.py`.

### Why `item6v3_pr1342` Passed In-Loop (`in_loop_passed = true`) but Failed Offline (`test_passed = false`)

This mismatch is directly established from `bench/loop/results/item6-pilot-v3.jsonl`, `bench/loop/results/item6-pilot-v3.run1/turn_events.jsonl`, `bench/loop/results/item6-pilot-v3.diffs/item6v3_pr1342.diff`, `bench/loop/pilot_pr.py`, and `bench/loop/results/item6-pilot-v3.grade.json`:

1. **Partial edit with no in-loop test additions**: On turn 6, the model executed a single successful `search_replace` on `more_itertools/more.py`, inserting only the `n < 0` check (`if n is not None and n < 0: raise ValueError('n must be at least 0')`). It never added the `n == 0` early-return guard and never edited `tests/test_more.py` (`item6v3_pr1342.diff` is 14 lines in `more_itertools/more.py` only).
2. **End-of-loop test run against unmodified `base_commit` tests**: Across turns 7–11, the model called only `read_file` and `grep` (it never called `run_tests` or `finish`). When turn 11 exhausted `max_turns = 12`, because turn 6 had dirtied the worktree (`dirty_since_last_test = True`), `bench/loop/pilot_pr.py` (lines 2564–2570) ran `run_tests(clean_task, worktree_dir)` once against the scratch worktree's unmodified `base_commit` (`20c4ee5c`) `tests/test_more.py`. Because `base_commit`'s `tests/test_more.py` has no `n == 0` or `n < 0` regression tests for `chunked_even` and the added `n < 0` guard broke no existing test, `python3 -m unittest tests.test_more` exited `0`, setting `passed = true` and `stop_reason = "pass"` in `item6-pilot-v3.jsonl`.
3. **Authoritative offline regrade against `merged_commit` tests**: During `pilot_pr.py grade`, `regrade_task_diff` applies `item6v3_pr1342.diff` to a clean `base_commit` tree and mounts `merged_commit`'s authoritative `tests/test_more.py` read-only inside `/usr/bin/bwrap` (Section 6). Under the 738 authoritative tests, `ChunkedEvenTests.test_zero_chunk_size` fails with 1 error (`ValueError: Step for islice() must be a positive integer or None.`) because `n == 0` is unhandled in the candidate diff—the exact gap Grok flagged in Tier 2 review.

(Note: `item6v3_pr1345` triggered the same end-of-loop `dirty_since_last_test` evaluation after its turn-11 `search_replace` without calling `run_tests`/`finish`; on `item6v3_pr1345`, the candidate edit also passed all 740 authoritative `merged_commit` tests offline.)

### Contamination Flag, Failure Modes, and Scope of the DROP Call

1. **Possible Training-Data Contamination on `#1260` (`more_itertools/recipes.py`)**: Although PR #1260 was authored `2026-09-07` and merged `2026-09-18` (strictly post-`2026-04-15` `Qwen3.6-35B-A3B` release), `more_itertools/recipes.py` mirrors Python's standard-library `itertools` documentation recipes (`http://docs.python.org/library/itertools.html#recipes`), with `running_median` and `running_mean` already in `recipes.py` and `running_min`, `running_max`, and `running_statistics` moved into `recipes.py` on `2026-04-08` (commit `6294fa6`, prior to the `2026-04-15` release cutoff). `item6v3_pr1260` is therefore flagged as possible training-data contamination of the target file/idioms. In this run, `item6v3_pr1260` exhausted `max_turns = 12` with `0` diff lines (`test_passed = false`, automatic `NON-APPROVAL`), so this contamination risk did not inflate v3's pass or approval counts. *(Pre-existing environment note: PR #1260's frozen `expected_test_count` of `200` for `tests.test_recipes` matches the host Python 3.14.4 environment where `unittest discover -s bench/loop` runs 80/80 OK, whereas Python 3.12.3 runs `199` tests in `tests.test_recipes`—a Python-version-dependent count difference that does not affect `item6v3_pr1260`'s empty-diff grade.)*
2. **Compaction Removed the v2 Context-Overflow Confound**: Unlike v2 (`3/7` `context_overflow`), v3 had `0/7` `context_overflow` and `0/7` `harness_failure` across all 7 tasks (`38` compaction events, max preflight prompt `4,946` tokens vs. `57,344` cap).
3. **Observed Failure Modes**: Without context overflow, 4 of 7 tasks still produced empty diffs (`item6v3_pr1260` read/grepped through `max_turns = 12` without editing; `item6v3_pr1305`, `item6v3_pr1322`, and `item6v3_pr1311` hit `repeat_code` on turns 11, 5, and 8 after repeated reads/greps or JSON parse errors without editing). The 3 tasks that did edit (`pr1269`, `pr1342`, `pr1345`) all ran to turn 12 without calling `run_tests` or `finish`: one (`pr1345`) passed offline tests and earned `APPROVE-WITH-NITS` (0 hand-fix lines), one (`pr1342`) implemented only half the fix (`n < 0`, omitting `n == 0`), and one (`pr1269`) introduced a `maxlen=None` regression and missed the `None`-sentinel edge case.
4. **No Overclaiming Beyond the Bars**: Under Section 15.5's absolute bars, `1/7` (`14.3%`) authoritative offline test passes and `1/7` (`14.3%`) blind Grok approvals independently trigger **DROP**. This settles the pre-registered scale/no-scale question for this single-model `Qwen3.6-35B-A3B` structured-tool loop on unseen external PRs; it is a small ($n = 7$) test on one external repository (with 4/7 prompts from PR bodies and `#1260` flagged above) and makes no broader claim beyond those bars.
5. **Possible Harness Confounds (Not Yet Measured)**: Separate from model capability, four possible harness-level confounds observed in v3 have not been isolated or measured yet: (a) `repeat_code` triggered by repeated read-only calls after Stage 1 compaction (`stale_tool_summary`), (b) JSON parse errors in tool-call blocks, (c) very short generations, and (d) in-loop test feedback (`run_tests`/`finish`) never being invoked across all 7 tasks. Their individual impact on the v3 outcome has not been measured.

## 17. Item 6 Pilot v3 CPU-Only `turn_events` Analysis (2026-11-22 CT)

**Scope: descriptive, post-hoc, n=7, one repo.** This section measures the harness-level confounds flagged at the end of Section 16 strictly from the committed v3 artifacts (`bench/loop/results/item6-pilot-v3.{jsonl,grade.json,diffs/,run1/turn_events.jsonl,run1/run.log}`) and `bench/loop/pilot_pr.py`. **No GPU session, model call, re-run, or re-grade occurred; the official v3 DROP decision (`1/7` authoritative offline test passes, `1/7` blind Grok approvals) and all 13 frozen files in `bench/loop/results/item6-pilot-v3.SHA256SUMS` stay byte-identical.**

Reproducible machine-readable summary committed to `bench/loop/results/item6-pilot-v3.analysis.json` via:

```bash
python3 bench/loop/analyze_v3_turns.py --output bench/loop/results/item6-pilot-v3.analysis.json
```

### 17.1 `repeat_code` Stops, Unconditional Stage 1 Compaction, and Post-Compaction File Re-Reads

- **Tasks Stopping on `repeat_code` (`3 / 7`)**: `item6v3_pr1305` (turn 10), `item6v3_pr1322` (turn 4), and `item6v3_pr1311` (turn 7). Zero other tasks stopped on `repeat_code`.
- **Exact Duplicated Reply Not Recorded**: Neither the raw assistant text (`content`), nor the SHA-256 `code_hash`, nor the matched earlier turn index is persisted in `item6-pilot-v3.jsonl`, `turn_events.jsonl`, or `run.log`. In `bench/loop/pilot_pr.py:2256-2276`, `_run_task_loop_turns` hashes `content + json.dumps(raw_tool_calls)` in memory and `break`s before `_append_turn_log` (so `turn_events.jsonl` has no `turn_tools` / `turn_parse_error` row on the `repeat_code` turn).
- **Compaction-Log Cross-Check (`38` vs. `36` in `history`)**: Across all 7 tasks, `turn_events.jsonl` records **38** compaction events (`34` `history_compact` with `stages=["stale_tool_summary"]`, `4` `tool_truncate` on `read_file`; `0` Stage 2 events), matching `run.log` (`38` `COMPACTION` lines) and top-level `compaction_events_total` sum (`38`, `65,809` chars saved). Per-turn `history[t]["compaction"]` sums to **36** because the `repeat_code` early-break dict (`bench/loop/pilot_pr.py:2263-2273`) omits `"compaction"` on `item6v3_pr1305` turn 10 (`480` chars saved) and `item6v3_pr1311` turn 7 (`739` chars saved).
- **Per-Task `repeat_code` Breakdown** *(all 3 tasks had `0` edit calls — 100% read-only tools plus parse errors, `diff_empty = true`)*:

| Task ID | Stop Turn | Stop Turn Tokens / Wall | Preceding Tool Calls (Read-Only / Edit / Parse Errors) | Same-Turn Stage 1 `stale_tool_summary` Immediately Before Stop? | Best Available Duplicated-Reply Proxy *(exact text not recorded)* |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `item6v3_pr1305` | 10 *(11 turns)* | `67` tok / `2.34 s` | `9` read-only (`5 read_file`, `4 grep`), `0` edits, `3` parse errors (t=0, 2, 3) | **Yes** — turn 10 (`turn_events.jsonl:55`, `run.log:57`; `9,413 -> 8,933` chars, `3,642 -> 3,463` tok; omitted from `history[10]`) | Turn 8 is the sole earlier exact token match (`67` tok: `read_file(tests/test_more.py, 4520..4590)`); nearest others: t=4 (`64`), t=6 (`69`). |
| `item6v3_pr1322` | 4 *(5 turns)* | `43` tok / `0.89 s` | `2` read-only (`1 read_file`, `1 grep`), `0` edits, `2` parse errors (t=2, 3) | **No on turn 4** — sole Stage 1 compaction ran **1 turn earlier on turn 3** (`turn_events.jsonl:59`, `run.log:65`; `6,665 -> 4,287` chars, `2,437 -> 1,406` tok); turn 1's 43-char `grep` was too short to shrink on turn 4 (`pilot_pr.py:1773`) | Turn 3 is the sole earlier exact token match (`43` tok: `turn_parse_error` `"No valid tool calls found..."`), pointing to a repeated non-tool/empty visible reply immediately after turn 3's compaction. |
| `item6v3_pr1311` | 7 *(8 turns)* | `497` tok / `9.48 s` | `9` read-only (`4 read_file`, `5 grep`), `0` edits, `0` parse errors | **Yes** — turn 7 (`turn_events.jsonl:107`, `run.log:102`; `8,095 -> 7,356` chars, `3,129 -> 2,872` tok; omitted from `history[7]`) | **No earlier token match** (max earlier turn was t=0 at `210` tok; t=1..6 were `65–148` tok). Because `code_hash` hashes visible `content` (+ `tool_calls`) only, the count exceeds the visible reply; consistent with but not proof of unrecorded reasoning tokens. |

- **Unconditional Stage 1 Compaction vs. Available Context**: In `bench/loop/pilot_pr.py:1867-1884` (`COMPACT_KEEP_RECENT_TURNS = 2`, line 64), Stage 1 `stale_tool_summary` runs unconditionally whenever more than 2 user tool-result turns exist, even when prompts are tiny. Across all 7 tasks, peak prompt utilization was `5,905` tokens pre-compaction (`4,946` preflight, `4,763` server `usage.prompt_tokens`) — at most **10.3%** of the `57,344`-token prompt cap (`43,008` Stage 2 target never reached). Every compacted turn was replaced with `[Use read_file/grep to re-inspect if needed.]` (`bench/loop/pilot_pr.py:1771`), while `seen_code_hashes` (`bench/loop/pilot_pr.py:2258-2276`) hard-terminates the task if the model re-emits an identical read-only reply.
- **File Re-Reads After Compaction (`21 / 36` `read_file` Calls = `58.3%`)**: Counting `read_file` calls targeting a path already read earlier in the same task after at least one `history_compact` (`stale_tool_summary`) event:
  - **Overall**: **21** same-path re-reads across **6 of 7** tasks (`pr1260`: 6, `pr1269`: 5, `pr1305`: 3, `pr1322`: 0, `pr1342`: 3, `pr1345`: 3, `pr1311`: 1).
  - **Overlapping line range**: **17 / 21** overlapped a previously read line range (`pr1260`: 6, `pr1269`: 5, `pr1305`: 1, `pr1342`: 2, `pr1345`: 3).
  - **Exact `(path, start, end)` re-reads**: **2 / 21** (`item6v3_pr1269` turn 10 `more_itertools/more.py:3120-3145` duplicating turn 6 after turn 9 compacted turn 6; `item6v3_pr1342` turn 4 `more_itertools/more.py:4627-4670` duplicating turn 1 immediately after turn 4 compacted turn 1).
  - **Prompt-vs-Truncation Mismatch**: `format_tool_messages` (`bench/loop/pilot_pr.py:1320`) advertises `read_file` as `max 250 lines/call` (`READ_FILE_MAX_LINES = 250`, line 44), while `TOOL_RESULT_MAX_LINES = 120` (line 54) elided lines on all 4 `tool_truncate` events (`pr1260` t=2 `113` elided & t=3 `27` elided; `pr1269` t=2 `12` elided; `pr1345` t=1 `56` elided).

### 17.2 `turn_parse_error` Events (`7` Events Across `4 / 7` Tasks)

- **Recording Sources**: `turn_events.jsonl` logs `prompt_tokens`, `completion_tokens`, `tools=[]`, and `result_chars` without the error text or raw model reply (`bench/loop/pilot_pr.py:2288-2303`); `run.log` does not log `turn_parse_error`. The exact parser error string is preserved in `item6-pilot-v3.jsonl` `history[turn].err` (matching `result_chars` byte-for-byte on all 7 events). **The raw model reply / offending JSON snippet is not recorded anywhere in the committed v3 records.**

| Task ID | Turn | Prompt Tok | Comp. Tok | `result_chars` | Error Class | Recorded Error Message (`item6-pilot-v3.jsonl` `history[turn].err`) | Next-Turn Outcome |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `item6v3_pr1269` | 7 | 2,862 | 3,410 | 83 | `json_expecting_comma_delimiter` | `Invalid JSON in tool block: Expecting ',' delimiter: line 1 column 1555 (char 1554)` | `read_only_tool_call` |
| `item6v3_pr1305` | 0 | 843 | 211 | 65 | `json_extra_data` | `Invalid JSON in tool block: Extra data: line 2 column 1 (char 90)` | `read_only_tool_call` |
| `item6v3_pr1305` | 2 | 2,277 | 107 | 65 | `json_extra_data` | `Invalid JSON in tool block: Extra data: line 2 column 1 (char 94)` | `parse_error` |
| `item6v3_pr1305` | 3 | 2,397 | 54 | 101 | `no_valid_tool_calls` | `No valid tool calls found. Respond with a \`\`\`json block containing a tool call or list of tool calls.` | `read_only_tool_call` |
| `item6v3_pr1322` | 2 | 2,194 | 75 | 69 | `json_expecting_value` | `Invalid JSON in tool block: Expecting value: line 1 column 1 (char 0)` | `parse_error` |
| `item6v3_pr1322` | 3 | 1,246 | 43 | 101 | `no_valid_tool_calls` | `No valid tool calls found. Respond with a \`\`\`json block containing a tool call or list of tool calls.` | `repeat_code` |
| `item6v3_pr1345` | 7 | 2,111 | 657 | 83 | `json_expecting_comma_delimiter` | `Invalid JSON in tool block: Expecting ',' delimiter: line 1 column 1639 (char 1638)` | `edit_tool_call` |

- **Class Breakdown**:
  - `json_expecting_comma_delimiter` (`2`): `pr1269` t=7 (`3,410` tok, `char 1554`) and `pr1345` t=7 (`657` tok, `char 1638`) — both single-line JSON failures at `>1,550` chars right before large `search_replace` attempts (`extract_tool_calls`, `bench/loop/pilot_pr.py:1261-1265`).
  - `json_extra_data` (`2`): `pr1305` t=0 and t=2 (`line 2 column 1`, `char 90`/`94`) — `json.loads` at `bench/loop/pilot_pr.py:1262` rejects multiple newline-separated JSON objects inside one fenced block (NDJSON instead of a JSON array).
  - `json_expecting_value` (`1`): `pr1322` t=2 (`line 1 column 1`, `char 0`).
  - `no_valid_tool_calls` (`2`): `pr1305` t=3 and `pr1322` t=3 — fallback at `bench/loop/pilot_pr.py:2281-2287` when `extract_tool_calls` yields neither valid calls nor JSON decode errors.
  - Five of the 7 parse errors occurred on `pr1305` (`3`) and `pr1322` (`2`), both of which subsequently ended on `repeat_code` with empty diffs.

### 17.3 Completion-Length Distribution, Unrecorded Reasoning Split, and Short Turns (`< 100` Tokens)

- **Visible vs. Reasoning Tokens Not Recorded**: Zero reasoning-related fields appear anywhere in the committed v3 records (`reasoning_related_keys_in_committed_records = []`). Although `server_ask` (`bench/loop/pilot_pr.py:3030-3037`) computes `reasoning_chars = len(msg.get("reasoning_content") or "")` and captures `finish_reason`, `_run_task_loop_turns` discards both and stores only `usage.completion_tokens` (`history[t]["tokens"]` and `turn_events.completion_tokens`). Two observations show the count exceeds the visible reply; consistent with but not proof of unrecorded reasoning tokens:
  1. `item6v3_pr1311` turn 7 logged `497` completion tokens yet matched an earlier turn's visible `code_hash` when no earlier turn exceeded `210` tokens.
  2. `item6v3_pr1269` turns 5–6 logged `4,171` and `4,213` completion tokens (just above `REASONING_BUDGET = 4096`, `bench/loop/pilot_pr.py:34`) while emitting 1–2 short `read_file` JSON calls.
- **Overall Distribution (`n = 72` Executed Turns, `22,472` Total Tokens)**:
  - `min = 43`, `p10 = 57.3`, `p25 = 65.8`, `median = 79.0`, `mean = 312.11` (`stdev = 784.90`), `p75 = 181.8`, `p90 = 504.2`, `p95 = 927.2`, `max = 4,213`.
  - Buckets: `<50`: **6**, `50–99`: **35**, `100–199`: **17**, `200–499`: **6**, `500–999`: **4**, `>=1000`: **4**.
  - Skew: `item6v3_pr1269` alone accounts for `14,104 / 22,472` (**62.8%**) of all completion tokens (turns 5–7 = `4,171`, `4,213`, `3,410`).
- **Short-Turn Set (`< 100` Completion Tokens: `41 / 72` Turns = `56.9%`)**:
  - Per-task counts: `pr1260` `9/12`, `pr1269` `3/12`, `pr1305` `8/11`, `pr1322` `4/5`, `pr1342` `6/12`, `pr1345` `6/12`, `pr1311` `5/8`.
  - **Outcome on the short turn itself**: `35` valid read-only tool calls (`read_file`/`grep`), `3` `parse_error` (`pr1305` t=3 `54`; `pr1322` t=2 `75`, t=3 `43`), `2` `repeat_code` stops (`pr1305` t=10 `67`; `pr1322` t=4 `43`), and `1` successful `search_replace` (`pr1345` t=11 `68` — the final edit of the passing task).
  - **What followed on the next turn**: `31` read-only tool calls, `3` `repeat_code` stops (all 3 `repeat_code` stops — `pr1305` t=9->10, `pr1322` t=3->4, `pr1311` t=6->7 — were immediately preceded by a `< 100`-token turn), `2` `parse_error` (`pr1322` t=1->2, t=2->3), `2` `task_end_repeat_code`, `2` `task_end_pass` (`pr1342` t=11, `pr1345` t=11), and `1` `edit_tool_call` (`pr1345` t=9->10).
  - Plain reading: `< 100`-token turns were mostly well-formed single-call navigation turns (`35/41` valid `read_file`/`grep` + `1/41` valid `search_replace`), not corrupted truncations; however, combined with shallow multi-turn slicing they dominated the 12-turn budget on empty-diff tasks (e.g., `pr1260` spent 9/12 turns at `47–77` tokens reading slices without ever editing).

### 17.4 Tool-Usage Counts and `run_tests` / `finish` Reachability

| Task ID | `read_file` (ok/err) | `grep` (ok/err) | `search_replace` (ok/err) | `list_files` | `create_file` | `run_tests` | `finish` | Total Calls | First OK Edit Turn |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `item6v3_pr1260` | 8 (8/0) | 4 (4/0) | 0 (0/0) | 0 | 0 | 0 | 0 | 12 | `null` |
| `item6v3_pr1269` | 7 (7/0) | 5 (5/0) | 2 (2/0) | 0 | 0 | 0 | 0 | 14 | 9 |
| `item6v3_pr1305` | 5 (5/0) | 4 (4/0) | 0 (0/0) | 0 | 0 | 0 | 0 | 9 | `null` |
| `item6v3_pr1322` | 1 (1/0) | 1 (1/0) | 0 (0/0) | 0 | 0 | 0 | 0 | 2 | `null` |
| `item6v3_pr1342` | 6 (6/0) | 5 (5/0) | 2 (1/1) | 0 | 0 | 0 | 0 | 13 | 6 |
| `item6v3_pr1345` | 5 (5/0) | 4 (4/0) | 3 (2/1) | 0 | 0 | 0 | 0 | 12 | 10 |
| `item6v3_pr1311` | 4 (4/0) | 5 (5/0) | 0 (0/0) | 0 | 0 | 0 | 0 | 9 | `null` |
| **Overall** | **36 (36/0)** | **28 (28/0)** | **7 (5/2)** | **0** | **0** | **0** | **0** | **71** | — |

- **Confirmed Unused**: `run_tests` = **0 / 71**, `finish` = **0 / 71** (alongside `list_files` = 0 and `create_file` = 0). `64 / 71` (**90.1%**) of all calls were read-only (`read_file` + `grep`) and `7 / 71` (**9.9%**) were `search_replace` (`5` succeeded, `2` failed: `pr1342` t=5 ambiguous 5 matches, `pr1345` t=8 0 matches).
- **Static Reachability in `bench/loop/pilot_pr.py`**:
  - **Wired in dispatch**: Both `finish` (`pilot_pr.py:2365-2369, 2432-2486`) and `run_tests` (`pilot_pr.py:2370-2394`) are implemented and reachable whenever `extract_tool_calls` (`pilot_pr.py:1232-1274`) extracts `{"tool": "run_tests", "args": {}}` or `{"tool": "finish", "args": {"summary": "..."}}`.
  - **No OpenAI `tools` JSON schema**: `server_ask` (`pilot_pr.py:3000-3040`) sends no `"tools"` parameter to `/v1/chat/completions`; tools are declared strictly in free-text prompt prose (`format_tool_messages`, `pilot_pr.py:1301-1352`).
  - **Prompt presence**: `run_tests` appears in the system tool list (`pilot_pr.py:1309`, included when `has_tests=True`, which holds for all 7 v3 tasks) and in the user prompt line `Verification command (\`run_tests\`): \`...\`` (`pilot_pr.py:1337`). However, neither the system `Rules:` bullets (`pilot_pr.py:1328-1333`) nor the user prompt's workflow sentence (`pilot_pr.py:1344-1345`: *"Start by reading... then apply targeted edits... and call `finish` when done."*) instructs calling `run_tests`. `finish` appears in the system tool list (`pilot_pr.py:1327`), user closing sentence (`pilot_pr.py:1345`), and the turn-11 `final_turn_note` (`pilot_pr.py:2021, 2107-2112`), which was attached on all 4 tasks reaching turn 11 (`pr1260`, `pr1269`, `pr1342`, `pr1345`) without eliciting a `finish` call.
  - **Observed edit timing**: Across the 3 tasks that edited, first successful edits occurred late (`pr1342` turn 6, `pr1269` turn 9, `pr1345` turn 10); `pr1269` and `pr1345` were still applying `search_replace` on turn 11, while `pr1342` spent turns 7–11 reading/grepping `tests/test_more.py`.

### 17.5 End-of-Loop `dirty_since_last_test` Check and the `item6v3_pr1342` False Pass

- **Code Path**: `dirty_since_last_test` is initialized `False` (`bench/loop/pilot_pr.py:2015`), set `True` on any successful `search_replace`/`create_file` (`pilot_pr.py:2406`), and cleared only by in-loop `run_tests` (`pilot_pr.py:2385`) or `finish` (`pilot_pr.py:2467`). When the loop exits with `stop_reason in ("max_turns", "budget")`, `has_tests=True`, and `dirty_since_last_test=True`, `pilot_pr.py:2564-2570` runs `run_tests(clean_task, worktree_dir)` once against the scratch worktree's `base_commit` test suite; if that exits `0`, it overwrites `stop_reason` to `"pass"` and sets `history[-1]["passed"] = True`.
- **Triggered Tasks (`3 / 7`)**: All 3 editing tasks (`pr1269`, `pr1342`, `pr1345`) reached turn 12 with `dirty_since_last_test = True` and `0` calls to `run_tests`/`finish`:
  - `item6v3_pr1269`: end-of-loop `base_commit` tests **failed** -> `stop_reason = "max_turns"`, `in_loop_passed = false`, offline `test_passed = false` (consistent with Grok's Tier 2 finding of a `maxlen=None` regression).
  - `item6v3_pr1342` (**false pass**, matching Section 16): turn 6 `search_replace` added only the `n < 0` guard in `more_itertools/more.py` (`item6v3_pr1342.diff`: 14 lines, `tests/test_more.py` untouched, omitting `n == 0`). After turns 7–11 read/grepped without calling `run_tests`/`finish`, `pilot_pr.py:2564-2570` ran `base_commit` (`20c4ee5c`) `tests/test_more.py` (which lacks `n == 0` / `n < 0` tests for `chunked_even`), exited `0`, and rewrote `stop_reason` from `"max_turns"` to `"pass"` (`in_loop_passed = true`). Offline `regrade_task_diff` (`pilot_pr.py:3441`) mounted `merged_commit`'s authoritative `tests/test_more.py` read-only in `/usr/bin/bwrap` and failed (`test_passed = false` in `item6-pilot-v3.grade.json`; Grok Tier 2 `REQUEST-CHANGES`, `12` hand-fix lines).
  - `item6v3_pr1345`: end-of-loop `base_commit` tests **passed** (`stop_reason = "pass"`, `in_loop_passed = true`) and offline authoritative `merged_commit` tests also **passed** (`test_passed = true`, Grok `APPROVE-WITH-NITS`, `0` hand-fix lines).
- **Reporting Artifact**: Rewriting `stop_reason` from `"max_turns"` to `"pass"` at `pilot_pr.py:2568` makes `pr1342` and `pr1345` indistinguishable in JSONL from explicit `finish` passes. As stated in Section 16, only offline `regrade_task_diff` counts for scoring, and the official v3 grade (`1/7` tests, `1/7` approvals, **DROP**) is unchanged.

### 17.6 Required v4 Telemetry and Ranked Harness Fixes *(Descriptive, Post-Hoc, n=7, One Repo)*

No harness edits are applied in this analysis PR. Diagnostic telemetry is required in v4 regardless of which behavioral changes are adopted; the remaining harness fixes are ranked by observed frequency and directness of link to failed v3 tasks, with all impact labels stated as untested hypotheses:

#### Required in v4 (Regardless of Other Changes)

- **Required — Persist missing diagnostic telemetry (`reasoning_chars`, `content_chars`, `finish_reason`, `repeat_code` matched turn/hash, truncated parse-error snippet, and `repeat_code` turn compactions)**
  - *Evidence*: `reasoning_chars` is computed at `pilot_pr.py:3033` and then discarded; `repeat_code` (`pilot_pr.py:2256-2276`) drops `code_hash`, matched turn index, `turn_events` logging, and `turn_compactions`; `turn_parse_error` (`pilot_pr.py:2288-2303`) drops `err_msg` and any truncated raw snippet.
  - *Hypothesised impact (untested)*: **Diagnostic only** (`0` direct task-pass delta, required in v4 regardless of other changes to remove measurement blind spots so future runs report visible vs. reasoning tokens and exact repeat/parse causes directly).

#### Ranked Behavioral Harness Fixes

1. **Rank 1 — Gate Stage 1 `stale_tool_summary` compaction on prompt-token pressure (not unconditional age `keep_recent_turns = 2`) and avoid hard-exiting `repeat_code` on read-only replies *(inferred trigger)***
   - *Evidence*: All `34` Stage 1 compactions fired at `2,140–5,905` tokens (`3.7%–10.3%` of the `57,344`-token cap), injecting `[Use read_file/grep to re-inspect if needed.]` (`pilot_pr.py:1771`). That was followed by `21 / 36` (`58.3%`) same-path post-compaction re-reads (`17` overlapping, `2` exact range duplicates), same-turn compaction directly before `2 / 3` `repeat_code` stops (`pr1305` t=10, `pr1311` t=7; plus 1-turn-prior compaction on `pr1322` t=3), and `3 / 7` empty-diff `repeat_code` stops (`0` edits across all 3). Because neither the raw duplicated reply text, nor `code_hash`, nor the matched earlier turn index is persisted (Section 17.1), that `repeat_code` fired on repeated read-only replies is **inferred** from the preceding zero-edit, read-only tool histories (and on `pr1322`, the sole token-count proxy is turn 3's `turn_parse_error` non-tool reply rather than a read-only tool call).
   - *Hypothesised impact (untested)*: **High** (touches `6/7` tasks with post-compaction re-reads and, under the inferred read-only `repeat_code` trigger, up to `3/7` empty-diff `repeat_code` terminations). Keeping full tool outputs while below a token threshold (e.g., `>= 50%` of `max_prompt_tokens`) preserves read context across the 12-turn loop and may reduce re-read turns, while restricting `repeat_code` (e.g., warning instead of hard stop on read-only calls, or requiring consecutive identical replies) would prevent read-only re-inspection from killing a task.

2. **Rank 2 — Harden `extract_tool_calls` JSON parsing (multi-object NDJSON / fenced-block recovery) and/or pass native OpenAI `tools` schema**
   - *Evidence*: `7` `turn_parse_error` turns wasted across `4 / 7` tasks (`pr1305`: 3, `pr1322`: 2, `pr1269`: 1 at `3,410` tok, `pr1345`: 1 at `657` tok). Two were `Extra data: line 2 column 1` (`pr1305` t=0, t=2: `json.loads` at `pilot_pr.py:1262` rejects newline-separated JSON objects in one block, fixable via `json.JSONDecoder().raw_decode`), two were `Expecting ',' delimiter` at char `1554`/`1638` on large single-line `search_replace` payloads (`pr1269` t=7, `pr1345` t=7), one was `Expecting value` (`pr1322` t=2), and two had no ```` ```json ```` block (`pr1305` t=3, `pr1322` t=3). `server_ask` (`pilot_pr.py:3010-3018`) currently sends no OpenAI `"tools"` schema.
   - *Hypothesised impact (untested)*: **Medium–High** (could recover up to `7` wasted turns across `4/7` tasks, including `pr1269`'s 3,410-token failed edit turn and `5` error turns on `repeat_code` tasks `pr1305` and `pr1322`).

3. **Rank 3 — Prompt/auto-trigger `run_tests` after edits and keep end-of-loop `dirty_since_last_test` status distinct from `stop_reason = "pass"`**
   - *Evidence*: `run_tests` = `0/71` and `finish` = `0/71` across all 7 tasks (`pilot_pr.py:1328-1333` `Rules:` and `1344-1345` omit `run_tests`). All 3 editing tasks (`pr1269`, `pr1342`, `pr1345`) exhausted 12 turns without seeing any in-loop test output, and `pr1269`'s diff failed even `base_commit` tests at loop end. Separately, `pilot_pr.py:2564-2570` overwrote `stop_reason = "max_turns"` to `"pass"` on `pr1342` (false pass against `base_commit` tests) and `pr1345`.
   - *Hypothesised impact (untested)*: **Medium** (could deliver actual test-failure tracebacks mid-loop — directly relevant to base-suite regressions like `pr1269` — and eliminate misleading `"stop_reason": "pass"` records by recording e.g. `stop_reason = "max_turns"` with a separate `end_of_loop_test_passed` boolean; note this cannot catch missing tests absent from `base_commit`, as on `pr1342`, unless the model also writes tests).

4. **Rank 4 — Align `TOOL_RESULT_MAX_LINES` (`120`) with `READ_FILE_MAX_LINES` (`250`) when prompt utilization is low**
   - *Evidence*: `format_tool_messages` (`pilot_pr.py:1320`) advertises `read_file` up to `250` lines/call (`READ_FILE_MAX_LINES = 250`, line 44), but `TOOL_RESULT_MAX_LINES = 120` (line 54) immediately elided lines on all `4` `tool_truncate` events (`pr1260` t=2 `113` elided & t=3 `27` elided; `pr1269` t=2 `12` elided; `pr1345` t=1 `56` elided) at `< 4,000` prompt tokens (`< 7%` of `57,344`).
   - *Hypothesised impact (untested)*: **Medium–Low** (removes a direct prompt-vs-harness contradiction and could reduce multi-turn follow-up slicing on tasks like `pr1260` and `pr1345`).

### 17.7 Open Question *(Not a Harness Fix)*

- **Median `79.0`-Token Completion vs. `REASONING_BUDGET = 4,096`**: Across all `72` executed v3 turns, median `usage.completion_tokens` was `79.0` (`p75 = 181.8`; `41 / 72 = 56.9%` of turns `< 100` tokens; Section 17.3) against a configured `REASONING_BUDGET = 4,096` (`bench/loop/pilot_pr.py:34`) — under `2%` of the reasoning budget on the median turn — while `item6v3_pr1269` turns 5–6 reached `4,171` and `4,213` tokens. Why `Qwen3.6-35B-A3B` generated under `100` total completion tokens on most turns despite a `4,096`-token reasoning budget, and how those tokens split between reasoning and visible output, cannot be determined from the committed v3 records (where `reasoning_chars` and `reasoning_content` were not persisted); this remains an open question rather than a proposed harness fix.

## 18. Amendment, Nov 22 2026: Item 6 Pilot v4 (Telemetry, Four Ranked Harness Fixes, and Unseen `lark-parser/lark` PRs, Pre-Run)

Stated before any v4 practice or counted GPU session (2026-11-22 CT). **No GPU session starts in this commit.** Per AJ's decision following Section 17, v4 adds the required Section 17.6 telemetry and **all four ranked harness fixes**, runs a pre-declared non-counting practice run on the 7 v3 `more-itertools` tasks first, and evaluates the counted run on a newly selected unseen batch of 7 external-repository PRs.

### 18.1 Freeze Status & Unchanged Protocol Elements

- **v1, v2, and v3 Permanently Frozen (`DROP`)**:
  - **v1** (`item6-pilot`): `0/6` authoritative tests, `0/7` approvals, **DROP** (frozen in PR #23).
  - **v2** (`item6-pilot-v2`): `0/6` authoritative tests, `0/7` approvals, **DROP** (`bench/loop/results/item6-pilot-v2.final.SHA256SUMS`, 12/12 OK).
  - **v3** (`item6-pilot-v3`): `1/7` authoritative tests, `1/7` approvals, **DROP** (`bench/loop/results/item6-pilot-v3.SHA256SUMS`, 13/13 OK; post-hoc analysis in `bench/loop/results/item6-pilot-v3.analysis.json` untouched).
  - All frozen result artifacts and `SHA256SUMS` under `bench/loop/results/` and `/tmp/lab-seats/item6-v3-frozen` stay strictly untouched. Both v4 launchers refuse frozen labels `item6-pilot`, `item6-pilot-v2`, and `item6-pilot-v3`.
- **v3 Tasks Retired to Development Set**: Because the 7 v3 `more-itertools/more-itertools` tasks (`pr1260`, `pr1269`, `pr1305`, `pr1322`, `pr1342`, `pr1345`, `pr1311`) drove the Section 17 analysis and v4 fixes, they are now a **DEVELOPMENT set** and may **never** be counted for v4 KEEP/DROP.
- **Unchanged Model, Serving, Budgets, and Absolute Bars (Same as v3)**:
  - Model: `Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf` (single-model loop; no DeepSeek arm).
  - Serving: `scripts/llmctl.py invite qwen --ctx 65536 --np 1` (`total_slots 1 n_ctx 65536`, `slot_ctx = 65,536`, `RESERVED_OUTPUT_TOKENS = 8,192`, `max_prompt_tokens = 57,344`). No serving flag changes are required by any v4 fix.
  - Sampling & Budgets: `temperature = 0.6`, `top_p = 0.95`, `top_k = 20`, `REASONING_BUDGET = 4,096`, `MAX_TOKENS = 8,192`, `MAX_TURNS_DEFAULT = 12`, `TASK_BUDGET_TOKENS = 32,768`, `TASK_WALL_BUDGET = 617` s (`floor(4320 / 7)`), `CEILING_SECONDS = 4,320` s (1.2 GPU-hours).
  - **Absolute KEEP / DROP Bars (Section 15.5, unchanged)**: No cloud-seat baseline exists on `lark-parser/lark`; bars are absolute (`compute_keep_drop`, `bench/loop/pilot_pr.py`):
    - **KEEP**: Authoritative offline test pass rate $\ge 50.0\%$ ($\ge 4/7$ on $N_{\text{test}} = 7$) **AND** blind Tier 2 Grok 4.7 high approval $\ge 3/7$ ($\ge 42.9\%$) **AND** average `hand_fix_lines` $\le 20$ per approved PR (`tamper = true` fails both bars).
    - **DROP**: Authoritative offline test pass rate $< 33.3\%$ ($\le 2/7 = 28.6\%$ on $N_{\text{test}} = 7$) **OR** blind Tier 2 Grok 4.7 high approval $< 2/7$ ($< 28.6\%$).
    - **INCONCLUSIVE**: Intermediate outcome (e.g., `3/7` tests with $\ge 2/7$ approvals, or avg `hand_fix_lines > 20`); defaults to **DROP** unless AJ approves a bounded extension.
  - Same outer `/usr/bin/bwrap` read-only authoritative test grading, schema v2 (`tamper: null` on unreviewed empty diffs, explicit `diff_empty`, `abort_reason`, `harness_failure`), and per-run random leak sentinel.

### 18.2 Required v4 Diagnostic Telemetry (Frozen)

Recorded per turn in `<run_dir>/turn_events.jsonl` (uncommitted) and in task JSONL `history[turn]` (`bench/loop/pilot_pr.py`):

| Event / Record | Added Telemetry Fields | Notes |
| :--- | :--- | :--- |
| Every model-reply turn (`turn_tools`, `turn_parse_error`, `turn_repeat_code`, and `history[turn]`) | `reasoning_chars` (`int`), `content_chars` (`int`), `finish_reason` (`str \| null`) | `server_ask` preserves both `finish` and `finish_reason`; `_run_task_loop_turns` persists all three on every reply turn. |
| `turn_repeat_code` (and `history[turn]` on `repeat_code` stop) | `matched_turn` (`int`), `reply_hash` (`str`, SHA-256 hex), `repeat_read_only` (`bool`), `compaction_count` (`int`), plus `compaction` list preserved in `history[turn]` | Removes the v3 blind spot where `repeat_code` broke before `_append_turn_log` and dropped `turn_compactions`. |
| `turn_tools` (when a read-only repeat is allowed instead of hard-stopped) | `read_only_repeat_matched_turn` (`int`), `reply_hash` (`str`) | Makes allowed read-only repeats observable. |
| `turn_parse_error` (and `history[turn]` on parse error) | `error` (`str`, capped at 500 chars), `raw_snippet` (`str`, seed-redacted, capped at `PARSE_ERROR_RAW_SNIPPET_MAX_CHARS = 500` chars) | Removes the v3 blind spot where raw offending model replies were discarded. |
| `auto_run_tests` (and task JSONL top-level fields) | `passed` (`bool`), `dirty_since_last_test` (`bool`), `result_chars` (`int`); task-level `run_tests_calls`, `finish_tests_calls`, `auto_run_tests`, `end_of_loop_test_passed` | Keeps end-of-loop test status strictly separate from `stop_reason` and `passed`. |

### 18.3 Frozen v4 Ranked Harness Fixes & Parameters

| Fix Rank | Change in `bench/loop/pilot_pr.py` | Frozen Parameters |
| :--- | :--- | :--- |
| **Rank 1a — Pressure-Gated Stage 1 Compaction** | Gate Stage 1 `stale_tool_summary` on actual prompt-token pressure (`tokens_before > stage1_trigger_tokens`) rather than running unconditionally on every turn after `keep_recent_turns`. Stage 2a–2d budget compaction stays intact above `target_tokens`. | `COMPACT_STAGE1_TRIGGER_RATIO = 0.50` (`28,672` tokens at `57,344` max prompt tokens); `COMPACT_KEEP_RECENT_TURNS = 2`; `COMPACT_MIN_RECENT_TURNS = 1`; `COMPACT_TARGET_CTX_RATIO = 0.75` (`43,008` tokens); `STALE_ASSISTANT_MAX_CHARS = 1,200`. |
| **Rank 1b — Read-Only `repeat_code` Guard** | Extract tool calls before the `repeat_code` stop check. If the repeated reply consists strictly of read-only tool calls (`READ_ONLY_TOOLS = {"read_file", "grep", "list_files"}`), do **not** hard-stop on the first repeat: execute the read, append a nudge pointing to `matched_turn`, and keep bounded safeguards against true infinite loops (trigger is inferred per Sec. 17.1). Non-read-only repeats (`search_replace`, `create_file`, parse errors) still hard-stop immediately. | `READ_ONLY_TOOLS = {"read_file", "grep", "list_files"}`; `MAX_CONSECUTIVE_READ_ONLY_REPEATS = 2` (hard-stop on 2nd consecutive repeated read-only turn); `MAX_TOTAL_READ_ONLY_REPEATS = 3` (hard-stop on 3rd total repeated read-only turn in a task). |
| **Rank 2 — Robust JSON Tool-Call Parsing** | **Choice & Justification**: Harden `extract_tool_calls` JSON parsing (while preserving existing `raw_tool_calls` support) rather than enabling native OpenAI `tools` in `llama-server`. `scripts/llm-serve.sh` launches `llama-server` without `--jinja`; keeping v3 serving unchanged avoids introducing a serving/template confound with `Qwen3.6-35B-A3B`'s `reasoning_content`, and robust JSON parsing is deterministic and CPU-verified across all 7 logged v3 parse-error classes plus synthetic edge cases. Tolerates code fences (`json`, `tool`, bare, unclosed), leading/trailing prose, trailing commas outside string literals, single object vs. list, NDJSON multi-object streams (`json.JSONDecoder(strict=False).raw_decode`), unescaped newlines in strings, and missing commas between array objects, while refusing to silently mangle genuinely corrupted unescaped-quote JSON. | `PARSE_ERROR_RAW_SNIPPET_MAX_CHARS = 500`; `strict=False` decoder; trailing-comma stripper respects JSON string escapes. |
| **Rank 3 — Prompt `run_tests` + Separate End-of-Loop Auto-Run** | Instruct the model in `format_tool_messages` (`Rules:` + user workflow) and `final_turn_note` to call `run_tests` after `search_replace`/`create_file` edits before `finish` (when `has_tests = true`). If a testable task ends without aborting (`stop_reason not in ABORT_STOP_REASONS` and `stop_reason != "pass"`) and either never called tests (`run_tests_calls == 0 and finish_tests_calls == 0`) or had edits since the last test run (`dirty_since_last_test`), auto-run `run_tests` once and record `auto_run_tests = true` and `end_of_loop_test_passed` as separate diagnostic fields that **never** rewrite `stop_reason` to `"pass"` and **never** set `passed = true` (only hidden offline `grade` counts). | `auto_run_tests` (`bool`), `end_of_loop_test_passed` (`bool \| null`), `run_tests_calls` (`int`), `finish_tests_calls` (`int`). |
| **Rank 4 — Align `TOOL_RESULT_MAX_LINES` with Prompt (`250`)** | Align `TOOL_RESULT_MAX_LINES` with `READ_FILE_MAX_LINES = 250` stated in `format_tool_messages` (`max 250 lines/call`). Raise companion char/turn-feedback caps so a single 250-line read (~8.5–11k chars) is not re-elided at low prompt utilization while still bounding pathological outputs. | `READ_FILE_MAX_LINES = TOOL_RESULT_MAX_LINES = 250` (`HEAD = 160`, `TAIL = 90`); `TOOL_RESULT_MAX_CHARS = 12,000`; `TURN_FEEDBACK_MAX_LINES = 300` (`HEAD = 200`, `TAIL = 100`); `TURN_FEEDBACK_MAX_CHARS = 16,000`; `TEST_OUTPUT_MAX_LINES = 80` (`HEAD = 30`, `TAIL = 50`), `TEST_OUTPUT_MAX_CHARS = 3,500` (unchanged). |

### 18.4 Unseen External-Repo Task Selection Rule (Stated Before Inspecting Any Diff)

Implemented in `bench/loop/select_v4.py` and verified by CPU tests in `bench/loop/test_pilot_pr_v4.py`:

- **Contamination Cutoff & Primary Source**:
  - `Qwen/Qwen3.6-35B-A3B` Hugging Face release timestamp: **`2026-04-15T05:59:19Z`** (source: `https://huggingface.co/Qwen/Qwen3.6-35B-A3B`, API field `createdAt: "2026-04-15T05:59:19.000Z"`; unsloth GGUF `https://huggingface.co/unsloth/Qwen3.6-35B-A3B-GGUF` `createdAt: "2026-04-16T04:31:31.000Z"`, `lastModified: "2026-04-20T12:42:25.000Z"`).
- **Phase 1 — Primary Repo (`more-itertools/more-itertools`) after `2026-11-17`**:
  - Window: `[2026-11-18T00:00:00Z, 2026-11-22T23:59:59Z]`; explicitly excludes the 7 frozen v3 dev PRs (`{1260, 1269, 1305, 1322, 1342, 1345, 1311}`).
  - Same numstat and offline `/usr/bin/bwrap` pass-at-merged / fail-at-base filters as v3 (first-parent PR merge `^Merge pull request #(\d+)\b` or squash `\(#(\d+)\)$`, no binary/rename/build/CI files, `>= 1` runtime `.py` + `>= 1` test `.py`, `2..8` files, `15..250` changed lines, offline `python3 -I -B -m unittest` in `/usr/bin/bwrap`).
  - **Observed Phase 1 Result (at pinned HEAD `e3f79f4fde5f7c107f70a20730b17240a05ba99b`, fetched 2026-11-22)**: **0 / 7 qualifying PRs** (1 post-`2026-11-17` PR, `#1366`, mechanically excluded for `no_test_py_changed`).
- **Phase 2 — Single Fallback Repo (Fixed Pre-Stated Priority Shortlist)**:
  - Because Phase 1 yielded fewer than 7 tasks (`needed = 7`), evaluate a fixed priority shortlist of pure-Python, zero-runtime-dependency, stdlib-`unittest` GitHub repositories stated before inspecting any candidate repo or diff, over `[2026-05-01T00:00:00Z, 2026-11-22T23:59:59Z]` with the exact same numstat and `/usr/bin/bwrap` filters:
    1. `python-markdown/markdown` (pinned HEAD `5609061bd3359e882b745de184ebfe5ef1c08011`): **1** bwrap-verified PR (`#1621`, `89` tests) on this host (`aj-Ryzen-AI-MAX`), where Debian/Ubuntu system package `python3-markdown` (`Markdown 3.10.2`, `/usr/lib/python3/dist-packages/markdown-3.10.2.dist-info`) is installed under `/usr` — which outer `/usr/bin/bwrap` bind-mounts read-only — registering the `markdown.extensions` entry points (including `footnotes`). On a host without `python3-markdown` in `/usr`, `select_v4.py` returns **0** verified PRs (`bwrap_verify_failed:merged_commit_tests_did_not_pass`, because `tests.test_apis.TestMarkdownBasics.testEntryPointExtension` raises `ModuleNotFoundError: footnotes`). Because outer `bwrap` bind-mounts `/usr`, the `python-markdown/markdown` (and `pyparsing/pyparsing`) audit count depends on host `/usr` packages and is informational only; **either way (`0` or `1`, both `< 7`), the frozen `lark-parser/lark` selection and task list are unchanged.**
    2. `pyparsing/pyparsing` (pinned HEAD `810199f89bf916590426e1c5cb3d612584f11a2f`): **3** bwrap-verified PRs (`#621`, `#652`, `#653`) on this host (informational audit count; fewer than 7).
    3. **`lark-parser/lark`** (pinned HEAD `9a4fb9c7458e8155636773a3cded0016d52516da`): **7** bwrap-verified PRs (`#1543`, `#1601`, `#1619`, `#1613`, `#1624`, `#1632`, `#1641`) $\rightarrow$ **SELECTED (`shortfall = 0`)**.
    4. `python/typing_extensions` (pinned HEAD `a2024556ab75799fbd2f41d1c2d114dd6372de12`) — not needed after #3 satisfied 7/7.
    5. `bottlepy/bottle` (pinned HEAD `aba0c1a7ee59ed851db001d100b6a792b54a94a3`) — not needed after #3 satisfied 7/7.
  - Local bare mirror stored read-only under `/data/datasets/item6-v4-repos/lark.git` (outside `strix-halo-lab`; `/data` is obscured by `--tmpfs` inside `/usr/bin/bwrap`).
- **Rule-Built Task Prompts (`tasks_item6_v4.build_v4_task_prompt`)**:
  - Built strictly by deterministic rule from verbatim GitHub/git metadata without viewing any merged diff and without hand-writing task prose:
    1. Linked non-PR GitHub issue title and body when linked (4/7: PR #1601 $\to$ Issue #1598, PR #1619 $\to$ Issue #1618, PR #1613 $\to$ Issue #1500, PR #1632 $\to$ Issue #1630).
    2. Linked PR title and body when a merge PR's body is strictly a `"Merges PR #M"` wrapper (1/7: PR #1624 $\to$ PR #1622).
    3. PR's own title and body (1/7: PR #1543).
    4. Verbatim git commit subject when GitHub returns HTTP 404 for the PR (1/7: PR #1641, `Fix InteractiveParser.copy() sharing the lexer thread with the original (#1641)`).
  - Mechanically strips HTML comments, replaces every fenced code block (```` ``` ```` / `~~~`) with `[code block removed]`, and redacts `104729`. Hidden tests, reference diffs, `merged_commit` SHAs, and seed `104729` never enter the loop.

### 18.5 Frozen v4 Unseen Task List (`bench/loop/tasks_item6_v4.py`, `lark-parser/lark`)

| Task ID | PR # | Merged (UTC) | Lines | Base Commit | Prompt Source | Test Command (`test_cmd`) | Expected Tests | Target Files |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `item6v4_pr1543` | #1543 | `2026-05-02T19:50:46Z` | 80 | `1573ca82a7b4af3a81919245e31a84a68b40f5b7` | PR #1543 | `python3 -m unittest tests.test_trees` | 22 | `docs/visitors.rst`, `lark/visitors.py`, `tests/test_trees.py` |
| `item6v4_pr1601` | #1601 | `2026-06-03T07:20:38Z` | 21 | `71ab62450cbb6f48d91a73b7e385aca5d4f6994f` | Issue #1598 | `python3 -m unittest tests.test_parser` | 1146 | `lark/parsers/xearley.py`, `tests/test_parser.py` |
| `item6v4_pr1619` | #1619 | `2026-07-19T07:41:12Z` | 28 | `5892df12bd6badd3ee555db3b2ae54a4e5911147` | Issue #1618 | `python3 -m unittest tests.test_grammar` | 27 | `lark/lexer.py`, `tests/test_grammar.py` |
| `item6v4_pr1613` | #1613 | `2026-08-25T11:32:09Z` | 30 | `51272c044e76f729238f5a93ee0337eac2f07396` | Issue #1500 | `python3 -m unittest tests.test_reconstructor` | 9 | `lark/reconstruct.py`, `tests/test_reconstructor.py` |
| `item6v4_pr1624` | #1624 | `2026-08-25T13:21:10Z` | 33 | `e1817787d2ed2a10477734b1f784cbc7eee8dfa4` | PR #1622 (via #1624) | `python3 -m unittest tests.test_trees` | 25 | `lark/visitors.py`, `tests/test_trees.py` |
| `item6v4_pr1632` | #1632 | `2026-08-26T19:56:53Z` | 30 | `bb11b5398b9a96865ff7c57e04739410273434df` | Issue #1630 | `python3 -m unittest tests.test_tree_templates` | 21 | `lark/tree_templates.py`, `tests/test_tree_templates.py` |
| `item6v4_pr1641` | #1641 | `2026-08-27T11:07:40Z` | 29 | `e7c2564859ba865618d81db1a5aa0b9a3ce5ec8e` | Commit subject (#1641; GitHub 404) | `python3 -m unittest tests.test_parser` | 1166 | `lark/parsers/lalr_interactive_parser.py`, `lark/parsers/lalr_parser_state.py`, `tests/test_parser.py` |

- All **7 of 7** tasks are testable (`has_tests = true`, `testable_total = 7`), merged between `2026-05-02` and `2026-08-27` (strictly post-`2026-04-15` Qwen3.6-35B-A3B release), and verified offline in `/usr/bin/bwrap` (pass at `merged_commit` with exact test counts, fail at `base_commit`) by `bench/loop/test_pilot_pr_v4.py`.

### 18.6 Two-Step Execution Protocol & Launchers

#### Step 1: Practice Run on the 7 v3 `more-itertools` Dev PRs (Pre-Declared as NOT Counting)

- **Declared in Advance as NOT Counting**:
  - Runs FIRST on the 7 retired v3 `more-itertools/more-itertools` dev PRs (`item6v3_pr1260`, `item6v3_pr1269`, `item6v3_pr1305`, `item6v3_pr1322`, `item6v3_pr1342`, `item6v3_pr1345`, `item6v3_pr1311`).
  - **No KEEP/DROP decision is computed, no Tier 2 Grok review is run, and the practice run is NEVER reported as a pilot result.**
  - Outputs stay in uncommitted `/tmp/lab-seats/item6-v4-practice/` (never written to `bench/loop/results/`).
- **Practice Pass Criteria (All 4 Required)**:
  1. Zero `context_overflow` across all 7 dev tasks,
  2. Zero `harness_failure` (`task_error`) across all 7 dev tasks,
  3. Telemetry fields (`reasoning_chars`, `content_chars`, `finish_reason`, plus `matched_turn`/`reply_hash` on any `turn_repeat_code` and `raw_snippet` on any `turn_parse_error`) present in every model-reply turn in `turn_events.jsonl`,
  4. At least one `run_tests` call (or `finish` test run / end-of-loop `auto_run_tests`) per task.
- **Budget & Ceiling**: Same per-task ceiling as v3 (`TASK_WALL_BUDGET = 617` s; total ceiling `CEILING_SECONDS = 4,320` s = 1.2 GPU-hours).
- **Post-Practice Freeze Rule**: Parameters may be adjusted after inspecting the practice run, **but any adjustments must be committed and frozen in a dated v4 pre-run note in `docs/item6-pilot.md` (verified pushed via `scripts/prereg-guard.sh --head docs/item6-pilot.md origin/main`) before launching Step 2 (the counted v4 run).**
- **Launcher**: `bench/loop/runs/item6-v4-practice/run.sh` (waits for PR merge and AJ's go):

```bash
WT=/home/aj/projects/strix-halo-lab EXPECT_HEAD=$(git -C /home/aj/projects/strix-halo-lab rev-parse origin/main) TARGET_REPO=/data/datasets/item6-v3-repos/more-itertools.git nohup bash /home/aj/projects/strix-halo-lab/bench/loop/runs/item6-v4-practice/run.sh >/dev/null 2>&1 &
```

#### Step 2: Counted Unseen v4 Pilot Run (`item6-pilot-v4` on `lark-parser/lark`)

- Runs **only** after Step 1 passes, the practice note and final v4 pre-run parameter freeze are committed and pushed to `origin/main`, and AJ gives a separate yes.
- **Launcher**: `bench/loop/runs/item6-pilot-v4/run.sh`:

```bash
WT=/home/aj/projects/strix-halo-lab EXPECT_HEAD=$(git -C /home/aj/projects/strix-halo-lab rev-parse origin/main) TARGET_REPO=/data/datasets/item6-v4-repos/lark.git nohup bash /home/aj/projects/strix-halo-lab/bench/loop/runs/item6-pilot-v4/run.sh >/dev/null 2>&1 &
```

- If the external bare mirror does not yet exist on disk, populate it read-only before launching:

```bash
mkdir -p /data/datasets/item6-v4-repos && git clone --bare https://github.com/lark-parser/lark.git /data/datasets/item6-v4-repos/lark.git
```



