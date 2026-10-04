#!/usr/bin/env bash
# Resumable model download. Run by model-download.service until all files are complete.
set -uo pipefail
cd /data/models
python3 - <<'EOF' > manifest.tsv || exit 1
import json, urllib.request
def files(repo, pref):
    t = json.load(urllib.request.urlopen(f"https://huggingface.co/api/models/{repo}/tree/main?recursive=true"))
    return [(repo, f["path"], f["size"]) for f in t if f["path"].startswith(pref) and f["path"].endswith(".gguf")]
for repo, p, size in files("unsloth/Qwen3.6-35B-A3B-GGUF", "Qwen3.6-35B-A3B-UD-Q4_K_XL") + files("unsloth/DeepSeek-V4-Flash-0731-GGUF", "UD-IQ2_M/"):
    print(f"https://huggingface.co/{repo}/resolve/main/{p}\t{p}\t{size}")
EOF
rc=0
while IFS=$'\t' read -r url path size; do
  mkdir -p "$(dirname "$path")"
  [[ -f $path && $(stat -c %s "$path") -eq $size ]] && { echo "OK   $path"; continue; }
  curl -sSL --fail --retry 10 --retry-all-errors -C - -o "$path" "$url" || rc=1
  [[ $(stat -c %s "$path" 2>/dev/null || echo 0) -eq $size ]] && echo "DONE $path" || { echo "INCOMPLETE $path"; rc=1; }
done < manifest.tsv
exit $rc
