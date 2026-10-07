---
name: llm-serve
description: Start, stop, check or read logs of any model server through scripts/llmctl.py sessions (Qwen3.6-35B-A3B or Laguna XS 2.1 on 127.0.0.1:8081, DeepSeek on :8080), and run a client under its memory cap. Use whenever a task needs a model behind the OpenAI-compatible API, and to unload it afterwards.
---

# Model servers through llmctl

`scripts/llmctl.py` owns every model lifecycle as a session (one live at a time, state in `/data/orch/orch.db`, table `sessions`). Do not start a server any other way: not `llm-serve.sh start`, not `systemctl start llama-deepseek`, not `llama-server`. A model started outside llmctl shows as UNOWNED and `invite` refuses until `bye` ends it.

```
scripts/llmctl.py status
scripts/llmctl.py invite qwen --ctx 65536 --np 4
scripts/llmctl.py invite deepseek
scripts/llmctl.py swap laguna
scripts/llmctl.py run --mem 8G --as 16G -- python3 bench/loop/agent.py --set v4 ...
scripts/llmctl.py bye
```

- `invite <qwen|laguna|deepseek>`: preflight (printed) -> start -> bounded `/health` wait -> ACTIVE. Options for the small models: `--backend vk|hip --ctx N --np N` (defaults vk, 32768, 1). Any failure ends FAILED with the reason stored and the unit stopped.
- `bye` ends the ACTIVE session and checks GTT fell under 16 GiB. With no session it ends a resident registered unit (UNOWNED); processes outside a registered unit are reported, not killed.
- `swap <endpoint>` = `bye` then `invite`, recorded as one transition.
- `run -- <cmd>` is only allowed inside an ACTIVE session. It wraps the client in a user scope with `MemoryMax` (default 8G), `MemorySwapMax=0` and `RLIMIT_AS` (default 16G, an HTTP client's budget; a GPU client needs `--as` raised) and reports `memory.peak`. A cap kill exits 137 with "memory cap" and leaves the session ACTIVE. Every long client (agent.py, bench/loop/run.py) goes through it: 2026-10-07 a 95 GiB python3 OOM-killed Cursor.
- Fails closed: an unreadable GTT refuses `invite` and `swap`.
- Ending DeepSeek (`bye`, or `swap` away from it) needs an interactive terminal and the word yes: the user runs it, an agent cannot. `invite deepseek` uses `sudo -n systemctl` through `/etc/sudoers.d/llmctl`; if it fails with a sudo error the drop-in is not installed (`scripts/install-llmctl-sudoers.sh`, run by the user).
- gpu-guard denies `invite`, `swap`, `bye` and `run` for agent Bash while a model is resident; `status` passes. When it denies, report to the user and wait.
- Tests, no GPU: `python3 scripts/llmctl-test.py`.

## The primitive underneath

`scripts/llm-serve.sh` runs llama-server as a transient user unit `llm-8081`. llmctl calls its `start` for qwen and laguna (it runs `scripts/preflight.sh` itself too, so the preflight prints twice). `status` and `logs` are still the way to read the server log; `stop` is `llmctl bye`'s job now.

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

- One model at a time. Qwen and Laguna cannot both be resident (gpu-guard cutoff, user's decision). Switching = `llmctl swap`.
- End what you invited when the task is done (`llmctl bye`). A forgotten server holds ~21 GiB and blocks every other load.
- Backend default `vk` comes from the depth-0 table only (Vulkan tg +16% for Qwen, pp equal). At long prompts HIP may win. Measure before changing the default; see the `measure` skill.
- Load time: the small-model start waits up to 180 s for `/health`; DeepSeek's wait is 600 s, a first value not yet measured. If it times out, read `logs` before retrying. Do not loop.
- Laguna smoke-tested 2026-10-05 at the defaults: GTT peak 21.2 GiB, tg ~80 t/s. It is a reasoning model: give it a `max_tokens` well above the answer length (a 256 cap returned empty `content`), or cap thinking with `reasoning_budget_tokens` the way orch.py does.
- Linger is on: a running `llm-8081` survives logout until stopped (it is transient, so not across a reboot). `stop` is required, not tidy-up.
- New model or flags: edit the `case` in `scripts/llm-serve.sh` and the registry in `scripts/llmctl.py` (systems agent), add a test to `scripts/llmctl-test.py` and a gpu-guard matrix case if the entry point changes.
