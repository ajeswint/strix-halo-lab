# Review roles

Source of truth for the roster, the reply format, and precedence. `CLAUDE.md` and `AGENTS.md` carry the same seat pin. If a roster line disagrees with this file, this file wins.
Updated 2026-11-11 CT (AJ, America/Chicago): writer is Google Antigravity, model Gemini 3.8 Flash (`gemini-3.8-flash-high`), effort high (Argon is quota-exhausted); reviewer is Grok 4.7 high. The Claude Code writer remains closed.
Updated 2026-11-05 CT (AJ, America/Chicago): the writer seat moved from Claude Code (Sonnet) to Google Antigravity, Gemini 4 Argon, effort high; the reviewer is unchanged. The earlier 2026-11-06-dated entry (Claude writer plus Claude reviewer) is superseded for the writer. The 2026-10-14 roster (kept below as history) is historical for drafts. The README decision log keeps its paragraph. `orchestrator/orch.py` on DeepSeek was not that cloud agent and is unchanged.

## Seats

| Seat | Who | Does |
|---|---|---|
| code-writer | Google Antigravity, model Gemini 3.8 Flash (slug `gemini-3.8-flash-high`), reasoning effort high. Headless `agy` one-shot and the interactive App; rules in `docs/antigravity-writer.md`. `.claude/agents/code-writer.md` is a stub (not a Claude agent). | Drafts code, commands, and repo edits. Does not review its own draft. Works on a branch, stages named paths only, pushes only if the task says so (see Writer git rules). |
| adversarial-reviewer | Grok 4.7 high. | Reviews only. Does not edit the draft. First line is `APPROVE`, `APPROVE-WITH-NITS`, or `REQUEST-CHANGES`. |
| Ryzen Max Bot | Grok bot on this MAX. | Launches the writer as an `agy -p` one-shot and relays, and merges the PR on an `APPROVE*` sign-off. Does not write product code in place of the writer. |
| User (AJ) | Human. | Final judge. Runs sudo and host actions. |

Gemini 3.8 Flash is the writer's model through Antigravity. That is not the benched "Gemini overseer" of the 2026-10-14 roster, which stays benched until AJ un-benches it and is not a draft seat.

Domain arms, invoked by name, are not these seats: `systems`, `trainer`, `evaluator`, `red-team`.

## Reply format

Every full reply to AJ or to the other seat has three parts, in this order. A one-line answer skips them.

1. **Detail** — the full write-up. Long is fine; this is the record.
2. **Relay** — written by the seat that is replying. The code-writer's Relay (the Antigravity writer's too) is for the adversarial-reviewer to read. The adversarial-reviewer's Relay is for the code-writer to read. Short, pasteable as-is.
3. **Outline** — a nested outline of the Detail.

The reviewer's one-shot puts the verdict on the first line, then those three parts. The verdict is exactly one of `APPROVE`, `APPROVE-WITH-NITS`, `REQUEST-CHANGES`. `APPROVE-WITH-NITS` does not block paste. Soft nits: AJ (2026-11-05 CT, with the Antigravity writer) set them back to parked unless AJ asks for a chase. This reverses the earlier standing "chase soft nits" rule and returns to the state after the last chase (PR `lab/chase-docs-nits`, which AJ called the last chase). When AJ does ask, the writer applies the nits in a follow-up one-shot on the same branch and the reviewer re-reviews. `REQUEST-CHANGES` is blocking. Each blocking finding names the fix in words. The reviewer does not apply it. AJ confirmed in his own words 2026-11-05 CT: automate merges when the reviewer signs off with `APPROVE*`.

The reviewer's no-write rule is a prompt rule, not enforced: the one-shot runs with `bypassPermissions`, so only the agent file's tool list and the gpu-guard hook hold the line. The writer's rules are prompt rules too, with less behind them: the `agy` one-shot runs with `--dangerously-skip-permissions`, has no tool list, and gpu-guard does not wrap it (`docs/antigravity-writer.md`).

**Merge.** Ryzen Max Bot merges; the code-writer never merges. `REQUEST-CHANGES` stops the merge. AJ can still veto or revert.

- A first-pass plain `APPROVE` (no nits) is enough for the bot to merge. No re-review is required.
- A first-pass `APPROVE-WITH-NITS` is mergeable: the nits stay parked unless AJ asks for a chase. If AJ asks, the writer chases them and the reviewer re-reviews; that re-review's first line `APPROVE` or `APPROVE-WITH-NITS` is then enough to merge. Which of these the bot follows on a first-pass `APPROVE-WITH-NITS` is the bot's launcher policy, not enforced here; AJ can veto or revert.
- The PRs are opened as drafts, and `gh pr merge` refuses a draft. The bot must mark it ready first: `gh pr ready` on the PR, then `gh pr merge`.

