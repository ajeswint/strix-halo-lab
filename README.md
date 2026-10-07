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

`bench/loop/` (live copy `/data/bench/loop`): `tasks.py` holds 20 held-out Python tasks written for this set (spec, unit tests, reference solution); none was used for prompt iteration or as a few-shot example. `run.py --selftest` checks that every reference passes and an empty solution fails every task; a brute-force cross-check of the tie-break tasks (lis, knapsack, shortest_path) found 0 mismatches in 1,200 random cases. `run.py --label L -n 4` samples 4 candidates per task from `llm-8081` and grades them only by the tests, each candidate in bwrap (no network, read-only `/usr`, scratch dir only, 4 GiB address-space cap, 60 s timeout; since 2026-10-07 the oracle reaches the sandbox over stdin after the solution is imported, plus a static deny-list, see Grader hardening). Results go to `bench/loop/results/L.jsonl` (per sample, code included) and `L.summary.json`, which includes `gtt_peak_gib` sampled every 1 s during the run; pass preflight's pre-load `gtt_used` as `--gtt-baseline` to also get `gtt_model_gib` (peak minus idle). loop-v0 predates this; its GTT figures below come from a shell sampler.

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

## Small-model loop v3: DeepSeek V4 Flash as fixer (pre-run)

Stated before the run (measure skill step 6; committed and pushed before the preflight and before `llama-deepseek` starts, results empty). Follows the Laguna fixer result (ebf9923: A 1/5, Qwen control 3/5). The user said yes to starting DeepSeek on 2026-10-06. v3 numbers tune nothing.
- Question: does DeepSeek V4 Flash IQ2_M, run through the same fix mode on the same 5 stored v3 failures, add tasks beyond what the same-protocol Qwen pass (arm B, 3/5) added?
- Arm C: `agent.py --set v3 --tasks <the 5 ids> --fix-from results/qwen-v3-agent-k4e4-vk-np4.jsonl -k 4 -e 2 --task-budget 98304 --parallel 1 --model deepseek-v4-flash --api http://127.0.0.1:8080 --label deepseek-v3-fix-k4e2-hip`. Same prompts, sampling (temperature 0.6, top_p 0.95, top_k 20), `reasoning_budget_tokens` 8192 inside `max_tokens` 12288, fix-mode seeds 2000 + 10 x episode + turn and stop rules as arms A and B. Differences, all forced by the model: `llama-deepseek.service` (HIP build-hip, UD-IQ2_M, `-np 1`, ctx 65536, so one 64k slot and tasks run one after another), alias `deepseek-v4-flash`. Held fixed rather than set to DeepSeek's or orch.py's own sampling (0.2, budget 6144), so C is comparable with A and B.
- Baselines, reused and not rerun: A `laguna-v3-fix-k4e2-vk` 1/5; B `qwen-v3-fix-k4e2-vk` 3/5 (forth_vm, farthest_vertex, mod_sqrts); loop-alone 25/30. hist_calendar and billiard were solved by no arm, so at most 2 tasks can be added beyond B.
- Metric: C solved out of 5 on the fresh seed 104729; `agent.py --regrade` on the jsonl must match the summary. Also recorded: tokens, turns, wall time, `gtt_peak_gib` and `gtt_model_gib` (baseline = the preflight `gtt_used`), stop reasons, completion tokens per turn, seconds per turn. Total of 30 = 25 + C's gain.
- Bar (same shape as the Laguna bar): C solves >= 3 of the 5 AND C solves >= 2 more than B, which with B = 3 means 5/5, i.e. forth_vm, farthest_vertex, mod_sqrts, hist_calendar and billiard. Otherwise not confirmed and the DeepSeek fixer role is dropped. A 4/5 is recorded as a lead, not a confirmation: one run, 5 tasks, B's own 3/5 is one draw (per-seed sampling is not reproducible under batching), so +1 is inside the noise.
- What the run buys besides the question: seconds and tokens per turn for DeepSeek on this task shape (the README's 11-16 t/s at depth gives the estimate below), its GTT peak with a 64k slot, and whether hist_calendar and billiard are solvable by a stronger model at all or are limited by the tests/spec.
- Memory safety (2026-10-04 OOM: a second model loaded beside DeepSeek): Qwen and Laguna are not resident (`llm-8081` inactive, GTT 5 GiB, a non-llama client holds ~5.8 GiB). `scripts/preflight.sh` on shard 1 of the DeepSeek GGUF must print READY right before the start (needs MemAvailable and free GTT >= 84.7 + 16 GiB). The start is `sudo systemctl start llama-deepseek`, run by the user. While it is up nothing else loads: no `llm-serve.sh`, bench, training or second llama process; graders run in bwrap with a 4 GiB address-space cap and one at a time (`--parallel 1`). The expected peak is ~86 GiB of 108 GiB GTT plus the ~5.8 GiB client, leaving ~16 GiB of GTT and ~24 GiB of MemAvailable for everything else, so no Chrome, Unreal or builds during the run. It is stopped after the arm (`sudo systemctl stop llama-deepseek`); it is not enabled at boot.
- Cost: at most 5 x 2 x 4 = 40 turns (<= 491,520 completion tokens; K x E binds before the 98,304 budget). At ~11-15 t/s and ~10k completion tokens per turn (A and B averaged 10.0k and 10.7k), ~11-15 min per turn plus prefill: 17-30 turns (A and B used 17 and 22) is ~3-7.5 h, ceiling ~10 h (40 turns x 15 min); one 86 GiB load. The GPU is not usable for other work for that time.

Result (run 2026-10-06/07; preflight READY at 5.8 GiB GTT used before the start, no other llama process, `llama-deepseek` started by the user, `/health` ok before the run). Pre-run commit: 41717a1.

```
question:  does DeepSeek V4 Flash IQ2_M as fixer add tasks beyond the same-protocol Qwen pass?   stated in: 41717a1
baseline:  B qwen-v3-fix-k4e2-vk 3/5 (reused);  A laguna-v3-fix-k4e2-vk 1/5;  loop-alone 25/30
C DeepSeek fixer (deepseek-v3-fix-k4e2-hip)   solved 5/5 -> 30/30 total   112,477 tokens, 12 turns, 7,447 s (2.07 h), gtt_model_gib 85.67 (peak 91.47)
bar:       C >= 3 of 5 AND C >= B + 2 (= 5/5)
verdict:   5 >= 3 and 5 = 3 + 2 -> CONFIRMED by the stated bar. One run, 5 tasks: a lead worth a held-out replication, not a rate.
```

- Per task: forth_vm 4 turns, farthest_vertex 1, mod_sqrts 2, hist_calendar 3, billiard 2, every task solved in episode 0 (stops: 5 `pass`; no `repeat_error`, `repeat_code`, `max_turns` or no-code turn; 0 of 12 turns at the 12,288 cap). hist_calendar and billiard were solved by no earlier arm (loop-alone, Laguna fixer, Qwen control), so C added 2 tasks beyond B and 4 beyond A. `agent.py --regrade` gives 5, matching the summary; visible passes 5 = fresh passes 5.
- Cost per turn: 620 s mean (max 741 s), 9,373 completion tokens mean, ~15.5 t/s, against ~10.7k tokens and 408 s per turn for the Qwen control (mean `gen_s`, 4 slots in parallel, ~26 t/s per slot). C used 112k tokens against 236k for B and took 2.07 h against 0.88 h: fewer tokens and turns, 2.4x the wall time, and it needs the whole 108 GiB GTT budget (86 GiB model, one 64k slot, ~91.5 GiB peak with the ~5.8 GiB client), so it can only run sequentially after Qwen is unloaded.
- Oracle-read check (after the audit in `~/testing-strategy-audit.md` found the grader writes `test_solution.py` beside `solution.py`): a probe confirms a solution can read it, but no code block in arm C, nor in any of the 865 stored solutions across all results files, reads the test file, the cwd or frames (`builtins` hits are a Forth dictionary variable). The two newly solved tasks use no imports beyond `fractions` and `math` and no literal case lists. Grader hardening is a separate change after this run; it does not touch these numbers.
- Reading, not rate: the stored failures were Qwen's own last attempts, so C sees code and an error from a weaker solver and gets two episodes and four turns; five tasks, one run, a sampler whose draws flip ~11% of the time under batching. The bar was set at B + 2 with B = 3, so it needed all five; it was met. v3 is now exhausted as a headroom set (25 + 5 = 30/30 with the two-model pipeline), so a replication needs a new held-out set (v4) and a loop-alone baseline on it; a result there, not this one, is what would put a DeepSeek fixer stage into the loop. v3 numbers tune nothing.
- Memory safety: no OOM or swap pressure. GTT 91.1-91.5 GiB, MemAvailable 24-26 GiB, swap 1.4-2.7 GB of 8 GB, flat.

## Grader hardening (pre-run)

Stated before the implementation (measure skill step 6; this commit changes only the README, `bench/loop/run.py` is untouched). Follows the audit check above: `run.grade` writes `test_solution.py` into the sandbox dir next to `solution.py`, so a solution can `open()` the oracle (probe: 5,884 chars read). No GPU, no server.
- Question: can the grader close that read, and the obvious ways around it, without changing any stored pass/fail? It is a tripwire, not isolation: the solution and the oracle still share one Python process.
- Design:
  1. The oracle is not on disk. The sandbox runs `python3 -E -s -c <harness>`; the harness imports `solution` first, prints a ready line, and only then the parent writes the oracle (plus a fresh random nonce) to the child's stdin. The harness reads fd 0 with an `os.read` bound before the import, compiles the oracle, runs it against `from solution import *`, and prints the nonce on success. A solution that reads stdin at import blocks (nothing is written yet) and times out.
  2. Pass = exit code 0 AND the nonce in stdout. This also closes `sys.exit(0)` / `os._exit(0)` at import or call time, which passed before (exit code 0).
  3. A static check on the solution source runs in the parent before the sandbox starts, over `ast` plus `symtable`:
     - modules: `os posix io _io builtins inspect gc traceback linecache ctypes importlib runpy pickle marshal code codeop pdb bdb trace tracemalloc subprocess shutil pathlib socket signal __main__`;
     - builtin names, flagged only where `symtable` resolves them to the builtin (a name the solution itself binds is its own variable): `eval exec compile open getattr setattr delattr vars globals locals dir __import__ breakpoint input help exit quit`, and `__builtins__` always;
     - attributes (also as `from m import <attr>` aliases, and as an exact or, for the long ones, substring match in string constants, which covers `getattr(x, "f_back")`, `"{0.f_back}".format(f)`): the frame/code/traceback family (`_getframe _current_frames currentframe f_back f_globals f_locals f_code f_builtins f_trace gi_frame gi_code cr_frame cr_code ag_frame ag_code tb_frame tb_next co_consts co_code co_names co_filename co_varnames __code__ __globals__ __closure__ __builtins__`), `__subclasses__ __bases__ __mro__ __dict__ __loader__ __spec__ __getattribute__ __reduce__ __reduce_ex__`, `settrace setprofile gettrace getprofile get_objects get_referrers get_referents`, `stdin __stdin__ modules`;
     - an assignment to a denied builtin name whose right-hand side loads a denied name (`vars = vars`) is flagged; `sys` itself stays allowed.
     A hit returns `(False, "grader: forbidden ...")`, which the loop feeds back like any other error.
  4. Tracebacks keep their shape: the oracle is registered in `linecache` under `<oracle>` so a failing assert still prints its source line, and harness frames are skipped.
- Read before the list was fixed (all 870 stored rows with code, 864 distinct, across `bench/loop/results/*.jsonl`):
  - `import sys` in 62 distinct solutions; the only attribute used is `sys.setrecursionlimit` (35 uses), so `sys` stays allowed and only its introspective attributes are denied.
  - `vars` (6 occurrences, a local variable in v1_19_bool_equiv) and `compile` (8 occurrences, a user-defined function in v1_01_regex_match) are always the solution's own bindings, never the builtins. A flat name ban would flip those rows; hence the `symtable` rule. `builtins` (22 occurrences, forth_vm and sexpr_eval) is a dictionary variable; only the module `builtins` is denied. `.compile` is `re.compile` throughout.
  - The import scan shows no stored solution importing a denied module (the imports are `re heapq math sys collections fractions typing datetime calendar bisect itertools functools random string`). Attributes and string constants were only sampled, and the references were not scanned; the regrade below is what proves no row flips.
- Attack probes in `run.py --selftest` (reference solution + the attack; each must FAIL grading, on every set v1, v2, v3): `open()` of the oracle path; `import os` + `os.listdir`; `sys._getframe`; `inspect.stack()`; frame walk through `__import__("sys")`; `vars(...)`; `getattr(x, "f_back")`; `"{0.f_back}".format(f)`; `globals()["__builtins__"]`; `vars = vars`; `sys.exit(0)` at import. Plus raw probes with the static check switched off, run with a 5 s timeout: a stdin read at import must not get the oracle (it times out); a dump of the sandbox dir, `/proc/self/cmdline`, `/proc/self/environ` and `/tmp` must contain no `test_solution.py` and not the oracle's sentinel text.
- Not closed, stated so the tripwire is not read as a wall: a solution can still forge the ready line, or walk frames through a path the deny-list did not name (string-built attribute names that dodge both the name and the substring rule, `type`/`object` tricks), or exhaust the process. The oracle's source constants are visible to any code that reaches a frame. Real isolation needs a second process for the oracle; not done here.
- Regrade bar, stated now: every stored jsonl under `bench/loop/results` is regraded with the new grader (each row with code against its set's visible tests; rows that passed also against the fresh seed 104729 where the file is a loop run). The per-row visible pass/fail must equal the stored `passed` for all rows, so every count is unchanged: loop-alone 25/30 (v3) and 29/30 (v2), v2 best-of-16 23/30, fixer arms A 1/5, B 3/5, C 5/5 (30/30 total), and the run.py files' pass@1 and best-of-N. Any flip stops the work: it is listed by task, with the solution and the reason, for the user's review; no count is edited.
- Cost: CPU only (about 870 sandbox runs, a few per second in parallel).

Result (implementation ad05319, pre-run c821b3d; run 2026-10-07, CPU only, no server started):

```
question:  can the grader close the oracle read and the obvious ways around it with no stored pass/fail changing?   stated in: c821b3d
selftest:  run.py --selftest exit 0 on v0, v1, v2, v3 (every ref passes, every empty solution fails, 20 attack probes + 3 raw probes fail, 3 controls pass); agent.py --selftest exit 0 on v0-v3
leak:      no test_solution.py in the sandbox dir; a dump of /w, /tmp, /proc/self/cmdline and /proc/self/environ finds no oracle text (positive control: a planted copy is detected)
regrade:   regrade_stored.py: 870 rows with code, 11 files, 0 row flips, 0 fresh flips, every count unchanged -> bar met
```

- Counts after the regrade (`bench/loop/regrade_stored.py`; old = stored, new = regraded): loop-alone v3 25/25, v2 29/29, v1 weak12 12/12; v2 best-of-16 23/23; fixer arms A 1/1, B 3/3, C 5/5 (30/30 total); run.py files pass@1 and best-of-N identical to 4 decimals (qwen v0 0.8625/1.0, qwen v1 0.6833/0.9333, laguna v1 0.45/0.6667, qwen v1 weak12 0.4375/0.8333).
- What changed for the loop: a solution that trips the deny-list gets `grader: forbidden ...` as its error text; failing asserts still show their source line (`File "<oracle>"`); any exit 0 without the nonce (e.g. `sys.exit(0)` at import) is a fail, where it used to pass.
- Still a tripwire: see "Not closed" above. `bench/loop/regrade_stored.py` is the check to rerun after any change to `run.py`'s grader; it exits 1 on any flip.

## Small-model loop v4: probe of 10 fresh tasks (pre-run)

Stated before the run (measure skill step 6; this commit changes only the README, results empty, no GPU touched). Follows the DeepSeek fixer result (2512b38: 5/5 on the stored v3 failures, 30/30 total), which has no held-out replication, and the grader hardening (49f460c). Not a keep/drop; its numbers tune nothing (no prompt, K, E, budget or task edits from it).
- Question: does loop-alone Qwen (`agent.py` K=4 E=4) leave enough failures on fresh tasks, on the hardened grader, for a DeepSeek-fixer replication to be meaningful? The replication needs >= 5 or so stored failures to feed the fixer; v3 left 5 of 30, v2 left 1 of 30. A probe of 10 settles whether v4 is hard enough before 20 more tasks are written and 3-4 GPU hours are spent on them.
- Tasks: `bench/loop/tasks_v4.py` (commit c7b54f4), 10 new tasks written 2026-10-07, modelled on the v3 failures (long specs, exact edge rules, tie-breaks, big numbers): v4_01 json_patch (RFC 6902 subset, pointer escapes, canonical indexes, JSON equality), v4_02 mini_asm (two-pass assembler: expression parser, `.equ` cycles, `.org`/`.space`/`.align` evaluation order, relative branches), v4_03 dst_zone (wall time to UTC with gaps, folds, southern-hemisphere rules, `next_transition`), v4_04 rr_priority (preemptive priority + round robin, same-instant ordering rules, times to 10^12), v4_05 hm_infer (Hindley-Milner with let/letrec, canonical variable names), v4_06 phi_blocks (iterated dominance frontier, entry in its own frontier, 30,000 nodes), v4_07 sub_game (subtraction games with piles to 10^18, winning moves), v4_08 lattice_poly (simple-polygon validation, Pick's theorem), v4_09 dec_round (decimal strings, 7 rounding modes, huge exponents), v4_10 bracelets (proper colorings up to rotation and reflection, mod any m, n to 10^12). No v0-v3 id or entry-point name is reused. None was used for prompt or loop iteration. Every test file has exactly one `random.seed(N)` line (N = 4001-4010), and its seeded random cases are checked against an oracle built differently from the reference (tick simulation vs event skipping, Algorithm W vs levels, node-removal dominators vs Cooper-Harvey-Kennedy, `datetime` vs own calendar, `decimal` vs own digits, orbit enumeration vs Burnside). Prompts are 1,054-3,102 chars (v3: up to 2,859). Every reference passes the visible seed, `random.seed(104729)` and seeds 1-5, and every empty solution fails; each reference grades in <= 0.8 s. `run.py --selftest` and `agent.py --selftest` exit 0 on v0, v1, v2, v3 and v4; `run.py --set v4` is registered. The file is written so tasks 11-30 (seeds 4011-4030) append at its marker without touching the first 10.
- Arm: `bench/loop/agent.py --set v4 --tasks v4_01_json_patch,v4_02_mini_asm,v4_03_dst_zone,v4_04_rr_priority,v4_05_hm_infer,v4_06_phi_blocks,v4_07_sub_game,v4_08_lattice_poly,v4_09_dec_round,v4_10_bracelets -k 4 -e 4 --label qwen-v4-probe-agent-k4e4-vk-np4 --gtt-baseline` followed by the preflight `gtt_used`: up to 4 episodes of up to 4 turns, failures fed back, task budget 196,608 completion tokens, `--parallel 4`, as the v3 baseline.
- Fixed settings, as v3: Vulkan, `scripts/llm-serve.sh start qwen vk 65536 4`, temperature 0.6, top_p 0.95, top_k 20, `reasoning_budget_tokens` 8192 inside `max_tokens` 12288, prompt suffix from run.py, llama.cpp 836d57176 `build-vk`, Qwen3.6-35B-A3B UD-Q4_K_XL, one model resident, sampling seeds 1000 + 10 x episode + turn, the fresh seed 104729. Difference from every earlier loop run: the hardened grader (oracle over stdin, nonce, static deny-list), so this is its first live run.
- Metric: solved = the passing code also passes with `random.seed(104729)` (summary `solved`, out of 10); `agent.py --regrade` on the JSONL must give the same count. Also recorded: completion tokens, turns, wall time, `gtt_model_gib`, stop reasons, turns at the 12,288-token cap, and the number of turns whose error text begins `grader: forbidden` (does the model trip the deny-list on legitimate code?).
- Bar, stated now: solved <= 8/10 (at least 2 unsolved) means v4 has room: tasks 11-30 are written and only those 20 are run with the same settings and code, and the probe's 10 become the first 10 rows of the 30-task v4 loop-alone baseline (v4_01-10 may not be edited in between, or the probe is void as baseline). Solved >= 9/10 means v4 is too easy at this difficulty: the solved tasks are made harder (named in the next pre-run) and re-probed, and nothing else runs. A hit of the bar says only that v4 is hard enough to probe further, not a failure rate: with v3's rate (5 of 30) the chance of >= 2 failures in 10 is about 0.5, and these tasks are meant to be harder but that is not measured.
- What the run buys besides the question: the first third of the v4 loop-alone baseline arm (reused in the full 30, not rerun), the failure texts and stored last attempts of whatever it leaves unsolved (the fixer arm's inputs), the cap-hit rate and seconds per turn on the longer v4 prompts, and a count of deny-list trips.
- Memory safety: `llama-deepseek` and `llm-8081` are inactive (GTT ~5.8 GiB, a non-llama client). `scripts/preflight.sh /data/models/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf` must print READY right before `scripts/llm-serve.sh start qwen vk 65536 4`; the server is stopped after the arm. No Chrome or builds during the run.
- Cost: at most 10 x 16 = 160 turns (K x E binds before the token budget). v3 ran 131 turns in 3.61 h (~99 s of wall per turn at 4 slots), so ~1-2.5 h expected if the tasks need 4-8 turns each, ceiling ~5 h with the tail where fewer than 4 tasks are left. Needs the user's yes before the preflight.

Result (run 2026-10-07 05:05-08:23 CDT, session 4; preflight READY at 5.8 GiB GTT used before the start, `llama-deepseek` inactive; `llm-8081` stopped after, GTT 5.7 GiB). Pre-run commit: 1ac0423; code and tasks unchanged since (`git diff 1ac0423 HEAD -- bench/loop` empty). First live run of the hardened grader. Started as `scripts/llmctl.py run -- python3 bench/loop/agent.py ...` inside an ACTIVE qwen session (`--ctx 65536 --np 4`), then `--regrade` inside the same session.

```
question:  does loop-alone Qwen K=4 E=4 leave enough failures on 10 fresh v4 tasks?   stated in: 1ac0423
arm:       loop K=4 E=4 (qwen-v4-probe-agent-k4e4-vk-np4)   solved 4/10 (fresh seed)   1,198,419 completion tokens, 112 turns, 11,853 s (3.29 h)
rule:      solved <= 8/10 -> v4 has room, write tasks 11-30, run only those 20; >= 9/10 -> too easy, harden the solved tasks and re-probe
verdict:   4 <= 8 -> v4 has room: 6 unsolved tasks. Probe rows become the first 10 of the 30-task baseline (v4_01-10 stay frozen). Not a keep/drop.
```

- Unsolved (6): mini_asm (16 turns, 196,608 tokens: the whole task budget), dst_zone (16), rr_priority (14), hm_infer (12), phi_blocks (14), dec_round (16). Solved (4): json_patch (episode 2, turn 2; 11 turns), sub_game (episode 2, turn 1; 9 turns), lattice_poly (first turn), bracelets (episode 0, turn 2). 3 of 4 solves needed feedback.
- Hard-coding check: visible passes 4 = fresh passes 4; `agent.py --regrade` gives 4 tasks with fresh >= 1. All 10 tasks have a fresh seed.
- Stops, 32 episodes: 4 `pass`, 19 `max_turns`, 9 `repeat_error`. Grader deny-list: 0 turns began `grader: forbidden`, so the hardened grader did not reject legitimate code here.
- **mini_asm is a length failure, not a wrong-code failure**: all 16 turns ended at the 12,288-token cap (`finish` = length), so no code block was ever produced. Its "fail" says the task is not solvable inside this reasoning budget, not that feedback could not fix it. Cap hits overall: 33 of 112 turns (29%; v3 22%, v2 16%); by task: mini_asm 16 of 16, phi_blocks 5 of 14, dec_round 5 of 16, dst_zone 2 of 16, rr_priority 2 of 14, sub_game 2 of 9, hm_infer 1 of 12, json_patch / lattice_poly / bracelets 0; none on a passing turn. Excluding mini_asm the cap hit 17 of 96 turns (18%).
- Failed-turn error texts (107 turns): 62 `Traceback` (wrong code or a crash on a test), 33 `no code block` (the cap truncations, mini_asm 16 of them), 10 `timeout`.
- Stored failures for a fixer arm: 6 tasks with a last attempt, but mini_asm has no coded turn at all, so `stored_failure` has nothing to feed for it; 5 usable (dst_zone, rr_priority, hm_infer, phi_blocks, dec_round) if the replication ran on this probe alone.
- Cost: 3.29 h GPU against 1-2.5 h expected (ceiling ~5 h); 112 turns of the 160 maximum; ~106 s of wall per turn at 4 slots (v3 ~99 s); mean `gen_s` 357 s per turn. `gtt_model_gib` 22.54, peak 28.34 GiB. Memory cap: the `agent.py` run (parallel 4, bwrap graders) peaked at `memory.peak` 145 MiB under the 8,192 MiB cap, the regrade at 39 MiB, so the cap has about 55x headroom and no kill is expected at this shape. One run, 10 tasks, no spread estimate.

## Small-model loop v4: tasks 11-30 and the 30-task baseline (pre-run)

Stated before the run (measure skill steps 1-6; this commit changes only the README, results empty, no GPU touched, nothing loaded, invited or called while writing it). Follows the v4 probe (result 4e3de27: 4/10 solved, bar met, 6 unsolved). Not a keep/drop; its numbers tune nothing (no prompt, K, E, budget, task or grader edit from it).
- Question: how many of the 30 v4 tasks does loop-alone Qwen (`agent.py` K=4 E=4) leave unsolved, and how many of those leave a usable stored failure, as the input pool for the DeepSeek-fixer replication (v3 fixer 5/5, 2512b38, one run on 5 failures)?
- Tasks: `bench/loop/tasks_v4.py`, tasks 11-30 appended in commit 8497590 (seeds 4011-4030, one `random.seed(N)` line each), written 2026-10-07 by four parallel writers, no model run behind them, none used for prompt or loop iteration, difficulty not adjusted from the probe or any run.: v4_11 hdlc_unframe (HDLC stream framing, escapes, aborts, CRC), v4_12 markov_run (Markov-algorithm interpreter and rule-line parser), v4_13 load_properties (Java `.properties`, continuations, `\u` surrogates), v4_14 ustar_entries (tar header checksums, octal fields, prefix join), v4_15 msgpack_loads (MessagePack decoder, strict rules, hostile length headers), v4_16 ifc_calendar (International Fixed Calendar conversions, intercalary days), v4_17 timer_sched (timers with cancels and mute windows, counts to 10^12, same-instant order), v4_18 book_rooms (online room booking with cleanup gaps and shift flex to 10^9), v4_19 leap_clock (elapsed seconds vs UTC labels with +1/-1 leap seconds), v4_20 list_schedule (longest-chain priority list scheduling, zero-duration cascades), v4_21 kth_coprime (k-th integer coprime to n, n to 10^12, k to 10^18), v4_22 bounded_compositions (bounded compositions mod a prime, Lucas, n to 10^15), v4_23 two_square_reps (sums of two squares, representation count and pairs, n to 10^12), v4_24 fib_edges (digit count and first/last k digits of F(n), n to 10^18), v4_25 capped_part_count (partitions with per-size caps mod m, n to 10^18), v4_26 rect_union (area, perimeter and components of a rectangle union, coordinates to 10^9), v4_27 mst_census (MST weight, exact count and lexicographically smallest tree on a multigraph), v4_28 pal_range (longest palindrome per range query with tie-breaks), v4_29 maximal_runs (all runs of a string with smallest period), v4_30 cocircular (densest exact circle through integer points). No new id or entry-point name is reused from v0-v4: all 140 ids are unique and none of the 20 new entry-point names occurs in an earlier set (the older pairs `glob_match` and `justify`, v0 against v2, predate this work and are untouched). Verified before the commit: every reference passes the visible seed, `random.seed(104729)` and seeds 1-5, every empty solution fails, each reference grades in <= 0.4 s (limit 0.8 s), prompts are 1,437-3,180 chars, no reference trips the deny-list, `run.py --selftest` and `agent.py --selftest` exit 0 on v0-v4 (v4 = 30 tasks), seeded random cases are checked against an oracle built differently from the reference. One cold review found one defect (v4_19's prompt said "tuples" for `leaps` while a test passes a list entry; the prompt wording was corrected, nothing else). v4_01-10 and `run.py`/`agent.py` are byte-identical to the probe: `git diff --numstat 4e3de27 HEAD -- bench/loop` shows only `tasks_v4.py`, 4866 added, 0 deleted.
- Baseline (reused, not rerun): the probe rows `qwen-v4-probe-agent-k4e4-vk-np4` (4e3de27): 4/10 solved, 6 unsolved, 5 usable stored failures (dst_zone, rr_priority, hm_infer, phi_blocks, dec_round; mini_asm has no coded turn). They are valid as the first 10 rows of the 30-task baseline because v4_01-10, `agent.py` and `run.py` have not changed since. The 30-task baseline = those 10 rows + this arm's 20. Same settings and code, so nothing else differs between the two parts.
- Arm: `scripts/llmctl.py run -- python3 bench/loop/agent.py --set v4 --tasks v4_11_hdlc_unframe,v4_12_markov_run,v4_13_load_properties,v4_14_ustar_entries,v4_15_msgpack_loads,v4_16_ifc_calendar,v4_17_timer_sched,v4_18_book_rooms,v4_19_leap_clock,v4_20_list_schedule,v4_21_kth_coprime,v4_22_bounded_compositions,v4_23_two_square_reps,v4_24_fib_edges,v4_25_capped_part_count,v4_26_rect_union,v4_27_mst_census,v4_28_pal_range,v4_29_maximal_runs,v4_30_cocircular -k 4 -e 4 --label qwen-v4b-agent-k4e4-vk-np4 --gtt-baseline 5.8`, inside an ACTIVE session opened with `scripts/llmctl.py invite qwen --ctx 65536 --np 4`, run in the background (it outlives a turn; `agent.py` prints a task only when it finishes, in task order, and writes rows in that order, so an empty log or JSONL mid-run is normal and a kill loses the tail). The idle GTT baseline 5.8 GiB is the last measured value (5.7-5.8 across llmctl sessions 2-4); `invite` prints the preflight reading, and if it differs by more than 0.3 GiB the figure is corrected in the result, not silently. Then `agent.py --regrade` on the JSONL inside the same session; the count must equal the summary `solved`. Ends with `scripts/llmctl.py bye`.
- Fixed settings, as the probe: Vulkan, ctx 65536, 4 slots (`--parallel 4`), temperature 0.6, top_p 0.95, top_k 20, `reasoning_budget_tokens` 8192 inside `max_tokens` 12288, prompt suffix from `run.py`, up to 4 episodes of 4 turns, task budget 196,608 completion tokens, sampling seeds 1000 + 10 x episode + turn, fresh seed 104729, llama.cpp 836d57176 `build-vk`, Qwen3.6-35B-A3B UD-Q4_K_XL, hardened grader, one model resident.
- Metric: solved = the passing code also passes with `random.seed(104729)` (summary `solved`, out of 20). Over the 30: unsolved = 30 - (4 + solved), and usable stored failures = unsolved tasks whose last attempt came from a coded turn (a code block was produced). A task with no coded turn (every turn truncated at the 12,288-token cap, as mini_asm) is not usable; `agent.py`'s `stored_failure` has nothing to feed for it. Also recorded: completion tokens, turns, wall time, `gtt_model_gib`, stop reasons, turns at the cap, `grader: forbidden` count, per-task turns.
- Bar, stated now: usable stored failures over the 30 >= 10 (this arm adds >= 5, the probe holds 5) means the pool is big enough for a DeepSeek-fixer replication to be meaningful: the next pre-run (its own question, control arm, bar and cost, written before any GPU work) takes all usable failures from the 30 as its input. 10 is a judgement, not a measured threshold: with n = 5 the v3 fixer comparison needed all five to clear its bar (fixer 5/5 vs Qwen control 3/5), and a single run with a sampler whose draws flip ~11% of the time under batching makes a +2 gap on n = 5 noise-thin; at n >= 10 a +3 gap is 30 points of rate. Usable 5-9 (this arm adds 0-4) means the pool is thin: nothing starts on it automatically; the user decides between a replication at that n with a bar stated for that n and writing further tasks (a separate pre-run; v4_01-30 stay frozen either way). Usable cannot fall below 5, the probe already holds them. Neither outcome is a keep/drop, and neither edits a task, prompt, K, E or budget.
- What the run buys besides the question: the remaining 20 rows of the 30-task loop-alone baseline (v4 solved over 30 and its failure texts), the stored last attempts the fixer arm will read, cap-hit rate and seconds per turn on 20 more long prompts, the deny-list trip count on the hardened grader (probe: 0 of 112 turns), and a second measured `memory.peak` for `agent.py` under the llmctl cap.
- n: 20 new tasks, one run, no spread estimate (a rerun would flip ~11% of sampler draws); 30 tasks in the combined baseline. A solved rate over 30 is a count with a wide interval, not a failure rate; no claim beyond the counts is made from it.
- Cost: from the probe, 3.29 h of GPU per 10 tasks (112 turns, 11,853 s, ~106 s of wall per turn at 4 slots), so ~6.5 h expected for 20 tasks (~224 turns if the tasks need as many turns as the probe's 11.2 per task; ~2.4M completion tokens). Ceiling: 20 x 16 = 320 turns x ~106 s = ~9.4 h, stated as ~10 h; the token budget caps it at 20 x 196,608 = 3.9M. Cap hits can lengthen turns (the probe's capped turns were the long ones), which is why the ceiling is not the expectation. DeepSeek must stay unloaded (it is inactive; ~85 GiB GTT does not fit beside Qwen's +22.4). One model is resident the whole time and nothing else runs on the GPU.
- Memory plan: `scripts/llmctl.py invite qwen --ctx 65536 --np 4` runs `scripts/preflight.sh` on the model right before the load (NOT READY = stop, no retry loop); the server is ACTIVE at ~28.2 GiB GTT (+22.4 over the 5.8 baseline, measured); `run` caps the client at `MemoryMax` 8 GiB, `MemorySwapMax=0`, `RLIMIT_AS` 16 GiB, and records `memory.peak`. The probe's `agent.py` peaked at 145 MiB at `--parallel 4` (regrade 39 MiB), about 55x headroom; the cap stays at 8 GiB. No Chrome, builds or second client during the run; a cap kill exits 137 and leaves the session ACTIVE.
- Result files: `agent.py` writes `bench/loop/results/qwen-v4b-agent-k4e4-vk-np4.jsonl` and `.summary.json` in the repo; copying them to `/data/bench/loop/results` is the user's call (live-sync), as for the probe.
- **This run needs the user's separate yes** (it is a GPU run of ~6.5 h, up to ~10 h). Writing and committing these tasks and this section is not that yes, and nothing in this commit loads or calls a model.

## Model lifecycle: llmctl sessions (2026-10-07)

Why: before this, nothing in the tree stopped one model and loaded another. `llm-serve.sh` managed only the small model, `llama-deepseek` is a separate sudo-only unit with no `Conflicts=`, `preflight.sh` only gates, and "one model at a time" lived in prose. On 2026-10-07 at 03:58 the kernel OOM-killed a 95 GiB `python3` in Cursor's scope while a Qwen server held 28 GiB of GTT; Cursor's scope failed with it and the v4 probe run (started 03:38) was lost with no rows written. What allocated the 95 GiB is not established: the grader's sandbox child has `RLIMIT_AS` 4 GiB, and a solution that prints in a loop grew the grader parent only ~130 MiB in 8 s (tested under a 3 GiB cap), so unbounded output buffering is ruled out as the main cause. The `agent.py` parent is the suspect (nothing capped it), not proven.

`scripts/llmctl.py` (tests: `python3 scripts/llmctl-test.py`, no GPU) owns every server lifecycle as a session, centralized for now; the endpoint registry at the top of the file is data, so per-endpoint delegation later is an adapter.
- **Endpoints**: `qwen` and `laguna` (user unit `llm-8081`, :8081, started through `scripts/llm-serve.sh`), `deepseek` (system unit `llama-deepseek`, :8080). Each row: kind, unit, port, model path, expected GTT delta (what the model adds over the pre-invite baseline; the ACTIVE session note shows measured and expected side by side).
- **Session states**: INVITE -> PREFLIGHT -> LOADING -> ACTIVE -> BYE -> ENDED, or FAILED (preflight NOT READY, start or `/health` failure, GTT not released); ABORTED when the process is gone or the controller died mid-transition. Table `sessions` in `/data/orch/orch.db` (DDL in `orchestrator/schema.sql`, idempotent, `user_version` stays 1). A unique partial index makes a second live session impossible. State is reconciled once per invocation; no polling, no watchdog.
- **Commands**: `invite <endpoint> [--backend vk|hip --ctx N --np N]`, `bye`, `swap <endpoint>`, `status`, `run [--mem 8G] [--as 16G] -- <cmd>`.
- **UNOWNED** = a llama process, an active registered unit or GTT above 16 GiB with no ACTIVE session. `invite` and `swap` refuse; `bye` ends a resident registered unit without a row (this is how a server left by a crashed run is cleaned up); a llama process outside any registered unit is reported, not killed.
- **Fails closed**: unreadable `mem_info_gtt_used` refuses `invite` and `swap` (gpu-guard still fails open).
- **DeepSeek**: `sudo -n systemctl start|stop llama-deepseek` through `/etc/sudoers.d/llmctl` (repo copy `etc/sudoers.d/llmctl`: exactly those two commands, no wildcards; the user installs it once with `scripts/install-llmctl-sudoers.sh`). Ending DeepSeek (`bye`, or `swap` away) needs an interactive terminal and the word yes, so an agent cannot do it. Installed by the user 2026-10-07; `sudo -n systemctl stop llama-deepseek` verified to pass without a password (the install script runs it as a no-op while the unit is inactive); `start` verified by the first `invite deepseek` (below). First live use: the stale Qwen left by the crashed run was ended with `llmctl bye`, GTT 28.3 -> 5.8 GiB (session 1, `unowned:llm-8081`). Known gap: a direct `sudo systemctl start llama-deepseek` while idle bypasses the preflight, because the drop-in allows the command to anyone running as aj and gpu-guard only covers the resident case.
- **Live round trips, 2026-10-07** (user's yes per goal; sampler max of `mem_info_gtt_used` at 1 s over the invite, baseline 5.8 GiB, `llama-deepseek` inactive, preflight READY): `invite qwen --ctx 65536 --np 4` ACTIVE in 6.2 s, peak 28.2 GiB (+22.4), 4 slots, `bye` -> 5.8 GiB (session 2). `invite deepseek` ACTIVE in 21.3 s, peak 91.1 GiB (+85.3), 1 slot, `bye` by the user at a terminal -> 5.8 GiB (session 3). Both `run` health checks: rc 0, `memory.peak` 24 MiB. The registry `gtt_need` values were the file sizes and an idle-baseline delta (21, 86, Laguna 19.1 = file size), compared in the note against absolute GTT; now measured deltas (qwen 22.4, deepseek 85.5, laguna 20.7) and the note prints `+delta over the baseline before (expected +N)`. Page cache state was not checked (the files were probably warm), so a cold-cache DeepSeek load is unmeasured.
- **Memory cap**: `run` is allowed only inside an ACTIVE session and wraps the client in `systemd-run --user --scope -p MemoryMax=8G -p MemorySwapMax=0 -p OOMPolicy=continue` plus `RLIMIT_AS` 16 GiB, then reads that scope's `memory.peak` and `oom_kill`. A cap kill exits 137 with "memory cap" and leaves the session ACTIVE. **The 8 GiB is a first value, not a measured one**: `agent.py` has never had a measured peak. `memory.peak` is recorded in the session note on every run, and the first real run's peak sets the next value (measured 2026-10-07: the v4 probe `agent.py` run at `--parallel 4` peaked at 145 MiB, its regrade at 39 MiB, the health checks at 24 MiB; the cap stays at 8 GiB, a decision for later). The 16 GiB `RLIMIT_AS` suits an HTTP client; a ROCm client maps far more address space and needs `--as` raised.
- **gpu-guard**: `scripts/llmctl.py` with any verb but `status` is denied for agent Bash while GTT is above 16 GiB (20 matrix cases, 164 total); `scripts/llmctl-test.py` is allowed (stub endpoints, no model).
- **Not in a session**: `bench/bench.sh`, llama-bench, llama-perplexity and training load their own model. They still need `scripts/preflight.sh`, which reads NOT READY while a session is ACTIVE; `llmctl bye` first.
- **Unmeasured**: DeepSeek's `/health` wait is 600 s as a first value; the load took 21 s (cache state unchecked) and a cold-cache load has not been timed. `llmctl invite` and `llm-serve.sh start` both run the preflight, so it prints twice for the small models.
- Tests, no GPU (39 cases, `scripts/llmctl-test.py`): invite -> ACTIVE -> run -> bye, one live session, FAILED on a failed preflight and on a failed start, ABORTED after a killed process, UNOWNED refusal and `bye` on an unowned unit, unreadable-GTT refusal for invite and swap, no-TTY refusal ending a confirm-end endpoint (and the pty yes/no paths), swap as one transition, swap with a failing invite leaving nothing resident, a `run` child past the cap killed with the session untouched, `RLIMIT_AS` giving MemoryError, `memory.peak` recorded, the unique index.

## Roadmap (active)

1. Orchestrator + SQLite memory: structured verdicts (finding, file, severity, accepted/rejected + reason) retrieved into prompts. DeepSeek as an hourly adversarial reviewer of diffs; static system/rules/repo summary first in the prompt, changing material last, for cache hits.
2. Small-model agentic loop: Qwen3.6-35B-A3B in a reason -> act -> observe -> retry cycle with hard feedback, not single-shot sampling.
   - Done: best-of-N harness, `bench/loop/run.py` (loop-v0 1035d5e: best-of-4 kept; loop-v1 10fc559: Laguna as a second sampler dropped). It samples independently and never shows the model its test failure, so it is the baseline, not the loop.
   - Kept 2026-10-06: `bench/loop/agent.py`, one model, K=4 E=4: 12/12 vs best-of-16 10/12 at 19.7% of the tokens (see the v1 agentic loop results; regex_match's pass was a fresh sample, not feedback). Confirmed 2026-10-06 on 30 unseen v2 tasks: 29/30 vs early-stop best-of-16 23/30 at 55.7% of the tokens (pre-run 27e2be7; 4 of the 6 extra tasks were feedback wins). Laguna as a fixer on the 5 stored v3 failures: 1/5 vs Qwen fix-mode control 3/5, not confirmed, role dropped (v3 fixer section). DeepSeek V4 Flash as fixer on the same 5: 5/5 (30/30 total), confirmed by its pre-run bar (41717a1); one run, sequential only (86 GiB), needs a held-out replication on a new v4 set (probe tasks c7b54f4, probe pre-run in its v4 section) before it becomes a loop stage. Grader hardened 2026-10-07 (tripwire, no stored count changed; see Grader hardening). v4 probe (10 tasks, hardened grader, through `llmctl run`) 2026-10-07: 4/10 solved, bar met, 6 unsolved (v4 probe result). Next: tasks 11-30 (pre-run first), the 20-task loop-alone arm, then the DeepSeek-fixer replication. Design: Action at first is submitting `solution.py`; the harness runs the tests in bwrap and feeds the failure back. Critic = tests and compiler, which the model cannot write to (bwrap, `_banned()`). Context per turn: task + current code + latest failure, no chat history (fits a 16k slot). Brakes: max K turns, a token budget per task, stop on a repeated error or code hash. Final grade on a fresh oracle seed the loop never saw, so hard-coding a fed-back case does not count (27 of 30 v1 tasks have a single `random.seed(N)`; the other 3 are flagged).
   - Kept only if it beats independent best-of-N at equal tokens; K and the threshold go in its pre-run commit. Baseline: best-of-16 on the 12 weak v1 tasks (pre-run 52f0a05).
   - Later, each with its own pre-run commit: tools beyond submit-code; a second small model in a role (fixer or second sampler; two small models fit in GTT but need a deliberate change to the one-model guard); DeepSeek as judge only as a separate pass, since it cannot be resident beside Qwen (~85 + ~23 GiB = all 108 GiB of GTT). Tests outrank any judge.
3. One timed LoRA job, kept only if it beats the base model on held-out tasks. Verdicts are not training pairs; a dataset has to be built. Risks: model collapse, bad judge.
4. DaVinci Resolve Studio in a container: davincibox chosen; licence type and install deferred.
5. Server-class hardware research, criterion bandwidth per dollar with confirmed software support.
