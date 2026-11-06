#!/usr/bin/env bash
# Launch the two standing seats as sequential one-shots (docs/review-roles.md is canonical for
# roster and format):
#   writer    Google Antigravity CLI `agy -p`, model Gemini 4 Argon, effort high (AJ, 2026-11-05 CT)
#   reviewer  Claude Code `claude -p --agent adversarial-reviewer`, Sonnet, effort high (unchanged)
# Ryzen Max Bot (the Grok bot on this MAX) calls this; it only launches and relays and
# writes no product code.
#
# Usage: tools/lab-seats/launch.sh [--dry-run] [--name NAME] (--task TEXT | --task-file FILE)
#
# Scratch: ${LAB_SEATS_ROOT:-/tmp/lab-seats}/NAME/ (NAME defaults to a timestamp)
#   TASK.md  task text as given         writer-prompt.txt / reviewer-prompt.txt  stdin of each one-shot
#   run.sh   the generated wrapper      writer-out.md / reviewer-out.md  stdout (Detail / Relay / Outline)
#   writer.log / reviewer.log  stderr   verdict.txt  first line of the reviewer output, via verdict.py
#   run.pid  pid of the detached wrapper; run.status written last (done | writer-failed | reviewer-failed)
# writer-out.md is agy's stdout; its stderr (soft-deny notices, AGY_ERROR lines) goes to writer.log.
# --dry-run writes everything above except the outputs, prints run.sh, and starts nothing.
# Without it, run.sh is started detached (nohup) and this script returns at once.
#
# Caps (set in the environment of this script; baked into run.sh at launch time):
#   LAB_SEATS_TIMEOUT   wall-clock seconds per one-shot, default 3600 (unmeasured default; timeout(1);
#                       rc 124 -> *-failed rc=124, rc 137 if it needed --kill-after=30's SIGKILL)
#   LAB_SEATS_MAX_USD   optional; adds --max-budget-usd N to the REVIEWER one-shot only (claude, print mode).
#                       `agy --help` (1.5.1) has no budget flag, so the writer has no spend cap. Unset = none.
#   LAB_SEATS_WRITER_MODEL  agy model slug, default gemini-4-argon. UNCONFIRMED: `agy models` needs a sign-in and
#                       the slug has not been read from it yet. A wrong slug fails the writer non-zero with no
#                       silent fallback (https://antigravity.google/docs/cli/headless).
# --max-turns is documented upstream for claude (print mode only; https://code.claude.com/docs/en/cli-reference)
# but not shown in 2.1.317 `claude --help`; not wired, untested. agy has no equivalent flag.
#
# Writer posture: --dangerously-skip-permissions. In headless mode agy has no prompt: without an allow rule a tool
# call is soft-denied, the run exits 0 and the writer could not edit or commit (https://antigravity.google/docs/cli/headless).
# The flag matches the old claude bypassPermissions posture for approval, but it is weaker on enforcement: agy has
# no per-agent tool list here and the gpu-guard PreToolUse hook (Claude hook format) does not wrap agy. See
# docs/antigravity-writer.md.
#
# The one-shots load no model. They run no privileged commands; host actions stay with AJ.
set -euo pipefail

here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
repo=$(cd "$here/../.." && pwd)
root=${LAB_SEATS_ROOT:-/tmp/lab-seats}

dry=0 name="" task="" task_file=""
usage() { sed -n '2,/^set -euo/p' "$0" | sed '$d' | sed 's/^# \{0,1\}//' >&2; exit 2; }
while [ $# -gt 0 ]; do
    case $1 in
        --dry-run) dry=1; shift ;;
        --name) [ $# -ge 2 ] || usage; name=$2; shift 2 ;;
        --task) [ $# -ge 2 ] || usage; task=$2; shift 2 ;;
        --task-file) [ $# -ge 2 ] || usage; task_file=$2; shift 2 ;;
        -h|--help) usage ;;
        *) echo "launch.sh: unknown argument: $1" >&2; usage ;;
    esac
done

if [ -n "$task_file" ]; then
    [ -r "$task_file" ] || { echo "launch.sh: cannot read $task_file" >&2; exit 2; }
    task=$(cat "$task_file")
fi
[ -n "$task" ] || { echo "launch.sh: --task or --task-file is required" >&2; usage; }

[ -n "$name" ] || name=$(date +%Y%m%d-%H%M%S)
case $name in
    ''|*[!A-Za-z0-9._-]*|.|..) echo "launch.sh: --name must match [A-Za-z0-9._-]+" >&2; exit 2 ;;
esac

tmo=${LAB_SEATS_TIMEOUT:-3600}
case $tmo in
    ''|*[!0-9]*|0) echo "launch.sh: LAB_SEATS_TIMEOUT must be a positive integer (seconds)" >&2; exit 2 ;;
esac
budget=""
if [ -n "${LAB_SEATS_MAX_USD:-}" ]; then
    case $LAB_SEATS_MAX_USD in
        *[!0-9.]*|.|*.*.*) echo "launch.sh: LAB_SEATS_MAX_USD must be a number (e.g. 5 or 2.50)" >&2; exit 2 ;;
    esac
    budget=" --max-budget-usd $LAB_SEATS_MAX_USD"
