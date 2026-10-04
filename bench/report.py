#!/usr/bin/env python3
# Summarize /data/bench/results.jsonl: tokens/sec per label/backend/test
import json, sys
rows = [json.loads(l) for l in open(sys.argv[1] if len(sys.argv) > 1 else "/data/bench/results.jsonl") if '"avg_ts"' in l]
print(f"{'label':<28}{'backend':<8}{'model':<40}{'test':<8}{'t/s':>9}{'±':>7}")
for r in rows:
    test = f"pp{r['n_prompt']}" if r["n_prompt"] else f"tg{r['n_gen']}"
    model = r["model_filename"].split("/")[-1][:38]
    print(f"{r['label']:<28}{r['backend']:<8}{model:<40}{test:<8}{r['avg_ts']:>9.1f}{r['stddev_ts']:>7.1f}")
