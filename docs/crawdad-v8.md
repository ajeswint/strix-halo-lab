## v8 tasks: held-out set for the CRAwDAD retrieval test (2026-10-19)

Written by Claude inline, with no subagents, every check under `prlimit --as=4294967296`, and no GPU. No model has seen these tasks.
- Design (reviewer accord 2026-10-19; size by the user):
  - 30 tasks in v7's four families, split 8/7/7/8, because `retrieve()` reads one family of the v7 corpus: formats v8_01-08, number_theory v8_09-15, graphs_geometry v8_16-22, simulation_dp v8_23-30 (`memring.FAMILIES["v8"]`).
  - Why 30: the no-retrieval arm on v8 is a full debate, so it also repeats crawdad-v7-30's keep at the same n. The retrieval arm does not count as that repeat: its prompts carry the corpus, so it is the new question. At 20 tasks the same `net >= 3` line would be a different claim, and the family mix would stop matching the corpus.
  - The style is v7_11-30's, which is already calibrated (Qwen solo 9/20, R1-Distill 6/20, leaf 12/20, all-fail 8/20), so there is no probe batch.
  - New problems, and v8 never enters the corpus: a near-copy of a v7 task would make a gain look like retrieval when the stored module was already the answer. graphs_geometry stays even though R1-Distill's rows there are all failures.
- Tasks, seeds 8001-8030:
  - formats: 01 hex_color, 02 morse_text, 03 case_convert, 04 money_text, 05 cidr_range, 06 clock_12h, 07 luhn_digits, 08 query_pairs;
  - number_theory: 09 digit_persistence, 10 euler_phi, 11 goldbach_pairs, 12 pascal_mod, 13 primitive_triples, 14 happy_count, 15 egyptian_greedy;
  - graphs_geometry: 16 two_color, 17 lattice_segment, 18 closest_pair, 19 euler_trail, 20 triangle_kind, 21 manhattan_center, 22 tree_centers;
  - simulation_dp: 23 robot_walk, 24 elevator_scan, 25 josephus_order, 26 max_subarray, 27 stair_ways, 28 lcs_smallest, 29 matrix_chain, 30 ledger_events.
  Prompts are 1,202-2,022 chars and references 15-44 lines.
- Checks:
  - `check_tasks.py --set v8`: 30/30 OK.
  - `run.py --selftest --set v8`, `agent.py --selftest --set v8`, `debate.py --selftest` (protocol `137acf32c95d`, unchanged) and `memring.py --selftest`: OK.
  - Mutant control: 60 single-node AST mutants, two per task (a comparison, an arithmetic operator, an int constant or and/or), graded at the visible seed. 57 are caught. The 3 survivors are equivalent: in v8_05 a /33 prefix still raises ValueError through the negative shift that follows; v8_11's sieve index 0 is never read; in v8_20, `>=` after the `==` branch changes nothing. A fourth survivor, v8_26 rejecting -10**9, was a test gap, closed with a boundary test before this commit. The script is in the session scratchpad.
  - Near-copy check against v7: the word-set overlap (Jaccard, words of 4+ letters) between prompts is at most 0.37, for v8_16 two_color against v7_22 course_order (shared validation wording, different problem). The median of the per-task maxima is 0.23, and v7's own within-set maximum is 0.27. The closest in substance is v8_27 stair_ways against v7_19 change_ways: both count with a DP, but ordered moves with broken stairs against unordered coin sums, so the stored module is not the answer.
- Draft defects, each caught by the checker or by independent code before this commit:
  - wrong hand-written literals in v8_09 (persistence of 400 nines), v8_20 (a right angle written as acute) and v8_30 (a ledger total);
  - a garbled example line in v8_13, and a self-referential assert in v8_19 and in v8_26;
  - v8_15's bound q <= 100 contradicted its 5/121 example. It is now q <= 200, which gives at most 11 terms and 1,348 digits (measured over every p/q).
  - v8_17's entry name `lattice_count` clashed with v4, so it was renamed `segment_lattice_*`;
  - v8_10's random 10**12 oracle was too slow for the 0.8 s limit and was dropped; the prime literal covers that path;
  - v8_08's reference was trimmed from 53 to 44 lines.
