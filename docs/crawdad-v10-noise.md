## v10 tasks: held-out set for the CRAwDAD retrieval and noise test (2026-11-11)

Written by Antigravity (code-writer) inline, with no subagents, every check under `prlimit --as=4294967296`, and no GPU. No model has seen these tasks.
- Held-out set of exactly 90 tasks balanced across v7's four families in a 23/22/22/23 split: formats v10_01-08 and v10_31-45 (23), number_theory v10_09-15 and v10_46-60 (22), graphs_geometry v10_16-22 and v10_61-75 (22), simulation_dp v10_23-30 and v10_76-90 (23) (`memring.FAMILIES["v10"]`).
- Design:
  - 90 tasks in v7's four families: formats (23), number_theory (22), graphs_geometry (22), simulation_dp (23).
  - Target scale: 90 tasks (23/22/22/23). Why 90: same-prompt sampling and prompt-cache variation causes ~1 task flip per 30 tasks, so an observed net difference of +3 on n=30 sits right at the noise boundary and cannot separate signal from noise. Scaling to n=90 provides sufficient statistical power to test retrieval against noise floor bounds.
  - Style: identical to v7_11-30 and v8 (one or two functions, ~6 rules each with examples, explicit type and value error handling, reference implementations <= 65 lines, measured 11-65 lines).
  - Novelty: checked against tasks_v1 through v8 in `bench/loop` and v9 in `bench/loop/tasks_v9.py` on branch `lab/coding-memory-loop-v1`. All task IDs and function entry points are distinct; no substantive duplicate of any v1-v9 task.
- Tasks, seeds 10001-10090:
  - formats (23): 01 mac_address, 02 netstring, 03 leb128, 04 cron_field, 05 slugify_text, 06 isbn13, 07 http_range, 08 card_deck, 31 hex_dump, 32 c_string_escape, 33 base32_rfc, 34 nmea_checksum, 35 soundex_code, 36 roman_numeral, 37 zigzag_varint, 38 base58_btc, 39 uuid_urn, 40 intel_hex, 41 semver_parse, 42 tsv_record, 43 syslog_timestamp, 44 coap_option, 45 bcd_decode;
  - number_theory (22): 09 mobius_mertens, 10 legendre_jacobi, 11 carmichael_lambda, 12 continued_fraction, 13 mod_sqrt, 14 farey_sequence, 15 miller_rabin, 46 lucas_lehmer, 47 chinese_remainder, 48 pollard_rho, 49 sum_of_divisors, 50 stern_brocot, 51 bezout_identity, 52 lucas_theorem, 53 multiplicative_order, 54 totient_sum, 55 liouville_lambda, 56 factorial_mod_p, 57 ramanujan_sum, 58 continued_fraction_sqrt, 59 lucas_sequence, 60 engel_expansion;
  - graphs_geometry (22): 16 polygon_centroid, 17 bounding_box_3d, 18 bipartite_match, 19 bellman_ford_neg, 20 point_winding, 21 max_clique_small, 22 degree_sequence, 61 convex_hull_2d, 62 tarjan_scc, 63 kruskal_mst, 64 circle_intersection, 65 welsh_powell_coloring, 66 point_in_convex, 67 dijkstra_path, 68 segment_intersection, 69 graph_isomorphism, 70 minimum_enclosing_circle, 71 articulation_points, 72 eulerian_path_directed, 73 tree_diameter_radius, 74 minkowski_sum_convex, 75 edmonds_karp_flow;
  - simulation_dp (23): 23 traffic_light, 24 rod_cutting_cost, 25 token_bucket, 26 optimal_bst, 27 vending_machine, 28 word_break_dp, 29 assembly_line_dp, 30 connect_four, 76 elevator_scan, 77 knapsack_01_exact, 78 lcs_three_strings, 79 cache_clock_second_chance, 80 min_coins_change, 81 turing_machine_1d, 82 edit_distance_ops, 83 round_robin_quantum, 84 max_sum_rectangle, 85 game_of_life_torus, 86 longest_alternating_subseq, 87 particle_collision_1d, 88 subset_sum_count, 89 packet_queue_leaky, 90 max_weight_independent_path.
  Prompts are 1,064-2,672 chars, references 11-65 lines. Each task test suite contains exactly one `random.seed(10000 + NN)` call with property checks or independent verification oracles.
