# Antigravity writer seat

The `code-writer` seat is Google Antigravity, model Gemini 4 Argon, reasoning effort high. Set by AJ 2026-11-05 CT (America/Chicago); the Claude Code writer (`claude -p --agent code-writer`, Sonnet) is closed. `docs/review-roles.md` is canonical for the roster; this file holds the writer's operating rules, because Antigravity does not read `.claude/agents/` or `CLAUDE.md` on its own. Antigravity's own docs list `AGENTS.md` at the workspace root as an always-on rules file, so `AGENTS.md` carries the binding writer rules in short and this file has the detail (https://antigravity.google/docs/rules/).

The adversarial-reviewer is unchanged: Claude Code, Sonnet, effort high, `.claude/agents/adversarial-reviewer.md`.

## Two instances

| Instance | What | Launched by |
|---|---|---|
| Headless one-shot | `agy` 1.5.1 at `/home/aj/.local/bin/agy`, `agy -p "..." --model gemini-4-argon --effort high --dangerously-skip-permissions` | `tools/lab-seats/launch.sh` (Ryzen Max Bot), cwd = the repo, output in `/tmp/lab-seats/NAME/writer-out.md` |
| Interactive App | Antigravity App v2.29.0 linux-x64, `/home/aj/Applications/Antigravity/antigravity` | AJ. Set model Gemini 4 Argon and effort High in the UI after sign-in. |

## Verified, and not

Verified on this MAX 2026-11-05 (CT), without signing in and without a model call:

- `agy --version` prints `1.5.1`. `agy --help` lists `-p/--print/--prompt`, `--model`, `--effort` (`low|medium|high|xhigh|max`), `--dangerously-skip-permissions`, `--print-timeout`, `--output-format`, `--sandbox`, `--settings`, `--agent`.
- `agy changelog` (1.5.0) names the models "Gemini 4 Argon and Gemini 3.8 Flash".
- `agy models` answers "Please sign in to view available models". So the model slug is **not confirmed**. `gemini-4-argon` is the launcher default and is overridable with `LAB_SEATS_WRITER_MODEL`. A wrong slug exits non-zero with no silent fallback (https://antigravity.google/docs/cli/headless), so the writer fails loudly, not on a different model.
- Print mode takes the prompt as the `-p` argument; stdin is used only with `--input-format stream-json` (same page). The launcher therefore passes the prompt inline and redirects stdin from `/dev/null`, and refuses a writer prompt over 100000 bytes (Linux caps one argument at 128 KiB).

Not verified (no sign-in, so no live one-shot has run): that the slug resolves, that `--effort high` is accepted with that model, how long a real writer run takes (the 3600 s default is unmeasured), host RAM of an `agy` run, and the App's behavior on rules files. `bash tools/lab-seats/test.sh` covers the launcher against a fake `agy`; it proves flags and sequencing, not the real CLI.

## Permissions posture

Headless mode has no approval prompt. A tool call with no matching allow rule is soft-denied: the run continues, exits 0, and prints a notice on stderr. In `default` mode shell commands ask, so without a flag the writer could not run `git commit` and would still exit 0 (https://antigravity.google/docs/cli/headless).

Choice: `--dangerously-skip-permissions` on the writer one-shot. For approval it matches the old `bypassPermissions` posture of both Claude seats. It is weaker on enforcement, and that is accepted, not hidden:

- The Claude writer had a tool list in its agent file and the gpu-guard hook. The `agy` writer has neither. The rules below are prompt rules.
- A scoped alternative exists (`permissions.allow` rules, `--sandbox`, `--settings`). Their schemas and their effect on `git`, `gh` and the repo's scripts are untested here, so none is wired. If AJ wants one, test it with a fake task first.

## gpu-guard

`.claude/hooks/gpu-guard.sh` is a Claude Code `PreToolUse` hook: it reads `.tool_input.command` from Claude's hook JSON and blocks with exit 2. It stays on the reviewer path (`adversarial-reviewer.md`) and the domain arms that name it. **It does not wrap `agy`**: the hook is registered in Claude agent frontmatter, and `agy` does not read that.

Antigravity has its own hooks (`.agents/hooks.json` in the workspace, `~/.gemini/config/hooks.json` globally; events include `PreToolUse`; a hook denies with JSON on stdout carrying `decision`; https://antigravity.google/docs/hooks). That payload and decision format differ from Claude's, and the docs do not say whether hooks run in `-p` mode. No equivalent hook is shipped, because it cannot be tested without a signed-in session. Until one is tested, the model-load rules for the Antigravity writer are rules, not a tripwire:

- Do not load a model. The launcher's tasks are drafts; model servers start and stop only through `scripts/llmctl.py`, with `scripts/preflight.sh` right before any load, and never beside the DeepSeek server (~85 GiB GTT). Ask AJ.
- A writer task that needs a GPU is not a writer task: stop and say so in the Relay.
- Backstop that does hold: any Claude seat or domain arm that runs Bash still goes through gpu-guard, and the reviewer checks the writer's diff for loads.

## Writer rules

Same as the old code-writer, restated here for a model that does not read `CLAUDE.md`:

- Read `README.md`, then `CLAUDE.md` and `docs/review-roles.md`, before drafting. `CLAUDE.md` is the working-rule list: terse, mechanism-level; exact copy-paste commands, no `<placeholders>` in command blocks; measured numbers beat claims; verify versions and install steps against upstream docs and cite the URL.
- Do not review or approve your own draft. Do not treat Ryzen Max Bot's relay as a license to skip the reviewer.
- Git: work on the branch the task names, never `main`. Stage named paths only (`git add path1 path2`), never `git add -A`, `git add .` or `git commit -a`. Check `git status` and `git diff --cached` before each commit. Leave AJ's unrelated edits (for example `.claude/settings.json`) unstaged. Push only if the task says so, only that branch, never force. Do not merge: Ryzen Max Bot merges after an `APPROVE*` sign-off.
- Soft nits are parked unless AJ asks for a chase (`docs/review-roles.md`, Reply format). A blocking `REQUEST-CHANGES` finding is fixed.
- Files under `bench/`, `etc/`, `systemd/`, `envs/`, `models/`, `scripts/` mirror live paths: update the copy in the same change.
- Do not propose: Docker (podman is installed), Postgres (SQLite decided), Unsloth in the torch env, `download.pytorch.org` ROCm wheels, IOMMU off, GTT above 108 GiB.
- Stay in this repo's Roadmap. Flag before drifting into Johnny, Unreal or another project.
- No subagents unless AJ asks (2026-10-15: four unrequested writer agents, one OOM). Antigravity can start subagents; that rule applies to them.
- Never run sudo, never store credentials. Sign-in to Antigravity is AJ's, interactive, once; the writer does not touch `~/.gemini`.
- Reply format: Detail, then Relay, then Outline. The Relay is for the adversarial-reviewer: short, pasteable, PR URL in it. A one-line answer skips the three parts.

## Gaps

- The interactive App has no launcher path into the reviewer: `launch.sh` always runs the writer first. Until a reviewer-only mode exists, Ryzen Max Bot or AJ starts the reviewer by hand with the App's Relay and branch.
- The `agy` writer has no budget cap (`LAB_SEATS_MAX_USD` applies to the reviewer only) and no turn cap; the outer `timeout` is the only cap. `agy -p` without `--print-timeout` waits for background tasks to finish (`agy changelog`, 1.5.0), so the timeout matters. It signals the `agy` process only; after rc 124 or 137 check `pgrep -af agy` as well as `git status` and `.git/index.lock`.