fi

wmodel=${LAB_SEATS_WRITER_MODEL:-gemini-4-argon}
case $wmodel in
    ''|*[!A-Za-z0-9._-]*) echo "launch.sh: LAB_SEATS_WRITER_MODEL must match [A-Za-z0-9._-]+" >&2; exit 2 ;;
esac

if [ "$dry" -eq 0 ]; then
    command -v agy >/dev/null 2>&1 || { echo "launch.sh: agy not on PATH (~/.local/bin?)" >&2; exit 1; }
    command -v claude >/dev/null 2>&1 || { echo "launch.sh: claude not on PATH (~/.local/bin?)" >&2; exit 1; }
fi

dir=$root/$name
if [ -e "$dir/run.sh" ]; then
    echo "launch.sh: $dir already has a run; pick another --name" >&2
    exit 1
fi
mkdir -p "$dir"

printf '%s\n' "$task" > "$dir/TASK.md"

# Writer prompt: the task, then the standing format. Reviewer prompt: what to check and where.
# agy -p takes the prompt as an argument (stdin is for --input-format stream-json only), so the
# writer prompt rides on the command line; Linux caps one argument at 128 KiB, hence the size check.
{
    printf 'You are the code-writer seat for strix-halo-lab (Google Antigravity, Gemini 4 Argon, effort high).\n'
    printf 'Repo: %s. Read README.md, CLAUDE.md, docs/review-roles.md and docs/antigravity-writer.md first.\n' "$repo"
    printf 'Do the task below. Do not review your own work. Reply with Detail, then Relay, then Outline;\n'
    printf 'your Relay is for the adversarial-reviewer. Put any PR URL in Relay.\n\n'
    printf '# TASK\n\n'
    cat "$dir/TASK.md"
} > "$dir/writer-prompt.txt"
wbytes=$(wc -c < "$dir/writer-prompt.txt")
if [ "$wbytes" -gt 100000 ]; then
    echo "launch.sh: writer prompt is $wbytes bytes (> 100000): agy -p takes it as one argument; shorten the task or point it at a file in the repo" >&2
    exit 2
fi

{
    printf 'You are the adversarial-reviewer seat for strix-halo-lab (Sonnet, effort high).\n'
    printf 'Repo: %s. Read CLAUDE.md and docs/review-roles.md first. Review only; do not edit.\n' "$repo"
    printf 'The task given to the writer is in %s/TASK.md.\n' "$dir"
    printf "The writer's reply is in %s/writer-out.md. Treat its claims as claims: check them against\n" "$dir"
    printf 'HEAD, `git status` and `git diff` in the repo, and say so where you could not.\n'
    printf 'First line of your reply is exactly APPROVE, APPROVE-WITH-NITS or REQUEST-CHANGES.\n'
    printf 'Then Detail, then Relay (for the code-writer), then Outline.\n'
} > "$dir/reviewer-prompt.txt"

# The wrapper. Unquoted heredoc: $dir and $repo are fixed now; \$ stays literal for run time.
cat > "$dir/run.sh" <<EOF
#!/usr/bin/env bash
# Generated by tools/lab-seats/launch.sh. Sequential one-shots, each under timeout $tmo s; the reviewer runs only if the writer exited 0 with output.
set -u
cd "$repo" || exit 1
echo \$\$ > "$dir/run.pid"

timeout --kill-after=30 $tmo agy -p "\$(cat "$dir/writer-prompt.txt")" --model $wmodel --effort high --dangerously-skip-permissions < /dev/null > "$dir/writer-out.md" 2> "$dir/writer.log"
rc=\$?
if [ "\$rc" -ne 0 ]; then
    echo "writer-failed rc=\$rc" > "$dir/run.status"
    exit "\$rc"
fi
if [ ! -s "$dir/writer-out.md" ]; then
    echo "writer-failed rc=0 (empty output; see writer.log)" > "$dir/run.status"
    exit 1
fi

timeout --kill-after=30 $tmo claude -p --model sonnet --effort high --permission-mode bypassPermissions --agent adversarial-reviewer$budget < "$dir/reviewer-prompt.txt" > "$dir/reviewer-out.md" 2> "$dir/reviewer.log"
rc=\$?
if [ "\$rc" -ne 0 ]; then
    echo "reviewer-failed rc=\$rc" > "$dir/run.status"
    exit "\$rc"
fi

python3 -I "$here/verdict.py" "$dir/reviewer-out.md" > "$dir/verdict.txt" 2>&1
echo "done verdict=\$(head -n1 "$dir/verdict.txt")" > "$dir/run.status"
EOF
chmod +x "$dir/run.sh"

if [ "$dry" -eq 1 ]; then
    echo "launch.sh: dry run, scratch at $dir, nothing started"
    echo "---- $dir/run.sh"
    cat "$dir/run.sh"
    exit 0
fi

nohup bash "$dir/run.sh" > "$dir/launcher.log" 2>&1 < /dev/null &
echo "launch.sh: started pid $! ; scratch at $dir ; status in $dir/run.status"
