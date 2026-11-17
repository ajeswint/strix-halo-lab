#!/usr/bin/env bash
# CRAwDAD 2-slot quality check: crawdad-v8-d2p2 (seed-base 4000, same as crawdad-v8-d2).
# AJ approved 2026-11-17 15:39 CST. Worktree /tmp/wt-d2p2 @ bc260ff701ba815640eb1c9eda7927064b2c6cc1 (origin/main).
# Protocol: Stage N v8 debate, exactly as d2/d3/d4 (expected hash 137acf32c95d at seed-base 4000).
# ONLY differences from Stage N: every invite gets --ctx 65536 --np 2 (2 slots x 32768, the same per-slot
# context as d2), every debate.py step gets --parallel 2, plus a STEP timing line per session.
# Pre-registered bar (also in prereg.md, written before launch):
#   PASS: leaf score 8..13/30 AND discordant tasks vs crawdad-v8-d2 <= 10.
#   FAIL: leaf score <= 7, OR discordant tasks vs crawdad-v8-d2 > 10.
# No DeepSeek. No model substitution. No code changes.
# Never touch /home/aj/projects/strix-halo-lab, /data/ring-memloop-v9,
# or /home/aj/lab-archive/crawdad-v8-baseline-2026-11-07.
set -euo pipefail

WT=/tmp/wt-d2p2
DIR=/tmp/lab-seats/crawdad-v8-d2p2
LOG="$DIR/run.log"
MAX_STEPS=12
EXPECT_HEAD=bc260ff701ba815640eb1c9eda7927064b2c6cc1
INVITE_OPTS=(--ctx 65536 --np 2)
PARALLEL=2

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

[[ "$(git rev-parse HEAD)" == "$EXPECT_HEAD" ]] || { echo "ERROR: head not $EXPECT_HEAD"; exit 1; }
[[ -z "$(git status --porcelain)" ]] || { echo "ERROR: worktree dirty"; exit 1; }
[[ -s "$DIR/prereg.md" ]] || { echo "ERROR: $DIR/prereg.md missing"; exit 1; }

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

# Served shape must be 2 slots x 32768 per slot (same per-slot ctx as d2), else stop.
check_props() {
  local out
  out=$(curl -s http://127.0.0.1:8081/props | python3 -c "import json,sys;p=json.load(sys.stdin);print('total_slots',p.get('total_slots'),'n_ctx',(p.get('default_generation_settings') or {}).get('n_ctx'),'build',p.get('build_info'))")
  echo "props: $out"
  if [[ "$out" != "total_slots 2 n_ctx 32768 "* ]]; then
    echo "ERROR: served shape is not 2 slots x 32768: $out"
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
  scripts/llmctl.py invite "$seat" "${INVITE_OPTS[@]}" 2>&1 | tee -a "$slog"
  check_props 2>&1 | tee -a "$slog"
  local t0 t1
  t0=$(date +%s.%N); echo "STEP_START $label s$sess $seat $(date -u +%FT%TZ) $t0" | tee -a "$slog"
  scripts/llmctl.py run -- python3 bench/loop/debate.py step "$@" --parallel "$PARALLEL" 2>&1 | tee -a "$slog"
  t1=$(date +%s.%N); echo "STEP_END $label s$sess $seat $(date -u +%FT%TZ) $t1" | tee -a "$slog"
  python3 -c "print('STEP_WALL $label s$sess $seat %.1f s' % ($t1-$t0))" | tee -a "$slog"
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
run_arm crawdad-v8-d2p2 4000
echo "=== d2p2 complete $(date -Iseconds) ==="
