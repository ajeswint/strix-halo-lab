#!/usr/bin/env bash
# First loads of the CRAwDAD pair and the RAG servers, one at a time through llmctl. Quick and dirty smoke
# test, not a benchmark. GPU: run only on the user's go (each load needs READY; llmctl prints the preflight).
# Usage: scripts/first-load.sh [STEP ...]   output dir: FIRSTLOAD_OUT, default /data/bench/first-load;
#        STEP from rag1 rag2 rag2cpu rerank qwen32 r1d32 (default: all, cheap first). rag2cpu needs rag2's vectors.
# Each step: invite (defaults: vk, ctx 32768 LLMs / 8192 RAG, np 1) -> llmctl status (the session note holds the
# GTT delta over the pre-invite baseline, for llmctl gtt_need) -> probe under llmctl run -> bye.
# A failed invite or bye stops the run; a failed probe is recorded and the run goes on. Exit 1 if anything failed.
# Run as ONE Bash command: gpu-guard denies llmctl verbs from agent Bash while a 32B model is resident.
# Results: OUTDIR/first-load.jsonl (one line per probe, incl. server build_info) and OUTDIR/status.log
# (session notes + the server's placement lines; set LLM_SERVE_LV=4 or llama.cpp v0.7.0 does not print them).
set -uo pipefail
here=$(cd "$(dirname "$0")" && pwd)
OUT=${FIRSTLOAD_OUT:-/data/bench/first-load}
STEPS=("$@"); [ ${#STEPS[@]} -eq 0 ] && STEPS=(rag1 rag2 rag2cpu rerank qwen32 r1d32)
CTL=${LLMCTL:-$here/llmctl.py}   # LLMCTL / FIRSTLOAD_API: stub test only (no GPU)
mkdir -p "$OUT"
rc=0
for s in "${STEPS[@]}"; do
    case $s in
        rag2cpu) ep=rag2; opts=(--backend cpu); ref=(--ref "$OUT/rag2.vectors.json")
                 [ -f "$OUT/rag2.vectors.json" ] || { echo "rag2cpu needs $OUT/rag2.vectors.json (run rag2 first)"; rc=1; continue; } ;;
        rag1|rag2|rerank|qwen32|r1d32) ep=$s; opts=(); ref=() ;;
        *) echo "unknown step $s" >&2; exit 2 ;;
    esac
    echo "== $s $(date -Is)"
    t0=$(date +%s)
    "$CTL" invite "$ep" "${opts[@]}" || { echo "invite $ep failed; stopping"; exit 1; }
    { echo "== $s load_s=$(( $(date +%s) - t0 ))"; "$CTL" status; } | tee -a "$OUT/status.log"
    "$CTL" run --mem 2G --as 4G -- python3 -I "$here/first-load-probe.py" "$s" "$OUT" "${ref[@]}" || rc=1
    # Placement lines from the server log (printed only at LLM_SERVE_LV=4; llm-serve.sh)
    journalctl --user -u llm-8081 --since "@$t0" --no-pager -o cat 2>/dev/null \
        | grep -E "Started llm-8081|offloaded|model buffer size|flash_attn" | sed "s/^/[$s] /" | tee -a "$OUT/status.log"
    "$CTL" bye || { echo "bye failed; stopping"; exit 1; }
done
echo "first-load done rc=$rc; results $OUT/first-load.jsonl"
exit $rc
