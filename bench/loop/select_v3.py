#!/usr/bin/env python3
"""Mechanical PR selection and offline bwrap verification for Item 6 Pilot v3.

Selects 7 unseen merged PRs from an external stdlib-only Python repository
(`more-itertools/more-itertools`) using a strictly mechanical rule defined
before inspecting any candidate diff:
  1. First-parent merge commits on master up to pinned HEAD matching
     `Merge pull request #N`.
  2. Merge commit timestamp (UTC) strictly after Qwen3.6-35B-A3B release
     (2026-04-15T05:59:19Z, Hugging Face) within
     [2026-05-01T00:00:00Z, 2026-11-21T00:00:00Z].
  3. Touches at least one runtime implementation file (`more_itertools/*.py`)
     and at least one test file (`tests/test_*.py`), with 2..8 changed files,
     no build/CI/dependency files (`.github/`, `requirements/`,
     `pyproject.toml`, `setup.cfg`, `tox.ini`), and total diff size
     (added + deleted lines via `git diff --numstat`) in [15, 250].
  4. Offline verification in the outer `/usr/bin/bwrap` sandbox (no network,
     stdlib-only `python3 -I -B`): the merged-commit test files PASS at
     `merged_commit` and FAIL at `base_commit`.
  5. Sorted by `(merged_at_utc, pr_number)` ascending; take the 7 most recent
     verified PRs (`verified[-7:]`).

Never prints diff hunks or reference solutions.
"""
import argparse
from datetime import datetime, timezone
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import pilot_pr  # noqa: E402

V3_REPO_SLUG = "more-itertools/more-itertools"
V3_REPO_URL = "https://github.com/more-itertools/more-itertools.git"
DEFAULT_V3_REPO_DIR = os.environ.get(
    "ITEM6_V3_REPO_DIR", "/data/datasets/item6-v3-repos/more-itertools.git"
)
V3_HEAD_COMMIT = "e3f79f4fde5f7c107f70a20730b17240a05ba99b"

# Contamination cutoff: Qwen/Qwen3.6-35B-A3B createdAt on Hugging Face is
# 2026-04-15T05:59:19.000Z (unsloth GGUF created 2026-04-16, lastModified 2026-04-20).
QWEN36_RELEASE_UTC = "2026-04-15T05:59:19Z"
QWEN36_RELEASE_SOURCE = "https://huggingface.co/Qwen/Qwen3.6-35B-A3B"

V3_WINDOW_START = "2026-05-01T00:00:00Z"
V3_WINDOW_END = "2026-11-21T00:00:00Z"
V3_MIN_CHANGED_LINES = 15
V3_MAX_CHANGED_LINES = 250
V3_MIN_CHANGED_FILES = 2
V3_MAX_CHANGED_FILES = 8
V3_BATCH_SIZE = 7

DISALLOWED_PATH_PREFIXES = (".github/", "requirements/")
DISALLOWED_EXACT_PATHS = frozenset({"pyproject.toml", "setup.cfg", "tox.ini"})


def _is_impl_py(path):
    return path.startswith("more_itertools/") and path.endswith(".py")


def _is_test_py(path):
    return path.startswith("tests/test_") and path.endswith(".py")


def _is_disallowed_path(path):
    if path in DISALLOWED_EXACT_PATHS:
        return True
    return any(path.startswith(pref) for pref in DISALLOWED_PATH_PREFIXES)


def _numstat_for_range(repo_dir, base_sha, merged_sha):
    """Return (changed_files: list[str], total_lines: int, has_binary: bool) via git diff --numstat."""
    out = subprocess.check_output(
        ["git", "-C", repo_dir, "diff", "--numstat", f"{base_sha}..{merged_sha}"],
        text=True,
    )
    files = []
    total_lines = 0
    has_binary = False
    for line in out.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        added_s, deleted_s, path = parts[0], parts[1], parts[2]
        files.append(path.strip())
        if added_s == "-" or deleted_s == "-":
            has_binary = True
        else:
            total_lines += int(added_s) + int(deleted_s)
    return sorted(files), total_lines, has_binary


def _test_files_to_cmd(test_files):
    """Build deterministic stdlib unittest command for changed test files."""
    mods = []
    for tf in sorted(test_files):
        mod = tf[:-3].replace("/", ".") if tf.endswith(".py") else tf
        mods.append(mod)
    return "python3 -m unittest " + " ".join(mods)


