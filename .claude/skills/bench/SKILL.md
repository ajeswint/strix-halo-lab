---
name: bench
description: Run llama-bench under Framework's fixed conditions with bench/bench.sh, summarise with bench/report.py, and compare against the README tables. Use for throughput numbers and backend comparisons.
---

# Benchmarks

Before running: run the `preflight` skill with the model, and get the user's yes (a GPU run). Nothing else on the GPU while it runs; bench numbers taken beside another load are void.

```
/data/bench/bench.sh t4-qwen-recheck /data/models/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf
python3 /data/bench/report.py | grep -E 'label|t3-fan-qwen|t4-qwen-recheck'
```

- `bench.sh <label> <gguf> [extra llama-bench args]`: pp2048 / tg128, `-ngl 999 -fa on -lm none`, `-r 3`, HIP then Vulkan. Appends a state line (power profile, tuned, cmdline, GTT) plus results to `/data/bench/results.jsonl`.
- Depth sweep (long-context behaviour): `/data/bench/bench.sh t4-qwen-depth /data/models/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf -d 0,8192,32768 -r 2`
- Run the live copy in `/data/bench/`. The repo `bench/` is its mirror. After a run, copy the results back so the repo matches (see `live-sync`): `cp /data/bench/results.jsonl bench/results.jsonl`. The evaluator does not write files: it hands this step to the user or `systems`.

## Labels

`t<N>-<what>`, where N follows the last series in `results.jsonl` (t3 = fan-pegged, current baseline). Never reuse a label. A changed condition (extra args, different build, power profile) is a new label, never an overwrite.

Baseline to compare against: `t3-fan-qwen` and `t3-fan-dsv4-*` (README Benchmarks table).

## Reading results

- Report pp and tg per backend with ± stddev and n (`-r`). Keep/drop follows the `measure` skill.
- Token generation is memory-bandwidth bound (~117 GB/s effective). A tg change of a few % from a power/clock knob is noise unless it repeats.
- `fanpeg-suite.sh` is the cooling A/B suite (long, loads DeepSeek). Do not run it without a specific question it answers.
- `post-reboot.sh <label>` is for after BIOS/kernel/cmdline changes only.
- If a result changes a README number, update the table and say which label it came from.
