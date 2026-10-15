#!/usr/bin/env bash
# Serve one model on 127.0.0.1:8081 as a transient user unit (llm-8081).
# Usage: scripts/llm-serve.sh start MODEL [hip|vk|cpu] [ctx] [parallel]
#        scripts/llm-serve.sh stop | status | logs
# MODEL: qwen (Qwen3.6-35B-A3B), laguna (Laguna XS 2.1),
#        qwen32 (Qwen3-32B), r1d32 (DeepSeek-R1-Distill-Qwen-32B)        the CRAwDAD pair, 2026-10-15
#        rag1 (Qwen3-Embedding-0.6B, Qwen's RAG), rag2 (EmbeddingGemma 2, R1-Distill's RAG),
#        rerank (Qwen3-Reranker-4B, shared): /v1/embeddings resp. /v1/rerank, ctx default 8192,
#        batch = ubatch = ctx (an embedding input must fit one ubatch), no KV reuse.
# cpu = build-vk with --device none -ngl 0: the f32 reference for EmbeddingGemma 2 (its activations
# overflow float16; the GPU backends may compute in f16, so its first load compares GPU vs cpu vectors).
# DeepSeek V4 Flash is not served here: it has its own system unit on :8080 (llama-deepseek).
# start runs scripts/preflight.sh first and refuses if it is NOT READY.
# Defaults: vk (Vulkan tg beats HIP by 16% for Qwen at depth 0, pp equal; README Benchmarks),
# ctx 32768 total (RAG models 8192), 1 slot. -c is shared across slots: ctx 65536 parallel 4 = 16k per slot.
# Same conditions as llama-deepseek.service otherwise: -ngl 999 -fa on -lm none.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
UNIT=llm-8081; PORT=8081; LL=/data/src/llama.cpp

case ${1:-} in
start)
    R=/data/models/rag; KIND=llm
    case ${2:-} in
        qwen)   M=/data/models/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf;            ALIAS=qwen3.6-35b-a3b ;;
        laguna) M=/data/models/Laguna-XS-2.1-Q4_K_M.gguf;                  ALIAS=laguna-xs-2.1 ;;
        qwen32) M=/data/models/Qwen3-32B-Q4_K_M.gguf;                      ALIAS=qwen3-32b ;;
        r1d32)  M=/data/models/DeepSeek-R1-Distill-Qwen-32B-Q4_K_M.gguf;   ALIAS=r1-distill-qwen-32b ;;
        rag1)   M=$R/Qwen3-Embedding-0.6B-Q8_0.gguf; ALIAS=qwen3-embedding-0.6b; KIND=embed ;;
        rag2)   M=$R/embeddinggemma-2-Q8_0.gguf;     ALIAS=embeddinggemma-2;     KIND=embed ;;
        rerank) M=$R/Qwen3-Reranker-4B.Q8_0.gguf;    ALIAS=qwen3-reranker-4b;    KIND=rerank ;;
        *) echo "usage: $0 start qwen|laguna|qwen32|r1d32|rag1|rag2|rerank [hip|vk|cpu] [ctx] [parallel]" >&2; exit 2 ;;
    esac
    [ "$KIND" = llm ] && DEFCTX=32768 || DEFCTX=8192
    BE=${3:-vk}; CTX=${4:-$DEFCTX}; NP=${5:-1}
    case $BE in hip|vk) BIN=$BE; DEV=(-ngl 999) ;; cpu) BIN=vk; DEV=(--device none -ngl 0) ;;
        *) echo "backend must be hip, vk or cpu" >&2; exit 2 ;; esac
    # A cpu model sits in RAM, not GTT, so gpu-guard and the 16 GiB cutoff cannot see it: RAG models only.
    if [ "$BE" = cpu ] && [ "$KIND" = llm ]; then echo "cpu backend is for rag1|rag2|rerank only" >&2; exit 2; fi
    case $KIND in
        llm)    EXTRA=(--cache-reuse 256) ;;
        embed)  EXTRA=(--embedding -b "$CTX" -ub "$CTX") ;;
        rerank) EXTRA=(--reranking -b "$CTX" -ub "$CTX") ;;
    esac
    if systemctl --user is-active -q "$UNIT"; then
        echo "$UNIT already running; stop it first" >&2; exit 1
    fi
    "$here/preflight.sh" "$M" || { echo "refusing to start: preflight NOT READY" >&2; exit 1; }
    systemd-run --user --unit="$UNIT" --collect --property=Restart=no \
        --setenv=ROCBLAS_USE_HIPBLASLT=1 \
        "$LL/build-$BIN/bin/llama-server" -m "$M" --alias "$ALIAS" \
        "${DEV[@]}" -fa on -lm none -c "$CTX" -np "$NP" "${EXTRA[@]}" \
        --no-webui --host 127.0.0.1 --port "$PORT"
    # Bounded wait for the model to load (Qwen ~21 GiB from NVMe); not a watchdog.
    for _ in $(seq 1 180); do
        if curl -sf "http://127.0.0.1:$PORT/health" >/dev/null; then
            echo "up: $ALIAS on $BE, ctx $CTX, parallel $NP, http://127.0.0.1:$PORT/v1"
            exit 0
        fi
        systemctl --user is-active -q "$UNIT" || { echo "$UNIT exited during load:" >&2; journalctl --user -u "$UNIT" -n 30 --no-pager >&2; exit 1; }
        sleep 1
    done
    echo "not healthy after 180 s; still loading or stuck. Check: $0 logs" >&2; exit 1
    ;;
stop)
    systemctl --user stop "$UNIT" 2>/dev/null || true
    echo "stopped $UNIT" ;;
status)
    echo "$UNIT: $(systemctl --user is-active "$UNIT" 2>/dev/null || true)"
    curl -sf "http://127.0.0.1:$PORT/v1/models" | python3 -c 'import json,sys; print("serving:", ", ".join(m["id"] for m in json.load(sys.stdin)["data"]))' 2>/dev/null \
        || echo "serving: nothing on :$PORT"
    for d in /sys/class/drm/card*/device; do { read -r u < "$d/mem_info_gtt_used"; } 2>/dev/null && echo "gtt_used=$((u >> 30))GiB"; done ;;
logs)
    journalctl --user -u "$UNIT" -n "${2:-50}" --no-pager ;;
*)
    echo "usage: $0 start qwen|laguna|qwen32|r1d32|rag1|rag2|rerank [hip|vk|cpu] [ctx] [parallel] | stop | status | logs [n]" >&2; exit 2 ;;
esac
