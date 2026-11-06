#!/usr/bin/env bash
# Dry-run test for tools/lab-seats. Loads no model and never starts the real claude:
# launch.sh runs with --dry-run, and the generated run.sh runs once against a fake `claude`
# on PATH. All scratch is under a mktemp dir.
# Usage: bash tools/lab-seats/test.sh
set -u
here=$(cd "$(dirname "$0")" && pwd)
repo=$(cd "$here/../.." && pwd)
launch=$here/launch.sh
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

fail=0
ok()  { echo "ok   $1"; }
bad() { echo "FAIL $1"; fail=1; }
check() { if "${@:2}"; then ok "$1"; else bad "$1"; fi; }

# --- static checks
check "launch.sh is executable"            test -x "$launch"
check "no sudo in launch.sh"               bash -c '! grep -qiw sudo "$1"' _ "$launch"
check "no sudo in verdict.py"              bash -c '! grep -qiw sudo "$1"' _ "$here/verdict.py"
check "no Johnny relay.sh in the repo"     bash -c 'cd "$1" && [ -z "$(git ls-files "*relay.sh" "*fetch-and-score.sh"; find . -path ./.git -prune -o \( -name relay.sh -o -name fetch-and-score.sh \) -print)" ]' _ "$repo"
for f in docs/review-roles.md AGENTS.md .claude/agents/code-writer.md .claude/agents/adversarial-reviewer.md \
         tools/lab-seats/README.md tools/lab-seats/verdict.py; do
    check "present: $f"                     test -s "$repo/$f"
done
for a in code-writer adversarial-reviewer; do
    check "$a: model sonnet, effort high"  bash -c 'grep -q "^model: sonnet$" "$1" && grep -q "^effort: high$" "$1"' _ "$repo/.claude/agents/$a.md"
done

# --- dry run: scratch files, flags, nothing started
export LAB_SEATS_ROOT=$tmp/seats
out=$("$launch" --dry-run --name t1 --task "confirm the seats" 2>&1); rc=$?
check "dry-run exits 0"                    test "$rc" -eq 0
d=$LAB_SEATS_ROOT/t1
for f in TASK.md writer-prompt.txt reviewer-prompt.txt run.sh; do
    check "dry-run wrote $f"               test -s "$d/$f"
done
check "dry-run started nothing"            bash -c '[ ! -e "$1/run.pid" ] && [ ! -e "$1/writer-out.md" ]' _ "$d"
w="claude -p --model sonnet --effort high --permission-mode bypassPermissions --agent code-writer"
r="claude -p --model sonnet --effort high --permission-mode bypassPermissions --agent adversarial-reviewer"
check "run.sh writer flags exact"          grep -qF "$w <" "$d/run.sh"
check "run.sh reviewer flags exact"        grep -qF "$r <" "$d/run.sh"
check "writer line before reviewer line"   bash -c '[ "$(grep -n -F -e "--agent code-writer" "$1" | cut -d: -f1)" -lt "$(grep -n -F -e "--agent adversarial-reviewer" "$1" | cut -d: -f1)" ]' _ "$d/run.sh"
check "run.sh has no sudo"                 bash -c '! grep -qiw sudo "$1"' _ "$d/run.sh"
check "run.sh wraps both in timeout 3600" bash -c '[ "$(grep -c -F "timeout --kill-after=30 3600 claude -p" "$1")" -eq 2 ]' _ "$d/run.sh"
check "run.sh no budget flag by default"   bash -c '! grep -qF -e "--max-budget-usd" "$1"' _ "$d/run.sh"
LAB_SEATS_TIMEOUT=90 LAB_SEATS_MAX_USD=2.5 "$launch" --dry-run --name t4 --task x >/dev/null 2>&1
check "caps env baked into run.sh"         bash -c 'grep -qF "timeout --kill-after=30 90 claude" "$1" && [ "$(grep -c -F -e "--max-budget-usd 2.5 <" "$1")" -eq 2 ]' _ "$LAB_SEATS_ROOT/t4/run.sh"
check "bad LAB_SEATS_TIMEOUT refused"      bash -c '! LAB_SEATS_TIMEOUT=abc "$1" --dry-run --name t5 --task x >/dev/null 2>&1' _ "$launch"
check "bad LAB_SEATS_MAX_USD refused"      bash -c '! LAB_SEATS_MAX_USD=1e3 "$1" --dry-run --name t6 --task x >/dev/null 2>&1' _ "$launch"
check "run.sh has no --bg"                 bash -c '! grep -qF -e "--bg" "$1"' _ "$d/run.sh"
check "bad --name refused"                 bash -c '! "$1" --dry-run --name "a/b" --task x >/dev/null 2>&1' _ "$launch"
check "missing task refused"               bash -c '! "$1" --dry-run --name t2 >/dev/null 2>&1' _ "$launch"
check "reused --name refused"              bash -c '! "$1" --dry-run --name t1 --task x >/dev/null 2>&1' _ "$launch"

# --- run.sh against a fake claude: sequencing and verdict capture
mkdir -p "$tmp/bin"
cat > "$tmp/bin/claude" <<'EOF'
#!/usr/bin/env bash
cat >/dev/null
case " $* " in
    *" --agent code-writer "*) printf '## Detail\nwrote it\n## Relay\nreview this\n## Outline\n- x\n' ;;
    *" --agent adversarial-reviewer "*) printf '%s\n\nDetail...\n' "${FAKE_VERDICT:-APPROVE-WITH-NITS}" ;;
    *) exit 9 ;;
esac
EOF
chmod +x "$tmp/bin/claude"
PATH="$tmp/bin:$PATH" bash "$d/run.sh"
check "fake run: status done w/ verdict"   grep -q "^done verdict=APPROVE-WITH-NITS$" "$d/run.status"
check "fake run: verdict.txt"              test "$(cat "$d/verdict.txt")" = "APPROVE-WITH-NITS"
"$launch" --dry-run --name t3 --task x >/dev/null 2>&1
PATH="$tmp/bin:$PATH" FAKE_VERDICT="Looks fine" bash "$LAB_SEATS_ROOT/t3/run.sh"
check "fake run: malformed verdict seen"   grep -q "^done verdict=verdict.py:" "$LAB_SEATS_ROOT/t3/run.status"

# --- verdict.py
v() { printf '%b' "$1" | python3 -I "$here/verdict.py" - 2>/dev/null; echo "rc=$?"; }
check "verdict APPROVE"                    test "$(v 'APPROVE\nx')" = "$(printf 'APPROVE\nrc=0')"
check "verdict nits rc 0"                  test "$(v '\n  APPROVE-WITH-NITS  \nx')" = "$(printf 'APPROVE-WITH-NITS\nrc=0')"
check "verdict request-changes rc 1"       test "$(v 'REQUEST-CHANGES\nx')" = "$(printf 'REQUEST-CHANGES\nrc=1')"
check "verdict decorated rejected"         test "$(v '**APPROVE**\nx')" = "rc=2"
check "verdict not-first rejected"         test "$(v 'Review:\nAPPROVE\n')" = "rc=2"
check "verdict empty rejected"             test "$(v '')" = "rc=2"

[ "$fail" -eq 0 ] && echo "ALL OK" || { echo "FAILED"; exit 1; }
