#!/usr/bin/env python3
"""CPU-only unit tests for Roadmap Item 6 Pilot harness and task suite."""
import json
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
        if key in ("hidden_diff", "merged_commit", "hidden_sentinel"):
            raise AssertionError(f"LEAK TRIPWIRE TRIGGERED: In-loop access to '{key}'!")
        return super().__getitem__(key)

    def get(self, key, default=None):
        if key in ("hidden_diff", "merged_commit", "hidden_sentinel"):
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

            # Scenario 1: Model solves on turn 1 after error feedback using structured search_replace tools
            def mock_solver_turn1(messages, seed):
                joined = pilot_pr.messages_to_text(messages)
                if "Tool results:" not in joined:
                    # Buggy turn 0
                    calls = [
                        {"tool": "search_replace", "args": {"path": "calc.py", "old": "return 0", "new": "return a - b"}},
                        {"tool": "finish", "args": {"summary": "initial edit"}},
                    ]
                    return {
                        "content": "```json\n" + json.dumps(calls) + "\n```",
                        "usage": {"completion_tokens": 30},
                    }
                # Fix on turn 1
                calls = [
                    {"tool": "search_replace", "args": {"path": "calc.py", "old": "return a - b", "new": "return a + b"}},
                    {"tool": "finish", "args": {"summary": "fixed add"}},
                ]
                return {
                    "content": "```json\n" + json.dumps(calls) + "\n```",
                    "usage": {"completion_tokens": 30},
                }

            res1 = pilot_pr.run_task_loop(task, mock_solver_turn1, temp_dir, max_turns=4)
            self.assertTrue(res1["passed"])
            self.assertEqual(res1["stop_reason"], "pass")
            self.assertEqual(res1["turns_executed"], 2)
            self.assertIn("+    return a + b", res1["final_diff"])

            # Scenario 2: Repeat code stop
            def mock_solver_repeat(messages, seed):
                calls = [
                    {"tool": "search_replace", "args": {"path": "calc.py", "old": "nonexistent_line", "new": "return 999"}},
                ]
                return {
                    "content": "```json\n" + json.dumps(calls) + "\n```",
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

            def mock_doc_writer(messages, seed):
                calls = [
                    {"tool": "search_replace", "args": {"path": "doc.md", "old": "# Old title", "new": "# New title"}},
                    {"tool": "create_file", "args": {"path": "new_note.md", "content": "New untracked file content\n"}},
                    {"tool": "finish", "args": {"summary": "updated docs"}},
                ]
                return {
                    "content": "```json\n" + json.dumps(calls) + "\n```",
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

            # 2. Leak tripwire on every turn prompt (including feedback turn 1) using per-run random sentinel
            run_sentinel = pilot_pr.generate_run_sentinel()
            s_half = len(run_sentinel) // 2
            leaky_task = {
                "id": "item6_leaky",
                "pr_number": 902,
                "title": "Leaky task",
                "base_commit": base_sha,
                "merged_commit": "2222222222222222222222222222222222222222",
                "hidden_sentinel": run_sentinel,
                "has_tests": True,
                # Assemble the sentinel at test runtime so Turn 0 prompt is clean and Turn 1 feedback trips the wire
                "test_cmd": f"printf '%s%s in error\\n' '{run_sentinel[:s_half]}' '{run_sentinel[s_half:]}' && exit 1",
                "prompt": "Edit doc.md",
                "files": ["doc.md"],
            }
            # Direct check_prompt_leak raises PromptLeakError (subclass of AssertionError)
            with self.assertRaises(AssertionError) as cm:
                pilot_pr.check_prompt_leak(f"leaked {run_sentinel}", leaky_task, run_sentinel=run_sentinel)
            self.assertIsInstance(cm.exception, pilot_pr.PromptLeakError)
            self.assertEqual(cm.exception.branch, "run_sentinel")

            ask_calls = []
            def mock_leaky_trigger(messages, seed):
                ask_calls.append(len(messages))
                calls = [
                    {"tool": "search_replace", "args": {"path": "doc.md", "old": "# New title", "new": "# Trigger title"}},
                    {"tool": "finish", "args": {"summary": "trigger test"}},
                ]
                return {
                    "content": "```json\n" + json.dumps(calls) + "\n```",
                    "usage": {"completion_tokens": 20},
                }

            res_leak = pilot_pr.run_task_loop(
                leaky_task,
                mock_leaky_trigger,
                temp_dir,
                max_turns=3,
                run_sentinel=run_sentinel,
            )
            # Turn 1 must NEVER reach ask_fn (fail closed), and partial diff from turn 0 is preserved
            self.assertEqual(len(ask_calls), 1, "Leaked prompt on turn 1 must never be sent to ask_fn")
            self.assertFalse(res_leak["passed"])
            self.assertEqual(res_leak["stop_reason"], "prompt_leak")
            self.assertEqual(res_leak["leak_branch"], "run_sentinel")
            self.assertIn("+# Trigger title", res_leak["final_diff"])
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
            def mock_client(messages, seed):
                joined = pilot_pr.messages_to_text(messages)
                if "Fix `bench/loop/debate.py` parser logic" in joined:
                    calls = [
                        {"tool": "create_file", "args": {"path": "mock_pr06.txt", "content": "pr06\n"}},
                        {"tool": "finish", "args": {"summary": "pr06 mock"}},
                    ]
                    return {
                        "content": "```json\n" + json.dumps(calls) + "\n```",
                        "usage": {"completion_tokens": 42, "prompt_tokens": 100},
                    }
                calls = [
                    {
                        "tool": "search_replace",
                        "args": {
                            "path": "AGENTS.md",
                            "old": "# Working rules for agents in this repo",
                            "new": "# Updated AGENTS",
                        },
                    },
                    {"tool": "create_file", "args": {"path": "new_file.txt", "content": "hello\n"}},
                    {"tool": "finish", "args": {"summary": "pr15 mock"}},
                ]
                return {
                    "content": "```json\n" + json.dumps(calls) + "\n```",
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
            passing_indices = (0, 1, 3, 4, 6)  # 4 testable (pr06, pr08, pr14, pr20) + 1 non-testable (pr15)
            with open(jsonl_path, "w") as jf:
                for i, t in enumerate(all_tasks):
                    # 4 of 6 testable pass: use true hidden_diff for passing tasks so fresh regrade passes!
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

            # 1) Without reviews -> PENDING_REVIEW (since 4/6 >= 3/6)
            g_pending = pilot_pr.grade_subcommand(label="full-batch", results_dir=results_dir)
            self.assertEqual(g_pending["testable_passed"], 4)
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
            def cheating_model(messages, seed):
                calls = [
                    {
                        "tool": "create_file",
                        "args": {
                            "path": "scripts/test-prereg-guard.sh",
                            "content": "#!/usr/bin/env bash\nexit 0\n",
                            "overwrite": True,
                            "justification": "Replacing test script with minimal passing stub",
                            "executable": True,
                        },
                    },
                    {"tool": "finish", "args": {"summary": "cheating"}},
                ]
                return {
                    "content": "```json\n" + json.dumps(calls) + "\n```",
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

    def test_forged_and_broken_selftest_grades_fail_on_6_and_16(self):
        """Verify print-only forged debate.py (PR #6) and broken ground.py (PR #16) grade ok=False."""
        repo_root = os.path.abspath(os.path.join(HERE, "..", ".."))

        # Case 1: print-only forged debate.py for PR #6
        task6 = tasks_item6.get_task("item6_pr06")
        scratch_dir6 = tempfile.mkdtemp(prefix="forged_pr6_")
        try:
            pilot_pr.create_isolated_scratch_repo(repo_root, task6["base_commit"], scratch_dir6)
            forged_debate = (
                "import sys\n"
                "def main():\n"
                "    for i in range(59):\n"
                "        print(f'ok forged {i}')\n"
                "    print('selftest OK (protocol 137acf32c95d)')\n"
                "    sys.exit(0)\n"
                "if __name__ == '__main__':\n"
                "    main()\n"
            )
            target_path6 = os.path.join(scratch_dir6, "bench/loop/debate.py")
            os.makedirs(os.path.dirname(target_path6), exist_ok=True)
            with open(target_path6, "w", encoding="utf-8") as f:
                f.write(forged_debate)
            diff6 = pilot_pr.capture_worktree_diff(scratch_dir6, task6["base_commit"])
            passed6, out6 = pilot_pr.regrade_task_diff(task6, diff6, repo_root=repo_root, timeout=60)
            self.assertFalse(
                passed6,
                f"Print-only forged debate.py must grade ok=False, but got ok={passed6}! output:\n{out6}",
            )
        finally:
            shutil.rmtree(scratch_dir6, ignore_errors=True)

        # Case 2: broken ground.py for PR #16 (corrupted SEED_BASE causing selftest check failure)
        task16 = tasks_item6.get_task("item6_pr16")
        scratch_dir16 = tempfile.mkdtemp(prefix="broken_pr16_")
        try:
            pilot_pr.create_isolated_scratch_repo(repo_root, task16["base_commit"], scratch_dir16)
            hdiff16 = tasks_item6.get_hidden_diff(task16, repo_root)
            pilot_pr.apply_updates(scratch_dir16, {"__patch__": hdiff16.rstrip("\n")})
            ground_path = os.path.join(scratch_dir16, "bench/loop/ground.py")
            with open(ground_path, "r", encoding="utf-8") as f:
                src = f.read()
            broken_src = src.replace("SEED_BASE = 5000", "SEED_BASE = 0")
            with open(ground_path, "w", encoding="utf-8") as f:
                f.write(broken_src)
            diff16 = pilot_pr.capture_worktree_diff(scratch_dir16, task16["base_commit"])
            passed16, out16 = pilot_pr.regrade_task_diff(task16, diff16, repo_root=repo_root, timeout=60)
            self.assertFalse(
                passed16,
                f"Broken ground.py must grade ok=False, but got ok={passed16}! output:\n{out16}",
            )
        finally:
            shutil.rmtree(scratch_dir16, ignore_errors=True)

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

            # 2. Verify inner bwrap wrapper inside outer bwrap succeeds when outer isolation and layout are present
            home_d, tmp_d, shim_d = pilot_pr.prepare_isolated_home_and_tmp(scratch_dir)
            try:
                env_ns = pilot_pr.build_minimal_env(home_dir="/home/pilot", tmp_dir="/tmp")
                ns_check_py = (
                    "import subprocess, sys\n"
                    "res = subprocess.run(['bwrap', '--ro-bind', '/usr', '/usr', '--bind', '/tmp', '/w', '--chdir', '/w', 'python3', '-c', 'print(1)'], capture_output=True, text=True)\n"
                    "print('NESTED_RC=' + str(res.returncode))\n"
                )
                bw_cmd = pilot_pr.build_outer_bwrap_cmd(
                    scratch_dir, home_d, tmp_d, shim_d, ["python3", "-I", "-B", "-"], env_ns
                )
                self.assertEqual(bw_cmd[0], "/usr/bin/bwrap")
                res_ns = subprocess.run(bw_cmd, input=ns_check_py, capture_output=True, text=True, timeout=15)
                self.assertEqual(res_ns.returncode, 0, res_ns.stderr)
                self.assertIn("NESTED_RC=0", res_ns.stdout, "Inner bwrap must succeed inside outer bwrap when layout is present")
            finally:
                pilot_pr.cleanup_isolated_home_and_tmp(scratch_dir)

            # Verify restored merged-commit test files are mounted read-only and cannot be tampered with or deleted
            t16 = tasks_item6.get_task("item6_pr16")
            pilot_pr.create_isolated_scratch_repo(repo_root, t16["base_commit"], scratch_dir)
            check_hidden_tests_code = (
                "import os, sys\n"
                "p = '/work/bench/loop/test_ground.py'\n"
                "if not os.path.exists(p):\n"
                "    print('FAIL: test_ground.py missing')\n"
                "    sys.exit(1)\n"
                "try:\n"
                "    with open(p, 'w') as f: f.write('tamper')\n"
                "    print('TAMPER_WRITE_SUCCEEDED')\n"
                "    sys.exit(1)\n"
                "except OSError:\n"
                "    pass\n"
                "try:\n"
                "    os.unlink(p)\n"
                "    print('TAMPER_UNLINK_SUCCEEDED')\n"
                "    sys.exit(1)\n"
                "except OSError:\n"
                "    pass\n"
                "print('GRADED_TEST_FILE_IMMUTABLE')\n"
                "sys.exit(1)\n"
            )
            with open(os.path.join(scratch_dir, "bench", "loop", "ground.py"), "w") as f:
                f.write(check_hidden_tests_code)
            diff_t16 = pilot_pr.capture_worktree_diff(scratch_dir, t16["base_commit"])
            ok16, out16 = pilot_pr.regrade_task_diff(t16, diff_t16, repo_root=repo_root, timeout=30)
            self.assertFalse(ok16)
            self.assertIn("GRADED_TEST_FILE_IMMUTABLE", out16)
            self.assertNotIn("TAMPER_", out16)

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
        """Verify inner bwrap wrapper verifies layout, fails closed without isolation, and hides graded files/proc on real grade path."""
        scratch_dir = tempfile.mkdtemp(prefix="pilot_inner_wrap_")
        outside_dir = tempfile.mkdtemp(prefix="pilot_outside_graded_")
        ro_dir = tempfile.mkdtemp(prefix="pilot_ro_graded_")
        try:
            home_d, tmp_d, shim_d = pilot_pr.prepare_isolated_home_and_tmp(scratch_dir)
            shim_bwrap = os.path.join(shim_d, "bwrap")

            # 1. Setup failure on host exits non-zero (fail closed without outer sandbox isolation)
            res_fail = subprocess.run(
                [shim_bwrap, "--ro-bind", "/usr", "/usr", "python3", "-c", "print('UNSAFE_RUN')"],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(res_fail.returncode, 0, "Wrapper must exit non-zero when isolation cannot be set up")
            self.assertNotIn("UNSAFE_RUN", res_fail.stdout, "Payload must not execute on setup failure")

            # 2. Outside graded test file exists on host, but cannot be read from inside outer sandbox
            outside_file = os.path.join(outside_dir, "test_ground.py")
            with open(outside_file, "w") as f:
                f.write("SECRET_OUTSIDE_GROUND_PROBE")
            self.assertTrue(os.path.exists(outside_file), "Graded test file must exist on host outside sandbox")

            # 3. Read-only mounted graded test file inside /work cannot be overwritten or deleted
            os.makedirs(os.path.join(scratch_dir, "bench", "loop"), exist_ok=True)
            ro_file = os.path.join(ro_dir, "test_ground.py")
            with open(ro_file, "w") as f:
                f.write("AUTHORITATIVE_GROUND_CONTENT")
            self.assertTrue(os.path.exists(ro_file), "Authoritative test file must exist outside sandbox")

            env_ns = pilot_pr.build_minimal_env(home_dir="/home/pilot", tmp_dir="/tmp")
            inner_tester = (
                f"import os, subprocess, sys\n"
                f"outside_f = {outside_file!r}\n"
                f"cand_d = '/tmp/cand_test'\n"
                f"os.makedirs(cand_d, exist_ok=True)\n"
                f"cand_probe_py = (\n"
                f"    'import os, sys\\n'\n"
                f"    f'outside_f = {{outside_f!r}}\\n'\n"
                f"    'if os.path.exists(outside_f):\\n'\n"
                f"    '    print(\"LEAK: outside file visible in sandbox\")\\n'\n"
                f"    '    sys.exit(1)\\n'\n"
                f"    'try:\\n'\n"
                f"    '    with open(outside_f): pass\\n'\n"
                f"    '    print(\"LEAK: opened outside file\")\\n'\n"
                f"    '    sys.exit(1)\\n'\n"
                f"    'except FileNotFoundError:\\n'\n"
                f"    '    pass\\n'\n"
                f"    'ro_path = \"/work/bench/loop/test_ground.py\"\\n'\n"
                f"    'if not os.path.exists(ro_path):\\n'\n"
                f"    '    print(\"FAIL: ro_path does not exist\")\\n'\n"
                f"    '    sys.exit(2)\\n'\n"
                f"    'with open(ro_path) as f:\\n'\n"
                f"    '    if f.read() != \"AUTHORITATIVE_GROUND_CONTENT\":\\n'\n"
                f"    '        print(\"FAIL: wrong content in ro_path\")\\n'\n"
                f"    '        sys.exit(2)\\n'\n"
                f"    'try:\\n'\n"
                f"    '    with open(ro_path, \"w\") as f: f.write(\"tamper\")\\n'\n"
                f"    '    print(\"LEAK: wrote to ro_path\")\\n'\n"
                f"    '    sys.exit(3)\\n'\n"
                f"    'except OSError:\\n'\n"
                f"    '    pass\\n'\n"
                f"    'try:\\n'\n"
                f"    '    os.unlink(ro_path)\\n'\n"
                f"    '    print(\"LEAK: unlinked ro_path\")\\n'\n"
                f"    '    sys.exit(4)\\n'\n"
                f"    'except OSError:\\n'\n"
                f"    '    pass\\n'\n"
                f"    'print(\"INNER_ISOLATION_VERIFIED\")\\n'\n"
                f"    'sys.exit(0)\\n'\n"
                f")\n"
                f"cmd = [\n"
                f"    '/pilot_shim/bwrap',\n"
                f"    '--ro-bind', '/usr', '/usr',\n"
                f"    '--symlink', 'usr/lib', '/lib',\n"
                f"    '--symlink', 'usr/lib64', '/lib64',\n"
                f"    '--symlink', 'usr/bin', '/bin',\n"
                f"    '--proc', '/proc',\n"
                f"    '--dev', '/dev',\n"
                f"    '--tmpfs', '/tmp',\n"
                f"    '--unshare-all',\n"
                f"    '--die-with-parent',\n"
                f"    '--new-session',\n"
                f"    '--clearenv',\n"
                f"    '--setenv', 'PATH', '/usr/bin',\n"
                f"    '--bind', cand_d, '/w',\n"
                f"    '--chdir', '/w',\n"
                f"    'python3', '-c', cand_probe_py,\n"
                f"]\n"
                f"p = subprocess.run(cmd, capture_output=True, text=True)\n"
                f"sys.stdout.write(p.stdout)\n"
                f"sys.stderr.write(p.stderr)\n"
                f"sys.exit(p.returncode)\n"
            )
            ro_binds = [(ro_file, "/work/bench/loop/test_ground.py")]
            bw_cmd = pilot_pr.build_outer_bwrap_cmd(
                scratch_dir, home_d, tmp_d, shim_d, ["python3", "-c", inner_tester], env_ns, ro_binds=ro_binds
            )
            res_wrap = subprocess.run(bw_cmd, capture_output=True, text=True, timeout=15)
            self.assertEqual(res_wrap.returncode, 0, f"Wrapped isolation failed: {res_wrap.stderr}")
            self.assertIn("INNER_ISOLATION_VERIFIED", res_wrap.stdout)
            self.assertNotIn("LEAK:", res_wrap.stdout)
        finally:
            pilot_pr.cleanup_isolated_home_and_tmp(scratch_dir)
            shutil.rmtree(scratch_dir, ignore_errors=True)
            shutil.rmtree(outside_dir, ignore_errors=True)
            shutil.rmtree(ro_dir, ignore_errors=True)

    def test_sandbox_proc_isolation_no_grader_cmdline_or_memory(self):
        """Verify from inside sandbox no host grader cmdline or grader memory is reachable (holds with or without ptrace restrictions)."""
        scratch_dir = tempfile.mkdtemp(prefix="pilot_proc_iso_")
        host_pid = os.getpid()
        self.assertTrue(os.path.exists(f"/proc/{host_pid}/cmdline"), "Host grader cmdline must exist on host")
        self.assertTrue(os.path.exists(f"/proc/{host_pid}/mem"), "Host grader memory must exist on host")
        try:
            home_d, tmp_d, shim_d = pilot_pr.prepare_isolated_home_and_tmp(scratch_dir)
            env_ns = pilot_pr.build_minimal_env(home_dir="/home/pilot", tmp_dir="/tmp")
            proc_probe_py = (
                f"import glob, os, sys\n"
                f"host_pid = {host_pid}\n"
                f"my_pid = str(os.getpid())\n"
                f"if os.path.exists(f'/proc/{{host_pid}}'):\n"
                f"    print('LEAK: host_pid exists in sandbox /proc!')\n"
                f"    sys.exit(1)\n"
                f"for p in glob.glob('/proc/[0-9]*/cmdline'):\n"
                f"    if f'/proc/{{my_pid}}/' in p:\n"
                f"        continue\n"
                f"    try:\n"
                f"        data = open(p, 'rb').read()\n"
                f"        if b'/usr/bin/bwrap' in data or b'test_pilot_pr' in data:\n"
                f"            print(f'LEAK: host or bwrap cmdline in {{p}}: {{data!r}}')\n"
                f"            sys.exit(2)\n"
                f"    except Exception:\n"
                f"        pass\n"
                f"try:\n"
                f"    open(f'/proc/{{host_pid}}/mem', 'rb')\n"
                f"    print('LEAK: opened host memory!')\n"
                f"    sys.exit(3)\n"
                f"except (FileNotFoundError, ProcessLookupError, PermissionError):\n"
                f"    pass\n"
                f"print('GRADER_PROC_ISOLATION_VERIFIED')\n"
                f"sys.exit(0)\n"
            )
            bw_cmd = pilot_pr.build_outer_bwrap_cmd(
                scratch_dir, home_d, tmp_d, shim_d, ["python3", "-c", proc_probe_py], env_ns
            )
            res = subprocess.run(bw_cmd, capture_output=True, text=True, timeout=15)
            self.assertEqual(res.returncode, 0, f"Proc isolation probe failed: {res.stderr}")
            self.assertIn("GRADER_PROC_ISOLATION_VERIFIED", res.stdout)
            self.assertNotIn("LEAK:", res.stdout)
        finally:
            pilot_pr.cleanup_isolated_home_and_tmp(scratch_dir)
            shutil.rmtree(scratch_dir, ignore_errors=True)

    def test_http_context_overflow_produces_failed_record_and_continues(self):
        """Verify HTTP 400 context overflow records failed context_overflow record with empty diff and continues."""
        import io
        import urllib.error

        task = {
            "id": "item6_pr15",
            "pr_number": 15,
            "has_tests": False,
            "test_cmd": "",
            "base_commit": "af2b1a5c4ca765fd411f9e9f9d48c2d099420722",
            "merged_commit": "mock",
            "prompt": "Test prompt",
            "files": ["docs/item6-pilot.md"],
        }
        err_msg = b'{"error": "request (38364 tokens) exceeds the available context size (32768 tokens), try increasing it"}'
        def mock_overflow_ask(prompt, seed):
            raise urllib.error.HTTPError(
                "http://127.0.0.1:8081/v1/chat/completions",
                400,
                "Bad Request",
                hdrs={},
                fp=io.BytesIO(err_msg),
            )

        scratch_dir = tempfile.mkdtemp(prefix="pilot_overflow_")
        try:
            res = pilot_pr.run_task_loop(task, mock_overflow_ask, scratch_dir)
            self.assertFalse(res["passed"])
            self.assertEqual(res["stop_reason"], "context_overflow")
            self.assertEqual(res["stop"], "context_overflow")
            self.assertEqual(res["final_diff"], "")
            self.assertEqual(res["turns_executed"], 1)
            self.assertIn("exceeds the available context size", res["history"][0]["err"])

            # Verify generic request error
            def mock_500_ask(prompt, seed):
                raise urllib.error.HTTPError(
                    "http://127.0.0.1:8081/v1/chat/completions",
                    500,
                    "Internal Server Error",
                    hdrs={},
                    fp=io.BytesIO(b"server crash"),
                )
            res500 = pilot_pr.run_task_loop(task, mock_500_ask, scratch_dir)
            self.assertFalse(res500["passed"])
            self.assertEqual(res500["stop_reason"], "request_error")
            self.assertEqual(res500["final_diff"], "")
        finally:
            shutil.rmtree(scratch_dir, ignore_errors=True)

    def test_resume_runs_only_missing_tasks_and_records_byte_identical(self):
        """Verify resume runs only missing tasks and leaves existing records byte-identical."""
        temp_dir = tempfile.mkdtemp(prefix="pilot_resume_test_")
        try:
            jsonl_path = os.path.join(temp_dir, "test-label.jsonl")
            line1 = '{"task_id": "item6_pr06", "pr_number": 6, "has_tests": true, "passed": false, "stop_reason": "repeat_error", "turns_executed": 2, "history": [], "total_completion_tokens": 100, "final_diff": "diff1", "wall_s": 10.5, "model": "qwen", "server": {}}\n'
            line2 = '{"task_id": "item6_pr08", "pr_number": 8, "has_tests": true, "passed": false, "stop_reason": "max_turns", "turns_executed": 4, "history": [], "total_completion_tokens": 200, "final_diff": "diff2", "wall_s": 20.0, "model": "qwen", "server": {}}\n'
            with open(jsonl_path, "w", encoding="utf-8") as f:
                f.write(line1)
                f.write(line2)

            def mock_ask(messages, seed):
                calls = [
                    {"tool": "create_file", "args": {"path": "test.txt", "content": "hello\n"}},
                    {"tool": "finish", "args": {"summary": "created test.txt"}},
                ]
                return {
                    "content": "```json\n" + json.dumps(calls) + "\n```",
                    "reasoning_chars": 0,
                    "finish": "stop",
                    "usage": {"completion_tokens": 10, "prompt_tokens": 20},
                    "gen_s": 0.5,
                }

            # Run with resume=True targeting pr06 (already exists) and pr15 (missing)
            res = pilot_pr.run_subcommand(
                label="test-label",
                tasks_arg="item6_pr06,item6_pr15",
                results_dir=temp_dir,
                resume=True,
                ask_fn=mock_ask,
            )

            # Only item6_pr15 was executed
            self.assertEqual(len(res), 1)
            self.assertEqual(res[0]["task_id"], "item6_pr15")

            # Check that existing lines 1 and 2 remain strictly byte-identical
            with open(jsonl_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            self.assertEqual(lines[0], line1)
            self.assertEqual(lines[1], line2)
            self.assertEqual(len(lines), 3)
            self.assertEqual(json.loads(lines[2])["task_id"], "item6_pr15")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_grade_empty_diff_automatic_non_approval_hand_fix_excluded(self):
        """Verify grade treats empty-diff tasks as non-approved with hand_fix excluded without requiring review."""
        temp_dir = tempfile.mkdtemp(prefix="pilot_grade_empty_")
        try:
            jsonl_path = os.path.join(temp_dir, "grade-empty.jsonl")
            rev_path = os.path.join(temp_dir, "grade-empty.reviews.json")
            rows = [
                {
                    "task_id": "item6_pr13",
                    "pr_number": 13,
                    "has_tests": True,
                    "passed": False,
                    "stop_reason": "repeat_error",
                    "turns_executed": 2,
                    "final_diff": "",
                    "total_completion_tokens": 100,
                    "wall_s": 15.0,
                },
                {
                    "task_id": "item6_pr15",
                    "pr_number": 15,
                    "has_tests": False,
                    "passed": False,
                    "stop_reason": "context_overflow",
                    "turns_executed": 1,
                    "final_diff": "",
                    "total_completion_tokens": 0,
                    "wall_s": 0.5,
                },
            ]
            with open(jsonl_path, "w", encoding="utf-8") as f:
                for r in rows:
                    f.write(json.dumps(r) + "\n")

            # No reviews provided for empty-diff tasks; reviews file is empty dict
            with open(rev_path, "w", encoding="utf-8") as f:
                json.dump({}, f)

            summary = pilot_pr.grade_subcommand(
                label="grade-empty",
                reviews_file=rev_path,
                results_dir=temp_dir,
            )

            self.assertEqual(summary["tasks_evaluated"], 2)
            self.assertEqual(summary["testable_passed"], 0)
            self.assertTrue(summary["reviews_complete"])
            self.assertEqual(summary["approved_final"], 0)
            self.assertIsNone(summary["avg_hand_fix_lines_per_approved"])
            self.assertEqual(summary["decision"], "DROP")

            for pt in summary["per_task"]:
                self.assertFalse(pt["test_passed"])
                self.assertEqual(pt["final_verdict"], "NON-APPROVAL")
                self.assertIsNone(pt["hand_fix_lines"])
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_structured_edit_tools_match_nomatch_ambiguous_and_retry(self):
        """Verify read_file, list_files, grep, search_replace (match, no-match, ambiguous), and retry within turn budget."""
        temp_dir = tempfile.mkdtemp(prefix="pilot_tools_test_")
        try:
            subprocess.run(["git", "init"], cwd=temp_dir, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Tester"], cwd=temp_dir, check=True)
            subprocess.run(["git", "config", "user.email", "tester@repo.org"], cwd=temp_dir, check=True)

            os.makedirs(os.path.join(temp_dir, "src"), exist_ok=True)
            with open(os.path.join(temp_dir, "src", "mod.py"), "w", encoding="utf-8") as f:
                f.write(
                    "SEED = 104729\n"
                    "def f():\n"
                    "    x = 1\n"
                    "    return x\n"
                    "def g():\n"
                    "    x = 1\n"
                    "    return x + 1\n"
                )
            with open(os.path.join(temp_dir, "test_mod.py"), "w", encoding="utf-8") as f:
                f.write("from src import mod\nassert mod.f() == 10\nassert mod.g() == 2\n")
            subprocess.run(["git", "add", "."], cwd=temp_dir, check=True)
            subprocess.run(["git", "commit", "-m", "base"], cwd=temp_dir, check=True, capture_output=True)
            base_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=temp_dir, text=True).strip()

            # list_files + glob
            ok_ls, out_ls = pilot_pr.tool_list_files(temp_dir, path=".", glob_pattern="*.py")
            self.assertTrue(ok_ls)
            self.assertIn("src/mod.py", out_ls)
            self.assertNotIn(".git", out_ls)

            # grep redacts grading seed 104729
            ok_gr, out_gr = pilot_pr.tool_grep(temp_dir, pattern=r"SEED", path="src")
            self.assertTrue(ok_gr)
            self.assertIn("<REDACTED_SEED>", out_gr)
            self.assertNotIn("104729", out_gr)

            # read_file window and redaction
            ok_rf, out_rf = pilot_pr.tool_read_file(temp_dir, "src/mod.py", start=1, end=4)
            self.assertTrue(ok_rf)
            self.assertIn("lines 1-4 of 7", out_rf)
            self.assertIn("<REDACTED_SEED>", out_rf)
            self.assertNotIn("104729", out_rf)

            # search_replace: no-match rejected
            ok_nm, msg_nm = pilot_pr.tool_search_replace(temp_dir, "src/mod.py", "does_not_exist", "y = 2")
            self.assertFalse(ok_nm)
            self.assertIn("0 matches", msg_nm)

            # search_replace: ambiguous (2 matches) rejected
            ok_amb, msg_amb = pilot_pr.tool_search_replace(temp_dir, "src/mod.py", "    x = 1", "    x = 10")
            self.assertFalse(ok_amb)
            self.assertIn("ambiguous (2 matches", msg_amb)

            # search_replace: no-op rejected
            ok_noop, msg_noop = pilot_pr.tool_search_replace(temp_dir, "src/mod.py", "def f():", "def f():")
            self.assertFalse(ok_noop)
            self.assertIn("no-op", msg_noop)

            # In-loop retry after failed no-match and ambiguous search_replace, then targeted unique match passes
            task = {
                "id": "item6_tool_retry",
                "pr_number": 910,
                "title": "Tool retry task",
                "base_commit": base_sha,
                "merged_commit": "3" * 40,
                "has_tests": True,
                "test_cmd": "python3 test_mod.py",
                "prompt": "Change f() in src/mod.py to return 10.",
                "files": ["src/mod.py"],
            }
            turn_idx = [0]

            def retry_model(messages, seed):
                t = turn_idx[0]
                turn_idx[0] += 1
                joined = pilot_pr.messages_to_text(messages)
                if t == 0:
                    # First attempt fails due to ambiguous match
                    calls = [{"tool": "search_replace", "args": {"path": "src/mod.py", "old": "    x = 1", "new": "    x = 10"}}]
                elif t == 1:
                    self.assertIn("ambiguous (2 matches", joined)
                    # Second attempt fails due to 0 matches
                    calls = [{"tool": "search_replace", "args": {"path": "src/mod.py", "old": "def f():\n    x = 999", "new": "def f():\n    x = 10"}}]
                else:
                    self.assertIn("0 matches", joined)
                    # Third attempt provides unique context and finishes
                    calls = [
                        {
                            "tool": "search_replace",
                            "args": {
                                "path": "src/mod.py",
                                "old": "def f():\n    x = 1\n    return x",
                                "new": "def f():\n    x = 10\n    return x",
                            },
                        },
                        {"tool": "finish", "args": {"summary": "updated f()"}},
                    ]
                return {"content": "```json\n" + json.dumps(calls) + "\n```", "usage": {"completion_tokens": 40}}

            res = pilot_pr.run_task_loop(task, retry_model, temp_dir, max_turns=6)
            self.assertTrue(res["passed"])
            self.assertEqual(res["stop_reason"], "pass")
            self.assertEqual(res["turns_executed"], 3)
            self.assertIn("-    x = 1", res["final_diff"])
            self.assertIn("+    x = 10", res["final_diff"])
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_structured_edit_tools_path_escape_rejected(self):
        """Verify all edit and read tools reject absolute paths, '..', .git, and symlink escapes."""
        temp_dir = tempfile.mkdtemp(prefix="pilot_tool_escape_")
        outside_dir = tempfile.mkdtemp(prefix="pilot_tool_out_")
        try:
            outside_file = os.path.join(outside_dir, "secret.txt")
            with open(outside_file, "w", encoding="utf-8") as f:
                f.write("original secret\n")
            os.makedirs(os.path.join(temp_dir, ".git"), exist_ok=True)
            with open(os.path.join(temp_dir, ".git", "config"), "w", encoding="utf-8") as f:
                f.write("[core]\n")
            os.symlink(outside_file, os.path.join(temp_dir, "sym_file.txt"))
            os.symlink(outside_dir, os.path.join(temp_dir, "sym_dir"))

            bad_paths = [
                outside_file,
                "../secret.txt",
                "sub/../../secret.txt",
                ".git/config",
                "sym_file.txt",
                "sym_dir/secret.txt",
            ]
            for bp in bad_paths:
                ok_r, _ = pilot_pr.tool_read_file(temp_dir, bp)
                self.assertFalse(ok_r, f"read_file must reject {bp}")
                ok_s, _ = pilot_pr.tool_search_replace(temp_dir, bp, "original", "pwned")
                self.assertFalse(ok_s, f"search_replace must reject {bp}")
                ok_c, _, _ = pilot_pr.tool_create_file(temp_dir, bp, "pwned\n", overwrite=True, justification="escape attempt test")
                self.assertFalse(ok_c, f"create_file must reject {bp}")
                ok_g, _ = pilot_pr.tool_grep(temp_dir, "secret", path=bp)
                self.assertFalse(ok_g, f"grep must reject {bp}")
                ok_l, _ = pilot_pr.tool_list_files(temp_dir, path=bp)
                self.assertFalse(ok_l, f"list_files must reject {bp}")

            with open(outside_file, "r", encoding="utf-8") as f:
                self.assertEqual(f.read(), "original secret\n")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
            shutil.rmtree(outside_dir, ignore_errors=True)

    def test_whole_file_rewrite_cap_and_create_file_overwrite_guard(self):
        """Verify create_file rejects unapproved overwrites, caps justified overwrites, and search_replace caps large whole-file rewrites."""
        temp_dir = tempfile.mkdtemp(prefix="pilot_rewrite_cap_")
        try:
            sess = pilot_pr.ToolSession(temp_dir, max_overwrites=1)

            # 1. Creating a brand-new file (with executable=True) succeeds
            ok_new, msg_new, is_ed = sess.execute({
                "tool": "create_file",
                "args": {"path": "scripts/new.sh", "content": "#!/usr/bin/env bash\necho hi\n", "executable": True},
            })
            self.assertTrue(ok_new, msg_new)
            self.assertTrue(is_ed)
            mode = os.stat(os.path.join(temp_dir, "scripts", "new.sh")).st_mode & 0o777
            self.assertEqual(mode, 0o755)

            # 2. create_file over an existing file without overwrite=True is rejected
            with open(os.path.join(temp_dir, "a.py"), "w", encoding="utf-8") as f:
                f.write("a = 1\n")
            with open(os.path.join(temp_dir, "b.py"), "w", encoding="utf-8") as f:
                f.write("b = 1\n")

            ok_no_ow, msg_no_ow, _ = sess.execute({
                "tool": "create_file",
                "args": {"path": "a.py", "content": "a = 2\n"},
            })
            self.assertFalse(ok_no_ow)
            self.assertIn("already exists", msg_no_ow)

            # 3. create_file with overwrite=True but missing/short justification is rejected
            ok_short_j, msg_short_j, _ = sess.execute({
                "tool": "create_file",
                "args": {"path": "a.py", "content": "a = 2\n", "overwrite": True, "justification": "too short"},
            })
            self.assertFalse(ok_short_j)
            self.assertIn("justification", msg_short_j)

            # 4. create_file with overwrite=True and clear justification succeeds up to cap (1)
            ok_ow1, msg_ow1, _ = sess.execute({
                "tool": "create_file",
                "args": {
                    "path": "a.py",
                    "content": "a = 2\n",
                    "overwrite": True,
                    "justification": "Full replacement required because file is being split into modules.",
                },
            })
            self.assertTrue(ok_ow1, msg_ow1)

            # 5. Second existing-file overwrite in same task is rejected by cap
            ok_ow2, msg_ow2, _ = sess.execute({
                "tool": "create_file",
                "args": {
                    "path": "b.py",
                    "content": "b = 2\n",
                    "overwrite": True,
                    "justification": "Attempting second full overwrite beyond the per-task cap.",
                },
            })
            self.assertFalse(ok_ow2)
            self.assertIn("cap reached", msg_ow2)

            # 6. search_replace whole-file rewrite cap on large existing file (>= 80 lines)
            large_lines = [f"line_{i} = {i}" for i in range(100)]
            large_old = "\n".join(large_lines) + "\n"
            large_new = "\n".join(f"rewritten_{i} = {i}" for i in range(100)) + "\n"
            with open(os.path.join(temp_dir, "big.py"), "w", encoding="utf-8") as f:
                f.write(large_old)

            ok_big, msg_big, _ = sess.execute({
                "tool": "search_replace",
                "args": {"path": "big.py", "old": large_old, "new": large_new},
            })
            self.assertFalse(ok_big)
            self.assertIn("whole-file rewrite cap", msg_big)

            # Targeted edit on the same 100-line file succeeds
            ok_small, msg_small, _ = sess.execute({
                "tool": "search_replace",
                "args": {"path": "big.py", "old": "line_42 = 42", "new": "line_42 = 420"},
            })
            self.assertTrue(ok_small, msg_small)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_context_preflight_overflow_recorded_and_run_continues(self):
        """Verify prompt-size preflight records context_overflow without calling model and multi-task run continues."""
        results_dir = tempfile.mkdtemp(prefix="pilot_preflight_res_")
        try:
            ask_calls = []

            def selective_counter(messages):
                text = pilot_pr.messages_to_text(messages)
                # Simulate item6_pr15 exceeding 65536 - 8192 = 57344 tokens; item6_pr06 fits
                if "Audit and fix stale lines" in text:
                    return 60000
                return 2500

            def mock_ask(messages, seed):
                ask_calls.append(pilot_pr.messages_to_text(messages)[:80])
                calls = [
                    {"tool": "create_file", "args": {"path": "touched.txt", "content": "ok\n"}},
                    {"tool": "finish", "args": {"summary": "done"}},
                ]
                return {"content": "```json\n" + json.dumps(calls) + "\n```", "usage": {"completion_tokens": 25}}

            # Run item6_pr15 (preflight overflow) followed by item6_pr06 (runs cleanly)
            rows = pilot_pr.run_subcommand(
                label="preflight-test",
                tasks_arg="item6_pr15,item6_pr06",
                max_turns=1,
                slot_ctx=65536,
                reserved_output_tokens=8192,
                results_dir=results_dir,
                ask_fn=mock_ask,
                token_counter=selective_counter,
            )
            self.assertEqual(len(rows), 2)
            by_id = {r["task_id"]: r for r in rows}

            # item6_pr15 stopped at preflight without ever calling ask_fn
            r15 = by_id["item6_pr15"]
            self.assertFalse(r15["passed"])
            self.assertEqual(r15["stop_reason"], "context_overflow")
            self.assertEqual(r15["final_diff"], "")
            self.assertEqual(r15["total_completion_tokens"], 0)
            self.assertIn("prompt preflight overflow", r15["history"][0]["err"])

            # item6_pr06 was NOT aborted and ran normally
            self.assertEqual(len(ask_calls), 1, "ask_fn must only be called for the non-overflowing task")
            r06 = by_id["item6_pr06"]
            self.assertNotEqual(r06["stop_reason"], "context_overflow")
            self.assertIn("touched.txt", r06["final_diff"])

            # Also verify an unexpected RuntimeError in task 1 does not abort task 2
            def exploding_then_ok(messages, seed):
                text = pilot_pr.messages_to_text(messages)
                if "Audit and fix stale lines" in text:
                    raise RuntimeError("transient client failure")
                calls = [
                    {"tool": "create_file", "args": {"path": "survived.txt", "content": "yes\n"}},
                    {"tool": "finish", "args": {"summary": "done"}},
                ]
                return {"content": "```json\n" + json.dumps(calls) + "\n```", "usage": {"completion_tokens": 15}}

            rows2 = pilot_pr.run_subcommand(
                label="fault-isolation-test",
                tasks_arg="item6_pr15,item6_pr06",
                max_turns=1,
                results_dir=results_dir,
                ask_fn=exploding_then_ok,
                token_counter=lambda m: 1000,
            )
            by_id2 = {r["task_id"]: r for r in rows2}
            self.assertEqual(by_id2["item6_pr15"]["stop_reason"], "task_error")
            self.assertEqual(by_id2["item6_pr15"]["final_diff"], "")
            self.assertIn("survived.txt", by_id2["item6_pr06"]["final_diff"])
        finally:
            shutil.rmtree(results_dir, ignore_errors=True)

    def test_np1_64k_serving_config_llmctl_and_v1_freeze_guard(self):
        """Verify 1-slot 64k config in pilot_pr, run.sh, llmctl.py (including np2 GTT entries), and v1 freeze guard."""
        repo_root = os.path.abspath(os.path.join(HERE, "..", ".."))

        # 1. pilot_pr defaults
        self.assertEqual(pilot_pr.SLOT_CTX_DEFAULT, 65536)
        self.assertEqual(pilot_pr.RESERVED_OUTPUT_TOKENS, 8192)
        self.assertEqual(pilot_pr.SLOT_CTX_DEFAULT - pilot_pr.RESERVED_OUTPUT_TOKENS, 57344)

        # 2. run.sh uses --ctx 65536 --np 1, checks total_slots 1 n_ctx 65536, defaults to item6-pilot-v2, refuses item6-pilot
        run_sh = os.path.join(repo_root, "bench", "loop", "runs", "item6-pilot", "run.sh")
        with open(run_sh, "r", encoding="utf-8") as f:
            run_sh_text = f.read()
        self.assertIn("INVITE_OPTS=(--ctx 65536 --np 1)", run_sh_text)
        self.assertIn("total_slots 1 n_ctx 65536 ", run_sh_text)
        self.assertIn('LABEL="${LABEL:-item6-pilot-v2}"', run_sh_text)

        env_v1 = dict(os.environ, WT=repo_root, EXPECT_HEAD="0" * 40, LABEL="item6-pilot")
        res_v1 = subprocess.run(["bash", run_sh], cwd=repo_root, env=env_v1, capture_output=True, text=True)
        self.assertNotEqual(res_v1.returncode, 0)
        self.assertIn("frozen", res_v1.stderr)

        # 3. scripts/llmctl.py qwen defaults to ctx=65536 and carries measured np2 GTT deltas
        scripts_dir = os.path.join(repo_root, "scripts")
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        import llmctl  # noqa: E402
        qwen_ep = llmctl.ENDPOINTS["qwen"]
        self.assertEqual(qwen_ep.ctx, 65536)
        self.assertEqual(llmctl.expected_gtt(qwen_ep, {"ctx": None, "np": 1}), 22.4)
        self.assertEqual(llmctl.expected_gtt(qwen_ep, {"ctx": 65536, "np": 2}), 22.3)
        self.assertEqual(llmctl.expected_gtt(llmctl.ENDPOINTS["qwen32"], {"ctx": 65536, "np": 2}), 34.7)
        self.assertEqual(llmctl.expected_gtt(llmctl.ENDPOINTS["r1d32"], {"ctx": 65536, "np": 2}), 34.8)

        # 4. Per-task wall budget default is floor(4320 / 7) == 617 s
        self.assertEqual(pilot_pr.CEILING_SECONDS_DEFAULT, 4320)
        self.assertEqual(pilot_pr.TASK_WALL_BUDGET_DEFAULT, 617)
        self.assertIn("TASK_WALL_BUDGET=", run_sh_text)
        self.assertIn("--task-wall-budget", run_sh_text)

    def test_stub_truncation_guard_rejects_90_of_100_and_allows_move(self):
        """Verify stub/truncation guard rejects replacing 90 of 100 lines with 1 line, but allows moving the same block into another file."""
        temp_dir = tempfile.mkdtemp(prefix="pilot_stub_guard_")
        try:
            block_90 = "\n".join(f"item_row_{i} = {i * 17}" for i in range(90)) + "\n"
            tail_10 = "\n".join(f"tail_row_{i} = {i}" for i in range(10)) + "\n"
            src_path = os.path.join(temp_dir, "big_doc.py")
            with open(src_path, "w", encoding="utf-8") as f:
                f.write(block_90 + tail_10)

            # 1. search_replace replacing 90 of 100 lines with 1 line -> REJECTED
            sess1 = pilot_pr.ToolSession(temp_dir)
            ok_stub, msg_stub, _ = sess1.execute({
                "tool": "search_replace",
                "args": {"path": "big_doc.py", "old": block_90, "new": "# stubbed\n"},
            })
            self.assertFalse(ok_stub)
            self.assertIn("stub/truncation guard rejected", msg_stub)
            # File must remain untouched on disk
            with open(src_path, "r", encoding="utf-8") as f:
                self.assertEqual(f.read(), block_90 + tail_10)

            # 2. create_file(overwrite=True, justification=...) truncating 100-line file to 1 line -> REJECTED
            ok_ow_stub, msg_ow_stub, _ = sess1.execute({
                "tool": "create_file",
                "args": {
                    "path": "big_doc.py",
                    "content": "# stubbed\n",
                    "overwrite": True,
                    "justification": "Trying to replace the whole file with a one-line stub.",
                },
            })
            self.assertFalse(ok_ow_stub)
            self.assertIn("stub/truncation guard rejected", msg_ow_stub)

            # 3. Cumulative multi-call truncation (30 + 30 lines removed = 60/100) -> REJECTED on second edit
            chunk_a = "\n".join(f"item_row_{i} = {i * 17}" for i in range(30)) + "\n"
            chunk_b = "\n".join(f"item_row_{i} = {i * 17}" for i in range(30, 60)) + "\n"
            sess_cum = pilot_pr.ToolSession(temp_dir)
            ok_c1, msg_c1, _ = sess_cum.execute({
                "tool": "search_replace",
                "args": {"path": "big_doc.py", "old": chunk_a, "new": ""},
            })
            self.assertTrue(ok_c1, msg_c1)
            ok_c2, msg_c2, _ = sess_cum.execute({
                "tool": "search_replace",
                "args": {"path": "big_doc.py", "old": chunk_b, "new": ""},
            })
            self.assertFalse(ok_c2)
            self.assertIn("stub/truncation guard rejected", msg_c2)

            # Restore original file for move test
            with open(src_path, "w", encoding="utf-8") as f:
                f.write(block_90 + tail_10)

            # 4. Move the exact same 90-line block into another file first, then remove from source -> ALLOWED
            sess_move = pilot_pr.ToolSession(temp_dir)
            ok_dest, msg_dest, _ = sess_move.execute({
                "tool": "create_file",
                "args": {"path": "moved_part.py", "content": block_90},
            })
            self.assertTrue(ok_dest, msg_dest)
            ok_rm, msg_rm, _ = sess_move.execute({
                "tool": "search_replace",
                "args": {"path": "big_doc.py", "old": block_90, "new": "# moved to moved_part.py\n"},
            })
            self.assertTrue(ok_rm, msg_rm)
            ok_fin, msg_fin = sess_move.check_no_unrelocated_truncations()
            self.assertTrue(ok_fin, msg_fin)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_reachability_all_seven_reference_solutions(self):
        """Verify all 7 merged PR reference solutions are reachable under real v2 tool limits, and check_reachability is never imported by pilot_pr."""
        # Isolation invariant: pilot_pr must never import check_reachability
        with open(os.path.join(HERE, "pilot_pr.py"), "r", encoding="utf-8") as f:
            pilot_src = f.read()
        self.assertNotIn("check_reachability", pilot_src)

        import check_reachability  # noqa: E402
        repo_root = os.path.abspath(os.path.join(HERE, "..", ".."))
        reports = check_reachability.check_all_tasks(repo_root=repo_root)
        self.assertEqual(len(reports), 7)
        for rep in reports:
            self.assertTrue(
                rep["reachable"],
                f"Task {rep['task_id']} was NOT reachable under v2 tool limits: {rep['errors']}",
            )
            self.assertLessEqual(rep["overwrites_used"], pilot_pr.MAX_EXISTING_FILE_OVERWRITES)

    def test_task_wall_budget_records_failure_and_continues(self):
        """Verify hitting per-task wall budget records stop_reason='task_wall_budget', passed=False, preserves partial diff, and continues to next task."""
        results_dir = tempfile.mkdtemp(prefix="pilot_wall_budget_")
        try:
            # Simulated monotonic clock: advances 400 s per ask_fn call on item6_pr15, 10 s on item6_pr06
            now = [0.0]

            def fake_clock():
                return now[0]

            def timed_ask(messages, seed):
                joined = pilot_pr.messages_to_text(messages)
                if "Audit and fix stale lines" in joined:
                    # First call takes 700 s (> 617 s per-task wall budget) after applying an edit
                    now[0] += 700.0
                    calls = [{"tool": "create_file", "args": {"path": "partial_pr15.txt", "content": "partial\n"}}]
                    return {"content": "```json\n" + json.dumps(calls) + "\n```", "usage": {"completion_tokens": 20}}
                # Second task (item6_pr06) finishes well within its own 617 s budget
                now[0] += 10.0
                calls = [
                    {"tool": "create_file", "args": {"path": "ok_pr06.txt", "content": "done\n"}},
                    {"tool": "finish", "args": {"summary": "done"}},
                ]
                return {"content": "```json\n" + json.dumps(calls) + "\n```", "usage": {"completion_tokens": 20}}

            rows = pilot_pr.run_subcommand(
                label="wall-budget-test",
                tasks_arg="item6_pr15,item6_pr06",
                max_turns=4,
                task_wall_budget=617,
                clock_fn=fake_clock,
                results_dir=results_dir,
                ask_fn=timed_ask,
                token_counter=lambda m: 1000,
            )
            self.assertEqual(len(rows), 2)
            by_id = {r["task_id"]: r for r in rows}

            r15 = by_id["item6_pr15"]
            self.assertFalse(r15["passed"])
            self.assertEqual(r15["stop_reason"], "task_wall_budget")
            self.assertEqual(r15["stop"], "task_wall_budget")
            # Partial diff applied before wall budget expired is preserved for grading (matching max_turns/budget)
            self.assertIn("partial_pr15.txt", r15["final_diff"])

            # Second task still executed with its own fresh 617 s wall budget
            r06 = by_id["item6_pr06"]
            self.assertNotEqual(r06["stop_reason"], "task_wall_budget")
            self.assertIn("ok_pr06.txt", r06["final_diff"])

            # Also verify TimeoutError during ask_fn records task_wall_budget cleanly
            temp_dir = tempfile.mkdtemp(prefix="pilot_wall_timeout_")
            try:
                subprocess.run(["git", "init"], cwd=temp_dir, check=True, capture_output=True)
                subprocess.run(["git", "config", "user.name", "T"], cwd=temp_dir, check=True)
                subprocess.run(["git", "config", "user.email", "t@t"], cwd=temp_dir, check=True)
                with open(os.path.join(temp_dir, "x.txt"), "w") as f:
                    f.write("hi\n")
                subprocess.run(["git", "add", "."], cwd=temp_dir, check=True)
                subprocess.run(["git", "commit", "-m", "base"], cwd=temp_dir, check=True, capture_output=True)
                base_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=temp_dir, text=True).strip()
                t_mock = {
                    "id": "item6_timeout",
                    "pr_number": 920,
                    "title": "Timeout task",
                    "base_commit": base_sha,
                    "merged_commit": "4" * 40,
                    "has_tests": False,
                    "test_cmd": "",
                    "prompt": "Update x.txt",
                    "files": ["x.txt"],
                }

                def timeout_ask(messages, seed, timeout=None):
                    raise TimeoutError("timed out")

                timeout_ask._accepts_timeout = True
                res_to = pilot_pr.run_task_loop(t_mock, timeout_ask, temp_dir, max_turns=4, task_wall_budget=617)
                self.assertFalse(res_to["passed"])
                self.assertEqual(res_to["stop_reason"], "task_wall_budget")
            finally:
                shutil.rmtree(temp_dir, ignore_errors=True)
        finally:
            shutil.rmtree(results_dir, ignore_errors=True)

    def test_final_turn_note_fires_only_on_last_turn(self):
        """Verify the final-turn note is shown to the model strictly on turn index max_turns - 1 (both normal and parse-error paths)."""
        temp_dir = tempfile.mkdtemp(prefix="pilot_final_note_")
        try:
            subprocess.run(["git", "init"], cwd=temp_dir, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "T"], cwd=temp_dir, check=True)
            subprocess.run(["git", "config", "user.email", "t@t"], cwd=temp_dir, check=True)
            with open(os.path.join(temp_dir, "a.txt"), "w") as f:
                f.write("line1\n")
            subprocess.run(["git", "add", "."], cwd=temp_dir, check=True)
            subprocess.run(["git", "commit", "-m", "base"], cwd=temp_dir, check=True, capture_output=True)
            base_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=temp_dir, text=True).strip()

            task = {
                "id": "item6_final_note",
                "pr_number": 921,
                "title": "Final note check",
                "base_commit": base_sha,
                "merged_commit": "5" * 40,
                "has_tests": False,
                "test_cmd": "",
                "prompt": "Read a.txt",
                "files": ["a.txt"],
            }

            # Case 1: Normal tool-call turns (max_turns=4 -> turns 0, 1, 2, 3)
            saw_note = []
            turn_n = [0]

            def observe_turns(messages, seed):
                t = turn_n[0]
                turn_n[0] += 1
                last_user = messages[-1]["content"] if messages else ""
                saw_note.append("This is your final turn" in last_user)
                calls = [{"tool": "read_file", "args": {"path": "a.txt", "start": 1, "end": t + 1}}]
                return {"content": "```json\n" + json.dumps(calls) + "\n```", "usage": {"completion_tokens": 10}}

            pilot_pr.run_task_loop(task, observe_turns, temp_dir, max_turns=4)
            self.assertEqual(saw_note, [False, False, False, True])

            # Case 2: Parse-error (no tool calls) on turn max_turns - 2 still delivers final-turn note on turn max_turns - 1
            saw_note2 = []
            turn_n2 = [0]

            def observe_parse_err(messages, seed):
                t = turn_n2[0]
                turn_n2[0] += 1
                last_user = messages[-1]["content"] if messages else ""
                saw_note2.append("This is your final turn" in last_user)
                if t == 1:
                    # Emit unparseable prose on turn max_turns - 2 (turn 1 of 3)
                    return {"content": "thinking without tool call", "usage": {"completion_tokens": 10}}
                calls = [{"tool": "read_file", "args": {"path": "a.txt", "start": 1, "end": t + 1}}]
                return {"content": "```json\n" + json.dumps(calls) + "\n```", "usage": {"completion_tokens": 10}}

            pilot_pr.run_task_loop(task, observe_parse_err, temp_dir, max_turns=3)
            self.assertEqual(saw_note2, [False, False, True])
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_pr16_read_and_grep_run_py_with_oracle_sentinel_does_not_trip(self):
        """Reading or grepping bench/loop/run.py at PR #16 base (containing ORACLE-SENTINEL-7f3a91c2) must not trip and must leave a record."""
        results_dir = tempfile.mkdtemp(prefix="pilot_pr16_noleak_res_")
        run_dir = tempfile.mkdtemp(prefix="pilot_pr16_noleak_run_")
        try:
            task16 = tasks_item6.get_task("item6_pr16")
            self.assertEqual(task16["base_commit"], "6c56cc09eaafb2376422e73515b39f8193893740")

            turn_seen = []
            saw_oracle_sentinel_in_prompt = [False]

            def pr16_reader_model(messages, seed):
                idx = len(turn_seen)
                turn_seen.append(idx)
                joined = pilot_pr.messages_to_text(messages)
                if idx == 0:
                    calls = [
                        {"tool": "grep", "args": {"pattern": "ORACLE-SENTINEL", "path": "bench/loop/run.py"}},
                        {"tool": "read_file", "args": {"path": "bench/loop/run.py", "start": 345, "end": 360}},
                    ]
                    return {"content": "```json\n" + json.dumps(calls) + "\n```", "usage": {"completion_tokens": 30}}
                # Turn 1 receives tool output containing ORACLE-SENTINEL-7f3a91c2; check_prompt_leak must NOT trip
                if "ORACLE-SENTINEL-7f3a91c2" in joined:
                    saw_oracle_sentinel_in_prompt[0] = True
                calls = [
                    {"tool": "create_file", "args": {"path": "bench/loop/pr16_probe.txt", "content": "checked\n"}},
                ]
                return {"content": "```json\n" + json.dumps(calls) + "\n```", "usage": {"completion_tokens": 25}}

            rows = pilot_pr.run_subcommand(
                label="pr16-sentinel-check",
                tasks_arg="item6_pr16",
                max_turns=2,
                results_dir=results_dir,
                run_dir=run_dir,
                ask_fn=pr16_reader_model,
                token_counter=lambda m: 1500,
            )
            self.assertEqual(len(rows), 1)
            self.assertEqual(len(turn_seen), 2, "Turn 1 must execute after reading ORACLE-SENTINEL-7f3a91c2")
            self.assertTrue(
                saw_oracle_sentinel_in_prompt[0],
                "Tool results from bench/loop/run.py at 6c56cc09 must contain ORACLE-SENTINEL-7f3a91c2",
            )
            row = rows[0]
            self.assertEqual(row["task_id"], "item6_pr16")
            self.assertNotEqual(row["stop_reason"], "prompt_leak")
            self.assertIn("pr16_probe.txt", row["final_diff"])

            # Verify JSONL record and diff were flushed
            jsonl_path = os.path.join(results_dir, "pr16-sentinel-check.jsonl")
            self.assertTrue(os.path.exists(jsonl_path))
            with open(jsonl_path, "r", encoding="utf-8") as f:
                lines = [json.loads(ln) for ln in f if ln.strip()]
            self.assertEqual(len(lines), 1)
            self.assertEqual(lines[0]["task_id"], "item6_pr16")

            # Verify per-turn instrumentation logged tool name, path/pattern args, and result_chars in run_dir
            events_path = os.path.join(run_dir, "turn_events.jsonl")
            self.assertTrue(os.path.exists(events_path))
            with open(events_path, "r", encoding="utf-8") as f:
                events = [json.loads(ln) for ln in f if ln.strip()]
            self.assertGreaterEqual(len(events), 2)
            t0_tools = {t["tool"]: t for t in events[0]["tools"]}
            self.assertIn("grep", t0_tools)
            self.assertEqual(t0_tools["grep"]["args"].get("pattern"), "ORACLE-SENTINEL")
            self.assertEqual(t0_tools["grep"]["args"].get("path"), "bench/loop/run.py")
            self.assertGreater(t0_tools["grep"]["result_chars"], 0)
            self.assertIn("read_file", t0_tools)
            self.assertEqual(t0_tools["read_file"]["args"].get("path"), "bench/loop/run.py")
            self.assertGreater(t0_tools["read_file"]["result_chars"], 0)
            # No leak history file should exist when no leak fired
            self.assertFalse(any(fn.startswith("leak_history_") for fn in os.listdir(run_dir)))
        finally:
            shutil.rmtree(results_dir, ignore_errors=True)
            shutil.rmtree(run_dir, ignore_errors=True)

    def test_genuine_hidden_diff_leak_fails_closed_records_prompt_leak_and_continues(self):
        """A genuine hidden_diff leak fails closed, records stop_reason=prompt_leak, keeps partial diff, logs leak history to run_dir, and continues other tasks."""
        results_dir = tempfile.mkdtemp(prefix="pilot_hdiff_leak_res_")
        run_dir = tempfile.mkdtemp(prefix="pilot_hdiff_leak_run_")
        repo_root = os.path.abspath(os.path.join(HERE, "..", ".."))
        try:
            # Verify per-run sentinels are random and distinct
            s1 = pilot_pr.generate_run_sentinel()
            s2 = pilot_pr.generate_run_sentinel()
            self.assertNotEqual(s1, s2)
            self.assertTrue(s1.startswith("PILOT-RUN-SENTINEL-"))

            # Verify repo-internal run_dir is redirected away from git repo
            redirected = pilot_pr._safe_uncommitted_run_dir(
                os.path.join(repo_root, "bench", "loop", "results"),
                label="safety-test",
                repo_root=repo_root,
            )
            self.assertTrue(redirected.startswith("/tmp/lab-seats/"))

            # Build two tasks: task A leaks its own hidden_diff into turn-1 tool output after making a partial edit;
            # task B runs cleanly right after to prove run_subcommand does not re-raise AssertionError and continues.
            base_pr06 = tasks_item6.get_task("item6_pr06")
            base_pr15 = tasks_item6.get_task("item6_pr15")
            leaked_marker = "diff --git a/secret_oracle.py b/secret_oracle.py\n+SECRET_ORACLE_ANSWER = 999999"
            task_a = dict(base_pr06)
            task_a["hidden_diff"] = leaked_marker
            # Simulated leaky test_cmd prints the hidden_diff on failure so turn 1 prompt contains hidden_diff
            task_a["test_cmd"] = (
                "python3 -c \"print(" + repr(leaked_marker) + "); raise SystemExit(1)\""
            )

            ask_calls_by_task = {"pr06": 0, "pr15": 0}

            def mock_two_task_model(messages, seed):
                joined = pilot_pr.messages_to_text(messages)
                # Ensure leaked hidden_diff NEVER reaches the model!
                self.assertNotIn(leaked_marker, joined, "Leaked hidden_diff must NEVER be sent to ask_fn!")
                if "Fix `bench/loop/debate.py` parser logic" in joined:
                    ask_calls_by_task["pr06"] += 1
                    calls = [
                        {"tool": "create_file", "args": {"path": "partial_before_leak.txt", "content": "partial edit\n"}},
                        {"tool": "run_tests", "args": {}},
                    ]
                    return {"content": "```json\n" + json.dumps(calls) + "\n```", "usage": {"completion_tokens": 30}}
                ask_calls_by_task["pr15"] += 1
                calls = [
                    {"tool": "create_file", "args": {"path": "after_leak_ok.txt", "content": "continued\n"}},
                    {"tool": "finish", "args": {"summary": "done"}},
                ]
                return {"content": "```json\n" + json.dumps(calls) + "\n```", "usage": {"completion_tokens": 20}}

            rows = pilot_pr.run_subcommand(
                label="hidden-diff-leak",
                tasks_arg="item6_pr06,item6_pr15",
                max_turns=3,
                results_dir=results_dir,
                run_dir=run_dir,
                ask_fn=mock_two_task_model,
                token_counter=lambda m: 1200,
                tasks_override=[task_a, base_pr15],
            )
            self.assertEqual(len(rows), 2, "run_subcommand must record both tasks and not abort on prompt_leak")
            by_id = {r["task_id"]: r for r in rows}

            # Task A: failed closed before turn 1 ask_fn, recorded as prompt_leak, partial diff preserved
            self.assertEqual(ask_calls_by_task["pr06"], 1, "Turn 1 with leaked hidden_diff must not be sent to model")
            r_a = by_id["item6_pr06"]
            self.assertFalse(r_a["passed"])
            self.assertEqual(r_a["stop_reason"], "prompt_leak")
            self.assertEqual(r_a["stop"], "prompt_leak")
            self.assertEqual(r_a["leak_branch"], "hidden_diff")
            self.assertIn("partial_before_leak.txt", r_a["final_diff"])

            # Task B: continued cleanly after task A's prompt_leak
            self.assertEqual(ask_calls_by_task["pr15"], 1)
            r_b = by_id["item6_pr15"]
            self.assertTrue(r_b["passed"])
            self.assertEqual(r_b["stop_reason"], "applied_no_tests")
            self.assertIn("after_leak_ok.txt", r_b["final_diff"])

            # Verify JSONL was flushed with both records and does NOT leak raw hidden_diff content
            jsonl_path = os.path.join(results_dir, "hidden-diff-leak.jsonl")
            with open(jsonl_path, "r", encoding="utf-8") as f:
                raw_jsonl = f.read()
            self.assertNotIn(leaked_marker, raw_jsonl, "JSONL must not contain raw leaked hidden_diff")
            parsed_rows = [json.loads(ln) for ln in raw_jsonl.splitlines() if ln.strip()]
            self.assertEqual([r["task_id"] for r in parsed_rows], ["item6_pr06", "item6_pr15"])

            # Verify partial diff file was written on disk
            diff_a = os.path.join(results_dir, "hidden-diff-leak.diffs", "item6_pr06.diff")
            with open(diff_a, "r", encoding="utf-8") as f:
                self.assertIn("partial_before_leak.txt", f.read())

            # Verify instrumentation logged leak_branch and saved leaked message history ONLY under run_dir
            events_path = os.path.join(run_dir, "turn_events.jsonl")
            with open(events_path, "r", encoding="utf-8") as f:
                events = [json.loads(ln) for ln in f if ln.strip()]
            leak_events = [e for e in events if e.get("event") == "prompt_leak"]
            self.assertEqual(len(leak_events), 1)
            self.assertEqual(leak_events[0]["leak_branch"], "hidden_diff")
            hist_file = leak_events[0]["history_file"]
            self.assertTrue(os.path.exists(hist_file))
            self.assertTrue(os.path.realpath(hist_file).startswith(os.path.realpath(run_dir) + os.sep))
            with open(hist_file, "r", encoding="utf-8") as f:
                hist_data = json.load(f)
            self.assertEqual(hist_data["leak_branch"], "hidden_diff")
            self.assertIn(leaked_marker, pilot_pr.messages_to_text(hist_data["messages"]))

            # Also verify zero-edit turn-0 leak (e.g. prompt contains hidden_diff) produces empty diff & prompt_leak
            task_zero = dict(base_pr15)
            task_zero["hidden_diff"] = "UNIQUE_TURN0_HIDDEN_DIFF_LEAK"
            task_zero["prompt"] = task_zero["prompt"] + "\n" + task_zero["hidden_diff"]
            zero_ask_calls = []
            def never_called(messages, seed):
                zero_ask_calls.append(True)
                return {"content": "", "usage": {}}
            rows_z = pilot_pr.run_subcommand(
                label="zero-edit-leak",
                tasks_arg="item6_pr15",
                max_turns=2,
                results_dir=results_dir,
                run_dir=run_dir,
                ask_fn=never_called,
                tasks_override=[task_zero],
            )
            self.assertEqual(len(zero_ask_calls), 0)
            self.assertEqual(rows_z[0]["stop_reason"], "prompt_leak")
            self.assertEqual(rows_z[0]["final_diff"], "")
        finally:
            shutil.rmtree(results_dir, ignore_errors=True)
            shutil.rmtree(run_dir, ignore_errors=True)

    def test_resume_frozen_v2_queues_only_pr16_and_matches_committed_sha256sums(self):
        """RESUME=1 on frozen v2 run-1 evidence queues only item6_pr16 and leaves existing 6 records and diffs byte-for-byte identical against committed SHA256SUMS."""
        import hashlib

        repo_root = os.path.abspath(os.path.join(HERE, "..", ".."))
        committed_res = os.path.join(repo_root, "bench", "loop", "results")
        sums_path = os.path.join(committed_res, "item6-pilot-v2.SHA256SUMS")
        self.assertTrue(os.path.exists(sums_path), f"Committed SHA256SUMS missing: {sums_path}")

        def _sha256_bytes(data: bytes) -> str:
            return hashlib.sha256(data).hexdigest()

        def _sha256_file(path: str) -> str:
            with open(path, "rb") as f:
                return _sha256_bytes(f.read())

        # 1. Verify all committed entries in item6-pilot-v2.SHA256SUMS match on disk
        expected_hashes = {}
        with open(sums_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                digest, rel = line.split(None, 1)
                expected_hashes[rel] = digest
                full_p = os.path.join(committed_res, rel)
                self.assertTrue(os.path.exists(full_p), f"Missing committed frozen file: {rel}")
                self.assertEqual(_sha256_file(full_p), digest, f"SHA256 mismatch on committed {rel}")

        self.assertEqual(len(expected_hashes), 9)
        self.assertNotIn("item6-pilot-v2.diffs/item6_pr16.diff", expected_hashes)

        # 2. Copy frozen jsonl and diffs into a temp results dir and run RESUME=1 across all 7 tasks
        tmp_res = tempfile.mkdtemp(prefix="pilot_v2_resume_res_")
        tmp_run = tempfile.mkdtemp(prefix="pilot_v2_resume_run_")
        try:
            shutil.copy2(
                os.path.join(committed_res, "item6-pilot-v2.jsonl"),
                os.path.join(tmp_res, "item6-pilot-v2.jsonl"),
            )
            shutil.copytree(
                os.path.join(committed_res, "item6-pilot-v2.diffs"),
                os.path.join(tmp_res, "item6-pilot-v2.diffs"),
            )

            executed_prompts = []

            def mock_pr16_resume(messages, seed):
                executed_prompts.append(pilot_pr.messages_to_text(messages)[:120])
                calls = [
                    {"tool": "create_file", "args": {"path": "bench/loop/resume_probe.txt", "content": "pr16\n"}},
                ]
                return {"content": "```json\n" + json.dumps(calls) + "\n```", "usage": {"completion_tokens": 18}}

            rows = pilot_pr.run_subcommand(
                label="item6-pilot-v2",
                tasks_arg=None,
                max_turns=1,
                results_dir=tmp_res,
                run_dir=tmp_run,
                ask_fn=mock_pr16_resume,
                token_counter=lambda m: 1500,
                resume=True,
            )

            # Only item6_pr16 should have been queued and run
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["task_id"], "item6_pr16")
            self.assertEqual(len(executed_prompts), 1)

            # Verify all 6 frozen diff files remain byte-for-byte identical to committed SHA256SUMS
            for rel, digest in expected_hashes.items():
                if rel.startswith("item6-pilot-v2.diffs/"):
                    self.assertEqual(
                        _sha256_file(os.path.join(tmp_res, rel)),
                        digest,
                        f"Frozen diff {rel} was modified during RESUME=1!",
                    )
            self.assertTrue(os.path.exists(os.path.join(tmp_res, "item6-pilot-v2.diffs", "item6_pr16.diff")))

            # Verify the 6 frozen JSONL lines remain byte-for-byte identical to committed item6-pilot-v2.jsonl
            resumed_jsonl = os.path.join(tmp_res, "item6-pilot-v2.jsonl")
            with open(resumed_jsonl, "rb") as f:
                all_lines = f.readlines()
            self.assertEqual(len(all_lines), 7)
            frozen_6_lines = [ln for ln in all_lines if json.loads(ln)["task_id"] != "item6_pr16"]
            self.assertEqual(len(frozen_6_lines), 6)
            self.assertEqual(
                _sha256_bytes(b"".join(frozen_6_lines)),
                expected_hashes["item6-pilot-v2.jsonl"],
                "Existing 6 frozen JSONL records must be byte-for-byte identical to committed SHA256SUMS!",
            )
        finally:
            shutil.rmtree(tmp_res, ignore_errors=True)
            shutil.rmtree(tmp_run, ignore_errors=True)

    def test_launcher_completeness_check_writes_incomplete_missing_and_exits_nonzero(self):
        """Verify run.sh checks all 7 task IDs at the end, writes incomplete missing=<ids> and exits non-zero when any is missing, and defaults TASK_WALL_BUDGET=617."""
        repo_root = os.path.abspath(os.path.join(HERE, "..", ".."))
        run_sh = os.path.join(repo_root, "bench", "loop", "runs", "item6-pilot", "run.sh")
        frozen_jsonl = os.path.join(repo_root, "bench", "loop", "results", "item6-pilot-v2.jsonl")

        with open(run_sh, "r", encoding="utf-8") as f:
            run_sh_text = f.read()

        self.assertIn('TASK_WALL_BUDGET="${TASK_WALL_BUDGET:-617}"', run_sh_text)
        self.assertIn('--run-dir "$DIR"', run_sh_text)
        self.assertIn("check_results_complete", run_sh_text)
        self.assertIn("incomplete missing=", run_sh_text)

        # Extract on_exit and check_results_complete directly from run.sh and exercise both missing & complete cases
        tmp_dir = tempfile.mkdtemp(prefix="pilot_complete_check_")
        try:
            harness_sh = os.path.join(tmp_dir, "test_complete.sh")
            script = (
                "#!/usr/bin/env bash\n"
                "set -euo pipefail\n"
                f"RUN_SH={run_sh!r}\n"
                'DIR="$1"\n'
                'RESULTS_FILE="$2"\n'
                "start=$(date +%s)\n"
                "invited=0\n"
                'eval "$(sed -n \'/^on_exit() {/,/^}/p\' "$RUN_SH")"\n'
                'eval "$(sed -n \'/^check_results_complete() {/,/^}/p\' "$RUN_SH")"\n'
                'eval "$(sed -n \'/^ALL_TASKS=(/,/^)/p\' "$RUN_SH")"\n'
                "trap on_exit EXIT\n"
                'echo "running $(date -Iseconds)" > "$DIR/run.status"\n'
                "set +e\n"
                'missing_ids=$(check_results_complete "$RESULTS_FILE" "${ALL_TASKS[@]}")\n'
                "complete_rc=$?\n"
                "set -e\n"
                "if [[ $complete_rc -ne 0 ]]; then\n"
                "  wall_now=$(( $(date +%s) - start ))\n"
                '  echo "incomplete missing=${missing_ids} wall_s=${wall_now} end=$(date -Iseconds)" > "$DIR/run.status"\n'
                "  exit 1\n"
                "fi\n"
                "exit 0\n"
            )
            with open(harness_sh, "w", encoding="utf-8") as f:
                f.write(script)
            os.chmod(harness_sh, 0o755)

            # Case 1: Frozen 6-record item6-pilot-v2.jsonl (missing item6_pr16) -> must exit non-zero & write incomplete missing=item6_pr16
            d_miss = os.path.join(tmp_dir, "miss")
            os.makedirs(d_miss, exist_ok=True)
            r_miss = subprocess.run(["bash", harness_sh, d_miss, frozen_jsonl], capture_output=True, text=True)
            self.assertNotEqual(r_miss.returncode, 0, "Missing item6_pr16 must exit non-zero")
            with open(os.path.join(d_miss, "run.status"), "r", encoding="utf-8") as f:
                st_miss = f.read().strip()
            self.assertTrue(
                st_miss.startswith("incomplete missing=item6_pr16 "),
                f"Expected 'incomplete missing=item6_pr16 ...', got: {st_miss!r}",
            )
            self.assertNotIn("done rc=0", st_miss)

            # Case 2: All 7 records present -> must exit 0 & write done rc=0
            d_ok = os.path.join(tmp_dir, "ok")
            os.makedirs(d_ok, exist_ok=True)
            full_jsonl = os.path.join(tmp_dir, "full7.jsonl")
            shutil.copy2(frozen_jsonl, full_jsonl)
            with open(full_jsonl, "a", encoding="utf-8") as f:
                f.write(json.dumps({"task_id": "item6_pr16", "pr_number": 16}) + "\n")
            r_ok = subprocess.run(["bash", harness_sh, d_ok, full_jsonl], capture_output=True, text=True)
            self.assertEqual(r_ok.returncode, 0, f"Complete 7-record jsonl should exit 0: {r_ok.stderr}")
            with open(os.path.join(d_ok, "run.status"), "r", encoding="utf-8") as f:
                st_ok = f.read().strip()
            self.assertTrue(st_ok.startswith("done rc=0 "), f"Expected 'done rc=0 ...', got: {st_ok!r}")
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_pr16_reading_own_target_files_at_base_does_not_trip_but_full_hidden_diff_trips(self):
        """Reading/grepping/listing item6_pr16's own target files at base 6c56cc0 (context lines shared with reference diff) must not trip; injecting full hidden_diff still trips."""
        repo_root = os.path.abspath(os.path.join(HERE, "..", ".."))
        results_dir = tempfile.mkdtemp(prefix="pilot_pr16_ctx_res_")
        run_dir = tempfile.mkdtemp(prefix="pilot_pr16_ctx_run_")
        try:
            task16 = tasks_item6.get_task("item6_pr16")
            self.assertEqual(task16["base_commit"], "6c56cc09eaafb2376422e73515b39f8193893740")
            full_hidden_diff = tasks_item6.get_hidden_diff(task16, repo_root=repo_root)
            self.assertIn("diff --git a/README.md b/README.md", full_hidden_diff)
            # Context line shared verbatim between README.md at base 6c56cc0 and item6_pr16's hidden_diff
            shared_context_line = "docs/crawdad-v10-noise.md"
            self.assertIn(shared_context_line, full_hidden_diff)

            turn_calls = []
            saw_readme_context = [False]
            saw_list_files = [False]

            def read_target_files_model(messages, seed):
                turn_idx = len(turn_calls)
                turn_calls.append(turn_idx)
                joined = pilot_pr.messages_to_text(messages)
                if turn_idx == 0:
                    # Read, grep, and list item6_pr16's own target files at base 6c56cc0
                    calls = [
                        {"tool": "list_files", "args": {"path": "."}},
                        {"tool": "list_files", "args": {"path": "bench/loop"}},
                        {"tool": "read_file", "args": {"path": "README.md", "start": 1, "end": 250}},
                        {"tool": "grep", "args": {"pattern": "crawdad-v10-noise", "path": "README.md"}},
                        {"tool": "grep", "args": {"pattern": "roadmap\\.md", "path": "README.md"}},
                    ]
                    return {"content": "```json\n" + json.dumps(calls) + "\n```", "usage": {"completion_tokens": 35}}
                if shared_context_line in joined:
                    saw_readme_context[0] = True
                if "bench/loop/run.py" in joined:
                    saw_list_files[0] = True
                calls = [
                    {"tool": "create_file", "args": {"path": "bench/loop/ctx_ok.txt", "content": "ok\n"}},
                ]
                return {"content": "```json\n" + json.dumps(calls) + "\n```", "usage": {"completion_tokens": 20}}

            rows = pilot_pr.run_subcommand(
                label="pr16-ctx-no-misfire",
                tasks_arg="item6_pr16",
                max_turns=2,
                results_dir=results_dir,
                run_dir=run_dir,
                ask_fn=read_target_files_model,
                token_counter=lambda m: 2000,
            )
            self.assertEqual(len(rows), 1)
            self.assertEqual(len(turn_calls), 2, "Turn 1 must execute without misfiring on README.md context lines")
            self.assertTrue(saw_readme_context[0], "README.md context lines shared with hidden_diff must be in turn 1 prompt")
            self.assertTrue(saw_list_files[0], "list_files output must be in turn 1 prompt")
            self.assertNotEqual(rows[0]["stop_reason"], "prompt_leak")

            # Injecting the full reference hidden_diff of item6_pr16 MUST still trip check_prompt_leak and fail closed
            guard_task16 = dict(task16, hidden_diff=full_hidden_diff)
            with self.assertRaises(pilot_pr.PromptLeakError) as cm:
                pilot_pr.check_prompt_leak(f"leaked:\n{full_hidden_diff}\n", guard_task16)
            self.assertEqual(cm.exception.branch, "hidden_diff")

            leaked_task16 = dict(task16)
            leaked_task16["hidden_diff"] = full_hidden_diff
            leaked_task16["prompt"] = leaked_task16["prompt"] + "\n" + full_hidden_diff
            called_on_leak = []
            def must_not_run(messages, seed):
                called_on_leak.append(True)
                return {"content": "", "usage": {}}

            rows_leak = pilot_pr.run_subcommand(
                label="pr16-full-hidden-leak",
                tasks_arg="item6_pr16",
                max_turns=2,
                results_dir=results_dir,
                run_dir=run_dir,
                ask_fn=must_not_run,
                tasks_override=[leaked_task16],
            )
            self.assertEqual(len(called_on_leak), 0, "Model must never be called when full hidden_diff leaks")
            self.assertEqual(rows_leak[0]["stop_reason"], "prompt_leak")
            self.assertEqual(rows_leak[0]["leak_branch"], "hidden_diff")
        finally:
            shutil.rmtree(results_dir, ignore_errors=True)
            shutil.rmtree(run_dir, ignore_errors=True)

    def test_hidden_diff_and_merged_sha_only_in_host_memory_not_in_sandbox_or_logs(self):
        """Verify hidden_diff and merged_commit never enter scratch tree, sandbox TMPDIR/env/argv, stdout/run.log, or turn_events.jsonl; leak histories default under /tmp/lab-seats/."""
        import contextlib
        import io

        repo_root = os.path.abspath(os.path.join(HERE, "..", ".."))
        results_dir = tempfile.mkdtemp(prefix="pilot_memonly_res_")
        run_dir = tempfile.mkdtemp(prefix="pilot_memonly_run_")
        orig_build_bwrap = pilot_pr.build_outer_bwrap_cmd
        captured_bwrap = []
        try:
            # Verify default_run_dir resolves strictly under /tmp/lab-seats/
            self.assertEqual(pilot_pr.default_run_dir("item6-pilot-v2"), "/tmp/lab-seats/item6-pilot-v2")

            task16 = tasks_item6.get_task("item6_pr16")
            merged_sha = task16["merged_commit"]
            full_hidden_diff = tasks_item6.get_hidden_diff(task16, repo_root=repo_root)
            # Pick a distinctive added line from PR #16's hidden diff that does not exist at base 6c56cc0
            added_marker = "docs/crawdad-ground-v1.md"
            self.assertIn(added_marker, full_hidden_diff)

            # Spy on build_outer_bwrap_cmd while still running the real sandbox
            def spy_build_bwrap(task_dir, home_dir, tmp_dir, shim_dir, inner_argv, env_dict, ro_binds=None):
                cmd = orig_build_bwrap(task_dir, home_dir, tmp_dir, shim_dir, inner_argv, env_dict, ro_binds=ro_binds)
                # Inspect scratch tree and sandbox TMPDIR on host at execution time
                scratch_entries = []
                for dp, dns, fns in os.walk(task_dir):
                    dns[:] = [d for d in dns if d != ".git"]
                    for fn in fns:
                        scratch_entries.append(os.path.join(dp, fn))
                tmp_entries = os.listdir(tmp_dir)
                captured_bwrap.append({
                    "cmd": list(cmd),
                    "env": dict(env_dict),
                    "tmp_entries": tmp_entries,
                    "scratch_has_ground": any(p.endswith("bench/loop/ground.py") for p in scratch_entries),
                })
                return cmd

            pilot_pr.build_outer_bwrap_cmd = spy_build_bwrap

            # Use a sandboxed test_cmd that dumps env, argv, /tmp, and /work/bench/loop inside the child
            probe_task = dict(task16)
            probe_task["test_cmd"] = (
                "python3 -c \"import os, sys; "
                "print('CHILD_ENV=' + repr(dict(os.environ))); "
                "print('CHILD_ARGV=' + repr(sys.argv)); "
                "print('CHILD_TMP=' + repr(os.listdir('/tmp'))); "
                "print('CHILD_WORK=' + repr(sorted(os.listdir('/work/bench/loop'))))\""
            )

            turn_n = [0]
            def sandbox_probe_model(messages, seed):
                t = turn_n[0]
                turn_n[0] += 1
                if t == 0:
                    calls = [
                        {"tool": "read_file", "args": {"path": "README.md", "start": 1, "end": 40}},
                        {"tool": "run_tests", "args": {}},
                    ]
                else:
                    calls = [
                        {"tool": "create_file", "args": {"path": "bench/loop/memonly_probe.txt", "content": "ok\n"}},
                        {"tool": "finish", "args": {"summary": "probed"}},
                    ]
                return {"content": "```json\n" + json.dumps(calls) + "\n```", "usage": {"completion_tokens": 25}}

            stdout_buf = io.StringIO()
            stderr_buf = io.StringIO()
            with contextlib.redirect_stdout(stdout_buf), contextlib.redirect_stderr(stderr_buf):
                rows = pilot_pr.run_subcommand(
                    label="memonly-check",
                    tasks_arg="item6_pr16",
                    max_turns=2,
                    results_dir=results_dir,
                    run_dir=run_dir,
                    ask_fn=sandbox_probe_model,
                    token_counter=lambda m: 1500,
                    tasks_override=[probe_task],
                )

            self.assertEqual(len(rows), 1)
            self.assertTrue(rows[0]["passed"])
            self.assertGreaterEqual(len(captured_bwrap), 1, "run_tests must have invoked outer bwrap sandbox")

            # 1. Verify sandbox env, argv, scratch tree, and TMPDIR contain neither hidden_diff nor merged_commit
            for rec in captured_bwrap:
                cmd_str = " ".join(str(x) for x in rec["cmd"])
                env_str = json.dumps(rec["env"], sort_keys=True)
                self.assertNotIn(merged_sha, cmd_str)
                self.assertNotIn(full_hidden_diff, cmd_str)
                self.assertNotIn(added_marker, cmd_str)
                self.assertNotIn(merged_sha, env_str)
                self.assertNotIn(full_hidden_diff, env_str)
                self.assertNotIn(added_marker, env_str)
                self.assertEqual(rec["tmp_entries"], [], "Sandbox TMPDIR must be empty before child starts")
                self.assertFalse(rec["scratch_has_ground"], "Scratch tree must not contain merged-only files")

            # 2. Verify run.log-equivalent stdout/stderr does not contain hidden_diff or merged_commit
            run_log_out = stdout_buf.getvalue() + stderr_buf.getvalue()
            self.assertNotIn(merged_sha, run_log_out)
            self.assertNotIn(full_hidden_diff, run_log_out)

            # 3. Verify turn_events.jsonl does not contain hidden_diff or merged_commit
            events_path = os.path.join(run_dir, "turn_events.jsonl")
            self.assertTrue(os.path.exists(events_path))
            with open(events_path, "r", encoding="utf-8") as f:
                events_text = f.read()
            self.assertNotIn(merged_sha, events_text)
            self.assertNotIn(full_hidden_diff, events_text)
            self.assertNotIn(added_marker, events_text)

            # 4. Even when a prompt_leak trips on merged_commit or hidden_diff, turn_events.jsonl and stdout/run.log
            #    must still NEVER contain the hidden_diff or merged_commit SHA (only leak_history_*.json in run_dir does)
            leak_task = dict(task16)
            leak_task["prompt"] = leak_task["prompt"] + f"\n{merged_sha}"
            stdout_leak = io.StringIO()
            stderr_leak = io.StringIO()
            with contextlib.redirect_stdout(stdout_leak), contextlib.redirect_stderr(stderr_leak):
                rows_l = pilot_pr.run_subcommand(
                    label="memonly-leak-check",
                    tasks_arg="item6_pr16",
                    max_turns=1,
                    results_dir=results_dir,
                    run_dir=run_dir,
                    ask_fn=lambda m, s: {"content": "", "usage": {}},
                    tasks_override=[leak_task],
                )
            self.assertEqual(rows_l[0]["stop_reason"], "prompt_leak")
            self.assertEqual(rows_l[0]["leak_branch"], "merged_commit")
            with open(events_path, "r", encoding="utf-8") as f:
                events_after = f.read()
            self.assertNotIn(merged_sha, events_after)
            self.assertNotIn(full_hidden_diff, events_after)
            self.assertNotIn(merged_sha, stdout_leak.getvalue() + stderr_leak.getvalue())
            with open(os.path.join(results_dir, "memonly-leak-check.jsonl"), "r", encoding="utf-8") as f:
                self.assertNotIn(merged_sha, f.read())
        finally:
            pilot_pr.build_outer_bwrap_cmd = orig_build_bwrap
            shutil.rmtree(results_dir, ignore_errors=True)
            shutil.rmtree(run_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
