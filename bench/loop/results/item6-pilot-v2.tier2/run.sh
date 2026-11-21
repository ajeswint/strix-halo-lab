#!/usr/bin/env bash
# Tier 2 blind reviews: one fresh cursor-agent session per task (no --resume), cwd holds only packet.md, ask (read-only) mode.
T=/tmp/lab-seats/item6-v2-tier2
echo "running $(date -Is)" > $T/run.status
for d in $T/item6_pr*/; do
  ( cd "$d" && timeout 1800 cursor-agent -p --trust --mode ask --model grok-4.7-high --output-format json "Read the file packet.md in the current directory in full and follow its instructions exactly. Read no other file and use no other tool." < /dev/null > out.json 2> err.log; echo "rc=$? $(date -Is)" > rc.txt ) &
done
wait
echo "done $(date -Is)" > $T/run.status
