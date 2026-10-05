#!/usr/bin/env bash
# PreToolUse hook on Bash for the trainer and evaluator agents.
# Denies commands that can load a model while llama-deepseek.service holds the GPU.
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
# python passes; eval and xargs are not followed. This is a tripwire, not a sandbox.
python3 - <<'PY'
import os, re, shlex, sys

cmd = os.environ.get("GUARD_CMD", "")
if not cmd:
    sys.exit(0)

WRAPPERS = {"sudo", "doas", "nohup", "time", "env", "nice", "ionice", "setsid", "exec", "stdbuf", "command", "chrt", "taskset", "unbuffer", "script"}
# wrapper flags that take a separate argument (sudo -u aj, nice -n 10, env -u VAR)
FLAG_WITH_ARG = {"-u", "-g", "-n", "-c", "-C", "-o", "-p", "-f", "-S", "-i"}
SHELLS = {"bash", "sh", "zsh", "dash", "ksh"}
LOADERS = {"torchrun", "accelerate"}
BENCH_SCRIPTS = {"bench.sh", "fanpeg-suite.sh", "post-reboot.sh"}
PY_RE = re.compile(r"^python[0-9.]*$")

def is_bench_script(tok):
    return tok.endswith(".sh") and ("bench/" in tok or os.path.basename(tok) in BENCH_SCRIPTS)

def strip_prefix(toks):
    """Drop VAR=val assignments and wrappers plus their flags, so the real program is toks[0]."""
    while toks:
        t = toks[0]
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", t):
            toks.pop(0); continue
        if os.path.basename(t) in WRAPPERS:
            toks.pop(0)
            while toks and toks[0].startswith("-"):
                flag = toks.pop(0)
                # env -i / time -v style flags take no arg; -u/-n/-c style take one.
                # "sh -c" is handled by the caller before this; here -c means e.g. ionice -c 2.
                if flag in FLAG_WITH_ARG and toks and flag not in {"-i"}:
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
                     f"Refusing `{reason}`: it can load a model. Ask the user to stop the service first.\n")
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

        if PY_RE.match(first):
            if rest and rest[0].endswith("bench/report.py") and not any(a.endswith(".py") for a in rest[1:]):
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
