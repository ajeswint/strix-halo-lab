#!/usr/bin/env bash
# Matrix for gpu-guard.sh. Runs only the python matcher with GTT used simulated
# (default: DeepSeek's 86 GiB peak), regardless of real state. Loads nothing; safe to run anytime.
# Usage: bash .claude/hooks/gpu-guard-test.sh
set -u
here=$(dirname "$0")
py=$(mktemp)
trap 'rm -f "$py"' EXIT
sed -n "/^python3 - <<'PY'$/,/^PY$/p" "$here/gpu-guard.sh" | sed '1d;$d' > "$py"

GiB=$((1<<30))
DEEPSEEK=$((86*GiB)); QWEN=22360456160; LAGUNA=20548085120; IDLE=$((GiB/2)); CUT=$((16*GiB))
DS=/data/models/UD-IQ2_M/DeepSeek-V4-Flash-0731-UD-IQ2_M-00001-of-00003.gguf

fail=0; n=0
tg() {  # tg <expected rc: 2 deny, 0 allow> <GTT used bytes> <command>
    n=$((n+1))
    GUARD_GTT_USED="$2" GUARD_CMD="$3" python3 "$py" 2>/dev/null; rc=$?
    if [ "$rc" != "$1" ]; then fail=$((fail+1)); printf 'FAIL want %s got %s (gtt %s): %s\n' "$1" "$rc" "$2" "$3"; fi
}
t() { tg "$1" "$DEEPSEEK" "$2"; }  # t <expected rc> <command>, with DeepSeek resident

# GTT cutoff (added 2026-10-05): armed above 16 GiB, whichever model is resident
tg 0 "$IDLE" 'llama-bench -m m.gguf'
tg 0 "$IDLE" 'systemctl start llama-deepseek'
tg 0 "$IDLE" "bash bench/fanpeg-suite.sh"
tg 0 "$CUT" 'llama-server -m m.gguf'
tg 0 0 'python3 train.py'
tg 2 $((CUT+1)) 'llama-server -m m.gguf'
tg 2 "$QWEN" 'systemctl start llama-deepseek'
tg 2 "$QWEN" 'sudo systemctl start llama-deepseek.service'
tg 2 "$LAGUNA" 'systemctl enable --now llama-deepseek'
tg 2 "$LAGUNA" "llama-bench -m $DS"
tg 2 "$QWEN" "bench/bench.sh x $DS"
tg 2 "$QWEN" 'bash bench/fanpeg-suite.sh'
tg 2 "$LAGUNA" 'llama-server -m /data/models/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf'
tg 2 "$QWEN" 'llama-cli -m /data/models/Laguna-XS-2.1-Q4_K_M.gguf'
tg 0 "$QWEN" 'python3 orchestrator/orch.py --task x'
tg 0 "$QWEN" 'python3 bench/report.py'
tg 0 "$QWEN" 'systemctl status llama-deepseek'
# DeepSeek resident, run outside the service (fanpeg-suite.sh): same denies
t 2 'systemctl start llama-deepseek'
t 2 'systemctl enable --now llama-deepseek'
t 0 'systemctl enable llama-deepseek'

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
# added 2026-10-05: long-form wrapper flags with a separate argument
t 2 'timeout --kill-after 2 5 systemctl stop llama-deepseek'
t 2 'timeout --signal TERM 5 systemctl stop llama-deepseek'
t 2 'timeout --kill-after=2 5 systemctl stop llama-deepseek'
t 2 'sudo --user aj python3 x.py'
t 2 'sudo --chdir /tmp systemctl stop llama-deepseek'
t 2 'nice --adjustment 10 python3 x.py'
t 2 'env --unset X python3 x.py'
t 2 'ionice --class 3 python3 x.py'
t 2 'stdbuf --output L python3 x.py'
t 2 'time --output f python3 x.py'
t 0 'timeout --signal TERM 5 free -g'
# added 2026-10-05: env -a/--argv0/-f/--file, script value flags, command-string scan
t 2 'env --argv0 cat python3 x.py'
t 2 'env -a cat python3 x.py'
t 2 'env --file /tmp/e python3 x.py'
t 2 "script --echo always -c 'python3 x.py' /tmp/t"
t 2 "script -E always -c 'python3 x.py' /tmp/t"
t 0 'script --log-io /tmp/l -q /tmp/t'
t 2 "script -qc 'systemctl stop llama-deepseek' /tmp/t"
t 0 "script -qc 'free -g' /tmp/t"
t 2 'sudo -nu aj python3 x.py'
t 2 'sudo -nu aj systemctl stop llama-deepseek'
t 0 'script --log-io /tmp/l -c ls /tmp/t'
t 2 "env -S 'systemctl stop llama-deepseek'"
t 2 "env --split-string 'python3 x.py'"
t 2 "env --split-string='python3 x.py'"
t 2 "env -S'python3 x.py'"
t 2 "script -c 'systemctl stop llama-deepseek' /tmp/t"
t 2 "script --command='llama-bench -m m.gguf' /tmp/t"
t 2 "script -qc 'python3 x.py' /tmp/t"
t 0 "env -S 'ls -la'"
t 0 "script -c 'free -g' /tmp/t"
# added 2026-10-05: getopt-style glued values and clusters
t 2 "script -qc'systemctl stop llama-deepseek' /tmp/t"
t 2 "script -qc'python3 x.py' /tmp/t"
t 0 "script -qc'free -g' /tmp/t"
t 2 "env -iS'python3 x.py'"
t 2 'env -iu X python3 x.py'
t 2 'env -iuX python3 x.py'
t 2 'sudo -uaj python3 x.py'
t 2 'sudo --user=aj systemctl stop llama-deepseek'
t 2 'nice -n10 python3 x.py'
t 2 'timeout -k2 5 systemctl stop llama-deepseek'
t 2 'timeout -sKILL 5 systemctl stop llama-deepseek'
# documented gaps: tripwire, not sandbox. If one starts failing, the gap closed; move it up.
t 0 'eval "systemctl stop llama-deepseek"'
t 0 'systemd-run python3 x.py'
t 0 "runuser -u aj -- python3 x.py"
t 0 "su -c 'python3 x.py' aj"
t 0 'flock /tmp/l python3 x.py'
t 0 'strace -f python3 x.py'
t 0 'echo llama-deepseek | xargs systemctl stop'
t 0 'echo $(systemctl stop llama-deepseek)'

echo "$((n-fail))/$n passed"
[ "$fail" = 0 ]
