#!/usr/bin/env bash
# Roadmap Item 6 Pilot v3 — Step 2: Unseen External-Repo PR Test Launcher
#
# Evaluates 7 unseen merged PRs from `more-itertools/more-itertools` (post-2026-04-15
# Qwen3.6-35B-A3B release, mechanically selected by bench/loop/select_v3.py) using
# the standing single-Qwen3.6-35B-A3B agentic loop with tool-output compaction
# (bench/loop/pilot_pr.py). NO DeepSeek arm.
#
# Prerequisite: Step 1 practice run (bench/loop/runs/item6-v3-practice/run.sh)
# must complete with its result note recorded and compaction settings frozen in
# docs/item6-pilot.md, committed AND pushed to REMOTE_REF before launch.
#
# Safety invariants:
# - Preflight requires llama-deepseek=inactive and READY.
# - Never touch /data/ring-memloop-v9 or any seal.key.
# - Clean worktree, expected HEAD, prereg-guard, and pinned external bare repo
#   verified before any GPU activity.
set -euo pipefail

WT="${WT:-<path-to-clean-worktree>}"
LABEL="${LABEL:-item6-pilot-v3}"
DIR="${DIR:-/tmp/lab-seats/${LABEL}}"
LOG="$DIR/run.log"
EXPECT_HEAD="${EXPECT_HEAD:-<expected-git-commit-sha>}"
PREREG_FILE="docs/item6-pilot.md"
REMOTE_REF="${REMOTE_REF:-origin/main}"
TARGET_REPO="${TARGET_REPO:-/data/datasets/item6-v3-repos/more-itertools.git}"
V3_PINNED_HEAD="e3f79f4fde5f7c107f70a20730b17240a05ba99b"
QWEN_MODEL_PATH="/data/models/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf"
INVITE_OPTS=(--ctx 65536 --np 1)
SLOT_CTX=65536
CEILING_SECONDS="${CEILING_SECONDS:-4320}" # 1.2 GPU-hours (4320 s) hard ceiling
TASK_WALL_BUDGET="${TASK_WALL_BUDGET:-617}" # floor(4320/7) = 617 s per task
RESUME="${RESUME:-0}"

# Refuse to overwrite frozen v1, frozen v2, or practice results
if [[ "$LABEL" == "item6-pilot" || "$LABEL" == "item6-pilot-v2" || "$LABEL" == "item6-v3-practice" ]]; then
  echo "ERROR: v3 launcher refuses frozen/practice label '$LABEL'; use LABEL=item6-pilot-v3" >&2
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
echo $$ > "$DIR/run.pid"

exec >>"$LOG" 2>&1

start=$(date +%s)
echo "running $(date -Iseconds)" > "$DIR/run.status"
echo "=== start v3 unseen pilot $(date -Iseconds) pwd=$PWD head=$(git rev-parse HEAD) target_repo=$TARGET_REPO ceiling_seconds=$CEILING_SECONDS resume=$RESUME ==="

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

# 1. Clean worktree, expected HEAD, and external bare repo pin checks
[[ "$(git rev-parse HEAD)" == "$EXPECT_HEAD" ]] || { echo "ERROR: head not $EXPECT_HEAD"; exit 1; }
[[ -z "$(git status --porcelain)" ]] || { echo "ERROR: worktree dirty"; exit 1; }
[[ -z "$(git ls-files -v | grep -E '^[hSs]' || true)" ]] || { echo "ERROR: worktree contains skip-worktree or assume-unchanged files"; exit 1; }
[[ -f "$PREREG_FILE" ]] || { echo "ERROR: prereg file does not exist: $PREREG_FILE"; exit 1; }
[[ -s "$PREREG_FILE" ]] || { echo "ERROR: prereg file is empty: $PREREG_FILE"; exit 1; }
[[ "$(git hash-object "$PREREG_FILE")" == "$(git rev-parse "HEAD:$PREREG_FILE")" ]] || { echo "ERROR: $PREREG_FILE does not match HEAD"; exit 1; }
[[ -d "$TARGET_REPO" ]] || { echo "ERROR: external bare repo not found: $TARGET_REPO"; exit 1; }
git -C "$TARGET_REPO" cat-file -e "${V3_PINNED_HEAD}^{commit}" || { echo "ERROR: pinned commit $V3_PINNED_HEAD missing in $TARGET_REPO"; exit 1; }

# 2. Pre-registered bar guard: verifies file is tracked, clean, committed, and reachable from pushed remote ref
bash scripts/prereg-guard.sh --head "$PREREG_FILE" "$REMOTE_REF"

# 3. Memory preflight check before model load
preflight() {
  if ! command -v bwrap >/dev/null 2>&1; then
    echo "ERROR: bwrap (bubblewrap) is required for task sandboxes but is not installed"
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

# 6. Run the 7 unseen external PR tasks through the feedback loop
ALL_TASKS=(
  "item6v3_pr1260"
  "item6v3_pr1269"
  "item6v3_pr1305"
  "item6v3_pr1322"
  "item6v3_pr1342"
  "item6v3_pr1345"
  "item6v3_pr1311"
)
TASKS=("${ALL_TASKS[@]}")

check_results_complete() {
  local results_file="$1"
  shift
  python3 - "$results_file" "$@" <<'PY'
import json, os, sys
results_file = sys.argv[1]
expected = sys.argv[2:]
present = set()
if os.path.exists(results_file):
    with open(results_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
                tid = row.get("task_id")
                if tid:
                    present.add(tid)
            except json.JSONDecodeError:
                pass
missing = [tid for tid in expected if tid not in present]
if missing:
    print(",".join(missing))
    sys.exit(1)
PY
}

RESULTS_FILE="bench/loop/results/${LABEL}.jsonl"
if [[ "$RESUME" == "1" ]]; then
  echo "=== Resume mode active (RESUME=1): inspecting $RESULTS_FILE ==="
  if [[ -f "$RESULTS_FILE" ]]; then
    filtered_tasks=()
    for task_id in "${ALL_TASKS[@]}"; do
      if check_results_complete "$RESULTS_FILE" "$task_id" >/dev/null 2>&1; then
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
if [[ ${#TASKS[@]} -gt 0 ]]; then
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
    timeout --kill-after=30 "$remaining" scripts/llmctl.py run -- python3 bench/loop/pilot_pr.py run \
      --label "$LABEL" --task-suite v3 --target-repo "$TARGET_REPO" \
      --tasks "$task_id" --slot-ctx "$SLOT_CTX" --task-wall-budget "$TASK_WALL_BUDGET" \
      --run-dir "$DIR" --resume
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
fi

# 7. End model session
scripts/llmctl.py bye
invited=0

# 8. Completeness check
set +e
missing_ids=$(check_results_complete "$RESULTS_FILE" "${ALL_TASKS[@]}")
complete_rc=$?
set -e
if [[ $complete_rc -ne 0 ]]; then
  wall_now=$(( $(date +%s) - start ))
  echo "incomplete missing=${missing_ids} wall_s=${wall_now} end=$(date -Iseconds)" > "$DIR/run.status"
  echo "ERROR: results file $RESULTS_FILE is missing expected task ids: ${missing_ids}"
  exit 1
fi

# 9. Offline grading against authoritative merged-commit tests (read-only bwrap mount)
echo "=== Offline grading and report $(date -Iseconds) ==="
python3 bench/loop/pilot_pr.py grade --label "$LABEL" --task-suite v3 --target-repo "$TARGET_REPO"
echo "=== Item 6 pilot v3 (${LABEL}) completed $(date -Iseconds) ==="
