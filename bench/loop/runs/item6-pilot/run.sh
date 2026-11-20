#!/usr/bin/env bash
# Roadmap Item 6 Pilot: Real-PR Test Launcher
#
# Evaluates 7 real PR tasks from strix-halo-lab repository history using the kept local setup:
# single Qwen3.6-35B-A3B agentic loop with test feedback (bench/loop/pilot_pr.py).
# NO DeepSeek arm (AJ dropped it).
#
# Pre-registered bar: docs/item6-pilot.md.
# Must be committed AND pushed to REMOTE_REF (origin/main) before launch.
#
# Safety invariants:
# - Preflight requires llama-deepseek=inactive and READY.
# - Never touch /data/ring-memloop-v9 or any seal.key.
# - Clean worktree and expected HEAD verified before any GPU activity.
set -euo pipefail

WT="${WT:-<path-to-clean-worktree>}"
LABEL="${LABEL:-item6-pilot-v2}"
DIR="${DIR:-/tmp/lab-seats/${LABEL}}"
LOG="$DIR/run.log"
EXPECT_HEAD="${EXPECT_HEAD:-<expected-git-commit-sha>}"
PREREG_FILE="docs/item6-pilot.md"
REMOTE_REF="${REMOTE_REF:-origin/main}"
QWEN_MODEL_PATH="/data/models/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf"
INVITE_OPTS=(--ctx 65536 --np 1)
PARALLEL=1
SLOT_CTX=65536
CEILING_SECONDS="${CEILING_SECONDS:-4320}" # 1.2 GPU-hours (4320 s) hard ceiling
TASK_WALL_BUDGET="${TASK_WALL_BUDGET:-$(( CEILING_SECONDS / 7 ))}" # floor(4320/7) = 617 s per task
RESUME="${RESUME:-0}"

# Refuse to overwrite frozen v1 results
if [[ "$LABEL" == "item6-pilot" ]]; then
  echo "ERROR: v1 results (label 'item6-pilot') are frozen and must not be overwritten; use LABEL=item6-pilot-v2" >&2
  exit 1
fi

# Refuse to run when WT or EXPECT_HEAD is still the placeholder or empty
if [[ -z "$WT" || "$WT" == "<path-to-clean-worktree>" || "$WT" == "<"*">" ]]; then
  echo "ERROR: WT must be set to a real worktree path (got '$WT')" >&2
  exit 1
fi
if [[ -z "$EXPECT_HEAD" || "$EXPECT_HEAD" == "<expected-git-commit-sha>" || "$EXPECT_HEAD" == "<"*">" ]]; then
  echo "ERROR: EXPECT_HEAD must be set to the expected git commit SHA (got '$EXPECT_HEAD')" >&2
  exit 1
fi

mkdir -p "$DIR"
cd "$WT"
# Record actual bash PID
echo $$ > "$DIR/run.pid"

# Append all stdout/stderr to run.log
exec >>"$LOG" 2>&1

start=$(date +%s)
echo "running $(date -Iseconds)" > "$DIR/run.status"
echo "=== start $(date -Iseconds) pwd=$PWD head=$(git rev-parse HEAD) ceiling_seconds=$CEILING_SECONDS resume=$RESUME ==="

invited=0
on_exit() {
  local rc=$?
  if [[ $invited -eq 1 ]]; then
    echo "=== EXIT trap: scripts/llmctl.py bye (script rc=$rc) ==="
    scripts/llmctl.py bye || true
    invited=0
  fi
  local wall=$(( $(date +%s) - start ))
  if [[ -f "$DIR/run.status" ]] && grep -q '^incomplete' "$DIR/run.status"; then
    echo "=== end $(date -Iseconds) rc=$rc wall_s=$wall (status: $(cat "$DIR/run.status")) ==="
  else
    echo "done rc=$rc wall_s=$wall end=$(date -Iseconds)" > "$DIR/run.status"
    echo "=== end $(date -Iseconds) rc=$rc wall_s=$wall ==="
  fi
}
trap on_exit EXIT

# 1. Clean worktree and expected HEAD checks
[[ "$(git rev-parse HEAD)" == "$EXPECT_HEAD" ]] || { echo "ERROR: head not $EXPECT_HEAD"; exit 1; }
[[ -z "$(git status --porcelain)" ]] || { echo "ERROR: worktree dirty"; exit 1; }
[[ -z "$(git ls-files -v | grep -E '^[hSs]' || true)" ]] || { echo "ERROR: worktree contains skip-worktree or assume-unchanged files"; exit 1; }
[[ -f "$PREREG_FILE" ]] || { echo "ERROR: prereg file does not exist: $PREREG_FILE"; exit 1; }
[[ -s "$PREREG_FILE" ]] || { echo "ERROR: prereg file is empty: $PREREG_FILE"; exit 1; }
[[ "$(git hash-object "$PREREG_FILE")" == "$(git rev-parse "HEAD:$PREREG_FILE")" ]] || { echo "ERROR: $PREREG_FILE does not match HEAD"; exit 1; }

