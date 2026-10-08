Context for the reviewer (sent before CLAUDE.md on every review; keep it short and true).

What this repo is: the working record of one Framework Desktop (Ryzen AI Max+ 395, Radeon 8060S gfx1151, 128 GB unified memory) used as a local LLM box. README.md is the decision log. Files under bench/, etc/, systemd/, envs/, models/, scripts/ are copies of live files; the tree mirrors their real paths. Reviews see diffs only; README.md is not sent whole.

Decisions already made. Do not report them as defects:
- SQLite with one writer for orchestrator memory. Postgres only if parallel writers hit lock errors. No Docker (podman). No Unsloth in the torch env.
- PyTorch from AMD's gfx1151 wheel index, never download.pytorch.org ROCm wheels. Installs into /data/envs/torch use `--index-strategy unsafe-best-match` and envs/torch-constraints.txt.
- IOMMU stays on. GTT is capped at 108 GiB; the 64k DeepSeek server peaks near 86 GiB.
- Set-and-forget: settings are applied once where they can reset. No polling loops or watchdogs unless a revert was observed.
- DeepSeek V4 Flash is the background reviewer (this tool). Qwen3.6-35B-A3B is the small model for the loop. Models are started and stopped only through scripts/llmctl.py sessions.
- Experiments are pre-registered: a pre-run commit states the question, the bar and the cost before any result exists. A bar in a pre-run is a decision, not a defect.

What is worth reporting: bugs, wrong claims in docs or comments, unsafe commands, broken reproducibility, data loss or security risk, and code that does not do what its README or comment says. If a file is not in the diff, say nothing about it.
