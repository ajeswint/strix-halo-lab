## CRAwDAD debate runner (2026-10-15, no GPU)

`bench/loop/debate.py` runs the crawdad-qd-v2 tree on code tasks (protocol and deliberate deviations from the paper code in its docstring; paper notes in `docs/crawdad-notes.md`). It is not a measurement and keeps or drops nothing until a pre-run states a question and a bar.
- Seats: Qwen3-32B (`qwen32`) and DeepSeek-R1-Distill-Qwen-32B (`r1d32`), one resident at a time. A balanced seeded coin (seed 42, half the tasks each) picks the first speaker. R1 is a solo answer from both seats (the exclusive-solve check the paper never runs; the coin's seat's R1 opens the debate), R2 the critic, R3 defend or be persuaded, R4 the last word. `VERDICT: accept` ends the debate; the module standing then is the leaf, graded once on fresh seed 104729. No test result reaches a model. A parse failure is a failure, never a coin flip.
- Reasoning budget 2,048 tokens (user, 2026-10-15) through the per-request `reasoning_budget_tokens` with a budget message, inside `max_tokens` 6,144. In v0.7.0 the per-request field takes effect only when the chat template exposes thinking tags (`tools/server/server-common.cpp`, the `thinking_end_tags` check). Whether both 32B templates do is unverified until a GPU stage reads `reasoning_chars` against the cap.
- A set takes five llmctl sessions, alternating seats: `step` asks every reply the served seat owes, resumes after a failure, and refuses another set, task list, protocol hash, llama.cpp build or model file than the run started with. Procedure: `llm-serve` skill, "CRAwDAD debate".
- Tested: `debate.py --selftest`, 34 checks against scripted seats and the real bwrap grader on six v1 tasks, passing on 6 of 6 runs: parsing, every leaf type, history labels and order, the thinking trace and the second seat's solo never in a debate prompt, the request body, the guards, resume after a mid-step failure, five sessions from either seat. Server-side checks (thinking tags in the two templates, the budget in effect, verdict-line compliance, turn times, tg at depth): the GPU smoke below, PASS 2026-10-18.
- `bench/loop/check_tasks.py`: v6's task checks as a script (v6 passes 30/30; a part file with three planted defects fails on each). The `llm-serve` skill's DeepSeek fix-stage example moved from v7 to v8, because registering v7 would let its gate pass.

## CRAwDAD debate runner: GPU smoke on 2 spent v1 tasks (pre-run)

Stated before any GPU use (2026-10-18; the user said draft and execute, and waived the Grok round for this one). Not a measurement and not a keep/drop: it answers only what the stub selftest cannot, before v7 is written and before a real CRAwDAD pre-run sets a bar. v1 is spent, so nothing sealed is used.
- Question: does `debate.py` work end to end against the two real servers? That covers four things: the 2,048-token reasoning budget is in effect for each seat, replies end in code rather than running out of tokens, the verdict lines parse, and stored grades reproduce. Second question: what does a turn cost (gen_s, tg at the prompt depths reached)?
- Tasks: `v1_20_determinant` (both models solved it in loop-v1) and `v1_24_add_duration` (neither did in 8 attempts, so disagreement and rounds R3/R4 are likely). The balanced coin gives each seat the first word on one. Label `crawdad-smoke-v1`.
- Code as of this commit: protocol `137acf32c95d`, unchanged. Rows gain `budget_hit`, true when the thinking trace ends with `BUDGET_MESSAGE`. llama.cpp v0.7.0 injects that message only when the template exposes thinking tags and the budget forces the end tag (`common/sampling.cpp`, `tools/server/server-common.cpp:1447`). Selftest 35 checks OK.
- Procedure: `llm-serve` skill, "CRAwDAD debate", with `--label crawdad-smoke-v1 --set v1 --tasks v1_20_determinant,v1_24_add_duration` on the first step. Endpoint defaults: vk, ctx 32768, 1 slot, `--parallel 1`. Up to 5 sessions, one model resident, each a single background chain with `bye` after a successful invite. `llmctl run` at its defaults (8 GiB MemoryMax, 16 GiB AS); each grade's child is capped at 1 GiB AS. Memory: +26.7 / +26.8 GiB GTT over the 7.3 GiB idle at first load.
- Cost: at most 10 replies, each at most 6,144 tokens, ~9 min at the first load's 11.1 t/s, so <= ~1.5 h of decode plus up to 5 loads.
- Pass, every line has to hold:
  1. Every reply has `finish` = `stop`. A `length` means the budget did not leave room for the answer.
  2. Every R1 has a code block, and no task ends as `no_code` or `parse_fail`.
  3. Each seat has at least one reply with `budget_hit` true, which shows the budget is in effect for that template. If a seat's thinking never reached 2,048 tokens, that line is unanswered rather than failed, and the report says so.
  4. `think_leak` is false on every reply.
  5. `report --regrade` exits 0.
- Recorded, no bar: gen_s, completion_tokens, reasoning_chars, prompt_n and tg_tps per reply; session count; GTT per session (llmctl note); `memory.peak` per run.
- On a fail: the cause is fixed in the runner or the server config, and the smoke repeats under a new label. Solve counts mean nothing here, with n = 2 on a spent set; they tune nothing and are not compared with loop-v1.

### Result (2026-10-18, at 974d684): PASS on every line

