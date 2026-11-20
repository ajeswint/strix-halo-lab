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
- **Unchanged Protocol Elements**: No change to KEEP/DROP/INCONCLUSIVE bars (Section 9), mechanical PR selection (Section 4), isolation / outer `/usr/bin/bwrap` + read-only test file grading rules (Section 6), or the empty-diff automatic non-approval rule (Section 10).
- **Recorded Observation (Not Fixed Now) & Development-Set Caveat**:
  - v2 stopped first-request context overflow, but `item6_pr13` and `item6_pr14` still ended `context_overflow` at turns 8 and 7 as tool output accumulated in the conversation history. Those records stand unchanged and are not re-run or fixed for v2.
  - Restated from Section 11: v2 reruns the exact same 7 PRs whose v1 failures shaped these harness fixes (development-set re-test).
