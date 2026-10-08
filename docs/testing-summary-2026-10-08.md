# strix-halo-lab: testing summary, 2026-10-04 to 2026-10-08

Status at writing: **all further testing is paused** (user decision, 2026-10-08, after the v6 task set was committed at `eda3c30`). No server is running, no GPU stage of v6 has run.
Source of every number below: `README.md` (the decision log, with each pre-run commit and result commit) and `bench/loop/results/`. Where this file adds a number the README does not carry, it says so ("computed here"). Predictions are marked **PREDICTION** and are not measurements.

Contents: 1. What was tested and why. 2. Results in order. 3. What the results add up to. 4. How far to trust them (noise, confounds). 5. Entropy: noise, diversity and drift. 6. Incidents. 7. Predictions for the paused v6 run. 8. Open items.

---

## 1. What was tested, and the vocabulary

The machine is a Framework Desktop (Ryzen AI Max+ 395, Radeon 8060S iGPU, 128 GB unified memory, 108 GiB of it usable as GTT). The testing falls in three groups:

1. **Hardware and serving benchmarks**: throughput of llama.cpp on HIP and Vulkan, cooling, memory bandwidth.
2. **The orchestrator**: DeepSeek V4 Flash as an adversarial commit reviewer, verdicts kept in SQLite.
3. **The small-model loop (Roadmap 2)**: can Qwen3.6-35B-A3B (the "small model") write correct Python for held-out tasks, graded only by unit tests, and what raises its solve count: more samples, feedback, a second model, a larger fixer?

Vocabulary used throughout:

| Term | Meaning |
|---|---|
| task | a spec (prompt), a test file (the oracle), and a reference solution. Sets v0-v6 hold 20, 30, 30, 30, 30, 10, 30 tasks |
| pass@1 | mean pass rate over all samples (one try per sample) |
| best-of-N | share of tasks where any of N independent samples passes the tests |
| loop (K, E) | `agent.py`: up to E episodes of up to K turns; a failing turn feeds the test error back; stops on pass, repeated code/error, turn cap or token budget. Used K=4, E=4 |
| fresh seed | the solved count is the passing code re-graded with the tests' `random.seed(N)` replaced by `104729`, a seed no turn saw. Closes hard-coding of fed-back cases |
| fix mode | an episode starts from a stored failure (last coded attempt plus its error) instead of the bare task |
| usable failure | an unsolved task whose last attempt came from a coded turn. A task whose every turn hit the token cap has no code to repair |
| held-out | not used for prompt, loop or design iteration |
| pre-run | the README section committed **before** a run: question, metric, threshold, settings, cost. The result is then read against it |

Method, fixed from the first loop run (the `measure` skill): state the question and the keep/drop threshold in a commit before the preflight; run once; report against the threshold; do not tune from the result.

---

## 2. Results, in order

### 2.1 Hardware and serving (2026-10-04)

| Item | Measured | Reading |
|---|---|---|
| Cooling | Fan header 0 has no fan; the CPU fan is on header 1, which the EC curve never ramps. APU hit ~100 °C in two minutes and fell off boost to ~105 W. With both headers forced to 100% (`fan-peg.service`): 138 W / ~2885 MHz for ~8 min, then 120 W / ~2790 MHz at 68-71 °C indefinitely. Prompt processing +35-40% | fixed by a service; open: check the silkscreen at the fan plug |
| Qwen3.6-35B-A3B Q4_K_XL, depth 0 | HIP pp 1392 / tg 53.1; Vulkan pp 1390 / tg 61.7 t/s | |
| DeepSeek V4 Flash IQ2_M | depth 0: HIP 261 / 16.4, Vulkan 223 / 18.6; depth 64k: tg 11.7 (HIP) / 11.1 (Vulkan) | background reviewer, not interactive |
| Mechanism | token generation is memory-bandwidth bound (~117 GB/s effective); power and clock knobs do not move it. HIP wins prompt processing at every depth, Vulkan wins generation at short context, they meet near 32k | serve long context on HIP |
| PyTorch gfx1151 | bf16 matmul 32-36 TFLOPS (hipBLASLt); LoRA smoke test (100M Llama, r=16) loss decreases, 14.4k tok/s, 2 GiB peak | env works; no real training run yet |
| Dropped after measurement/analysis | IOMMU off, GTT above 108 GiB (64k DeepSeek peaks at 86 GiB), forced GPU DPM high (+15-20 W idle for ~2%) | |

