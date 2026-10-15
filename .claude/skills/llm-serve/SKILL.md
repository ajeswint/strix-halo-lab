---
name: llm-serve
description: Start, stop, check or read logs of any model server through scripts/llmctl.py sessions (Qwen3.6-35B-A3B, Laguna XS 2.1, the CRAwDAD pair Qwen3-32B / R1-Distill-Qwen-32B, or a RAG embedder/reranker on 127.0.0.1:8081; DeepSeek V4 Flash on :8080), and run a client under its memory cap. Use whenever a task needs a model behind the OpenAI-compatible API, and to unload it afterwards.
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

- `invite <qwen|laguna|qwen32|r1d32|rag1|rag2|rerank|deepseek>`: preflight (printed) -> start -> bounded `/health` wait -> ACTIVE. Options for the :8081 models: `--backend vk|hip|cpu --ctx N --np N` (defaults vk, ctx 32768 for LLMs and 8192 for rag1/rag2/rerank, 1 slot; `cpu` only for the RAG models). Any failure ends FAILED with the reason stored and the unit stopped.
- `bye` ends the ACTIVE session and checks GTT fell under 16 GiB. With no session it ends a resident registered unit (UNOWNED); processes outside a registered unit are reported, not killed.
- `swap <endpoint>` = `bye` then `invite`, recorded as one transition.
- `run -- <cmd>` is only allowed inside an ACTIVE session. It wraps the client in a user scope with `MemoryMax` (default 8G), `MemorySwapMax=0` and `RLIMIT_AS` (default 16G, an HTTP client's budget; a GPU client needs `--as` raised) and reports `memory.peak`. A cap kill exits 137 with "memory cap" and leaves the session ACTIVE. Every long client (agent.py, bench/loop/run.py) goes through it: 2026-10-07 a 95 GiB python3 OOM-killed Cursor.
- Fails closed: an unreadable GTT refuses `invite` and `swap`.
- Ending DeepSeek (`bye`, or `swap` away from it) needs an interactive terminal and the word yes: the user runs it, an agent cannot. `invite deepseek` uses `sudo -n systemctl` through `/etc/sudoers.d/llmctl`; if it fails with a sudo error the drop-in is not installed (`scripts/install-llmctl-sudoers.sh`, run by the user).
- gpu-guard denies `invite`, `swap`, `bye` and `run` for agent Bash while a model is resident; `status` passes. When it denies, report to the user and wait.
- Tests, no GPU: `python3 scripts/llmctl-test.py`.

## Loop + DeepSeek fix stage (optional, off by default)

KEPT 2026-10-15 (README "v6 pipeline" sections: Qwen loop 24/30, DeepSeek fixer 6/6 vs Qwen fix-mode control 2/6, 0.40 GPU h per added solve; one run per arm). Use it when a loop run leaves failures worth DeepSeek's GPU time. It is never part of a measurement arm unless that arm's pre-run says so. Two sessions, each one background Bash chain (gpu-guard denies `run`, `bye` and `python3` while a model is resident, so nothing can be added mid-session). Each chain opens with a `select_fix.py` gate that runs before any invite and refuses with exit 4:
- `fresh SET LABEL` (session 1): `SET` is registered in `run.SETS`, no stored `results/*.jsonl` row is a task of `SET` (a stored arm is a finished measurement; rerunning one is a new pre-run, not this procedure), and the label is new (`agent.py` overwrites an existing label's files).
- `ready S1 LABEL` (session 2): session 1's fix files exist and are non-empty (its `select` exited 0), and the DeepSeek label is new.

The blocks below use v7. No v7 exists today (v0-v5 are finished measurements, v6 is spent), so both refuse at the gate before any load. A real run first registers a new set (`bench/loop/tasks_vN.py` plus its `SETS` line, as v6 was) and changes `SET`.

Session 1, Qwen loop, then the selector. `bye` sits inside the group that runs only after a successful `invite`, so a gate refusal or a refused invite never ends someone else's session:

```
SET=v7; L=qwen-$SET-agent-k4e4-vk-np4; python3 bench/loop/select_fix.py fresh $SET $L && scripts/llmctl.py invite qwen --ctx 65536 --np 4 && { scripts/llmctl.py run -- python3 bench/loop/agent.py --set $SET -k 4 -e 4 --label $L && scripts/llmctl.py run -- python3 bench/loop/agent.py --regrade bench/loop/results/$L.jsonl --set $SET > bench/loop/results/$L.regrade.txt && python3 bench/loop/select_fix.py select $L --tag $L; scripts/llmctl.py bye; }
```

- `select` exit 0: `fix-$L-tasks.txt` and `fix-$L-stored.jsonl` written (unsolved tasks whose last coded turn failed the visible tests; the files are named after the session 1 label, so they belong to that arm only). Exit 3: nothing to fix, stop. Exit 2: the regrade disagrees with the summary, stop and report. The chain's exit code is `bye`'s, so read the gate's and the selector's lines in the log.
- Before session 2: the user's yes for the DeepSeek load (every time), and READY at the invite preflight. Free GTT binds: DeepSeek needs 100.7 GiB, so READY only at GTT used <= 7,857,319,520 B (2026-10-15 idle reads 7.2-7.4 GiB). Ask the user to close Chrome and other GPU clients first. NOT READY: stop and report; never lower the margin.

Session 2, DeepSeek fix mode on the selected tasks. `ready` runs before the invite, so a session 1 that wrote no fix files never loads DeepSeek. No `bye` (the user's, at a terminal):

```
SET=v7; S1=qwen-$SET-agent-k4e4-vk-np4; L=deepseek-$SET-fix-k4e2-hip; python3 bench/loop/select_fix.py ready $S1 $L && scripts/llmctl.py invite deepseek && scripts/llmctl.py run -- python3 bench/loop/agent.py --set $SET --tasks "$(cat bench/loop/results/fix-$S1-tasks.txt)" --fix-from bench/loop/results/fix-$S1-stored.jsonl -k 4 -e 2 --task-budget 98304 --parallel 1 --api http://127.0.0.1:8080 --model deepseek-v4-flash --label $L && scripts/llmctl.py run -- python3 bench/loop/agent.py --regrade bench/loop/results/$L.jsonl --set $SET > bench/loop/results/$L.regrade.txt && python3 bench/loop/select_fix.py check $L
```

- Cost from v6: ~0.4 h per selected task on DeepSeek, up to ~1.5 h (8 turns x ~692 s); the GPU and ~85 GiB GTT are held throughout; no Chrome, Unreal or builds while it is up. The fix-from and task-list files stay untracked.
- A task solved here is solved by the pipeline, not by Qwen: report S1 and S2 separately.

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

Args: `start <qwen|laguna|qwen32|r1d32|rag1|rag2|rerank> [hip|vk|cpu] [ctx] [parallel]`. Defaults: `vk`, ctx 32768 (RAG models 8192), 1 slot. RAG models start with `--embedding` (rag1, rag2) or `--reranking` (rerank) and batch = ubatch = ctx, because an embedding input must fit one ubatch. `cpu` (`--device none -ngl 0 -fa off`, RAG models only, refused for LLMs because RAM is invisible to gpu-guard) is the reference for EmbeddingGemma 2, whose activations overflow float16. `-fa off` because with no KV cache flash attention casts K/V to f16; still not pure f32 (Q8_0 matmuls quantize activations to q8_0 blocks with an f16 scale, safe to ~8.3e6). `LLM_SERVE_LV=4` adds `-lv 4`: v0.7.0 prints the offloaded-layers and buffer-size lines only at 4. `-c` is total and is split across slots: 65536 with 4 slots = 16k each. Fixed flags match llama-deepseek.service: `-ngl 999 -fa on -lm none --cache-reuse 256`. Jinja chat templates are on by default in this build.

API: `http://127.0.0.1:8081/v1` (chat/completions, models). Aliases: `qwen3.6-35b-a3b`, `laguna-xs-2.1`, `qwen3-32b`, `r1-distill-qwen-32b`, `qwen3-embedding-0.6b` (`/v1/embeddings`), `embeddinggemma-2` (`/v1/embeddings`), `qwen3-reranker-4b` (`/v1/rerank`). The five new ones first loaded 2026-10-15 (`scripts/first-load.sh`, model-add skill); their llmctl `gtt_need` is the measured delta. DeepSeek is separate: system unit `llama-deepseek` on :8080, alias `deepseek-v4-flash`. Starting it needs the user's yes.

## Rules

- One model at a time. Qwen and Laguna cannot both be resident (gpu-guard cutoff, user's decision); neither can the two 32B models or a model and a RAG server (preflight refuses any second llama-* process). Switching = `llmctl swap`.
- End what you invited when the task is done (`llmctl bye`). A forgotten Qwen holds ~28 GiB of GTT at ctx 65536 np 4 (+22.4 over baseline) and blocks every other load.
- Backend default `vk` comes from the depth-0 table only (Vulkan tg +16% for Qwen, pp equal). At long prompts HIP may win. Measure before changing the default; see the `measure` skill.
- Load time: the small-model start waits up to 180 s for `/health`; DeepSeek's wait is 600 s, a first value (measured 21 s on 2026-10-07 with cache state unchecked; cold-cache unmeasured). If it times out, read `logs` before retrying. Do not loop.
- Laguna smoke-tested 2026-10-05 at the defaults: GTT peak 21.2 GiB, tg ~80 t/s. It is a reasoning model: give it a `max_tokens` well above the answer length (a 256 cap returned empty `content`), or cap thinking with `reasoning_budget_tokens` the way orch.py does.
- Linger is on: a running `llm-8081` survives logout until stopped (it is transient, so not across a reboot). `stop` is required, not tidy-up.
- New model or flags: edit the `case` in `scripts/llm-serve.sh` and the registry in `scripts/llmctl.py` (systems agent), add a test to `scripts/llmctl-test.py` and a gpu-guard matrix case if the entry point changes.
