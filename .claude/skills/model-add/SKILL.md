---
name: model-add
description: Add a new GGUF model to /data/models with full validation (sha256 against the HF LFS oid, GGUF header parse, llama.cpp arch support), then register it in README, llm-serve, gpu-guard sizes and preflight. Use when downloading, replacing or retiring a model.
---

# Adding a model

## Decide first
- Why this model: which roadmap item, and what it should beat. Check the licence on the model card and cite the URL.
- Fit: file size + 16 GiB must be under ~107 GiB free GTT, alone. Anything over ~20 GiB means it cannot share the box with Qwen or Laguna.
- Quant: prefer unsloth UD or bartowski quants that match the existing ones. Check the arch is supported by the built llama.cpp (`/data/src/llama.cpp` HEAD 836d57176). A new arch may need a rebuild, which is a separate step.

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

## Register
- README Software state, Models row: repo, quant, size, sha256 prefix, date verified, purpose.
- `scripts/llm-serve.sh` `case` entry with a short name and alias, if it will be served on :8081.
- `.claude/hooks/gpu-guard.sh` header "Sizes" line, and a matrix case in `gpu-guard-test.sh` if the 16 GiB cutoff no longer sits below the smallest model.
- To have `models/fetch.sh` manage it, add a `files("repo", "prefix")` entry in its Python block. That script rewrites `manifest.tsv` on every run, and it does not read `urls.txt`. Then run `live-sync` so `/data/models/fetch.sh` matches.

## First load = smoke test
Use the `preflight` skill, then `llm-serve` start, then one completion. Report load time, GTT used, pp/tg from one short request, and whether the chat template rendered (no raw special tokens in the output). Then the `bench` skill with a new label if it will be used seriously.

## Retiring
Deleting a model file is destructive: ask first. Remove it from README, llm-serve, the guard comment, and the `files()` entry in `models/fetch.sh` if one was added, in the same commit.
