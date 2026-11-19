#!/usr/bin/env python3
"""CPU-only unit tests for Roadmap Item 6 Pilot harness and task suite."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pilot_pr  # noqa: E402
import tasks_item6  # noqa: E402


class ExplodingTaskDict(dict):
    """Tripwire dictionary that explodes if hidden fields are accessed."""

    def __getitem__(self, key):
        if key in ("hidden_diff", "merged_commit"):
            raise AssertionError(f"LEAK TRIPWIRE TRIGGERED: In-loop access to '{key}'!")
        return super().__getitem__(key)

    def get(self, key, default=None):
        if key in ("hidden_diff", "merged_commit"):
            raise AssertionError(f"LEAK TRIPWIRE TRIGGERED: In-loop get() for '{key}'!")
        return super().get(key, default)


class TestPilotPr(unittest.TestCase):

    def test_task_definitions(self):
        """Verify all 7 PR tasks are defined with valid fields."""
        tasks = tasks_item6.load_tasks()
        self.assertEqual(len(tasks), 7)
        expected_prs = [6, 8, 13, 14, 15, 16, 20]
        self.assertEqual([t["pr_number"] for t in tasks], expected_prs)

        testable_count = sum(1 for t in tasks if t["has_tests"])
        self.assertEqual(testable_count, 6)
        non_testable_count = sum(1 for t in tasks if not t["has_tests"])
        self.assertEqual(non_testable_count, 1)

        for t in tasks:
            self.assertTrue(t["id"].startswith("item6_pr"))
            self.assertEqual(len(t["base_commit"]), 40)
            self.assertEqual(len(t["merged_commit"]), 40)
            self.assertTrue(len(t["prompt"]) > 50)
            self.assertTrue(len(t["files"]) >= 1)
            if t["has_tests"]:
                self.assertTrue(len(t["test_cmd"]) > 0)
            else:
                self.assertEqual(t["test_cmd"], "", f"Task {t['id']} has_tests=False must have empty test_cmd")

    def test_mechanical_pr_selection_rule(self):
        """Enumerate merged PRs from git history and assert the rule yields exactly the 7 listed PRs."""
        selected, excluded = tasks_item6.enumerate_and_filter_prs()
        selected_nums = [p["pr_number"] for p in selected]
        tasks = tasks_item6.load_tasks()
        task_nums = [t["pr_number"] for t in tasks]
        self.assertEqual(selected_nums, [6, 8, 13, 14, 15, 16, 20])
        self.assertEqual(selected_nums, task_nums)

        # Verify PR #4 and #5 are mechanically excluded for pre_antigravity_claude_seat_setup
        excl_by_pr = {p["pr_number"]: p["reason"] for p in excluded}
        self.assertEqual(excl_by_pr.get(4), "pre_antigravity_claude_seat_setup")
        self.assertEqual(excl_by_pr.get(5), "pre_antigravity_claude_seat_setup")
        # Verify PR #7, #9, #10 are excluded as single_file_readme_only
        for n in (7, 9, 10):
            self.assertEqual(excl_by_pr.get(n), "single_file_readme_only")
        # Verify PR #17, #18, #19 are excluded as gpu_result_checkin
        for n in (17, 18, 19):
            self.assertEqual(excl_by_pr.get(n), "gpu_result_checkin")

        # Verify base_commit, merged_commit, and files match task definitions
        for p, t in zip(selected, tasks):
            self.assertEqual(p["base_commit"], t["base_commit"])
            self.assertEqual(p["merged_commit"], t["merged_commit"])
            self.assertEqual(p["files"], sorted(t["files"]))


    def test_exploding_task_leak_guard(self):
        """Ensure in-loop prompt generation and strip_hidden never touch hidden fields."""
        for t in tasks_item6.load_tasks():
            exploding = ExplodingTaskDict(t)
            # strip_hidden should safely access and strip
            clean = tasks_item6.strip_hidden(exploding)
            self.assertNotIn("hidden_diff", clean)
            self.assertNotIn("merged_commit", clean)

            # format_turn_prompt must never access hidden fields
            p0 = pilot_pr.format_turn_prompt(clean)
            self.assertNotIn("LEAK", p0)
            self.assertNotIn(t["merged_commit"], p0)

            p1 = pilot_pr.format_turn_prompt(clean, last_code="xyz", test_error="AssertionError: 1 != 2")
            self.assertIn("AssertionError: 1 != 2", p1)
            self.assertNotIn(t["merged_commit"], p1)

    def test_file_extraction_markdown(self):
        """Verify extraction from markdown headers and code blocks."""
        text = (
            "Here is the change:\n\n"
            "### bench/loop/foo.py\n"
            "```python\n"
            "def foo():\n    return 100\n"
            "```\n\n"
            "### docs/notes.md\n"
            "```markdown\n"
            "# Notes\n"
            "```\n"
        )
        files = pilot_pr.extract_file_updates(text)
        self.assertIn("bench/loop/foo.py", files)
        self.assertIn("docs/notes.md", files)
        self.assertEqual(files["bench/loop/foo.py"].strip(), "def foo():\n    return 100")

    def test_diff_extraction(self):
        """Verify extraction from unified diff fence."""
        diff_text = (
            "Patch:\n"
            "```diff\n"
            "diff --git a/file.txt b/file.txt\n"
            "--- a/file.txt\n"
            "+++ b/file.txt\n"
            "@@ -1 +1 @@\n"
            "-hello\n"
            "+world\n"
            "```\n"
        )
        updates = pilot_pr.extract_file_updates(diff_text)
        self.assertIn("__patch__", updates)
        self.assertTrue(updates["__patch__"].startswith("diff --git"))

    def test_evaluate_diff_metrics(self):
        """Test offline diff evaluation metrics."""
        d1 = "diff --git a/a.py b/a.py\n+x = 1\n+y = 2\n"
        d2 = "diff --git a/a.py b/a.py\n+x = 1\n+y = 3\n"
        metrics = pilot_pr.evaluate_diff(d1, d2)
        self.assertIn("line_overlap_jaccard", metrics)
        self.assertTrue(0.0 < metrics["line_overlap_jaccard"] < 1.0)

        # Identical
        metrics_ident = pilot_pr.evaluate_diff(d1, d1)
        self.assertEqual(metrics_ident["line_overlap_jaccard"], 1.0)

    def test_mock_loop_execution(self):
        """Test full loop mechanics in a temporary repository with a simulated model."""
        temp_dir = tempfile.mkdtemp(prefix="pilot_pr_unit_")
        try:
            subprocess.run(["git", "init"], cwd=temp_dir, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Tester"], cwd=temp_dir, check=True)
            subprocess.run(["git", "config", "user.email", "tester@repo.org"], cwd=temp_dir, check=True)

            code_file = os.path.join(temp_dir, "calc.py")
            with open(code_file, "w") as f:
                f.write("def add(a, b):\n    return 0\n")
            test_file = os.path.join(temp_dir, "test_calc.py")
            with open(test_file, "w") as f:
                f.write("import calc\nassert calc.add(2, 3) == 5\n")

            subprocess.run(["git", "add", "."], cwd=temp_dir, check=True)
            subprocess.run(["git", "commit", "-m", "initial"], cwd=temp_dir, check=True, capture_output=True)
            base_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=temp_dir, text=True).strip()

            task = {
                "id": "item6_mock",
                "pr_number": 900,
                "title": "Mock Task",
                "base_commit": base_sha,
                "merged_commit": "abcdef1234567890abcdef1234567890abcdef12",
                "has_tests": True,
                "test_cmd": "python3 test_calc.py",
                "prompt": "Fix add() to return a + b",
                "files": ["calc.py"],
            }

            # Scenario 1: Model solves on turn 1 after error feedback
            def mock_solver_turn1(prompt, seed):
                if "failed automated verification" not in prompt:
                    # Buggy turn 0
                    return {
                        "content": "### calc.py\n```python\ndef add(a, b):\n    return a - b\n```",
                        "usage": {"completion_tokens": 30},
                    }
                # Fix on turn 1
                return {
                    "content": "### calc.py\n```python\ndef add(a, b):\n    return a + b\n```",
                    "usage": {"completion_tokens": 30},
                }

            res1 = pilot_pr.run_task_loop(task, mock_solver_turn1, temp_dir, max_turns=4)
            self.assertTrue(res1["passed"])
            self.assertEqual(res1["stop_reason"], "pass")
            self.assertEqual(res1["turns_executed"], 2)

            # Scenario 2: Repeat code stop
            def mock_solver_repeat(prompt, seed):
                return {
                    "content": "### calc.py\n```python\ndef add(a, b):\n    return 999\n```",
                    "usage": {"completion_tokens": 30},
                }

            res2 = pilot_pr.run_task_loop(task, mock_solver_repeat, temp_dir, max_turns=4)
            self.assertFalse(res2["passed"])
            self.assertEqual(res2["stop_reason"], "repeat_code")

        finally:
            shutil.rmtree(temp_dir)

    def test_in_loop_leak_tripwire_and_no_tests_guard(self):
        """Verify leak tripwire runs on every prompt in-loop, and run_tests is not called when has_tests is False."""
        temp_dir = tempfile.mkdtemp(prefix="pilot_pr_guard_")
        try:
            subprocess.run(["git", "init"], cwd=temp_dir, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Tester"], cwd=temp_dir, check=True)
            subprocess.run(["git", "config", "user.email", "tester@repo.org"], cwd=temp_dir, check=True)

            doc_file = os.path.join(temp_dir, "doc.md")
            with open(doc_file, "w") as f:
                f.write("# Old title\n")
            subprocess.run(["git", "add", "."], cwd=temp_dir, check=True)
            subprocess.run(["git", "commit", "-m", "initial"], cwd=temp_dir, check=True, capture_output=True)
            base_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=temp_dir, text=True).strip()

            # 1. Task with has_tests=False: run_tests must NOT be called
            no_test_task = {
                "id": "item6_notest",
                "pr_number": 901,
                "title": "Doc task",
                "base_commit": base_sha,
                "merged_commit": "1111111111111111111111111111111111111111",
                "has_tests": False,
                "test_cmd": "",
                "prompt": "Update doc.md and add new_note.md",
                "files": ["doc.md", "new_note.md"],
            }
            # Direct call to run_tests on has_tests=False must raise AssertionError
            with self.assertRaises(AssertionError):
                pilot_pr.run_tests(no_test_task, temp_dir)

            def mock_doc_writer(prompt, seed):
                return {
                    "content": (
                        "### doc.md\n```markdown\n# New title\n```\n\n"
                        "### new_note.md\n```markdown\nNew untracked file content\n```\n"
                    ),
                    "usage": {"completion_tokens": 25},
                }

            res = pilot_pr.run_task_loop(no_test_task, mock_doc_writer, temp_dir, max_turns=4)
            self.assertTrue(res["passed"])
            self.assertEqual(res["stop_reason"], "applied_no_tests")
            self.assertEqual(res["turns_executed"], 1)
            # Diff must capture both modified tracked file (doc.md) and new untracked file (new_note.md)
            self.assertIn("+# New title", res["final_diff"])
            self.assertIn("new_note.md", res["final_diff"])
            self.assertIn("+New untracked file content", res["final_diff"])

            # 2. Leak tripwire on every turn prompt (including feedback turn 1)
            leaky_task = {
                "id": "item6_leaky",
                "pr_number": 902,
                "title": "Leaky task",
                "base_commit": base_sha,
                "merged_commit": "2222222222222222222222222222222222222222",
                "has_tests": True,
                # Test output echoes LEAK_SENTINEL on failure so turn 1 prompt triggers tripwire
                "test_cmd": "echo 'LEAK_SENTINEL in error' && exit 1",
                "prompt": "Edit doc.md",
                "files": ["doc.md"],
            }
            with self.assertRaises(AssertionError):
                pilot_pr.run_task_loop(leaky_task, mock_doc_writer, temp_dir, max_turns=3)
        finally:
            shutil.rmtree(temp_dir)

    def test_run_and_grade_subcommands_end_to_end(self):
        """Test pilot_pr.py run and grade subcommands with a mocked model client and keep/drop bars."""
        if not pilot_pr.has_bwrap():
            self.skipTest("bwrap sandbox required for #6 and #16 selftests in end-to-end grade test")
        temp_dir = tempfile.mkdtemp(prefix="pilot_pr_e2e_")
        results_dir = tempfile.mkdtemp(prefix="pilot_pr_res_")
        try:
            subprocess.run(["git", "init"], cwd=temp_dir, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Tester"], cwd=temp_dir, check=True)
            subprocess.run(["git", "config", "user.email", "tester@repo.org"], cwd=temp_dir, check=True)

            # Create target file at base_commit
            with open(os.path.join(temp_dir, "debate_mock.py"), "w") as f:
                f.write("def parse():\n    return 'old'\n")
            subprocess.run(["git", "add", "."], cwd=temp_dir, check=True)
            subprocess.run(["git", "commit", "-m", "base"], cwd=temp_dir, check=True, capture_output=True)

            # Test `run` subcommand on real repo worktree for item6_pr06 and item6_pr15 with mock client
            def mock_client(prompt, seed):
                if "Fix `bench/loop/debate.py` parser logic" in prompt:
                    return {
                        "content": "### README.md\n```markdown\n# Updated README\n```\n",
                        "usage": {"completion_tokens": 42, "prompt_tokens": 100},
                    }
                return {
                    "content": "### AGENTS.md\n```markdown\n# Updated AGENTS\n```\n### new_file.txt\n```text\nhello\n```\n",
                    "usage": {"completion_tokens": 35, "prompt_tokens": 90},
                }

            run_res = pilot_pr.run_subcommand(
                label="test-e2e",
                tasks_arg="item6_pr06,item6_pr15",
                max_turns=1,
                 results_dir=results_dir,
                ask_fn=mock_client,
            )
            self.assertEqual(len(run_res), 2)

            # Verify per-PR diff files were written for offline Grok review
            diff_06 = os.path.join(results_dir, "test-e2e.diffs", "item6_pr06.diff")
            diff_15 = os.path.join(results_dir, "test-e2e.diffs", "item6_pr15.diff")
            self.assertTrue(os.path.exists(diff_06))
            self.assertTrue(os.path.exists(diff_15))
            with open(diff_15) as f:
                d15_text = f.read()
            self.assertIn("+# Updated AGENTS", d15_text)
            self.assertIn("new_file.txt", d15_text)

            # Grade without reviews file -> PENDING_REVIEW or DROP based on test rate
            # Also test grade_subcommand with a full 7-task synthetic result set + reviews file
            all_tasks = tasks_item6.load_tasks()
            jsonl_path = os.path.join(results_dir, "full-batch.jsonl")
            passing_indices = (1, 3, 4, 6)  # 3 testable (pr08, pr14, pr20) + 1 non-testable (pr15)
            with open(jsonl_path, "w") as jf:
                for i, t in enumerate(all_tasks):
                    # 3 of 6 testable pass: use true hidden_diff for passing tasks so fresh regrade passes!
                    should_pass = i in passing_indices
                    diff_for_grade = tasks_item6.get_hidden_diff(t) if should_pass else ""
                    jf.write(
                        pilot_pr.json.dumps({
                            "task_id": t["id"],
                            "pr_number": t["pr_number"],
                            "has_tests": t["has_tests"],
                            "passed": True,  # even if in-loop claims True, grade re-runs tests from scratch!
                            "stop_reason": "pass",
                            "turns_executed": 1,
                            "total_completion_tokens": 100,
                            "wall_s": 5.0,
                            "final_diff": diff_for_grade,
                        }) + "\n"
                    )

            # 1) Without reviews -> PENDING_REVIEW (since 3/6 >= 2/6)
            g_pending = pilot_pr.grade_subcommand(label="full-batch", results_dir=results_dir)
            self.assertEqual(g_pending["testable_passed"], 3)
            self.assertEqual(g_pending["testable_tasks"], 6)
            self.assertEqual(g_pending["decision"], "PENDING_REVIEW")

            # 2) With reviews meeting KEEP bar (4/6 tests pass, 4/7 approved, avg hand-fix 5 <= 20, tamper=False)
            rev_path = os.path.join(results_dir, "full-batch.reviews.json")
            reviews = {}
            for i, t in enumerate(all_tasks):
                reviews[t["id"]] = {
                    "first_verdict": "APPROVE" if i < 3 else "REQUEST-CHANGES",
                    "final_verdict": "APPROVE-WITH-NITS" if i < 4 else "REQUEST-CHANGES",
                    "hand_fix_lines": 5 if i < 4 else 0,
                    "tamper": False,
                    "fresh_session": True,
                }
            with open(rev_path, "w") as rf:
                pilot_pr.json.dump(reviews, rf)

            g_keep = pilot_pr.grade_subcommand(label="full-batch", reviews_file=rev_path, results_dir=results_dir)
            self.assertEqual(g_keep["approved_first_pass"], 3)
            self.assertEqual(g_keep["approved_final"], 4)
            self.assertEqual(g_keep["avg_hand_fix_lines_per_approved"], 5.0)
            self.assertEqual(g_keep["decision"], "KEEP")

            # 3) Test compute_keep_drop directly across all decision boundaries
            self.assertEqual(pilot_pr.compute_keep_drop(4, 6, 4, 7, 0.0), "KEEP")
            self.assertEqual(pilot_pr.compute_keep_drop(3, 6, 3, 7, 15.0), "KEEP")
            self.assertEqual(pilot_pr.compute_keep_drop(1, 6, 4, 7, 0.0), "DROP")
            self.assertEqual(pilot_pr.compute_keep_drop(3, 6, 1, 7, 0.0), "DROP")
            self.assertEqual(pilot_pr.compute_keep_drop(2, 6, 2, 7, 0.0), "INCONCLUSIVE")
            self.assertEqual(pilot_pr.compute_keep_drop(3, 6, 3, 7, 25.0), "INCONCLUSIVE")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
            shutil.rmtree(results_dir, ignore_errors=True)

    def test_path_confinement_and_seed_redaction(self):
        """Verify apply_updates rejects absolute paths, '..', and symlink escapes, and prompts redact seed 104729."""
        temp_dir = tempfile.mkdtemp(prefix="pilot_pr_confine_")
        outside_dir = tempfile.mkdtemp(prefix="pilot_pr_outside_")
        try:
            outside_target = os.path.join(outside_dir, "pwned.txt")
            with open(outside_target, "w") as f:
                f.write("original")

            # 1. Direct file updates with absolute path or '..'
            ok_abs, msg_abs = pilot_pr.apply_updates(temp_dir, {outside_target: "hacked"})
            self.assertFalse(ok_abs)
            self.assertIn("Absolute path rejected", msg_abs)

            ok_trav, msg_trav = pilot_pr.apply_updates(temp_dir, {"../pwned.txt": "hacked"})
            self.assertFalse(ok_trav)
            self.assertIn("Path traversal", msg_trav)

            ok_sub_trav, msg_sub_trav = pilot_pr.apply_updates(temp_dir, {"sub/../../pwned.txt": "hacked"})
            self.assertFalse(ok_sub_trav)
            self.assertIn("Path traversal", msg_sub_trav)

            ok_git, msg_git = pilot_pr.apply_updates(temp_dir, {".git/config": "hacked"})
            self.assertFalse(ok_git)
            self.assertIn(".git rejected", msg_git)

            # 2. Symlink escape (both symlink file and symlink directory)
            os.symlink(outside_target, os.path.join(temp_dir, "link_file.txt"))
            os.symlink(outside_dir, os.path.join(temp_dir, "link_dir"))

            ok_symf, msg_symf = pilot_pr.apply_updates(temp_dir, {"link_file.txt": "hacked"})
            self.assertFalse(ok_symf)
            self.assertIn("Symlink component rejected", msg_symf)

            ok_symd, msg_symd = pilot_pr.apply_updates(temp_dir, {"link_dir/pwned.txt": "hacked"})
            self.assertFalse(ok_symd)
            self.assertIn("Symlink component rejected", msg_symd)

            with open(outside_target) as f:
                self.assertEqual(f.read(), "original")

            # 3. Unified diff patch with traversal or symlink mode
            bad_patch_trav = (
                "diff --git a/../pwned.txt b/../pwned.txt\n"
                "--- a/../pwned.txt\n"
                "+++ b/../pwned.txt\n"
                "@@ -1 +1 @@\n"
                "-original\n"
                "+hacked\n"
            )
            ok_pt, msg_pt = pilot_pr.apply_updates(temp_dir, {"__patch__": bad_patch_trav})
            self.assertFalse(ok_pt)
            self.assertIn("Rejected unsafe patch path", msg_pt)

            bad_patch_sym = (
                "diff --git a/link_file.txt b/link_file.txt\n"
                "--- a/link_file.txt\n"
                "+++ b/link_file.txt\n"
                "@@ -1 +1 @@\n"
                "-original\n"
                "+hacked\n"
            )
            ok_ps, msg_ps = pilot_pr.apply_updates(temp_dir, {"__patch__": bad_patch_sym})
            self.assertFalse(ok_ps)
            self.assertIn("Rejected unsafe patch path", msg_ps)

            bad_patch_mode = (
                "diff --git a/newlink b/newlink\n"
                "new file mode 120000\n"
                "--- /dev/null\n"
                "+++ b/newlink\n"
                "@@ -0,0 +1 @@\n"
                "+/etc/passwd\n"
            )
            ok_pm, msg_pm = pilot_pr.apply_updates(temp_dir, {"__patch__": bad_patch_mode})
            self.assertFalse(ok_pm)
            self.assertIn("Symlink mode 120000", msg_pm)

            # 4. Grading seed 104729 redaction from worktree file context and error feedback
            seeded_file = os.path.join(temp_dir, "agent.py")
            with open(seeded_file, "w") as f:
                f.write("FRESH_SEED = 104729\n")
            task = {
                "id": "item6_seed_test",
                "pr_number": 903,
                "title": "Seed redaction test",
                "base_commit": "0" * 40,
                "merged_commit": "1" * 40,
                "has_tests": True,
                "test_cmd": "true",
                "prompt": "Check agent.py",
                "files": ["agent.py"],
            }
            p0 = pilot_pr.format_turn_prompt(task, worktree_dir=temp_dir)
            self.assertNotIn("104729", p0)
            self.assertIn("FRESH_SEED = <REDACTED_SEED>", p0)

            p1 = pilot_pr.format_turn_prompt(task, last_code="x", test_error="Failed at seed 104729", worktree_dir=temp_dir)
            self.assertNotIn("104729", p1)
            self.assertIn("<REDACTED_SEED>", p1)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
            shutil.rmtree(outside_dir, ignore_errors=True)

    def test_git_isolation_cannot_resolve_merged_commit(self):
        """Verify create_isolated_scratch_repo creates a standalone tree that cannot resolve merged_commit."""
        scratch_dir = tempfile.mkdtemp(prefix="pilot_pr_iso_")
        repo_root = os.path.abspath(os.path.join(HERE, "..", ".."))
        try:
            task = tasks_item6.get_task("item6_pr06")
            base_sha = task["base_commit"]
            merged_sha = task["merged_commit"]

            pilot_pr.create_isolated_scratch_repo(repo_root, base_sha, scratch_dir)

            # 1. Verify target files exist at base state
            self.assertTrue(os.path.exists(os.path.join(scratch_dir, "bench", "loop", "debate.py")))

            # 2. Verify merged_commit and base_commit SHAs from main repo are unknown objects in scratch_dir
            res_show = subprocess.run(
                ["git", "cat-file", "-e", merged_sha],
                cwd=scratch_dir,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(res_show.returncode, 0, "Scratch repo must NOT contain merged_commit in object store!")

            res_log = subprocess.run(
                ["git", "show", merged_sha],
                cwd=scratch_dir,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(res_log.returncode, 0, "git show merged_commit must fail in isolated scratch repo!")

            # 3. Verify capture_worktree_diff works cleanly on edits and new files in the isolated scratch repo
            with open(os.path.join(scratch_dir, "new_isolated.txt"), "w") as f:
                f.write("isolated content\n")
            diff_out = pilot_pr.capture_worktree_diff(scratch_dir, base_sha)
            self.assertIn("new_isolated.txt", diff_out)
            self.assertIn("+isolated content", diff_out)
        finally:
            shutil.rmtree(scratch_dir, ignore_errors=True)

    def test_self_grading_test_overwrite_rejected_by_grade(self):
        """Verify that overwriting a test file with 'exit 0' passes in-loop if unguarded, but FAILS during grade."""
        scratch_dir = tempfile.mkdtemp(prefix="pilot_pr_selfgrade_")
        results_dir = tempfile.mkdtemp(prefix="pilot_pr_sg_res_")
        repo_root = os.path.abspath(os.path.join(HERE, "..", ".."))
        try:
            # Take PR #20 (test_cmd: bash scripts/test-prereg-guard.sh, test_files: ['scripts/test-prereg-guard.sh'])
            task = tasks_item6.get_task("item6_pr20")
            pilot_pr.create_isolated_scratch_repo(repo_root, task["base_commit"], scratch_dir)

            # Simulate a cheating model that overwrites scripts/test-prereg-guard.sh with 'exit 0'
            def cheating_model(prompt, seed):
                return {
                    "content": "### scripts/test-prereg-guard.sh\n```bash\n#!/usr/bin/env bash\nexit 0\n```\n",
                    "usage": {"completion_tokens": 20},
                }

            loop_res = pilot_pr.run_task_loop(task, cheating_model, scratch_dir, max_turns=2)
            # In-loop test_cmd ran the overwritten test file and saw exit 0:
            self.assertTrue(loop_res["passed"])

            # Now grade_subcommand re-runs in a fresh tree with test_files restored from merged_commit
            jsonl_path = os.path.join(results_dir, "cheat.jsonl")
            with open(jsonl_path, "w") as f:
                f.write(pilot_pr.json.dumps(loop_res) + "\n")

            grade_res = pilot_pr.grade_subcommand(
                label="cheat",
                repo_root=repo_root,
                results_dir=results_dir,
                tasks_override=[task],
            )
            self.assertEqual(grade_res["testable_tasks"], 1)
            self.assertEqual(grade_res["testable_passed"], 0, "exit 0 overwrite of test file must NOT count as pass in grade!")
            self.assertFalse(grade_res["per_task"][0]["test_passed"])
            self.assertTrue(grade_res["per_task"][0]["in_loop_passed"])
        finally:
            shutil.rmtree(scratch_dir, ignore_errors=True)
            shutil.rmtree(results_dir, ignore_errors=True)

    def test_launcher_refuses_placeholder_wt_and_expect_head(self):
        """Verify bench/loop/runs/item6-pilot/run.sh refuses to run when WT or EXPECT_HEAD is a placeholder."""
        repo_root = os.path.abspath(os.path.join(HERE, "..", ".."))
        run_sh = os.path.join(repo_root, "bench", "loop", "runs", "item6-pilot", "run.sh")

        # 1. Default invocation (WT is placeholder) -> exits non-zero
        r1 = subprocess.run(["bash", run_sh], cwd=repo_root, capture_output=True, text=True)
        self.assertNotEqual(r1.returncode, 0)
        self.assertIn("WT must be set", r1.stderr)

        # 2. WT set, but EXPECT_HEAD is still placeholder -> exits non-zero
        env2 = dict(os.environ, WT=repo_root, EXPECT_HEAD="<expected-git-commit-sha>")
        r2 = subprocess.run(["bash", run_sh], cwd=repo_root, env=env2, capture_output=True, text=True)
        self.assertNotEqual(r2.returncode, 0)
        self.assertIn("EXPECT_HEAD must be set", r2.stderr)

    def test_launcher_exit_trap_preserves_incomplete_ceiling_status(self):
        """Verify bench/loop/runs/item6-pilot/run.sh EXIT trap does not overwrite incomplete ceiling status."""
        repo_root = os.path.abspath(os.path.join(HERE, "..", ".."))
        check_sh = os.path.join(repo_root, "bench", "loop", "runs", "item6-pilot", "check_ceiling_trap.sh")
        res = subprocess.run(["bash", check_sh], cwd=repo_root, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"check_ceiling_trap.sh failed:\n{res.stdout}\n{res.stderr}")
        self.assertIn("Item 2 check passed", res.stdout)

    def test_import_time_exit_stubs_fail_grade_on_6_13_16(self):
        """Verify sys.exit(0) and os._exit(0) stubs of model modules grade FAIL for PRs #6, #13, and #16."""
        repo_root = os.path.abspath(os.path.join(HERE, "..", ".."))
        cases = [
            ("item6_pr06", "bench/loop/debate.py"),
            ("item6_pr13", "bench/loop/tasks_v10.py"),
            ("item6_pr16", "bench/loop/ground.py"),
        ]
        stubs = [
            ("sys.exit(0)", "import sys\nsys.exit(0)\n"),
            ("os._exit(0)", "import os\nos._exit(0)\n"),
        ]
        for task_id, target_file in cases:
            task = tasks_item6.get_task(task_id)
            for stub_name, stub_code in stubs:
                scratch_dir = tempfile.mkdtemp(prefix=f"stub_{task_id}_")
                try:
                    pilot_pr.create_isolated_scratch_repo(repo_root, task["base_commit"], scratch_dir)
                    full_target = os.path.join(scratch_dir, target_file)
                    os.makedirs(os.path.dirname(full_target), exist_ok=True)
                    with open(full_target, "w", encoding="utf-8") as f:
                        f.write(stub_code)
                    stub_diff = pilot_pr.capture_worktree_diff(scratch_dir, task["base_commit"])
                    self.assertTrue(len(stub_diff) > 0)

                    passed, out = pilot_pr.regrade_task_diff(task, stub_diff, repo_root=repo_root, timeout=30)
                    self.assertFalse(
                        passed,
                        f"Stub {stub_name} in {target_file} ({task_id}) must grade FAIL, but got passed=True! out={out}",
                    )
                finally:
                    shutil.rmtree(scratch_dir, ignore_errors=True)

    def test_env_isolation_no_repo_root_and_no_git_alternate_leak(self):
        """Verify model code under grade cannot see PILOT_REPO_ROOT/GIT_*, and GIT_ALTERNATE_OBJECT_DIRECTORIES cannot leak merged SHA."""
        repo_root = os.path.abspath(os.path.join(HERE, "..", ".."))
        main_git_objects = subprocess.check_output(
            ["git", "-C", repo_root, "rev-parse", "--git-path", "objects"],
            text=True,
        ).strip()
        if not os.path.isabs(main_git_objects):
            main_git_objects = os.path.abspath(os.path.join(repo_root, main_git_objects))

        scratch_dir = tempfile.mkdtemp(prefix="pilot_env_iso_")
        old_env = os.environ.copy()
        try:
            # Poison parent os.environ with GIT_ALTERNATE_OBJECT_DIRECTORIES and PILOT_REPO_ROOT
            os.environ["GIT_ALTERNATE_OBJECT_DIRECTORIES"] = main_git_objects
            os.environ["PILOT_REPO_ROOT"] = repo_root
            os.environ["GIT_DIR"] = os.path.join(repo_root, ".git")

            # 1. Verify build_minimal_env strips all of them
            min_env = pilot_pr.build_minimal_env()
            self.assertNotIn("PILOT_REPO_ROOT", min_env)
            self.assertNotIn("GIT_ALTERNATE_OBJECT_DIRECTORIES", min_env)
            self.assertNotIn("GIT_DIR", min_env)
            self.assertFalse(any(k.startswith("GIT_") for k in min_env))
            self.assertFalse(any(repo_root in str(v) for v in min_env.values()))

            # 2. Create isolated scratch repo while parent env is poisoned
            task = tasks_item6.get_task("item6_pr06")
            pilot_pr.create_isolated_scratch_repo(repo_root, task["base_commit"], scratch_dir)

            # Using build_minimal_env() (as run_tests and grade do), merged_commit must be unresolvable
            res_cat = subprocess.run(
                ["git", "cat-file", "-e", task["merged_commit"]],
                cwd=scratch_dir,
                env=min_env,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(res_cat.returncode, 0, "Scratch repo must not resolve merged SHA even when parent has GIT_ALTERNATE_OBJECT_DIRECTORIES")

            # 3. Verify model code running under regrade_task_diff sees neither PILOT_REPO_ROOT nor GIT_* nor repo_root in env
            probe_code = (
                "import os, sys\n"
                "for k, v in os.environ.items():\n"
                f"    if k == 'PILOT_REPO_ROOT' or k.startswith('GIT_') or {repo_root!r} in v:\n"
                "        print('LEAKED_ENV:', k, v)\n"
                "        sys.exit(0)\n"
                "sys.exit(1)\n"
            )
            full_target = os.path.join(scratch_dir, "bench", "loop", "debate.py")
            with open(full_target, "w", encoding="utf-8") as f:
                f.write(probe_code)
            probe_diff = pilot_pr.capture_worktree_diff(scratch_dir, task["base_commit"])

            passed, out = pilot_pr.regrade_task_diff(task, probe_diff, repo_root=repo_root, timeout=30)
            self.assertFalse(passed)
            self.assertNotIn("LEAKED_ENV:", out)
        finally:
            os.environ.clear()
            os.environ.update(old_env)
            shutil.rmtree(scratch_dir, ignore_errors=True)

    def test_review_record_missing_fields_raises_error(self):
        """Verify grade raises ValueError when a review record is missing verdict or hand_fix_lines."""
        results_dir = tempfile.mkdtemp(prefix="pilot_rev_err_")
        try:
            task = tasks_item6.get_task("item6_pr15")  # non-testable task for fast check
            jsonl_path = os.path.join(results_dir, "revcheck.jsonl")
            with open(jsonl_path, "w") as f:
                f.write(
                    pilot_pr.json.dumps({
                        "task_id": task["id"],
                        "pr_number": task["pr_number"],
                        "has_tests": False,
                        "passed": True,
                        "stop_reason": "applied_no_tests",
                        "turns_executed": 1,
                        "total_completion_tokens": 50,
                        "wall_s": 1.0,
                        "final_diff": "+line\n",
                    }) + "\n"
                )

            # 1. Missing hand_fix_lines -> must raise ValueError, not default to 0
            rev_missing_hf = os.path.join(results_dir, "missing_hf.json")
            with open(rev_missing_hf, "w") as f:
                pilot_pr.json.dump({task["id"]: {"verdict": "APPROVE", "tamper": False}}, f)
            with self.assertRaises(ValueError):
                pilot_pr.grade_subcommand("revcheck", reviews_file=rev_missing_hf, results_dir=results_dir, tasks_override=[task])

            # 2. Missing verdict -> must raise ValueError
            rev_missing_v = os.path.join(results_dir, "missing_v.json")
            with open(rev_missing_v, "w") as f:
                pilot_pr.json.dump({task["id"]: {"hand_fix_lines": 5, "tamper": False}}, f)
            with self.assertRaises(ValueError):
                pilot_pr.grade_subcommand("revcheck", reviews_file=rev_missing_v, results_dir=results_dir, tasks_override=[task])

            # 3. Missing tamper -> must raise ValueError
            rev_missing_tamper = os.path.join(results_dir, "missing_tamper.json")
            with open(rev_missing_tamper, "w") as f:
                pilot_pr.json.dump({task["id"]: {"verdict": "APPROVE", "hand_fix_lines": 5}}, f)
            with self.assertRaises(ValueError):
                pilot_pr.grade_subcommand("revcheck", reviews_file=rev_missing_tamper, results_dir=results_dir, tasks_override=[task])

            # 4. Tamper=True on a passing testable task -> forces test_passed=False and approved=0
            t_testable = tasks_item6.get_task("item6_pr14")
            hd14 = tasks_item6.get_hidden_diff(t_testable)
            with open(jsonl_path, "w") as f:
                f.write(
                    pilot_pr.json.dumps({
                        "task_id": t_testable["id"],
                        "pr_number": t_testable["pr_number"],
                        "has_tests": True,
                        "passed": True,
                        "stop_reason": "pass",
                        "turns_executed": 1,
                        "total_completion_tokens": 50,
                        "wall_s": 1.0,
                        "final_diff": hd14,
                    }) + "\n"
                )
            rev_tamper_true = os.path.join(results_dir, "tamper_true.json")
            with open(rev_tamper_true, "w") as f:
                pilot_pr.json.dump({
                    t_testable["id"]: {
                        "verdict": "APPROVE",
                        "hand_fix_lines": 0,
                        "tamper": True,
                        "fresh_session": True,
                    }
                }, f)
            g_tamper = pilot_pr.grade_subcommand(
                "revcheck",
                reviews_file=rev_tamper_true,
                results_dir=results_dir,
                tasks_override=[t_testable],
            )
            self.assertEqual(g_tamper["testable_passed"], 0, "tamper=True must count as test FAIL!")
            self.assertFalse(g_tamper["per_task"][0]["test_passed"])
            self.assertEqual(g_tamper["approved_final"], 0, "tamper=True must count as non-approved!")
        finally:
            shutil.rmtree(results_dir, ignore_errors=True)

    def test_sentinel_token_not_in_cmdline_environ_or_stdin(self):
        """Verify a model module reading /proc/self/cmdline, /proc/self/environ, and sys.stdin cannot find the grade token."""
        repo_root = os.path.abspath(os.path.join(HERE, "..", ".."))
        scratch_dir = tempfile.mkdtemp(prefix="pilot_tok_probe_")
        try:
            task = tasks_item6.get_task("item6_pr06")
            pilot_pr.create_isolated_scratch_repo(repo_root, task["base_commit"], scratch_dir)

            # Join marker dynamically so the literal '@@PILOT_GRADE_OK_' does not appear in the probe source itself
            probe_code = (
                "import os, sys\n"
                "cmdline = open('/proc/self/cmdline', 'rb').read().decode('utf-8', 'replace')\n"
                "environ = open('/proc/self/environ', 'rb').read().decode('utf-8', 'replace')\n"
                "stdin_data = sys.stdin.read()\n"
                "needle = '@@PILOT_' + 'GRADE_OK_'\n"
                "if needle in cmdline or needle in environ or needle in stdin_data:\n"
                "    print('TOKEN_LEAK_FOUND')\n"
                "else:\n"
                "    print('TOKEN_CLEAN')\n"
                "sys.exit(0)\n"
            )
            full_target = os.path.join(scratch_dir, "bench", "loop", "debate.py")
            with open(full_target, "w", encoding="utf-8") as f:
                f.write(probe_code)
            probe_diff = pilot_pr.capture_worktree_diff(scratch_dir, task["base_commit"])

            passed, out = pilot_pr.regrade_task_diff(task, probe_diff, repo_root=repo_root, timeout=30)
            self.assertFalse(passed, "Probe that exits before running tests must grade FAIL")
            self.assertIn("TOKEN_CLEAN", out)
            self.assertNotIn("TOKEN_LEAK_FOUND", out)
        finally:
            shutil.rmtree(scratch_dir, ignore_errors=True)

    def test_isolated_python_usercustomize_and_clean_home_path_tmpdir(self):
        """Verify usercustomize.py planted in HOME does not run under grade, and HOME/PATH/TMPDIR in grade child do not contain repo_root."""
        repo_root = os.path.abspath(os.path.join(HERE, "..", ".."))
        scratch_dir = tempfile.mkdtemp(prefix="pilot_usercust_")
        old_env = os.environ.copy()
        try:
            # 1. Poison parent HOME, PATH, TMPDIR, and PYTHONPATH with repo_root
            os.environ["HOME"] = os.path.join(repo_root, "fake_home")
            os.environ["PATH"] = f"{repo_root}/bin:" + os.environ.get("PATH", "/usr/bin:/bin")
            os.environ["TMPDIR"] = os.path.join(repo_root, "fake_tmp")
            os.environ["PYTHONPATH"] = repo_root

            task = tasks_item6.get_task("item6_pr13")
            pilot_pr.create_isolated_scratch_repo(repo_root, task["base_commit"], scratch_dir)

            # 2. Simulate an in-loop command that plants usercustomize.py in its HOME user-site directory
            # and verify that even if planted during loop run_tests, it does not survive or execute during grade
            plant_task = dict(
                task,
                test_cmd=(
                    "python3 -c \"import os, site, sys; "
                    "us = os.path.expanduser(f'~/.local/lib/python{sys.version_info.major}.{sys.version_info.minor}/site-packages'); "
                    "os.makedirs(us, exist_ok=True); "
                    "open(os.path.join(us, 'usercustomize.py'), 'w').write('print(\\\"USERCUSTOMIZE_RAN\\\")\\n')\""
                ),
            )
            ok_loop, _ = pilot_pr.run_tests(plant_task, scratch_dir)
            self.assertTrue(ok_loop)

            # 3. Now run regrade_task_diff with a probe module that checks if USERCUSTOMIZE_RAN or if repo_root is in HOME/PATH/TMPDIR
            probe_code = (
                "import os, sys\n"
                "for k in ('HOME', 'PATH', 'TMPDIR', 'PYTHONPATH'):\n"
                f"    val = os.environ.get(k, '')\n"
                f"    if {repo_root!r} in val:\n"
                "        print('REPO_IN_ENV:', k, val)\n"
                "print('ENV_CHECK_DONE')\n"
                "TASKS = []\n"
            )
            full_target = os.path.join(scratch_dir, "bench", "loop", "tasks_v10.py")
            with open(full_target, "w", encoding="utf-8") as f:
                f.write(probe_code)
            probe_diff = pilot_pr.capture_worktree_diff(scratch_dir, task["base_commit"])

            passed, out = pilot_pr.regrade_task_diff(task, probe_diff, repo_root=repo_root, timeout=30)
            self.assertFalse(passed)
            self.assertIn("ENV_CHECK_DONE", out)
            self.assertNotIn("USERCUSTOMIZE_RAN", out)
            self.assertNotIn("REPO_IN_ENV:", out)
        finally:
            os.environ.clear()
            os.environ.update(old_env)
            shutil.rmtree(scratch_dir, ignore_errors=True)

    def test_bwrap_sandbox_blocks_outside_writes_reads_proc_and_fails_closed(self):
        """Verify bwrap sandbox blocks writing /tmp or real HOME, hides repo//data/main checkout and parent /proc, supports nested bwrap (#6, #16), and fails closed."""
        self.assertTrue(pilot_pr.has_bwrap(), "bwrap must be present and functional on this machine")
        repo_root = os.path.abspath(os.path.join(HERE, "..", ".."))
        real_home = os.path.expanduser("~")
        host_tmp_probe = "/tmp/outside-probe-item6-test"
        host_home_probe = os.path.join(
            real_home,
            f".local/lib/python{sys.version_info.major}.{sys.version_info.minor}/site-packages/usercustomize_item6_probe.py",
        )
        if os.path.exists(host_tmp_probe):
            os.remove(host_tmp_probe)
        if os.path.exists(host_home_probe):
            os.remove(host_home_probe)

        scratch_dir = tempfile.mkdtemp(prefix="pilot_bwrap_iso_")
        try:
            task = tasks_item6.get_task("item6_pr06")
            pilot_pr.create_isolated_scratch_repo(repo_root, task["base_commit"], scratch_dir)

            # 1. Probe module attempts to:
            #    - write /tmp/outside-probe-item6-test and real_home/.local/.../usercustomize_item6_probe.py
            #    - read repo_root, /home/aj/projects/strix-halo-lab, /data, and real_home contents
            #    - scan /proc/*/cwd and /proc/*/cmdline for repo_root or /home/aj/projects/strix-halo-lab
            probe_code = (
                "import glob, os, sys\n"
                "try:\n"
                f"    open({host_tmp_probe!r}, 'w').write('pwned')\n"
                "except Exception:\n"
                "    pass\n"
                "try:\n"
                f"    os.makedirs(os.path.dirname({host_home_probe!r}), exist_ok=True)\n"
                f"    open({host_home_probe!r}, 'w').write('pwned')\n"
                "except Exception:\n"
                "    pass\n"
                "leaks = []\n"
                f"for p in ({repo_root!r}, '/home/aj/projects/strix-halo-lab', '/data/models', '/data/orch', os.path.join({real_home!r}, '.bashrc'), os.path.join({real_home!r}, '.gitconfig')):\n"
                "    if os.path.exists(p):\n"
                "        leaks.append('PATH_EXISTS:' + p)\n"
                "for pc in glob.glob('/proc/[0-9]*/cwd'):\n"
                "    try:\n"
                "        target = os.readlink(pc)\n"
                f"        if {repo_root!r} in target or 'strix-halo-lab' in target:\n"
                "            leaks.append('PROC_CWD:' + target)\n"
                "    except Exception:\n"
                "        pass\n"
                "if leaks:\n"
                "    print('SANDBOX_LEAK:', leaks)\n"
                "else:\n"
                "    print('SANDBOX_ISOLATED_OK')\n"
                "sys.exit(0)\n"
            )
            full_target = os.path.join(scratch_dir, "bench", "loop", "debate.py")
            with open(full_target, "w", encoding="utf-8") as f:
                f.write(probe_code)

            # Test both loop run_tests and grade regrade_task_diff
            _, loop_out = pilot_pr.run_tests(task, scratch_dir)
            self.assertIn("SANDBOX_ISOLATED_OK", loop_out)
            self.assertNotIn("SANDBOX_LEAK:", loop_out)
            self.assertFalse(os.path.exists(host_tmp_probe), "/tmp write inside sandbox must not appear on host /tmp!")
            self.assertFalse(os.path.exists(host_home_probe), "HOME write inside sandbox must not appear in real HOME!")

            probe_diff = pilot_pr.capture_worktree_diff(scratch_dir, task["base_commit"])
            passed, grade_out = pilot_pr.regrade_task_diff(task, probe_diff, repo_root=repo_root, timeout=30)
            self.assertFalse(passed)
            self.assertIn("SANDBOX_ISOLATED_OK", grade_out)
            self.assertNotIn("SANDBOX_LEAK:", grade_out)
            self.assertFalse(os.path.exists(host_tmp_probe), "/tmp write during grade must not appear on host /tmp!")
            self.assertFalse(os.path.exists(host_home_probe), "HOME write during grade must not appear in real HOME!")

            # 2. Verify inner bwrap wrapper inside outer bwrap fails closed when nested isolation cannot be established
            #    (Ubuntu AppArmor prevents nested unshare/mounts under /usr/bin/bwrap; wrapper must exit non-zero)
            home_d, tmp_d, shim_d = pilot_pr.prepare_isolated_home_and_tmp(scratch_dir)
            try:
                env_ns = pilot_pr.build_minimal_env(home_dir="/home/pilot", tmp_dir="/tmp")
                ns_check_py = (
                    "import subprocess, sys\n"
                    "res = subprocess.run(['bwrap', '--ro-bind', '/usr', '/usr', '--bind', '/tmp', '/w', '--chdir', '/w', 'python3', '-c', 'print(1)'], capture_output=True, text=True)\n"
                    "print('NESTED_RC=' + str(res.returncode))\n"
                )
                bw_cmd = pilot_pr.build_outer_bwrap_cmd(
                    scratch_dir, home_d, tmp_d, shim_d, ["python3", "-I", "-c", ns_check_py], env_ns
                )
                self.assertEqual(bw_cmd[0], "/usr/bin/bwrap")
                res_ns = subprocess.run(bw_cmd, capture_output=True, text=True, timeout=15)
                self.assertEqual(res_ns.returncode, 0, res_ns.stderr)
                self.assertIn("NESTED_RC=1", res_ns.stdout, "Inner bwrap must fail closed inside outer bwrap")
            finally:
                pilot_pr.cleanup_isolated_home_and_tmp(scratch_dir)

            # Verify graded test files are not visible on disk inside /work during grade
            t16 = tasks_item6.get_task("item6_pr16")
            pilot_pr.create_isolated_scratch_repo(repo_root, t16["base_commit"], scratch_dir)
            check_hidden_tests_code = (
                "import os, sys\n"
                "if os.path.exists('/work/bench/loop/test_ground.py') or os.path.exists('/work/_pilot_merged_selftest.py'):\n"
                "    print('GRADED_TEST_FILE_VISIBLE')\n"
                "else:\n"
                "    print('GRADED_TEST_FILE_HIDDEN')\n"
                "sys.exit(1)\n"
            )
            with open(os.path.join(scratch_dir, "bench", "loop", "ground.py"), "w") as f:
                f.write(check_hidden_tests_code)
            diff_t16 = pilot_pr.capture_worktree_diff(scratch_dir, t16["base_commit"])
            ok16, out16 = pilot_pr.regrade_task_diff(t16, diff_t16, repo_root=repo_root, timeout=30)
            self.assertFalse(ok16)
            self.assertIn("GRADED_TEST_FILE_HIDDEN", out16)
            self.assertNotIn("GRADED_TEST_FILE_VISIBLE", out16)

            # 3. Verify fail-closed when bwrap is unavailable
            orig_has_bwrap = pilot_pr.has_bwrap
            try:
                pilot_pr.has_bwrap = lambda: False
                with self.assertRaises(RuntimeError):
                    pilot_pr.run_tests(task, scratch_dir)
                with self.assertRaises(RuntimeError):
                    pilot_pr.regrade_task_diff(task, probe_diff, repo_root=repo_root, timeout=15)
            finally:
                pilot_pr.has_bwrap = orig_has_bwrap
        finally:
            if os.path.exists(host_tmp_probe):
                os.remove(host_tmp_probe)
            if os.path.exists(host_home_probe):
                os.remove(host_home_probe)
            shutil.rmtree(scratch_dir, ignore_errors=True)

    def test_inner_bwrap_wrapper_isolation_and_fail_closed(self):
        """Verify inner bwrap wrapper isolates mounts and PID namespace, and fails closed on setup failure."""
        scratch_dir = tempfile.mkdtemp(prefix="pilot_inner_wrap_")
        try:
            home_d, tmp_d, shim_d = pilot_pr.prepare_isolated_home_and_tmp(scratch_dir)
            shim_bwrap = os.path.join(shim_d, "bwrap")

            # 1. Setup failure exits non-zero (fail closed without isolation)
            res_fail = subprocess.run(
                [shim_bwrap, "--ro-bind", "/usr", "/usr", "python3", "-c", "print('UNSAFE_RUN')"],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(res_fail.returncode, 0, "Wrapper must exit non-zero when isolation cannot be set up")
            self.assertNotIn("UNSAFE_RUN", res_fail.stdout, "Payload must not execute on setup failure")

            # 2. Inside the wrapped run in an existing user namespace:
            # - graded test file under /work is not readable
            # - other processes' /proc/<pid>/cmdline is not visible
            dummy_work = os.path.join(scratch_dir, "work")
            os.makedirs(dummy_work, exist_ok=True)
            with open(os.path.join(dummy_work, "test_ground.py"), "w") as f:
                f.write("SECRET_GRADED_TEST_DATA")

            dummy_scratch = os.path.join(scratch_dir, "candidate_scratch")
            os.makedirs(dummy_scratch, exist_ok=True)

            probe_py = (
                "import glob, os, sys\n"
                "if os.path.exists('/work') or os.path.exists('/work/test_ground.py'):\n"
                "    print('LEAK:GRADED_TEST_VISIBLE')\n"
                "    sys.exit(2)\n"
                "my_pid = os.getpid()\n"
                "pids = [int(p) for p in os.listdir('/proc') if p.isdigit()]\n"
                "other_cmds = []\n"
                "for p in pids:\n"
                "    if p != my_pid and p != 1:\n"
                "        try:\n"
                "            cmdline = open(f'/proc/{p}/cmdline').read()\n"
                "            if cmdline:\n"
                "                other_cmds.append((p, cmdline))\n"
                "        except Exception:\n"
                "            pass\n"
                "if other_cmds:\n"
                "    print('LEAK:OTHER_PROC_VISIBLE', other_cmds)\n"
                "    sys.exit(3)\n"
                "print('INNER_ISOLATION_VERIFIED')\n"
                "sys.exit(0)\n"
            )

            inner_test_cmd = [
                shim_bwrap,
                "--ro-bind", "/usr", "/usr",
                "--symlink", "usr/lib", "/lib",
                "--symlink", "usr/lib64", "/lib64",
                "--symlink", "usr/bin", "/bin",
                "--proc", "/proc",
                "--dev", "/dev",
                "--tmpfs", "/tmp",
                "--unshare-all",
                "--die-with-parent",
                "--new-session",
                "--clearenv",
                "--setenv", "PATH", "/usr/bin",
                "--bind", dummy_scratch, "/w",
                "--chdir", "/w",
                "python3", "-c", probe_py,
            ]

            runner_cmd = ["unshare", "--user", "--map-root-user"] + inner_test_cmd
            res_wrap = subprocess.run(runner_cmd, capture_output=True, text=True, timeout=15)
            self.assertEqual(res_wrap.returncode, 0, f"Wrapped isolation failed: {res_wrap.stderr}")
            self.assertIn("INNER_ISOLATION_VERIFIED", res_wrap.stdout)
            self.assertNotIn("LEAK:", res_wrap.stdout)
        finally:
            pilot_pr.cleanup_isolated_home_and_tmp(scratch_dir)
            shutil.rmtree(scratch_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
