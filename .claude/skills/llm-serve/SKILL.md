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

The blocks below use v9. No v9 exists today (v0-v5 are finished measurements, v6 is spent, v7 was the CRAwDAD debate set and is now the retrieval corpus, v8 is held out for the retrieval test), so both refuse at the gate before any load. A real run first registers a new set (`bench/loop/tasks_vN.py` plus its `SETS` line, as v6 was) and changes `SET`.

Session 1, Qwen loop, then the selector. `bye` sits inside the group that runs only after a successful `invite`, so a gate refusal or a refused invite never ends someone else's session:

```
SET=v9; L=qwen-$SET-agent-k4e4-vk-np4; python3 bench/loop/select_fix.py fresh $SET $L && scripts/llmctl.py invite qwen --ctx 65536 --np 4 && { scripts/llmctl.py run -- python3 bench/loop/agent.py --set $SET -k 4 -e 4 --label $L && scripts/llmctl.py run -- python3 bench/loop/agent.py --regrade bench/loop/results/$L.jsonl --set $SET > bench/loop/results/$L.regrade.txt && python3 bench/loop/select_fix.py select $L --tag $L; scripts/llmctl.py bye; }
```

- `select` exit 0: `fix-$L-tasks.txt` and `fix-$L-stored.jsonl` written (unsolved tasks whose last coded turn failed the visible tests; the files are named after the session 1 label, so they belong to that arm only). Exit 3: nothing to fix, stop. Exit 2: the regrade disagrees with the summary, stop and report. The chain's exit code is `bye`'s, so read the gate's and the selector's lines in the log.
- Before session 2: the user's yes for the DeepSeek load (every time), and READY at the invite preflight. Free GTT binds: DeepSeek needs 100.7 GiB, so READY only at GTT used <= 7,857,319,520 B (2026-10-15 idle reads 7.2-7.4 GiB). Ask the user to close Chrome and other GPU clients first. NOT READY: stop and report; never lower the margin.

