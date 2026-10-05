---
name: measure
description: Protocol for any keep/drop decision based on numbers. Covers tuning changes, backend or flag choices, best-of-N vs pass@1, LoRA vs base, and judge vs tests. Use before proposing such a change (to state the threshold) and when reporting its result.
---

# Measurement protocol

"Measured numbers beat claims." Every change that is kept needs a measured delta against a stated threshold.

## Before the run (write this down first)

1. **Question**: one sentence. ("Does `-np 4` raise best-of-8 throughput without changing per-sample quality?")
2. **Baseline**: the exact label, commit or config it is compared against. It must be measured under the same conditions. Reuse an existing label only if nothing changed since.
3. **Metric and threshold**: what you count, and the delta that would justify keeping the change. Example: "keep if best-of-8 beats pass@1 by >= 10 points on the held-out set". State it before the run, never after.
4. **n**: repetitions or tasks, enough for the delta to exceed run-to-run spread. llama-bench: `-r 3` minimum. Task evals: a held-out set of fixed size, named.
5. **Cost**: GPU minutes, and whether DeepSeek must be unloaded. The user's yes covers this cost.
6. **Commit 1-4 and the fixed settings before any GPU work** (before preflight and the server start), in their own commit with no results. The result cites that hash. Written down first but committed together with the results, the history cannot show the order (loop-v0, 1035d5e).

## During

- One variable at a time. Everything else stays fixed and is recorded: commit, build (`build-hip`/`build-vk`), model file, flags, power profile.
- `preflight` before every load. Nothing else on the GPU.

## After (report format)

```
question:  ...          stated in: <hash of the pre-run commit>
baseline:  <label/commit>   result: <value ± spread, n>
change:    <label/commit>   result: <value ± spread, n>
delta:     <abs and %>      threshold: <stated before>   -> keep | drop | inconclusive
```

- Inconclusive (delta inside the spread) means drop, or rerun with a bigger n if the user agrees. It never means keep.
- A dropped change is recorded too: one line in README Decisions with the number ("GPU DPM forced high: +15-20 W idle for ~2%").

## Evals specific to roadmap 2/3

- Held out means held out. Tasks used for prompt iteration, few-shot examples or the judge's prompt are excluded and listed.
- Tests and the compiler outrank the judge. When they disagree, the test wins, and the judge's verdict is counted as a judge error rate.
- Report pass@1 and best-of-N on the same tasks with the same seeds/temperature, plus total tokens and wall time. Efficiency is part of the result.
- Watch for collapse when outputs feed back into training: track diversity (distinct solutions per task) and held-out score per iteration.
