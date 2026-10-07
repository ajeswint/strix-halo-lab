# strix-halo-lab

Working repo for a Framework Desktop (Ryzen AI Max+ 395 / Strix Halo, Radeon 8060S gfx1151, 128 GB unified LPDDR5X) used as a local LLM box: the orchestrator, the small-model loop, training experiments, and the machine's config and decisions. Config files under `bench/`, `etc/`, `systemd/`, `envs/`, `models/`, `scripts/` are copies of the live files; paths in the tree mirror where the file lives.

**Provenance.** Started 2026-10-04 from a snapshot of [strix-halo-setup](https://github.com/ajeswint/strix-halo-setup) at `b94e957` (archived, read-only). That repo holds the commit history of the install and tuning work; this one starts from its final state. The machine setup is complete: install, tuning, firewall. Work here is the Roadmap.

**Carried over, open:** check the silkscreen at the fan plug (see *Why the fan is pegged*). Orchestrator timer still held. Its DB (`/data/orch/orch.db`) has no review of this repo yet, so the first `review` here covers the whole tree.

## Hardware

- Framework Desktop, Ryzen AI Max+ 395, Radeon 8060S iGPU (gfx1151), 128 GB LPDDR5X-8000 (256 GB/s theoretical)
- OS: WD_Black SN7100 1 TB in the back M.2 slot (enumerates as `nvme1n1`)
- Data: WD_Black SN7100X 2 TB in the front slot, 4K LBA, XFS at `/data` (`scripts/data-drive-setup.sh`). Address disks by `/dev/disk/by-id`, never `nvmeXn1`.
- BIOS 3.06, EC and PD firmware current (2026-10-03). BIOS update produced no performance change.

## Software state (verified 2026-10-04)

| Layer | State |
|---|---|
| OS | Ubuntu 26.04.1 LTS, kernel 7.0.0-38-generic, in-tree `amdgpu` |
| System ROCm | 10.0.0 (`amdrocm-core10.0-gfx1151`), `scripts/rocm-install.sh`, `scripts/rocm-verify.sh` |
| GTT | tuned to 108 GiB visible to the GPU |
| Power | `tuned` + `tuned-ppd`, profile `accelerator-performance`, persisted via `etc/tuned/` (replaced power-profiles-daemon) |
| Cooling | `systemd/fan-peg.service`: `framework_tool --fansetduty 100` at boot and after resume. See *Why the fan is pegged*. |
| llama.cpp | `/data/src/llama.cpp` HEAD 836d57176, `build-hip` (gfx1151) and `build-vk`; `etc/ld.so.conf.d/rocm.conf` puts the HIP libs on the linker path |
| Serving | `systemd/llama-deepseek.service`: DeepSeek V4 Flash UD-IQ2_M, HIP, 64k context, `127.0.0.1:8080`, alias `deepseek-v4-flash`. Started manually, not enabled at boot (pins ~85 GiB GTT). |
| Models | `/data/models`: Qwen3.6-35B-A3B UD-Q4_K_XL, DeepSeek V4 Flash 0731 UD-IQ2_M (3 shards), Laguna XS 2.1 Q4_K_M (bartowski, 20.55 GB, sha256 `239b1417…3491dae6` verified 2026-10-04; tested as a second small model for the loop and dropped after loop-v1 (10fc559: it solved no task Qwen missed); file kept on disk. Smoke test 2026-10-05 via `scripts/llm-serve.sh start laguna` (vk, ctx 32768, 1 slot): load 3.1 s (file likely in page cache), GTT peak 21.17 GiB from 0.52 idle, tg ~79-80 t/s, pp ~95-120 t/s on a 57-token prompt. It is a reasoning model: a code-only prompt used 1,639 tokens, most of them `reasoning_content`, and a 256-token cap returned empty `content`. Callers need a reasoning budget like orch.py's). `models/fetch.sh` + `systemd/model-download.service` (disabled, download complete). |
| Python / training | `/data/envs/torch`: uv venv on system Python 3.14.4. torch 2.13.0+rocm10.0.0 via `torch[device-gfx1151]` from `stable.repo.amd.com/rocm/whl-next/` (bundles its own ROCm user-space runtime; nothing loads from `/opt/rocm`), transformers 5.18.0, peft 0.21.2, trl 1.14.1, datasets 5.0.1, accelerate 1.15.0. `envs/install-torch-env.sh [target-dir]` builds an equivalent env (default `/data/envs/torch`; one-shot, refuses an existing target; validated 2026-10-04 into an empty scratch dir). `envs/freeze.txt` is that fresh install's package list, not the live env's. Live differs: three orphans (`tyro`, `typeguard`, `docstring-parser`) from the first resolver backtrack, and newer transitive versions from a later `--upgrade` (filelock 4.0.10 vs 3.32.3, rocm-bootstrap 0.3.0 vs 0.1.0, setuptools 84 vs 81, numpy 2.5.3 vs 2.5.2, networkx 3.7 vs 3.6.1, markupsafe 3.0.4 vs 3.0.3). The torch/transformers/peft/trl/datasets/accelerate versions are identical in both. `HF_HOME=/data/hf-cache`. |
| Tooling | uv, gh, git-lfs, podman (rootless) + distrobox, sqlite3, tmux, btop, nvtop, aria2, fd-find, vulkan-tools |
| Firewall | ufw active: deny incoming, allow outgoing; RDP 3389/tcp and SSH 22/tcp, both from 192.168.50.0/24 only. Copy in `etc/ufw/user.rules`. |
| Remote access | GNOME Desktop Sharing (user-level `gnome-remote-desktop.service`, mirrors the logged-in session). System Remote Login off. GDM auto-login for `aj` (`etc/gdm3/custom.conf`) so a session exists after reboot; the login keyring is not unlocked by auto-login and prompts on the local screen. `openssh-server` (installed 2026-10-05, password auth, no keys yet) as the recovery path when RDP breaks. Remmina profiles need color depth GFX or Automatic: the server closes connections that don't offer the RDP Graphics Pipeline. |
| Always on | sleep/suspend/hibernate/hybrid-sleep targets masked; `etc/systemd/logind.conf.d/00-always-on.conf` ignores lid, suspend/hibernate keys, idle and the **power key** (short press does nothing; long press still forces off). |
| Cursor | AppArmor adjustments in `etc/apparmor.d/` so Cursor's terminal sandbox runs under Ubuntu's user-namespace restriction. Keep the local conffile on Cursor updates. |

Not installed, by decision: Docker (podman instead), Postgres (SQLite, see below), Unsloth (would need Python 3.10-3.13 and its own torch; separate env if ever), bitsandbytes.

## Security (2026-10-04)

- **Firewall:** ufw enabled 2026-10-04 (it was installed but inactive). Rules match the ports in use "for now": the LAN gets RDP (3389/tcp) and SSH (22/tcp, added 2026-10-05) from 192.168.50.0/24, everything else inbound is dropped. mDNS and DHCP replies pass via ufw's stock `before.rules`. CUPS (631), DNS stub (53) and llama-server (8080) listen on loopback only. Add a rule when a new LAN service is added.
- **Disk encryption: none, by decision.** Neither drive is encrypted; the performance cost was judged not worth it. Physical access to the box = access to the data.
- **In place:** Secure Boot on, unattended-upgrades on, SSH LAN-only. Cursor's AppArmor profile is unconfined by design (see Cursor row).
- **2026-10-05 Grok Bot RDP incident.** An outside agent (Grok Bot, with sudo) spent the night "fixing" RDP: set RDP credentials `aj`/`123` at user, headless and system level (two in plaintext systemd drop-ins), opened 3389 and OpenSSH to any source in ufw, installed openssh-server, enabled GDM auto-login, masked sleep, and left the user-level headless daemon on 3389, which is the wrong mode for sharing the desktop. Cleaned up the same day: headless unit and drop-ins removed, headless and system credentials cleared, system Remote Login disabled, ufw back to LAN-only, scripts deleted. Kept by choice: auto-login, sleep masks, logind drop-in, SSH (LAN-only). Desktop Sharing credentials re-set by hand. Grok Bot's local-exec daemon config remains in `~/.grokbot/`.
- **Memory exhaustion is not guarded by the system.** 2026-10-04 18:16: `llama-perplexity` (Qwen, ~22 GB) was started while `llama-deepseek.service` held ~85 GiB GTT. Swap hit 0, the kernel OOM killer fired once and killed Cursor (0.4 GB, `oom_score_adj` 300) instead of either llama process, then kworkers blocked >120 s and the journal stops; reboot required. systemd-oomd logged nothing. Rule: before loading any model, check `free -g`, GTT used and `systemctl is-active llama-deepseek`; never load beside the DeepSeek server.

## Why the fan is pegged

The EC's automatic fan curve drives fan header 0, which has no fan on it (reads 0 RPM at 100% duty). The CPU heatsink fan is on header 1, which the curve never ramps. Under sustained load the APU hit ~100 °C in two minutes and fell off boost to ~105 W. With both headers forced to 100% (`fan-peg.service`) the chip holds 138 W / ~2885 MHz for ~8 minutes, then 120 W / ~2790 MHz at 68-71 °C indefinitely — Framework's published spec. Prompt processing rose 35-40%. Hottest point in the whole suite was 84 °C (64k-context HIP run). Open: check the silkscreen at the fan plug; if it says "APU Fan", the header mapping is an EC firmware bug to report to Framework.

## Benchmarks

`bench/bench.sh <label> <gguf>` runs llama-bench under Framework's conditions (pp2048 / tg128, `-ngl 999 -fa on -lm none`) on HIP and Vulkan and appends to `bench/results.jsonl`; `bench/report.py` summarises. `bench/fanpeg-suite.sh` is the cooling A/B suite; `bench/fanpeg-mon.log` is its 2 s power/clock/temp trace. `bench/post-reboot.sh` checks BIOS, cmdline, GTT, power profile after a reboot, then benches.

Fan-pegged results (t/s):

| Model | HIP pp / tg | Vulkan pp / tg |
|---|---|---|
| Qwen3.6-35B-A3B Q4_K_XL, depth 0 | 1392 / 53.1 | 1390 / 61.7 |
| DeepSeek V4 Flash IQ2_M, depth 0 | 261 / 16.4 | 223 / 18.6 |
| DeepSeek, depth 8k | 202 / 15.0 | 174 / 17.7 |
| DeepSeek, depth 32k | 119 / 13.5 | 108 / 13.6 |
| DeepSeek, depth 64k | — / 11.7 | — / 11.1 |

Token generation is memory-bandwidth bound (~117 GB/s effective); power and clock knobs do not move it. HIP wins prompt processing at every depth; Vulkan wins generation at short context; they meet around 32k. HIP is used for long-context serving.

PyTorch on gfx1151, bf16 square matmul, warm, TFLOPS: 2048² 34.7, 4096² 36.4, 8192² 32.3 (hipBLASLt, which torch selects by default). LoRA smoke test (random-init 100M Llama, r=16, bf16): loss decreases, finite, 14.4k tok/s, 2 GiB peak.

## Decisions

- **Measure, don't assume.** The machine follows Framework's published local-AI setup as baseline; deviations need a benchmark delta. Dropped after measurement or analysis: IOMMU off (GPU and NPU are already identity-mapped; would cost USB4/NVMe DMA protection), GTT above 108 GiB (64k DeepSeek peaks at 86 GiB), GPU DPM forced high (+15-20 W idle for ~2%).
- **Set-and-forget.** Settings that must persist are applied once at the points where they can reset (boot, resume). No polling loops, watchdogs or self-tests unless observed behaviour shows a revert.
- **SQLite, one writer**, WAL mode, for the orchestrator's memory. Postgres + pgvector only when parallel writers hit lock errors or maintained migrations are needed. Vectors later via sqlite-vec in the same file.
- **PyTorch from AMD's gfx1151 wheels**, not `download.pytorch.org` ROCm 7.x wheels (no gfx1151 kernels; Unsloth's AMD page assumes an MI300 via `HSA_OVERRIDE_GFX_VERSION`).
- **uv gotcha:** the AMD wheel index also hosts `fsspec` (one version). With uv's default first-index strategy that pins `fsspec` and silently backtracks `datasets`/`trl` to 2020-era releases. Always pass `--index-strategy unsafe-best-match` when installing into the torch env with that index.
- **DeepSeek V4 Flash is a background reviewer**, not an interactive model (1-3 min per turn cached, 4-6 uncached). Interactive and agentic work uses lighter MoE models (Qwen3.6-35B-A3B).
- **Four Claude agents in `.claude/agents/`** (systems, trainer, evaluator, red-team); no Claude reviewer, `orch.py` on DeepSeek is the reviewer. `.claude/hooks/gpu-guard.sh` is a PreToolUse tripwire on systems, trainer and evaluator Bash, armed while GTT used is above 16 GiB (any model resident; DeepSeek also loads outside its service via the bench scripts). Armed, it denies model loads, `systemctl start` of llama-deepseek, and stopping that service. One cutoff means two small models cannot be resident together. loop-v1 ran them one at a time and dropped Laguna, so the rule stays. `orchestrator/orch.py` and `bench/report.py` are allowed through. Not on the parent session. Known gaps stay in the script header.
- **Procedures as skills** in `.claude/skills/`: preflight, llm-serve, bench, measure, orch-review, live-sync, torch-install, model-add, handoff (user-only). Agents preload theirs via `skills:` frontmatter. Deterministic checks are scripts the skills call (`scripts/preflight.sh`, `scripts/llm-serve.sh`, `scripts/drift-check.sh`), so a gate is an exit code, not prose. Small models are served only via `scripts/llm-serve.sh` (transient user unit `llm-8081`, `127.0.0.1:8081`); its `start` runs preflight and is denied by gpu-guard while armed.

## Orchestrator (v1, 2026-10-04)

`orchestrator/orch.py` (Python stdlib only) has DeepSeek review new commits and keeps the verdicts in SQLite (`/data/orch/orch.db`, WAL, one writer, schema in `orchestrator/schema.sql`, versioned by `PRAGMA user_version`).

```
python3 orchestrator/orch.py review ~/projects/strix-halo-lab
python3 orchestrator/orch.py findings
python3 orchestrator/orch.py findings --all --detail 1
python3 orchestrator/orch.py verdict 1 rejected "reason" --by claude
python3 orchestrator/orch.py runs
```

- Reviews the diff from the last successfully reviewed commit to HEAD (committed work only). The first review covers the whole tree. Per-file diffs over 20k chars (logs, JSONL) are not sent; their first 3 lines at HEAD are, so code that writes or reads them is not judged blind (the cause of run 2's false positives).
- Prompt order is static to changing: system rules, README + CLAUDE.md, past verdicts, commit log, diff. Measured: resending the same prompt reused 18,640 of 18,644 tokens from llama-server's cache (0.2 s vs 97 s). The server has one slot, so any other request in between evicts it.
- Output is schema-constrained JSON (`response_format.type = json_schema`, nested `json_schema.schema`, which is what this llama.cpp build reads). Reasoning is capped per request with `reasoning_budget_tokens` 6144 inside `max_tokens` 12288. Without a cap, run 1 spent all 8,192 tokens reasoning and returned no answer.
- Findings are de-duplicated by file + normalised title. Accepted/rejected verdicts with reasons go back into the next prompt.
- Skips (no new commits, server down) exit 0 and are logged as `skipped` runs. Errors exit 1 and keep the raw response.
- `systemd/user/orch-review.{service,timer}` would run it hourly as a user unit. NOT installed: held until a review produces a finding worth keeping. To install:
  ```
  mkdir -p ~/.config/systemd/user && ln -sf ~/projects/strix-halo-lab/systemd/user/orch-review.service ~/projects/strix-halo-lab/systemd/user/orch-review.timer ~/.config/systemd/user/ && systemctl --user daemon-reload && systemctl --user enable --now orch-review.timer
  ```
  Linger is on (`loginctl show-user aj -p Linger` = yes, checked 2026-10-05): the user manager stays up across logout, and an enabled user unit (this timer, once installed) starts at boot without a login. `llm-8081` is transient: a running one survives logout until it is stopped, holding GTT and keeping gpu-guard armed, but does not come back after a reboot.

First full review (run 2): 18,644 prompt tokens, 6,489 generated, 534 s. All three findings were false positives (rejected #1-#3 with reasons): the model judged `bench.sh`'s JSONL writer with `results.jsonl` omitted. Run 3 (two small commits, 5,313 prompt tokens, 415 s): 0 findings, but it missed a real doc error (this section claimed the timer was running). Only 138 tokens came from cache because README.md, which sits early in the prompt, changed in those commits. Every run so far used the full 6,144-token reasoning budget, so a review costs ~7 min of GPU regardless of diff size.

## Small-model loop v0 (2026-10-05)

`bench/loop/` (live copy `/data/bench/loop`): `tasks.py` holds 20 held-out Python tasks written for this set (spec, unit tests, reference solution); none was used for prompt iteration or as a few-shot example. `run.py --selftest` checks that every reference passes and an empty solution fails every task; a brute-force cross-check of the tie-break tasks (lis, knapsack, shortest_path) found 0 mismatches in 1,200 random cases. `run.py --label L -n 4` samples 4 candidates per task from `llm-8081` and grades them only by the tests, each candidate in bwrap (no network, read-only `/usr`, scratch dir only, 4 GiB address-space cap, 60 s timeout). Results go to `bench/loop/results/L.jsonl` (per sample, code included) and `L.summary.json`, which includes `gtt_peak_gib` sampled every 1 s during the run; pass preflight's pre-load `gtt_used` as `--gtt-baseline` to also get `gtt_model_gib` (peak minus idle). loop-v0 predates this; its GTT figures below come from a shell sampler.

Stated before the run (measure skill):
- Question: does test-selected best-of-4 beat pass@1 for Qwen3.6-35B-A3B on loop-v0?
- Metric: pass@1 = mean pass rate over all 80 samples, spread = min-max over the 4 seeds. best-of-4 = share of tasks where any of the 4 samples passes the tests (the tests pick the candidate, which is how the loop uses them).
- Threshold: keep best-of-4 as the loop's default if it beats pass@1 by >= 10 points. If pass@1 >= 95%, the set is saturated and says nothing; it needs harder tasks before any keep/drop.
- Fixed: Qwen3.6-35B-A3B UD-Q4_K_XL, Vulkan, `-c 65536 -np 4` (16k per slot), temperature 0.6, top_p 0.95, top_k 20, seeds 0-3, `reasoning_budget_tokens` 8192 inside `max_tokens` 12288, 4 concurrent requests.

Result, `qwen-vk-np4-2026-10-05` (preflight READY, served by `scripts/llm-serve.sh start qwen vk 65536 4`, stopped after):

```
question:  test-selected best-of-4 vs pass@1, Qwen3.6-35B-A3B, loop-v0 (20 tasks x 4 samples)
pass@1:    86.25% (69/80)   per-seed spread 75% / 100% / 80% / 90%
best-of-4: 100% (20/20)
delta:     +13.75 points    threshold: >= 10   -> keep best-of-4 as the loop default
```

- Ceiling: best-of-4 hit 100%, so the delta is capped by the set, not the method. Not saturated on pass@1 (86% < 95%), but the next set needs harder tasks to measure best-of-N beyond 4 or to compare models.
- Failures (11), each on a case the spec states: csv_split 3 (quoted `"x,y"` field: one MemoryError at the 4 GiB cap, one rejected as a stray quote; one lost the trailing empty field), eval_expr 2 (both `UnboundLocalError` on `pos`, a missing `nonlocal`), glob_match 2 (`[abc]x` vs `bx`: bracket classes broken), roman_to_int 1 (accepted "IIII"), parse_duration 1 (rejected "1h30m"), justify 1 (the textbook 16-wide example), knapsack 1 (spent all 12,288 tokens reasoning, no code block). Read from the per-sample `err`; no test or harness fault.
- Reasoning budget: 36/80 samples ran past 8,192 completion tokens and passed 27/36 (75%); the other 44 passed 42/44 (95%). Correlation only: hard tasks both run long and fail more. Whether a bigger budget helps is a separate one-variable run.
- Cost: 547,913 completion tokens, median 7,452 per sample, 4,585 s wall (76 min), ~120 t/s aggregate over 4 slots, median 246 s per sample. GTT 5.15 GiB before (another GPU client, not llama), peak 27.76 GiB: Qwen at 65k ctx / 4 slots is ~22.6 GiB.
- Diversity: every passing solution is textually distinct after whitespace removal (weak measure; identifiers differ). A structural measure is needed before any self-training on these outputs.

## Small-model loop v1: Qwen vs Laguna (2026-10-05)

`bench/loop/tasks_v1.py`: 30 new tasks written after loop-v0 hit best-of-4 = 100%: parsers with error cases (regex subset, strict JSON, UTF-8 with maximal-subpart replacement, cron, polynomial expansion, exact rational expressions, boolean equivalence, ISO 8601 durations), exact tie-breaks (alien order, weighted intervals, word ladders) and performance limits. Most tests compare against a brute-force oracle inside the test on seeded random inputs. Where a stdlib call would solve the task (re, json, codecs, `bytes.decode`, eval), `_banned()` in run.py's test prelude rejects the solution. `run.py --selftest --set v1`: all 30 references pass, empty solutions fail all 30, and each banned shortcut tried was rejected. None of the tasks was used for prompt iteration or as a few-shot example.

Stated before the run (measure skill step 6; this section is committed before any preflight, results empty):
- Question: does Laguna XS 2.1 solve loop-v1 tasks that Qwen3.6-35B-A3B does not, enough to keep it as a second model in the loop with tests as referee?
- Metric: per model, pass@1 (mean over 120 samples, per-seed spread) and best-of-4 (tasks with any passing sample). Per-task overlap at best-of-4: only Qwen, only Laguna, both, neither. Union best-of-4 = tasks solved by either.
- Threshold: keep Laguna if union best-of-4 exceeds Qwen best-of-4 by >= 3 tasks (10 points of 30). Otherwise drop it from the loop. If Qwen best-of-4 is 30/30 the comparison is inconclusive, which means drop (and the set was not hard enough).
- Harder than v0: counts as harder if Qwen pass@1 on v1 is below its v0 value, 86.25%.
- Fixed for both models: Vulkan, `scripts/llm-serve.sh start <model> vk 65536 4` (16k per slot), temperature 0.6, top_p 0.95, top_k 20 (Qwen3's thinking-mode recommendation, also applied to Laguna so sampling is not a variable), seeds 0-3, `reasoning_budget_tokens` 8192 inside `max_tokens` 12288, 4 concurrent requests, same prompt suffix. One model resident at a time: Qwen first, then Laguna. `--gtt-baseline` = the `gtt_used` printed by the preflight right before each start.
- Cost: loop-v0 took 76 min for 80 samples; v1 is 120 samples per model on harder tasks, so an estimated 2-3 h per model.

Result (labels `qwen-v1-vk-np4-2026-10-05`, `laguna-v1-vk-np4-2026-10-05`; each started by `scripts/llm-serve.sh` after its preflight printed READY at 5.2 GiB GTT used; `llm-8081` stopped after each):

```
question:  does Laguna add loop-v1 tasks Qwen cannot solve?   stated in: b9b211e
Qwen:      pass@1 68.33% (82/120)  per-seed 70.0 / 76.7 / 70.0 / 56.7%   best-of-4 93.33% (28/30)
Laguna:    pass@1 45.00% (54/120)  per-seed 46.7 / 46.7 / 43.3 / 43.3%   best-of-4 66.67% (20/30)
union:     28/30 = Qwen alone       delta: +0 tasks   threshold: >= +3   -> drop Laguna from the loop
```

| Best-of-4 overlap | Tasks |
|---|---|
| Only Qwen (8) | json_parse, utf8_decode, cron_next, rational_eval, sliding_median, min_window_subseq, next_palindrome, merge_stones |
| Only Laguna (0) | none |
| Both (20) | the other 20 |
| Neither (2) | regex_match, add_duration |

- Laguna's solved tasks are a subset of Qwen's, so on this evidence a second model adds nothing to test-selected best-of-N. Spending the GPU time on more Qwen samples is the better use. On no task did Laguna do markedly better: its pass counts beat Qwen's only on calendar_k (4/4 vs 3/4), poly_expand (2 vs 1) and reach_target (4 vs 3).
- Harder than v0: yes. Qwen pass@1 fell from 86.25% to 68.33%, and best-of-4 dropped below 100%, so this set can separate models.
- Neither solved regex_match or add_duration in 8 attempts. Every failure is a model error on a case the spec states (`ab*c` vs `ac`, `(ab)*`, `PT45M` read as months, no month-end clamp), or the 12,288-token cap was hit before any code. No test or harness fault found.
- `gtt_model_gib` (peak minus the preflight baseline): Qwen 22.65, Laguna 22.57, both at `-c 65536 -np 4`. Peaks 27.85 and 27.77 GiB.
- Tokens and time: Qwen 1,023,491 completion tokens, 8,542 s (2.4 h), 4 samples hit `max_tokens`. Laguna 1,123,783 tokens, 7,523 s (2.1 h), 18 hit `max_tokens`. Median completion: Qwen 8,742, Laguna 8,856, so most samples on both models ran past the 8,192 reasoning budget. Next measurement: Qwen best-of-16 on the 12 v1 tasks it passed at most 2/4. A one-variable reasoning-budget run (Qwen only, its own pre-run commit) waits on that result.

## Small-model loop v1: Qwen best-of-16 on the weak tasks (2026-10-05)

Stated before the run (measure skill step 6; committed before any preflight, results empty):
- Question: with 16 samples per task instead of 4, does Qwen3.6-35B-A3B solve add_duration and regex_match, the two v1 tasks nobody solved in 10fc559?
- Tasks (12, every v1 task Qwen passed at most 2/4 in `qwen-v1-vk-np4-2026-10-05`): regex_match 0, add_duration 0, json_parse 1, cron_next 1, poly_expand 1, bool_equiv 1, fraction_to_base 1, utf8_decode 2, rational_eval 2, skyline 2, min_window_subseq 2, count_digit 2.
- Samples: seeds 4-15 (12 new per task, 144 total), combined with seeds 0-3 from 10fc559 for best-of-16. The other 18 v1 tasks are already solved at 3-4/4 and are not rerun.
- Metric: per task, passes out of 16 and finish reasons (`stop` with code vs `length` without code). Qwen best-of-16 on v1 = 28 + the number of the two unsolved tasks solved.
- Reading, fixed now:
  - Both solved: Qwen reaches 30/30 on v1, so this set has nothing left for a second model.
  - Either way, a second model can add at most 2 v1 tasks, under the >= 3 bar from b9b211e; no new model is justified on v1.
  - add_duration still unsolved: wrong code, not the cap (all 4 earlier samples stopped normally with code at 8,709-8,901 tokens).
  - regex_match still unsolved: not proof Qwen cannot do it, since 3 of its 4 earlier samples hit the 12,288 cap with no code. That is the reasoning-budget run, Qwen only, with its own pre-run commit.
  - The reasoning-budget run, Q8 and any coding-model search wait on this result. Laguna returns only if a later pre-run commit names it.
- Fixed settings, identical to the Qwen v1 run: Vulkan, `scripts/llm-serve.sh start qwen vk 65536 4` (16k per slot), temperature 0.6, top_p 0.95, top_k 20, `reasoning_budget_tokens` 8192 inside `max_tokens` 12288, 4 concurrent requests, same prompt suffix, llama.cpp 836d57176 `build-vk`, Qwen3.6-35B-A3B UD-Q4_K_XL. One model resident; one-model guard unchanged. `--gtt-baseline` = the preflight `gtt_used` right before the start. Runner: `bench/loop/run.py --set v1 --tasks ... --seed-start 4 -n 12` (4fbde71), label `qwen-v1-weak12-s4-15-vk-np4-2026-10-05`.
- Cost: about 3 h (v1 Qwen averaged 71 s per sample over 120; these tasks run longer). DeepSeek is already inactive.

Result (label `qwen-v1-weak12-s4-15-vk-np4-2026-10-05`, seeds 4-15, combined with seeds 0-3 of `qwen-v1-vk-np4-2026-10-05`; preflight READY at 5.2 GiB GTT used before the start):

```
question:  do 16 samples let Qwen solve add_duration and regex_match?   stated in: 52f0a05
best-of-4:   10/12 of these tasks (0/4 on both targets)
best-of-16:  10/12   regex_match 0/16, add_duration 0/16   -> neither solved
```

| Task | seeds 0-3 | seeds 4-15 | | Task | seeds 0-3 | seeds 4-15 |
|---|---|---|---|---|---|---|
| regex_match | 0/4 | 0/12 | | rational_eval | 2/4 | 9/12 |
| add_duration | 0/4 | 0/12 | | skyline | 2/4 | 11/12 |
| json_parse | 1/4 | 3/12 | | min_window_subseq | 2/4 | 7/12 |
| utf8_decode | 2/4 | 3/12 | | bool_equiv | 1/4 | 4/12 |
| cron_next | 1/4 | 2/12 | | count_digit | 2/4 | 8/12 |
| poly_expand | 1/4 | 6/12 | | fraction_to_base | 1/4 | 10/12 |

- Reading, as stated: Qwen best-of-16 on v1 = 28/30; a second model can add at most 2, under the >= 3 bar. add_duration unsolved = wrong code: 16/16 stopped normally with code (parse errors on `-PT1S`, `-P1M`, `P1DT`, no rejection of `2026-1-05`). regex_match unsolved is not proof of inability, but the cap is less of the story than 4 samples suggested: 7/16 hit 12,288 tokens (6 with no code); the other 9 wrote code that crashed (`UnboundLocalError`, `TypeError`) or failed a stated case (`a.c` vs `ac`, `ab*c` vs `ac`, empty pattern).
- Pass@1 on these 12: 40.6% (78/192); seeds 4-15 alone 43.75% (63/144), per-seed 25.0-58.3%.
- Fresh-seed regrade (`agent.py --regrade`, seed 104729): 63 visible passes = 63 fresh passes (seeds 0-3: 82 = 82 over all 30 tasks). Best-of-16 solved stays 10/12.
- Baseline for the loop run: 192 samples, 1,801,480 completion tokens.
- Cost: 1,345,915 completion tokens, 11,210 s (3.1 h) for 144 samples, not the 1-1.5 h first estimated. `gtt_model_gib` 22.94 (peak 28.14).

## Small-model loop v1: agentic loop vs best-of-16 on the weak tasks (pre-run)

Stated before the run (measure skill step 6; committed before the loop's preflight, results empty):
- Question: on the same 12 weak v1 tasks, does the feedback loop (`bench/loop/agent.py`, 685a33b: test failure fed back, up to K turns) solve more tasks than independent best-of-16 at no more tokens?
- Baseline: best-of-16 = `qwen-v1-vk-np4-2026-10-05` seeds 0-3 + `qwen-v1-weak12-s4-15-vk-np4-2026-10-05` seeds 4-15 (pre-run 52f0a05). Baseline solved = tasks with any sample passing the fresh-seed regrade (`agent.py --regrade`); baseline tokens = completion tokens of all 192 samples.
- Change: the loop, K = 4 turns per episode, E = 4 episodes per task (at most 16 turns, the same sample count as best-of-16), task budget 196,608 completion tokens (16 x 12,288). Solved = the episode's passing code also passes on `random.seed(104729)`, which no turn saw. add_duration has fixed cases only, so its fresh grade equals its visible grade (flagged no_fresh).
- Threshold: keep the loop if it solves >= 2 more of the 12 than best-of-16 with total completion tokens <= best-of-16's, or the same number or more with <= 50% of best-of-16's tokens. Otherwise drop (best-of-N stays the loop default). If best-of-16 solves 11 or 12, the +2 clause cannot be met and only the token clause can keep the loop.
- Also reported: per task turns and stop reasons (pass, repeat_code, repeat_error, max_turns, task_budget), visible-pass vs fresh-pass (hard-coding check), and tokens to first pass for both methods.
- Fixed settings, identical to the baseline: Vulkan, `scripts/llm-serve.sh start qwen vk 65536 4`, temperature 0.6, top_p 0.95, top_k 20, `reasoning_budget_tokens` 8192 inside `max_tokens` 12288, prompt suffix from run.py, llama.cpp 836d57176 `build-vk`, Qwen3.6-35B-A3B UD-Q4_K_XL, one model resident. Loop seeds 1000 + 10 x episode + turn. 4 tasks in flight, episodes within a task sequential. `--gtt-baseline` = the preflight `gtt_used` before the start. Command: `bench/loop/agent.py --set v1 --tasks ... -k 4 -e 4 --label qwen-v1-weak12-agent-k4e4-vk-np4`.
- Cost: at most 192 turns (~3.8 h at the baseline's rate); expected less, since an episode ends at the first green run. Runs after best-of-16 finishes, never beside it.

Result (label `qwen-v1-weak12-agent-k4e4-vk-np4`, run 2026-10-06; preflight READY at 5.3 GiB GTT used before the start; `llm-8081` stopped after):

```
question:  does the feedback loop beat best-of-16 at <= its tokens?   stated in: 22fb4a4
baseline:  best-of-16 (2b4045e)   solved 10/12 (fresh seed)   1,801,480 completion tokens, 192 samples
change:    loop K=4 E=4           solved 12/12 (11 fresh seed + add_duration visible, no_fresh)     354,128 completion tokens, 37 turns
delta:     +2 tasks at 19.7% of the tokens   threshold: +2 at <= 100%, or +0 at <= 50%   -> keep (both clauses met)
```

| Task | turns | passed at (episode, turn) | tokens | best-of-16 tokens to first pass |
|---|---|---|---|---|
| regex_match | 5 | (1, 0) | 52,065 | unsolved (171,814 for 16) |
| add_duration | 10 | (2, 3) | 92,399 | unsolved (143,099 for 16) |
| json_parse | 2 | (0, 1) | 19,825 | 9,898 |
| utf8_decode | 2 | (0, 1) | 19,429 | 10,096 |
| cron_next | 6 | (1, 2) | 59,092 | 27,431 |
| poly_expand | 3 | (0, 2) | 28,657 | 19,254 |
| rational_eval | 1 | (0, 0) | 9,692 | 18,276 |
| skyline | 2 | (0, 1) | 17,485 | 8,460 |
| min_window_subseq | 1 | (0, 0) | 8,463 | 17,127 |
| bool_equiv | 3 | (0, 2) | 28,756 | 19,789 |
| count_digit | 1 | (0, 0) | 9,535 | 9,496 |
| fraction_to_base | 1 | (0, 0) | 8,730 | 26,441 |

- Verdict by the stated threshold: keep the loop over independent best-of-N. Limits on what it shows:
  - regex_match passed on the first turn of episode 1, a fresh single-shot sample with no feedback. That is one independent draw passing where 16 earlier draws had not, so feedback gets no credit for it. Episode 0's 4 feedback turns fixed one crash and then failed on other stated cases.
  - add_duration is the task feedback solved: episode 2, turn 4, after three fed-back failures: a duration-parse `ValueError`, a month clamp that dropped the time (`P1M` from `2026-01-31T10:00:00` gave `2026-02-28T00:00:00`), and an `UnboundLocalError`. Its tests have fixed cases only (no fresh seed), so it was checked separately: the passing code matches the reference on 3,000 random valid and invalid inputs in the bwrap sandbox (seed 777; `bench/loop/oracle_add_duration.py <result jsonl>` reruns it). No hard-coding.
  - Most of the token saving is the early stop, not the feedback. A sequential best-of-16 that stops at the first pass would have used 481,181 tokens and solved 10; the loop used 26% fewer and solved 12. On 6 of the 10 easy tasks the loop's first pass came later than best-of-16's, because a feedback turn costs as much as a fresh sample.
  - One run on 12 tasks, so the +2 has no spread estimate. Confirmation belongs on tasks the loop has not seen.
- Hard-coding check: visible passes 12 = fresh passes 12 (11 with a fresh seed, add_duration by the reference comparison above). Stops: 16 episodes, 12 `pass`, 2 `max_turns`, 1 `repeat_code`, 1 `repeat_error`, no `task_budget`.
- Cost: 3,955 s (66 min) wall, `gtt_model_gib` 22.99 (peak 28.29).

## Small-model loop v2: confirming the agentic loop on unseen tasks 

Stated before the run (measure skill step 6; committed before the preflight, results empty):
- Question: on 30 tasks the loop was not designed on, does the feedback loop (`bench/loop/agent.py` K=4 E=4) solve more tasks than early-stop best-of-16, or the same number for clearly fewer tokens?
- Tasks: `bench/loop/tasks_v2.py`, 30 new tasks written 2026-10-06 (v2_01-10 parsers/strings, v2_11-20 graphs/DP/data structures, v2_21-30 math/geometry/dates/simulation). None was used for prompt or loop iteration. Every test file has exactly one `random.seed(N)` line; every reference passes the visible seed, `random.seed(104729)` and seeds 1-5; empty solutions fail (`run.py --selftest --set v2`, `agent.py --selftest --set v2`).
- Baseline: early-stop best-of-16 = `agent.py --set v2 -k 1 -e 16 --label qwen-v2-bo16es-vk-np4`: up to 16 independent single-turn samples per task, no feedback (each episode starts from the bare task), stops at the first sample that passes the visible tests.
- Change: `agent.py --set v2 -k 4 -e 4 --label qwen-v2-agent-k4e4-vk-np4`: up to 4 episodes of up to 4 turns, failures fed back. Same 16-turn cap and task budget (196,608 completion tokens per task) as the baseline.
- Metric, same for both: solved = the passing code also passes the tests with `random.seed(104729)` (summary `solved`, out of 30); tokens = summary `completion_tokens_total`. `agent.py --regrade` on each result JSONL must give the same solved count (tasks with >= 1 fresh pass).
- Threshold: loop confirmed if K=4 E=4 solves >= baseline + 2 of 30 with tokens <= baseline tokens, or the same count with tokens <= 75% of baseline tokens. Otherwise inconclusive, and early-stop best-of-N stays the default loop. (Fewer solved than the baseline is also not confirmed.)
- Fixed settings, both runs: Vulkan, `scripts/llm-serve.sh start qwen vk 65536 4`, temperature 0.6, top_p 0.95, top_k 20, `reasoning_budget_tokens` 8192 inside `max_tokens` 12288, prompt suffix from run.py, llama.cpp 836d57176 `build-vk`, Qwen3.6-35B-A3B UD-Q4_K_XL, one model resident, `--parallel 4` (4 tasks in flight, episodes within a task sequential). Seeds 1000 + 10 x episode + turn (baseline: 1000, 1010, ..., 1150). `--gtt-baseline` = the preflight `gtt_used` before the start. Runs are sequential, baseline first, one server load for both.
- Cost: at most 480 turns per run (~5.9M tokens, ~10 h at the v1 best-of-16 rate); expected 2-4 h per run, since easy tasks stop after 1-2 turns. The v1 estimate was off by 2x, so these numbers are a guess.

Result (run 2026-10-06; preflight READY at 5.5 GiB GTT used before the start, `llama-deepseek` inactive; one server load, baseline then loop; `llm-8081` stopped after, GTT 5.4 GiB):

```
question:  does the loop beat early-stop best-of-16 on 30 unseen tasks?   stated in: 27e2be7
baseline:  early-stop best-of-16 (qwen-v2-bo16es-vk-np4)   solved 23/30 (fresh seed)   1,733,092 completion tokens, 175 turns, 16,115 s
change:    loop K=4 E=4 (qwen-v2-agent-k4e4-vk-np4)       solved 29/30 (fresh seed)     965,594 completion tokens,  97 turns, 10,016 s
delta:     +6 tasks at 55.7% of the tokens, 62% of the wall time   threshold: +2 at <= 100%, or +0 at <= 75%   -> confirmed (clause 1; clause 2 needs the same count)
```

| Task | loop turns | passed at (episode, turn) | loop tokens | baseline |
|---|---|---|---|---|
| int_eval | 2 | (0, 1) | 19,499 | unsolved (159,921 for 16) |
| str_literal | 4 | (1, 1) | 37,620 | unsolved (151,356 for 16) |
| xml_lite | 3 | (0, 2) | 29,883 | unsolved (167,690 for 16) |
| tree_max_path | 6 | (1, 2) | 62,938 | unsolved (189,278 for 16) |
| min_cost_flow | 6 | (2, 0) | 59,491 | unsolved (149,575 for 16) |
| best_rational | 13 | (3, 0) | 142,568 | unsolved (176,084 for 16) |
| apply_patch | 13 | unsolved | 127,452 | unsolved (147,864 for 16) |
| ipv6_canonical | 3 | (0, 2) | 28,903 | 14 turns, 132,902 |
| path_glob | 2 | (0, 1) | 18,760 | 8 turns, 73,067 |
| earliest_order | 10 | (2, 1) | 111,699 | 8 turns, 87,542 |
| iso_week | 9 | (2, 2) | 88,025 | 3 turns, 28,037 |
| other 19 tasks | 1-3 each | | 238,756 | solved, 1-4 turns each |

- Verdict by the stated threshold: confirmed. The loop is the default for Roadmap 2; early-stop best-of-N is the baseline it was measured against.
- Feedback credit: of the 6 tasks only the loop solved, 4 passed on a feedback turn (turn > 0: int_eval, str_literal, xml_lite, tree_max_path) and 2 on the first turn of a later episode, i.e. a fresh sample with no feedback (min_cost_flow, best_rational). Counting only the 4 feedback wins (27 vs 23), the +2 clause still holds. Over all 29 solved tasks: 12 passed on a turn > 0, 17 on turn 0.
- Same seed, different result: an episode's turn 0 uses the baseline's seed for that sample index (1000 + 10 x episode), with the same prompt. min_cost_flow (episode 2, seed 1020) and best_rational (episode 3, seed 1030) passed in the loop where the baseline's seed-1020 and seed-1030 samples failed. Over all 44 matched turn-0 draws (same task, seed and prompt size), 5 disagree: those 2, b64_strict and shell_split at seed 1000 (loop passed; the baseline solved both on a later sample), and iso_week at seed 1020 (baseline passed; the loop solved it on a feedback turn). With 4 slots batching, llama.cpp sampling is not reproducible per seed, so turn-0 samples count as independent draws. The 4 feedback wins are not among the 5: their turn-0 samples failed in both runs.
- No task was solved by the baseline and missed by the loop. The loop was slower to its first pass on earliest_order (8 -> 10 turns), iso_week (3 -> 9) and perfect_power (2 -> 3) (feedback turns cost as much as fresh samples).
- Hard-coding check: visible passes = fresh passes in both runs (23 = 23, 29 = 29). `agent.py --regrade` on each JSONL gives the same counts. All 30 tasks have a fresh seed (no no_fresh).
- Stops, loop: 44 episodes, 29 `pass`, 7 `max_turns`, 6 `repeat_error`, 2 `repeat_code`, no `task_budget`; 16 of 97 turns ended at the 12,288-token cap. Baseline: 175 single-turn episodes, 23 `pass`, 152 failed.
- One run each on 30 tasks: no spread estimate. The 6-task gap is large next to v1's +2 on 12, and points the same way.
- Cost: 7.26 h GPU in total; `gtt_model_gib` 22.79 (baseline) and 22.37 (loop), peak 28.29 GiB.

## Small-model loop v3: headroom for the next comparison

Stated before the run (measure skill step 6; committed before the preflight, results empty). Not a keep/drop: the loop stays the Roadmap 2 default whatever this run gives, and its numbers tune nothing (no prompt, K, E, budget or task edits from it).
- Question: does loop-alone (`bench/loop/agent.py` K=4 E=4) leave room on a harder held-out set, so that a later arm (a second model as fixer, retrieved memory, or K/E) can show a +2 gain? v2 left 1 unsolved task of 30, so no arm could clear +2 there.
- Tasks: `bench/loop/tasks_v3.py`, 30 new tasks written 2026-10-06, modelled on the 7 v2 tasks early-stop best-of-16 failed (apply_patch, int_eval, str_literal, xml_lite, tree_max_path, min_cost_flow, best_rational): multi-rule specs with error cases and tie-break rules. v3_01-10 parsers/interpreters/formats (INI interpolation, Forth VM, URL normalisation, Markdown tables, S-expressions, Mustache, protobuf wire, strftime, RPN to infix, bencode), v3_11-20 graphs/trees/DP/data structures (bridges, min cut, rerooting, lexicographic route DP, digit DP, persistent multiset, path max edge, Steiner tree, min mean cycle, tree isomorphism), v3_21-30 number theory/exact arithmetic/geometry/calendars/simulation (modular square roots, discrete log, Pell, polygon clipping, Julian/Gregorian switch, apportionment, 2D LP, monthly recurrence, n-th root digits, billiard). None copies a v0-v2 concept; none was used for prompt or loop iteration. Every test file has exactly one `random.seed(N)` line (N = 3001-3030) and checks seeded random cases against an oracle inside the test, not the ref. Every reference passes the visible seed, `random.seed(104729)` and seeds 1-5; empty solutions fail (`run.py --selftest --set v3`, `agent.py --selftest --set v3`). Each test grades in <= 2.1 s.
- Arm: `agent.py --set v3 -k 4 -e 4 --label qwen-v3-agent-k4e4-vk-np4`: up to 4 episodes of up to 4 turns, failures fed back, task budget 196,608 completion tokens.
- Metric: solved = the passing code also passes with `random.seed(104729)` (summary `solved`, out of 30); `agent.py --regrade` on the JSONL must give the same count. Also recorded: completion tokens, turns, wall time, `gtt_model_gib`, stop reasons, turns at the token cap.
- Rule: solved <= 26/30 means v3 has room (>= 4 unsolved) and is the reserved held-out set for the next role/memory comparison; that comparison gets its own pre-run and threshold. Solved >= 27/30 means v3 is too easy for a +2 bar and a harder v4 gets written.
- Fixed settings, as v2: Vulkan, `scripts/llm-serve.sh start qwen vk 65536 4`, temperature 0.6, top_p 0.95, top_k 20, `reasoning_budget_tokens` 8192 inside `max_tokens` 12288, prompt suffix from run.py, llama.cpp 836d57176 `build-vk`, Qwen3.6-35B-A3B UD-Q4_K_XL, one model resident, `--parallel 4`. Seeds 1000 + 10 x episode + turn. `--gtt-baseline` = the preflight `gtt_used` before the start. v3 prompts are up to 2,859 chars (v2: 2,031), so a late feedback turn with long code can reach the 16k slot end before 12,288 tokens; same slot as v2, recorded via `finish`.
- Cost: at most 480 turns (~5.9M tokens). At v2's loop rate (~413 s per turn per slot), 5-10 h if tasks average 8-16 turns; ceiling ~14 h. One run, no baseline arm.

Result (run 2026-10-06 13:54-17:31; preflight READY at 5.6 GiB GTT used before the start, `llama-deepseek` inactive; `llm-8081` stopped after, GTT 5.8 GiB). This is also the v3 loop-alone baseline arm: a later role or memory arm on v3 compares against it and does not rerun it.

```
question:  does loop K=4 E=4 leave room on v3?   stated in: 99f919a
arm:       loop K=4 E=4 (qwen-v3-agent-k4e4-vk-np4)   solved 25/30 (fresh seed)   1,398,114 completion tokens, 131 turns, 13,002 s (3.61 h)
rule:      solved <= 26/30 -> v3 reserved for the next role/memory comparison; >= 27/30 -> v3 too easy, write v4
verdict:   25 <= 26 -> v3 has room: 5 unsolved tasks. Reserved as the held-out set. Not a keep/drop.
```

- Unsolved (all 4 episodes used, each stopping early on a repeated error, repeated code or the turn cap; 136,919-163,272 tokens each): forth_vm (13 turns), farthest_vertex (14), mod_sqrts (14), hist_calendar (13), billiard (13). Headroom is 5 tasks; this run sets no bar for a later arm (the next pre-run picks one; +2 here would mean 27/30).
- Solved: 25. 15 on a cold turn (turn 0 of an episode; 14 of those on the very first turn), 10 on a feedback turn: url_normalize, sexpr_eval, mustache, proto_wire, rpn_infix, digit_kth, persistent_multiset, dlog, monthly_rule, root_digits. Slowest solves: sexpr_eval 12 turns, root_digits 11.
- Hard-coding check: visible passes 25 = fresh passes 25; `agent.py --regrade` on the JSONL gives 25. All 30 tasks have a fresh seed (no no_fresh).
- Stops, 52 episodes: 25 `pass`, 12 `max_turns`, 14 `repeat_error`, 1 `repeat_code`, no `task_budget`. 29 of 131 turns ended at the 12,288-token cap (22%; v2: 16 of 97).
- One run, 30 tasks, no spread estimate. The ~11% opening-draw flip rate (5 of 44) is from the v2 pair, not a v3 measurement; whether +2 on 30 tasks is distinguishable from sampling noise is open, so the next pre-run states its bar (or repeats on sometimes-solved tasks) before its run.
- Cap hits by task (29 of 131 turns): 24 are on the five unsolved tasks (farthest_vertex 9 of 14 turns, mod_sqrts 6 of 14, forth_vm 4 of 13, billiard 3 of 13, hist_calendar 2 of 13), 5 on solved tasks, none on a passing turn. Only farthest_vertex is mostly cap-limited (9 of 14 turns); the other four are under half, so the cap alone does not explain their failures. Every unsolved task has at least 2 cap turns, so a reasoning-budget arm could touch all five, but a large gain from it is not supported by these counts.
- Cost: 3.61 h GPU (estimate was 5-10 h; the 30-task runs cost 2.8-4.5 h so far); `gtt_model_gib` 22.74, peak 28.34 GiB. The run log (`/tmp/v3/run.log`) is buffered when stdout goes to a file; read the JSONL for progress.

## Small-model loop v3: a second model as fixer (pre-run)

Stated before the run (measure skill step 6; committed and pushed before the preflight and any server start, results empty). The loop stays the Roadmap 2 default whatever this gives; v3 numbers tune nothing (no prompt, K, E, budget or task edits from them).
- Question: does a second model on the 5 stored v3 failures (forth_vm, farthest_vertex, mod_sqrts, hist_calendar, billiard) add tasks beyond what a same-protocol Qwen pass adds?
- Code: `agent.py --fix-from <loop jsonl> --tasks id,id`. Each episode starts at turn 0 from the stored failure: the last turn with a code block of that task in `qwen-v3-agent-k4e4-vk-np4.jsonl` (its code and its test error; the prompt is the loop's feedback prompt). The stored code counts as already tried (resubmitting it ends the episode as `repeat_code`), the stored error as the previous error (an identical new error ends it as `repeat_error`, as in the loop). Grading, the fresh seed 104729 and the K, E and budget stops are unchanged. Sampling seeds are 2000 + 10 x episode + turn (loop: 1000 + ...), so a Qwen fix pass does not replay the draws of the original run. Selftests exit 0 (`agent.py --selftest`, `run.py --selftest --set v3`), including a scripted fake-model case for fix mode.
- Arms, one model resident at a time, `--set v3 -k 4 -e 2 --task-budget 98304 --parallel 4`, same prompts, sampling (temperature 0.6, top_p 0.95, top_k 20), `reasoning_budget_tokens` 8192 inside `max_tokens` 12288, Vulkan, `scripts/llm-serve.sh start <qwen|laguna> vk 65536 4`, llama.cpp 836d57176 `build-vk`:
  - A: Laguna XS 2.1 as fixer (`--model laguna-xs-2.1`), label `laguna-v3-fix-k4e2-vk`.
  - B: Qwen3.6-35B-A3B in fix mode, same code and settings, label `qwen-v3-fix-k4e2-vk`. Control for "more Qwen effort from the stored failure". Order: A first (Qwen is already stopped), `llm-8081` stopped, preflight, then B; Qwen is never resident when Laguna loads. `--gtt-baseline` = the preflight `gtt_used` before each start.
- Baseline: the stored loop-alone 25/30 (25c286d, `qwen-v3-agent-k4e4-vk-np4`), not rerun. An arm's gain is the number of the 5 it solves on the fresh seed, so the total is 25 + gain out of 30.
- Metric: per arm, solved out of 5 (fresh seed; `agent.py --regrade` on the jsonl must match the summary). Also recorded: completion tokens, turns, wall time, `gtt_model_gib`, stop reasons.
- Bar: A solves >= 3 of the 5 AND A solves >= 2 more than B. Otherwise not confirmed and the fixer role is dropped (Laguna stays a dropped second sampler, v1). Confirmed means 28+/30 with A, and that Laguna did what a second Qwen pass did not. 5 tasks, one run per arm: a confirmed result is a lead, not a measurement of the rate (per-seed sampling is not reproducible under 4-slot batching, ~11% opening-draw flips on v2); a miss by one task is a miss.
- What the run buys besides the question: B shows how many of the 5 more Qwen effort from the stored failure recovers (K=4 E=2 from the last code), which sets the fixer's cost-free alternative for any later arm.
- Cost: at most 5 x 2 x 4 = 40 turns per arm (<= 491,520 completion tokens; the 98,304 task budget equals 8 full-cap turns, so K x E binds first). At ~413 s per turn per slot with 4 tasks in flight and the 5th after, <= ~1.8 h per arm worst case, ~1-1.5 h expected; both arms ~2-3.5 h GPU plus two model loads. `llama-deepseek` stays inactive (preflight READY before each load); DeepSeek as fixer is not part of this run.

Result (run 2026-10-06; preflight READY at 5.8 GiB GTT used before each load, `llama-deepseek` inactive; `llm-8081` stopped after each arm, GTT 5 GiB at the end). Pre-run commit: b6bf2d0.

```
question:  does a second model on the 5 stored v3 failures add tasks beyond a same-protocol Qwen pass?   stated in: b6bf2d0
baseline:  qwen-v3-agent-k4e4-vk-np4   solved 25/30 (stored, not rerun)
A Laguna fixer   (laguna-v3-fix-k4e2-vk)   solved 1/5 -> 26/30 total   169,750 tokens, 17 turns, 1,759.5 s, gtt_model_gib 22.30
B Qwen fix mode  (qwen-v3-fix-k4e2-vk)     solved 3/5 -> 28/30 total   236,304 tokens, 22 turns, 3,150.5 s, gtt_model_gib 22.47
bar:       A >= 3 of 5 AND A >= B + 2
verdict:   A = 1 < 3 and A = B - 2 -> NOT CONFIRMED. The Laguna fixer role is dropped.
```

- Per task (A / B): forth_vm fail / SOLVED, farthest_vertex SOLVED / SOLVED, mod_sqrts fail / SOLVED, hist_calendar fail / fail, billiard fail / fail. Both arms solved farthest_vertex on turn 0 of episode 0; B alone solved forth_vm (7 turns, after a `max_turns` episode) and mod_sqrts (4 turns). `agent.py --regrade` gives A 1 and B 3, matching both summaries; visible passes equal fresh passes.
- Stops, 4 and 5 tasks x 2 episodes: A 7 `repeat_error`, 1 `repeat_code`, 1 `pass` (9 episodes, one task needed one); B 3 `pass`, 3 `repeat_error`, 2 `max_turns`. A used no turn at the 12,288 cap (0 of 17); B had 4 of 22 (all no-code turns).
- A stopped early more than B: 3 of A's 9 episodes and 2 of B's 8 ended after one turn on `repeat_error` (the first fix hit the same test error as the stored failure; forth_vm both episodes and billiard episode 1 for A, billiard both episodes for B). The loop's stop rule applies to the stored error as written in the pre-run, so this is part of the protocol, not a bug; but A's 17 turns vs B's 22 means A had less feedback to work with.
- B's 3 of 5 does not show a fix-mode effect: the original run failed these tasks on its own draws, and the same-model rerun with new seeds from the last code recovered three. That is the noise-plus-more-effort reading the control was there to measure, and it is the reading the bar was set against. It also means the 25/30 baseline is not a ceiling for Qwen alone: 28/30 here is the stored 25 plus B's gain, not a new loop-alone figure. One run per arm, 5 tasks.
- Consequence: no second-model fixer. If a later pre-run wants a second model, the control is "more Qwen episodes from the stored failure", which recovered 3 of 5 here at 236k tokens. v3 tunes nothing.
- Cost: 0.49 h (A) + 0.88 h (B) = 1.37 h of runs plus two loads (estimate 2-3.5 h).

## Roadmap (active)

1. Orchestrator + SQLite memory: structured verdicts (finding, file, severity, accepted/rejected + reason) retrieved into prompts. DeepSeek as an hourly adversarial reviewer of diffs; static system/rules/repo summary first in the prompt, changing material last, for cache hits.
2. Small-model agentic loop: Qwen3.6-35B-A3B in a reason -> act -> observe -> retry cycle with hard feedback, not single-shot sampling.
   - Done: best-of-N harness, `bench/loop/run.py` (loop-v0 1035d5e: best-of-4 kept; loop-v1 10fc559: Laguna as a second sampler dropped). It samples independently and never shows the model its test failure, so it is the baseline, not the loop.
   - Kept 2026-10-06: `bench/loop/agent.py`, one model, K=4 E=4: 12/12 vs best-of-16 10/12 at 19.7% of the tokens (see the v1 agentic loop results; regex_match's pass was a fresh sample, not feedback). Confirmed 2026-10-06 on 30 unseen v2 tasks: 29/30 vs early-stop best-of-16 23/30 at 55.7% of the tokens (pre-run 27e2be7; 4 of the 6 extra tasks were feedback wins). Laguna as a fixer on the 5 stored v3 failures: 1/5 vs Qwen fix-mode control 3/5, not confirmed, role dropped (v3 fixer section). Next: another role or memory arm, with its own pre-run commit. Design: Action at first is submitting `solution.py`; the harness runs the tests in bwrap and feeds the failure back. Critic = tests and compiler, which the model cannot write to (bwrap, `_banned()`). Context per turn: task + current code + latest failure, no chat history (fits a 16k slot). Brakes: max K turns, a token budget per task, stop on a repeated error or code hash. Final grade on a fresh oracle seed the loop never saw, so hard-coding a fed-back case does not count (27 of 30 v1 tasks have a single `random.seed(N)`; the other 3 are flagged).
   - Kept only if it beats independent best-of-N at equal tokens; K and the threshold go in its pre-run commit. Baseline: best-of-16 on the 12 weak v1 tasks (pre-run 52f0a05).
   - Later, each with its own pre-run commit: tools beyond submit-code; a second small model in a role (fixer or second sampler; two small models fit in GTT but need a deliberate change to the one-model guard); DeepSeek as judge only as a separate pass, since it cannot be resident beside Qwen (~85 + ~23 GiB = all 108 GiB of GTT). Tests outrank any judge.
3. One timed LoRA job, kept only if it beats the base model on held-out tasks. Verdicts are not training pairs; a dataset has to be built. Risks: model collapse, bad judge.
4. DaVinci Resolve Studio in a container: davincibox chosen; licence type and install deferred.
5. Server-class hardware research, criterion bandwidth per dollar with confirmed software support.