- Checks:
  - `check_tasks.py --set v10`: 90/90 OK (0 failing).
  - `check_tasks.py --set v8`: 30/30 OK.
  - `run.py --selftest --set v10`: OK (90 tasks).
  - `agent.py --selftest --set v10`: OK.
  - `debate.py --selftest`: OK (default protocol `137acf32c95d` preserved; non-default and restricted seed base checks pass).
  - `memring.py --selftest`: OK.
  - Mutant control (`bench/loop/test_tasks_v10.py`): 180 single-edit AST mutants in `bench/loop/tasks_v10_mutants.py`, exactly 2 per task, tested at visible seed under `run.grade`. All 180 fail (0 survivors, 0 equivalent mutants).
  - Unittest: `python3 -m unittest bench/loop/test_tasks_v10.py`: 4 tests ran, OK.
- Registration:
  - `run.SETS["v10"] = "tasks_v10"`.
  - `memring.FAMILIES["v10"]` maps all 90 task IDs to their respective families (23 formats, 22 number_theory, 22 graphs_geometry, 23 simulation_dp).

## CRAwDAD noise floor and retrieval on v10 (pre-run)

Stated before any GPU session (2026-11-11 CT). For review before running; **no GPU session starts in this commit; stage N and stage V each wait for AJ's separate yes, and V's bar is fixed from N's result before V runs.**

- Context and Question: On `v8` (n=30), the fixed-parser redraw (`crawdad-v8-d2` vs `crawdad-v8-r2`) gave leaf D 9/30 vs DR 12/30 (net +3), repeating the pre-fix result (`crawdad-v8-d` 8/30 vs `crawdad-v8-r` 11/30, net +3). Both runs sat exactly on the keep bar (`net >= 3`). However, in both runs, one gain (`v8_18_closest_pair`) was an R1-Distill `graphs_geometry` task with an empty retrieval read (`retrieved: []`), whose prompt and seed were identical between D and DR. Same-prompt variation (KV prompt cache reuse differences across sequential turns on `--cache-reuse 256` and sampling nondeterminism) flips ~1 task per 30 tasks, so net +3 cannot be statistically separated from noise. This pre-run defines a two-stage experiment:
  1. **Stage N (Noise Floor on v8)**: Measure the unprompted leaf flip rate and leaf total spread across three independent D runs on `v8` under the fixed parser with distinct reply seeds.
  2. **Stage V (Retrieval on v10)**: Test retrieval on the larger held-out set `v10` (n=90), evaluated with an exact paired sign test and a noise-scaled threshold pinned T=9 from p_same=1/7.

