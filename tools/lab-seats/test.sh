#!/usr/bin/env bash
# Dry-run test for tools/lab-seats. Loads no model and never starts the real agy or claude:
# launch.sh runs with --dry-run, and the generated run.sh runs against a fake `agy` (writer)
# and a fake `claude` (reviewer) on PATH. All scratch is under a mktemp dir.
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
for f in docs/review-roles.md docs/antigravity-writer.md AGENTS.md .claude/agents/code-writer.md \
         .claude/agents/adversarial-reviewer.md tools/lab-seats/README.md tools/lab-seats/verdict.py; do
    check "present: $f"                     test -s "$repo/$f"
done
check "reviewer: model sonnet, effort high" bash -c 'grep -q "^model: sonnet$" "$1" && grep -q "^effort: high$" "$1"' _ "$repo/.claude/agents/adversarial-reviewer.md"
# The writer seat is Antigravity, not a Claude agent: the old file must be a stub that cannot launch
# (no YAML frontmatter, no tool list) and must point at the Antigravity doc.
check "code-writer.md is a stub (no frontmatter)" bash -c '[ "$(head -n1 "$1")" != "---" ] && ! grep -q "^tools:" "$1" && grep -q "docs/antigravity-writer.md" "$1"' _ "$repo/.claude/agents/code-writer.md"
check "AGENTS.md names Antigravity writer"  bash -c 'grep -q "Antigravity" "$1" && grep -q "Gemini 4 Argon" "$1"' _ "$repo/AGENTS.md"

# --- dry run: scratch files, flags, nothing started
export LAB_SEATS_ROOT=$tmp/seats
out=$("$launch" --dry-run --name t1 --task "confirm the seats" 2>&1); rc=$?
check "dry-run exits 0"                    test "$rc" -eq 0
d=$LAB_SEATS_ROOT/t1
for f in TASK.md writer-prompt.txt reviewer-prompt.txt run.sh; do
    check "dry-run wrote $f"               test -s "$d/$f"
done
check "dry-run started nothing"            bash -c '[ ! -e "$1/run.pid" ] && [ ! -e "$1/writer-out.md" ]' _ "$d"
w="agy -p \"\$(cat \"$d/writer-prompt.txt\")\" --model gemini-4-argon --effort high --dangerously-skip-permissions < /dev/null"
r="claude -p --model sonnet --effort high --permission-mode bypassPermissions --agent adversarial-reviewer"
check "run.sh writer is agy, flags exact"  grep -qF "$w >" "$d/run.sh"
check "run.sh reviewer flags exact"        grep -qF "$r <" "$d/run.sh"
check "run.sh has no claude code-writer"   bash -c '! grep -qF -e "--agent code-writer" "$1"' _ "$d/run.sh"
check "run.sh writer is not claude"        bash -c '! grep -E "claude -p.*writer-prompt" "$1"' _ "$d/run.sh"
check "writer line before reviewer line"   bash -c '[ "$(grep -n -F -e "agy -p" "$1" | head -n1 | cut -d: -f1)" -lt "$(grep -n -F -e "--agent adversarial-reviewer" "$1" | cut -d: -f1)" ]' _ "$d/run.sh"
check "run.sh has no sudo"                 bash -c '! grep -qiw sudo "$1"' _ "$d/run.sh"
check "run.sh wraps each in timeout 3600" bash -c '[ "$(grep -c -F "timeout --kill-after=30 3600 agy -p" "$1")" -eq 1 ] && [ "$(grep -c -F "timeout --kill-after=30 3600 claude -p" "$1")" -eq 1 ]' _ "$d/run.sh"
check "run.sh no budget flag by default"   bash -c '! grep -qF -e "--max-budget-usd" "$1"' _ "$d/run.sh"
LAB_SEATS_TIMEOUT=90 LAB_SEATS_MAX_USD=2.5 LAB_SEATS_WRITER_MODEL=gemini-x.1 "$launch" --dry-run --name t4 --task x >/dev/null 2>&1
check "caps env baked into run.sh"         bash -c 'grep -qF "timeout --kill-after=30 90 agy" "$1" && grep -qF "timeout --kill-after=30 90 claude" "$1" && grep -qF -e "--model gemini-x.1 --effort high" "$1" && [ "$(grep -c -F -e "--max-budget-usd 2.5 <" "$1")" -eq 1 ] && ! grep -F "agy -p" "$1" | grep -qF -e "--max-budget-usd"' _ "$LAB_SEATS_ROOT/t4/run.sh"
check "bad LAB_SEATS_WRITER_MODEL refused" bash -c '! LAB_SEATS_WRITER_MODEL="a b;c" "$1" --dry-run --name t7 --task x >/dev/null 2>&1' _ "$launch"
check "writer prompt names Antigravity"    bash -c 'grep -q "Google Antigravity" "$1" && grep -q "docs/antigravity-writer.md" "$1"' _ "$d/writer-prompt.txt"
head -c 120000 /dev/zero | tr '\0' x > "$tmp/big.txt"
check "oversize writer prompt refused"     bash -c '! "$1" --dry-run --name t8 --task-file "$2" >/dev/null 2>&1' _ "$launch" "$tmp/big.txt"
check "bad LAB_SEATS_TIMEOUT refused"      bash -c '! LAB_SEATS_TIMEOUT=abc "$1" --dry-run --name t5 --task x >/dev/null 2>&1' _ "$launch"
check "bad LAB_SEATS_MAX_USD refused"      bash -c '! LAB_SEATS_MAX_USD=1e3 "$1" --dry-run --name t6 --task x >/dev/null 2>&1' _ "$launch"
check "run.sh has no --bg"                 bash -c '! grep -qF -e "--bg" "$1"' _ "$d/run.sh"
check "bad --name refused"                 bash -c '! "$1" --dry-run --name "a/b" --task x >/dev/null 2>&1' _ "$launch"
check "missing task refused"               bash -c '! "$1" --dry-run --name t2 >/dev/null 2>&1' _ "$launch"
check "reused --name refused"              bash -c '! "$1" --dry-run --name t1 --task x >/dev/null 2>&1' _ "$launch"