Five sessions (llmctl 25-29), 9 replies, both tasks reached a leaf. Results are in `bench/loop/results/crawdad-smoke-v1.debate.{jsonl,meta.json,summary.json}`, build b11669-620d2225c, protocol `137acf32c95d`.
1. `finish` = `stop` on 9 of 9.
2. Every R1 has code, and every R2-R4 reply has a verdict line (reject with code, or accept). No `no_code` and no `parse_fail`.
3. `budget_hit` is true on 3 of 5 Qwen3-32B replies (both solos and none of its 3 debate replies) and on 5 of 5 R1-Distill replies. So the per-request budget is in effect for both templates. A reply that hit the cap still ended with code: completion 2,378-3,459 tokens, so 330-1,411 tokens past the 2,048 budget (the forced message and end tag included), and visible content of 1,172-5,256 chars.
4. `think_leak` is false on 9 of 9.
5. `report --regrade`: `ok`, exit 0.

Recorded (one run, no spread):
- Decode: tg 10.88-11.27 t/s. The lowest is at the deepest prompt (2,595 tokens, Qwen R3), so tg at depth is about 3% below the shallow rate up to there. A reply took 117-317 s. Thinking: Qwen 2,252-9,443 chars, R1-Distill 7,533-8,374.
- Sessions: 33 min 20 s wall from the first invite to the last bye, of which 32 min was decode (1,920.9 s). Loads and swaps added about 1.3 min over 5 sessions, with the files warm in the page cache.
- Memory: GTT +26.7 / +26.8 GiB over 7.4 GiB idle, matching `gtt_need`, and back to 7.4 GiB after every bye. Client `memory.peak` 38-39 MiB.
- Leaves: add_duration ended at R3 accept (Qwen, defending, accepted R1-Distill's module) and determinant at R4 max_rounds.

Seen, not measured (n = 2, a spent set):
- Qwen's R3 `accept` reply also carried a code block, which the verdict rules say to omit. `walk` keeps the previous standing module on accept (`debate.py`, the `accept` branch), so the leaf is R1-Distill's R2 module, as designed. Compliance with "accept: write no code" is not perfect.
- determinant: Qwen's solo passed and R1-Distill's failed. With R1-Distill first, Qwen's R2 critic rejected with a new module that failed, and the leaf failed. So the debate lost a solve one seat had alone. The summary counts this case as `qwen32_only` 1 and `debate_solved` 0. It is a single case and says nothing about rates, but it is the case the exclusive-solve check exists to catch, and the real pre-run should name it.
- Cost model for the real pre-run: at about 3.6 min per reply and 5-9 replies per task, a 30-task set is roughly 9-16 h of decode.

Next: v7, rewritten inline with no agents and every reference and test run under `prlimit --as=4294967296`, then the CRAwDAD pre-run with a question and a bar. Each needs the user's go.

## v7 tasks: held-out set for the CRAwDAD debate (batch 1 of 3, 2026-10-18)

`bench/loop/tasks_v7.py`, registered as `v7` in `run.SETS`. It replaces the v7 lost in the 2026-10-15 crash. Written inline in one session by Claude, with no subagents. Every check ran under `prlimit --as=4294967296`, and no model ran.
- Batch 1 is v7_01-10, seeds 7001-7010. The buckets are those of v6: formats (01 packbits, 02 ini_strict, 03 semver_order), number theory and combinatorics (04 partition_rank, 05 digit_rules), graphs and geometry (06 route_lexmin, 07 rect_union), simulation and DP (08 bowling_frames, 09 paint_posts, 10 justify_lines). Tasks 11-30 append at the marker in the file, and v7_01-10 stay frozen from now on, so a 10-task probe stays the first 10 rows of a 30-task run.
- Unaimed: no family was taken from a stored failure. Difficulty is a judgement for the debate pair, not a measurement. Specs are exact, at 1,300-2,600 chars, and the algorithms fit a 2,048-token thinking budget (DP, Dijkstra, coordinate compression, digit DP). There is no 10^18-scale number theory of the v4-v6 kind. Whether this gives headroom in both directions is for the CRAwDAD pre-run's probe to show.
- Each test file has one `random.seed(N)`. Seeded cases are checked against an oracle built differently from the reference:
  - 01: groupby encoder, and packet streams built with their expansion
  - 02: a generator that serializes a known dict
  - 03: a `cmp_to_key` comparator
  - 04: brute enumeration, Euler's pentagonal recurrence, and a distinct-parts product
  - 05: brute force, and a forward tight-flag DP
  - 06: simple-path DFS, an O(n^2) Dijkstra, and a grid with known C(118, 59)
  - 07: unit-grid counting under affine maps
  - 08: frame generator
  - 09: brute force over all plans, and a forward DP
  - 10: properties
- Checks: `check_tasks.py --set v7` 10/10 OK. `run.py --selftest --set v7` and `agent.py --selftest --set v7` OK. `debate.py --selftest` OK (protocol unchanged). Negative control: 20 single-line mutants of the references (two per task, each a plausible bug) graded against the tests. 19 caught; the 20th is equivalent (a zero-area rectangle's difference-array marks cancel), so 19 of 19 non-equivalent mutants were caught. The script is in the session scratchpad, not the repo.
- Two entry-point clashes found by the checker were renamed: `parse_ini` (v3) became `parse_ini_strict`, and `justify` (v0) became `justify_lines`. Two example values in v7_05's prompt were wrong in the draft and were recomputed before the checker ran. The 10^18 count, 168856464709124011, matches the closed form 1 + (9^19 - 9) / 8.
- Sealed from 6680747: no prompt, test or reference edits on v7_01-10, except a defect found by a cold review, which is fixed and recorded here before any model sees the set.
- Cold review, 2026-10-18, allowed by the user and capped:
  - Setup: ten solvers, one per task, `red-team` agent type (tools Read/Grep/Glob only: no Bash, no writes, so no code ran), model Sonnet. Each got its prompt verbatim with "use no tools, read no file", and returned one module plus a list of ambiguities. All ten reported `TOOLS USED: none`, at 13-16k tokens each.
  - Grading: the code was graded by `run.grade`, whose child is capped, at the visible seed, the fresh seed 104729 and seeds 1-3. 10 of 10 passed on all five, each on the first attempt. No defect, no prompt edit, and the seal stands.
  - Listed ambiguities that a test depends on: v7_02's `a=1\r\r` (only one "\r" is dropped), v7_05's out-of-range lo or hi raising before the lo > hi shortcut, and v7_09's rows given as tuples being rejected. Each is resolved by explicit prompt text ("loses that one \r", the argument ranges, "list of lists"), and each solver took that reading. The other listed points are not tested: subclasses of str, list or int, more than 200 rectangles, n > 300, ints past 4,300 digits.
  - The solver code is kept in the session scratchpad, not the repo.

## CRAwDAD probe on v7_01-10 (pre-run)

Stated before any GPU session (2026-10-18; the user's go, and the bar is the user's, relayed from the review that accepted 6680747). Not a keep/drop of the debate. It decides how v7 tasks 11-30 are written. The set is v7_01-10 as committed in 6680747, unchanged after the cold review.
- Label `crawdad-v7-probe`, `--set v7 --tasks v7_01_packbits,v7_02_ini_strict,v7_03_semver_order,v7_04_partition_rank,v7_05_digit_rules,v7_06_route_lexmin,v7_07_rect_union,v7_08_bowling_frames,v7_09_paint_posts,v7_10_justify_lines` on the first step. `coin()` shuffles that list (seed 42, five tasks per seat first), and `step` refuses a later change of the list, so this label cannot grow into the 30-task run; that run is a later label.
- Code: `debate.py` protocol `137acf32c95d`, as in the smoke run, with seats `qwen32` / `r1d32` at the endpoint defaults (vk, ctx 32768, 1 slot, `--parallel 1`), reasoning budget 2,048 and `max_tokens` 6,144. Procedure: `llm-serve` skill, "CRAwDAD debate", with this label. Up to 5 sessions, one model resident at a time, each a background chain with `bye` after a successful invite.
- Cost and memory: 20 solo replies plus 1-3 debate replies per task, so 30-50 replies. At the smoke run's ~3.6 min per reply that is about 1.8-3 h of decode; the worst case (6,144 tokens at ~11 t/s, ~9 min per reply) is 7.5 h. GTT +26.7 / +26.8 GiB over the 7.4 GiB idle, client capped by `llmctl run` (8 GiB), each grade's child at 1 GiB AS.
- Per task, from `results/crawdad-v7-probe.debate.summary.json` and the rows:
  - signal = the two solos disagree (one passes, one fails), or at least one solo passes and the leaf fails;
  - all-fail = both solos and the leaf fail.
- Bar, applied in this order:
  1. all-fail >= 8 of 10: v7_01-10 stay, and 11-30 are written easier.
  2. signal >= 2 of 10: 11-30 are written in this same style.
  3. signal = 0: v7_01-10 stay, and 11-30 get less of the algorithm spelled out in the prompt.
  4. signal = 1 (and all-fail < 8): not covered by the user's bar. The result is reported, and the user decides.
  Lines 1 and 4 (order and gap) are Claude's additions to the relayed bar, made because all-fail >= 8 and signal >= 2 can both hold (8 all-fail plus 2 signal) and signal = 1 falls between the rules. Nothing else is decided from this run: no prompt, K, budget or protocol change.
- Recorded, no bar: the determinant case (tasks where a solo passed and the leaf failed, with the seat), per-reply time (gen_s mean, median, max per seat and per round), `budget_hit` rate per seat, any `finish` = `length`, `no_code` and `parse_fail` counts, leaf rounds and stops, session count, GTT per session and `memory.peak`.
- Validity: `report --regrade` must exit 0; otherwise the run is reported as unreadable and the bar is not applied. One run, n = 10, no spread: the bar reads headroom for writing tasks, not a rate.

### Result (2026-10-18, at 073cc52): all-fail 9 of 10, so line 1 applies, and 11-30 get easier

Four sessions (llmctl 30-33; the fifth was not needed), 39 replies, 10 of 10 tasks at a leaf, `report --regrade` ok, exit 0. Results are in `bench/loop/results/crawdad-v7-probe.debate.{jsonl,meta.json,summary.json}`.

| task | first | solo Qwen | solo R1-D | leaf | stop |
|---|---|---|---|---|---|
| v7_01 packbits | r1d32 | fail | fail | fail | R3 accept |
| v7_02 ini_strict | r1d32 | fail | fail | fail | R2 accept |
| v7_03 semver_order | qwen32 | fail | fail | fail | R4 accept |
| v7_04 partition_rank | qwen32 | fail | fail | fail | R2 accept |
| v7_05 digit_rules | r1d32 | fail | fail | fail | R3 accept |
| v7_06 route_lexmin | qwen32 | fail | fail | fail | R2 accept |
| v7_07 rect_union | r1d32 | fail | fail | fail | R2 accept |
| v7_08 bowling_frames | qwen32 | fail | fail (length, no code) | fail | R4 max_rounds |
| v7_09 paint_posts | qwen32 | fail | fail | fail | R4 accept |
| v7_10 justify_lines | r1d32 | pass | pass | pass | R3 accept |

- Bar, in the stated order: all-fail = 9 >= 8, so line 1 applies. v7_01-10 stay as committed, and tasks 11-30 are written easier. Signal = 0 (no solo disagreement, and no passing solo dropped by a leaf), which on its own would have been line 3, "less spelled out". The order stated in the pre-run decides between them, so line 3 does not apply.
- For contrast, not a bar: the cold-review solvers (Sonnet, no thinking budget, no tests run) passed 10 of 10 on the same prompts. The gap is the pair at a 2,048-token budget against these specs, not the prompts' determinacy.
- Recorded, no bar:
  - Determinant case (a solo passed and the leaf failed): 0.
  - Per reply: gen_s mean 260 s. Qwen 18 replies, mean 249, median 261, max 308. R1-Distill 21 replies, mean 269, median 280, max 565 (the length reply). By round, mean: R1 291, R2 249, R3 185, R4 245.
  - Decode 10,146 s (2.8 h). Wall 2 h 50 min 38 s from the first invite to the last bye.
  - tg 10.74-11.16 t/s at prompts up to 3,671 tokens.
  - `budget_hit`: Qwen 17/18, R1-Distill 17/21.
  - One `finish` = `length`: R1-Distill's solo on v7_08, 6,144 tokens and no code. It was not the debate's opener; Qwen opened that task.
  - Leaves R2 4, R3 3, R4 3. Stops: accept 9, max_rounds 1. No `parse_fail`.
  - GTT 34.1-34.3 GiB while resident, back to 7.4-7.5 after each bye. `memory.peak` 40-45 MiB.
- New, not seen in the smoke run: `think_leak` on 5 replies, all R1-Distill and all with `budget_hit`. After llama.cpp forced the end tag, the model emitted `<think>` again and kept reasoning in `content`, then closed it and answered. The thinking traces in content run 16-8,702 chars. So for this template the per-request budget caps the first trace but not the reasoning. `visible()` keeps only the text after the last `</think>`, and all 5 close it, so no trace reached a debate prompt (`history`, `debate.py`). A real pre-run should name this: either count that text against the budget, or accept it as part of R1-Distill's reply.
- Next: tasks 11-30, written easier (the bar's direction; how much easier is the next pre-run's judgement), then the 30-task run under its own label and pre-run. Each needs the user's go.
- Accord (review relayed by the user, 2026-10-18, on 05605d1): line 1 applies, signal 0 and all-fail 9 confirmed from the committed rows. The reviewer rebuilt all 19 debate prompts from the rows; none contains `<think>`, `</think>` or a slice of a leaked prefix. The bowling solo's prefix ends with the budget message. "Easier" means fewer rules and a smaller set of corner cases. The next pre-run records R1-Distill's continued reasoning as this one did, and the budget and protocol stay unchanged.

## v7 tasks 11-30: written easier (2026-10-18)

Stated with the tasks, not before them: this is the judgement the probe's bar left to the next step, and no model has seen these tasks. Written by Claude inline, with no subagents, every check under `prlimit --as=4294967296`, and no GPU.
- How much easier, measured against v7_01-10:
  - one or two functions per task;
  - about six rules, each shown by an example;
  - validation is at most a type check plus a range;
  - at most one stated size, with the algorithm named when one is needed (heap, BFS, sieve, DP);
  - references of at most about 40 lines (v7_29's stack machine is 60).
  The model is justify_lines, the one probe task both seats solved. Prompts are 1,168-1,831 chars (v7_01-10: 1,309-2,630), and references are 12-60 lines (v7_01-10: 35-65).
- Tasks, seeds 7011-7030:
  - formats: 11 rle_letters, 12 hex_lines, 13 column_totals, 14 bit_flags, 15 duration_words;
  - number theory and combinatorics: 16 collatz_leader, 17 prime_gap, 18 perm_rank, 19 change_ways, 20 radix_text;
  - graphs and geometry: 21 island_stats, 22 course_order, 23 shoelace, 24 knight_hops, 25 point_location;
  - simulation and DP: 26 teller_queue, 27 lis_count, 28 life_board, 29 stack_machine, 30 wrap_cost.
- Oracles, each built differently from the reference: groupby and regex expansion; `ljust` formatting; a table generator; `int(bits, 2)`; arithmetic without divmod; plain chain loops; trial division; `itertools.permutations`; recursive enumeration; `int()` behind a canonical-form regex; union-find; brute-force permutations; the trapezoid formula and lattice walking; Bellman-Ford-style relaxation; a star-polygon triangle fan; a unit-time tick simulation; DFS over increasing subsequences; a Counter-based Life; expression trees evaluated by `eval`; brute force over all line breaks.
- Checks:
  - `check_tasks.py --set v7`: 30/30 OK.
  - v7_01-10 are byte-identical to 6680747 (sha256 of their task dicts `b523b223c82ff7ce`, before and after).
  - `run.py --selftest --set v7` (30 tasks), `agent.py --selftest --set v7` and `debate.py --selftest` OK.
  - Mutant control on 11-30: 40 single-line mutants, two per task. 39 caught. The 40th (v7_25, "strictly above" changed to "on or above" in the crossing rule) is equivalent, because boundary points are classified first and either half-open convention gives the same parity. So 39 of 39 non-equivalent mutants were caught. The script is in the session scratchpad.
- Draft defects fixed before the first checker run:
  - v7_23's example line was garbled;
  - v7_27's example count was wrong: [1, 5, 2, 6, 3, 7] has 3 longest subsequences, not 4;
  - three test literals were checked against independent code. 321335886 (ways to pay 1000 with UK coins) and 134 (knight, 200 by 200, corner to corner) were right. The base-36 text of 10^30 was wrong and is now `2oy99wnkl1c76diocq9s`.
- Open: the cold review of 11-30 (same method as batch 1, capped, needs the user's go). Sealed from this commit, with the same rule as v7_01-10: only a defect found by the cold review may change a task, recorded here before any model sees it.
- Amendment (review relayed by the user, 2026-10-18, on c1e96d4). Seventeen of the twenty prompts meet the easier bar. Three were held before the cold review because they still carried batch-1 validation: v7_13 (header checks, a number grammar, a single "\r" rule), v7_20 (the canonical form only: leading zeros, "-0" and the int() near-misses), and v7_29 (name and operand checks, every jump target checked before running, a 10,000-step cap). No model had seen them, so the seal above gives way to the reviewer's hold; nothing else changed.
  - v7_13: `splitlines()`, the header is split and stripped (names guaranteed distinct, no check), each field goes through `int()`, and the only check is the field count.
  - v7_20: one rule, an optional "-" then digits whose value is below the base. Leading zeros and "-0" are now accepted. `to_base` is unchanged.
  - v7_29: programs are guaranteed well-formed, with in-range jumps, and guaranteed to stop. The only runtime check is stack underflow.
  Each keeps its id, entry names and seed. Results: references 15, 35 and 36 lines; prompts 1,363, 1,427 and 1,632 chars. `check_tasks.py --set v7` 30/30, run/agent selftests on v7 OK, and only these three task dicts differ from c1e96d4. Mutant control on the three new references: 9 mutants, 9 caught. The cold review now covers all twenty.
- Cold review of 11-30, 2026-10-18/19, on 153dece:
  - Method as in batch 1: twenty solvers, one per task, `red-team` agent type (Read/Grep/Glob only: no Bash, no writes, no code run), model Sonnet, prompt verbatim with "use no tools, read no file". All twenty reported `TOOLS USED: none`, at 13-15k tokens each. 18 ran in one batch; v7_27 and v7_30 were rejected at the per-spawn permission prompt and re-run in a second batch.
  - Grading: `run.grade` at the visible seed, 104729 and seeds 1-3. 20 of 20 passed on all five, each on the first attempt. No defect, no prompt edit; the seal on v7_11-30 stands from 153dece.
  - Listed ambiguities: nothing a test depends on that the prompt leaves open. Recurring untested points: subclasses of str, list and int, wrong-type exceptions (the prompts say ValueError), sizes past the stated bounds, and `int()`'s acceptance of underscores and non-ASCII digits in v7_13, which the prompt hands to `int()` on purpose.
  - Solver code is in the session scratchpad, not the repo.

## CRAwDAD debate on v7 (30 tasks, pre-run)

Stated before any GPU session (2026-10-18, measure skill steps 1-6). For review before it runs; the GPU sessions need the user's go after that. The set is v7 as of 2ba635b: v7_01-10 from 6680747, v7_11-30 from 153dece, all cold-reviewed, sealed, no edits since.
- Question: does the CRAwDAD debate leaf solve more v7 tasks than the first speaker's own solo answer, and is it at least as good as either model alone?
- Arms, all in one run, label `crawdad-v7-30`, `--set v7` with no `--tasks`, so all 30 (first step only):
  - first-speaker solo F: the R1 that opens each debate. The coin gives 15 tasks to each seat (seed 42, a shuffle of the 30 sorted ids). On v7_01-10 it differs from the probe's coin on 6 tasks;
  - each model's solo, Q (Qwen3-32B) and R (R1-Distill): both solos on every task, as in the probe;
  - leaf L: the module standing when the debate ends, graded once on the fresh seed 104729.
- Fixed and recorded: `debate.py` protocol `137acf32c95d` (reasoning budget 2,048, `max_tokens` 6,144, `SEED_BASE` 4000, sampling 0.6 / 0.95 / 20), llama.cpp b11669-620d2225c on vk, endpoint defaults (ctx 32768, 1 slot, `--parallel 1`), model files as in the probe meta. No budget, prompt or protocol change from the probe.
- Metric, per task: a rescue is F fail and L pass; a drop is F pass and L fail (the determinant case); net = rescues - drops. Totals: L, F, Q, R, and U (either solo passes).
- Bar, stated now:
  - keep the debate as configured as the base for the next CRAwDAD steps (critique rows, retrieval) when net >= 3 and L >= max(Q, R);
  - drop it as configured when net <= 0;
  - net 1 or 2 is inconclusive, which is a drop unless the user approves a rerun on more tasks (measure skill);
  - no room: if both Q and R are >= 27 of 30, or L = 30, the run cannot separate the arms, and that is reported instead of a verdict.
  3 of 30 is 10 points, the same size as the +3 bars used at n = 15 and 30 in v3-v6. It is a judgement, not a measured spread: one run, no repeat, and `--parallel 1` makes each draw reproducible rather than averaged.
- Recorded, no bar:
  - rescues and drops by first-speaker seat; leaf rounds and stops; signal and all-fail counts as in the probe, split v7_01-10 vs v7_11-30 (whether the easier batch gave headroom);
  - per-reply gen_s, tg and prompt depth, decode hours, wall time, GPU hours per leaf solve vs per solo solve;
  - `budget_hit` per seat, `finish` = `length`, `no_code` and `parse_fail` counts;
  - R1-Distill's continued reasoning, recorded as in the probe and changing nothing: `think_leak` rows, the length of the text before the last `</think>`, and any reply where an opened `<think>` is never closed (only then could trace text reach a debate prompt through `visible()`), with whether such a reply entered a prompt;
  - determinism check: v7_01-10's solos use the same prompt, seed, build and model as the probe, so each is compared with the probe row (content identical or not). A difference is reported, not corrected.
- Cost: the probe averaged 3.9 replies per task at 260 s each, so about 117 replies and about 8.5 h of decode, plus up to 5 loads. Worst case, every task reaching R4 with 6,144-token replies, is about 150 replies and 22 h. Sessions are background chains under llmctl, one model resident at a time (GTT +26.7 / +26.8 GiB over 7.4 idle), client capped at 8 GiB, each grade's child at 1 GiB AS. `report --regrade` must exit 0, or the run is unreadable and the bar is not applied.
- Procedure: `llm-serve` skill, "CRAwDAD debate", with label `crawdad-v7-30` and `--set v7` on the first step.

### Result (2026-10-19, at 5fbba2a): net +3 and L 13 >= max(Q 10, R 7), so keep, exactly at the line

Accord on the pre-run relayed by the user (2026-10-18), then the user's go on all five sessions. Five sessions (llmctl 34-38, qwen32 / r1d32 alternating), 105 replies, 30 of 30 tasks at a leaf, `report --regrade` ok, exit 0. Results are in `bench/loop/results/crawdad-v7-30.debate.{jsonl,meta.json,summary.json}`.

| task | first | solo Qwen | solo R1-D | leaf | stop |
|---|---|---|---|---|---|
| v7_01 packbits | r1d32 | fail | fail | fail | R3 accept |
| v7_02 ini_strict | r1d32 | fail | fail | fail | R2 accept |
| v7_03 semver_order | r1d32 | fail | fail | fail | R2 parse_fail |
| v7_04 partition_rank | r1d32 | fail | fail | fail | R4 max_rounds |
| v7_05 digit_rules | r1d32 | fail | fail | fail | R3 accept |
| v7_06 route_lexmin | qwen32 | fail | fail | fail | R4 accept |
| v7_07 rect_union | qwen32 | fail | fail | fail | R3 accept |
| v7_08 bowling_frames | r1d32 | fail | fail | fail | R3 accept |
| v7_09 paint_posts | r1d32 | fail | fail (length, no code) | fail | R1 no_code |
| v7_10 justify_lines | qwen32 | pass | pass | pass | R2 accept |
| v7_11 rle_letters | qwen32 | fail | fail | fail | R2 accept |
| v7_12 hex_lines | qwen32 | pass | pass | pass | R2 accept |
| v7_13 column_totals | qwen32 | pass | pass | pass | R2 accept |
| v7_14 bit_flags | r1d32 | fail | fail | fail | R2 accept |
| v7_15 duration_words | qwen32 | pass | pass | pass | R2 accept |
| v7_16 collatz_leader | qwen32 | fail | fail | fail | R2 accept |
| v7_17 prime_gap | qwen32 | fail | pass | pass (rescue) | R3 accept |
| v7_18 perm_rank | r1d32 | fail | fail | fail | R2 accept |
| v7_19 change_ways | r1d32 | fail | fail | fail | R3 accept |
| v7_20 radix_text | qwen32 | pass | fail | pass | R2 accept |
| v7_21 island_stats | r1d32 | pass | fail | pass (rescue) | R3 accept |
| v7_22 course_order | qwen32 | pass | fail | pass | R2 accept |
| v7_23 shoelace | qwen32 | pass | fail | pass | R2 accept |
| v7_24 knight_hops | r1d32 | fail | fail | fail | R3 accept |
| v7_25 point_location | r1d32 | fail | fail | fail | R3 accept |
| v7_26 teller_queue | qwen32 | fail | fail | fail | R2 accept |
| v7_27 lis_count | qwen32 | pass | pass | pass | R2 accept |
| v7_28 life_board | r1d32 | fail | pass | pass | R2 accept |
| v7_29 stack_machine | r1d32 | fail | fail | pass (rescue) | R3 accept |
| v7_30 wrap_cost | qwen32 | pass | fail | pass | R4 accept |

- Totals: F 10, L 13, Q 10, R 7, U 12. Rescues 3 (v7_17, v7_21, v7_29), drops 0, net +3, and L = F + net.
- Bar: net 3 >= 3 and L 13 >= max(10, 7), so the keep line applies. The debate as configured is the base for the next CRAwDAD steps. The no-room line does not apply (Q and R are below 27, L is below 30).
- Scope: one run, no repeat, and the verdict sits on the line: one rescue fewer is net 2, inconclusive. Two of the three rescues are tasks the critic's model also solved alone:
  - v7_17: R1-Distill's R2 code replaced Qwen's failing opener, and R1-Distill's solo passed too;
  - v7_21: Qwen's R2 code replaced R1-Distill's, and Qwen's solo passed too.
  Only v7_29 is a pass that neither solo had: Qwen's R2 code passed after R1-Distill's opener failed, and Qwen's own solo had failed; R1-Distill accepted at R3. In both v7_17 and v7_21 the R2 code is not the critic's solo code. The leaf passed every task in U, plus v7_29.
- Easier batch: all 3 rescues and all 7 signal tasks are in v7_11-30. Signal: v7_01-10 0, v7_11-30 7. All-fail: v7_01-10 9, v7_11-30 8 (17 in all). On v7_01-10 the run repeats the probe: F 1, leaf 1 (v7_10).
- By first speaker: Qwen opened 15, opener solo 9, leaf 10 (1 rescue); R1-Distill opened 15, opener solo 1, leaf 3 (2 rescues). No drops for either seat.
- Recorded, no bar:
  - Leaves: R1 1, R2 16, R3 10, R4 3. Stops: accept 27, max_rounds 1 (v7_04), no_code 1, parse_fail 1.
    - no_code is v7_09: R1-Distill's opener hit 6,144 tokens (`finish` = `length`) and wrote no code, so the task ended at R1.
    - parse_fail is v7_03: Qwen's R2 put its VERDICT line inside the code fence, which `parse()` skips. That module failed the tests too, so no pass was lost.
  - Per reply: 105 replies, gen_s mean 237 s. Qwen 49 replies, mean 233, median 239, max 288. R1-Distill 56 replies, mean 240, median 259, max 564 (the length reply). By round, mean: R1 264, R2 223, R3 162, R4 156.
  - Decode 24,889 s (6.91 h), against the pre-run's ~8.5 h for ~117 replies. Wall 6 h 57 min 14 s from the first invite (03:36:00Z) to the last bye (10:33:14Z).
  - tg 10.69-11.25 t/s at prompts of 437-3,983 tokens.
  - GPU hours per solve, decode only:
    - Qwen solo: 2.01 h for 10 solves, 0.20 h each;
    - R1-Distill solo: 2.39 h for 7, 0.34 h each;
    - both solos: 4.40 h for U = 12, 0.37 h each (and U needs an oracle to pick the passing one);
    - debate path (the opener's R1 plus R2-R4, 75 replies): 4.74 h for L = 13, 0.36 h each.
  - `budget_hit`: Qwen 43/49, R1-Distill 40/56. One `finish` = `length` (v7_09). `no_code` 17: 16 accept replies without code (the walk ignores code on an accept) plus the v7_09 solo. No reject without code.
  - GTT 34.3-34.4 GiB while a model was resident, 7.6 GiB after each bye. `memory.peak` 40-61 MiB.
- R1-Distill's continued reasoning, recorded and changing nothing:
  - `think_leak` (a `</think>` in content) on 4 replies, all R1-Distill solos with `budget_hit`. The text before the last `</think>` is 1,372-9,290 chars, and `visible()` cuts it.
  - New shape, on 3 replies (R1-Distill solos on v7_06, v7_12 and v7_19, all `budget_hit`): the content opens with `<think>` (`<think><think>` on two of them) and never closes it. The start and end of each are answer text (approach, code, explanation); the reasoning is in `reasoning_content` (6,932-8,874 chars).
  - Only v7_19's was an opener, so its whole content, tags included, went into Qwen's R2 prompt through `visible()`. Read in full, the text after the tags is the answer and contains no reasoning. So no trace reached a prompt, but the literal tags did. v7_19 is all-fail, so this cannot be a drop. One reply cannot show whether the tags changed Qwen's critique.
- Determinism vs the probe (reported, not corrected):
  - Qwen's 10 solos on v7_01-10 are byte-identical to the probe's.
  - R1-Distill's v7_01-03 are identical and v7_04-10 differ. All 20 grades are the same.
  - The request order on R1-Distill's one slot matches the probe through v7_03R1. Then the probe sent v7_03R2 (Qwen opened v7_03 there) and this run sent v7_04R1. That fits outputs that depend on the server's prompt-cache state (`--cache-reuse 256`, one slot) as well as on prompt and seed. Not tested.
  - So the pre-run's "`--parallel 1` makes each draw reproducible" holds at most for an identical request sequence; as written it was too broad. The probe's length reply moved with this: its v7_08 solo was 6,144 tokens, and this run's is 3,791; this run's length reply is v7_09.
- Pre-run text: its date line said 2026-10-19, but 5fbba2a was committed 2026-10-18 22:22 CDT (2026-10-19T03:22:34Z). The line now says 2026-10-18. Nothing else in the pre-run changed.
- Next, each step needing the user's go: the bar names critique rows and retrieval as the next CRAwDAD steps on this configuration, with `visible()` unchanged (accord below).
- Accord (review relayed by the user, 2026-10-19, on 4947330): the keep stands at the line.
  - The leaf's passes beyond Qwen's solos are v7_17, v7_28 and v7_29. v7_28 is R1-Distill's opener kept by an accept, so it is not a rescue. v7_21 was already a Qwen solo pass.
  - `visible()` stays as it is, and the never-closed `<think>` case is recorded with no new protocol hash. The tag wraps the same "To solve this problem," essay that tag-free solos put in content (1,183-1,707 chars before the code fence, not counting the tags). Stripping the tag characters would leave that essay. The closed cases are still cut at `</think>`.
  - v7_03's VERDICT and CONFIDENCE lines are inside the code block, which closes only after them, so `parse()` drops them. `CODE_BLOCK` would drop them from an unclosed fence too.

## CRAwDAD solver-row corpus from v7 (2026-10-19, no GPU)

A build with a readout and no bar. No model ran.
- Order (the user's question, which goes first; reviewer accord 2026-10-19): a solver-row retrieval test comes before any critique kind.
  - Putting critic text in first mixes two questions. A zero would not say whether retrieval failed or whether the corpus called a failing module fine.
  - The critique kind (the comment, for slots 2 and 4) is built only if solver-row retrieval shows a gain, and its rows carry the grader's result, never the accept word.
  - Evidence from the v7-30 rows (45 critic judgments against the true grade of the judged module; counts, not rates): R1-Distill accepted 10 of the 14 failing modules it judged (10 of its 21 accepts are failures). Qwen's accepts are 4 failures and 2 passes. Of 15 rejects of failing code, 3 produced passing code, the 3 rescues.
- Determinism line for the next debate pre-run (agreed with the reviewer, replacing the cross-run byte check):
  - within one server load, compare that seat's requests by index with the earlier run;
  - byte-compare while the index is the same prompt and the same position;
  - the first index that differs in prompt or position, and every request after it in that load, is grades only;
  - if an index matches and the output still differs, it is grades only from the next request to the end of that load.
  The `--cache-reuse` cause stays untested.
- Built: `memring.py debate --root DIR --set v7 A.debate.jsonl [B ...]`.
  - It regrades every coded reply on the fresh seed (the grade the debate stored) and exits 2 on any disagreement.
  - It seals and admits each module to its writer's solver slot (`DEBATE_SLOT`: Qwen 1, R1-Distill 3), whatever the debate role.
  - It skips the code in accept replies, as `walk()` does.
  - It flushes once per slot, with no canaries.
  - The family map `FAMILIES["v7"]` is the four writing buckets: formats, number_theory, graphs_geometry, simulation_dp.
- Found while building, fixed before any commit: the first draft took the code from accept replies and flushed both slots together. That put Qwen's v7_20 module in R1-Distill's slot: R1-Distill's accept restated it, and the duplicate check spans one flush.
- Readout on crawdad-v7-30 plus crawdad-v7-probe, in a scratch root. It rebuilds in about 1 s from the committed jsonl, so no root is kept yet.
  - 144 replies: 106 coded non-accept, 16 accept-reply code blocks skipped, 0 regrade mismatches.
  - Admitted 58 Qwen and 47 R1-Distill. One refused: Qwen's v7_29 solo, an empty code block.
  - Committed 47 and 43. Rejected as duplicates 11 and 4, all exact: the v7_01-10 solos that are byte-identical in the two runs, Qwen's v7_01 R2, and R1-Distill's v7_04 R3, which restates its own R1.
  - Pass rows: Qwen 14 on 11 tasks (its 10 solo passes and the v7_29 rescue); R1-Distill 10 on 8 tasks (its 7 solo passes and its own passing R2 module on v7_30). The tasks with any pass row are the leaf's 13. Fail rows: 33 and 33.
  - Pass/fail by family, Qwen: formats 3/8, graphs_geometry 4/7, number_theory 1/11, simulation_dp 6/7. R1-Distill: formats 3/6, graphs_geometry 0/11, number_theory 2/8, simulation_dp 5/8.
- For the retrieval pre-run, not decided here:
  - Each model reads only its own slots (slot roles, 2026-10-15), so a family-filtered read for R1-Distill on graphs_geometry can return failures only.
  - `retrieve()` does not filter by kind.
  - v7 is now the corpus, so the test needs held-out tasks outside v7 (a v8 set, not written).
- Tested: `memring.py --selftest` with two new checks (the real grader on v7_10's reference: the writer's slot, accept code skipped, a contradicted stored grade exits 2); `agent.py --selftest --set v7` OK.
- Next, each step needing the user's go: the v8 tasks, then the retrieval pre-run.
- Accord (review relayed by the user, 2026-10-19, on 611e5e5): modules stay in the writer's solver slot, and the round is not stored for the first retrieval test.
  - A solo-only filter would drop a writer's only pass on two tasks: Qwen's v7_29 R2 (a rescue; its solo is the refused empty block) and R1-Distill's v7_30 R2 (not a rescue: Qwen opened v7_30 and its solo passed).
  - It would also drop the four debate modules that sit beside the same writer's solo pass (Qwen v7_10, v7_21 and v7_30; R1-Distill v7_17).
  - The retrieval pre-run may put the round in the verdict and run two arms if that is its question. A re-ingest costs about 1 s.