- Stage N: Noise-floor measurement on `v8` (30 tasks):
  - Arms: repeat the unchanged D arm (`crawdad-v8-d2` configuration, fixed parser, protocol `137acf32c95d` family) on `v8` twice more with distinct reply seed bases:
    - Label `crawdad-v8-d3`: `--seed-base 4100` (reply seeds `4100 + round`), protocol `667669b28bca`.
    - Label `crawdad-v8-d4`: `--seed-base 4200` (reply seeds `4200 + round`), protocol `7bc16a2123d1`.
    - Existing arm `crawdad-v8-d2` (`seed_base 4000`, protocol `137acf32c95d`, leaf 9/30) serves as the first arm of the triad {d2, d3, d4}.
    - All runs share: `COIN_SEED = 42` (15 openers per seat), fresh grading seed `104729`, sampling (`temperature = 0.6`, `top_p = 0.95`, `top_k = 20`), budgets (`REASONING_BUDGET = 2048`, `MAX_TOKENS = 6144`), build (`b11669-620d2225c` on `vk`), model files (`/data/models/Qwen3-32B-Q4_K_M.gguf`, `/data/models/DeepSeek-R1-Distill-Qwen-32B-Q4_K_M.gguf`), and endpoint defaults (`qwen32` and `r1d32`, `vk`, `ctx 32768`, 1 slot, `--parallel 1`).
  - Stored same-seed / same-prompt flip rates (measured on CPU):
    - `crawdad-v8-d` vs `crawdad-v8-d2` (same seed base 4000, coin 42, VK build; pre-fix vs fixed parser): 100/107 (93.5%) replies byte-identical; 107/107 (100%) grade identical. 0 grade flips. Leaf went 8/30 -> 9/30 purely because `v8_02_morse_text` Qwen R2 reject was parsed under the new parser and reached R3 (R1-Distill accepted) to pass (108 replies total in d2 vs 107 in d; the extra row is R1-Distill round 3 only).
    - `crawdad-v8-d2` vs `crawdad-v8-r2` on the 7 R1-Distill `graphs_geometry` solos (`v8_16`–`v8_22`) with empty retrieval read (identical prompt per task, e.g. 572 tokens for `v8_18`, and seed 4001): 0/7 matched byte-for-byte due to KV cache reuse drift across sequential requests; 1/7 grade flips (`v8_18_closest_pair` flipped False in D2 to True in R2, producing +1 net from same-prompt noise).
  - Metrics across {d2, d3, d4}:
    - Leaf totals L_2, L_3, L_4 in [0, 30].
    - Pairwise discordant counts: D_ij = sum_{t=1}^{30} [L_i(t) != L_j(t)] for (i, j) in {(d2,d3), (d2,d4), (d3,d4)}.
    - Cross-seed triad discordance and spread: mean discordant rate p_flip = (1 / 90) * (D_23 + D_24 + D_34), leaf range Delta_N = max(L) - min(L), sample standard deviation s_L = sqrt((1/2) * sum_i (L_i - L_bar)^2). These cross-seed triad metrics across different seed bases (4000/4100/4200) are reported as recorded spread only, not as the paired-null sigma for same-seed contrasts.
  - Pre-committed rule setting the v10 Stage V bar:
    - Stage V is a same-seed paired contrast (D vs DR at seed base 4000) over N=90 tasks. Under the paired null hypothesis of zero retrieval effect, task flips between same-seed runs occur due to same-seed / same-prompt variation (KV cache reuse drift across sequential requests and sampling nondeterminism).
    - Base T_noise on the measured same-seed paired flip rate already reported in this section: 0 grade flips on d vs d2 (0/30) and 1/7 on the identical empty-read R1 graphs solos (p_same = 1/7 = 0.143 ≈ 4.3/30).
    - For each task i, the paired contrast indicator X_i in {-1, 0, +1} has E[X_i] = 0 and Var(X_i) = p_same = 1/7, yielding net noise variance Var(net) = 90 * (1/7) = 90/7 and paired noise standard error sigma_paired = sqrt(90/7) ≈ 3.586.
    - To guard against noise with a ~99% one-sided confidence margin (2.5 * sigma_paired), bounded below by the minimum net gain required for an exact paired sign test to reach p <= 0.05 when at least 1 discordant loss occurs (7 gains vs 1 loss, net +6, exact binomial p = 0.035), the noise net threshold is pinned as a number before data:
      T_noise = max(ceil(2.5 * sqrt(90 / 7)), 6) = max(ceil(2.5 * 3.586), 6) = max(9, 6) = 9
    - Numeric evaluation:
      - p_same = 0 (observed d vs d2 on 30 tasks / 107 replies: 0 grade flips): ceil(2.5 * 0) = 0 => T_noise = max(0, 6) = 6 (the sign-test lower bound).
      - p_same = 1/7 = 0.143 ≈ 4.3/30 (observed same-prompt empty-read flip rate on the 7 R1-Distill graphs solos): ceil(2.5 * sqrt(90 / 7)) = ceil(8.96) = 9 => T_noise = max(9, 6) = 9, pinned as the threshold before data.
    - Check against v8 effect: On v8 (n=30), retrieval produced leaf 12 vs 9 without retrieval (+3 on 30 tasks, +10.0%). Scaled to n=90, a repeat of the v8 effect (+3 * 3 = +9 net gain) explicitly meets the pinned threshold T = 9 (+9 >= 9). Keep still also requires exact sign-test p <= 0.05 on discordant tasks (e.g. 9 gains vs 0 losses gives p = 0.002; 10 gains vs 1 loss gives net +9 with p = 0.006; 11 gains vs 2 losses gives net +9 with p = 0.011).