def verify_pr_in_bwrap(repo_dir, base_sha, merged_sha, test_files, timeout=120):
    """Verify in outer bwrap sandbox (offline, stdlib-only) that:
    1. Running merged test_files at merged_commit PASSES (rc == 0) and reports >= 1 test.
    2. Running the same merged test_files overlaid read-only onto base_commit FAILS (rc != 0).

    Returns (ok: bool, details: dict).
    """
    if not pilot_pr.has_bwrap():
        raise RuntimeError("bwrap sandbox is unavailable; cannot verify v3 candidates offline")

    test_cmd = _test_files_to_cmd(test_files)
    clean_env = pilot_pr.build_minimal_env()

    def _run_commit_with_ro_tests(commit_sha):
        wt_dir = tempfile.mkdtemp(prefix="v3_verify_wt_")
        ro_dir = tempfile.mkdtemp(prefix="v3_verify_ro_")
        try:
            pilot_pr.create_isolated_scratch_repo(repo_dir, commit_sha, wt_dir)
            ro_binds = []
            for tf in sorted(test_files):
                host_tf = pilot_pr.resolve_confined_path(ro_dir, tf)
                os.makedirs(os.path.dirname(host_tf), exist_ok=True)
                show_res = subprocess.run(
                    ["git", "-C", repo_dir, "show", f"{merged_sha}:{tf}"],
                    env=clean_env,
                    capture_output=True,
                )
                if show_res.returncode != 0:
                    return -1, f"failed to restore {tf} from {merged_sha}"
                with open(host_tf, "wb") as f:
                    f.write(show_res.stdout)
                ro_binds.append((host_tf, os.path.join("/work", tf)))

            home_dir, tmp_dir, shim_dir = pilot_pr.prepare_isolated_home_and_tmp(wt_dir)
            try:
                iso_cmd = pilot_pr._wrap_shell_with_isolated_python3(test_cmd, "/work")
                env = pilot_pr.build_minimal_env(home_dir="/home/pilot", tmp_dir="/tmp")
                bwrap_cmd = pilot_pr.build_outer_bwrap_cmd(
                    wt_dir, home_dir, tmp_dir, shim_dir, ["bash", "-c", iso_cmd], env, ro_binds=ro_binds
                )
                res = subprocess.run(
                    bwrap_cmd,
                    stdin=subprocess.DEVNULL,
                    cwd=wt_dir,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )
                out = (res.stdout or "") + (res.stderr or "")
                return res.returncode, out
            finally:
                pilot_pr.cleanup_isolated_home_and_tmp(wt_dir)
        finally:
            shutil.rmtree(wt_dir, ignore_errors=True)
            shutil.rmtree(ro_dir, ignore_errors=True)

    merged_rc, merged_out = _run_commit_with_ro_tests(merged_sha)
    m_ran = re.search(r"Ran (\d+) tests?", merged_out)
    merged_test_count = int(m_ran.group(1)) if m_ran else 0
    merged_ok = (
        merged_rc == 0
        and merged_test_count > 0
        and "OK" in merged_out
        and "FAILED" not in merged_out
        and "ERROR" not in merged_out
    )
    if not merged_ok:
        return False, {
            "merged_rc": merged_rc,
            "merged_test_count": merged_test_count,
            "base_rc": None,
            "reason": "merged_commit_tests_did_not_pass",
        }

    base_rc, base_out = _run_commit_with_ro_tests(base_sha)
    b_ran = re.search(r"Ran (\d+) tests?", base_out)
    base_test_count = int(b_ran.group(1)) if b_ran else 0
    base_failed = (base_rc != 0)
    if not base_failed:
        return False, {
            "merged_rc": merged_rc,
            "merged_test_count": merged_test_count,
            "base_rc": base_rc,
            "base_test_count": base_test_count,
            "reason": "base_commit_did_not_fail_merged_tests",
        }

    return True, {
        "merged_rc": merged_rc,
        "merged_test_count": merged_test_count,
        "base_rc": base_rc,
        "base_test_count": base_test_count,
        "test_cmd": test_cmd,
    }


