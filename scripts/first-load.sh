#!/usr/bin/env bash
# First loads of the CRAwDAD pair and the RAG servers, one at a time through llmctl. Quick and dirty smoke
# test, not a benchmark. GPU: run only on the user's go (each load needs READY; llmctl prints the preflight).
# Usage: scripts/first-load.sh [OUTDIR] [STEP ...]   OUTDIR default /data/bench/first-load;
#        STEP from rag1 rag2 rag2cpu rerank qwen32 r1d32 (default: all, cheap first). rag2cpu needs rag2's vectors.
# Each step: invite (defaults: vk, ctx 32768 LLMs / 8192 RAG, np 1) -> llmctl status (the session note holds the
# GTT delta over the pre-invite baseline, for llmctl gtt_need) -> probe under llmctl run -> bye.
# A failed invite or bye stops the run; a failed probe is recorded and the run goes on. Exit 1 if anything failed.
# Run as ONE Bash command: gpu-guard denies llmctl verbs from agent Bash while a 32B model is resident.
# Results: OUTDIR/first-load.jsonl (one line per probe, incl. server build_info) and OUTDIR/status.log.
set -uo pipefail
here=$(cd "$(dirname "$0")" && pwd)
OUT=${1:-/data/bench/first-load}; shift || true
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
    "$CTL" bye || { echo "bye failed; stopping"; exit 1; }
done
echo "first-load done rc=$rc; results $OUT/first-load.jsonl"
exit $rc
