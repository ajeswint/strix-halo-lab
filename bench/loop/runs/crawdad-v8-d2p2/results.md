# crawdad-v8-d2p2 — quality-check result

Graded 2026-11-17 after the run finished at 7:23:22 PM CST, against the
pre-registered bar in `prereg.md` (committed on `lab/d2p2-prereg` as
`45c97252852272c993cf9cebb37ec4d77cedf598` at 5:01 PM CST, while the run
was still in progress and before any summary existed). The amendment
(`L >= 14` and `D <= 10` also PASS) was part of that commit.

## Verdict: PASS

- `regrade: ok` (required; a mismatch would void the run).
- Leaf score `L = 12 / 30` (`debate_solved` 12).
- Discordant vs `crawdad-v8-d2` (same seed base 4000): `D = 7` (5 gains, 2 losses).
- Bar: PASS if `8 <= L <= 13` and `D <= 10`, or (amendment) `L >= 14` and `D <= 10`.
  FAIL if `L <= 7` or `D > 10`. This result is inside the original PASS band.
- Decision under the bar: adopt 2 slots as the default for future runs.

Protocol `137acf32c95d`, build `b11669-620d2225c`, seed base 4000, set v8,
30/30 complete — same protocol and build as d2/d3/d4.

## Flips vs crawdad-v8-d2

Gains (fail on d2, pass on d2p2):

- `v8_01_hex_color`
- `v8_08_query_pairs`
- `v8_13_primitive_triples`
- `v8_18_closest_pair`
- `v8_20_triangle_kind`

Losses (pass on d2, fail on d2p2):

- `v8_02_morse_text`
- `v8_14_happy_count`

## Context (not the bar)

Stage N leaf scores: d2 9/30, d3 12/30, d4 10/30. d2p2's 12/30 matches d3
and sits in the middle of that range.

Cross-seed disagreements in Stage N: D23 = 7, D24 = 7, D34 = 10. D = 7
vs same-seed d2 is the same size as D23 and D24, and below D34, so it is
inside the Stage N noise floor.

For reference only (bar is vs d2, not these): D vs d3 = 6 (3 gains, 3
losses); D vs d4 = 12 (7 gains, 5 losses). The d4 count is above 10 but
is a different seed base and is not part of the pre-registered call.

Recorded, no bar: 104 replies (d2 108); 1 `parse_fail` (`v8_07_luhn_digits`,
`leaf_pass` false); tokens 370,774 vs d2 379,720 (prompt 110,548 / 115,140;
completion 260,226 / 264,580). Lengths are nearly equal, so the wall-time
drop is not from shorter replies. Decode `gen_s` 25,241.3 s (7.01 GPU-h)
vs d2 24,593 s (6.83 GPU-h).

## Wall time

d2p2 launcher wall, from `run.status` / `run.log`:

- start 2026-11-17 3:46:07 PM CST, end 7:23:22 PM CST
- `wall_s = 13035` (3 h 37 m 15 s), `rc=0`

Per-session `STEP_WALL` (debate step only):

| session | seat   | STEP_WALL | CST start → end        |
|---------|--------|-----------|------------------------|
| s1      | qwen32 | 3633.0 s  | 3:46:14 PM → 4:46:47 PM |
| s2      | r1d32  | 6236.3 s  | 4:46:53 PM → 6:30:50 PM |
| s3      | qwen32 | 2168.6 s  | 6:30:57 PM → 7:07:06 PM |
| s4      | r1d32  | 805.6 s   | 7:07:13 PM → 7:20:38 PM |
| s5      | qwen32 | 152.4 s   | 7:20:46 PM → 7:23:18 PM |

`STEP_WALL` sum = 12,995.9 s.

d2 had no launcher `wall_s`. Times below are reconstructed from the user
journal for `llm-8081.service` on 2026-11-06 (America/Chicago) and from
log mtimes / the regrade file (`report-regrade.log` mtime 5:41:49 PM CST).
The earlier "~6.6 h" figure was an approximation; measured values:

| d2 measure | seconds | clock | notes |
|------------|---------|-------|-------|
| s1 qwen32 server up | 7181 | 10:13:43 AM → 12:13:24 PM CST | |
| idle gap s1→s2 | 1681 | 28 m 1 s | operational delay, not a model swap |
| s2 r1d32 server up | 11161 | 12:41:25 PM → 3:47:26 PM CST | |
| swap s2→s3 | 182 | 3 m 2 s | |
| s3 qwen32 server up | 4540 | 3:50:28 PM → 5:06:08 PM CST | |
| swap s3→s4 | 90 | 1 m 30 s | |
| s4 r1d32 server up | 1737 | 5:07:38 PM → 5:36:35 PM CST | |
| **server-up sum** | **24619** | **6 h 50 m 19 s** | closest like-for-like to d2p2 STEP_WALL |
| first start → last stop | 26572 | 7 h 22 m 52 s | includes the 28 m idle gap |
| first start → regrade done | 26886 | 7 h 28 m 6 s | 10:13:43 AM → 5:41:49 PM CST |
| that span minus idle gap | 25205 | 7 h 0 m 5 s | continuous-run analogue, includes swaps + regrade |

Reduction vs d2:

- vs server-up sum 24,619 s: **47.1%** (13,035 vs 24,619)
- vs continuous-run analogue 25,205 s: **48.3%**
- vs calendar span 26,572 s: **50.9%**

All three are well above the timing-probe 25% bar (the probe itself was
46.5% on 8 tasks). Decode work was slightly higher on d2p2 (7.01 vs 6.83
GPU-h), so the wall drop is from overlapping two slots, not from less work.

## Artifacts

- `bench/loop/results/crawdad-v8-d2p2.debate.{jsonl,meta.json,summary.json}`
- this directory: session logs, `run.log`, `run.status`, `crawdad-v8-d2p2.status.txt`,
  launcher `run.sh` / `run.sh.diff`, and `prereg.md`
- not included: `run.pid`
