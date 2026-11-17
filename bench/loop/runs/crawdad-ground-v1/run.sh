#!/usr/bin/env bash
# CRAwDAD Grounding v1 (PR #16): arms P/G/C on v10 (90 tasks), seeds 5000-5099,
# qwen32 session then r1d32 session, then CPU report --regrade.
# Worktree /tmp/wt-ground-run @ 1eb694f8aaf53f7730dd6922c1dcfe8d301208f6 (merged main).
# Protocol hash must be a7efb2060615. No DeepSeek. No model substitution.
# Never touch /home/aj/projects/strix-halo-lab, /data/ring-memloop-v9,
# or /home/aj/lab-archive/crawdad-v8-baseline-2026-11-07.
set -euo pipefail

WT=/tmp/wt-ground-run
DIR=/tmp/lab-seats/crawdad-ground-v1
LABEL=crawdad-ground-v1
EXPECT_HEAD=1eb694f8aaf53f7730dd6922c1dcfe8d301208f6
EXPECT_PROTOCOL=a7efb2060615
MAX_STEPS=6

cd "$WT"
echo $$ > "$DIR/run.pid"

exec >>"$DIR/out.log" 2>>"$DIR/err.log"

start=$(date +%s)
echo "running $(date -Iseconds)" > "$DIR/run.status"
echo "=== start $(date -Iseconds) pwd=$PWD head=$(git rev-parse HEAD) ==="

invited=0
on_exit() {
  local rc=$?
  if [[ $invited -eq 1 ]]; then
    echo "=== EXIT trap: scripts/llmctl.py bye (script rc=$rc) ==="
    scripts/llmctl.py bye || true
    invited=0
  fi
  local wall=$(( $(date +%s) - start ))
  echo "done rc=$rc wall_s=$wall end=$(date -Iseconds)" > "$DIR/run.status"
  echo "=== end $(date -Iseconds) rc=$rc wall_s=$wall ==="
}
trap on_exit EXIT

if [[ "$(git rev-parse HEAD)" != "$EXPECT_HEAD" ]]; then
  echo "ERROR: worktree head is not $EXPECT_HEAD"; exit 1
fi
if [[ -n "$(git status --porcelain)" ]]; then
  echo "ERROR: worktree is dirty"; exit 1
fi
proto=$(python3 -c "import sys; sys.path.insert(0,'bench/loop'); import ground; print(ground.PROTOCOL)")
if [[ "$proto" != "$EXPECT_PROTOCOL" ]]; then
  echo "ERROR: protocol hash $proto != $EXPECT_PROTOCOL"; exit 1
fi
echo "protocol hash OK: $proto"

preflight() {
  local out rc
  set +e
  out=$(bash scripts/preflight.sh 2>&1)
  rc=$?
  set -e
  printf '%s\n' "$out"
  if [[ $rc -ne 0 ]]; then
    echo "ERROR: preflight.sh exited $rc"
    return 1
  fi
  if ! grep -q 'llama-deepseek=inactive' <<<"$out"; then
    echo "ERROR: preflight did not report llama-deepseek=inactive"
    return 1
  fi
  if ! grep -qx 'READY' <<<"$out"; then
    echo "ERROR: preflight did not print READY"
    return 1
  fi
}

# ground.py status prints per-task lines, then status_line():
#   done: N/90 tasks complete across all arms (P, G, C)
#   owed {...}; next session: invite qwen32|r1d32
# Fixed logic: capture to a file, echo the full listing to stderr only,
# print just the last non-empty line on stdout (no tee into captured stdout).
status_last_line() {
  local tmp="$DIR/${LABEL}.status.txt"
  python3 bench/loop/ground.py status --label "$LABEL" > "$tmp"
  cat "$tmp" >&2
  awk 'NF{line=$0} END{print line}' "$tmp"
}

parse_seat() {
  local line=$1
  if [[ "$line" == done:* ]]; then
    echo "done"
    return 0
  fi
  if [[ "$line" =~ next\ session:\ invite\ (qwen32|r1d32) ]]; then
    echo "${BASH_REMATCH[1]}"
    return 0
  fi
  echo "ERROR: cannot parse status line: $line" >&2
  return 1
}

refuse_if_exists() {
  local ext f
  for ext in ground.meta.json ground.jsonl ground.summary.json; do
    f="$WT/bench/loop/results/${LABEL}.${ext}"
    if [[ -e "$f" ]]; then
      echo "ERROR: refused, output exists: $f"
      return 1
    fi
  done
}

session() {
  local sess=$1 seat=$2
  shift 2
  local slog="$DIR/${LABEL}.s${sess}.${seat}.log"
  echo "=== $LABEL session $sess seat=$seat $(date -Iseconds) ==="
  preflight 2>&1 | tee -a "$slog"
  invited=1
  scripts/llmctl.py invite "$seat" 2>&1 | tee -a "$slog"
  scripts/llmctl.py run -- python3 bench/loop/ground.py step "$@" 2>&1 | tee -a "$slog"
  scripts/llmctl.py bye 2>&1 | tee -a "$slog"
  invited=0
  echo "=== $LABEL session $sess finished $(date -Iseconds) ==="
}

export PYTHONUNBUFFERED=1
refuse_if_exists
session 1 qwen32 --label "$LABEL" --set v10

i=1
while [[ $i -lt $MAX_STEPS ]]; do
  line=$(status_last_line)
  echo "STATUS $LABEL: $line"
  seat=$(parse_seat "$line")
  if [[ "$seat" == done ]]; then
    break
  fi
  i=$((i + 1))
  session "$i" "$seat" --label "$LABEL"
done

line=$(status_last_line)
echo "STATUS $LABEL final: $line"
seat=$(parse_seat "$line")
if [[ "$seat" != done ]]; then
  echo "ERROR: $LABEL not done after $MAX_STEPS sessions (status: $line)"
  exit 1
fi

echo "=== report --regrade $LABEL $(date -Iseconds) ==="
python3 bench/loop/ground.py report --label "$LABEL" --regrade
echo "=== $LABEL complete $(date -Iseconds) ==="
