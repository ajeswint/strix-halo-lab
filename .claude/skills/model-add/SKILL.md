---
name: model-add
description: Add a new GGUF model to /data/models with full validation (sha256 against the HF LFS oid, GGUF header parse, llama.cpp arch support), then register it in README, llm-serve, gpu-guard sizes and preflight. Use when downloading, replacing or retiring a model.
---

# Adding a model

## Decide first
- Why this model: which roadmap item, and what it should beat. Check the licence on the model card and cite the URL.
- Fit: file size + 16 GiB must be under ~107 GiB free GTT, alone. Anything over ~20 GiB means it cannot share the box with Qwen or Laguna.
- Quant: prefer unsloth UD or bartowski quants that match the existing ones. Check the arch is supported by the built llama.cpp (`/data/src/llama.cpp` HEAD 620d2225c, v0.7.0; old 836d57176 kept as build-*-836d57176). A new arch may need a rebuild, which is a separate step.

## Download

Resumable, to `/data/models`. Use `aria2c` or `curl -C -`, not a browser. Get the size and LFS sha256 from the HF API first:

```
curl -s "https://huggingface.co/api/models/bartowski/Laguna-XS-2.1-GGUF/tree/main" | python3 -c 'import json,sys; [print(f["path"], f["size"], f.get("lfs",{}).get("oid")) for f in json.load(sys.stdin) if f["path"].endswith(".gguf")]'
```

## Validate (no GPU)
1. Size matches the API.
2. `sha256sum` matches the LFS oid. Size alone is not validation.
3. The header parses and the arch is known. Use the gguf-py in the llama.cpp tree:
   `PYTHONPATH=/data/src/llama.cpp/gguf-py python3 -c "import gguf,sys; r=gguf.GGUFReader(sys.argv[1]); print(r.fields['general.architecture'].contents(), len(r.tensors))" /data/models/Laguna-XS-2.1-Q4_K_M.gguf`
   Split models: shard 1 may hold metadata only; check every shard.
4. The arch string appears in `build-hip` and `build-vk` libllama: `strings /data/src/llama.cpp/build-hip/bin/libllama.so | grep -c laguna`.
   A 0 is not proof of absence: the linker tail-merges short strings (`qwen2` lives only inside a longer string). On 0, check the arch table and the model class instead: `grep -n '"qwen2"' /data/src/llama.cpp/src/llama-arch.cpp` and `strings /data/src/llama.cpp/build-hip/bin/libllama.so | grep -c '_ZN17llama_model_qwen2D'`.
5. Rerankers: the GGUF must carry `cls.output.weight` and rank pooling (`<arch>.pooling_type` 4). Most community Qwen3-Reranker GGUFs lack the head and score garbage (llama.cpp #16407). Check with gguf-py: `'cls.output.weight' in {t.name for t in r.tensors}`.

## Register
- README Software state, Models row: repo, quant, size, sha256 prefix, date verified, purpose.
- `scripts/llm-serve.sh` `case` entry with a short name and alias, if it will be served on :8081.
- `.claude/hooks/gpu-guard.sh` header "Sizes" line, and a matrix case in `gpu-guard-test.sh` if the 16 GiB cutoff no longer sits below the smallest model.
- To have `models/fetch.sh` manage it, add a `files("repo", "prefix")` entry in its Python block. That script rewrites `manifest.tsv` on every run, and it does not read `urls.txt`. Then run `live-sync` so `/data/models/fetch.sh` matches.

## First load = smoke test
Use the `preflight` skill, then `llm-serve` start, then one completion. Report load time, GTT used, pp/tg from one short request, and whether the chat template rendered (no raw special tokens in the output). Then the `bench` skill with a new label if it will be used seriously.

For the CRAwDAD pair and the RAG servers this is scripted (quick and dirty, GPU, the user's go first): `scripts/first-load.sh` runs invite -> status -> `scripts/first-load-probe.py` under `llmctl run` -> bye for rag1, rag2, rag2cpu, rerank, qwen32, r1d32, cheap first, as ONE Bash command (gpu-guard denies llmctl verbs mid-run). Results go to `/data/bench/first-load/first-load.jsonl` and `status.log`. The invite note's GTT delta replaces the `gtt_need` estimate in llmctl.py. rag2cpu compares EmbeddingGemma 2 vectors against the GPU run and fails below cos 0.99. Stub-tested only (fake llmctl via `LLMCTL`, fake server via `FIRSTLOAD_API`, output dir via `FIRSTLOAD_OUT`), 2026-10-15.
Reading rules (Grok accord, 2026-10-15): `ok` is a smoke flag, not a verdict. `load_s` includes preflight: no load-time claims from it. The gtt_need replacement is the invite note in `status.log` (rag2's note, not rag2cpu's: that one sits in RAM). pp/tg come from one cold request (shader compile included): keep them out of bench tables. LLM `ok` = no template leak, not "code came out": read finish, content_chars, reasoning_chars. A rag2cpu pass means two processes agreed, not that the cpu side ran in f32: quote the journal offload line of both runs (first-load.sh copies them into `status.log`; run with `LLM_SERVE_LV=4`, v0.7.0 hides them at the default 3). Since the 2026-10-15 rerun the cpu backend runs `-fa off` (no f16 K/V cast) and the probe adds two long docs (~1.4k and ~5.6k tokens). Rerun just the pair: `FIRSTLOAD_OUT=/data/bench/first-load-rag2-lv4 LLM_SERVE_LV=4 scripts/first-load.sh rag2 rag2cpu`. Rerank has no margin: read the scores. A failed cpu invite stops the run before rerank, qwen32, r1d32.

## Retiring
Deleting a model file is destructive: ask first. Remove it from README, llm-serve, the guard comment, and the `files()` entry in `models/fetch.sh` if one was added, in the same commit.
