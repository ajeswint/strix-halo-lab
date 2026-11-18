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
1. **Task Environment**: Each PR task is evaluated in a fresh, isolated git worktree (`git worktree add --detach <wt_dir> <base_commit>`) checked out strictly at its `base_commit`.
2. **Task Prompt Input**:
   - Repository background and working rules (no GPU load, stage named paths, measured numbers).
   - Task requirements extracted from original PR issue / title / instructions.
   - List of expected files to edit or add, plus their base contents at `base_commit`.
   - Verification commands to run (only when `has_tests = true`).
3. **Hidden Information Isolation (Leak Prevention)**:
   - The merged diff (`hidden_diff`), commit log after `base_commit`, and merge commit SHA (`merged_commit`) are strictly held out.
   - Task definitions strip hidden fields (`strip_hidden(task)`) before passing to the loop runner.
   - A prompt leak tripwire (`check_prompt_leak(prompt, task)`) runs on **every** prompt right before it is sent to the model inside `run_task_loop`, raising `AssertionError` if any hidden field or sentinel appears.
   - An exploding dictionary tripwire test (`bench/loop/test_pilot_pr.py`) enforces that accessing `hidden_diff` or `merged_commit` during prompt construction or in-loop execution immediately raises `AssertionError`.
   - Hidden diffs are read solely by the post-loop offline `grade` subcommand.

## 6. Output Evaluation & Review Gate

The output of the local loop is judged through the standing repository quality gate:
1. **Worktree Diff Capture (Uncommitted & New Files Included)**:
   - At the end of each task's loop (before removing the scratch worktree), the runner marks any untracked new files with intent-to-add (`git add -N .`) and records `git diff <base_commit>` against the working tree.
   - The per-PR diff is saved to `bench/loop/results/<label>.diffs/<task_id>.diff` and stored in `bench/loop/results/<label>.jsonl`.
2. **Tier 1: Automated Test Gate (Repo Tests Outrank the Judge)**:
   - For tasks with `has_tests = true`: The worktree test suite (`test_cmd`) is executed on CPU. If tests fail, the task is marked as a test failure regardless of model explanations.
   - For tasks with `has_tests = false`: `test_cmd` is `""` and `run_tests` is not executed; evaluation relies on Tier 2 and Tier 3.
3. **Tier 2: Adversarial Reviewer Gate (Grok 4.7 high, outside the GPU run)**:
   - After the GPU session ends (`scripts/llmctl.py bye`), the per-PR diffs written to `bench/loop/results/<label>.diffs/<task_id>.diff` are reviewed offline by the standing `adversarial-reviewer` seat (Grok 4.7 high, `.claude/agents/adversarial-reviewer.md`).
   - Review verdicts (`APPROVE`, `APPROVE-WITH-NITS`, or `REQUEST-CHANGES`) and AJ hand-fix line counts are recorded in a reviews JSON file (`bench/loop/results/<label>.reviews.json`, or passed via `--reviews-file` to `pilot_pr.py grade`).
   - If `REQUEST-CHANGES`, at most 1 repair turn is allowed on the local model with the reviewer's findings fed back.
4. **Tier 3: Offline Grading & Keep/Drop Computation (`pilot_pr.py grade`)**:
   - `python3 bench/loop/pilot_pr.py grade --label <label> [--reviews-file <path>]` computes test pass rates ($S_{\text{test}} / N_{\text{test}}$), diff overlap against `hidden_diff`, reviewer approval rates ($A_1 / N$, $A_{\text{final}} / N$), average AJ hand-fix lines per approved PR, and the pre-registered keep/drop verdict (`KEEP`, `DROP`, `INCONCLUSIVE`, or `PENDING_REVIEW` if reviewer verdicts have not yet been supplied), writing `bench/loop/results/<label>.grade.json`.

## 7. Metrics

1. **Test Pass Rate ($S_{\text{test}} / N_{\text{test}}$)**:
   - Fraction of testable tasks ($N_{\text{test}} = 6$) passing their automated test suite.
2. **First-Pass Approve Rate ($A_1 / N$)**:
   - Fraction of tasks ($N = 7$) receiving `APPROVE` or `APPROVE-WITH-NITS` on the initial turn.
3. **Final Approve Rate ($A_{\text{final}} / N$)**:
   - Fraction of tasks receiving approval after at most 1 repair turn.
4. **Accepted-Findings Rate**:
   - Ratio of valid, accepted reviewer findings to total reviewer findings.
5. **Wall Time per PR**:
   - Generation seconds, prompt evaluation seconds, test execution seconds, and clock wall time.
6. **AJ Hand-Fix Amount**:
   - Number of PRs requiring manual intervention, and total lines added/deleted in hand-fixes.

## 8. GPU Time and Resource Estimate

- **Hardware**: Framework Desktop, Ryzen AI Max+ 395, Radeon 8060S gfx1151 (108 GiB GTT).
- **Memory Footprint**: Qwen3.6-35B-A3B uses 22.4 GiB GTT. Preflight requires `llama-deepseek=inactive` and `READY`. Idle GTT headroom is >80 GiB.
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
- **Worst-Case Ceiling**:
  - Max $K=4$ turns + 1 review repair turn = 5 turns per task.
  - Worst-case GPU time for 7 PRs: $7 \times 5 \times 80 \text{ s} \approx 2,800 \text{ s} \approx 46.7 \text{ minutes} \approx \mathbf{0.78\text{ GPU-hours}}$.
  - Conservative ceiling: $< \mathbf{1.5\text{ GPU-hours}}$.

## 9. Keep / Drop Bars (Worth Scaling to Full Test)

The pilot's purpose is to decide whether local agentic loops on real PRs justify scaling to a larger, full-scale test (e.g. 20–30 PRs).

### Decision Partition

| Outcome | Criteria | Decision |
| :--- | :--- | :--- |
| **KEEP** (Scale to Full Test) | - Test Pass Rate on testable PRs $\ge 3/6$ ($50.0\%$); **AND**<br>- Final Reviewer Approval $\ge 3/7$ ($42.9\%$); **AND**<br>- Average AJ hand-fix $\le 20$ lines per approved PR. | Scale to full Roadmap Item 6 test. Local small model is viable for real repo tasks with execution feedback. |
| **DROP** (Do Not Scale) | - Test Pass Rate on testable PRs $< 2/6$ ($< 33.3\%$); **OR**<br>- Final Reviewer Approval $< 2/7$ ($< 28.6\%$). | Drop real-PR test line. The small model cannot generalize from synthetic puzzles to repo engineering. |
| **INCONCLUSIVE** | Intermediate result (e.g. exactly 2/6 test passes or 2/7 approvals). | Defaults to **DROP** per `measure` skill, unless AJ explicitly approves a bounded extension. |

### Worked Examples
- 4/6 tests pass, 4/7 approved, 0 hand-fix lines $\rightarrow$ **KEEP**
- 3/6 tests pass, 3/7 approved, 15 hand-fix lines $\rightarrow$ **KEEP**
- 1/6 tests pass, 2/7 approved $\rightarrow$ **DROP** (fails test pass threshold)
- 3/6 tests pass, 1/7 approved $\rightarrow$ **DROP** (fails reviewer threshold)
- 2/6 tests pass, 2/7 approved $\rightarrow$ **INCONCLUSIVE** (defaults to DROP)
