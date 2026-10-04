#!/usr/bin/env bash
# Post-login check for ROCm on gfx1151
for d in /opt/rocm/bin /opt/rocm/core-10.0/bin; do [ -d "$d" ] && PATH="$d:$PATH"; done
echo "== groups";   groups
echo "== binaries"; command -v rocminfo amd-smi hipcc || find /opt -maxdepth 4 -name rocminfo 2>/dev/null
echo "== rocminfo"; rocminfo | grep -E 'Name:\s+gfx|Marketing Name'
echo "== amd-smi";  amd-smi version; amd-smi static --asic