# --- run.sh against a fake agy (writer) and a fake claude (reviewer): sequencing and verdict capture
mkdir -p "$tmp/bin"
cat > "$tmp/bin/agy" <<'EOF'
#!/usr/bin/env bash
# fake agy: the prompt must arrive as the argument after -p; record argv shape, never read stdin
echo "$*" > "${FAKE_AGY_ARGS:-/dev/null}"
[ "$1" = "-p" ] || exit 8
case "$2" in "You are the code-writer seat"*) ;; *) exit 7 ;; esac
[ -n "${FAKE_AGY_RC:-}" ] && exit "$FAKE_AGY_RC"
[ -n "${FAKE_AGY_EMPTY:-}" ] && exit 0
printf '## Detail\nwrote it\n## Relay\nreview this\n## Outline\n- x\n'
EOF
cat > "$tmp/bin/claude" <<'EOF'
#!/usr/bin/env bash
cat >/dev/null
case " $* " in
    *" --agent adversarial-reviewer "*) printf '%s\n\nDetail...\n' "${FAKE_VERDICT:-APPROVE-WITH-NITS}" ;;
    *) exit 9 ;;
esac
EOF
chmod +x "$tmp/bin/agy" "$tmp/bin/claude"
export FAKE_AGY_ARGS=$tmp/agy-args.txt
PATH="$tmp/bin:$PATH" bash "$d/run.sh"
check "fake run: writer got model/effort/skip flags" grep -qF -e "--model gemini-4-argon --effort high --dangerously-skip-permissions" "$FAKE_AGY_ARGS"
check "fake run: writer-out from agy"      grep -q "^## Relay$" "$d/writer-out.md"
check "fake run: status done w/ verdict"   grep -q "^done verdict=APPROVE-WITH-NITS$" "$d/run.status"
check "fake run: verdict.txt"              test "$(cat "$d/verdict.txt")" = "APPROVE-WITH-NITS"
"$launch" --dry-run --name t3 --task x >/dev/null 2>&1
PATH="$tmp/bin:$PATH" FAKE_VERDICT="Looks fine" bash "$LAB_SEATS_ROOT/t3/run.sh"
check "fake run: malformed verdict seen"   grep -q "^done verdict=verdict.py:" "$LAB_SEATS_ROOT/t3/run.status"
# writer failure paths: the reviewer must not run
"$launch" --dry-run --name t9 --task x >/dev/null 2>&1
PATH="$tmp/bin:$PATH" FAKE_AGY_RC=3 bash "$LAB_SEATS_ROOT/t9/run.sh"
check "writer rc 3 -> writer-failed rc=3"  grep -q "^writer-failed rc=3$" "$LAB_SEATS_ROOT/t9/run.status"
check "writer rc 3 -> reviewer not run"    test ! -e "$LAB_SEATS_ROOT/t9/reviewer-out.md"
"$launch" --dry-run --name t10 --task x >/dev/null 2>&1
PATH="$tmp/bin:$PATH" FAKE_AGY_EMPTY=1 bash "$LAB_SEATS_ROOT/t10/run.sh"
check "writer empty output -> writer-failed" grep -q "^writer-failed rc=0 (empty output" "$LAB_SEATS_ROOT/t10/run.status"
check "writer empty -> reviewer not run"   test ! -e "$LAB_SEATS_ROOT/t10/reviewer-out.md"

# --- verdict.py
v() { printf '%b' "$1" | python3 -I "$here/verdict.py" - 2>/dev/null; echo "rc=$?"; }
check "verdict APPROVE"                    test "$(v 'APPROVE\nx')" = "$(printf 'APPROVE\nrc=0')"
check "verdict nits rc 0"                  test "$(v '\n  APPROVE-WITH-NITS  \nx')" = "$(printf 'APPROVE-WITH-NITS\nrc=0')"
check "verdict request-changes rc 1"       test "$(v 'REQUEST-CHANGES\nx')" = "$(printf 'REQUEST-CHANGES\nrc=1')"
check "verdict decorated rejected"         test "$(v '**APPROVE**\nx')" = "rc=2"
check "verdict not-first rejected"         test "$(v 'Review:\nAPPROVE\n')" = "rc=2"
check "verdict empty rejected"             test "$(v '')" = "rc=2"

[ "$fail" -eq 0 ] && echo "ALL OK" || { echo "FAILED"; exit 1; }
