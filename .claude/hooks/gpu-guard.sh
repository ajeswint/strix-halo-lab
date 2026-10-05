#!/usr/bin/env bash
# PreToolUse hook on Bash for the trainer, evaluator and systems agents.
# Not on the parent session: a decision recorded in README.md (Claude agents).
# Armed while GTT used is above 16 GiB, i.e. while any model is resident. Then it denies
# commands that can load a model, `systemctl start` of llama-deepseek, and commands that
# would stop that service (CLAUDE.md: ask before stopping it).
# Mechanism of the 2026-10-04 OOM: a second model load beside DeepSeek (~85 GiB GTT).
# The cutoff is GTT, not service state, because DeepSeek also loads outside the service
# (bench/fanpeg-suite.sh, bench.sh), and a resident small model must block DeepSeek too.
# Sizes: idle ~0.5 GiB; Qwen 20.8, Laguna 19.1, DeepSeek 86 GiB peak; GTT total 108 GiB.
# Qwen and Laguna cannot be resident together under this cutoff; revisit when a real run
# needs both.
# Exit 2 blocks the call; any other exit allows it.
set -u

# Real state, not a flag file. Highest card wins; unreadable counts as 0 (no amdgpu,
# nothing on the GPU). The python matcher applies the cutoff, so the matrix can test it.
GUARD_GTT_USED=0
for f in /sys/class/drm/card*/device/mem_info_gtt_used; do
    read -r v < "$f" 2>/dev/null || continue
    [ "$v" -gt "$GUARD_GTT_USED" ] 2>/dev/null && GUARD_GTT_USED=$v
done
export GUARD_GTT_USED

# Hook JSON arrives on stdin; the python script also arrives on stdin, so hand the
# command over via the environment.
GUARD_CMD=$(jq -r '.tool_input.command // empty') || exit 0
export GUARD_CMD

# Split the command into segments on ; && || | & and newlines, then judge each
# segment by its first real token after wrappers. Arguments (cat bench/bench.sh,
# git diff -- x.py) are never matched. bash -c "..." is recursed into.
# Known gaps: $(...) and backticks are not split; a new script name that wraps
# python passes; eval and xargs are not followed; a bare `kill <pid>` with no
# "llama" or pgrep in the segment passes; programs not in WRAPPERS that run a
# command (systemd-run, runuser, su -c, flock, strace) are not followed. This is a tripwire, not a sandbox.
python3 - <<'PY'
import os, re, shlex, sys

# 16 GiB: above idle (~0.5 GiB), below the smallest installed model (Laguna, 19.1 GiB).
GTT_CUTOFF = 16 * 2**30
gtt = int(os.environ.get("GUARD_GTT_USED", "0") or 0)
if gtt <= GTT_CUTOFF:
    sys.exit(0)

cmd = os.environ.get("GUARD_CMD", "")
if not cmd:
    sys.exit(0)

# wrapper -> its flags that take a separate argument (sudo -u aj, nice -n 10, env -u VAR).
# Per wrapper, because sudo -n and nice -n differ: sudo -n takes none, nice -n takes one.
# Long forms must be listed too: `--flag value` is two tokens; `--flag=value` is one and
# needs no entry.
WRAPPERS = {
    "sudo": {"-u", "-g", "-C", "-D", "-h", "-p", "-r", "-t", "-T", "-U",
             "--user", "--group", "--close-from", "--chdir", "--host", "--prompt",
             "--role", "--type", "--command-timeout", "--other-user"},
    "doas": {"-u", "-C"},
    "nohup": set(), "setsid": set(), "command": set(), "unbuffer": set(),
    "time": {"-f", "-o", "--format", "--output"},
    # env here is uutils coreutils 0.10.0 (env --version); -f/--file is uutils-only.
    # --block/default/ignore-signal take an optional =SIG only, so they need no entry.
    "env": {"-u", "-C", "-S", "-a", "-f",
            "--unset", "--chdir", "--split-string", "--argv0", "--file"},
    "nice": {"-n", "--adjustment"},
    "ionice": {"-c", "-n", "-p", "-P", "-u", "--class", "--classdata", "--pid", "--pgid", "--uid"},
    "exec": {"-a"},
    "stdbuf": {"-i", "-o", "-e", "--input", "--output", "--error"},
    "chrt": set(), "taskset": set(),
    # util-linux 2.41.3 (script --help). -t takes an optional attached file only.
    "script": {"-c", "-I", "-O", "-B", "-T", "-m", "-E", "-o",
               "--command", "--log-in", "--log-out", "--log-io", "--log-timing",
               "--logging-format", "--echo", "--output-limit"},
    "timeout": {"-k", "-s", "--kill-after", "--signal"},
}
# wrappers that take a positional before the program (taskset 3 cmd, chrt 10 cmd)
POSITIONAL = {"taskset": 1, "chrt": 1, "timeout": 1}
# wrapper flags whose argument is itself a command line: scan it, do not drop it
CMD_FLAGS = {"env": ("-S", "--split-string"), "script": ("-c", "--command")}

