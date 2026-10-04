#!/usr/bin/env bash
# Full rerun with fans pegged (framework_tool --fansetduty 100). Logs W/T/fan/sclk to /data/bench/fanpeg-mon.log
set -uo pipefail
M=/data/models/UD-IQ2_M/DeepSeek-V4-Flash-0731-UD-IQ2_M-00001-of-00003.gguf
Q=/data/models/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf
LL=/data/src/llama.cpp
D=$(dirname $(ls /sys/class/drm/card*/device/pp_dpm_sclk | head -1))
H=$(grep -l amdgpu /sys/class/hwmon/hwmon*/name | head -1 | xargs dirname)
F=$(grep -l cros_ec /sys/class/hwmon/hwmon*/name | head -1 | xargs dirname)
G=$D/mem_info_gtt_used
( while :; do echo "$(date +%s) phase=$(cat /tmp/fanpeg-phase 2>/dev/null) W=$(( $(cat $H/power1_average)/1000000 )) T=$(( $(cat $H/temp1_input)/1000 )) fan2=$(cat $F/fan2_input) fan1=$(cat $F/fan1_input) sclk=$(grep '\*' $D/pp_dpm_sclk | awk '{print $2}') busy=$(cat $D/gpu_busy_percent)"; sleep 2; done ) > /data/bench/fanpeg-mon.log & MON=$!
trap 'kill $MON' EXIT
tag() { sed "s/^{/{\"label\":\"$1\",\"backend\":\"$2\",/" | tee -a /data/bench/results.jsonl; }

echo soak > /tmp/fanpeg-phase
"$LL/build-vk/bin/llama-bench" -m $M -ngl 999 -fa on -lm none -p 2048 -n 0 -r 60 -o jsonl 2>/dev/null | tag t3-fan-vk-soak vk >/dev/null
echo qwen > /tmp/fanpeg-phase
bash /data/bench/bench.sh t3-fan-qwen $Q >/dev/null 2>&1
echo dsv4-depth > /tmp/fanpeg-phase
bash /data/bench/bench.sh t3-fan-dsv4-depth $M -d 0,8192,32768 -r 2 >/dev/null 2>&1
for be in vk hip; do
  echo fit64k-$be > /tmp/fanpeg-phase
  ( peak=0; while :; do u=$(cat $G); [ $u -gt $peak ] && peak=$u && echo $peak > /tmp/fanpeg-gtt-$be; sleep 2; done ) & P=$!
  ROCBLAS_USE_HIPBLASLT=1 "$LL/build-$be/bin/llama-bench" -m $M -ngl 999 -fa on -lm none -p 0 -n 128 -d 65536 -r 1 -o jsonl 2>/dev/null | tag t3-fan-dsv4-fit64k $be >/dev/null
  kill $P
done
echo done > /tmp/fanpeg-phase
