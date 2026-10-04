#!/usr/bin/env bash
# Post-reboot verification + benchmark. Usage: post-reboot.sh <label>
set -uo pipefail
LABEL=${1:-t2-post-reboot}
echo "BIOS:        $(cat /sys/class/dmi/id/bios_version)"
echo "cmdline:     $(cat /proc/cmdline)"
grep -q crashkernel /proc/cmdline && echo "crashkernel: STILL PRESENT" || echo "crashkernel: gone"
echo "MemTotal:    $(awk '/MemTotal/{printf "%.1f GiB", $2/1048576}' /proc/meminfo)"
echo "IOMMU:       $(ls /sys/class/iommu 2>/dev/null | wc -l) iommu device(s)"
echo "tuned:       $(tuned-adm active 2>/dev/null | sed 's/.*: //')"
echo "GTT:         $(( $(cat /sys/class/drm/card*/device/mem_info_gtt_total | head -1) / 1048576 )) MiB"
echo "download:    $(systemctl is-active model-download) / $(du -sh /data/models/UD-IQ2_M | cut -f1) of ~91G"
/data/bench/bench.sh "$LABEL" /data/models/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf >/dev/null
python3 /data/bench/report.py | grep -E "label|t1b|$LABEL"
