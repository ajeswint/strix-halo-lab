# tools/lab-seats

Launcher for the two standing seats: `code-writer` = Google Antigravity (`agy`, Gemini 3.8 Flash, effort high; since 2026-11-11 CT) and `adversarial-reviewer` = Claude Code (Sonnet, effort high, unchanged). Roster, reply format and precedence are in `docs/review-roles.md`; the writer's rules are in `docs/antigravity-writer.md`. Ryzen Max Bot (the Grok bot on this MAX) calls it; it launches and relays and writes no product code.

## Use

```
cd /home/aj/projects/strix-halo-lab
tools/lab-seats/launch.sh --name seats-check --task "Read docs/review-roles.md and confirm the standing seats. Do not edit files."
```

`--task-file FILE` instead of `--task` reads the task from a file. `--name` defaults to a timestamp and must match `[A-Za-z0-9._-]+`; a name that already has a run is refused. Without `--dry-run` the script returns at once and the wrapper runs detached (`nohup`).

Dry run (writes the scratch files, prints `run.sh`, starts no `agy` and no `claude`):

```
cd /home/aj/projects/strix-halo-lab
tools/lab-seats/launch.sh --dry-run --name seats-dry --task "Read docs/review-roles.md and confirm the standing seats. Do not edit files."
```

## What it runs

Sequentially, cwd = the repo, prompt on stdin:

```
agy -p "$(cat writer-prompt.txt)" --model gemini-3.8-flash-high --effort high --dangerously-skip-permissions < /dev/null
claude -p --model sonnet --effort high --permission-mode bypassPermissions --agent adversarial-reviewer
```

The writer's prompt is an argument, not stdin: `agy -p` reads stdin only with `--input-format stream-json` (https://antigravity.google/docs/cli/headless). `launch.sh` refuses a writer prompt over 100000 bytes (one argument is capped at 128 KiB); for a long task, put it in a repo file and name the file in `--task`. The reviewer's prompt still goes on stdin.

Each is wrapped in `timeout --kill-after=30` (default 3600 s). The reviewer runs only if the writer exited 0 **and** wrote a non-empty `writer-out.md` (headless `agy` soft-denies unapproved tools with exit 0, so an exit code alone is not enough). `--bg` is not used with claude: it cannot be combined with `-p` (https://code.claude.com/docs/en/cli-reference). `effort: high` is also in the reviewer's agent file (https://code.claude.com/docs/en/sub-agents).

**Writer flags.** `--dangerously-skip-permissions`: headless `agy` has no approval prompt and soft-denies a tool call without an allow rule (exit 0), so without it the writer could not edit or commit. It matches the old `bypassPermissions` posture for approval, with less behind it (no tool list, no gpu-guard); see `docs/antigravity-writer.md`. The standing writer slug `gemini-3.8-flash-high` is verified and has been used; it is the launcher default and is overridable with `LAB_SEATS_WRITER_MODEL`. An unknown slug fails non-zero with no silent fallback.

## Caps

| Env var | Effect |
|---|---|
| `LAB_SEATS_TIMEOUT` | seconds per one-shot, default 3600 (an unmeasured default, not tuned from a real run); integer, baked into `run.sh` at launch. A timeout gives `writer-failed rc=124`, or `rc=137` if the process ignored SIGTERM and `--kill-after=30` sent SIGKILL (same for `reviewer-failed`). |
| `LAB_SEATS_MAX_USD` | optional; adds `--max-budget-usd N` to the **reviewer** one-shot only (claude, print mode). `agy` 1.5.1 has no budget flag, so the writer is uncapped except by the timeout. Unset = no budget cap. |
| `LAB_SEATS_WRITER_MODEL` | `agy` model slug, default `gemini-3.8-flash-high`; must match `[A-Za-z0-9._-]+`; baked into `run.sh` at launch. |

`--max-turns` is documented upstream for claude (print mode only; https://code.claude.com/docs/en/cli-reference) but not shown in 2.1.317 `claude --help`; not wired, untested. `agy` has no equivalent.

A timeout signals the `agy` or `claude` process only; descendants may survive. After rc 124 or 137, check `git status`, a stale `.git/index.lock`, a half-staged index and orphan processes (`pgrep -af 'agy|claude'`) before relaunching (details: `docs/review-roles.md`, One-shot caps). Example:

```
cd /home/aj/projects/strix-halo-lab
LAB_SEATS_TIMEOUT=1800 LAB_SEATS_MAX_USD=5 tools/lab-seats/launch.sh --dry-run --name caps-dry --task "confirm the caps"
```

## Scratch (`/tmp/lab-seats/NAME/`, root overridable with `LAB_SEATS_ROOT`)

| File | Content |
|---|---|
| `TASK.md` | the task as given |
| `writer-prompt.txt`, `reviewer-prompt.txt` | stdin of each one-shot |
| `run.sh`, `run.pid`, `launcher.log` | generated wrapper, its pid, its own output |
| `writer-out.md`, `writer.log` | `agy` stdout (Detail / Relay / Outline) and stderr (soft-deny notices, `AGY_ERROR` lines) |
| `reviewer-out.md`, `reviewer.log` | reviewer stdout (verdict line first) and stderr |
| `verdict.txt` | output of `verdict.py` on `reviewer-out.md` |
| `run.status` | written last: `done verdict=...`, `writer-failed rc=N`, `writer-failed rc=0 (empty output; see writer.log)` or `reviewer-failed rc=N` |

`/tmp` does not survive a reboot. Anything worth keeping goes in a commit or the PR.

## verdict.py

`python3 -I tools/lab-seats/verdict.py FILE` prints the first non-blank line if it is exactly `APPROVE`, `APPROVE-WITH-NITS` or `REQUEST-CHANGES`. Exit 0 for the first two (nits do not block), 1 for `REQUEST-CHANGES`, 2 for anything else (a decorated or prefixed verdict is a format violation).

## Test

```
cd /home/aj/projects/strix-halo-lab
bash tools/lab-seats/test.sh
```

Loads no model and never starts the real `agy` or `claude`. It asserts: no sudo in the launcher, the exact `agy` writer and `claude` reviewer flags and writer-before-reviewer order in the generated `run.sh`, the caps and writer-model override, an oversize writer prompt refused, the writer-failure paths (non-zero exit, empty output) never reaching the reviewer, no Johnny `relay.sh` or `fetch-and-score.sh` in the tree, the docs present, `code-writer.md` being a frontmatter-less stub, and the verdict parser, using a fake `agy` and a fake `claude` on PATH. A pass proves flags and sequencing; it does not prove the real `agy` accepts them (no live one-shot has run).

## Limits

- The reviewer's read-only rule is a prompt rule, not enforced, plus its tool list. The one-shot runs with `bypassPermissions`, so Bash can still write; only the agent file and `.claude/hooks/gpu-guard.sh` hold the line.
- The writer's git rules (branch, named-path staging, push only if told) are prompt rules too; see `docs/review-roles.md`, Writer git rules. Behind them there is less than for the reviewer: `--dangerously-skip-permissions`, no tool list, and **gpu-guard does not wrap `agy`** (it is a Claude `PreToolUse` hook; Antigravity's own `.agents/hooks.json` uses a different payload and was not tested). Details: `docs/antigravity-writer.md`.
- The interactive Antigravity App is not launched from here, and `launch.sh` has no reviewer-only mode (it always runs the writer first).
- A one-shot counts as host RAM in preflight headroom (alongside Ryzen Max Bot and Chrome). It loads no model.
- Johnny's CIS `tools/relay/relay.sh` is not here and is not to be ported.
