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

- One model at a time. `start` runs preflight and refuses while another model is resident. Switching = `stop`, then `start`.
- Stop what you started when the task is done. A forgotten server stays resident and blocks every other load.
- Backend default `vk` comes from the depth-0 table only (Vulkan tg +16% for Qwen, pp equal). At long prompts HIP may win. Measure before changing the default; see the `measure` skill.
- Load time: start waits up to 180 s for `/health`. If it times out, read `logs` before retrying. Do not loop.
- Laguna smoke-tested 2026-10-05 at the defaults: GTT peak 21.2 GiB, tg ~80 t/s. It is a reasoning model: give it a `max_tokens` well above the answer length (a 256 cap returned empty `content`), or cap thinking with `reasoning_budget_tokens` the way orch.py does.
- Linger is on: a running `llm-8081` survives logout until stopped (it is transient, so not across a reboot). `stop` is required, not tidy-up.
- New model: the `model-add` skill (case, README, manifest, guard sizes). A new entry point also needs a gpu-guard matrix case.
