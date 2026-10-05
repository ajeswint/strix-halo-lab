#!/usr/bin/env bash
# PreToolUse hook on Bash for the trainer, evaluator and systems agents.
# Denies commands that can load a model while llama-deepseek.service holds the GPU,
# and commands that would stop that service (which would also disarm this hook).
# Mechanism of the 2026-10-04 OOM: a second model load beside DeepSeek (~85 GiB GTT).
# Exit 2 blocks the call; any other exit allows it.
set -u

# Only gate while DeepSeek actually holds the GPU. Real state, not a flag file.
systemctl is-active --quiet llama-deepseek || exit 0

# Hook JSON arrives on stdin; the python script also arrives on stdin, so hand the
# command over via the environment.
GUARD_CMD=$(jq -r '.tool_input.command // empty') || exit 0
export GUARD_CMD

# Split the command into segments on ; && || | & and newlines, then judge each
# segment by its first real token after wrappers. Arguments (cat bench/bench.sh,
# git diff -- x.py) are never matched. bash -c "..." is recursed into.
# Known gaps: $(...) and backticks are not split; a new script name that wraps
# python passes; eval and xargs are not followed; a bare `kill <pid>` with no
# "llama" or pgrep in the segment passes. This is a tripwire, not a sandbox.
python3 - <<'PY'
import os, re, shlex, sys

cmd = os.environ.get("GUARD_CMD", "")
if not cmd:
    sys.exit(0)

# wrapper -> its flags that take a separate argument (sudo -u aj, nice -n 10, env -u VAR).
# Per wrapper, because sudo -n and nice -n differ: sudo -n takes none, nice -n takes one.
WRAPPERS = {
    "sudo": {"-u", "-g", "-C", "-D", "-h", "-p", "-r", "-t", "-T", "-U"},
    "doas": {"-u", "-C"},
    "nohup": set(), "setsid": set(), "command": set(), "unbuffer": set(),
    "time": {"-f", "-o"},
    "env": {"-u", "-C", "-S"},
    "nice": {"-n"},
    "ionice": {"-c", "-n", "-p", "-P", "-u"},
    "exec": {"-a"},
    "stdbuf": {"-i", "-o", "-e"},
    "chrt": set(), "taskset": set(),
    "script": {"-c"},
    "timeout": {"-k", "-s"},
}
# wrappers that take a positional before the program (taskset 3 cmd, chrt 10 cmd)
POSITIONAL = {"taskset": 1, "chrt": 1, "timeout": 1}
SHELLS = {"bash", "sh", "zsh", "dash", "ksh"}
LOADERS = {"torchrun", "accelerate"}
BENCH_SCRIPTS = {"bench.sh", "fanpeg-suite.sh", "post-reboot.sh"}
# python scripts that talk to the live server or read results; they do not load a model
ALLOWED_PY = ("bench/report.py", "orchestrator/orch.py")
SERVICE_VERBS = {"stop", "restart", "try-restart", "kill", "reload-or-restart", "try-reload-or-restart"}
# disable/mask only stop a running unit with --now; plain disable/mask affect next boot only
NOW_VERBS = {"disable", "mask"}
# Unit has Restart=on-failure: a SIGTERM that exits 0 stays down, and repeated SIGKILLs
# hit the start limit (5 in 10 s) and leave it failed. Either way the hook goes idle.
KILLERS = {"kill", "pkill", "killall"}
PY_RE = re.compile(r"^python[0-9.]*$")

def is_bench_script(tok):
    return tok.endswith(".sh") and ("bench/" in tok or os.path.basename(tok) in BENCH_SCRIPTS)

def strip_prefix(toks):
    """Drop VAR=val assignments and wrappers plus their flags, so the real program is toks[0]."""
    while toks:
        t = toks[0]
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", t):
            toks.pop(0); continue
        w = os.path.basename(t)
        if w in WRAPPERS:
            toks.pop(0)
            while toks and toks[0].startswith("-"):
                flag = toks.pop(0)
                if flag in WRAPPERS[w] and toks:
                    toks.pop(0)
            for _ in range(POSITIONAL.get(w, 0)):
                if toks and not toks[0].startswith("-"):
                    toks.pop(0)
            continue
        break
    return toks

def deny(reason):
    gtt = "?"
    for p in sorted(os.popen("ls /sys/class/drm/card*/device/mem_info_gtt_used 2>/dev/null").read().split()):
        try:
            gtt = open(p).read().strip(); break
        except OSError:
            pass
    sys.stderr.write(f"gpu-guard: llama-deepseek is active (GTT used: {gtt} bytes). "
                     f"Refusing `{reason}`: it can load a model or disarm this guard. Report to the user and wait.\n")
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
        toks = strip_prefix(toks)
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