Session 2, DeepSeek fix mode on the selected tasks. `ready` runs before the invite, so a session 1 that wrote no fix files never loads DeepSeek. No `bye` (the user's, at a terminal):

```
SET=v9; S1=qwen-$SET-agent-k4e4-vk-np4; L=deepseek-$SET-fix-k4e2-hip; python3 bench/loop/select_fix.py ready $S1 $L && scripts/llmctl.py invite deepseek && scripts/llmctl.py run -- python3 bench/loop/agent.py --set $SET --tasks "$(cat bench/loop/results/fix-$S1-tasks.txt)" --fix-from bench/loop/results/fix-$S1-stored.jsonl -k 4 -e 2 --task-budget 98304 --parallel 1 --api http://127.0.0.1:8080 --model deepseek-v4-flash --label $L && scripts/llmctl.py run -- python3 bench/loop/agent.py --regrade bench/loop/results/$L.jsonl --set $SET > bench/loop/results/$L.regrade.txt && python3 bench/loop/select_fix.py check $L
```

- Cost from v6: ~0.4 h per selected task on DeepSeek, up to ~1.5 h (8 turns x ~692 s); the GPU and ~85 GiB GTT are held throughout; no Chrome, Unreal or builds while it is up. The fix-from and task-list files stay untracked.
- A task solved here is solved by the pipeline, not by Qwen: report S1 and S2 separately.

## CRAwDAD debate (bench/loop/debate.py)

Built 2026-10-15 (`python3 bench/loop/debate.py --selftest`, no server). GPU smoke passed 2026-10-18 (`crawdad-smoke-v1`, 2 v1 tasks, README "GPU smoke" result): the budget is in effect for both templates and the verdicts parse. No GPU session runs before a README pre-run for it is committed and the user says go (a Grok round unless the user waives it); each session is a GPU stage. Protocol, deviations from the paper and the file layout are in the `debate.py` docstring. Seats are llmctl endpoints `qwen32` and `r1d32` at the defaults (vk, ctx 32768, 1 slot); `step` refuses a slot under 26,624 tokens (`SLOT_MIN`), a served model that is not a seat, another llama.cpp build or model file than the run started with, and changed prompts or constants (protocol hash).

A set takes five sessions, alternating seats. Each is one background chain (gpu-guard denies `run`, `bye` and `python3` while a model is resident); `bye` sits in the group after a successful invite. The first step fixes the run in `results/<label>.debate.meta.json` (set, tasks, balanced coin); a probe passes `--tasks` on the first step only. Session 1 (Qwen first; `status` names the seat when a run already exists):

```
scripts/llmctl.py invite qwen32 && { scripts/llmctl.py run -- python3 bench/loop/debate.py step --label crawdad-v7 --set v7; scripts/llmctl.py bye; }
```

Between sessions, no server: `python3 bench/loop/debate.py status --label crawdad-v7` prints each task's state and `next session: invite <seat>`. Sessions 2-5, the seat it names, without `--set`:

```
scripts/llmctl.py invite r1d32 && { scripts/llmctl.py run -- python3 bench/loop/debate.py step --label crawdad-v7; scripts/llmctl.py bye; }
```

```
scripts/llmctl.py invite qwen32 && { scripts/llmctl.py run -- python3 bench/loop/debate.py step --label crawdad-v7; scripts/llmctl.py bye; }
```

- A step that dies (server gone, HTTP error) keeps every reply already written; the same command resumes and never asks a reply twice.
- After `status` prints `done`: `python3 bench/loop/debate.py report --label crawdad-v7 --regrade` (CPU only) writes `results/crawdad-v7.debate.summary.json` and exits 2 if any stored grade does not reproduce.
- Retrieval arm (README "CRAwDAD retrieval on v8"): only the first step changes. It adds `--retrieve` with the frozen export from `memring.py debate --passes-out`. Later steps are the same commands without it; the meta pins the export by sha256 and refuses a changed file or a repeated `--retrieve`:

```
scripts/llmctl.py invite qwen32 && { scripts/llmctl.py run -- python3 bench/loop/debate.py step --label crawdad-v8-r --set v8 --retrieve bench/loop/results/crawdad-v7.passes.json; scripts/llmctl.py bye; }
```
- Cost, measured on the smoke run (one run): replies took 117-317 s (about 3.6 min mean), tg 10.9-11.3 t/s at prompts up to 2,595 tokens, loads and swaps about 1.3 min over 5 sessions with the files warm. A 30-task set is roughly 9-16 h of decode at 5-9 replies per task. Worst case per reply is 6,144 tokens, about 9 min.

## crawdad group: the pair and three RAGs co-resident

`invite crawdad` loads Qwen3-32B, R1-Distill-Qwen-32B, rag1, rag2 and rerank in one session, each on its own port. Not for debate.py runs (they use the single seats on :8081 and stay as above). Not yet live-tested: the first invite on the MAX is the measurement of the co-resident GTT (expected +64.9 GiB, need 80.9 free), and needs the user's yes.

```
scripts/llmctl.py invite crawdad
scripts/llmctl.py status
scripts/llmctl.py bye
```

| member | port | alias | API |
|---|---|---|---|
| Qwen3-32B | 8082 | `qwen3-32b` | `/v1/chat/completions` |
| R1-Distill-Qwen-32B | 8083 | `r1-distill-qwen-32b` | `/v1/chat/completions` |
| rag1 Qwen3-Embedding-0.6B | 8084 | `qwen3-embedding-0.6b` | `/v1/embeddings` |
| rag2 EmbeddingGemma 2 | 8085 | `embeddinggemma-2` | `/v1/embeddings` |
| rerank Qwen3-Reranker-4B | 8086 | `qwen3-reranker-4b` | `/v1/rerank` |

- One preflight for the group (all five files, need >= 80.9 GiB), then members start in that order. A member that fails stops all of them (FAILED). No options: vk, each model's default ctx, 1 slot.
- `bye` stops all five. A member that dies while ACTIVE aborts the session; the survivors show as UNOWNED and `bye` ends them.
- Read a member's log: `LLM_SERVE_PORT=8082 scripts/llm-serve.sh logs 100` (8082-8086).
- Clients go through `scripts/llmctl.py run --` as with any session.

## The primitive underneath

`scripts/llm-serve.sh` runs llama-server as a transient user unit `llm-8081` (`llm-<port>` with `LLM_SERVE_PORT`, which only the crawdad group uses). llmctl calls its `start` for qwen and laguna (it runs `scripts/preflight.sh` itself too, so the preflight prints twice). `status` and `logs` are still the way to read the server log; `stop` is `llmctl bye`'s job now.

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

- One session at a time. Qwen and Laguna cannot both be resident (gpu-guard cutoff, user's decision); the two 32B models and the RAG servers are co-resident only as the `crawdad` group, never by a second invite (preflight refuses any second llama-* process). Switching = `llmctl swap`.
- End what you invited when the task is done (`llmctl bye`). A forgotten Qwen holds ~28 GiB of GTT at ctx 65536 np 4 (+22.4 over baseline) and blocks every other load.
- Backend default `vk` comes from the depth-0 table only (Vulkan tg +16% for Qwen, pp equal). At long prompts HIP may win. Measure before changing the default; see the `measure` skill.
- Load time: the small-model start waits up to 180 s for `/health`; DeepSeek's wait is 600 s, a first value (measured 21 s on 2026-10-07 with cache state unchecked; cold-cache unmeasured). If it times out, read `logs` before retrying. Do not loop.
- Laguna smoke-tested 2026-10-05 at the defaults: GTT peak 21.2 GiB, tg ~80 t/s. It is a reasoning model: give it a `max_tokens` well above the answer length (a 256 cap returned empty `content`), or cap thinking with `reasoning_budget_tokens` the way orch.py does.
- Linger is on: a running `llm-8081` survives logout until stopped (it is transient, so not across a reboot). `stop` is required, not tidy-up.
- New model or flags: edit the `case` in `scripts/llm-serve.sh` and the registry in `scripts/llmctl.py` (systems agent), add a test to `scripts/llmctl-test.py` and a gpu-guard matrix case if the entry point changes.
