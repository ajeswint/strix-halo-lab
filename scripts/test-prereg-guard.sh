#!/usr/bin/env bash
# scripts/test-prereg-guard.sh
#
# Tests scripts/prereg-guard.sh against a temporary git repository with a temporary bare remote.
# Exercises both pass and fail cases.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GUARD_SCRIPT="$SCRIPT_DIR/prereg-guard.sh"

if [[ ! -f "$GUARD_SCRIPT" ]]; then
  echo "ERROR: guard script not found at $GUARD_SCRIPT" >&2
  exit 1
fi

TMP_DIR="$(mktemp -d /tmp/test-prereg-guard.XXXXXX)"
cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

BARE_REMOTE="$TMP_DIR/remote.git"
WORK_DIR="$TMP_DIR/work"
OUTSIDE_FILE="$TMP_DIR/outside-prereg.md"

echo "=== Setting up test repos in $TMP_DIR ==="

# Initialize bare remote with default branch main
git init --bare --initial-branch=main "$BARE_REMOTE" >/dev/null 2>&1 || git init --bare "$BARE_REMOTE" >/dev/null 2>&1

# Initialize working clone
git clone "$BARE_REMOTE" "$WORK_DIR" >/dev/null 2>&1
cd "$WORK_DIR"
git config user.name "Test Runner"
git config user.email "test@example.com"
git config init.defaultBranch main

# Create initial commit on main
echo "# Initial" > README.md
git add README.md
git commit -m "initial commit" >/dev/null
git branch -M main
git push -u origin main >/dev/null 2>&1

echo "initial remote commit: $(git rev-parse HEAD)"

# Helper assertion function
assert_fails() {
  local desc="$1"
  local expected_err="$2"
  shift 2
  local out rc=0
  set +e
  out="$("$@" 2>&1)"
  rc=$?
  set -e
  if [[ $rc -eq 0 ]]; then
    echo "FAIL [expected error, got exit 0]: $desc"
    echo "Output was: $out"
    exit 1
  fi
  if [[ -n "$expected_err" && "$out" != *"$expected_err"* ]]; then
    echo "FAIL [expected error message containing '$expected_err']: $desc"
    echo "Actual output was: $out"
    exit 1
  fi
  echo "PASS: $desc (failed as expected with: $expected_err)"
}

assert_passes() {
  local desc="$1"
  local expected_sha="$2"
  local expected_ref="$3"
  shift 3
  local out rc=0
  set +e
  out="$("$@" 2>&1)"
  rc=$?
  set -e
  if [[ $rc -ne 0 ]]; then
    echo "FAIL [expected exit 0, got $rc]: $desc"
    echo "Output was: $out"
    exit 1
  fi
  if [[ -n "$expected_sha" && "$out" != *"$expected_sha"* ]]; then
    echo "FAIL [output missing expected sha '$expected_sha']: $desc"
    echo "Actual output was: $out"
    exit 1
  fi
  if [[ -n "$expected_ref" && "$out" != *"$expected_ref"* ]]; then
    echo "FAIL [output missing expected ref '$expected_ref']: $desc"
    echo "Actual output was: $out"
    exit 1
  fi
  echo "PASS: $desc (exit 0, matched sha and ref)"
}

echo ""
echo "=== Running Fail Cases ==="

# 1. Missing argument
assert_fails "Missing argument" "missing prereg path" \
  bash "$GUARD_SCRIPT"

# 2. Non-existent file
assert_fails "Non-existent file" "does not exist" \
  bash "$GUARD_SCRIPT" "does_not_exist.md"

# 3. File outside git repo
echo "outside" > "$OUTSIDE_FILE"
assert_fails "File outside repository" "outside the git repository" \
  bash "$GUARD_SCRIPT" "$OUTSIDE_FILE"

# 4. Untracked file inside repo
mkdir -p bench/loop/runs/test-run
echo "bar" > bench/loop/runs/test-run/prereg.md
assert_fails "Untracked file" "not tracked by git" \
  bash "$GUARD_SCRIPT" bench/loop/runs/test-run/prereg.md

# 5. Staged but uncommitted changes
git add bench/loop/runs/test-run/prereg.md
assert_fails "Staged but uncommitted file" "has uncommitted changes" \
  bash "$GUARD_SCRIPT" bench/loop/runs/test-run/prereg.md

# Commit the file locally (not pushed)
git commit -m "add prereg locally" >/dev/null
LOCAL_PREREG_SHA="$(git log -n 1 --format=%H -- bench/loop/runs/test-run/prereg.md)"

# 6. Committed locally but uncommitted worktree modification
echo "modified in worktree" >> bench/loop/runs/test-run/prereg.md
assert_fails "Worktree modified file" "has uncommitted changes" \
  bash "$GUARD_SCRIPT" bench/loop/runs/test-run/prereg.md
git checkout -- bench/loop/runs/test-run/prereg.md

# 7. Committed locally but NOT pushed to remote
assert_fails "Committed locally but not pushed" "is not reachable from pushed remote branch" \
  bash "$GUARD_SCRIPT" bench/loop/runs/test-run/prereg.md

# 8. Not reachable from specified remote ref
git checkout -b feature/test-branch >/dev/null 2>&1
git push -u origin feature/test-branch >/dev/null 2>&1
# On feature/test-branch it is pushed, but origin/main does not have it yet!
assert_fails "Not reachable from explicit origin/main" "is not reachable from remote ref origin/main" \
  bash "$GUARD_SCRIPT" bench/loop/runs/test-run/prereg.md origin/main

echo ""
echo "=== Running Pass Cases ==="

# 9. Pushed to origin/feature/test-branch (auto-detected via branch/upstream)
assert_passes "Reachable from current pushed branch" \
  "$LOCAL_PREREG_SHA" "origin/feature/test-branch" \
  bash "$GUARD_SCRIPT" bench/loop/runs/test-run/prereg.md

# 10. Explicit remote ref passed
assert_passes "Reachable with explicit remote ref" \
  "$LOCAL_PREREG_SHA" "origin/feature/test-branch" \
  bash "$GUARD_SCRIPT" bench/loop/runs/test-run/prereg.md origin/feature/test-branch

# 11. Merged and pushed to origin/main
git checkout main >/dev/null 2>&1
git merge --ff-only feature/test-branch >/dev/null 2>&1
git push origin main >/dev/null 2>&1
assert_passes "Reachable from origin/main after push" \
  "$LOCAL_PREREG_SHA" "origin/main" \
  bash "$GUARD_SCRIPT" bench/loop/runs/test-run/prereg.md

# 12. Direct execution via chmod +x
assert_passes "Direct execution of script" \
  "$LOCAL_PREREG_SHA" "origin/main" \
  "$GUARD_SCRIPT" bench/loop/runs/test-run/prereg.md

# 13. Sourced shell function
SOURCED_OUT="$(bash -c "source '$GUARD_SCRIPT' && check_prereg bench/loop/runs/test-run/prereg.md")"
if [[ "$SOURCED_OUT" != *"$LOCAL_PREREG_SHA"* || "$SOURCED_OUT" != *"origin/main"* ]]; then
  echo "FAIL: Sourced function check_prereg did not return expected output"
  echo "Output was: $SOURCED_OUT"
  exit 1
fi
echo "PASS: Sourced shell function check_prereg succeeded"

# 14. --head flag when HEAD matches file commit
assert_passes "Check with --head flag" \
  "$LOCAL_PREREG_SHA" "origin/main" \
  bash "$GUARD_SCRIPT" --head bench/loop/runs/test-run/prereg.md

echo ""
echo "=== ALL 14 TESTS PASSED ==="
