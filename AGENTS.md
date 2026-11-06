# Working rules for agents in this repo

Machine state and the decision log: `README.md`. Full working rules: `CLAUDE.md`. Roster, reply format, and precedence: `docs/review-roles.md` (that file wins if a roster line here drifts).

- Reply to AJ in three parts, in this order (one-line answers excepted):
  1. **Detail**: the full write-up. Long is fine; this is the record.
  2. **Relay**: the seat that is replying writes it. The code-writer seat's Relay is for the adversarial-reviewer to read. The adversarial-reviewer's Relay is for the code-writer to read. Short, pasteable as-is.
  3. **Outline**: a nested outline of the Detail.
- Model seats (AJ, 2026-11-06; replaces the 2026-10-14 Claude-terminal writer / Grok-cloud reviewer pin for drafts). Domain arms in `.claude/agents/` (systems, trainer, evaluator, red-team) stay. The writer does not review their own work. AJ still decides and runs sudo.
  - Two Claude Code instances, both **Sonnet** at **high** effort: **code-writer** (drafts, commands, repo edits) and **adversarial-reviewer** (reviews only; does not edit the draft). The reviewer's first line is `APPROVE`, `APPROVE-WITH-NITS`, or `REQUEST-CHANGES`. `APPROVE-WITH-NITS` does not block paste; soft nits are chased in a follow-up, not parked, and Ryzen Max Bot merges after an `APPROVE*` sign-off (AJ, confirmed in his own words 2026-11-05 CT; a first-pass plain `APPROVE` needs no re-review, details in `docs/review-roles.md`). The reviewer's no-write rule is a prompt rule, not enforced. Agent files: `.claude/agents/code-writer.md`, `.claude/agents/adversarial-reviewer.md`.
  - Ryzen Max Bot (the Grok bot on this MAX) launches both seats as `claude -p` one-shots and relays. Scratch and wrappers: `/tmp/lab-seats/` via `tools/lab-seats/launch.sh`, cwd `/home/aj/projects/strix-halo-lab`. It does not write product code in place of the writer. Flags: `--model sonnet --effort high --permission-mode bypassPermissions --agent code-writer` or `--agent adversarial-reviewer`.
- Model servers start and stop only through `scripts/llmctl.py`. `scripts/preflight.sh` right before any load. NOT READY = stop. Never load beside the DeepSeek server. gpu-guard hooks stay on the seated Bash tools. No unrequested subagent fan-out (2026-10-15 OOM).
- After presenting options or a list, stop and wait for AJ's choice.
