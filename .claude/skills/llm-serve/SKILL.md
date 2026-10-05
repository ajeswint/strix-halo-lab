---
name: llm-serve
description: Start, stop, check or read logs of the small-model llama-server (Qwen3.6-35B-A3B or Laguna XS 2.1) on 127.0.0.1:8081. Use whenever a task needs a small model behind the OpenAI-compatible API, and to unload it afterwards.
---

# Small-model server on :8081

`scripts/llm-serve.sh` runs llama-server as a transient user unit `llm-8081`. Start runs `scripts/preflight.sh` itself and refuses when NOT READY. gpu-guard denies `start` while any model is resident.

```
scripts/llm-serve.sh start qwen
scripts/llm-serve.sh start laguna
scripts/llm-serve.sh start qwen hip 65536 4
scripts/llm-serve.sh status
scripts/llm-serve.sh logs 100
scripts/llm-serve.sh stop
```

Args: `start <qwen|laguna> [hip|vk] [ctx] [parallel]`. Defaults: `vk`, ctx 32768, 1 slot. `-c` is total and is split across slots: 65536 with 4 slots = 16k each. Fixed flags match llama-deepseek.service: `-ngl 999 -fa on -lm none --cache-reuse 256`. Jinja chat templates are on by default in this build.

API: `http://127.0.0.1:8081/v1` (chat/completions, models). Aliases: `qwen3.6-35b-a3b`, `laguna-xs-2.1`. DeepSeek is separate: system unit `llama-deepseek` on :8080, alias `deepseek-v4-flash`. Starting it needs the user's yes.

## Rules

- One model at a time. Qwen and Laguna cannot both be resident (gpu-guard cutoff, user's decision). Switching = `stop`, then `start` the other.
- Stop what you started when the task is done. A forgotten server holds ~21 GiB and blocks every other load.
- Backend default `vk` comes from the depth-0 table only (Vulkan tg +16% for Qwen, pp equal). At long prompts HIP may win. Measure before changing the default; see the `measure` skill.
- Load time: start waits up to 180 s for `/health`. If it times out, read `logs` before retrying. Do not loop.
- Laguna has never been run on this box. Its first start is a smoke test: report load time, GTT used, and one completion.
- New model or flags: edit the `case` in `scripts/llm-serve.sh` (systems agent) and add a gpu-guard matrix case if the entry point changes.