- Registered: `run.SETS["v8"]`. The `llm-serve` skill's DeepSeek gate example moved from v8 to v9; `select_fix.py fresh v9` refuses (not registered).
- Sealed from this commit, with the same rule as v7: only a defect found by the cold review may change a task, recorded here before any model sees it.
- Cold review, 2026-10-19, on 488f1af (the user's go; reviewer: nothing in 488f1af holds it):
  - Method as for v7: thirty solvers, one per task, `red-team` agent type (Read/Grep/Glob only: no Bash, no writes, no code run), model Sonnet. Each got its prompt verbatim with "use no tools, read no file". All thirty reported `TOOLS USED: none` (one tool call each, the hand-back), at 12.2-13.4k tokens each, about 379k in all. All thirty ran in one batch, with no per-spawn prompt.
  - Grading: `run.grade` at the visible seed, the fresh seed 104729 and seeds 1-3. 30 of 30 passed on all five, each on the first attempt. No defect and no prompt edit, so the seal on v8 stands from 488f1af.
  - Listed ambiguities: none that a test depends on and the prompt leaves open. Recurring untested points:
    - subclasses of int, str, list and tuple;
    - ValueError rather than TypeError for a wrong type (the prompts say ValueError);
    - a trailing newline and non-ASCII digits;
    - v8_23's grid and command sizes, which solvers read as guarantees rather than checks;
    - ints past Python's 4,300-digit str limit in v8_04 ("no size limit"; the tests stop at 10**25);
    - unreduced p/q in v8_15 (2/4 gives [2]).
  - The solver code is kept in the session scratchpad, not the repo.
- Next, each step needing the user's go: the retrieval pre-run on v8, with the corpus from `memring.py debate` on v7.

## CRAwDAD retrieval on v8 (pre-run)

Stated before any GPU session (2026-10-19, measure skill steps 1-6). It is for review before it runs; the GPU sessions need the user's go after that. The design points marked "accord" were settled in review rounds relayed by the user. The set is v8 as of 23b316a (sealed, cold-reviewed). No model has seen v8.
- Question: when every prompt a seat writes starts with up to three of its own grader-passed v7 modules from the task's family, does the debate leaf solve more v8 tasks than the same debate without them?
- Arms. Both run on all 30 v8 tasks with the same coin (seed 42 over the 30 sorted ids, 15 openers per seat), the same seeds, build, model files and endpoint defaults as crawdad-v7-30:
  - D, label `crawdad-v8-d`: `debate.py` as configured, protocol `137acf32c95d`, no `--retrieve`. It is the no-retrieval baseline, and at the same n it also repeats crawdad-v7-30's keep (accord).
  - DR, label `crawdad-v8-r`: identical, except that every prompt each seat writes (solo R1 and R2-R4) starts with that seat's block for the task's family (`REF_HEAD`, then each module fenced and marked "grader pass"). Protocol `a01c192bac5d`, which binds the block layout and the export's sha256. In accord, the solo R1 prompts carry the block too: a solo written after a debate reply in the same load is not an unchanged baseline anyway, and D is the baseline.
- Retrieval is fixed by `bench/loop/results/crawdad-v7.passes.json` (sha256 `5118c06066ba7744…`, 27,370 bytes). It was built by `memring.py debate --passes-out` from crawdad-v7-30 and crawdad-v7-probe (0 regrade mismatches); a rebuild into a fresh root gives the same bytes.
  - For each seat's own solver slot (Qwen 1, R1-Distill 3) and family it holds pass rows only (accord: a labelled fail row is a later arm). Each task contributes its first committed row, tasks in id order, at most k = 3 per family. The order is fixed because "newest" in memring is the flush's seeded shuffle, not file order.
  - Rows per family (formats / number_theory / graphs_geometry / simulation_dp):
    - Qwen: 3 / 1 / 3 / 3, of 3 / 1 / 3 / 4 tasks with a pass: v7_12, 13, 15; v7_20; v7_21, 22, 23; v7_10, 27, 29.
    - R1-Distill: 3 / 1 / 0 / 3, of 3 / 1 / 0 / 4: v7_12, 13, 15; v7_17; none; v7_10, 27, 28.
    - The id order leaves out v7_30 in simulation_dp for both seats.
  - R1-Distill's graphs_geometry read is empty: those prompts carry no block (they are the plain prompts), and the rows record `retrieved: []` (accord: the empty read is recorded).
  - Blocks are 1,229-5,461 chars. v8 never enters the corpus, and `step` refuses an export built from the measured set.
  - Closest v7-to-v8 overlap, named in advance: v8_17's count is one gcd term (+1) of v7_23 shoelace's boundary sum, and Qwen's graphs_geometry block holds that passing v7_23 module.
- Metric, per task: leaf L_D and L_R. A gain is D fail and DR pass; a loss is D pass and DR fail; net = gains - losses = L_R - L_D.
- Bar, stated now:
  - keep retrieval as configured (pass rows, own slot, family, k = 3, every prompt) as the base for the next steps when net >= 3;
  - drop it as configured when net <= 0;
  - net 1 or 2 is inconclusive, which is a drop unless the user approves a rerun on more tasks;
  - no room: if L_D >= 27, the run cannot separate the arms, and that is reported instead of a verdict.
  This is the same +3 on 30 as crawdad-v7-30: a judgement, one run per arm, no repeat.
- Recorded, no bar:
  - Q and R (solo passes per seat) on both arms, so that a leaf gap already present in the solos is visible (accord). Solo gains and losses per seat, by family.
  - D read against crawdad-v7-30's bar (net over the first speaker's solo >= 3 and L >= max(Q, R)), as a replication reading. If D reads net <= 0, the debate keep is reopened for the user.
  - Gains and losses by family and by first-speaker seat, with R1-Distill's graphs_geometry prompts (empty read) split out.
  - Leaves and stops per arm, and critic verdicts against the judged module's true grade per seat (accepts of failing modules).
  - Prompt tokens per reply (DR adds the block), gen_s, decode hours, wall time; `budget_hit`, `finish` = `length`, `no_code`, `parse_fail`, `think_leak` and never-closed `<think>` per arm.
  - The retrieved task ids of every DR reply (row field `retrieved`).
  - Determinism (agreed line): byte-compare only while a load's requests match an earlier run's by index in prompt and position. No earlier run shares v8 prompts, so nothing is byte-compared; reported as not applicable.
