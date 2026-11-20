# Item 6 Pilot: Tier 2 Raw Review Artifacts

This directory contains the raw artifacts and provenance records for the Roadmap Item 6 pilot Tier 2 blind adversarial reviews (`grok-4.7-high`).

## Layout

- `run.sh`: The exact review runner script executed in `/tmp/lab-seats/item6-tier2`.
  - Invocation: `cursor-agent -p --trust --mode ask --model grok-4.7-high --output-format json "Read the file packet.md in the current directory in full and follow its instructions exactly. Read no other file and use no other tool."`
  - Runs with ask (read-only) mode, fresh context per task (no `--resume`), in an isolated working directory containing only `packet.md`.
- `tier2-sessions.json`: Metadata for the successful review executions (task ID, unique session ID, request ID, duration in milliseconds, exit status, timestamp).
- `success/`: Successful review run outputs from Nov 20, 2026 (11:37–11:42 AM CST) across all 5 reviewed tasks (`item6_pr06`, `item6_pr08`, `item6_pr14`, `item6_pr16`, `item6_pr20`):
  - `packet.md`: Blind review input packet provided to the reviewer.
  - `out.json`: Verbatim raw JSON response from `cursor-agent`.
  - `err.log`: Standard error output from `cursor-agent`.
  - `rc.txt`: Exit code and completion timestamp.
- `attempt1-trust-prompt/`: First execution attempt on Nov 18, 2026 (23:46 CST). Failed immediately with exit code 1 because `cursor-agent` paused for a workspace-trust confirmation (`--trust` was omitted). Produced zero usable reviews.
- `attempt2-usage-limit/`: Second execution attempt on Nov 18, 2026 (~23:47 CST). Failed immediately with exit code 1 across all tasks due to reaching Cursor's weekly usage quota (`ActionRequiredError: Weekly usage limit reached`). No credits were purchased. Produced zero usable reviews.

## Review Protocol & Task Coverage

- **Reviewed Tasks (5)**: `item6_pr06`, `item6_pr08`, `item6_pr14`, `item6_pr16`, `item6_pr20`.
- **Omitted Tasks (2)**: Per Section 10 of `docs/item6-pilot.md` (Nov 18 amendment), tasks with empty diffs (`item6_pr13` and `item6_pr15`, the latter due to `context_overflow`) receive automatic non-approval without Grok review, and their hand-fix lines are excluded from grading.
- **Model & Session Evidence**: Although `out.json` does not echo the model name in its payload keys, the model and reasoning tier (`grok-4.7-high`) are pinned by `run.sh`, and each task exhibits a distinct `session_id` in `tier2-sessions.json`, verifying fresh, independent sessions.
