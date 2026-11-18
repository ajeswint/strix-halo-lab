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
DIR="${DIR:-/tmp/lab-seats/item6-pilot}"
LOG="$DIR/run.log"
EXPECT_HEAD="${EXPECT_HEAD:-<expected-git-commit-sha>}"
PREREG_FILE="docs/item6-pilot.md"
REMOTE_REF="${REMOTE_REF:-origin/main}"
QWEN_MODEL_PATH="/data/models/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf"
INVITE_OPTS=(--ctx 65536 --np 2)
PARALLEL=2

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
[[ -z "$(git ls-files -v | grep -E '^[hSs]' || true)" ]] || { echo "ERROR: worktree contains skip-worktree or assume-unchanged files"; exit 1; }
[[ -f "$PREREG_FILE" ]] || { echo "ERROR: prereg file does not exist: $PREREG_FILE"; exit 1; }
[[ -s "$PREREG_FILE" ]] || { echo "ERROR: prereg file is empty: $PREREG_FILE"; exit 1; }
[[ "$(git hash-object "$PREREG_FILE")" == "$(git rev-parse "HEAD:$PREREG_FILE")" ]] || { echo "ERROR: $PREREG_FILE does not match HEAD"; exit 1; }

# 2. Pre-registered bar guard: verifies file is tracked, clean, committed, and reachable from pushed remote ref
bash scripts/prereg-guard.sh --head "$PREREG_FILE" "$REMOTE_REF"

# 3. Memory preflight check before model load (passes QWEN_MODEL_PATH so preflight checks model size + 16 GiB KV/buffer margin covering --ctx 65536 --np 2)
preflight() {
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

# 4. Check served properties (2 slots x 32768 per slot)
check_props() {
  local out
  out=$(curl -s http://127.0.0.1:8081/props | python3 -c "import json,sys;p=json.load(sys.stdin);print('total_slots',p.get('total_slots'),'n_ctx',(p.get('default_generation_settings') or {}).get('n_ctx'),'build',p.get('build_info'))")
  echo "props: $out"
  if [[ "$out" != "total_slots 2 n_ctx 32768 "* ]]; then
    echo "ERROR: served shape is not 2 slots x 32768: $out"
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

export PYTHONUNBUFFERED=1
for task_id in "${TASKS[@]}"; do
  echo "=== Starting task $task_id $(date -Iseconds) ==="
  t0=$(date +%s.%N)
  echo "STEP_START item6-pilot $task_id $(date -u +%FT%TZ) $t0"
  
  scripts/llmctl.py run -- python3 bench/loop/pilot_pr.py run --label item6-pilot --tasks "$task_id"
  
  t1=$(date +%s.%N)
  echo "STEP_END item6-pilot $task_id $(date -u +%FT%TZ) $t1"
  python3 -c "print('STEP_WALL item6-pilot $task_id %.1f s' % ($t1-$t0))"
  echo "=== Completed task $task_id $(date -Iseconds) ==="
done

# 7. End model session
scripts/llmctl.py bye
invited=0

# 8. Offline grading and evaluation against reference diffs
echo "=== Offline grading and report $(date -Iseconds) ==="
python3 bench/loop/pilot_pr.py grade --label item6-pilot
echo "=== Item 6 pilot completed $(date -Iseconds) ==="