- Stage V: Retrieval test on `v10` (90 tasks):
  - Arms: Both run on all 90 `v10` tasks (`--set v10`) with `COIN_SEED = 42` (45 openers per seat), `SEED_BASE = 4000` (seeds `4000 + round`), fresh grading seed `104729`, same sampling, budgets, build, model files, and endpoint defaults as `crawdad-v8`:
    - D, label `crawdad-v10-d`: `debate.py` baseline, protocol `137acf32c95d`, no `--retrieve`.
    - DR, label `crawdad-v10-r`: identical to D except `--retrieve bench/loop/results/crawdad-v7.passes.json` on step 1, protocol `a01c192bac5d`. Every prompt starts with up to k=3 passed v7 modules from the task's family.
  - Evaluation Bar for n=90:
    - Precondition (no-room rule): if L_D >= 77/90 (~85%) or L_D <= 9/90 (~10%), the task pool is saturated or uninformative; no verdict is rendered.
    - Strict partition of (net, p) space: With net = L_R - L_D (gains - losses) and p being the exact one-sided paired sign test p-value on discordant tasks (k = losses, n_disc = gains + losses, p_0 = 0.5), every outcome falls into exactly one category with no overlap and no gaps:

      | Net gain (net = L_R - L_D) | Exact sign test p <= 0.05 | Exact sign test 0.05 < p <= 0.10 | Exact sign test p > 0.10 |
      | :--- | :--- | :--- | :--- |
      | net >= T_noise (pinned T = 9) | **Keep** | **Inconclusive** | **Drop** |
      | 0 < net < T_noise (pinned T = 9) | **Inconclusive** | **Inconclusive** | **Drop** |
      | net <= 0 | **Drop** | **Drop** | **Drop** |

    - Partition definitions:
      - **Keep**: net >= T_noise (pinned T = 9) AND p <= 0.05. Both the noise floor and statistical significance are satisfied.
      - **Drop**: net <= 0 OR p > 0.10. Retrieval provided no net gain or the outcome was statistically indistinguishable from chance.
      - **Inconclusive**: 0 < net AND p <= 0.10 AND NOT Keep (specifically: 0 < net < T_noise with p <= 0.10, or net >= T_noise with 0.05 < p <= 0.10, for pinned T = 9). Defaults to drop unless AJ approves expansion.
    - Same-prompt caveat handling: DR tasks where the opener had an empty retrieval read (`retrieved: []`, e.g. R1-Distill on `graphs_geometry`) share identical opener prompts with D. The primary bar governs over all 90 tasks, but results will explicitly tabulate net gain excluding empty-read opener gains/losses. If excluding empty-read gains drops net < T_noise (pinned T = 9), the keep carries a recorded caveat.

- Cost estimates from stored `v8` redraw logs (`/tmp/lab-seats/crawdad-v8-{d2,r2}/session*.log` and `.debate.jsonl`):
  - `crawdad-v8-d2` (n=30): 4 sessions, 108 replies, decode 24,593 s (6.83 GPU-hours; GPU-hours from summed gen_s is the primary figure), prompt tok 115,140, comp tok 264,580 (total 379,720).
  - `crawdad-v8-r2` (n=30): 5 sessions, 109 replies, decode 25,048 s (6.96 GPU-hours; wall ~7 h 10 min across sessions), prompt tok 210,825, comp tok 270,199 (total 481,024).
  - Scaled for `v10` (n=90, exactly 3x tasks):
    - D (v10): ~324 replies, ~20.5–21.0 GPU hours decode (~16–18 h wall), ~1.14M tokens.
    - DR (v10): ~327 replies, ~20.9–21.5 GPU hours decode (~21–23 h wall), ~1.44M tokens.
  - Total GPU compute hours:
    - Stage N (noise floor on v8, 2 runs `d3` and `d4`): 2 * 6.83 h ~= 13.7 GPU hours.
    - Stage V (retrieval on v10, 2 runs `crawdad-v10-d` and `crawdad-v10-r`): 2 * 21.0 h ~= 42.0 GPU hours.
    - Total GPU hours for Stage N + Stage V: ~55.7 hours.