- Cost: crawdad-v7-30 took 6.91 h of decode for 105 replies. DR adds at most about 1.5k prompt tokens per reply. That is about 7-7.5 h of decode per arm, about 14-15 h for both, worst case about 44 h (every task to R4 at 6,144 tokens). Ten sessions, five per arm, one model resident at a time, D first. Memory as in crawdad-v7-30: GTT +26.7 / +26.8 GiB, client capped at 8 GiB, each grade's child at 1 GiB AS. `report --regrade` must exit 0 on both arms, or the run is unreadable and the bar is not applied.
- Code in this commit, no GPU:
  - `memring.Ring.passes()` (pass-only, one per task, task order, k) and `memring.py debate --passes-out`;
  - `debate.py step --retrieve EXPORT` (first step only; the meta pins the export by sha256 and refuses a changed file, `--retrieve` on a later step, a set without a family map, and an export built from the measured set), `ref_block`, `protocol(retrieval)`, the row field `retrieved`, and the report's `retrieval` and `empty_reads`.
  - Without `--retrieve` the prompts and hash are unchanged (`137acf32c95d`; the selftest checks both).
  - Selftests: `debate.py --selftest` (9 new checks) and `memring.py --selftest` (2 new, 1 extended) pass.
- Procedure: `llm-serve` skill, "CRAwDAD debate": D with label `crawdad-v8-d` and `--set v8`; then DR with label `crawdad-v8-r`, `--set v8` and `--retrieve bench/loop/results/crawdad-v7.passes.json` on the first step.
- Accord (review relayed by the user, 2026-10-19, on be1fd42): one block on every turn as built (`history()` carries reply text only, so blocks do not pile up); `prompt_n` recorded (already on every row). The deepest crawdad-v7-30 prompt was 3,983 tokens (Qwen's v7_04 R4), not the probe's 3,671.

### Result (2026-10-20, at be1fd42): net +3 (L_R 11, L_D 8), so the keep line applies, exactly at the line; one gain came from an unchanged prompt

The user's go came on 2026-10-19. Nine sessions ran: D in llmctl 39-42 (four sessions; no fifth was owed), DR in llmctl 43-47. That is 107 + 108 replies, 30 of 30 tasks at a leaf in each arm, and `report --regrade` ok (exit 0) on both. Protocols are `137acf32c95d` (D) and `a01c192bac5d` (DR, export sha256 `5118c060…` pinned in the meta). Results are in `bench/loop/results/crawdad-v8-{d,r}.debate.{jsonl,meta.json,summary.json}`.

| task | family | first | solos D (Q R) | solos DR (Q R) | leaf D | leaf DR | stop D | stop DR |
|---|---|---|---|---|---|---|---|---|
| v8_01 hex_color | formats | r1d32 | P - | - P | fail | fail | R3 accept | R3 accept |
| v8_02 morse_text | formats | r1d32 | - - | - - | fail | pass (gain) | R2 parse_fail | R3 accept |
| v8_03 case_convert | formats | r1d32 | P - | P - | fail | fail | R3 accept | R3 accept |
| v8_04 money_text | formats | r1d32 | - - | - - | fail | fail | R3 accept | R3 accept |
| v8_05 cidr_range | formats | r1d32 | - - | - - | fail | fail | R2 accept | R2 accept |
| v8_06 clock_12h | formats | qwen32 | P - | P - | pass | pass | R2 accept | R2 accept |
| v8_07 luhn_digits | formats | qwen32 | - - | - - | fail | fail | R2 accept | R3 accept |
| v8_08 query_pairs | formats | r1d32 | - - | - - | fail | fail | R3 accept | R4 max_rounds |
| v8_09 digit_persistence | number_theory | r1d32 | P P | P P | pass | pass | R2 accept | R2 parse_fail |
| v8_10 euler_phi | number_theory | qwen32 | - - | - - | fail | fail | R2 accept | R2 accept |
| v8_11 goldbach_pairs | number_theory | qwen32 | P P | P P | pass | pass | R2 accept | R2 accept |
| v8_12 pascal_mod | number_theory | qwen32 | - P | P - | fail | pass (gain) | R2 accept | R4 accept |
| v8_13 primitive_triples | number_theory | qwen32 | - - | - - | fail | fail | R2 accept | R2 accept |
| v8_14 happy_count | number_theory | r1d32 | P - | - - | pass | pass | R3 accept | R3 accept |
| v8_15 egyptian_greedy | number_theory | qwen32 | - - | - - | fail | fail | R3 accept | R3 accept |
| v8_16 two_color | graphs_geometry | qwen32 | - - | - - | fail | fail | R3 accept | R3 accept |
| v8_17 lattice_segment | graphs_geometry | qwen32 | - - | - - | fail | fail | R3 accept | R2 accept |
| v8_18 closest_pair | graphs_geometry | r1d32 | - - | - P | fail | pass (gain) | R2 accept | R2 accept |
| v8_19 euler_trail | graphs_geometry | r1d32 | - - | - - | fail | fail | R3 accept | R3 parse_fail |
| v8_20 triangle_kind | graphs_geometry | qwen32 | - - | - - | fail | fail | R4 accept | R2 accept |
| v8_21 manhattan_center | graphs_geometry | r1d32 | - - | P - | fail | fail | R2 accept | R2 accept |
| v8_22 tree_centers | graphs_geometry | qwen32 | - - | - - | fail | fail | R2 accept | R2 accept |
| v8_23 robot_walk | simulation_dp | qwen32 | - - | - P | fail | fail | R2 accept | R2 accept |
| v8_24 elevator_scan | simulation_dp | r1d32 | - - | - - | fail | fail | R2 accept | R3 accept |
| v8_25 josephus_order | simulation_dp | r1d32 | P - | P - | pass | fail (loss) | R3 accept | R2 parse_fail |
| v8_26 max_subarray | simulation_dp | qwen32 | - - | - - | fail | fail | R2 accept | R4 accept |
| v8_27 stair_ways | simulation_dp | qwen32 | - - | P P | fail | pass (gain) | R4 accept | R2 accept |
| v8_28 lcs_smallest | simulation_dp | r1d32 | P P | - - | pass | pass | R3 parse_fail | R3 accept |
| v8_29 matrix_chain | simulation_dp | r1d32 | P - | P - | pass | pass | R3 accept | R3 parse_fail |
| v8_30 ledger_events | simulation_dp | qwen32 | - - | P P | pass | pass | R3 accept | R2 accept |

- Totals: L_D 8, L_R 11. Gains v8_02, v8_12, v8_18, v8_27; loss v8_25; net +3. L_D is below 27, so there is room.
- Bar: net 3 >= 3, so the keep line applies: retrieval as configured is the base for the next steps.
- Scope: one run per arm, and the verdict sits on the line again. The gains and the loss do not all come from retrieval:
  - v8_18: R1-Distill opened, and its graphs_geometry read is empty, so its solo had the same prompt (572 tokens, same seed) in both arms. It failed in D and passed in DR with different bytes, and Qwen accepted it at R2 in both arms. This gain did not come from a reference block. Of R1-Distill's seven graphs_geometry solos (identical prompts in both arms), none matched byte for byte (the slot's request history differs, as in the crawdad-v7-30 determinism finding) and one flipped. So same-prompt draws move by about this much.
  - v8_02 and v8_25 are mirror images. On both tasks Qwen's R2 rewrite passed in both arms, and the outcome turned on which arm's R2 put `VERDICT:` inside the code fence (a parse_fail, so the opener's failing solo stood). That happened in D on v8_02 and in DR on v8_25.
  - v8_12 and v8_27 are the gains where a block was present and the solos changed. On v8_12, Qwen's solo passed in DR (block v7_20) and failed in D. On v8_27, both solos passed in DR (simulation_dp blocks) and both failed in D. Each is one draw.
  So the stated bar reads keep, but the run cannot tell retrieval from same-prompt variation at this size: without v8_18 the net is +2, inconclusive. Because the keep sits on the line again, the next pre-run should address this before building on it.
- Recorded, no bar:
  - Q and R: D 9 and 4, DR 10 and 7; U 10 and 13. Solo changes D to DR: Qwen +4 / -3 (gains v8_12, v8_21, v8_27, v8_30; losses v8_01, v8_14, v8_28); R1-Distill +5 / -2 (gains v8_01, v8_18, v8_23, v8_27, v8_30; losses v8_12, v8_28).
  - D against crawdad-v7-30's bar: F 4, rescues 4 (v8_14, v8_25, v8_29, v8_30), drops 0, net +4 >= 3, but L 8 < max(Q, R) = 9. D does not repeat the keep's second condition, while DR meets both (net +3 over F 8; L 11 >= 10). D's net is not <= 0, so the reopen clause does not trigger, but the debate keep now rests on one run that met both conditions and one that did not.
  - By family, leaf D to DR (gains / losses): formats 1 to 2 (+1 / 0), number_theory 3 to 4 (+1 / 0), graphs_geometry 0 to 1 (+1 / 0; the gain is v8_18 above), simulation_dp 4 to 4 (+1 / -1). By first speaker: Qwen-opened +2 / 0, R1-Distill-opened +2 / -1.
  - The named overlap: v8_17 failed in every solo and leaf of both arms, so Qwen's v7_23 shoelace module made no visible difference.
  - Leaves: D R2 15, R3 13, R4 2; DR R2 15, R3 12, R4 3. Stops: D accept 28, parse_fail 2; DR accept 25, parse_fail 4, max_rounds 1. All six parse failures are the VERDICT-inside-the-fence case (two fence lines, the closing one after the verdict): D v8_02 R2 Qwen and v8_28 R3 R1-Distill; DR v8_09 R2 Qwen, v8_25 R2 Qwen, v8_19 R3 R1-Distill and v8_29 R3 R1-Distill. Five of the six parse-failed modules passed the tests.
  - Critic verdicts against the judged module's grade:
    - R1-Distill accepted 14 of the 20 failing modules it judged in D, and 11 of 17 in DR.
    - Qwen accepted 7 of 18 in D, and 5 of 17 in DR.
  - Prompt depth (`prompt_tokens`): D mean 1,048, max 2,872; DR mean 1,925, max 4,323. Solo R1 prompts average 594 tokens in D and 1,422 in DR. `prompt_n` (the uncached part): D mean 1,031, DR mean 1,204.
  - Per reply: D gen_s mean 225 s, decode 6.69 h; DR mean 232 s, decode 6.97 h; tg 10.59-11.23 t/s. Wall: D 6 h 43 min 38 s (18:08:41Z to 00:52:19Z), DR 7 h 0 min 58 s (00:53:27Z to 07:54:25Z), 13 h 45 min 44 s in all.
  - `budget_hit`: D Qwen 46/51, R1-Distill 43/56; DR Qwen 46/51, R1-Distill 44/57. No `finish` = `length` in either arm. `no_code`: D 12, DR 15, mostly accepts without code. `think_leak`: R1-Distill D 2, DR 3. A never-closed `<think>` appears once in D (R1-Distill's v8_23 solo; Qwen opened, so it never entered a prompt) and none in DR.
  - DR empty reads: 12, all R1-Distill on graphs_geometry. Every DR row carries `retrieved`, and the ids seen match the export.
  - GTT 34.4-34.5 GiB while resident, 7.7 GiB after each bye; `memory.peak` 41-57 MiB.
  - Determinism: not applicable as stated (no earlier run shares v8 prompts). Within this run, R1-Distill's seven graphs_geometry solos had identical prompts in both arms and none matched byte for byte.
- Next: closed (the user, 2026-11-05 CT): the keep stands as it stands; no redraw, no new GPU work, no bars retuned. The parser arm is done (below, PR #6). Two caveats stay on the record with the keep: the VERDICT-in-fence parse failure was the largest single source of leaf flips (two of five), and same-prompt variation is as large as the measured effect, so the keep sits on the line and the run cannot tell retrieval from same-prompt variation. Later the same day AJ reopened a redraw line: see *CRAwDAD v8 redraw (fixed parser, pre-run)* below (this close stands as written; the redraw has its own pre-run).
- Parser fix (2026-11-05, PR #6 merged at `1a889a4`; no model, no GPU, no new run):
  - `parse()` in `bench/loop/debate.py` now reads `VERDICT:` / `CONFIDENCE:` lines that close a code block's body, but only when the prose outside the fences has none of that field (prose wins; per field). The lines need their colon and stand alone; a `# VERDICT:` comment (mid-code or as the last code line) is never read, and `confidence = 0.5` is code. The closing lines are cut from the returned code in every case, so the grader never sees them as source. A fence that holds only those lines is skipped for the code block before it.
  - Selftest: 13 new `in-fence` checks plus two `walk` checks (a recovered reject continues the debate, a recovered accept ends it); `debate.py --selftest` OK.
  - `debate.py reparse --label L [--regrade]` is read-only (writes no result file, asks no model): `parse()` over the stored replies, rows whose verdict or code block changed, and what `walk()` says with them. Run on both v8 arms with `--regrade`:
    - All six parse failures now yield a verdict and code. Four are accepts (D v8_28 R3; DR v8_09 R2, v8_19 R3, v8_29 R3): the opener's module stands as before, so the leaf grade is unchanged, only the stop reads `accept` instead of `parse_fail`. Two are rejects with code (D v8_02 R2, DR v8_25 R2): the debate would go on to R3 (R1-Distill), a reply that was never asked, so their leaves are unknown, not recovered. The re-parse alone moves no leaf count, and no keep or drop follows from it.
    - The re-grade of the cut code (D 22 modules, DR 29) matches the stored grade on 50 of 51. The cut itself changes nothing: 43 rows only lose closing `CONFIDENCE:` / `VERDICT:` lines. The odd one is DR v8_28's Qwen solo: its reply ended with `CONFIDENCE: 0.95` in a second, separate fence, so the stored "code" was that one line (graded fail); the code block before it now extracts and grades pass. A second mis-parse the first count did not name; it touches a solo, not a stop. Likewise DR v8_02's Qwen solo (same shape, still fails).
  - The `PROTOCOL` hash does not bind `parse()`: the v8 rows were parsed by the old parser and stay as stored; a new run would carry the same hash as crawdad-v8-d. Any redraw has to say which parser it used.
  - The user's call, made 2026-11-05 CT: take the keep as it stands; no redraw. Should a later run use the fixed parser, it must still say which parser it used (the line above). Reopened later 2026-11-05 CT: the pre-run in `## CRAwDAD v8 redraw (fixed parser, pre-run)` below states the parser for `crawdad-v8-d2` and `crawdad-v8-r2`; this call is not rewritten.

## CRAwDAD v8 redraw (fixed parser, pre-run)

Stated before any GPU session (2026-11-05 CT, measure skill steps 1-6). Reopens a redraw line under the user's new go after the 2026-11-05 close (`c2ae544`, PR #7); the stored `crawdad-v8-d` and `crawdad-v8-r` result files (`1b801af`) stay untouched as parsed by the old parser. For review by `adversarial-reviewer` before any run; **no GPU session starts in this commit, and each GPU stage waits for AJ's separate yes**. The set is the sealed, cold-reviewed `v8` as of `23b316a` (30 tasks, 8/7/7/8 across `formats`, `number_theory`, `graphs_geometry`, `simulation_dp`).
- Question: with the post-`1a889a4` `parse()` (`VERDICT:` / `CONFIDENCE:` allowed to close a code fence body when the prose outside fences has none of that field, and cut from the extracted code), does the D vs DR leaf net on the sealed `v8` set still meet the retrieval keep bar when every prompt a seat writes in DR starts with up to three of its own grader-passed `v7` modules from the task's family?
- Arms. Both run on all 30 `v8` tasks (`--set v8`, no `--tasks`) with the same balanced coin (`COIN_SEED = 42` over the 30 sorted task ids, 15 openers per seat), reply seeds (`SEED_BASE = 4000`, seed `4000 + round`), fresh grading seed `104729`, sampling (`temperature = 0.6`, `top_p = 0.95`, `top_k = 20`), `REASONING_BUDGET = 2048` (`BUDGET_MESSAGE`), `MAX_TOKENS = 6144`, build (`b11669-620d2225c` on `vk`), model files (`/data/models/Qwen3-32B-Q4_K_M.gguf`, `/data/models/DeepSeek-R1-Distill-Qwen-32B-Q4_K_M.gguf`) and llmctl endpoint defaults (`qwen32` and `r1d32`, `vk`, `ctx 32768`, 1 slot, `--parallel 1`) as `crawdad-v8-d` and `crawdad-v8-r`. Distinct redraw labels are used so `bench/loop/results/crawdad-v8-{d,r}.debate.{jsonl,meta.json,summary.json}` are never overwritten:
  - D, label `crawdad-v8-d2`: `debate.py` as configured, protocol `137acf32c95d`, no `--retrieve`. Plain-debate baseline on `v8` under the fixed parser; at the same `n = 30` it also gives a replication reading against `crawdad-v7-30`'s debate keep bar.
  - DR, label `crawdad-v8-r2`: identical to D except `--retrieve bench/loop/results/crawdad-v7.passes.json` on the first step only, protocol `a01c192bac5d` (binding `REF_HEAD`, the reference block layout, and the frozen export sha256 `5118c06066ba7744e627cc09c800f4444902a1634f887a65a65a466a6e2777d5`, 27,370 bytes). Every prompt each seat writes (solo R1 and R2-R4) starts with up to `k = 3` of that seat's own committed pass rows from `v7` in the task's family (Qwen slot 1: 3 / 1 / 3 / 3 rows; R1-Distill slot 3: 3 / 1 / 0 / 3 rows; R1-Distill's `graphs_geometry` read is empty, so those prompts carry no block and record `retrieved: []`).
- Parser: `bench/loop/debate.py` `parse()` and `peel_trailer()` as landed in PR #6 (`045d08e`, merged at `1a889a4`, unchanged at HEAD). When the prose outside code fences has no `VERDICT:` (or `CONFIDENCE:`), trailing `VERDICT:` / `CONFIDENCE:` lines inside a fenced code block stand in for the missing field (prose wins per field), are cut from the returned code before grading, and a fence holding only those lines is skipped for the code block before it.
  - `PROTOCOL` (`137acf32c95d` for D, `a01c192bac5d` for DR) hashes prompt strings, sampling constants and seeds—not `parse()` or `peel_trailer()`. Thus `crawdad-v8-d2` and `crawdad-v8-r2` carry the same `protocol` hashes in `.debate.meta.json` as `crawdad-v8-d` and `crawdad-v8-r` even though `parse()` differs. This pre-run records that `crawdad-v8-d2` and `crawdad-v8-r2` use the post-`1a889a4` parser, whereas `crawdad-v8-d` and `crawdad-v8-r` used the pre-`1a889a4` parser and stay as stored.
- Metric, per task: leaf `L_D` (on `crawdad-v8-d2`) and `L_R` (on `crawdad-v8-r2`), graded once on fresh seed `104729`. A gain is `crawdad-v8-d2` fail and `crawdad-v8-r2` pass; a loss is `crawdad-v8-d2` pass and `crawdad-v8-r2` fail; `net = gains - losses = L_R - L_D`.
- Bar, unchanged from the `v8` retrieval pre-run (`be1fd42`; not retuned):
  - keep retrieval as configured (pass rows, own slot, family, `k = 3`, every prompt) as the base for the next steps when `net >= 3`;
  - drop it as configured when `net <= 0`;
  - `net` 1 or 2 is inconclusive, which is a drop unless the user approves a rerun on more tasks (measure skill);
  - no room: if `L_D >= 27`, the run cannot separate the arms, and that is reported instead of a verdict.
- Reading rule, fixed before the run: if `crawdad-v8-r2` against `crawdad-v8-d2` reads `net <= 0` or `net` 1 or 2 while stored `crawdad-v8-{d,r}` (`1b801af`) read +3, the redraw's verdict governs (drop, or inconclusive = drop unless AJ approves a rerun) and the stored +3 stays an exploratory lead. The bar is not retuned either way.
- Same-prompt and parse caveats (why redraw, and what stays a recorded caveat rather than a bar change):
  - In-fence `parse_fail` removal: in `crawdad-v8-{d,r}` (`1b801af`), the six `VERDICT`-inside-the-fence `parse_fail` stops were the largest single source of leaf flips (two of the five leaf differences, `v8_02` in D and `v8_25` in DR, where Qwen's R2 reject had passing code inside a fence closed after `VERDICT: reject`, halting the debate at R2 instead of continuing to R3; plus two Qwen solos, DR `v8_28` and DR `v8_02`, where a trailing confidence-only fence hid the code block before it). Redrawing both arms with the post-`1a889a4` `parse()` removes the in-fence `parse_fail` / trailing-fence extraction class as a flip source and asks the R3/R4 replies that `crawdad-v8-{d,r}` never reached.
  - Same-prompt variation (recorded caveat and control readout, not a new bar): because `step` serves all 30 tasks sequentially on one llama-server slot with `--cache-reuse 256`, any difference in earlier requests on that slot shifts the prompt-cache state for subsequent requests, even when two requests share the exact prompt and seed. In `crawdad-v8-{d,r}`, all seven R1-Distill `graphs_geometry` solos (empty retrieval read, identical 572-token prompts in D and DR) differed in bytes and one (`v8_18`) flipped from fail in D to pass in DR, contributing +1 to the leaf net from an unchanged prompt. On `crawdad-v8-d2` and `crawdad-v8-r2`, R1-Distill's `graphs_geometry` read is still empty (`retrieved: []`), so those 7 R1 solos (`v8_16`–`v8_22`) remain an embedded same-prompt control across `crawdad-v8-d2` and `crawdad-v8-r2`. The result will record: (a) how many of those 7 R1-Distill solos match byte-for-byte or flip grade between `crawdad-v8-d2` and `crawdad-v8-r2`, (b) any leaf gain or loss on an R1-Distill-opened `graphs_geometry` task (`v8_18`, `v8_19`, `v8_21`) where the opener had an empty read, and (c) the leaf `net` both as-stated over all 30 tasks (which governs the keep/drop bar above) and alongside the count of leaf gains/losses on unchanged-prompt openers.
- Recorded, no bar:
  - `Q` and `R` (solo passes per seat) and `U` (union solo passes) on `crawdad-v8-d2` and `crawdad-v8-r2`, plus solo gains and losses per seat and by family.
  - `crawdad-v8-d2` read against `crawdad-v7-30`'s debate bar (`net` over first speaker's solo `F` >= 3 and `L_D >= max(Q, R)`), as a replication reading under the fixed parser. If `crawdad-v8-d2` reads `net <= 0` over `F`, the debate keep is reopened for the user.
  - Wider same-prompt control: leaf flips and solo flips, `crawdad-v8-d` vs `crawdad-v8-d2` and `crawdad-v8-r` vs `crawdad-v8-r2`, per task and per seat. `parse()` feeds no prompt: `history()` carries reply text only (`visible(row['content'])`), so a prompt is a function of the task, the arm's retrieval block and the earlier replies. Every R1 solo prompt in `crawdad-v8-d2` is byte-identical to `crawdad-v8-d`'s (and `crawdad-v8-r2`'s to `crawdad-v8-r`'s), and a later-round prompt matches wherever the earlier replies of that task matched byte for byte. So `crawdad-v8-d` vs `crawdad-v8-d2` is a same-prompt, parser-only replication over all 30 tasks, not only the 7 R1-Distill `graphs_geometry` solos; where the earlier replies differ in bytes (the stored rows already show that), the difference is same-prompt sampling variation, which the parser cannot explain. Read the flips as a noise floor beside the `net`; no bar attaches.
  - Gains and losses by family and by first-speaker seat, with R1-Distill's `graphs_geometry` prompts (empty read) split out, plus the `v8_17` / `v7_23` named overlap.
  - Leaves and stops per arm (`accept`, `max_rounds`, `no_code`, `parse_fail`), and critic verdicts against the judged module's true grade per seat.
  - Task-by-task comparison against stored `crawdad-v8-d` and `crawdad-v8-r` (`1b801af`) on the six prior in-fence `parse_fail` stops (`D`: `v8_02`, `v8_28`; `DR`: `v8_09`, `v8_19`, `v8_25`, `v8_29`) and the two prior trailing-fence Qwen solos (`DR`: `v8_02`, `v8_28`).
  - Determinism against stored `crawdad-v8-d` and `crawdad-v8-r` (agreed line): within each server load, compare requests by index with the corresponding `crawdad-v8-{d,r}` load while prompt and position match; byte-compare up to the first index that differs in prompt, position, or output, and compare grades only from the next request to the end of that load. Note: Sessions 1–3 of `crawdad-v8-d2` vs `crawdad-v8-d` (and `crawdad-v8-r2` vs `crawdad-v8-r`) issue the same sequence of prompts unless an R1 `no_code` or R2 verdict changes earlier in the load, while Session 4 (`r1d32`) diverges in schedule at the first recovered R2 reject (`v8_02` in D, `v8_25` in DR) that now owes an R3 reply.
  - Prompt tokens (`prompt_tokens`, `prompt_n`), `gen_s`, `tg_tps`, decode hours, wall time; `budget_hit`, `finish` = `length`, `no_code`, `parse_fail`, `think_leak` and never-closed `<think>` per arm; `retrieved` task ids per `crawdad-v8-r2` row; GTT per session and `memory.peak`.
- Cost: `crawdad-v8-d` took 6.69 h of decode (6 h 43 min 38 s wall, 107 replies, 4 sessions) and `crawdad-v8-r` took 6.97 h of decode (7 h 00 min 58 s wall, 108 replies, 5 sessions). Recovering R2/R3 rejects adds R3/R4 turns on tasks that previously stopped at `parse_fail`, so expect ~7–7.5 h of decode per arm (~14–15 h for both; worst case ~44 h if every task runs to R4 at 6,144 tokens). Up to 10 `llmctl` sessions, up to 5 per arm, one model resident at a time, `crawdad-v8-d2` first. Memory as in `crawdad-v8`: GTT +26.7 / +26.8 GiB over ~7.4–7.7 GiB idle, client capped at 8 GiB `MemoryMax` / 16 GiB `RLIMIT_AS`, each grade's child at 1 GiB AS. `report --regrade` must exit 0 on both arms, or the run is unreadable and the bar is not applied.
- Code in this commit, no GPU:
  - `README.md` only (this pre-run section and the top-of-file status line). `bench/loop/debate.py` (`parse()` as merged at `1a889a4`), `bench/loop/memring.py`, `bench/loop/results/crawdad-v7.passes.json`, and `bench/loop/results/crawdad-v8-{d,r}.debate.*` are untouched.
  - Selftest: `python3 -I bench/loop/debate.py --selftest` passes on HEAD (`protocol 137acf32c95d`).
- Procedure: `llm-serve` skill, "CRAwDAD debate". **GPU sessions do not run in this PR; each GPU stage waits for AJ's separate yes after this pre-run commit is reviewed.**
  - Before each invite below: `scripts/preflight.sh` reads READY and DeepSeek is not resident (never load beside it; `invite` and the `llm-serve` skill already gate this, named here for whoever pastes).
  - Arm D (`crawdad-v8-d2`), session 1 (`qwen32` first):
    ```
    scripts/llmctl.py invite qwen32 && { scripts/llmctl.py run -- python3 bench/loop/debate.py step --label crawdad-v8-d2 --set v8; scripts/llmctl.py bye; }
    ```
    Between sessions (no server): `python3 bench/loop/debate.py status --label crawdad-v8-d2`. Sessions 2–5, alternating the seat `status` names until `status` prints `done`:
    ```
    scripts/llmctl.py invite r1d32 && { scripts/llmctl.py run -- python3 bench/loop/debate.py step --label crawdad-v8-d2; scripts/llmctl.py bye; }
    ```
    ```
    scripts/llmctl.py invite qwen32 && { scripts/llmctl.py run -- python3 bench/loop/debate.py step --label crawdad-v8-d2; scripts/llmctl.py bye; }
    ```
    After `done` (CPU only):
    ```
    python3 bench/loop/debate.py report --label crawdad-v8-d2 --regrade
    ```
  - Arm DR (`crawdad-v8-r2`), session 1 (`qwen32` first, `--retrieve` on the first step only):
    ```
    scripts/llmctl.py invite qwen32 && { scripts/llmctl.py run -- python3 bench/loop/debate.py step --label crawdad-v8-r2 --set v8 --retrieve bench/loop/results/crawdad-v7.passes.json; scripts/llmctl.py bye; }
    ```
    Between sessions (no server): `python3 bench/loop/debate.py status --label crawdad-v8-r2`. Sessions 2–5, alternating the seat `status` names (without `--set` or `--retrieve`) until `status` prints `done`:
    ```
    scripts/llmctl.py invite r1d32 && { scripts/llmctl.py run -- python3 bench/loop/debate.py step --label crawdad-v8-r2; scripts/llmctl.py bye; }
    ```
    ```
    scripts/llmctl.py invite qwen32 && { scripts/llmctl.py run -- python3 bench/loop/debate.py step --label crawdad-v8-r2; scripts/llmctl.py bye; }
    ```
    After `done` (CPU only):
    ```
    python3 bench/loop/debate.py report --label crawdad-v8-r2 --regrade
    ```

