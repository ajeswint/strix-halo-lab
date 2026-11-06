# Review roles

Source of truth for the roster, the reply format, and precedence. `CLAUDE.md` and `AGENTS.md` carry the same seat pin. If a roster line disagrees with this file, this file wins.
Updated 2026-11-06 (AJ's decision date; the commit author date is 2026-11-05 local, -0600). The 2026-10-14 roster (kept below as history) is historical for drafts. The README decision log keeps its paragraph. `orchestrator/orch.py` on DeepSeek was not that cloud agent and is unchanged.

## Seats

| Seat | Who | Does |
|---|---|---|
| code-writer | Claude Code, Sonnet, effort high. `.claude/agents/code-writer.md`. | Drafts code, commands, and repo edits. Does not review its own draft. Works on a branch, stages named paths only, pushes only if the task says so (see Writer git rules). |
| adversarial-reviewer | Claude Code, Sonnet, effort high. `.claude/agents/adversarial-reviewer.md`. | Reviews only. Does not edit the draft. First line is `APPROVE`, `APPROVE-WITH-NITS`, or `REQUEST-CHANGES`. |
| Ryzen Max Bot | Grok bot on this MAX. | Launches the two seats as `claude -p` one-shots, relays, and merges the PR after an `APPROVE*` re-review. Does not write product code in place of the writer. |
| User (AJ) | Human. | Final judge. Runs sudo and host actions. |

Gemini stays benched until AJ un-benches it. It is not a draft seat.

Domain arms, invoked by name, are not these seats: `systems`, `trainer`, `evaluator`, `red-team`.

## Reply format

Every full reply to AJ or to the other seat has three parts, in this order. A one-line answer skips them.

1. **Detail** — the full write-up. Long is fine; this is the record.
2. **Relay** — written by the seat that is replying. The code-writer's Relay is for the adversarial-reviewer to read. The adversarial-reviewer's Relay is for the code-writer to read. Short, pasteable as-is.
3. **Outline** — a nested outline of the Detail.

The reviewer's one-shot puts the verdict on the first line, then those three parts. The verdict is exactly one of `APPROVE`, `APPROVE-WITH-NITS`, `REQUEST-CHANGES`. `APPROVE-WITH-NITS` does not block paste. Soft nits are chased, not parked (AJ's standing rule; AJ confirmed in his own words 2026-11-05 CT: automate merges when the reviewer signs off with `APPROVE*`, and chase soft nits): the code-writer applies them in a follow-up one-shot on the same branch, and the reviewer re-reviews. `REQUEST-CHANGES` is blocking. Each blocking finding names the fix in words. The reviewer does not apply it. One-off, for the docs-nit chase of PR `lab/chase-docs-nits`: AJ said it is the last soft-nit chase; after it merges, further soft nits stay parked unless AJ asks again.

The reviewer's no-write rule is a prompt rule, not enforced: the one-shot runs with `bypassPermissions`, so only the agent file's tool list and the gpu-guard hook hold the line.

**Merge.** Ryzen Max Bot merges; the code-writer never merges. `REQUEST-CHANGES` stops the merge. AJ can still veto or revert.

- A first-pass plain `APPROVE` (no nits) is enough for the bot to merge. No re-review is required.
- A first-pass `APPROVE-WITH-NITS` is not yet mergeable: the code-writer chases the nits, then the reviewer re-reviews. After a chase, the re-review's first line `APPROVE` or `APPROVE-WITH-NITS` is enough to merge (any nits still left are chased in the next change, not parked).
- The PRs are opened as drafts, and `gh pr merge` refuses a draft. The bot must mark it ready first: `gh pr ready` on the PR, then `gh pr merge`.

## Precedence

1. AJ decides. Sudo and host actions are AJ's. Seats never run sudo.
2. For a draft, code-writer writes and adversarial-reviewer reviews. Ryzen Max Bot launches, relays, and merges after an `APPROVE*` re-review (`tools/lab-seats/launch.sh`); it writes no product code.
3. Domain arms run when invoked with `--agent systems`, `--agent trainer`, `--agent evaluator`, or `--agent red-team`. systems owns live config and `orchestrator/orch.py`. trainer owns the LoRA job and does not start it without AJ's yes. evaluator reads benches and does not edit the repo to make a run pass. red-team attacks injection, judge manipulation, and collapse. red-team does not review diff correctness. That is the adversarial-reviewer.
4. `orchestrator/orch.py` on DeepSeek is the commit-review memory. It is not the standing draft reviewer. Do not add a second DeepSeek reviewer. A review that sees only GitHub still does not count for local MAX measurements (GTT, gpu-guard, live runs, root-only files).

