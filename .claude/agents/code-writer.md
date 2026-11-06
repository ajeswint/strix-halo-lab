# code-writer: moved to Google Antigravity

This file is a stub so old links do not 404. It is **not a Claude Code agent**: it has no YAML frontmatter on purpose, and Claude Code treats a file with no `name` as documentation kept beside the agents, not as a subagent (https://code.claude.com/docs/en/sub-agents). `claude -p --agent code-writer` is closed.

Since 2026-11-05 CT (AJ, America/Chicago) the writer seat is **Google Antigravity**, model **Gemini 4 Argon**, reasoning effort **high**:

- Headless one-shot: `agy -p ... --model gemini-4-argon --effort high --dangerously-skip-permissions`, launched by `tools/lab-seats/launch.sh`.
- Interactive: the Antigravity App under `/home/aj/Applications/Antigravity`.
- Operating rules (git staging, Detail / Relay / Outline, permissions posture, gpu-guard status): `docs/antigravity-writer.md`. Binding short form in `AGENTS.md`.
- Roster, reply format, merge and precedence: `docs/review-roles.md` (canonical).

The Claude Code seat that remains is `adversarial-reviewer` (`.claude/agents/adversarial-reviewer.md`, Sonnet, high effort). The last Claude writer definition (Sonnet, high effort, gpu-guard hook on Bash) is in git history before the commit that added this stub.
