# Item 6 Pilot: Real-PR Test Results (post-run)

Final post-run results for Roadmap Item 6 pilot (`docs/item6-pilot.md`), evaluated in accordance with the pre-registered protocol and the November 18, 2026 amendment.

## 1. Executive Summary & Decision

- **Pre-Registered Decision**: **DROP** (Do Not Scale).
- **Primary Thresholds**:
  - **Authoritative Test Pass Rate**: **0 / 6** (0.0%). Pre-registered DROP threshold is $< 2/6$ ($< 33.3\%$).
  - **Reviewer Approval Rate**: **0 / 7** (0.0%). Pre-registered DROP threshold is $< 2/7$ ($< 28.6\%$).
  - **Reviewer Hand-Fix Lines**: **n/a (no approved PRs)**. In the frozen v1 `bench/loop/results/item6-pilot.grade.json`, `avg_hand_fix_lines_per_approved` appears as `0.0` solely because the v1 grader emitted `0.0` on a zero denominator of approved PRs (subsequently fixed in `bench/loop/pilot_pr.py` for v2 to emit `null`). Among the 5 non-empty diffs reviewed by Grok 4.7 high, reported hand-fix lines were **800, 194, 1858, 170, and 30**, all well above the $\le 20$ lines bar.
- **Decision Partition**: Both DROP criteria are independently met. The pilot conclusively demonstrates that the single-model local agentic loop (`Qwen3.6-35B-A3B`) on real repository pull requests does not justify scaling to a full benchmark without a fundamental architectural redesign.

## 2. Hardware, Model, and Serving Configuration

- **Hardware**: Framework Desktop, AMD Ryzen AI Max+ 395, Radeon 8060S gfx1151 (Strix Halo unified memory, 108 GiB GTT).
- **Model**: `Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf` (file size 20.8 GiB, 22.4 GiB GTT footprint delta).
- **Serving Configuration**: `scripts/llmctl.py invite qwen --ctx 65536 --np 2` (Vulkan backend `build-vk`, 2 parallel slots $\times$ 32,768 context tokens per slot). The serving configuration remained strictly unchanged throughout all runs.
- **Sampling Parameters**: `temperature`: 0.6, `top_p`: 0.95, `top_k`: 20, `reasoning_budget`: 4,096 tokens, `max_tokens`: 8,192 tokens per completion, `task_budget`: 32,768 completion tokens per task.

## 3. Run Execution and Provenance

The evaluation was executed in two phases due to a context overflow on task `item6_pr15`:

1. **Run 1 (Initial Run at HEAD `86cbbe8`)**:
   - Executed tasks `item6_pr06`, `item6_pr08`, `item6_pr13`, and `item6_pr14`.
   - On `item6_pr15`, an unexpected first-turn prompt size of 38,364 tokens exceeded the 32,768-token per-slot context window, triggering an unhandled HTTP 400 exception that aborted the run.
   - Run 1 GPU wall time: **1,669 seconds**. The four completed task records were frozen unmodified.
