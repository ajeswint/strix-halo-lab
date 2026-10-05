# Working rules for agents in this repo

- Read `README.md` first; it is the current state of the machine and the decision log. Files under `bench/`, `etc/`, `systemd/`, `envs/`, `models/`, `scripts/` are copies of live files; the tree mirrors their real paths.
- Terse. Mechanism-level explanations. Yes/no first when the question is yes/no.
- Exact copy-paste commands only. Never `<placeholders>` in command blocks.
- Verify against current upstream docs before asserting versions or install steps. Cite the URL.
- Measured numbers beat claims. If you propose a tuning change, say what benchmark delta would justify keeping it.
- Simplest fix that is set-and-forget. No polling loops, watchdogs or demo self-tests unless there is evidence a setting reverts.
- Do not propose: Docker (podman is installed), Postgres (SQLite decided), Unsloth in the torch env, `download.pytorch.org` ROCm wheels, IOMMU off, GTT above 108 GiB.
- When installing into `/data/envs/torch` with the AMD wheel index, always add `--index-strategy unsafe-best-match` and the constraints file `envs/torch-constraints.txt`.
- Own errors plainly and correct forward.
- Stay in this repo's scope (the Roadmap in README.md). Other projects (aj-ta-unreal, Unreal Engine, etc.) are separate sessions; flag before drifting.
- Install the entire stack for a step first, then test. Never test one component while other installs are pending or running.
- Memory preflight before loading ANY model or running llama-bench/llama-perplexity/training: `scripts/preflight.sh` with the model path (`preflight` skill), right before the load. NOT READY = stop. Never load beside the DeepSeek server (~85 GiB GTT); ask before stopping it. (2026-10-04 OOM incident, README Security.)
- Procedures live in `.claude/skills/` (preflight, llm-serve, bench, measure, orch-review, live-sync, torch-install, model-add, handoff). Use the skill instead of re-deriving the steps. When a procedure changes, amend its skill in the same commit.
- After presenting options or a list, stop and wait for the user's choice.
- History before 2026-10-04 lives in the archived ajeswint/strix-halo-setup repo.
