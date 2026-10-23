#!/usr/bin/env bash
# Memory preflight before loading any model, llama-bench/llama-perplexity, or training.
# Usage: scripts/preflight.sh [model.gguf ...]   (split GGUF: pass shard 1; all shards are summed)
# Several models = one group loaded together (llmctl's crawdad group): their sizes are summed.
# PREFLIGHT_NEED_GIB=N raises the need to at least N GiB (llmctl passes the group's measured GTT deltas + 16,
# because five models' KV cache and buffers outgrow one 16 GiB margin over the summed files).
# Exit 0 = READY, 1 = NOT READY. Read-only; loads nothing.
# Policy (CLAUDE.md, README Security, 2026-10-04 OOM): one model at a time. READY needs
# llama-deepseek inactive, no llama-* process, GTT used <= 16 GiB (the gpu-guard cutoff),
# and, with a model given, MemAvailable and free GTT both >= model size + 16 GiB.
# The 16 GiB margin is a floor for KV cache and buffers, not a fit prediction.
set -u
GiB=$((1<<30)); CUT=$((16*GiB)); MARGIN=$((16*GiB))
gib() { awk -v b="$1" 'BEGIN{printf "%.1f", b/2^30}'; }

gtt_used=0; gtt_total=0
for d in /sys/class/drm/card*/device; do
    { read -r u < "$d/mem_info_gtt_used"; } 2>/dev/null || continue
    { read -r t < "$d/mem_info_gtt_total"; } 2>/dev/null || t=0
    [ "$u" -gt "$gtt_used" ] && gtt_used=$u
    [ "$t" -gt "$gtt_total" ] && gtt_total=$t
done
avail=$(( $(awk '/^MemAvailable:/{print $2}' /proc/meminfo) * 1024 ))
swapfree=$(( $(awk '/^SwapFree:/{print $2}' /proc/meminfo) * 1024 ))
ds=$(systemctl is-active llama-deepseek 2>/dev/null)
procs=$(pgrep -a '^llama-' | cut -c1-160)

fail=()
[ "$gtt_total" -eq 0 ] && fail+=("GTT unreadable")
case $ds in active|activating|reloading) fail+=("llama-deepseek is $ds (~85 GiB GTT); ask the user before stopping it");; esac
[ -n "$procs" ] && fail+=("llama process running")
[ "$gtt_used" -gt "$CUT" ] && fail+=("GTT used $(gib "$gtt_used") GiB > 16 GiB: a model is resident")

echo "gtt_used=$(gib "$gtt_used")GiB gtt_total=$(gib "$gtt_total")GiB mem_available=$(gib "$avail")GiB swap_free=$(gib "$swapfree")GiB llama-deepseek=$ds"
[ -n "$procs" ] && echo "llama processes:" && echo "$procs"

if [ $# -ge 1 ]; then
    size=0; names=()
    for m in "$@"; do
        if [ ! -f "$m" ]; then
            fail+=("model not found: $m"); continue
        fi
        # DeepSeek-...-00001-of-00003.gguf -> sum every shard of the set
        if [[ $m =~ ^(.*)-[0-9]{5}-of-([0-9]{5})\.gguf$ ]]; then
            s=$(stat -c %s "${BASH_REMATCH[1]}"-?????-of-"${BASH_REMATCH[2]}".gguf | awk '{s+=$1} END{print s}')
        else
            s=$(stat -c %s "$m")
        fi
        size=$((size + s)); names+=("$(basename "$m")")
    done
    need=$((size + MARGIN))
    if [ -n "${PREFLIGHT_NEED_GIB:-}" ]; then
        floor=$(awk -v g="$PREFLIGHT_NEED_GIB" 'BEGIN{printf "%d", g * 2^30}')
        [ "$floor" -gt "$need" ] && need=$floor
    fi
    echo "model=$(IFS=+; echo "${names[*]}") size=$(gib "$size")GiB need=$(gib "$need")GiB gtt_free=$(gib $((gtt_total - gtt_used)))GiB"
    [ "$avail" -lt "$need" ] && fail+=("MemAvailable $(gib "$avail") GiB < need $(gib "$need") GiB")
    [ $((gtt_total - gtt_used)) -lt "$need" ] && fail+=("free GTT $(gib $((gtt_total - gtt_used))) GiB < need $(gib "$need") GiB")
fi

if [ ${#fail[@]} -eq 0 ]; then
    echo "READY"; exit 0
fi
echo "NOT READY"; printf -- '- %s\n' "${fail[@]}"; exit 1
