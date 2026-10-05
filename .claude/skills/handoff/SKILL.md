---
name: handoff
description: End-of-session handoff. Verifies machine and git state, updates memory, and writes the handoff note in the standard format for the next session.
disable-model-invocation: true
---

# Session handoff

Gather state fresh. Do not write any of it from memory of earlier in the session.

```
git -C ~/projects/strix-halo-lab status --short && git -C ~/projects/strix-halo-lab log --oneline origin/main..HEAD && git -C ~/projects/strix-halo-lab ls-remote origin main
scripts/preflight.sh; scripts/llm-serve.sh status; systemctl is-active llama-deepseek
scripts/drift-check.sh
bash .claude/hooks/gpu-guard-test.sh | tail -1
```

Then:
1. Unpushed commits or a dirty tree: say so. Do not push or commit without the user's yes.
2. A small model still on :8081 that you started: say so and offer to stop it. Leaving one resident blocks the next session's loads.
3. Update the memory files under `~/.claude/projects/-home-aj-projects-strix-halo-lab/memory/` that this session made stale, and `MEMORY.md`. Absolute dates. Do not duplicate what README or git already records.
4. Write the note in this shape, terse, facts only:

```
strix-halo-lab handoff, YYYY-MM-DD (session N)

STATE
- main vs origin/main (hashes), tree clean/dirty.
- llama-deepseek: active/inactive. llm-8081: active/inactive. GTT used.
- Drift: none / list. Guard matrix: n/n.
- Memory files updated: ...

DONE THIS SESSION
1. What changed, with commit hashes and the measured numbers behind it.
   - Not done / skipped by decision, and why.
   - Errors made and how they were corrected.

OPEN NOTES
- Things the next session must know that are not in README.

PROPOSED NEXT GOAL (awaiting user's choice)
- One goal, what it needs from the user, and 1-2 alternatives.

Commits this session: ...
```

5. If the session changed machine state or a decision, check that README says so. The README is the record. The handoff is a pointer.
