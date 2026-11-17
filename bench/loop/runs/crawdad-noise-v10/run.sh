#!/usr/bin/env bash
# Stage N: crawdad-v8-d3 (seed-base 4100) then crawdad-v8-d4 (seed-base 4200).
# Worktree /tmp/wt-stage-n @ 6c56cc09eaafb2376422e73515b39f8193893740.
# Never touch /home/aj/projects/strix-halo-lab, /data/ring-memloop-v9,
# or /home/aj/lab-archive/crawdad-v8-baseline-2026-11-07.
set -euo pipefail

WT=/tmp/wt-stage-n
DIR=/tmp/lab-seats/crawdad-noise-v10
LOG="$DIR/run.log"
MAX_STEPS=12

cd "$WT"
# Record the actual bash PID (setsid may fork, so the launcher's $! can be stale).
echo $$ > "$DIR/run.pid"

# Append all stdout/stderr to run.log for the rest of the script.
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

# debate.py status prints one line per task, then status_line():
#   done: N/M tasks at a leaf, both solos complete
#   owed {...}; next session: invite qwen32|r1d32
status_last_line() {
  local label=$1
  local tmp="$DIR/${label}.status.txt"
  python3 bench/loop/debate.py status --label "$label" > "$tmp"
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
  local label=$1 ext f
  for ext in debate.jsonl debate.meta.json debate.summary.json; do
    f="$WT/bench/loop/results/${label}.${ext}"
    if [[ -e "$f" ]]; then
      echo "ERROR: refused, output exists: $f"
      return 1
    fi
  done
}

session() {
  local label=$1 sess=$2 seat=$3
  shift 3
  local slog="$DIR/${label}.s${sess}.${seat}.log"
  echo "=== $label session $sess seat=$seat $(date -Iseconds) ==="
  preflight 2>&1 | tee -a "$slog"
  invited=1
  scripts/llmctl.py invite "$seat" 2>&1 | tee -a "$slog"
  scripts/llmctl.py run -- python3 bench/loop/debate.py step "$@" 2>&1 | tee -a "$slog"
  scripts/llmctl.py bye 2>&1 | tee -a "$slog"
  invited=0
  echo "=== $label session $sess finished $(date -Iseconds) ==="
}

run_arm() {
  local label=$1 seed=$2
  refuse_if_exists "$label"
  echo "=== arm $label seed-base $seed $(date -Iseconds) ==="
  session "$label" 1 qwen32 --label "$label" --set v8 --seed-base "$seed"

  local i=1 line seat
  while [[ $i -lt $MAX_STEPS ]]; do
    line=$(status_last_line "$label")
    echo "STATUS $label: $line"
    seat=$(parse_seat "$line")
    if [[ "$seat" == done ]]; then
      break
    fi
    i=$((i + 1))
    session "$label" "$i" "$seat" --label "$label"
  done

  line=$(status_last_line "$label")
  echo "STATUS $label final: $line"
  seat=$(parse_seat "$line")
  if [[ "$seat" != done ]]; then
    echo "ERROR: $label not done after $MAX_STEPS sessions (status: $line)"
    return 1
  fi

  echo "=== report --regrade $label $(date -Iseconds) ==="
  python3 bench/loop/debate.py report --label "$label" --regrade
  echo "=== arm $label complete $(date -Iseconds) ==="
}

export PYTHONUNBUFFERED=1
# attempt2: d3 finished and regraded in attempt1 (launcher done-line parse bug); run d4 only.
run_arm crawdad-v8-d4 4200
echo "=== Stage N both arms complete $(date -Iseconds) ==="