### 2.2 Orchestrator (DeepSeek as reviewer), 2026-10-04 to 10-08

| Run | Result |
|---|---|
| 1 | error: no answer. All 8,192 tokens spent reasoning. Fix: `reasoning_budget_tokens` 6144 inside `max_tokens` 12288 |
| 2 | 18,644 prompt tokens, 534 s, 3 findings, **all false positives** (the model judged a JSONL writer with the file it writes omitted) |
| 3 | 5,313 prompt tokens, 415 s, 0 findings, and it **missed a real doc error** (the README claimed the timer was running) |
| 4 | scoped review of 13 files, 1,058 s, 52,729 prompt tokens, 10 reported. Passed the token guard by 519 tokens: 72,502 of 77,058 diff chars were excluded-file samples. Fixed by a 13,500-char sample cap |
| 5 | `baseline` at `606df2d`: no model, the tree up to there waived by decision |

Findings ledger (13 in total): **1 accepted** (#5, `memory()` over-fetched past verdicts, fixed in `606df2d`), **12 rejected** with reasons. Cost: every run used the full reasoning budget, so a review costs ~7 min of GPU whatever the diff size. A caching measurement: resending the same prompt reused 18,640 of 18,644 tokens (0.2 s against 97 s), but any intervening request evicts it (one slot).
Reading: a hit rate of 1 useful finding in 13, plus one real miss, does not justify an unattended hourly timer. The timer is **not installed** (held by decision, reconfirmed 2026-10-08).

### 2.3 The loop, experiment by experiment

All runs: Qwen3.6-35B-A3B UD-Q4_K_XL, Vulkan, 4 slots, ctx 65536 (16k per slot), temperature 0.6, top_p 0.95, top_k 20, reasoning budget 8192 inside `max_tokens` 12288, unless the row says otherwise. **One run per arm throughout; no arm has a spread estimate.**

| # | Set / arm | Question (threshold stated first) | Result | Verdict | GPU h |
|---|---|---|---|---|---|
| 1 | v0, best-of-4 vs pass@1 | best-of-4 beats pass@1 by >= 10 points? | pass@1 **86.25%** (69/80), best-of-4 **100%** (20/20), +13.75 | kept best-of-4. Ceiling hit: set saturated for best-of-N | 1.27 |
| 2 | v1 (30 harder tasks), Qwen vs Laguna | Laguna adds >= 3 tasks to Qwen's best-of-4? | Qwen pass@1 68.3% (82/120), best-of-4 28/30. Laguna 45.0% (54/120), best-of-4 20/30. Union 28/30, **+0** | Laguna dropped as second sampler. Its solved set is a subset of Qwen's | 2.37 + 2.09 |
| 3 | v1 weak 12, Qwen best-of-16 | do 16 samples solve the 2 tasks nobody solved? | regex_match 0/16, add_duration 0/16. best-of-16 28/30 | neither solved; 7/16 regex samples hit the token cap | 3.11 |
| 4 | v1 weak 12, loop vs best-of-16 | loop >= +2 tasks at <= tokens, or +0 at <= 50% | best-of-16 10/12 (1.80M tokens); loop **12/12** (354k tokens, 19.7%) | kept the loop. Caveat below | 1.10 |
| 5 | v2 (30 unseen), loop vs early-stop best-of-16 | loop >= +2 at <= tokens, or +0 at <= 75% | baseline **23/30** (1.73M tokens); loop **29/30** (966k tokens, 55.7%, 62% of wall) | **confirmed**; loop is the default | 7.26 |
| 6 | v3 (30, modelled on the v2 failures), loop alone | headroom: solved <= 26/30 leaves room | **25/30**, 1.40M tokens, 131 turns | room (5 unsolved). Not a keep/drop | 3.61 |
| 7 | v3, fixer arms on the 5 failures | Laguna fixer >= 3/5 and >= Qwen control + 2 | Laguna **1/5**, Qwen fix-mode control **3/5** | not confirmed; Laguna fixer role dropped | 0.49 + 0.88 |
| 8 | v3, DeepSeek fixer on the same 5 | DeepSeek >= 3/5 and >= control + 2 (= 5/5) | **5/5** (30/30 total), 12 turns, 112k tokens, 620 s per turn | confirmed by the stated bar, as a lead: 5 tasks, one run | 2.07 |
| 9 | grader hardening (CPU only) | close the oracle read with no stored pass/fail changing | selftests exit 0 v0-v3; leak probes clean; regrade of 870 stored rows: **0 row flips, 0 fresh flips** | done (`ad05319`). Still a tripwire, not isolation | 0 |
| 10 | v4 probe (10 tasks, hardened grader) | loop leaves >= 2 unsolved? | **4/10** solved, 6 unsolved; 33 of 112 turns at the cap; mini_asm 16/16 turns at the cap (no code at all) | room | 3.29 |
| 11 | v4 tasks 11-30 (20 unaimed) | usable failures over 30 >= 10? | **18/20** solved; 22/30 combined; **7** usable (bar of 10 not met) | thin pool | 2.34 |
| 12 | v5 (10 tasks aimed at the failure families) | arm adds >= 3 usable (pool >= 10)? | **2/10** solved; 8 usable; pool 15 over 40 tasks | bar met | 3.68 |
| 13 | fixer replication on the 15 stored failures | DeepSeek >= Qwen control + 3? | control Q **1/15** (87 turns, 930k tokens, 2.64 h); DeepSeek D **10/15** (52 turns, 534k tokens, 9.76 h) | **confirmed**, gap +9 | 2.64 + 9.76 |
| 14 | v6 pipeline (30 fresh tasks) | stage 1 + DeepSeek stage 2: U >= 6, S2 >= 3, S2 >= U/2 | **not run.** Tasks written, verified, cold-reviewed (30/30) | paused | 0 |

Total GPU time on loop runs: **about 46 h** (computed here from the README's wall times), plus ~0.7 h of orchestrator reviews.

Caveats on rows that look strongest:

- **Row 4** (12/12): `regex_match` passed on the first turn of a *fresh episode*, a single independent draw with no feedback, so feedback gets no credit for it. Most of the token saving came from stopping at the first pass: an early-stop best-of-16 would have used 481k tokens and solved 10, so the loop used 26% fewer and solved 12. On 6 of 10 easy tasks the loop's first pass came later than best-of-16's.
- **Row 5** (29 vs 23): of the 6 tasks only the loop solved, **4 passed on a feedback turn** (int_eval, str_literal, xml_lite, tree_max_path) and 2 on the first turn of a later episode (a fresh draw). Counting only the 4 feedback wins, 27 vs 23 still clears the +2 clause. No task was solved by the baseline and missed by the loop. Over the 29 solved tasks, 12 passed on a turn above 0 and 17 on turn 0.
- **Row 8** (5/5) was a lead until row 13 replicated it on 15 new failures.
- **Row 12**: the 2/10 is by construction. The families were chosen from the v4 failures, so the rate says the aim worked, not that the families are the cause.

### 2.4 Failure anatomy (what the failures were)

- **v0** (11 failures, all on a case the spec states): quoted CSV fields, missing `nonlocal`, glob bracket classes, "IIII" accepted, "1h30m" rejected, one run out of tokens before any code.
- **v1**: `add_duration` failed 16/16 with code (wrong code, not the cap). `regex_match` failed 16/16 with 7 at the cap.
- **v3 unsolved**: forth_vm, farthest_vertex (9 of 14 turns at the cap), mod_sqrts, hist_calendar, billiard.
- **v4 unsolved (8)**: dst_zone, rr_priority, hm_infer, phi_blocks, dec_round, leap_clock, list_schedule, and mini_asm (length failure: every turn hit the 12,288-token cap, so there is nothing to repair). Post hoc grouping (confounded with writer batch): 8 of 11 tasks in {time/scheduling with same-instant rules, program-semantics tools, exact decimal rounding} went unsolved against 0 of 19 in {parsers and file formats, number theory and combinatorics, geometry/graphs/strings}.
- **Token cap**: share of turns ending at 12,288 tokens: v2 16%, v3 22%, v4 probe 29%, v4 tasks 11-30 9%, v5 31%. Never on a passing turn. A cap hit means a long reasoning chain with no answer, so it is a different failure from wrong code.
- **Fixer repair**: DeepSeek's 10 solves came from the 15 stored failures where the Qwen control, with up to 8 turns each, recovered 1. DeepSeek's 5 misses: dst_zone, rr_priority (both end in `timeout`), group_infer, branch_influence, step_snap.

### 2.5 Grader hardening and the memory finding

- **Hole found by an audit** (`~/testing-strategy-audit.md`): the grader wrote `test_solution.py` next to `solution.py`, so a solution could `open()` the oracle (probe: 5,884 chars read). A scan of 865 stored solutions found none that did.
- **Fix**: oracle delivered over stdin after the solution is imported; pass = exit 0 **and** a per-run nonce on stdout (also closes `sys.exit(0)`); a static deny-list on the solution source. 20 attack probes and 3 raw probes must fail, 3 controls must pass. Regrade of all stored rows: 0 flips.
- **Honest limit**: solution and oracle still share one Python process. A forged ready line or a string-built attribute can still get through. It is a tripwire.
- **Deny-list trips in live runs** (hardened grader only: probe 112 + tasks 11-30 95 + v5 126 + control 87 + DeepSeek 52 = 472 turns): **2 trips**, both from `locals()` use (v5 `sigfig_sci`; `step_snap` in the DeepSeek arm). Legitimate code is rarely rejected, but it happens.
- **The 3.7 GiB `agent.py` peak** (v4b 3,734, v5 3,738, fixer 3,740 and 3,737 MiB, against 145 MiB in the probe): cause found 2026-10-08. A candidate appending to a list in a loop grows to the grader's `RLIMIT_AS`, so the cap sets the peak. Cap lowered 4 GiB -> 1 GiB (`b9a0948`): each runaway now peaks at ~0.92 GiB, worst case at `--parallel 4` 3.7 GiB instead of 14.8 GiB against the 8 GiB scope. Regrade: 0 flips.
- **Reference footprint** (`4243aad`): all 150 references (v0-v5) pass at 256 MiB; floor 64 MiB for 140, 128 MiB for 8, 192 MiB for 2. `--selftest` now requires each reference to pass at 512 MiB. This is the reference's footprint, not a claim about candidates.

### 2.6 The v6 set (written, not run)

30 tasks, seeds 6001-6030, four writers (formats/encodings 01-08, number theory/combinatorics 09-16, graphs/geometry 17-23, simulation/DP 24-30), none reading results or the README, no model of the benchmark. Checked: every reference passes the visible seed, 104729 and seeds 1-5 in <= 0.37 s; empty solutions fail; no id or entry-point name reused; `run.py` and `agent.py --selftest` exit 0 on v0-v6.
Cold review: four fresh reviewers saw only the prompts, wrote their own solutions, graded them against the hidden tests. **30 of 30 PASS** (6 on a second attempt, each a reviewer bug such as accepting a tuple where the prompt says list). I re-graded every reviewer solution: all 30 pass. No prompt was changed. Reviewers and writers were Claude subagents, not the benchmarked models.
Sealed: no prompt, loop or design iteration on v6.

---

## 3. What the results add up to

1. **More independent samples help, then saturate** (row 1: +13.75 points at k=4, ceiling 100%).
2. **Feedback beats independent sampling on the tasks tried** (rows 4, 5), at roughly half the tokens, but part of the saving is early stopping, and some "feedback" wins are fresh draws.
3. **Laguna as used here adds nothing**: subset of Qwen as sampler (8 tasks Qwen-only, 0 Laguna-only), 1/5 as fixer against a Qwen control of 3/5. The user's position is that Laguna was used incorrectly; the data supports "no gain in the second-sampler and fixer roles as tested", and does not test any other role.
4. **A bigger model repairs what the small model cannot**: DeepSeek V4 Flash fixed 10/15 stored Qwen failures (control 1/15) and 5/5 in v3. The price is 9.76 h for 15 tasks and the whole GPU (85 GiB model), against 2.64 h for the control.
5. **The failure profile is not uniform**: same-instant ordering, civil time, program-semantics tools and exact decimal rounding fail; parsers, number theory and geometry mostly do not. Token-cap failures are a separate class.
6. **The unaimed pass rate is high**: v2 97%, v4 tasks 11-30 90%, v3 83%. A hard failure pool needed aiming (v5: 20%). So a pipeline's measured gain depends heavily on how the task set was chosen, which is the reason v6 was written unaimed.
7. **Not measured**: DeepSeek alone on fresh tasks (no D-alone arm); the loop with any role for Laguna other than sampler or fixer; training (LoRA) at all; anything about the Qwen+Laguna adversary design.

---

## 4. How far to trust them

**Noise.** The sampler is not reproducible per seed under 4-slot batching: in v2, 5 of 44 matched turn-0 draws disagreed (about 11%, roughly 1.7 tasks of 15). Per-seed pass@1 in v1 ranged 56.7-76.7% for Qwen. Every arm is one run.

Computed here (descriptive; Wilson 95% intervals, and exact sign tests on tasks solved by one arm only. They treat tasks as independent and ignore sampler noise, so they bound optimism, they do not replace the pre-run bars):

| Result | Point | 95% interval | Paired comparison (tasks only one arm solved) | Sign-test p (two-sided) |
|---|---|---|---|---|
| v0 pass@1 | 69/80 = 86% | 77-92% | | |
| v1 Qwen pass@1 | 82/120 = 68% | 60-76% | Qwen-only 8, Laguna-only 0 | 0.008 |
| v1 Laguna pass@1 | 54/120 = 45% | 36-54% | | |
| v1 weak 12: loop vs best-of-16 | 12/12 vs 10/12 | 76-100% vs 55-95% | loop-only 2, baseline-only 0 | 0.5 |
| v2 loop vs early-stop best-of-16 | 29/30 vs 23/30 | 83-99% vs 59-88% | loop-only 6, baseline-only 0 | 0.031 |
| v3 loop alone | 25/30 | 66-93% | | |
| v3 fixers on 5: C vs B vs A | 5, 3, 1 of 5 | | C-only 2 vs B; B-only 2 vs A | 0.5 each |
| v4 combined loop | 22/30 | 56-86% | | |
| v5 loop (aimed) | 2/10 | 6-51% | | |
| fixer replication: D vs Q on 15 | 10/15 vs 1/15 | 42-85% vs 1-30% | D-only 9, Q-only 0 | 0.004 |

Reading the table: the row-5 result and the fixer replication hold up against noise; the +2 in row 4 and the 5/5 in row 8 do not (p = 0.5), which is why both were labelled leads and why row 13 mattered.

**Confounds, stated so they are not rediscovered:**

- **Selection effects.** Row 3/4's 12 "weak" tasks were chosen because Qwen scored <= 2/4 on them, so any rerun gains by regression to the mean (both arms were run on the same selection, so the comparison is fair, the absolute numbers are not). The 15 fixer inputs are Qwen's own last attempts at tasks it failed.
- **Different models, different quantisation.** DeepSeek is IQ2_M on HIP with one slot; Qwen is Q4_K_XL on Vulkan with four. "DeepSeek fixes more" is a statement about this model pair, in this pipeline, from stored Qwen code. It says nothing about DeepSeek writing solutions from the bare task.
- **Unequal inputs.** The fixer inputs are not uniform (a deny-list line, a bare `timeout`, an earlier coded turn). Both arms got the same inputs, so the comparison is unaffected, but absolute rates are not a rate of fixing Qwen's typical failure.
- **Thresholds are judgements.** The +3 on 15 (above the ~1.7-task flip), the pool of 10, U >= 6: stated before the runs, not derived.
- **Family labels are post hoc** and confounded with writer batch.
- **Pre-run bars were set after earlier results on the same lines of work** (each pre-run follows the previous result). No single bar was tuned on its own outcome, but the sequence is adaptive: the garden-of-forking-paths risk applies to the programme, not to any one row.
- **Grader is a tripwire.** If a candidate defeated it, the count would be inflated, not the failures. 870 stored rows regraded with 0 flips is evidence the stored counts are stable under the stricter grader, not proof of isolation.
- **Task-writer and reviewer independence** relies on instructions (do not read `results/`), not on enforcement.

---

## 5. Entropy

The word covers three different things here.

### 5.1 Result entropy (noise)
See section 4: ~11% opening-draw flips, single runs, no spreads, per-seed pass@1 spreads of 20-25 points (v0 75-100%, v1 Qwen 56.7-76.7%). Differences under ~2 tasks per 15-30 are re-roll size. The design response so far: stated bars with margins above the flip rate, fresh-seed regrades, reuse of baselines instead of reruns.

### 5.2 Diversity entropy (collapse risk)
Every passing v0 solution was textually distinct after whitespace removal. That is a weak measure (identifiers differ). No structural diversity measure exists yet, and it is a precondition for any self-training or LoRA on these outputs. README roadmap item 3 already says verdicts are not training pairs and that model collapse and a bad judge are the named risks. Nothing in 2.3 reduces that risk.

### 5.3 System entropy (drift and unmanaged state), ledger at 2026-10-08

| Item | State | Risk | Control in place |
|---|---|---|---|
| Orchestrator timer | **not installed**, held by decision | none while absent | README line; install steps documented |
| `bench/loop/results/fix15-v4-stored.jsonl`, `fix15-v5-stored.jsonl` | untracked inputs (filters of committed results) | rebuild needed if lost; the README gives the script | documented in the fixer section |
| `/data/bench/loop` vs repo | **DRIFT**: `run.py` differs and `tasks_v6.py` is missing in `/data/bench` (from `eda3c30`, 2026-10-08) | a run started from `/data/bench` would use the old grader/no v6. Runs are meant to start from the repo root | `scripts/drift-check.sh` reports it; a sync is a separate live-sync step the pre-run assigns to the user |
| `etc/sudoers.d/llmctl`, `etc/ufw/user.rules` | UNREADABLE by the checker (root-only) | unverified copies | known; compare with `sudo diff` |
| Grader | tripwire, not isolation | an evasion inflates solves | regrade script `regrade_stored.py` (pass files explicitly; no-arg crashes on the summary-less fix15 files) |
| Unpushed commits | `b883745` (unpause note) and `eda3c30` (v6 tasks) are on `main` locally, not on origin; this file's commit will be too | the reviewer's checkout lags until pushed | commits are pushed only on request |
| 29119 route | **dropped**; 2013 first editions (copies licensed to other institutions) stay in `~/Documents/projects`, outside the repo | the loop-testing pause that waited on them is moot; do not quote or commit the text | README top paragraph |
| Memory exhaustion | guarded now by `preflight.sh`, `llmctl` sessions, gpu-guard hook, 8 GiB `run` cap | gpu-guard fails open if GTT is unreadable; a direct `sudo systemctl start llama-deepseek` bypasses preflight | two known gaps recorded in the README |
| Model residency | one model at a time (DeepSeek ~85 GiB + Qwen ~23 GiB = all 108 GiB) | the Qwen+Laguna design needs a deliberate guard change | not done |

Principle applied: set-and-forget fixes, no polling loops or watchdogs unless a setting is seen to revert.

**Resolved after writing (2026-10-08):** `b883745`, `eda3c30` and `407323c` were pushed (`origin/main` = `407323c`), and `run.py` and `tasks_v6.py` were synced to `/data/bench/loop` (`cmp` identical; `drift-check.sh` then reported only the two root-only files). The rows above are the state at writing.

---

## 6. Incidents (they shaped the process)

- **2026-10-04 18:16**: `llama-perplexity` started beside the 85 GiB DeepSeek server; swap hit 0, the kernel OOM-killed Cursor, reboot needed. Led to `preflight.sh` and the "never load beside DeepSeek" rule.
- **2026-10-05**: an outside agent ("Grok Bot", with sudo) spent a night "fixing" RDP and left default credentials in plaintext drop-ins and 3389/SSH open to any source. Cleaned up the same day; ufw back to LAN-only.
- **2026-10-07 03:58**: a 95 GiB `python3` OOM-killed in Cursor's scope while Qwen held 28 GiB; the v4 probe run (started 03:38) lost with no rows written. Led to `llmctl` sessions and the `run` memory cap. What allocated the 95 GiB is not established.
- **2026-10-07**: the oracle-read hole (2.5).
- **Hardware**: Samsung 990 PRO died (ESD), RMA.
- **Process errors owned**: a first regrade crashed on the summary-less stored files; a first reading of the 3,747 MiB regrade peak as a possible problem was checked by replay before being called done.

---

## 7. Predictions for the paused v6 run

Made 2026-10-08, **before** any v6 model run, so they can be scored. They are my judgement from the tables above, not measurements, and the Qwen+Laguna design may change which question v6 answers.

Basis: unaimed-set solve rates 97% (v2), 90% (v4 tasks 11-30), 83% (v3), pooled v4 73%; the aimed set 20%. The v6 buckets are broad and unaimed, written by writers who did not see failures, prompts at least as long as v4's (1,000-3,200 chars), references with hard exact-tie-break rules.

| Quantity | Prediction | Reasoning |
|---|---|---|
| S1: Qwen loop solves, of 30 | **21-25** (central 23); plausible range 17-27 | between v3 (83%) and the pooled v4 (73%); the cold-review solver (a stronger model) passed 30/30, which says the specs are determinate, not that they are easy |
| Unsolved | 5-9 | 30 - S1 |
| No-coded-turn failures (mini_asm type) | 0-2 | 1 in 40 so far, plus heavy-reasoning tasks like v6_24/25/29 are candidates |
| U (usable failures) | 4-8, central 6 | **P(U >= 6) about 50%** |
| Token-cap share of turns | 10-25% | v4b 9%, v3 22%, v5 31% (aimed) |
| Stage 1 wall time | 4-6 h (ceiling ~14 h) | v4b 2.34 h / 20 tasks, v3 3.61 h / 30 |
| Stage 2 (DeepSeek) | ~0.65 h per usable failure; 4 h at U=6 | replication: 35,140 s for 15 |
| S2 (DeepSeek solves) | about half of U (replication 10/15 = 67% on aimed failures; the unaimed ones may be easier to repair or harder to fail) | |
| Bar met (U >= 6 and S2 >= 3 and S2 >= U/2) | **roughly 25-30%** | P(U >= 6) ~ 0.5 times P(S2 clears U/2, given U >= 6) ~ 0.55 |
| Most likely failure families | same-instant ordering / state-machine semantics (v6_24 regvm, 25 mlfq, 26 heap, 30 editor log), exact tie-break DP (27), big-count number theory (12, 14, 15) | extrapolated from 2.4; labelled as a guess |
| Memory peak, `agent.py` `--parallel 4` | ~1-4 GiB, under 8 GiB cap | 1 GiB grader cap, 4 graders |

The most probable single outcome is "thin": U in 4-5, which the pre-run records as no claim about the stage.
The prediction that matters for planning: a pipeline run costs ~9-11 h of GPU for an answer that is likely to be either thin or confirmed-by-a-lead, and the design it would evaluate may be superseded. That is why the run is paused rather than cancelled.

---

## 8. Open items

1. **v6 GPU stages** (Qwen stage 1 ~5.6 h, DeepSeek stage 2): paused; each needs the user's separate yes and a preflight right before the load. The DeepSeek `bye` is the user's, at a terminal.
2. **Qwen + Laguna adversary design**: unspecified. Constraints from the evidence: tests outrank any judge; the final grade stays the fixed oracle with the fresh seed; two small models fit in GTT (~28 + ~21 GiB) but need a deliberate change to the one-model guard; Laguna's two earlier roles failed, so the design needs to say why the new role differs. Design on v0-v5; leave v6 sealed.
3. **DeepSeek's role** in that design: sequential fixer, adversary, or out. Its one strong measured property is repair.
4. **Drift**: `/data/bench/loop` needs a sync of `run.py` and `tasks_v6.py` before any run is started from there.
5. **Unmeasured**: DeepSeek alone on fresh tasks; a Qwen best-of-N or longer-budget control on the 15 failures with equal GPU hours; a cold-cache DeepSeek load time; reasoning-budget effects (45% of v0 samples, 36 of 80, ran past 8,192 tokens and passed 75% against 95% for the rest; correlation only); any LoRA run.
6. **Orchestrator timer**: held.
7. **Protocol**: the 29119 route was dropped; the standing protocol is the pre-run bars and the `measure` skill. A deviation register (each loosened control, why, risk, compensating control) is a possible deliverable for a reviewer; not written.

---

*Commits referenced:* `1035d5e` v0, `10fc559` v1 Laguna, `22fb4a4`/`2b4045e` loop vs best-of-16, `27e2be7` v2 pre-run, `99f919a`/`25c286d` v3, `b6bf2d0`/`ebf9923` Laguna fixer, `41717a1`/`2512b38` DeepSeek fixer v3, `c821b3d`/`ad05319` grader hardening, `1ac0423`/`4e3de27` v4 probe, `782cdfd`/`e183af5` v4 tasks 11-30, `e7f6c8d`/`a411f62` v5, `ba90a8f`/`8a41410`/`72d8d26` fixer replication, `606df2d` orchestrator baseline, `b9a0948` grader cap, `4243aad` reference cap, `eda3c30` v6 tasks.