def enumerate_and_filter_v3_prs(
    repo_dir=DEFAULT_V3_REPO_DIR,
    head_ref=V3_HEAD_COMMIT,
    verify_bwrap=True,
    batch_size=V3_BATCH_SIZE,
):
    """Apply the pre-registered mechanical selection rule to `repo_dir` up to `head_ref`.

    Returns (selected: list[dict], excluded: list[dict]).
    """
    t_start = datetime.fromisoformat(V3_WINDOW_START.replace("Z", "+00:00"))
    t_end = datetime.fromisoformat(V3_WINDOW_END.replace("Z", "+00:00"))

    log_out = subprocess.check_output(
        [
            "git",
            "-C",
            repo_dir,
            "log",
            "--merges",
            "--first-parent",
            "--format=%H|%P|%cI|%s",
            head_ref,
        ],
        text=True,
    )

    git_eligible = []
    excluded = []

    for line in log_out.splitlines():
        if not line.strip():
            continue
        sha, parents_str, ts_str, subj = line.split("|", 3)
        m = re.match(r"^Merge pull request #(\d+)\b", subj)
        if not m:
            continue
        pr_num = int(m.group(1))
        parents = parents_str.split()
        if len(parents) < 2:
            continue
        base_sha = parents[0]

        commit_dt = datetime.fromisoformat(ts_str).astimezone(timezone.utc)
        if not (t_start <= commit_dt <= t_end):
            if commit_dt < t_start:
                # First-parent history is roughly chronological, keep scanning just in case of skew
                continue
            excluded.append({"pr_number": pr_num, "reason": "outside_date_window"})
            continue

        changed_files, total_lines, has_binary = _numstat_for_range(repo_dir, base_sha, sha)
        if has_binary:
            excluded.append({"pr_number": pr_num, "reason": "binary_file_changed"})
            continue
        if any(_is_disallowed_path(f) for f in changed_files):
            excluded.append({"pr_number": pr_num, "reason": "disallowed_build_or_ci_path"})
            continue
        impl_files = [f for f in changed_files if _is_impl_py(f)]
        test_files = [f for f in changed_files if _is_test_py(f)]
        if not impl_files:
            excluded.append({"pr_number": pr_num, "reason": "no_runtime_py_changed"})
            continue
        if not test_files:
            excluded.append({"pr_number": pr_num, "reason": "no_test_py_changed"})
            continue
        if not (V3_MIN_CHANGED_FILES <= len(changed_files) <= V3_MAX_CHANGED_FILES):
            excluded.append({
                "pr_number": pr_num,
                "reason": f"file_count_out_of_range({len(changed_files)})",
            })
            continue
        if not (V3_MIN_CHANGED_LINES <= total_lines <= V3_MAX_CHANGED_LINES):
            excluded.append({
                "pr_number": pr_num,
                "reason": f"line_count_out_of_range({total_lines})",
            })
            continue

        git_eligible.append({
            "pr_number": pr_num,
            "merged_commit": sha,
            "base_commit": base_sha,
            "merged_at_utc": commit_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "files": changed_files,
            "impl_files": impl_files,
            "test_files": test_files,
            "total_changed_lines": total_lines,
            "test_cmd": _test_files_to_cmd(test_files),
            "subject": subj,
        })

    # Sort chronologically ascending: (merged_at_utc, pr_number)
    git_eligible.sort(key=lambda x: (x["merged_at_utc"], x["pr_number"]))

    if not verify_bwrap:
        selected = git_eligible[-batch_size:]
        for drop_cand in git_eligible[:-batch_size]:
            excluded.append({"pr_number": drop_cand["pr_number"], "reason": "older_than_latest_7"})
        excluded.sort(key=lambda x: x["pr_number"])
        return selected, excluded

    # Walk from most recent backwards until we collect batch_size verified PRs
    # (equivalent to verifying all git_eligible and taking verified[-batch_size:],
    # while still deterministic and faster on CPU).
    selected_rev = []
    for cand in reversed(git_eligible):
        if len(selected_rev) >= batch_size:
            excluded.append({"pr_number": cand["pr_number"], "reason": "older_than_latest_7"})
            continue
        ok, details = verify_pr_in_bwrap(
            repo_dir, cand["base_commit"], cand["merged_commit"], cand["test_files"]
        )
        if not ok:
            excluded.append({
                "pr_number": cand["pr_number"],
                "reason": f"bwrap_verify_failed:{details.get('reason')}",
            })
            continue
        cand_copy = dict(cand)
        cand_copy["expected_test_count"] = details["merged_test_count"]
        cand_copy["verify_details"] = details
        selected_rev.append(cand_copy)

    selected = list(reversed(selected_rev))
    excluded.sort(key=lambda x: x["pr_number"])
    return selected, excluded


def main(argv=None):
    parser = argparse.ArgumentParser(description="Mechanical PR selector for Item 6 Pilot v3")
    parser.add_argument("--repo-dir", default=DEFAULT_V3_REPO_DIR)
    parser.add_argument("--head", default=V3_HEAD_COMMIT)
    parser.add_argument("--no-verify-bwrap", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    sel, exc = enumerate_and_filter_v3_prs(
        repo_dir=args.repo_dir,
        head_ref=args.head,
        verify_bwrap=not args.no_verify_bwrap,
    )
    if args.json:
        print(json.dumps({"selected": sel, "excluded_count": len(exc)}, indent=2))
    else:
        print(f"Selected {len(sel)} PRs (excluded {len(exc)} in-window candidates):")
        for p in sel:
            print(
                f"  PR #{p['pr_number']:4d} merged={p['merged_at_utc']} "
                f"lines={p['total_changed_lines']:3d} files={len(p['files'])} "
                f"tests={p.get('expected_test_count', '?')} "
                f"base={p['base_commit'][:10]} merged={p['merged_commit'][:10]} "
                f"files={p['files']}"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
