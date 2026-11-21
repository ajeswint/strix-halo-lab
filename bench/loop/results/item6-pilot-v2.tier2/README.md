# Item 6 Pilot v2: Tier 2 Raw Review Artifacts

This directory contains the raw artifacts and provenance records for the Roadmap Item 6 pilot v2 Tier 2 blind adversarial reviews (`grok-4.7-high`).

## Layout

- `run.sh`: The exact review runner script executed in `/tmp/lab-seats/item6-v2-tier2`.
  - Invocation: `cursor-agent -p --trust --mode ask --model grok-4.7-high --output-format json "Read the file packet.md in the current directory in full and follow its instructions exactly. Read no other file and use no other tool."`
  - Runs with ask (read-only) mode, fresh context per task (no `--resume`), in an isolated working directory containing only `packet.md`.
- `mkpackets.py`: Packet generator script used to build each blind `packet.md` from `tasks_item6.strip_hidden(t)`, `item6-pilot-v2.jsonl`, and `item6-pilot-v2.diffs/<task>.diff` (with no hidden diffs, merged SHAs, reference solutions, or grading seed). Running `python3 bench/loop/results/item6-pilot-v2.tier2/mkpackets.py check` from repo root confirms it regenerates all 5 v1 packets under `bench/loop/results/item6-pilot.tier2/success/` byte-for-byte identically.
- `tier2-sessions.json`: Metadata for the review executions (task ID, unique session ID, request ID, duration in milliseconds, exit status, timestamp).
- `success/`: Completed review run outputs from Nov 20, 2026 (18:59–19:01 CST) across all 3 non-empty v2 diffs (`item6_pr06`, `item6_pr08`, `item6_pr15`):
  - `packet.md`: Blind review input packet provided to the reviewer.
  - `out.json`: Verbatim raw JSON response from `cursor-agent`.
  - `err.log`: Standard error output from `cursor-agent` (empty, 0 bytes).
  - `rc.txt`: Exit code (`rc=0`) and completion timestamp.

## Review Protocol & Task Coverage

- **Reviewed Tasks (3)**: `item6_pr06`, `item6_pr08`, `item6_pr15`. All three completed with `rc=0`, `is_error=false`, `tamper=false`, and verdict `REQUEST-CHANGES` (`hand_fix_lines`: 100, 55, 22 respectively).
- **Omitted Tasks (4)**: Per Section 10 of `docs/item6-pilot.md` (Nov 18 amendment, unchanged in Sections 11–12), tasks with empty diffs (`item6_pr13`, `item6_pr14`, `item6_pr16` due to `context_overflow`, and `item6_pr20` due to `repeat_code`) receive automatic non-approval without Grok review, and their hand-fix lines are excluded from grading.
- **Model & Session Evidence**: Although `out.json` does not echo the model name in its payload keys, the model and reasoning tier (`grok-4.7-high`) are pinned by `run.sh`, and each task exhibits a distinct `session_id` in `tier2-sessions.json`, verifying fresh, independent sessions.
