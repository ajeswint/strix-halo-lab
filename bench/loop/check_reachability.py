#!/usr/bin/env python3
"""Offline CPU-only reachability check for Item 6 Pilot v2 structured edit tools.

Replays each of the 7 merged PR reference solutions strictly through pilot_pr.ToolSession
under the real v2 tool limits:
  - read_file window cap (READ_FILE_MAX_LINES = 250 lines/call)
  - search_replace exact-unique-match, whole-file rewrite cap, and stub/truncation guard
  - create_file overwrite cap (MAX_EXISTING_FILE_OVERWRITES = 1 per task) and stub/truncation guard
  - finish-time unrelocated-truncation check (ToolSession.check_no_unrelocated_truncations)

ISOLATION INVARIANT:
This script reads merged_commit / hidden_diff strictly offline outside the model loop.
It MUST NEVER be imported by pilot_pr.py or any in-loop code path.
"""
import difflib
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import pilot_pr  # noqa: E402
import tasks_item6  # noqa: E402


def _git_show_bytes(repo_root, rev, rel_path):
    res = subprocess.run(
        ["git", "-C", repo_root, "show", f"{rev}:{rel_path}"],
        capture_output=True,
    )
    if res.returncode != 0:
        return None
    return res.stdout


def _git_is_executable(repo_root, rev, rel_path):
    res = subprocess.run(
        ["git", "-C", repo_root, "ls-tree", rev, "--", rel_path],
        capture_output=True,
        text=True,
    )
    if res.returncode != 0 or not res.stdout.strip():
        return False
    mode = res.stdout.strip().split()[0]
    return mode == "100755"


def _build_unique_hunk_edits(base_text, merged_text):
    """Decompose base_text -> merged_text into exact-unique-match (old, new) search_replace operations."""
    base_lines = base_text.splitlines(keepends=True)
    merged_lines = merged_text.splitlines(keepends=True)
    sm = difflib.SequenceMatcher(None, base_lines, merged_lines, autojunk=False)
    opcodes = [op for op in sm.get_opcodes() if op[0] != "equal"]
    if not opcodes:
        return []

    # Group nearby non-equal opcodes separated by <= 3 equal lines so edits stay compact and contextual
    groups = []
    for op in opcodes:
        if not groups:
            groups.append([op])
        else:
            prev_i2 = groups[-1][-1][2]
            if op[1] - prev_i2 <= 3:
                groups[-1].append(op)
            else:
                groups.append([op])

    # Apply hunks sequentially against a simulated buffer so every (old, new) is guaranteed unique at apply time
    curr_lines = list(base_lines)
    offset = 0
    edits = []
    for grp in groups:
        i1 = grp[0][1] + offset
        i2 = grp[-1][2] + offset
        j1 = grp[0][3]
        j2 = grp[-1][4]
        new_core = "".join(merged_lines[j1:j2])

        # Expand context until `old` is non-empty and occurs uniquely in current text
        curr_text = "".join(curr_lines)
        found = None
        for ctx in (1, 2, 3, 5, 8, 12, 20, 40, len(curr_lines)):
            c_start = max(0, i1 - ctx)
            c_end = min(len(curr_lines), i2 + ctx)
            old_chunk = "".join(curr_lines[c_start:c_end])
            if not old_chunk:
                continue
            if curr_text.count(old_chunk) == 1:
                prefix = "".join(curr_lines[c_start:i1])
                suffix = "".join(curr_lines[i2:c_end])
                new_chunk = prefix + new_core + suffix
                if old_chunk != new_chunk:
                    found = (old_chunk, new_chunk, c_start, c_end)
                    break
        if found is None:
            return None
        old_chunk, new_chunk, c_start, c_end = found
        edits.append((old_chunk, new_chunk))
        # Update simulated lines & offset
        replacement_lines = new_chunk.splitlines(keepends=True)
        curr_lines[c_start:c_end] = replacement_lines
        offset += len(replacement_lines) - (c_end - c_start)

    if "".join(curr_lines) != merged_text:
        return None
    return edits


