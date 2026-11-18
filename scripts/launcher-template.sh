#!/usr/bin/env bash
# GPU Run Launcher Template
#
# Standard template for GPU run launchers (e.g. bench/loop/runs/<label>/run.sh).
# Requires pre-registered bar to be committed AND pushed to remote before launch.
#
# Usage:
#   1. Copy to bench/loop/runs/<label>/run.sh
#   2. Set EXPECT_HEAD, WT, DIR, PREREG_FILE, etc.
#   3. Ensure prereg.md is committed and pushed before running.
set -euo pipefail

WT="/tmp/wt-<run-label>"
DIR="/tmp/lab-seats/<run-label>"
LOG="$DIR/run.log"
EXPECT_HEAD="<expected-git-commit-sha>"
PREREG_FILE="bench/loop/runs/<run-label>/prereg.md"
REMOTE_REF="${REMOTE_REF:-origin/main}"

mkdir -p "$DIR"
cd "$WT"
# Record actual bash PID
echo $$ > "$DIR/run.pid"

# Append all stdout/stderr to run.log
exec >>"$LOG" 2>&1

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

# 1. Clean worktree and expected HEAD checks
[[ "$(git rev-parse HEAD)" == "$EXPECT_HEAD" ]] || { echo "ERROR: head not $EXPECT_HEAD"; exit 1; }
[[ -z "$(git status --porcelain)" ]] || { echo "ERROR: worktree dirty"; exit 1; }

# 2. Pre-registered bar guard: verifies file is tracked, clean, committed, and reachable from pushed remote ref
bash scripts/prereg-guard.sh "$PREREG_FILE" "$REMOTE_REF"

# 3. Memory preflight check before any model load
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
preflight

# 4. Model session and workload execution
# invited=1
# scripts/llmctl.py invite <endpoint> ...
