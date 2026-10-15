#!/usr/bin/env python3
"""First-load probe for one served model on :8081 (quick and dirty; scripts/first-load.sh drives it).

Usage: first-load-probe.py NAME OUTDIR [--ref FILE]
NAME is the llmctl endpoint (qwen32, r1d32, rag1, rag2, rag2cpu, rerank). Appends one JSON line to
OUTDIR/first-load.jsonl and prints it. Exit 0 = every check passed, 1 = a check failed, 2 = usage/HTTP error.

Checks, by kind:
- llm: one chat completion (code prompt, ~1.2k-token context, max_tokens 1024): pp and tg from the
  server's timings, template leak (raw special tokens in content or reasoning), reasoning split.
- embed: 4 inputs (2 queries, 2 code docs): dimension, all finite, each query nearest its own doc.
  Vectors saved to OUTDIR/NAME.vectors.json. With --ref (the cpu run against the GPU run's vectors):
  per-input cosine GPU vs cpu, min must be >= 0.99 (EmbeddingGemma 2 overflows float16).
- rerank: one query against 3 docs: the relevant doc must score highest.
GTT is read after the requests (max over cards, as llmctl does); llmctl's invite note has the load delta.
"""
import glob, json, math, os, sys, time, urllib.request

API = os.environ.get("FIRSTLOAD_API", "http://127.0.0.1:8081")   # override: stub test only
DIM = {"rag1": 1024, "rag2": 768, "rag2cpu": 768}
# Query/document prefixes: Qwen3-Embedding card (Instruct/Query); EmbeddingGemma v1 card ("task: ... | query:").
# TBD: the -2 GGUF carries no prompt metadata; check its card. The GPU-vs-cpu check does not depend on it.
PREFIX = {"rag1": ("Instruct: Given a question, retrieve code that answers it\nQuery: ", ""),
          "rag2": ("task: code retrieval | query: ", "title: none | text: ")}
PREFIX["rag2cpu"] = PREFIX["rag2"]
LEAKS = ("<|im_start|>", "<|im_end|>", "<|endoftext|>", "<｜Assistant｜>", "<｜User｜>", "<｜end▁of▁sentence｜>")

FIB = "def fib(n):\n    a, b = 0, 1\n    for _ in range(n):\n        a, b = b, a + b\n    return a\n"
CSV = "import csv\n\ndef read_rows(path):\n    with open(path, newline='') as f:\n        return list(csv.DictReader(f))\n"
SORT = "def by_key(items, key):\n    return sorted(items, key=lambda d: d[key])\n"


def http(path, body=None, timeout=1800):
    req = urllib.request.Request(API + path, data=None if body is None else json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def gtt():
    v = []
    for p in glob.glob("/sys/class/drm/card*/device/mem_info_gtt_used"):
        try:
            v.append(int(open(p).read()))
        except (OSError, ValueError):
            pass
    return round(max(v) / 2**30, 2) if v else None


def cos(a, b):
    return sum(x * y for x, y in zip(a, b)) / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)) or 1)


def llm(alias, rec):
    ctx = "\n".join(f"# helper {i}\n{FIB}{CSV}{SORT}" for i in range(12))   # ~1.2k tokens of context
    msg = f"{ctx}\nUsing the helpers above, write a function top_rows(path, key, n) that returns the n rows " \
          "of the CSV with the largest numeric value in column key. Reply with one Python code block."
    t = time.time()
    r = http("/v1/chat/completions", {"model": alias, "messages": [{"role": "user", "content": msg}],
                                      "max_tokens": 1024, "temperature": 0.6, "top_p": 0.95, "top_k": 20, "seed": 1})
    m = r["choices"][0]["message"]
    content, reasoning = m.get("content") or "", m.get("reasoning_content") or ""
    tm = r.get("timings", {})
    rec.update(wall_s=round(time.time() - t, 1), finish=r["choices"][0].get("finish_reason"),
               prompt_n=tm.get("prompt_n"), pp_tps=tm.get("prompt_per_second"),
               gen_n=tm.get("predicted_n"), tg_tps=tm.get("predicted_per_second"),
               content_chars=len(content), reasoning_chars=len(reasoning),
               leaks=[s for s in LEAKS if s in content or s in reasoning],
               think_tag_in_content="<think>" in content or "</think>" in content,
               content_head=content[:300])
    # finish=length with empty content is a reasoning budget issue, not a template failure: reported, not failed.
    return not rec["leaks"] and not rec["think_tag_in_content"] and bool(content or reasoning)