def replay_task_reference(task, repo_root=REPO_ROOT):
    """Replay one task's merged reference diff strictly through ToolSession limits.

    Returns a dict summarizing reachability, tool counts, overwrites_used, and errors (empty on success).
    """
    tid = task["id"]
    base_sha = task["base_commit"]
    merged_sha = task["merged_commit"]

    scratch_dir = tempfile.mkdtemp(prefix=f"reach_{tid}_")
    errors = []
    stats = {
        "task_id": tid,
        "pr_number": task["pr_number"],
        "reachable": False,
        "read_calls": 0,
        "create_calls": 0,
        "search_replace_calls": 0,
        "overwrites_used": 0,
        "total_tool_calls": 0,
        "files_checked": 0,
        "errors": errors,
    }
    try:
        pilot_pr.create_isolated_scratch_repo(repo_root, base_sha, scratch_dir)
        session = pilot_pr.ToolSession(scratch_dir, max_overwrites=pilot_pr.MAX_EXISTING_FILE_OVERWRITES)

        # Enumerate changed files between base_commit and merged_commit
        ns_out = subprocess.check_output(
            ["git", "-C", repo_root, "diff", "--name-status", f"{base_sha}..{merged_sha}"],
            text=True,
        ).strip()
        new_files = []
        mod_files = []
        del_files = []
        for line in ns_out.splitlines():
            parts = line.split("\t")
            status = parts[0]
            rel_path = parts[-1]
            if status.startswith("A"):
                new_files.append(rel_path)
            elif status.startswith("D"):
                del_files.append(rel_path)
            else:
                mod_files.append(rel_path)

        if del_files:
            errors.append(f"Deleted files unsupported by tool surface: {del_files}")
            return stats

        # 1. Exercise read_file in READ_FILE_MAX_LINES (250-line) windows over every modified existing file
        for rel_path in mod_files:
            base_bytes = _git_show_bytes(repo_root, base_sha, rel_path)
            if base_bytes is None:
                errors.append(f"Missing base file {rel_path}")
                return stats
            n_lines = len(base_bytes.decode("utf-8", errors="replace").splitlines())
            if n_lines > 0:
                start = 1
                while start <= n_lines:
                    end = min(n_lines, start + pilot_pr.READ_FILE_MAX_LINES - 1)
                    ok, out, _ = session.execute({
                        "tool": "read_file",
                        "args": {"path": rel_path, "start": start, "end": end},
                    })
                    stats["read_calls"] += 1
                    stats["total_tool_calls"] += 1
                    if not ok:
                        errors.append(f"read_file failed for {rel_path}:{start}-{end}: {out}")
                        return stats
                    start = end + 1

        # 2. Create all brand-new files first (so split/move destinations exist before shrinking source files)
        for rel_path in new_files:
            merged_bytes = _git_show_bytes(repo_root, merged_sha, rel_path)
            if merged_bytes is None:
                errors.append(f"Missing merged new file {rel_path}")
                return stats
            merged_text = merged_bytes.decode("utf-8")
            is_exec = _git_is_executable(repo_root, merged_sha, rel_path)
            ok, out, _ = session.execute({
                "tool": "create_file",
                "args": {"path": rel_path, "content": merged_text, "executable": is_exec},
            })
            stats["create_calls"] += 1
            stats["total_tool_calls"] += 1
            if not ok:
                errors.append(f"create_file failed for new file {rel_path}: {out}")
                return stats

        # 3. Replay every modified existing file via targeted search_replace hunks,
        #    falling back to justified create_file(overwrite=True) only if hunks hit rewrite cap
        for rel_path in mod_files:
            base_text = _git_show_bytes(repo_root, base_sha, rel_path).decode("utf-8")
            merged_text = _git_show_bytes(repo_root, merged_sha, rel_path).decode("utf-8")
            is_exec = _git_is_executable(repo_root, merged_sha, rel_path)
            hunks = _build_unique_hunk_edits(base_text, merged_text)
            used_overwrite = False

            if hunks is not None:
                # Try applying all hunks via search_replace
                full_target = pilot_pr.resolve_confined_path(scratch_dir, rel_path)
                snapshot = open(full_target, "r", encoding="utf-8").read()
                hunk_ok = True
                for old_chunk, new_chunk in hunks:
                    ok, out, _ = session.execute({
                        "tool": "search_replace",
                        "args": {"path": rel_path, "old": old_chunk, "new": new_chunk},
                    })
                    stats["search_replace_calls"] += 1
                    stats["total_tool_calls"] += 1
                    if not ok:
                        # Roll back partial file state and try single justified overwrite
                        with open(full_target, "w", encoding="utf-8") as f:
                            f.write(snapshot)
                        hunk_ok = False
                        break
                if not hunk_ok:
                    ok_ow, out_ow, _ = session.execute({
                        "tool": "create_file",
                        "args": {
                            "path": rel_path,
                            "content": merged_text,
                            "overwrite": True,
                            "justification": f"Full restructure of {rel_path} required after moving sections.",
                            "executable": is_exec,
                        },
                    })
                    stats["create_calls"] += 1
                    stats["total_tool_calls"] += 1
                    if not ok_ow:
                        errors.append(f"Both search_replace and justified overwrite failed for {rel_path}: {out_ow}")
                        return stats
                    used_overwrite = True
            else:
                ok_ow, out_ow, _ = session.execute({
                    "tool": "create_file",
                    "args": {
                        "path": rel_path,
                        "content": merged_text,
                        "overwrite": True,
                        "justification": f"Full restructure of {rel_path} required by PR specification.",
                        "executable": is_exec,
                    },
                })
                stats["create_calls"] += 1
                stats["total_tool_calls"] += 1
                if not ok_ow:
                    errors.append(f"Justified overwrite failed for {rel_path}: {out_ow}")
                    return stats
                used_overwrite = True

            # Verify mode if executable bit was added on an existing file without overwrite
            if is_exec and not used_overwrite:
                full_target = pilot_pr.resolve_confined_path(scratch_dir, rel_path)
                if not (os.stat(full_target).st_mode & 0o111):
                    errors.append(f"Executable bit missing on modified file {rel_path}")
                    return stats

        # 4. Run finish-time stub/truncation guard check
        stub_ok, stub_err = session.check_no_unrelocated_truncations()
        if not stub_ok:
            errors.append(f"Finish-time stub guard failed: {stub_err}")
            return stats

        # 5. Verify byte-for-byte match against merged_commit for every touched file
        all_touched = new_files + mod_files
        for rel_path in all_touched:
            full_target = pilot_pr.resolve_confined_path(scratch_dir, rel_path)
            expected = _git_show_bytes(repo_root, merged_sha, rel_path)
            with open(full_target, "rb") as f:
                actual = f.read()
            if actual != expected:
                errors.append(f"Byte mismatch after replay on {rel_path}")
                return stats
            stats["files_checked"] += 1

        # 6. Verify harness git diff capture is non-empty
        final_diff = pilot_pr.capture_worktree_diff(scratch_dir, base_sha)
        if not final_diff.strip():
            errors.append("Captured worktree diff is empty after replay")
            return stats

        stats["overwrites_used"] = session.overwrites_used
        stats["reachable"] = True
        return stats
    finally:
        shutil.rmtree(scratch_dir, ignore_errors=True)


def check_all_tasks(repo_root=REPO_ROOT):
    """Replay all 7 Item 6 tasks and return list of per-task reachability reports."""
    return [replay_task_reference(t, repo_root=repo_root) for t in tasks_item6.load_tasks()]


def main():
    reports = check_all_tasks(REPO_ROOT)
    failed = [r for r in reports if not r["reachable"]]
    for r in reports:
        status = "REACHABLE" if r["reachable"] else "UNREACHABLE"
        print(
            f"{r['task_id']:12} pr=#{r['pr_number']:<2} {status:11} "
            f"files={r['files_checked']:<2} reads={r['read_calls']:<2} "
            f"sr={r['search_replace_calls']:<2} creates={r['create_calls']:<2} "
            f"overwrites={r['overwrites_used']}/{pilot_pr.MAX_EXISTING_FILE_OVERWRITES}"
            + (f" errors={r['errors']}" if r["errors"] else "")
        )
    if failed:
        print(f"FAIL: {len(failed)}/{len(reports)} tasks unreachable under current tool limits", file=sys.stderr)
        return 1
    print(f"OK: {len(reports)}/{len(reports)} Item 6 reference solutions reachable under v2 tool limits")
    return 0


if __name__ == "__main__":
    sys.exit(main())
