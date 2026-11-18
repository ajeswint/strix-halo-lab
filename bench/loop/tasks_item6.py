#!/usr/bin/env python3
"""Task definitions for Roadmap Item 6 Pilot: Real-PR evaluation benchmark.

Defines 7 real PR tasks mechanically selected from strix-halo-lab repository history.
Each task defines:
  - id, pr_number, title
  - base_commit, merged_commit
  - has_tests (bool): whether reproducible test/check command exists
  - test_cmd (str): automated verification command to run on CPU
  - prompt (str): instructions shown to the model loop (task statement, rules, target files)
  - files (list[str]): expected target paths
  - hidden_diff: ground truth merged diff (held out, stripped from model loop via strip_hidden)
"""
import copy
import subprocess

PR_TASKS = [
    {
        "id": "item6_pr06",
        "pr_number": 6,
        "title": "debate.py: recover VERDICT/CONFIDENCE inside the closing code fence",
        "base_commit": "7a9f1d75c39f29d05ed92ce0671bb625ff143981",
        "merged_commit": "1a889a49feac28b2e637aa51936a2ea0f1ce69ca",
        "has_tests": True,
        "test_cmd": "python3 bench/loop/debate.py --selftest",
        "files": ["README.md", "bench/loop/debate.py"],
        "prompt": (
            "Repo ajeswint/strix-halo-lab: Fix `bench/loop/debate.py` parser logic.\n\n"
            "Problem: Some model outputs place `VERDICT:` and `CONFIDENCE:` inside the closing "
            "code fence of the solution code block, causing parse failures.\n\n"
            "Requirements:\n"
            "1. In `bench/loop/debate.py`, update `parse()` so that if the prose outside fences does not contain "
            "a verdict or confidence, check the closing lines of the code block body. Cut those closing lines from "
            "the returned code; skip any fence holding only those lines.\n"
            "2. Add read-only `reparse` subcommand to `debate.py` to inspect stored replies without running GPU or writing files.\n"
            "3. Update `debate.py --selftest` with tests verifying in-fence verdict/confidence recovery.\n"
            "4. Verify your fix with `python3 bench/loop/debate.py --selftest`."
        ),
    },
    {
        "id": "item6_pr08",
        "pr_number": 8,
        "title": "Seats: writer is Google Antigravity (Gemini 4 Argon, effort high)",
        "base_commit": "3ab57123b11fdd945f411bbd992fec08262c6ac8",
        "merged_commit": "a3003e92bea50e950791b2f0625b7323398a3cd2",
        "has_tests": True,
        "test_cmd": "bash tools/lab-seats/test.sh",
        "files": [
            ".claude/agents/adversarial-reviewer.md",
            ".claude/agents/code-writer.md",
            ".claude/hooks/gpu-guard.sh",
            "AGENTS.md",
            "CLAUDE.md",
            "README.md",
            "docs/antigravity-writer.md",
            "docs/review-roles.md",
            "orchestrator/context.md",
            "tools/lab-seats/README.md",
            "tools/lab-seats/launch.sh",
            "tools/lab-seats/test.sh",
        ],
        "prompt": (
            "Repo ajeswint/strix-halo-lab: Update the standing writer seat.\n\n"
            "Requirements:\n"
            "1. Move `code-writer` seat from Claude Code to Google Antigravity (Gemini 4 Argon, effort high).\n"
            "2. Create `docs/antigravity-writer.md` specifying Antigravity writer operating rules.\n"
            "3. Update `docs/review-roles.md`, `AGENTS.md`, and `CLAUDE.md` to reflect the new seat roster.\n"
            "4. Update launcher in `tools/lab-seats/launch.sh` to invoke `agy -p` with `--model` and `--dangerously-skip-permissions`.\n"
            "5. Update `tools/lab-seats/test.sh` to test the new launcher options.\n"
            "6. Verify with `bash tools/lab-seats/test.sh`."
        ),
    },
    {
        "id": "item6_pr13",
        "pr_number": 13,
        "title": "CRAwDAD noise floor + v10 retrieval retest (pre-run, no GPU)",
        "base_commit": "01c02e2b1527cb902a4a2728bd7d3aa92c68b3f2",
        "merged_commit": "74d35557c15931850945bf519426d6aaa55af41b",
        "has_tests": True,
        "test_cmd": "python3 -m unittest bench/loop/test_tasks_v10.py && python3 bench/loop/tasks_v10.py",
        "files": [
            "README.md",
            "bench/loop/debate.py",
            "bench/loop/memring.py",
            "bench/loop/run.py",
            "bench/loop/tasks_v10.py",
            "bench/loop/tasks_v10_mutants.py",
            "bench/loop/test_tasks_v10.py",
        ],
        "prompt": (
            "Repo ajeswint/strix-halo-lab: Add v10 held-out benchmark task suite and noise-floor pre-run.\n\n"
            "Requirements:\n"
            "1. Implement `bench/loop/tasks_v10.py` defining 90 held-out tasks across 4 families (formats, number_theory, graphs_geometry, simulation_dp).\n"
            "2. Implement `bench/loop/tasks_v10_mutants.py` and unit tests in `bench/loop/test_tasks_v10.py`.\n"
            "3. Add `--seed-base` argument to `bench/loop/debate.py`.\n"
            "4. Verify suite integrity with `python3 -m unittest bench/loop/test_tasks_v10.py` and `python3 bench/loop/tasks_v10.py`."
        ),
    },
    {
        "id": "item6_pr14",
        "pr_number": 14,
        "title": "README split (move-only) to cut agent token burn",
        "base_commit": "74d35557c15931850945bf519426d6aaa55af41b",
        "merged_commit": "af2b1a5c4ca765fd411f9e9f9d48c2d099420722",
        "has_tests": True,
        "test_cmd": "python3 -c \"import os; docs=['docs/setup-hardware.md','docs/serving.md','docs/orchestrator.md','docs/bench-small-model-loop.md','docs/crawdad-v7.md','docs/crawdad-v8.md','docs/crawdad-v10-noise.md','docs/roadmap.md']; assert all(os.path.exists(d) for d in docs); print('ALL DOCS EXIST')\"",
        "files": [
            "CLAUDE.md",
            "README.md",
            "docs/bench-small-model-loop.md",
            "docs/crawdad-v10-noise.md",
            "docs/crawdad-v7.md",
            "docs/crawdad-v8.md",
            "docs/orchestrator.md",
            "docs/roadmap.md",
            "docs/serving.md",
            "docs/setup-hardware.md",
        ],
        "prompt": (
            "Repo ajeswint/strix-halo-lab: Split README.md into topic documentation files under `docs/`.\n\n"
            "Requirements:\n"
            "1. Move-only split of the existing long `README.md` into topic files under `docs/`:\n"
            "   - `docs/setup-hardware.md`\n"
            "   - `docs/serving.md`\n"
            "   - `docs/orchestrator.md`\n"
            "   - `docs/bench-small-model-loop.md`\n"
            "   - `docs/crawdad-v7.md`\n"
            "   - `docs/crawdad-v8.md`\n"
            "   - `docs/crawdad-v10-noise.md`\n"
            "   - `docs/roadmap.md`\n"
            "2. Keep `README.md` concise with machine state, key decisions, and topic doc index.\n"
            "3. Update `CLAUDE.md` to instruct agents to read only `README.md` plus the topic doc relevant to their task."
        ),
    },
    {
        "id": "item6_pr15",
        "pr_number": 15,
        "title": "Stale-line fixes + writer roster update",
        "base_commit": "af2b1a5c4ca765fd411f9e9f9d48c2d099420722",
        "merged_commit": "6c56cc09eaafb2376422e73515b39f8193893740",
        "has_tests": False,
        "test_cmd": "bash tools/lab-seats/test.sh",
        "files": [
            ".claude/agents/evaluator.md",
            ".claude/agents/systems.md",
            ".claude/agents/trainer.md",
            ".claude/skills/measure/SKILL.md",
            ".claude/skills/preflight/SKILL.md",
            "AGENTS.md",
            "CLAUDE.md",
            "README.md",
            "docs/antigravity-writer.md",
            "docs/bench-small-model-loop.md",
            "docs/crawdad-v10-noise.md",
            "docs/review-roles.md",
            "docs/roadmap.md",
            "docs/serving.md",
            "docs/setup-hardware.md",
            "scripts/preflight.sh",
            "tools/lab-seats/README.md",
            "tools/lab-seats/launch.sh",
            "tools/lab-seats/test.sh",
        ],
        "prompt": (
            "Repo ajeswint/strix-halo-lab: Audit and fix stale lines across repository docs and agent configs.\n\n"
            "Requirements:\n"
            "1. Fix stale paths, references, and descriptions in `.claude/agents/`, `.claude/skills/`, and `docs/`.\n"
            "2. Update the writer seat from Argon to Gemini 3.8 Flash (`gemini-3.8-flash-high`) across "
            "`docs/review-roles.md`, `docs/antigravity-writer.md`, `AGENTS.md`, and `CLAUDE.md`.\n"
            "3. Verify lab-seats launcher test passes with `bash tools/lab-seats/test.sh`."
        ),
    },
    {
        "id": "item6_pr16",
        "pr_number": 16,
        "title": "crawdad-ground-v1: pre-run spec + grounded test-and-fix loop on v10 (draft, no GPU)",
        "base_commit": "6c56cc09eaafb2376422e73515b39f8193893740",
        "merged_commit": "1eb694f8aaf53f7730dd6922c1dcfe8d301208f6",
        "has_tests": True,
        "test_cmd": "python3 -m unittest bench/loop/test_ground.py && python3 bench/loop/ground.py --selftest",
        "files": [
            "README.md",
            "bench/loop/generate_visible.py",
            "bench/loop/ground.py",
            "bench/loop/tasks_v10_visible.py",
            "bench/loop/test_ground.py",
            "docs/crawdad-ground-v1.md",
        ],
        "prompt": (
            "Repo ajeswint/strix-halo-lab: Implement CRAwDAD Grounding v1 on v10 tasks (execution feedback loop).\n\n"
            "Requirements:\n"
            "1. Implement deterministic visible assert extraction in `bench/loop/generate_visible.py` generating `tasks_v10_visible.py`.\n"
            "2. Implement `bench/loop/ground.py` for Arm G (grounded with test feedback) vs Arm C (control without execution).\n"
            "3. Enforce strict information isolation: hidden tests and reference solutions must never enter model prompts.\n"
            "4. Add comprehensive unit tests in `bench/loop/test_ground.py`.\n"
            "5. Document pre-run specification in `docs/crawdad-ground-v1.md`.\n"
            "6. Verify with `python3 -m unittest bench/loop/test_ground.py` and `python3 bench/loop/ground.py --selftest`."
        ),
    },
    {
        "id": "item6_pr20",
        "pr_number": 20,
        "title": "Launcher guard: prereg must be committed and pushed before launch",
        "base_commit": "2bf58003ed4c138b20d0063dd5eab1bd4ddae637",
        "merged_commit": "dbf6a2cb442188dd8ad41811f548541130ae6320",
        "has_tests": True,
        "test_cmd": "bash scripts/test-prereg-guard.sh",
        "files": [
            ".claude/skills/measure/SKILL.md",
            "docs/setup-hardware.md",
            "scripts/launcher-template.sh",
            "scripts/prereg-guard.sh",
            "scripts/test-prereg-guard.sh",
        ],
        "prompt": (
            "Repo ajeswint/strix-halo-lab: Implement reusable preregistration launcher guard.\n\n"
            "Requirements:\n"
            "1. Implement `scripts/prereg-guard.sh` to verify a pre-registered bar file exists, is tracked, "
            "has no uncommitted changes, and is reachable from a pushed remote branch.\n"
            "2. Harden against bypasses: detect `skip-worktree` and `assume-unchanged` flags via `git ls-files -v`, "
            "verify against real remote commits using `git ls-remote`, reject empty files, and support `--head`.\n"
            "3. Implement `scripts/launcher-template.sh` utilizing `prereg-guard.sh --head`.\n"
            "4. Implement comprehensive test suite in `scripts/test-prereg-guard.sh`.\n"
            "5. Verify all tests pass with `bash scripts/test-prereg-guard.sh`."
        ),
    },
]


