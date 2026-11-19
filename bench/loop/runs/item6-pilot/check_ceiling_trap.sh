#!/usr/bin/env bash
# Item 2 verification: check that bench/loop/runs/item6-pilot/run.sh EXIT trap
# preserves "incomplete ceiling_exceeded" status and does not overwrite it with "done rc=124".
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_SH="$HERE/run.sh"
[[ -f "$RUN_SH" ]] || { echo "ERROR: run.sh not found at $RUN_SH" >&2; exit 1; }

TEST_DIR="$(mktemp -d /tmp/check_ceiling_trap_XXXXXX)"
cleanup() {
  rm -rf "$TEST_DIR"
}
trap cleanup EXIT

# 1. Verify that run.sh on_exit function contains the check for incomplete status
grep -q "grep -q '\^incomplete' \"\$DIR/run.status\"" "$RUN_SH" || {
  echo "ERROR: run.sh does not check for '^incomplete' in on_exit trap" >&2
  exit 1
}

# 2. Extract on_exit definition directly from run.sh and run under bash
TRAP_FUNC="$(sed -n '/^on_exit() {/,/^}/p' "$RUN_SH")"

cat << EOF > "$TEST_DIR/test_runner.sh"
#!/usr/bin/env bash
DIR="\$1"
start=\$(date +%s)
invited=0
$TRAP_FUNC
trap on_exit EXIT

echo "running \$(date -Iseconds)" > "\$DIR/run.status"
if [[ "\$2" == "ceiling" ]]; then
  echo "incomplete ceiling_exceeded wall_s=4321 ceiling_s=4320 end=\$(date -Iseconds)" > "\$DIR/run.status"
  exit 124
else
  exit 0
fi
EOF
chmod +x "$TEST_DIR/test_runner.sh"

# Test ceiling abort: status must remain incomplete ceiling_exceeded
set +e
"$TEST_DIR/test_runner.sh" "$TEST_DIR" ceiling >/dev/null 2>&1
rc=$?
set -e
[[ $rc -eq 124 ]] || { echo "ERROR: expected exit 124 on ceiling abort, got $rc" >&2; exit 1; }
status_ceiling="$(cat "$TEST_DIR/run.status")"
echo "Ceiling test status output: $status_ceiling"
[[ "$status_ceiling" == "incomplete ceiling_exceeded"* ]] || {
  echo "ERROR: EXIT trap overwrote incomplete ceiling status: $status_ceiling" >&2
  exit 1
}
[[ "$status_ceiling" != *"done rc=124"* ]] || {
  echo "ERROR: status contains 'done rc=124'" >&2
  exit 1
}

# Test normal exit: status must be done rc=0
"$TEST_DIR/test_runner.sh" "$TEST_DIR" normal >/dev/null 2>&1
status_normal="$(cat "$TEST_DIR/run.status")"
echo "Normal test status output: $status_normal"
[[ "$status_normal" == "done rc=0"* ]] || {
  echo "ERROR: expected 'done rc=0', got: $status_normal" >&2
  exit 1
}

echo "OK: run.sh EXIT trap preserves 'incomplete ceiling_exceeded' status on ceiling abort (Item 2 check passed)"
