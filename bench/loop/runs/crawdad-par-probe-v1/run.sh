#!/usr/bin/env bash
# CRAwDAD parallel timing probe v1 (AJ approved 2026-11-17 14:19 CST).
# Question: does llama-server --parallel 2 cut wall time for one session's replies?
# Bar: keep going only if step wall time drops >= 25% from arm 1 to arm 2. Pass rates NOT judged.
# Arm 1: qwen32 default (ctx 32768, np 1), debate.py step --parallel 1 (default).
# Arm 2: qwen32 --ctx 65536 --np 2 (32768 per slot, same as arm 1), debate.py step --parallel 2.
# Same 8 spent v7 tasks, qwen32 solo step only. No DeepSeek. No model substitution. No code changes.
# Worktree /tmp/wt-par-probe @ 1eb694f (origin/main). Timestamps taken outside `llmctl run`,
# after invite returns (model loaded, /health OK) and after the step returns: load time excluded.
set -euo pipefail

WT=/tmp/wt-par-probe
DIR=/tmp/lab-seats/crawdad-par-probe
EXPECT_HEAD=1eb694f8aaf53f7730dd6922c1dcfe8d301208f6
TASKS=v7_01_packbits,v7_02_ini_strict,v7_03_semver_order,v7_04_partition_rank,v7_05_digit_rules,v7_06_route_lexmin,v7_07_rect_union,v7_08_bowling_frames

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
  fi
  echo "done rc=$rc wall_s=$(( $(date +%s) - start )) end=$(date -Iseconds)" > "$DIR/run.status"
  echo "=== end $(date -Iseconds) rc=$rc ==="
}
trap on_exit EXIT

[[ "$(git rev-parse HEAD)" == "$EXPECT_HEAD" ]] || { echo "ERROR: head not $EXPECT_HEAD"; exit 1; }
[[ -z "$(git status --porcelain)" ]] || { echo "ERROR: worktree dirty"; exit 1; }
for l in crawdad-par-p1 crawdad-par-p2; do
  for f in bench/loop/results/$l.debate*; do if [[ -e "$f" ]]; then echo "ERROR: output exists: $f"; exit 1; fi; done
done

preflight() {
  local out rc
  set +e; out=$(bash scripts/preflight.sh 2>&1); rc=$?; set -e
  printf '%s\n' "$out"
  [[ $rc -eq 0 ]] || { echo "ERROR: preflight rc=$rc"; return 1; }
  grep -q 'llama-deepseek=inactive' <<<"$out" || { echo "ERROR: llama-deepseek not inactive"; return 1; }
  grep -qx 'READY' <<<"$out" || { echo "ERROR: preflight not READY"; return 1; }
}

arm() {
  local n=$1 label=$2; shift 2
  local slog="$DIR/arm$n.log" invite_args=() step_args=()
  while [[ $# -gt 0 && "$1" != "--" ]]; do invite_args+=("$1"); shift; done
  shift; step_args=("$@")
  echo "=== arm $n $label $(date -Iseconds) invite=[${invite_args[*]}] step=[${step_args[*]}] ===" | tee -a "$slog"
  preflight 2>&1 | tee -a "$slog"
  invited=1
  scripts/llmctl.py invite qwen32 "${invite_args[@]}" 2>&1 | tee -a "$slog"
  curl -s http://127.0.0.1:8081/props | python3 -c "import json,sys;p=json.load(sys.stdin);print('props: total_slots',p.get('total_slots'),'n_ctx',(p.get('default_generation_settings') or {}).get('n_ctx'),'build',p.get('build_info'))" 2>&1 | tee -a "$slog"
  local t0 t1
  t0=$(date +%s.%N); echo "STEP_START arm$n $(date -u +%FT%TZ) $t0" | tee -a "$slog"
  scripts/llmctl.py run -- python3 bench/loop/debate.py step --label "$label" --set v7 --tasks "$TASKS" "${step_args[@]}" 2>&1 | tee -a "$slog"
  t1=$(date +%s.%N); echo "STEP_END arm$n $(date -u +%FT%TZ) $t1" | tee -a "$slog"
  python3 -c "print('STEP_WALL arm$n %.1f s' % ($t1-$t0))" | tee -a "$slog"
  python3 bench/loop/debate.py status --label "$label" 2>&1 | tee -a "$slog"
  scripts/llmctl.py bye 2>&1 | tee -a "$slog"
  invited=0
  echo "=== arm $n finished $(date -Iseconds) ===" | tee -a "$slog"
}

export PYTHONUNBUFFERED=1
arm 1 crawdad-par-p1 --
arm 2 crawdad-par-p2 --ctx 65536 --np 2 -- --parallel 2
echo "=== probe complete $(date -Iseconds) ==="
