#!/usr/bin/env bash
# Serve one small model on 127.0.0.1:8081 as a transient user unit (llm-8081).
# Usage: scripts/llm-serve.sh start qwen|laguna [hip|vk] [ctx] [parallel]
#        scripts/llm-serve.sh stop | status | logs
# DeepSeek is not served here: it has its own system unit on :8080 (llama-deepseek).
# start runs scripts/preflight.sh first and refuses if it is NOT READY.
# Defaults: vk (Vulkan tg beats HIP by 16% for Qwen at depth 0, pp equal; README Benchmarks),
# ctx 32768 total, 1 slot. -c is shared across slots: ctx 65536 parallel 4 = 16k per slot.
# Same conditions as llama-deepseek.service otherwise: -ngl 999 -fa on -lm none.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
UNIT=llm-8081; PORT=8081; LL=/data/src/llama.cpp

case ${1:-} in
start)
    case ${2:-} in
        qwen)   M=/data/models/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf; ALIAS=qwen3.6-35b-a3b ;;
        laguna) M=/data/models/Laguna-XS-2.1-Q4_K_M.gguf;       ALIAS=laguna-xs-2.1 ;;
        *) echo "usage: $0 start qwen|laguna [hip|vk] [ctx] [parallel]" >&2; exit 2 ;;
    esac
    BE=${3:-vk}; CTX=${4:-32768}; NP=${5:-1}
    case $BE in hip|vk) ;; *) echo "backend must be hip or vk" >&2; exit 2 ;; esac
    if systemctl --user is-active -q "$UNIT"; then
        echo "$UNIT already running; stop it first" >&2; exit 1
    fi
    "$here/preflight.sh" "$M" || { echo "refusing to start: preflight NOT READY" >&2; exit 1; }
    systemd-run --user --unit="$UNIT" --collect --property=Restart=no \
        --setenv=ROCBLAS_USE_HIPBLASLT=1 \
        "$LL/build-$BE/bin/llama-server" -m "$M" --alias "$ALIAS" \
        -ngl 999 -fa on -lm none -c "$CTX" -np "$NP" --cache-reuse 256 \
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
    echo "usage: $0 start qwen|laguna [hip|vk] [ctx] [parallel] | stop | status | logs [n]" >&2; exit 2 ;;
esac