def load_tasks():
    """Return a deep copy of all PR tasks."""
    return copy.deepcopy(PR_TASKS)


def get_task(task_id_or_number):
    """Find a task by task ID (e.g. 'item6_pr06') or PR number (e.g. 6)."""
    for t in PR_TASKS:
        if t["id"] == task_id_or_number or t["pr_number"] == task_id_or_number:
            return copy.deepcopy(t)
    raise KeyError(f"Task not found: {task_id_or_number}")


def strip_hidden(task):
    """Strip reference diff and merge commits to prevent leakage into model loops.

    Returns a shallow copy containing only prompt, id, pr_number, title, base_commit,
    has_tests, test_cmd, and target files.
    """
    clean = dict(task)
    clean.pop("hidden_diff", None)
    clean.pop("merged_commit", None)
    return clean


def get_hidden_diff(task, repo_root=None):
    """Retrieve ground truth diff between base_commit and merged_commit for offline grading."""
    base = task["base_commit"]
    merged = task["merged_commit"]
    cmd = ["git", "diff", f"{base}..{merged}"]
    if repo_root:
        cmd = ["git", "-C", repo_root, "diff", f"{base}..{merged}"]
    try:
        return subprocess.check_output(cmd, stderr=subprocess.PIPE, text=True)
    except Exception as e:
        return f"# Error retrieving hidden diff: {e}"
