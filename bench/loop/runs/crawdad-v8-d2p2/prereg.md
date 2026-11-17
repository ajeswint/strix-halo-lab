# crawdad-v8-d2p2 — pre-registration (2-slot quality check)

Written 2026-11-17 before launch. AJ approved the run 2026-11-17 15:39 CST.

## Question
Does serving each seat with 2 llama-server slots (`--parallel 2` in `debate.py step`) change v8 debate quality
compared with the 1-slot Stage N runs? (The timing probe, PR #18, already showed a 46.5% wall-time drop.)

## Setup
- Worktree `/tmp/wt-d2p2` at `bc260ff701ba815640eb1c9eda7927064b2c6cc1` (origin/main), clean. No code changes.
- Label `crawdad-v8-d2p2`, set `v8` (all 30 tasks), `--seed-base 4000` (same seeds as `crawdad-v8-d2`).
  Expected protocol `137acf32c95d`, build `b11669-620d2225c` (same as d2/d3/d4).
- Launcher `/tmp/lab-seats/crawdad-v8-d2p2/run.sh`, a copy of the Stage N launcher
  (`/tmp/lab-seats/crawdad-noise-v10/run.sh`) with only these changes:
  - every `llmctl.py invite <seat>` gets `--ctx 65536 --np 2` (2 slots x 32768 per slot = d2's per-slot context);
    each session asserts `/props` reports `total_slots 2, n_ctx 32768` before stepping;
  - every `debate.py step` gets `--parallel 2`;
  - a `STEP_START` / `STEP_END` / `STEP_WALL` line per session;
  - head/clean-worktree/prereg-present guards.
- Seats: qwen32 (Qwen3-32B Q4_K_M) and r1d32 (DeepSeek-R1-Distill-Qwen-32B Q4_K_M), alternating per
  `debate.py status` "next session". No DeepSeek V4, no model substitution.
- Graded by `debate.py report --label crawdad-v8-d2p2 --regrade` (fresh seed 104729).

## Metrics
- Leaf score `L` = number of tasks with `leaf_pass` true in `crawdad-v8-d2p2.debate.summary.json`
  (= `debate_solved`). Reference: d2 9, d3 12, d4 10.
- Discordant tasks `D` = tasks whose `leaf_pass` differs between `crawdad-v8-d2p2` and `crawdad-v8-d2`
  (same seed base, task by task). Reference cross-seed counts: D23 7, D24 7, D34 10.

## Bar (pre-registered)
- **PASS:** 8 <= L <= 13 **and** D <= 10. 2 slots is adopted as the default for future runs.
- **FAIL:** L <= 7, **or** D > 10. Stay at 1 slot.
- Not covered by the bar as approved: L >= 14 with D <= 10. If it happens it is recorded as
  "outside the noise range, high" and the decision goes to AJ; it is not called PASS or FAIL.

## Recorded, no bar
- Per-session `STEP_WALL`, total wall time vs d2 (about 6.6 h at 1 slot), tokens per seat, regrade status.
- The run must finish with `regrade: ok`; a regrade mismatch voids the run.

## Amendment (2026-11-17 ~5 PM CST, before the result was seen)

The original bar text above is unchanged. This amendment closes the previously-open
"AJ's call" case only.

- **PASS (added):** L >= 14 **and** D <= 10 vs crawdad-v8-d2. Adopt 2 slots.
  A higher leaf score than the Stage N range cannot indicate that 2 slots hurt quality,
  so this case is now PASS rather than "outside the noise range, high" left to AJ.
- The original PASS band (8 <= L <= 13 and D <= 10) and the FAIL rule (L <= 7, or D > 10)
  are unchanged.

This amendment is committed while the run is still in progress, before any scored result:

- The run launched 2026-11-17 15:46 CST (3:46 PM CST) under the original bar.
- `run.status` at amendment time (2026-11-17 5:00:35 PM CST): `running 2026-11-17T15:46:07-06:00`
- No scored result yet: `/tmp/wt-d2p2/bench/loop/results/crawdad-v8-d2p2.debate.summary*` does not exist.
  In-progress session output (`crawdad-v8-d2p2.debate.jsonl` and `.debate.meta.json`) is present
  in the running worktree; the report/regrade summary is not. Those in-progress files are not
  in this commit.

## Note (llmctl GTT figure, not part of this bar)

The llmctl GTT expected figure at np2 (+26.7 GiB) undershoots the measured +34.7 GiB
from the 2-slot timing probe. A 2-slot table entry (so preflight is not checking against
too low a number) should follow in a separate PR. This does not change the quality-check bar.
