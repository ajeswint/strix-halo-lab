---
name: preflight
description: Memory preflight before loading any model, running llama-bench/llama-perplexity/llama-server, a bench script, or training. Use right before every GPU load, every time; a reading from earlier in the session does not count.
---

# Memory preflight

`scripts/llmctl.py invite` runs it and prints it for a server session (`llm-serve` skill). Run it yourself, immediately before the load, from the repo root, with the model you are about to load, for everything that is not a session: llama-bench, llama-perplexity, bench scripts, training. Not while a session is ACTIVE: it reads NOT READY by design.

```
scripts/preflight.sh /data/models/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf
```

No argument checks the box only. For split GGUFs pass shard 1; the script sums all shards.

- Exit 0 + `READY`: proceed. Report the `gtt_used / mem_available / llama-deepseek` line to the user with the result.
- Exit 1 + `NOT READY`: stop. Report every `-` reason line. Do not work around it.
  - `llama-deepseek is active`: ask the user before stopping it. Never stop it yourself.
  - `llama process running` / `a model is resident`: something else holds the GPU. Find it (`scripts/llmctl.py status`, `pgrep -a llama-`) and report; end only what you invited this session (`llmctl bye`).
  - `MemAvailable < need`: another workload (Chrome, Unreal, a build) is using RAM. Report; do not kill it.

## What READY means

One model at a time (2026-10-04 OOM, README Security): llama-deepseek inactive, no `llama-*` process, GTT used <= 16 GiB (gpu-guard's cutoff), and with a model given, MemAvailable and free GTT both >= model size + 16 GiB. The margin is a floor for KV cache and buffers, not a fit prediction.

Reference sizes: idle ~0.5 GiB GTT; Qwen 20.8 GiB file; Laguna 19.1 file / 21.2 GiB GTT peak at 32k ctx; Qwen 28.2 GiB GTT peak at ctx 65536 np 4 (+22.4 over a 5.8 GiB baseline); DeepSeek 84.7 file / 91.1-91.5 GiB GTT peak at 64k ctx (+85.5 over a 5.8 GiB baseline); GTT total 108 GiB. Files only, not loaded yet (2026-10-15): Qwen3-32B 18.4, R1-Distill-Qwen-32B 18.5, Qwen3-Reranker-4B 4.0, Qwen3-Embedding-0.6B 0.6, EmbeddingGemma 2 0.3 GiB; preflight needs file + 16 GiB free for each.

## Rules

- READY is not permission. GPU runs still need the user's yes where the agent's rules say so.
- If the script's checks and the CLAUDE.md rule ever disagree, the stricter one wins; report the disagreement so the script gets fixed.
- `.claude/hooks/gpu-guard.sh` is a tripwire behind this, not a substitute: it fails open and has documented gaps.