- Procedure and Commands:
  - **No GPU session starts in this commit; stage N and stage V each wait for AJ's separate yes, and V's bar is fixed from N's result before V runs.**
  - Preflight requirement: Before each `invite`, `scripts/preflight.sh` must read READY and DeepSeek must not be resident.
  - **Stage N: Arm `crawdad-v8-d3` (seed base 4100)**:
    - Session 1 (`qwen32` first):
      ```
      scripts/llmctl.py invite qwen32 && { scripts/llmctl.py run -- python3 bench/loop/debate.py step --label crawdad-v8-d3 --set v8 --seed-base 4100; scripts/llmctl.py bye; }
      ```
    - Between sessions: `python3 bench/loop/debate.py status --label crawdad-v8-d3`.
    - Sessions 2–5 (alternating `r1d32` and `qwen32` until status is `done`):
      ```
      scripts/llmctl.py invite r1d32 && { scripts/llmctl.py run -- python3 bench/loop/debate.py step --label crawdad-v8-d3; scripts/llmctl.py bye; }
      ```
      ```
      scripts/llmctl.py invite qwen32 && { scripts/llmctl.py run -- python3 bench/loop/debate.py step --label crawdad-v8-d3; scripts/llmctl.py bye; }
      ```
    - After done (CPU only):
      ```
      python3 bench/loop/debate.py report --label crawdad-v8-d3 --regrade
      ```
  - **Stage N: Arm `crawdad-v8-d4` (seed base 4200)**:
    - Session 1 (`qwen32` first):
      ```
      scripts/llmctl.py invite qwen32 && { scripts/llmctl.py run -- python3 bench/loop/debate.py step --label crawdad-v8-d4 --set v8 --seed-base 4200; scripts/llmctl.py bye; }
      ```
    - Between sessions: `python3 bench/loop/debate.py status --label crawdad-v8-d4`.
    - Sessions 2–5 (alternating `r1d32` and `qwen32` until status is `done`):
      ```
      scripts/llmctl.py invite r1d32 && { scripts/llmctl.py run -- python3 bench/loop/debate.py step --label crawdad-v8-d4; scripts/llmctl.py bye; }
      ```
      ```
      scripts/llmctl.py invite qwen32 && { scripts/llmctl.py run -- python3 bench/loop/debate.py step --label crawdad-v8-d4; scripts/llmctl.py bye; }
      ```
    - After done (CPU only):
      ```
      python3 bench/loop/debate.py report --label crawdad-v8-d4 --regrade
      ```
  - **Stage V: Arm `crawdad-v10-d` (v10 baseline, seed base 4000)**:
    - Session 1 (`qwen32` first):
      ```
      scripts/llmctl.py invite qwen32 && { scripts/llmctl.py run -- python3 bench/loop/debate.py step --label crawdad-v10-d --set v10; scripts/llmctl.py bye; }
      ```
    - Between sessions: `python3 bench/loop/debate.py status --label crawdad-v10-d`.
    - Sessions 2–5 (alternating `r1d32` and `qwen32` until status is `done`):
      ```
      scripts/llmctl.py invite r1d32 && { scripts/llmctl.py run -- python3 bench/loop/debate.py step --label crawdad-v10-d; scripts/llmctl.py bye; }
      ```
      ```
      scripts/llmctl.py invite qwen32 && { scripts/llmctl.py run -- python3 bench/loop/debate.py step --label crawdad-v10-d; scripts/llmctl.py bye; }
      ```
    - After done (CPU only):
      ```
      python3 bench/loop/debate.py report --label crawdad-v10-d --regrade
      ```
  - **Stage V: Arm `crawdad-v10-r` (v10 retrieval, seed base 4000)**:
    - Session 1 (`qwen32` first, `--retrieve` on first step only):
      ```
      scripts/llmctl.py invite qwen32 && { scripts/llmctl.py run -- python3 bench/loop/debate.py step --label crawdad-v10-r --set v10 --retrieve bench/loop/results/crawdad-v7.passes.json; scripts/llmctl.py bye; }
      ```
    - Between sessions: `python3 bench/loop/debate.py status --label crawdad-v10-r`.
    - Sessions 2–5 (alternating `r1d32` and `qwen32` until status is `done`):
      ```
      scripts/llmctl.py invite r1d32 && { scripts/llmctl.py run -- python3 bench/loop/debate.py step --label crawdad-v10-r; scripts/llmctl.py bye; }
      ```
      ```
      scripts/llmctl.py invite qwen32 && { scripts/llmctl.py run -- python3 bench/loop/debate.py step --label crawdad-v10-r; scripts/llmctl.py bye; }
      ```
    - After done (CPU only):
      ```
      python3 bench/loop/debate.py report --label crawdad-v10-r --regrade
      ```