## Launch

On aj-Ryzen-AI-MAX, from the repo:

```
cd /home/aj/projects/strix-halo-lab
tools/lab-seats/launch.sh --task "Read docs/review-roles.md and confirm the standing seats. Do not edit files."
```

That writes the scratch files under `/tmp/lab-seats/` and `nohup`s the launch script. The launch script runs the writer `claude -p` one-shot, then the reviewer one-shot. Flags on both:

```
claude -p --model sonnet --effort high --permission-mode bypassPermissions --agent code-writer
```

```
claude -p --model sonnet --effort high --permission-mode bypassPermissions --agent adversarial-reviewer
```

`claude --bg` does not combine with `-p` (https://code.claude.com/docs/en/cli-reference). Standing automation is the nohup wrapper, not a background TUI panel. `effort: high` is also set in each agent file (https://code.claude.com/docs/en/sub-agents).

Dry-run (writes the scratch files, does not start `claude`):

```
cd /home/aj/projects/strix-halo-lab
tools/lab-seats/launch.sh --dry-run --task "Read docs/review-roles.md and confirm the standing seats. Do not edit files."
```

## Writer git rules

The checkout is often dirty with AJ's own edits (for example `.claude/settings.json`). The code-writer:

- works on a branch named in the task, never commits to `main`;
- stages named paths only (`git add path1 path2`), never `git add -A`, `git add .` or `git commit -a`;
- checks `git status` and `git diff --cached` before each commit, and leaves unrelated modified files unstaged;
- pushes only if the task says so, and then only the task's branch; never force-pushes;
- does not merge. The merge is Ryzen Max Bot's, after an `APPROVE*` re-review.

## One-shot caps

`tools/lab-seats/launch.sh` wraps each one-shot in `timeout --kill-after=30` (default 3600 s; `LAB_SEATS_TIMEOUT` overrides). `LAB_SEATS_MAX_USD` optionally adds `--max-budget-usd` (print mode only; unset means none). `--max-turns` is documented upstream (print mode only; https://code.claude.com/docs/en/cli-reference) but not shown in 2.1.317 `claude --help`; not wired, untested.

The 3600 s default is an unmeasured default: no real one-shot has been timed against it. A timeout ends the run as `writer-failed rc=124` or `reviewer-failed rc=124`; rc 137 means the process ignored SIGTERM and `--kill-after=30` sent SIGKILL. The signal targets the `claude` process only; its descendants are not guaranteed to die (a test with a TERM-ignoring parent left orphaned `sleep` children). After any timeout (rc 124 or 137), before relaunching: check `git status`, look for a stale `.git/index.lock` and a half-staged index (`git diff --cached`), and look for orphan processes (`pgrep -af claude`).

## Rules that still bind

`CLAUDE.md` is the working-rule list. In particular: `scripts/llmctl.py` is the only start/stop path; `scripts/preflight.sh` right before any model load; never load beside DeepSeek; gpu-guard on the seated Bash hooks; measured numbers; no Docker, Postgres, or Unsloth in the torch env. No subagent fan-out unless AJ asks (2026-10-15 OOM). These one-shots are the two seats, not a fan-out.

Findings from any reviewer are claims to check against HEAD, not orders: concede what checks out, push back with evidence on what does not.

Host RAM: while a one-shot is running, count it, plus Ryzen Max Bot and Chrome, in preflight headroom.

## Historical: 2026-10-14 roster

Set by the user 2026-10-14 (historical, superseded for drafts 2026-11-06), given to every participant. Moved here from Claude's private memory 2026-10-15 so all agents can audit them.

| Who | Role |
|---|---|
| Claude (terminal on the MAX) | Writes the code; commits all state and rules inside this repo. |
| Grok 4.7 High Fast Cloud Agent | Adversarial check of Claude's pushed commits, reasoning backwards from them. Rounds continue until Claude and it reach an explicit accord. It sees only GitHub, not local MAX state (GTT, gpu-guard, live runs, root-only files), so its agreement on local measurements does not count. |
| Grok bot | Adversarial overseer of the repo, the Claude terminal, the Grok cloud agent and the user. |
| Gemini | Benevolent overseer of everyone. Benched until a Claude vs Grok loop deadlocks with no accord. |
| User | Final judge. |

- Claude and the user share the friction of the adversarial checks.
- Findings from any reviewer are claims to check against HEAD, not orders: concede what checks out, push back with evidence on what does not.
- Host-RAM load: the Grok bot runs on this box and Gemini is open in Chrome here; count both in preflight headroom.
