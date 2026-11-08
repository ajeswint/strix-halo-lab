# v9 novelty audit (2026-11-07, CPU only)

**Claim, and its limit.** The 30 tasks in `bench/loop/tasks_v9.py` are **unseen to the evaluated local models in this
lab** (`qwen3-32b`, `r1-distill-qwen-32b`): written 2026-11-07 by the code-writer seat (Claude Code, Opus), never sent
to any model endpoint, no probe, no prompt iteration. The authors and reviewers (Claude Code, Grok, AJ) have seen
them. **No claim is made about absence from any model's pretraining data**: several are standard textbook problems
(egg drop, Langton's ant, snake, lucky numbers, RDP), written fresh here. Original in this lab means: not a re-skin of a
v0-v8 task, checked by the audit below.

Tool: `bench/loop/novelty_audit.py` (deterministic, no embeddings, no network). Test: `bench/loop/test_tasks_v9.py`
(`TestNovelty`). Re-run: `python3 bench/loop/novelty_audit.py --set v9 --calibrate --markdown`.

## Method

Every v9 task is compared with all 240 exposed tasks (v0 20, v1-v4 30 each, v5 10, v6-v8 30 each) on six metrics:

| metric | what it measures | detects |
|---|---|---|
| `w5` | Jaccard of word 5-gram shingles of the prompts | copied or lightly edited spec text |
| `tfidf` | cosine of word TF-IDF prompt vectors (IDF over all 270 prompts) | same topic and vocabulary |
| `code` | Jaccard of identifier/keyword sets of the references | same implementation shape |
| `name` | Jaccard of id-slug + entry-point name tokens | same named problem |
| `conc` | Jaccard of concept tags (80 regex tags over prompt + ref: problem type, format, core algorithm) | same problem type / algorithm |
| `io` | entry-point arity signature identical | same I/O shape |

Rules (fixed with `--calibrate` on prior sets **before** the v9 audit was run; not changed afterwards):

- **HARD** (near-duplicate, test fails, no override): `w5 >= 0.08`; `code >= 0.60`; `name >= 0.50 and conc >= 0.40`;
  `tfidf >= 0.30 and conc >= 0.50 and io`.
- **REVIEW**: `tfidf >= 0.35` alone. It also fires on shared words with different meanings, so a REVIEW pair needs a
  written semantic verdict (problem type, I/O shape, core algorithm) in `novelty_audit.REVIEWED_DISTINCT`, or the test
  fails. A stale verdict (pair no longer flagged) also fails.

**Calibration.** `KNOWN_REUSES` are 7 prior pairs where a later set re-used an earlier problem. All 7 are flagged: 4
by a HARD rule (ipv6, url_normalize, rect_union, justify), 3 only by REVIEW (route_lexmin and lexmin_route vs
route_lex at tfidf 0.3995 / 0.4119, bencode_canonical vs bencode at 0.5076). The tfidf line 0.35 sits under the weakest
(0.3995). An earlier draft line of 0.45 missed both route pairs; it was lowered to 0.35 before v9 was scored. For scale,
among the 25,400 pairs (each v1-v8 task vs every task of an earlier set) the final rules flag 56 HARD and 113 REVIEW:
the rules are strict, many flagged prior pairs are related-but-different problems.

A planted copy of a v8 task under a v9 id, and a lightly reworded copy, are both HARD-flagged
(`test_planted_near_duplicates_are_hard_flagged`).

## Result

0 HARD flags. 8 REVIEW pairs on 6 tasks, each with a verdict below. Nearest prior task per metric (value, prior id
prefix); `hard` / `review` = number of flagged prior tasks.

| task | family | max w5 (prior) | max tfidf (prior) | max code (prior) | max name (prior) | max conc (prior) | hard | review (verdict) |
|---|---|---|---|---|---|---|---|---|
| v9_01_perm_mode | formats | 0.01 (v8_12) | 0.24 (v8_04) | 0.39 (v7_10) | 0.33 (v8_02) | 0.40 (v6_29) | 0 | 0 |
| v9_02_size_units | formats | 0.01 (v8_01) | 0.24 (v4_25) | 0.30 (v8_04) | 0.33 (v8_01) | 0.57 (v4_09) | 0 | 0 |
| v9_03_tab_stops | formats | 0.01 (v7_12) | 0.35 (v2_08) | 0.46 (v8_13) | 0.14 (v1_08) | 1.00 (03_eval) | 0 | 1 |
| v9_04_quoted_printable | formats | 0.01 (v8_08) | 0.27 (v7_01) | 0.44 (v8_08) | 0.33 (v7_01) | 0.75 (v2_06) | 0 | 0 |
| v9_05_header_params | formats | 0.00 (v8_05) | 0.29 (v7_02) | 0.37 (v8_28) | 0.33 (v8_01) | 0.67 (v3_04) | 0 | 0 |
| v9_06_flatten_keys | formats | 0.00 (08_spiral) | 0.26 (v7_02) | 0.36 (v7_02) | 0.00 (01_merge) | 0.67 (v4_26) | 0 | 0 |
| v9_07_page_ranges | formats | 0.01 (v8_27) | 0.15 (v6_06) | 0.39 (v8_08) | 0.29 (v8_01) | 0.50 (v1_08) | 0 | 0 |
| v9_08_outline_numbers | formats | 0.00 (v8_26) | 0.24 (v6_20) | 0.35 (v7_10) | 0.14 (07_parse) | 0.50 (v7_29) | 0 | 0 |
| v9_09_zeckendorf | number_theory | 0.01 (v8_10) | 0.30 (v4_24) | 0.42 (v8_25) | 0.20 (20_decode) | 0.38 (v4_24) | 0 | 0 |
| v9_10_aliquot_chain | number_theory | 0.01 (v8_10) | 0.38 (v8_29) | 0.37 (v4_10) | 0.25 (v8_29) | 0.33 (v4_10) | 0 | 1 |
| v9_11_primitive_root | number_theory | 0.01 (v8_12) | 0.49 (v8_13) | 0.48 (v8_10) | 0.33 (v8_13) | 0.57 (v8_10) | 0 | 1 |
| v9_12_factorial_zeros | number_theory | 0.02 (v8_12) | 0.29 (v4_22) | 0.44 (v4_10) | 0.00 (01_merge) | 0.50 (v4_22) | 0 | 0 |
| v9_13_lucky_sieve | number_theory | 0.01 (v8_10) | 0.13 (v4_21) | 0.51 (v8_10) | 0.00 (01_merge) | 0.25 (v1_17) | 0 | 0 |
| v9_14_consecutive_sums | number_theory | 0.02 (v8_10) | 0.19 (v4_21) | 0.50 (v4_10) | 0.25 (v1_12) | 0.50 (v7_17) | 0 | 0 |
| v9_15_gaussian_gcd | number_theory | 0.01 (v7_25) | 0.33 (v7_23) | 0.37 (v6_20) | 0.00 (01_merge) | 0.40 (v8_13) | 0 | 0 |
| v9_16_lca_queries | graphs_geometry | 0.02 (v8_22) | 0.28 (v3_13) | 0.44 (v8_19) | 0.00 (01_merge) | 0.43 (v8_22) | 0 | 0 |
| v9_17_key_maze | graphs_geometry | 0.00 (v3_18) | 0.31 (v7_28) | 0.45 (v7_21) | 0.20 (v7_28) | 0.50 (v7_24) | 0 | 0 |
| v9_18_eq_constraints | graphs_geometry | 0.00 (v3_11) | 0.26 (v3_09) | 0.40 (v7_03) | 0.17 (v3_20) | 0.44 (v4_01) | 0 | 0 |
| v9_19_func_graph_tails | graphs_geometry | 0.01 (v3_14) | 0.27 (v5_07) | 0.48 (v8_25) | 0.00 (01_merge) | 0.50 (v4_08) | 0 | 0 |
| v9_20_grid_line | graphs_geometry | 0.01 (v3_20) | 0.35 (v6_22) | 0.40 (v8_17) | 0.00 (01_merge) | 0.50 (v6_14) | 0 | 0 |
| v9_21_rdp_simplify | graphs_geometry | 0.01 (v8_18) | 0.39 (v8_18) | 0.38 (v8_18) | 0.00 (01_merge) | 0.60 (v2_30) | 0 | 2 |
| v9_22_polar_order | graphs_geometry | 0.01 (v8_20) | 0.37 (v7_25) | 0.36 (v7_22) | 0.33 (v7_03) | 0.60 (v8_18) | 0 | 2 |
| v9_23_egg_drop | simulation_dp | 0.01 (v7_12) | 0.20 (v4_24) | 0.40 (v6_14) | 0.17 (11_min) | 0.20 (v8_12) | 0 | 0 |
| v9_24_interleave_count | simulation_dp | 0.00 (v6_10) | 0.24 (v3_09) | 0.52 (v8_28) | 0.25 (v1_12) | 0.50 (v7_05) | 0 | 0 |
| v9_25_turmite_walk | simulation_dp | 0.01 (v8_23) | 0.26 (v8_23) | 0.36 (v8_28) | 0.20 (v8_23) | 0.33 (15_sudoku) | 0 | 0 |
| v9_26_sandpile_topple | simulation_dp | 0.01 (v6_18) | 0.22 (v6_17) | 0.39 (v7_21) | 0.00 (01_merge) | 0.33 (v1_26) | 0 | 0 |
| v9_27_snake_game | simulation_dp | 0.00 (v7_23) | 0.41 (v8_03) | 0.34 (v7_24) | 0.25 (v4_07) | 0.43 (v7_28) | 0 | 1 |
| v9_28_tax_lots | simulation_dp | 0.01 (v8_20) | 0.12 (v6_19) | 0.33 (v6_20) | 0.00 (01_merge) | 0.50 (v4_17) | 0 | 0 |
| v9_29_jump_reach | simulation_dp | 0.00 (v6_25) | 0.25 (v6_17) | 0.41 (v8_26) | 0.14 (11_min) | 0.25 (v7_29) | 0 | 0 |
| v9_30_dice_totals | simulation_dp | 0.01 (v8_04) | 0.16 (v6_06) | 0.32 (v8_10) | 0.14 (v7_13) | 0.50 (v4_09) | 0 | 0 |

### REVIEW verdicts (writer's; open to the adversarial reviewer)

| v9 task | prior task | tfidf | verdict |
|---|---|---|---|
| v9_03_tab_stops | v2_08_text_justify | 0.35 | Column arithmetic on one line (tab stops; collapse trailing space runs per fixed chunk) vs packing words into lines and distributing spaces. Shared words only. |
| v9_10_aliquot_chain | v8_29_matrix_chain | 0.38 | Shared word "chain". Iterated proper-divisor sums with cycle classification vs interval DP. |
| v9_11_primitive_root | v8_13_primitive_triples | 0.49 | Shared word "primitive" + gcd vocabulary. Multiplicative order mod n vs Pythagorean triple enumeration. |
| v9_21_rdp_simplify | v6_22_segment_pair_kinds | 0.36 | Shared segment vocabulary. Polyline simplification by point-segment distance vs segment-pair intersection classes. |
| v9_21_rdp_simplify | v8_18_closest_pair | 0.39 | Shared squared-distance vocabulary. RDP keep/drop recursion vs minimum pairwise distance. |
| v9_22_polar_order | v4_30_cocircular | 0.35 | Shared point-list vocabulary. Angular sort vs densest circle through points. |
| v9_22_polar_order | v7_25_point_location | 0.37 | Shared cross-product vocabulary. Angular order vs point-in-polygon classification. Angular comparison is a sub-step of some hull algorithms (v2_24, v6_18); no prior task asks for the order itself. |
| v9_27_snake_game | v8_03_case_convert | 0.41 | "snake" the game vs "snake_case". Grid simulation vs string conversion. |

## Families and design

formats v9_01-08 (perm_mode, size_units, tab_stops, quoted_printable, header_params, flatten_keys, page_ranges,
outline_numbers), number_theory v9_09-15 (zeckendorf, aliquot_chain, primitive_root, factorial_zeros, lucky_sieve,
consecutive_sums, gaussian_gcd), graphs_geometry v9_16-22 (lca_queries, key_maze, eq_constraints, func_graph_tails,
grid_line, rdp_simplify, polar_order), simulation_dp v9_23-30 (egg_drop, interleave_count, turmite_walk,
sandpile_topple, snake_game, tax_lots, jump_reach, dice_totals). Same style as v8: one to three functions, explicit
validation (type, range, bool is not an int), worked examples in the prompt, exact arithmetic where it matters, the
algorithm named when a naive one would be too slow. Oracles differ from the references (stdlib `stat.filemode` /
`str.expandtabs` / `Decimal`, brute force, generators that build the expected answer, Fraction-exact geometry).

## Grader checks (CPU, this machine, 2026-11-07)

- `check_tasks.check(tasks_v9.TASKS)`: 30 tasks, 0 failing (refs pass the visible seed, `FRESH_SEED` and seeds 1-5
  under the 512 MiB reference cap; empty solution fails; ref <= 0.8 s; prompts 1,387-2,412 chars; refs <= 90 lines;
  no id or entry-point name reused from v0-v8).
- `tasks_v9_mutants.py`: 60 wrong or naive variants (2 per task: off-by-one, rounding direction, missing validation,
  wrong tie-break, greedy instead of optimal, lost state, input mutation); all 60 FAIL the grader, none by SyntaxError.
- Weak spots, stated: tests check correctness, not complexity, unless a naive solution would exceed the 60 s sandbox
  timeout; v9_16 (LCA) and v9_19 (rho) state O(n log n) / O(n) requirements that a slow but correct solution on the
  test sizes may still pass.

## Limits

Lexical and keyword-semantic only. A problem re-told in new vocabulary whose concept is missing from `CONCEPTS` would
pass. The REVIEW verdicts are the writer's judgement, not an independent one. Thresholds come from 7 known reuse
pairs, a small calibration set.
