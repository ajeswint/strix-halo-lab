#!/usr/bin/env python3
r"""Mechanical PR selection and offline bwrap verification for Item 6 Pilot v4.

Pre-stated mechanical selection rule (written BEFORE inspecting any candidate diff
or fetching post-2026-11-17 repo histories):

Contamination cutoff (primary source):
  Qwen/Qwen3.6-35B-A3B Hugging Face release: 2026-04-15T05:59:19Z
  Source: https://huggingface.co/Qwen/Qwen3.6-35B-A3B (createdAt)
  (unsloth GGUF created 2026-04-16T04:31:31Z, lastModified 2026-04-20T12:42:25Z)

Phase 1 — Primary repo (`more-itertools/more-itertools`):
  - Exclude the 7 frozen v3 development-set PRs: {1260, 1269, 1305, 1322, 1342, 1345, 1311}.
  - Window: merge/commit UTC timestamp in [2026-11-18T00:00:00Z, 2026-11-22T23:59:59Z]
    (strictly after 2026-11-17).
  - First-parent commits on the default branch matching either:
      - `^Merge pull request #(\d+)\b` (merge commit; base = parents[0]), OR
      - `\(#(\d+)\)$` (GitHub squash-merge commit; base = parents[0]).
  - Purely from `git diff --numstat base..merged` (never inspecting diff hunks):
      - No binary files and no file renames (`=>`).
      - No build/CI/dependency files (`.github/`, `requirements/`,
        `pyproject.toml`, `setup.cfg`, `setup.py`, `tox.ini`, `Makefile`).
      - >= 1 runtime implementation `.py` file (`more_itertools/*.py`) and
        >= 1 test `.py` file (`tests/test_*.py`).
      - Changed file count in [2, 8]; total changed lines (added + deleted) in [15, 250].
  - Offline CPU verification in outer `/usr/bin/bwrap` (`python3 -I -B`, `--unshare-net`,
    stdlib-only `unittest`): merged-commit test files mounted read-only PASS at
    `merged_commit` (`rc == 0`, `Ran N tests`, `OK`, no `FAILED`/`ERROR`) and FAIL at
    `base_commit` (`rc != 0`).
  - Sort verified Phase 1 candidates ascending by `(merged_at_utc, pr_number)` and take up
    to the 7 most recent (`verified[-7:]`).

Phase 2 — Single fallback repo (ONLY if Phase 1 yields fewer than 7 qualifying PRs):
  - Evaluate the fixed priority shortlist of pure-Python, zero-runtime-dependency,
    stdlib-`unittest` GitHub repositories in exact order:
      1. `python-markdown/markdown`
      2. `pyparsing/pyparsing`
      3. `lark-parser/lark`
      4. `python/typing_extensions`
      5. `bottlepy/bottle`
  - Window: [2026-05-01T00:00:00Z, 2026-11-22T23:59:59Z] (strictly post-Qwen3.6 release
    with > 15-day buffer).
  - Exact same first-parent PR commit matching, numstat filters, and offline bwrap
    pass-at-merged / fail-at-base verification as Phase 1.
  - Pick the FIRST repo in shortlist order that reaches `needed = 7 - len(phase1)` verified
    PRs and take its `needed` most recent verified PRs (`verified[-needed:]`).
  - If NO single shortlist repo reaches `needed`, do NOT relax any filter and do NOT mix
    in a 3rd repo: pick the single shortlist repo with the highest verified count (ties
    broken by shortlist priority order), freeze `phase1 + phase2`, and report the shortfall.

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

DEFAULT_V4_REPOS_DIR = os.environ.get(
    "ITEM6_V4_REPOS_DIR", "/data/datasets/item6-v4-repos"
)

# Contamination cutoff: Qwen/Qwen3.6-35B-A3B createdAt on Hugging Face is
# 2026-04-15T05:59:19.000Z (unsloth GGUF created 2026-04-16, lastModified 2026-04-20).
QWEN36_RELEASE_UTC = "2026-04-15T05:59:19Z"
QWEN36_RELEASE_SOURCE = "https://huggingface.co/Qwen/Qwen3.6-35B-A3B"

V3_EXCLUDED_PR_NUMBERS = frozenset({1260, 1269, 1305, 1322, 1342, 1345, 1311})

V4_PRIMARY_WINDOW_START = "2026-11-18T00:00:00Z"
V4_PRIMARY_WINDOW_END = "2026-11-22T23:59:59Z"

V4_FALLBACK_WINDOW_START = "2026-05-01T00:00:00Z"
V4_FALLBACK_WINDOW_END = "2026-11-22T23:59:59Z"

V4_MIN_CHANGED_LINES = 15
V4_MAX_CHANGED_LINES = 250
V4_MIN_CHANGED_FILES = 2
V4_MAX_CHANGED_FILES = 8
V4_BATCH_SIZE = 7

DISALLOWED_PATH_PREFIXES = (".github/", "requirements/")
DISALLOWED_EXACT_PATHS = frozenset({
    "pyproject.toml",
    "setup.cfg",
    "setup.py",
    "tox.ini",
    "Makefile",
})

# Pinned commits recorded at 2026-11-22 fetch time for deterministic reproducibility.
V4_PRIMARY_SPEC = {
    "slug": "more-itertools/more-itertools",
    "name": "more-itertools",
    "url": "https://github.com/more-itertools/more-itertools.git",
    "pinned_head": "e3f79f4fde5f7c107f70a20730b17240a05ba99b",
    "impl_prefixes": ("more_itertools/",),
    "impl_exact": (),
    "test_prefixes": ("tests/",),
    "test_exact": (),
    "test_src_dir": None,
}

# Fixed priority shortlist of pure-Python, zero-dependency, stdlib-unittest fallback repos
# stated BEFORE inspecting any candidate repo or diff.
V4_FALLBACK_SPECS = [
    {
        "slug": "python-markdown/markdown",
        "name": "markdown",
        "url": "https://github.com/python-markdown/markdown.git",
        "pinned_head": "5609061bd3359e882b745de184ebfe5ef1c08011",
        "impl_prefixes": ("markdown/",),
        "impl_exact": (),
        "test_prefixes": ("tests/",),
        "test_exact": (),
        "test_src_dir": None,
    },
    {
        "slug": "pyparsing/pyparsing",
        "name": "pyparsing",
        "url": "https://github.com/pyparsing/pyparsing.git",
        "pinned_head": "810199f89bf916590426e1c5cb3d612584f11a2f",
        "impl_prefixes": ("pyparsing/",),
        "impl_exact": (),
        "test_prefixes": ("tests/",),
        "test_exact": (),
        "test_src_dir": None,
    },
    {
        "slug": "lark-parser/lark",
        "name": "lark",
        "url": "https://github.com/lark-parser/lark.git",
        "pinned_head": "9a4fb9c7458e8155636773a3cded0016d52516da",
        "impl_prefixes": ("lark/",),
        "impl_exact": (),
        "test_prefixes": ("tests/",),
        "test_exact": (),
        "test_src_dir": None,
    },
    {
        "slug": "python/typing_extensions",
        "name": "typing_extensions",
        "url": "https://github.com/python/typing_extensions.git",
        "pinned_head": "a2024556ab75799fbd2f41d1c2d114dd6372de12",
        "impl_prefixes": (),
        "impl_exact": ("src/typing_extensions.py",),
        "test_prefixes": (),
        "test_exact": ("src/test_typing_extensions.py",),
        "test_src_dir": "src",
    },
    {
        "slug": "bottlepy/bottle",
        "name": "bottle",
        "url": "https://github.com/bottlepy/bottle.git",
        "pinned_head": "aba0c1a7ee59ed851db001d100b6a792b54a94a3",
        "impl_prefixes": (),
        "impl_exact": ("bottle.py",),
        "test_prefixes": ("test/",),
        "test_exact": (),
        "test_src_dir": None,
    },
]


def _is_impl_py(path, repo_spec):
    if not path.endswith(".py"):
        return False
    if path in repo_spec.get("impl_exact", ()):
        return True
    return any(path.startswith(pref) for pref in repo_spec.get("impl_prefixes", ()))


def _is_test_py(path, repo_spec):
    if not path.endswith(".py"):
        return False
    if path in repo_spec.get("test_exact", ()):
        return True
    base = os.path.basename(path)
    if not base.startswith("test_"):
        return False
    return any(path.startswith(pref) for pref in repo_spec.get("test_prefixes", ()))


def _is_disallowed_path(path):
    if path in DISALLOWED_EXACT_PATHS:
        return True
    return any(path.startswith(pref) for pref in DISALLOWED_PATH_PREFIXES)


def _extract_pr_number(subject):
    """Extract PR number from first-parent GitHub merge or squash-merge commit subject."""
    s = (subject or "").strip()
    m = re.match(r"^Merge pull request #(\d+)\b", s)
    if m:
        return int(m.group(1)), "merge"
    m2 = re.search(r"\(#(\d+)\)$", s)
    if m2:
        return int(m2.group(1)), "squash"
    return None, None


def _numstat_for_range(repo_dir, base_sha, merged_sha):
    """Return (changed_files, total_lines, has_binary, has_rename) via git diff --numstat."""
    out = subprocess.check_output(
        ["git", "-C", repo_dir, "diff", "--no-renames", "--numstat", f"{base_sha}..{merged_sha}"],
        text=True,
    )
    files = []
    total_lines = 0
    has_binary = False
    has_rename = False
    for line in out.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        added_s, deleted_s, path = parts[0], parts[1], parts[2].strip()
        if " => " in path:
            has_rename = True
        files.append(path)
        if added_s == "-" or deleted_s == "-":
            has_binary = True
        else:
            total_lines += int(added_s) + int(deleted_s)
    return sorted(files), total_lines, has_binary, has_rename


def _test_files_to_cmd(test_files, repo_spec):
    """Build deterministic stdlib unittest command for changed test files."""
    src_dir = repo_spec.get("test_src_dir")
    if src_dir:
        basenames = sorted(os.path.basename(tf) for tf in test_files)
        if len(basenames) == 1:
            return f"python3 -m unittest discover -s {src_dir} -p {basenames[0]}"
        return f"python3 -m unittest discover -s {src_dir} -p 'test_*.py'"
    mods = []
    for tf in sorted(test_files):
        mod = tf[:-3].replace("/", ".") if tf.endswith(".py") else tf
        mods.append(mod)
    return "python3 -m unittest " + " ".join(mods)


def verify_pr_in_bwrap(repo_dir, base_sha, merged_sha, test_files, repo_spec, timeout=120):
    """Verify in outer bwrap sandbox (offline, stdlib-only) that:
    1. Running merged test_files at merged_commit PASSES (rc == 0) and reports >= 1 test.
    2. Running the same merged test_files overlaid read-only onto base_commit FAILS (rc != 0).

    Returns (ok: bool, details: dict).
    """
    if not pilot_pr.has_bwrap():
        raise RuntimeError("bwrap sandbox is unavailable; cannot verify v4 candidates offline")

    test_cmd = _test_files_to_cmd(test_files, repo_spec)
    clean_env = pilot_pr.build_minimal_env()

    def _run_commit_with_ro_tests(commit_sha):
        wt_dir = tempfile.mkdtemp(prefix="v4_verify_wt_")
        ro_dir = tempfile.mkdtemp(prefix="v4_verify_ro_")
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
                # Ensure parent directory exists in wt_dir for brand-new test files
                wt_tf_parent = os.path.dirname(pilot_pr.resolve_confined_path(wt_dir, tf))
                os.makedirs(wt_tf_parent, exist_ok=True)
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
            except subprocess.TimeoutExpired:
                return -2, f"timeout after {timeout}s"
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


def enumerate_and_filter_repo_prs(
    repo_dir,
    repo_spec,
    window_start,
    window_end,
    head_ref="HEAD",
    excluded_pr_numbers=frozenset(),
    verify_bwrap=True,
    batch_size=V4_BATCH_SIZE,
):
    """Apply the pre-registered v4 mechanical filter to one repository."""
    t_start = datetime.fromisoformat(window_start.replace("Z", "+00:00"))
    t_end = datetime.fromisoformat(window_end.replace("Z", "+00:00"))

    log_out = subprocess.check_output(
        [
            "git",
            "-C",
            repo_dir,
            "log",
            "--first-parent",
            "--format=%H|%P|%cI|%s",
            head_ref,
        ],
        text=True,
    )

    git_eligible = []
    excluded = []
    seen_prs = set()

    for line in log_out.splitlines():
        if not line.strip():
            continue
        sha, parents_str, ts_str, subj = line.split("|", 3)
        pr_num, merge_kind = _extract_pr_number(subj)
        if pr_num is None:
            continue
        parents = parents_str.split()
        if not parents:
            continue
        if merge_kind == "merge" and len(parents) < 2:
            continue
        base_sha = parents[0]

        commit_dt = datetime.fromisoformat(ts_str).astimezone(timezone.utc)
        if commit_dt < t_start:
            # Keep scanning lightly only if close; break once far past window (> 60 days older)
            if (t_start - commit_dt).days > 60:
                break
            continue
        if commit_dt > t_end:
            excluded.append({"pr_number": pr_num, "reason": "after_window_end"})
            continue
        if pr_num in excluded_pr_numbers:
            excluded.append({"pr_number": pr_num, "reason": "excluded_v3_dev_set"})
            continue
        if pr_num in seen_prs:
            excluded.append({"pr_number": pr_num, "reason": "duplicate_pr_number"})
            continue
        seen_prs.add(pr_num)

        changed_files, total_lines, has_binary, has_rename = _numstat_for_range(repo_dir, base_sha, sha)
        if has_binary:
            excluded.append({"pr_number": pr_num, "reason": "binary_file_changed"})
            continue
        if has_rename:
            excluded.append({"pr_number": pr_num, "reason": "rename_in_diff"})
            continue
        if any(_is_disallowed_path(f) for f in changed_files):
            excluded.append({"pr_number": pr_num, "reason": "disallowed_build_or_ci_path"})
            continue
        impl_files = [f for f in changed_files if _is_impl_py(f, repo_spec)]
        test_files = [f for f in changed_files if _is_test_py(f, repo_spec)]
        if not impl_files:
            excluded.append({"pr_number": pr_num, "reason": "no_runtime_py_changed"})
            continue
        if not test_files:
            excluded.append({"pr_number": pr_num, "reason": "no_test_py_changed"})
            continue
        if not (V4_MIN_CHANGED_FILES <= len(changed_files) <= V4_MAX_CHANGED_FILES):
            excluded.append({
                "pr_number": pr_num,
                "reason": f"file_count_out_of_range({len(changed_files)})",
            })
            continue
        if not (V4_MIN_CHANGED_LINES <= total_lines <= V4_MAX_CHANGED_LINES):
            excluded.append({
                "pr_number": pr_num,
                "reason": f"line_count_out_of_range({total_lines})",
            })
            continue

        git_eligible.append({
            "repo_slug": repo_spec["slug"],
            "repo_name": repo_spec["name"],
            "pr_number": pr_num,
            "merge_kind": merge_kind,
            "merged_commit": sha,
            "base_commit": base_sha,
            "merged_at_utc": commit_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "files": changed_files,
            "impl_files": impl_files,
            "test_files": test_files,
            "total_changed_lines": total_lines,
            "test_cmd": _test_files_to_cmd(test_files, repo_spec),
            "subject": subj,
        })

    git_eligible.sort(key=lambda x: (x["merged_at_utc"], x["pr_number"]))

    if not verify_bwrap:
        selected = git_eligible[-batch_size:] if batch_size > 0 else []
        for drop_cand in git_eligible[:-batch_size] if batch_size > 0 else git_eligible:
            excluded.append({"pr_number": drop_cand["pr_number"], "reason": "older_than_latest_batch"})
        excluded.sort(key=lambda x: x["pr_number"])
        return selected, excluded

    selected_rev = []
    for cand in reversed(git_eligible):
        if len(selected_rev) >= batch_size:
            excluded.append({"pr_number": cand["pr_number"], "reason": "older_than_latest_batch"})
            continue
        ok, details = verify_pr_in_bwrap(
            repo_dir,
            cand["base_commit"],
            cand["merged_commit"],
            cand["test_files"],
            repo_spec=repo_spec,
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


def select_v4_batch(
    repos_dir=DEFAULT_V4_REPOS_DIR,
    verify_bwrap=True,
    batch_size=V4_BATCH_SIZE,
    primary_head=None,
    fallback_heads=None,
):
    """Run the two-phase v4 mechanical selection rule across local bare mirrors in repos_dir.

    Returns a dict with:
      - primary_selected, primary_excluded
      - fallback_repo_slug (or None), fallback_selected, fallback_audit (per shortlist repo)
      - selected (combined ordered list: primary_selected + fallback_selected)
      - shortfall (int: max(0, batch_size - len(selected)))
    """
    fallback_heads = fallback_heads or {}
    prim_dir = os.path.join(repos_dir, f"{V4_PRIMARY_SPEC['name']}.git")
    prim_head = primary_head or V4_PRIMARY_SPEC.get("pinned_head") or "HEAD"
    primary_selected, primary_excluded = enumerate_and_filter_repo_prs(
        repo_dir=prim_dir,
        repo_spec=V4_PRIMARY_SPEC,
        window_start=V4_PRIMARY_WINDOW_START,
        window_end=V4_PRIMARY_WINDOW_END,
        head_ref=prim_head,
        excluded_pr_numbers=V3_EXCLUDED_PR_NUMBERS,
        verify_bwrap=verify_bwrap,
        batch_size=batch_size,
    )

    needed = max(0, batch_size - len(primary_selected))
    fallback_repo_slug = None
    fallback_selected = []
    fallback_audit = []

    if needed > 0:
        best_partial = None
        for spec in V4_FALLBACK_SPECS:
            fb_dir = os.path.join(repos_dir, f"{spec['name']}.git")
            if not os.path.isdir(fb_dir):
                fallback_audit.append({
                    "slug": spec["slug"],
                    "status": "mirror_not_present",
                    "verified_count": 0,
                })
                continue
            fb_head = fallback_heads.get(spec["slug"]) or spec.get("pinned_head") or "HEAD"
            sel, exc = enumerate_and_filter_repo_prs(
                repo_dir=fb_dir,
                repo_spec=spec,
                window_start=V4_FALLBACK_WINDOW_START,
                window_end=V4_FALLBACK_WINDOW_END,
                head_ref=fb_head,
                excluded_pr_numbers=frozenset(),
                verify_bwrap=verify_bwrap,
                batch_size=needed,
            )
            fallback_audit.append({
                "slug": spec["slug"],
                "status": "checked",
                "verified_count": len(sel),
                "excluded_count": len(exc),
                "pr_numbers": [p["pr_number"] for p in sel],
            })
            if len(sel) >= needed:
                fallback_repo_slug = spec["slug"]
                fallback_selected = sel[-needed:]
                break
            if best_partial is None or len(sel) > len(best_partial[1]):
                best_partial = (spec["slug"], sel)

        if fallback_repo_slug is None and best_partial is not None and len(best_partial[1]) > 0:
            fallback_repo_slug, fallback_selected = best_partial

    combined = list(primary_selected) + list(fallback_selected)
    return {
        "primary_repo_slug": V4_PRIMARY_SPEC["slug"],
        "primary_selected": primary_selected,
        "primary_excluded": primary_excluded,
        "fallback_repo_slug": fallback_repo_slug,
        "fallback_selected": fallback_selected,
        "fallback_audit": fallback_audit,
        "selected": combined,
        "shortfall": max(0, batch_size - len(combined)),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Mechanical PR selector for Item 6 Pilot v4")
    parser.add_argument("--repos-dir", default=DEFAULT_V4_REPOS_DIR)
    parser.add_argument("--no-verify-bwrap", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    res = select_v4_batch(repos_dir=args.repos_dir, verify_bwrap=not args.no_verify_bwrap)
    if args.json:
        print(json.dumps(res, indent=2))
    else:
        print(
            f"Phase 1 ({res['primary_repo_slug']}): {len(res['primary_selected'])} selected "
            f"(excluded {len(res['primary_excluded'])})"
        )
        if res["fallback_audit"]:
            print("Phase 2 fallback shortlist audit:")
            for item in res["fallback_audit"]:
                print(f"  - {item['slug']}: {item['status']} verified={item['verified_count']} prs={item.get('pr_numbers', [])}")
        print(f"Total selected: {len(res['selected'])} / {V4_BATCH_SIZE} (shortfall={res['shortfall']})")
        for p in res["selected"]:
            print(
                f"  [{p['repo_slug']}] PR #{p['pr_number']:4d} merged={p['merged_at_utc']} "
                f"lines={p['total_changed_lines']:3d} files={len(p['files'])} "
                f"tests={p.get('expected_test_count', '?')} "
                f"base={p['base_commit'][:10]} merged={p['merged_commit'][:10]} "
                f"files={p['files']}"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
