# tools/lab-seats

Launcher for the two standing Claude Code seats (`code-writer`, `adversarial-reviewer`; roster, reply format and precedence are in `docs/review-roles.md`). Ryzen Max Bot (the Grok bot on this MAX) calls it; it launches and relays and writes no product code.

## Use

```
cd /home/aj/projects/strix-halo-lab
tools/lab-seats/launch.sh --name seats-check --task "Read docs/review-roles.md and confirm the standing seats. Do not edit files."
```

`--task-file FILE` instead of `--task` reads the task from a file. `--name` defaults to a timestamp and must match `[A-Za-z0-9._-]+`; a name that already has a run is refused. Without `--dry-run` the script returns at once and the wrapper runs detached (`nohup`).

Dry run (writes the scratch files, prints `run.sh`, starts no `claude`):

```
cd /home/aj/projects/strix-halo-lab
tools/lab-seats/launch.sh --dry-run --name seats-dry --task "Read docs/review-roles.md and confirm the standing seats. Do not edit files."
```

## What it runs

Sequentially, cwd = the repo, prompt on stdin:

```
claude -p --model sonnet --effort high --permission-mode bypassPermissions --agent code-writer
claude -p --model sonnet --effort high --permission-mode bypassPermissions --agent adversarial-reviewer
```

Each is wrapped in `timeout --kill-after=30` (default 3600 s). The reviewer runs only if the writer exited 0. `--bg` is not used: it cannot be combined with `-p` (https://code.claude.com/docs/en/cli-reference). `effort: high` is also in each agent file (https://code.claude.com/docs/en/sub-agents).

## Caps

| Env var | Effect |
|---|---|
| `LAB_SEATS_TIMEOUT` | seconds per one-shot, default 3600; integer, baked into `run.sh` at launch. A timeout gives `writer-failed rc=124` or `reviewer-failed rc=124`. |
| `LAB_SEATS_MAX_USD` | optional; adds `--max-budget-usd N` to both one-shots (print mode only). Unset = no budget cap. |

There is no turn cap: `claude --help` (2.1.317) lists no `--max-turns`. Example:

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
| `writer-out.md`, `writer.log` | writer stdout (Detail / Relay / Outline) and stderr |
| `reviewer-out.md`, `reviewer.log` | reviewer stdout (verdict line first) and stderr |
| `verdict.txt` | output of `verdict.py` on `reviewer-out.md` |
| `run.status` | written last: `done verdict=...`, `writer-failed rc=N` or `reviewer-failed rc=N` |

`/tmp` does not survive a reboot. Anything worth keeping goes in a commit or the PR.

## verdict.py

`python3 -I tools/lab-seats/verdict.py FILE` prints the first non-blank line if it is exactly `APPROVE`, `APPROVE-WITH-NITS` or `REQUEST-CHANGES`. Exit 0 for the first two (nits do not block), 1 for `REQUEST-CHANGES`, 2 for anything else (a decorated or prefixed verdict is a format violation).

## Test

```
cd /home/aj/projects/strix-halo-lab
bash tools/lab-seats/test.sh
```

Loads no model and never starts the real `claude`. It asserts: no sudo in the launcher, the exact claude flags and writer-before-reviewer order in the generated `run.sh`, no Johnny `relay.sh` or `fetch-and-score.sh` in the tree, the docs and agent files present, and the verdict parser, using a fake `claude` on PATH.

## Limits

- The reviewer's read-only rule is a prompt rule, not enforced, plus its tool list. The one-shot runs with `bypassPermissions`, so Bash can still write; only the agent file and `.claude/hooks/gpu-guard.sh` hold the line.
- The writer's git rules (branch, named-path staging, push only if told) are prompt rules too; see `docs/review-roles.md`, Writer git rules.
- A one-shot counts as host RAM in preflight headroom (alongside Ryzen Max Bot and Chrome). It loads no model.
- Johnny's CIS `tools/relay/relay.sh` is not here and is not to be ported.
