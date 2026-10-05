---
name: preflight
description: Memory preflight before loading any model, running llama-bench/llama-perplexity/llama-server, a bench script, or training. Use right before every GPU load, every time; a reading from earlier in the session does not count.
---

# Memory preflight

Run it immediately before the load, from the repo root, with the model you are about to load:

```
scripts/preflight.sh /data/models/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf
```

No argument checks the box only. For split GGUFs pass shard 1; the script sums all shards.

- Exit 0 + `READY`: proceed. Report the `gtt_used / mem_available / llama-deepseek` line to the user with the result.
- Exit 1 + `NOT READY`: stop. Report every `-` reason line. Do not work around it.
  - `llama-deepseek is active`: ask the user before stopping it. Never stop it yourself.
  - `llama process running` / `a model is resident`: something else holds the GPU. Find it (`pgrep -a llama-`, `scripts/llm-serve.sh status`) and report; stop only what you started this session.
  - `MemAvailable < need`: another workload (Chrome, Unreal, a build) is using RAM. Report; do not kill it.

## What READY means

One model at a time (2026-10-04 OOM, README Security): llama-deepseek inactive, no `llama-*` process, GTT used <= 16 GiB (gpu-guard's cutoff), and with a model given, MemAvailable and free GTT both >= model size + 16 GiB. The margin is a floor for KV cache and buffers, not a fit prediction.

Reference sizes: idle ~0.5 GiB GTT; Qwen 20.8 GiB file; Laguna 19.1; DeepSeek 84.7 file / ~86 GiB GTT peak at 64k ctx; GTT total 108 GiB.

## Rules

- READY is not permission. GPU runs still need the user's yes where the agent's rules say so.
- If the script's checks and the CLAUDE.md rule ever disagree, the stricter one wins; report the disagreement so the script gets fixed.
- `.claude/hooks/gpu-guard.sh` is a tripwire behind this, not a substitute: it fails open and has documented gaps.
