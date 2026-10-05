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
| Models | `/data/models`: Qwen3.6-35B-A3B UD-Q4_K_XL, DeepSeek V4 Flash 0731 UD-IQ2_M (3 shards), Laguna XS 2.1 Q4_K_M (bartowski, 20.55 GB, sha256 `239b1417…3491dae6` verified 2026-10-04; second small model for the loop, not yet run). `models/fetch.sh` + `systemd/model-download.service` (disabled, download complete). |
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
- **Four Claude agents in `.claude/agents/`** (systems, trainer, evaluator, red-team); no Claude reviewer, `orch.py` on DeepSeek is the reviewer. `.claude/hooks/gpu-guard.sh` is a PreToolUse tripwire on systems, trainer and evaluator Bash, armed while GTT used is above 16 GiB (any model resident; DeepSeek also loads outside its service via the bench scripts). Armed, it denies model loads, `systemctl start` of llama-deepseek, and stopping that service. One cutoff means Qwen and Laguna cannot be resident together; revisit when a real run needs both. `orchestrator/orch.py` and `bench/report.py` are allowed through. Not on the parent session. Known gaps stay in the script header.
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
  Linger is off, so it would run while you're logged in (screen lock is fine), not after a logged-out boot.

First full review (run 2): 18,644 prompt tokens, 6,489 generated, 534 s. All three findings were false positives (rejected #1-#3 with reasons): the model judged `bench.sh`'s JSONL writer with `results.jsonl` omitted. Run 3 (two small commits, 5,313 prompt tokens, 415 s): 0 findings, but it missed a real doc error (this section claimed the timer was running). Only 138 tokens came from cache because README.md, which sits early in the prompt, changed in those commits. Every run so far used the full 6,144-token reasoning budget, so a review costs ~7 min of GPU regardless of diff size.

## Roadmap (active)

1. Orchestrator + SQLite memory: structured verdicts (finding, file, severity, accepted/rejected + reason) retrieved into prompts. DeepSeek as an hourly adversarial reviewer of diffs; static system/rules/repo summary first in the prompt, changing material last, for cache hits.
2. Small-model loop: Qwen3.6-35B-A3B made strong via tools, tests and best-of-N, with DeepSeek as judge. Tests and compiler outrank the judge.
3. One timed LoRA job, kept only if it beats the base model on held-out tasks. Verdicts are not training pairs; a dataset has to be built. Risks: model collapse, bad judge.
4. DaVinci Resolve Studio in a container: davincibox chosen; licence type and install deferred.
5. Server-class hardware research, criterion bandwidth per dollar with confirmed software support.