def embed(name, alias, outdir, ref, rec):
    q, d = PREFIX[name]
    inputs = [q + "How do I compute the n-th Fibonacci number?", q + "How do I load a CSV file as dicts?",
              d + FIB, d + CSV]
    r = http("/v1/embeddings", {"model": alias, "input": inputs})
    vecs = [x["embedding"] for x in sorted(r["data"], key=lambda x: x["index"])]
    finite = all(math.isfinite(v) for vec in vecs for v in vec)
    sims = [[round(cos(vecs[i], vecs[j]), 4) for j in (2, 3)] for i in (0, 1)]
    rec.update(dim=len(vecs[0]), dim_expected=DIM[name], finite=finite, query_doc_cos=sims,
               ranking_ok=sims[0][0] > sims[0][1] and sims[1][1] > sims[1][0])
    json.dump(vecs, open(f"{outdir}/{name}.vectors.json", "w"))
    ok = finite and rec["dim"] == DIM[name] and rec["ranking_ok"]
    if ref:
        rv = json.load(open(ref))
        rec["gpu_vs_cpu_cos"] = [round(cos(a, b), 5) for a, b in zip(rv, vecs)]
        rec["gpu_vs_cpu_min"] = min(rec["gpu_vs_cpu_cos"])
        ok = ok and rec["gpu_vs_cpu_min"] >= 0.99
    return ok


def rerank(alias, rec):
    docs = [CSV, FIB, SORT]
    r = http("/v1/rerank", {"model": alias, "query": "How do I compute the n-th Fibonacci number?", "documents": docs})
    scores = {x["index"]: x["relevance_score"] for x in r["results"]}
    rec.update(scores=[round(scores[i], 4) for i in range(len(docs))])
    return max(scores, key=scores.get) == 1 and all(math.isfinite(s) for s in scores.values())


def main(argv):
    if len(argv) not in (2, 4) or (len(argv) == 4 and argv[2] != "--ref"):
        print(__doc__, file=sys.stderr)
        return 2
    name, outdir = argv[0], argv[1]
    ref = argv[3] if len(argv) == 4 else None
    rec = {"name": name, "ts": time.strftime("%Y-%m-%dT%H:%M:%S")}
    try:
        models = http("/v1/models")["data"]
        alias = models[0]["id"]
        props = http("/props")
        rec.update(alias=alias, server={k: props.get(k) for k in ("build_info", "model_path", "model_alias")},
                   n_ctx=(props.get("default_generation_settings") or {}).get("n_ctx"))
        if name in ("qwen32", "r1d32"):
            ok = llm(alias, rec)
        elif name in DIM:
            ok = embed(name, alias, outdir, ref, rec)
        elif name == "rerank":
            ok = rerank(alias, rec)
        else:
            print(f"unknown name {name}", file=sys.stderr)
            return 2
    except (OSError, ValueError, KeyError, IndexError) as e:
        rec.update(error=f"{type(e).__name__}: {e}"[:300])
        ok = None
    rec.update(gtt_after_gib=gtt(), ok=ok)
    line = json.dumps(rec)
    print(line)
    with open(f"{outdir}/first-load.jsonl", "a") as f:
        f.write(line + "\n")
    return 0 if ok else (2 if ok is None else 1)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
