#!/usr/bin/env bash
# Usage: bench.sh <label> <model.gguf> [extra llama-bench args]
# Framework test conditions: pp2048 / tg128, concurrency 1. Appends to /data/bench/results.jsonl
set -euo pipefail
LABEL=$1; MODEL=$2; shift 2
OUT=/data/bench/results.jsonl
LL=/data/src/llama.cpp

state() {
  printf '{"label":"%s","ts":"%s","ppd":"%s","tuned":"%s","gpu_level":"%s","epp":"%s","cmdline":"%s","gtt_mib":%s}\n' \
    "$LABEL" "$(date -Is)" \
    "$(powerprofilesctl get 2>/dev/null || echo n/a)" \
    "$(tuned-adm active 2>/dev/null | sed 's/.*: //' || echo n/a)" \
    "$(cat /sys/class/drm/card*/device/power_dpm_force_performance_level 2>/dev/null | head -1)" \
    "$(cat /sys/devices/system/cpu/cpu0/cpufreq/energy_performance_preference)" \
    "$(cat /proc/cmdline)" \
    "$(( $(cat /sys/class/drm/card*/device/mem_info_gtt_total 2>/dev/null | head -1) / 1048576 ))"
}

state >> "$OUT"
for be in hip vk; do
  ROCBLAS_USE_HIPBLASLT=1 "$LL/build-$be/bin/llama-bench" -m "$MODEL" -ngl 999 -fa on -lm none \
    -p 2048 -n 128 -r 3 -o jsonl "$@" 2>/dev/null \
    | sed "s/^{/{\"label\":\"$LABEL\",\"backend\":\"$be\",/" | tee -a "$OUT"
done