# 2. Pre-registered bar guard: verifies file is tracked, clean, committed, and reachable from pushed remote ref
bash scripts/prereg-guard.sh --head "$PREREG_FILE" "$REMOTE_REF"

# 3. Memory preflight check before model load (passes QWEN_MODEL_PATH so preflight checks model size + 16 GiB KV/buffer margin covering --ctx 65536 --np 1)
preflight() {
  if ! command -v bwrap >/dev/null 2>&1; then
    echo "ERROR: bwrap (bubblewrap) is required for task selftest sandboxes (#6, #13, #16) but is not installed"
    return 1
  fi
  local out rc
  set +e
  out=$(bash scripts/preflight.sh "$QWEN_MODEL_PATH" 2>&1)
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

# 4. Check served properties (1 slot x 65536 per slot)
check_props() {
  local out
  out=$(curl -s http://127.0.0.1:8081/props | python3 -c "import json,sys;p=json.load(sys.stdin);print('total_slots',p.get('total_slots'),'n_ctx',(p.get('default_generation_settings') or {}).get('n_ctx'),'build',p.get('build_info'))")
  echo "props: $out"
  if [[ "$out" != "total_slots 1 n_ctx 65536 "* ]]; then
    echo "ERROR: served shape is not 1 slot x 65536: $out"
    return 1
  fi
}

# 5. Start served model session
echo "=== Inviting qwen with ${INVITE_OPTS[*]} ==="
scripts/llmctl.py invite qwen "${INVITE_OPTS[@]}"
invited=1
check_props

# 6. Run the 7 PR tasks through the feedback loop
TASKS=(
  "item6_pr06"
  "item6_pr08"
  "item6_pr13"
  "item6_pr14"
  "item6_pr15"
  "item6_pr16"
  "item6_pr20"
)

RESULTS_FILE="bench/loop/results/${LABEL}.jsonl"
if [[ "$RESUME" == "1" ]]; then
  echo "=== Resume mode active (RESUME=1): inspecting $RESULTS_FILE ==="
  if [[ -f "$RESULTS_FILE" ]]; then
    filtered_tasks=()
    for task_id in "${TASKS[@]}"; do
      if grep -q "\"task_id\": \"$task_id\"" "$RESULTS_FILE" 2>/dev/null; then
        echo "RESUME: skipping already completed task $task_id"
      else
        echo "RESUME: queuing missing task $task_id"
        filtered_tasks+=("$task_id")
      fi
    done
    TASKS=("${filtered_tasks[@]}")
  fi
  echo "=== Tasks to execute: ${TASKS[*]:-(none)} ==="
fi

export PYTHONUNBUFFERED=1
gpu_start=$(date +%s)
for task_id in "${TASKS[@]}"; do
  elapsed=$(( $(date +%s) - gpu_start ))
  remaining=$(( CEILING_SECONDS - elapsed ))
  if [[ $remaining -le 0 ]]; then
    echo "incomplete ceiling_exceeded wall_s=$elapsed ceiling_s=$CEILING_SECONDS end=$(date -Iseconds)" > "$DIR/run.status"
    echo "ERROR: GPU run exceeded the 1.2 h ceiling (${CEILING_SECONDS}s) before task $task_id; stopping and recording incomplete run."
    exit 124
  fi
  echo "=== Starting task $task_id $(date -Iseconds) (remaining_ceiling=${remaining}s) ==="
  t0=$(date +%s.%N)
  echo "STEP_START ${LABEL} $task_id $(date -u +%FT%TZ) $t0"
  
  set +e
  timeout --kill-after=30 "$remaining" scripts/llmctl.py run -- python3 bench/loop/pilot_pr.py run --label "$LABEL" --tasks "$task_id" --slot-ctx "$SLOT_CTX" --task-wall-budget "$TASK_WALL_BUDGET" --resume
  step_rc=$?
  set -e
  if [[ $step_rc -eq 124 || $step_rc -eq 137 ]]; then
    elapsed=$(( $(date +%s) - gpu_start ))
    echo "incomplete ceiling_exceeded task=$task_id wall_s=$elapsed ceiling_s=$CEILING_SECONDS end=$(date -Iseconds)" > "$DIR/run.status"
    echo "ERROR: GPU run hit the 1.2 h ceiling (${CEILING_SECONDS}s) during task $task_id (rc=$step_rc); stopping and recording incomplete run."
    exit 124
  elif [[ $step_rc -ne 0 ]]; then
    echo "ERROR: task $task_id exited with rc=$step_rc (continuing to next task)"
  fi
  
  t1=$(date +%s.%N)
  echo "STEP_END ${LABEL} $task_id $(date -u +%FT%TZ) $t1"
  python3 -c "print('STEP_WALL ${LABEL} $task_id %.1f s' % ($t1-$t0))"
  echo "=== Completed task $task_id $(date -Iseconds) ==="
done

# 7. End model session
scripts/llmctl.py bye
invited=0

# 8. Offline grading and evaluation against reference diffs
echo "=== Offline grading and report $(date -Iseconds) ==="
python3 bench/loop/pilot_pr.py grade --label "$LABEL"
echo "=== Item 6 pilot (${LABEL}) completed $(date -Iseconds) ==="