SHELLS = {"bash", "sh", "zsh", "dash", "ksh"}
LOADERS = {"torchrun", "accelerate"}
BENCH_SCRIPTS = {"bench.sh", "fanpeg-suite.sh", "post-reboot.sh"}
# python scripts that talk to the live server or read results; they do not load a model
ALLOWED_PY = ("bench/report.py", "orchestrator/orch.py")
# start: a resident model plus DeepSeek is the 2026-10-04 OOM in reverse order
SERVICE_VERBS = {"start", "stop", "restart", "try-restart", "kill", "reload-or-restart", "try-reload-or-restart"}
# enable/disable/mask change the running unit only with --now; without it, next boot only
NOW_VERBS = {"enable", "disable", "mask"}
# Unit has Restart=on-failure: a SIGTERM that exits 0 stays down, and repeated SIGKILLs
# hit the start limit (5 in 10 s) and leave it failed. Either way the hook goes idle.
KILLERS = {"kill", "pkill", "killall"}
PY_RE = re.compile(r"^python[0-9.]*$")

def is_bench_script(tok):
    return tok.endswith(".sh") and ("bench/" in tok or os.path.basename(tok) in BENCH_SCRIPTS)

def take_flags(w, flag, toks, depth):
    """Consume one option token of wrapper w the way getopt does. A value flag takes
    the rest of its own token (-uaj, -qc'cmd', --user=aj) or else the next token.
    A short cluster is read left to right until the first value flag (-nu aj).
    Values of command-string flags (env -S, script -c) are checked recursively."""
    takes = WRAPPERS[w]
    if flag.startswith("--"):
        name, eq, val = flag.partition("=")
        if not eq:
            if name not in takes or not toks:
                return
            val = toks.pop(0)
        if name in CMD_FLAGS.get(w, ()):
            check(val, depth + 1)
        return
    for i, c in enumerate(flag[1:], 1):
        if "-" + c in takes:
            val = flag[i + 1:] or (toks.pop(0) if toks else "")
            if "-" + c in CMD_FLAGS.get(w, ()):
                check(val, depth + 1)
            return

def strip_prefix(toks, depth=0):
    """Drop VAR=val assignments and wrappers plus their flags, so the real program is toks[0].
    Command-string arguments (env -S, script -c) are checked recursively."""
    while toks:
        t = toks[0]
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", t):
            toks.pop(0); continue
        w = os.path.basename(t)
        if w in WRAPPERS:
            toks.pop(0)
            while toks and toks[0].startswith("-"):
                take_flags(w, toks.pop(0), toks, depth)
            for _ in range(POSITIONAL.get(w, 0)):
                if toks and not toks[0].startswith("-"):
                    toks.pop(0)
            continue
        break
    return toks

def deny(reason):
    sys.stderr.write(f"gpu-guard: a model is resident (GTT used {gtt / 2**30:.1f} GiB > 16 GiB). "
                     f"Refusing `{reason}`: it can load a second model or stop llama-deepseek. "
                     f"Report to the user and wait.\n")
    sys.exit(2)

# Segment separators: || && ; | & and newline. Lone & covers `true & python3 x`;
# the redirect `2>&1` splits into harmless tokens.
SPLIT_RE = re.compile(r"\|\||&&|;|\||&|\n")

def check(cmd, depth=0):
    if depth > 4:
        return
    for seg in SPLIT_RE.split(cmd):
        try:
            toks = shlex.split(seg, comments=True)
        except ValueError:
            toks = seg.split()
        toks = strip_prefix(toks, depth)
        if not toks:
            continue
        first = os.path.basename(toks[0])
        rest = toks[1:]

        # bash -c "..." / sh -lc "...": recurse into the string
        if first in SHELLS:
            for i, a in enumerate(rest):
                if a.startswith("-") and "c" in a[1:] and i + 1 < len(rest):
                    check(rest[i + 1], depth + 1)
                    break
            if rest and is_bench_script(rest[0]):
                deny(seg.strip())
            continue
        if first in {"source", "."} and rest and is_bench_script(rest[0]):
            deny(seg.strip())

        if first == "systemctl":
            # isolate stops every unit not wanted by the target; llama-deepseek is started
            # by hand and not enabled, so isolate stops it without naming it
            if "isolate" in rest:
                deny(seg.strip())
            names_unit = any(a.split(".service")[0] == "llama-deepseek" for a in rest)
            if names_unit and any(a in SERVICE_VERBS for a in rest):
                deny(seg.strip())
            if names_unit and "--now" in rest and any(a in NOW_VERBS for a in rest):
                deny(seg.strip())
            continue

        if first in KILLERS:
            if any("llama" in a for a in rest) or "pgrep" in seg:
                deny(seg.strip())
            continue

        if PY_RE.match(first):
            if rest and rest[0].endswith(ALLOWED_PY) and not any(a.endswith(".py") for a in rest[1:]):
                continue
            deny(seg.strip())
        if first.endswith(".py"):           # ./train_lora.py run by path via shebang
            deny(seg.strip())
        if first == "uv" and rest and rest[0] == "run":
            deny(seg.strip())
        if first in LOADERS:
            deny(seg.strip())
        if first.startswith("llama-"):
            deny(seg.strip())
        if is_bench_script(toks[0]):
            deny(seg.strip())

check(cmd)
sys.exit(0)
PY