2. **Nov 18 Amendment & Resume Run (at HEAD `9115f8b`, PR #22)**:
   - Added `context_overflow` error handling and resume execution (`RESUME=1`).
   - Resumed execution on remaining tasks: `item6_pr15`, `item6_pr16`, and `item6_pr20`.
   - `item6_pr15` was caught immediately as `context_overflow` (0.23 s, 0 completion tokens) and recorded an empty diff.
   - Resume run ended cleanly at 11:28:24 PM CST on November 18, 2026, with exit code 0 and wall time of **790 seconds**. The model server was released immediately via `scripts/llmctl.py bye`.
3. **Total GPU Resource Utilization**:
   - Total GPU wall time: $1,669\text{ s} + 790\text{ s} = \mathbf{2,459\text{ seconds}}$ (~41.0 minutes).
   - This remained well within the pre-registered worst-case ceiling of $\mathbf{4,320\text{ seconds}}$ (1.2 hours).

## 4. Official Grade and Per-Task Results

The authoritative grade was computed via `python3 bench/loop/pilot_pr.py grade --label item6-pilot` in `/tmp/wt-item6-run2` at HEAD `9115f8b` with `reviews_complete: true` (exit code 0).

A single official grade file is committed: [`bench/loop/results/item6-pilot.grade.json`](../bench/loop/results/item6-pilot.grade.json). An earlier, superseded Nov 18 pre-review grade file (`reviews_complete: false`) was overwritten during grading in the run worktree and was not committed.

### Summary Metrics

| Metric | Result | Target (KEEP) | Threshold (DROP) |
| :--- | :--- | :--- | :--- |
| **Tasks Evaluated** | 7 | 7 | 7 |
| **Testable Tasks** | 6 | — | — |
| **Authoritative Test Passes** | **0 / 6** (0.0%) | $\ge 3/6$ (50.0%) | $< 2/6$ (< 33.3%) |
| **Final Reviewer Approvals** | **0 / 7** (0.0%) | $\ge 3/7$ (42.9%) | $< 2/7$ (< 28.6%) |
| **Avg Hand-Fix Lines / Approved** | **n/a (no approved PRs)** | $\le 20$ lines | $> 20$ lines |
| **Tamper Detected** | **0 / 7** (0.0%) | 0 | $> 0$ |
| **Final Decision** | **DROP** | **KEEP** | **DROP** |

### Per-Task Evaluation Breakdown

| Task ID | PR # | Description | Run / Commit | Testable | Test Passed | Final Verdict | Hand-Fix Lines | Stop Reason | Turns | Tokens | Wall (s) | Local Diff Lines | Hidden Jaccard | Tamper |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `item6_pr06` | #6 | Recover VERDICT/CONFIDENCE | Run 1 (`86cbbe8`) | Yes | FAIL | REQUEST-CHANGES | 800 | `repeat_error` | 3 | 21,130 | 390.70 | 718 | 0.0054 | False |
| `item6_pr08` | #8 | Antigravity writer seat docs/scripts | Run 1 (`86cbbe8`) | Yes | FAIL | REQUEST-CHANGES | 194 | `max_turns` | 4 | 28,267 | 595.75 | 619 | 0.0844 | False |
| `item6_pr13` | #13 | CRAwDAD noise floor / v10 tasks | Run 1 (`86cbbe8`) | Yes | FAIL | NON-APPROVAL (auto) | n/a (excluded) | `repeat_error` | 2 | 16,384 | 316.39 | 0 | 0.0000 | False |
| `item6_pr14` | #14 | README split (move-only) | Run 1 (`86cbbe8`) | Yes | FAIL | REQUEST-CHANGES | 1858 | `repeat_error` | 3 | 20,022 | 358.26 | 1,909 | 0.4906 | False |
| `item6_pr15` | #15 | Stale-line fixes & writer roster | Resume (`9115f8b`) | No | n/a | NON-APPROVAL (auto) | n/a (excluded) | `context_overflow` | 1 | 0 | 0.23 | 0 | 0.0000 | False |
| `item6_pr16` | #16 | crawdad-ground-v1 loop & spec | Resume (`9115f8b`) | Yes | FAIL | REQUEST-CHANGES | 170 | `repeat_error` | 3 | 21,773 | 398.08 | 390 | 0.0079 | False |
| `item6_pr20` | #20 | Launcher prereg push guard | Resume (`9115f8b`) | Yes | FAIL | REQUEST-CHANGES | 30 | `max_turns` | 4 | 21,462 | 384.05 | 190 | 0.0181 | False |

## 5. Tier 2 Blind Adversarial Reviews

Offline adversarial reviews were conducted by `grok-4.7-high` using `cursor-agent` in blind ask mode.

### Review Protocol & Assembly

- **Runner Command**: As recorded in [`bench/loop/results/item6-pilot.tier2/run.sh`](../bench/loop/results/item6-pilot.tier2/run.sh):
  ```bash
  cursor-agent -p --trust --mode ask --model grok-4.7-high --output-format json \
    "Read the file packet.md in the current directory in full and follow its instructions exactly. Read no other file and use no other tool."
  ```
- **Session Isolation**: Each task was reviewed in an isolated working directory containing only `packet.md` without repo access, git history, or knowledge of the merged solutions (`hidden_diff`). Fresh, independent sessions were verified by distinct `session_id`s in [`tier2-sessions.json`](../bench/loop/results/item6-pilot.tier2/tier2-sessions.json).
- **Automatic Non-Approvals (PR #13 and PR #15)**: Section 10 of `docs/item6-pilot.md` explicitly specifies:
  > *"A task with an empty diff (including context_overflow, and item6_pr13's empty diff) is an automatic non-approval with no Grok review. In offline grading (`pilot_pr.py grade`), `hand_fix_lines` is n/a (`None`) and excluded from the hand-fix average."*
  Because `item6_pr13` and `item6_pr15` produced empty diffs, neither task received a Grok review packet; both were scored automatically as `NON-APPROVAL` with excluded hand-fix lines. Even if both tasks had hypothetically been approved, the 0/6 authoritative test pass rate independently mandates DROP.

### Execution History and Failed Attempts

Raw artifacts for all review attempts are preserved under [`bench/loop/results/item6-pilot.tier2/`](../bench/loop/results/item6-pilot.tier2/):
1. **Attempt 1 (Nov 18, 23:46 CST, `attempt1-trust-prompt/`)**: `cursor-agent` halted immediately on `item6_pr06`, `item6_pr08`, `item6_pr16`, and `item6_pr20` with exit code 1 because the directory was not yet marked trusted and `--trust` was omitted; `item6_pr14` exited with code 126 (`/usr/bin/timeout: Argument list too long`). Zero usable reviews were produced.
2. **Attempt 2 (Nov 18, 23:47 CST, `attempt2-usage-limit/`)**: `cursor-agent` halted immediately with `ActionRequiredError: Weekly usage limit reached`. No credits were purchased, and no usable reviews were produced.
3. **Successful Execution (Nov 20, 11:37–11:42 AM CST, `success/`)**: Launched upon weekly quota reset with `--trust`. All 5 tasks completed cleanly with exit code 0 within 65 to 265 seconds. This was the sole set of completed reviews and did not overwrite or replace any earlier verdicts.

## 6. Failure Mode Analysis

The pilot surfaced several recurring failure patterns in the small-model local loop:

1. **Context Sizing Underestimate (`item6_pr15`)**:
   - Pre-registration estimated prompt sizes at 4,000–8,000 tokens. However, tasks requiring context from multiple repository files inflated Turn 0 prompts up to 38,364 tokens. Against a 32,768-token slot limit (`--ctx 65536 --np 2`), llama-server immediately rejected the request with HTTP 400.
2. **Diff Formatting & Truncation (`item6_pr06`, `item6_pr13`)**:
   - The model frequently failed to adhere to the required unified diff / edit format.
   - On `item6_pr06`, the model emitted an unclosed string at Turn 0, creating a syntax error that deleted the entire implementation of `debate.py`.
   - On `item6_pr13`, patch application repeatedly failed, resulting in an empty final diff (`local_diff_lines: 0`).
3. **Destructive Whole-File Rewrites (`item6_pr06`, `item6_pr14`)**:
   - Rather than making localized surgical edits, the model rewrote extensive portions of target files.
   - On `item6_pr14` (README move-only task), the model deleted `README.md` and created an 11-line stub `docs/setup-hardware.md`, omitting the other 7 required documentation files and producing a 1,909-line diff that failed all move checks.
4. **Error Adaptation Stalls (`repeat_error` on 4 of 7 tasks)**:
   - When automated test failures were fed back into subsequent turns, the model repeatedly regenerated identical or similarly flawed code, triggering early loop termination on `repeat_error` (PRs #6, #13, #14, #16).
5. **Logic Inversion & Shell Permissions (`item6_pr20`)**:
   - On the launcher guard script, the model inverted `git ls-files -v` logic (rejecting valid cached tags `^[HS]` and accepting `h`/`s`), mishandled pipelines under `set -o pipefail`, and failed to mark the new shell script executable (`100644`), causing test failures before logic could even be evaluated.

## 7. Scoping and Methodological Caveats

### What DROP Means
The DROP decision confirms the pre-registered hypothesis test:
- The single-model local agentic loop with execution test feedback under this specific harness (`Qwen3.6-35B-A3B`, `--ctx 65536 --np 2`, 32k context per slot, single-file unified diff generation) is **not viable for real repository engineering tasks** and **should not be scaled** to a 20–30 PR benchmark.

### What DROP Does Not Mean (Caveats)
- **Confounded Factors**: The sample size is limited ($n = 7$), restricted to a single model checkpoint and quantization (`Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf`), and tied to a specific harness. The model's reasoning capabilities are heavily confounded with harness-level design choices, including the rigid unified diff edit format, prompt construction strategy, scratch repository isolation, and the 32k context-window ceiling.
- **Not a General Capability Verdict**: This outcome indicates that this local setup cannot bridge the gap between synthetic puzzles (where it scored 24–29/30) and multi-file repository maintenance without significant infrastructure changes (e.g., larger per-slot context, structured tool calling instead of raw diff output, or multi-model review setups).
