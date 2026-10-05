#!/usr/bin/env bash
# Matrix for gpu-guard.sh. Runs only the python matcher, so llama-deepseek is
# simulated active regardless of its real state. Loads nothing; safe to run anytime.
# Usage: bash .claude/hooks/gpu-guard-test.sh
set -u
here=$(dirname "$0")
py=$(mktemp)
trap 'rm -f "$py"' EXIT
sed -n "/^python3 - <<'PY'$/,/^PY$/p" "$here/gpu-guard.sh" | sed '1d;$d' > "$py"

fail=0; n=0
t() {  # t <expected rc: 2 deny, 0 allow> <command>
    n=$((n+1))
    GUARD_CMD="$2" python3 "$py" 2>/dev/null; rc=$?
    if [ "$rc" != "$1" ]; then fail=$((fail+1)); printf 'FAIL want %s got %s: %s\n' "$1" "$rc" "$2"; fi
}

# model loaders
t 2 'python3 train.py'
t 2 'python train.py'
t 2 'python3.12 -c "import torch"'
t 2 '/data/envs/torch/bin/python x.py'
t 2 './train_lora.py'
t 2 'uv run train.py'
t 2 'torchrun --nproc-per-node 1 t.py'
t 2 'accelerate launch t.py'
t 2 'llama-bench -m m.gguf'
t 2 'llama-server -m m.gguf'
t 2 '/opt/llama/bin/llama-perplexity -m m.gguf'
t 2 'bench/bench.sh'
t 2 'bash bench/fanpeg-suite.sh'
t 2 'source bench/post-reboot.sh'
t 2 'bash -c "python3 x.py"'
t 2 'sh -lc "cd /tmp && llama-bench"'
t 2 'cd /tmp && python3 x.py'
t 2 'true & python3 x.py'
t 2 'ls | python3 x.py'
t 2 'FOO=1 python3 x.py'
t 2 'sudo -n python3 x.py'
t 2 'sudo -u aj python3 x.py'
t 2 'nice -n 10 python3 x.py'
t 2 'env -u HIP_VISIBLE_DEVICES python3 x.py'
t 2 'taskset 3 python3 x.py'
t 2 'chrt 10 llama-bench'
t 2 'nohup python3 x.py &'
t 2 'timeout 5 python3 x.py'
t 2 'python3 bench/report.py other.py'
# allowed: read-only or live-server clients
t 0 'python3 bench/report.py'
t 0 'python3 orchestrator/orch.py --task x'
t 0 'cat bench/bench.sh'
t 0 'git diff -- train.py'
t 0 'grep -rn python3 .'
t 0 'free -g'
t 0 'ls /data/models'
# service: stop/restart family
t 2 'systemctl stop llama-deepseek'
t 2 'systemctl stop llama-deepseek.service'
t 2 'sudo systemctl restart llama-deepseek'
t 2 'sudo -n systemctl stop llama-deepseek'
t 2 'systemctl try-restart llama-deepseek'
t 2 'systemctl kill -s SIGKILL llama-deepseek'
t 2 'systemctl reload-or-restart llama-deepseek'
t 2 'systemctl try-reload-or-restart llama-deepseek.service'
t 0 'systemctl is-active llama-deepseek'
t 0 'systemctl status llama-deepseek'
t 0 'systemctl stop model-download'
# added 2026-10-05: --now, isolate, timeout wrapper, kill commands
t 2 'sudo systemctl disable --now llama-deepseek'
t 2 'systemctl mask --now llama-deepseek.service'
t 2 'systemctl --now disable llama-deepseek'
t 0 'systemctl disable llama-deepseek'
t 0 'systemctl mask llama-deepseek'
t 2 'systemctl isolate multi-user.target'
t 2 'sudo systemctl isolate rescue.target'
t 2 'timeout 5 systemctl stop llama-deepseek'
t 2 'timeout -k 2 5s sudo systemctl stop llama-deepseek'
t 2 'timeout -s KILL 5 systemctl stop llama-deepseek'
t 2 'pkill llama-server'
t 2 'pkill -f llama'
t 2 'killall llama-server'
t 2 'sudo killall -9 llama-server'
t 2 'kill -9 $(pgrep llama-server)'
t 2 'kill $(pgrep -f server)'
t 0 'kill 12345'
t 0 'pkill -f firefox'
t 0 'timeout 5 free -g'
# documented gaps: tripwire, not sandbox. If one starts failing, the gap closed; move it up.
t 0 'eval "systemctl stop llama-deepseek"'
t 0 'echo llama-deepseek | xargs systemctl stop'
t 0 'echo $(systemctl stop llama-deepseek)'

echo "$((n-fail))/$n passed"
[ "$fail" = 0 ]