## Precedence

1. AJ decides. Sudo and host actions are AJ's. Seats never run sudo.
2. For a draft, code-writer (Antigravity) writes and adversarial-reviewer (Grok 4.7 high) reviews. Ryzen Max Bot launches, relays, and merges on an `APPROVE*` sign-off (`tools/lab-seats/launch.sh`); it writes no product code.
3. Domain arms run when invoked with `--agent systems`, `--agent trainer`, `--agent evaluator`, or `--agent red-team`. systems owns live config and `orchestrator/orch.py`. trainer owns the LoRA job and does not start it without AJ's yes. evaluator reads benches and does not edit the repo to make a run pass. red-team attacks injection, judge manipulation, and collapse. red-team does not review diff correctness. That is the adversarial-reviewer.
4. `orchestrator/orch.py` on DeepSeek is the commit-review memory. It is not the standing draft reviewer. Do not add a second DeepSeek reviewer. A review that sees only GitHub still does not count for local MAX measurements (GTT, gpu-guard, live runs, root-only files).

## Launch

On aj-Ryzen-AI-MAX, from the repo:

```
cd /home/aj/projects/strix-halo-lab
tools/lab-seats/launch.sh --task "Read docs/review-roles.md and confirm the standing seats. Do not edit files."
```

That writes the scratch files under `/tmp/lab-seats/` and `nohup`s the launch script. The launch script runs the writer `agy -p` one-shot, then the reviewer `claude -p` one-shot. Flags:

```
agy -p "PROMPT" --model gemini-3.8-flash-high --effort high --dangerously-skip-permissions
```

```
claude -p --model sonnet --effort high --permission-mode bypassPermissions --agent adversarial-reviewer
```

The first line is the shape; the launcher reads PROMPT from `writer-prompt.txt` (`agy -p` takes the prompt as an argument, not stdin; https://antigravity.google/docs/cli/headless). `gemini-3.8-flash-high` is the launcher default; override with `LAB_SEATS_WRITER_MODEL`; an unknown slug fails the writer non-zero, with no silent fallback. `--dangerously-skip-permissions` is there because headless `agy` has no prompt and soft-denies any tool without an allow rule (exit 0, nothing done); the reasoning and its cost are in `docs/antigravity-writer.md`.

`claude --bg` does not combine with `-p` (https://code.claude.com/docs/en/cli-reference). Standing automation is the nohup wrapper, not a background TUI panel. `effort: high` is also set in the reviewer's agent file (https://code.claude.com/docs/en/sub-agents).

Dry-run (writes the scratch files, does not start `agy` or `claude`):

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
- does not merge. The merge is Ryzen Max Bot's, after an `APPROVE*` sign-off.

These bind the Antigravity writer too. Antigravity reads `AGENTS.md` (always on) and not `CLAUDE.md`, so the short form is in `AGENTS.md` and the full list in `docs/antigravity-writer.md`.

## One-shot caps

`tools/lab-seats/launch.sh` wraps each one-shot in `timeout --kill-after=30` (default 3600 s; `LAB_SEATS_TIMEOUT` overrides). `LAB_SEATS_MAX_USD` optionally adds `--max-budget-usd` to the **reviewer** one-shot only (claude, print mode; unset means none). `agy` 1.5.1 has no budget or turn flag, so the writer has no spend cap, only the timeout. `--max-turns` is documented upstream for claude (print mode only; https://code.claude.com/docs/en/cli-reference) but not shown in 2.1.317 `claude --help`; not wired, untested.

The 3600 s default is an unmeasured default: no real one-shot has been timed against it. A timeout ends the run as `writer-failed rc=124` or `reviewer-failed rc=124`; rc 137 means the process ignored SIGTERM and `--kill-after=30` sent SIGKILL. The signal targets the `agy` or `claude` process only; its descendants are not guaranteed to die (a test with a TERM-ignoring parent left orphaned `sleep` children). An `agy` run that exits 0 with an empty `writer-out.md` is recorded as `writer-failed rc=0 (empty output; see writer.log)` and the reviewer does not run. After any timeout (rc 124 or 137), before relaunching: check `git status`, look for a stale `.git/index.lock` and a half-staged index (`git diff --cached`), and look for orphan processes (`pgrep -af 'agy|claude'`).

## Rules that still bind

`CLAUDE.md` is the working-rule list. In particular: `scripts/llmctl.py` is the only start/stop path; `scripts/preflight.sh` right before any model load; never load beside DeepSeek; gpu-guard on the Claude seats' Bash hooks (not on the Antigravity writer: `docs/antigravity-writer.md`); measured numbers; no Docker, Postgres, or Unsloth in the torch env. No subagent fan-out unless AJ asks (2026-10-15 OOM). These one-shots are the two seats, not a fan-out.

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
