#!/usr/bin/env bash
set -u
D=/tmp/lab-seats/grounding-writer
cd /tmp/wt-ground-v1 || exit 1
echo $$ > $D/run.pid
echo "running $(date -Is)" > $D/run.status
start=$(date +%s)
timeout --kill-after=30 10800 agy -p "$(cat $D/prompt.txt)" --model gemini-3.8-flash-high --effort high --dangerously-skip-permissions < /dev/null > $D/out.log 2> $D/err.log
rc=$?
echo "done rc=$rc wall_s=$(( $(date +%s) - start )) end=$(date -Is)" > $D/run.status
