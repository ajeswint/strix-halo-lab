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
                self.assertIsNotNone(t["test_cmd"])

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


if __name__ == "__main__":
    unittest.main()
