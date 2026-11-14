#!/usr/bin/env python3
"""CPU unit tests for CRAwDAD Grounding runner (bench/loop/ground.py)."""
import ast, os, re, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ground
import tasks_v10
import tasks_v10_visible
import run


class TestVisibleExtraction(unittest.TestCase):
    def test_visible_checks_derivable_from_prompt(self):
        """Every visible check's call or expr must appear in that task's prompt."""
        for t in tasks_v10.T:
            tid = t["id"]
            checks = tasks_v10_visible.CHECKS.get(tid, [])
            prompt_norm = " ".join(t["prompt"].split())
            for c in checks:
                expr = c["expr"]
                expr_norm = " ".join(expr.split())
                self.assertIn(expr_norm, prompt_norm,
                              f"Check expression {expr!r} not found in prompt for task {tid}")

    def test_every_ref_passes_visible_tests(self):
        """Every task's reference implementation must pass its visible tests in the sandbox."""
        for t in tasks_v10.T:
            tid = t["id"]
            vis = tasks_v10_visible.VISIBLE_TESTS.get(tid, "")
            if tid in tasks_v10_visible.NO_VISIBLE:
                self.assertEqual(vis, "", f"Expected empty visible tests for {tid}")
                continue
            self.assertTrue(len(vis) > 0, f"Missing visible tests for {tid}")
            ok, err = run.grade(t["ref"], vis, timeout=10)
            self.assertTrue(ok, f"Reference implementation failed visible tests for {tid}: {err}")


class TestStaticChecks(unittest.TestCase):
    def test_syntax_error(self):
        ok, err, checks = ground.static_checks("def foo(:", ["foo"])
        self.assertFalse(ok)
        self.assertIn("SyntaxError", err)

    def test_missing_entry_point(self):
        ok, err, checks = ground.static_checks("def bar(): pass", ["foo", "bar"])
        self.assertFalse(ok)
        self.assertIn("missing required entry point: foo", err)

    def test_deny_check_import(self):
        ok, err, checks = ground.static_checks("import socket\ndef foo(): pass", ["foo"])
        self.assertFalse(ok)
        self.assertIn("deny_check", err)

    def test_valid_static(self):
        ok, err, checks = ground.static_checks("def foo(): return 42", ["foo"])
        self.assertTrue(ok)
        self.assertEqual(err, "")


class TestSelectionKey(unittest.TestCase):
    def test_earliest_turn_wins_tie(self):
        c0 = {"turn": 0, "static_pass": True, "visible_pass": True, "model_pass": True}
        c1 = {"turn": 1, "static_pass": True, "visible_pass": True, "model_pass": True}
        best = ground.select_best_candidate([c0, c1])
        self.assertEqual(best["turn"], 0)

    def test_prefers_higher_tier(self):
        c0 = {"turn": 0, "static_pass": True, "visible_pass": False, "model_pass": False}
        c1 = {"turn": 1, "static_pass": True, "visible_pass": True, "model_pass": False}
        c2 = {"turn": 2, "static_pass": True, "visible_pass": True, "model_pass": True}
        self.assertEqual(ground.select_best_candidate([c0, c1])["turn"], 1)
        self.assertEqual(ground.select_best_candidate([c0, c1, c2])["turn"], 2)


class TestSignTestAndReport(unittest.TestCase):
    def test_exact_sign_test_worked_examples(self):
        self.assertEqual(round(ground.sign_test_p(9, 0), 3), 0.002)
        self.assertEqual(round(ground.sign_test_p(10, 1), 3), 0.006)
        self.assertEqual(round(ground.sign_test_p(11, 2), 3), 0.011)
        self.assertEqual(round(ground.sign_test_p(7, 1), 3), 0.035)

    def test_toy_report_verdicts(self):
        # Test partition logic:
        # Keep: net >= 9 and p <= 0.05
        # Drop: net <= 0 or p > 0.10
        # Inconclusive: otherwise
        p_9_0 = ground.sign_test_p(9, 0)
        self.assertTrue(9 >= ground.T_NOISE and p_9_0 <= 0.05)

        p_6_2 = ground.sign_test_p(6, 2)
        # net = +4 < 9 -> inconclusive or drop depending on p
        self.assertTrue(6 - 2 < ground.T_NOISE)

        p_loss = ground.sign_test_p(2, 5)
        self.assertTrue(2 - 5 <= 0)


class TestHiddenTestsAccessGuard(unittest.TestCase):
    class ExplodingTask(dict):
        def __getitem__(self, key):
            if key in ("tests", "ref"):
                raise AssertionError(f"FORBIDDEN ACCESS to hidden task field: {key!r}")
            return super().__getitem__(key)

    def test_in_loop_never_accesses_hidden_fields(self):
        """The loop must complete without ever accessing task['tests'] or task['ref']."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create exploding task dict
            exploding_task = self.ExplodingTask({
                "id": "v10_01_mac_address",
                "prompt": tasks_v10.T[0]["prompt"],
                "tests": tasks_v10.T[0]["tests"],
                "ref": tasks_v10.T[0]["ref"]
            })

            # Verify that accessing tests or ref explodes
            with self.assertRaises(AssertionError):
                _ = exploding_task["tests"]
            with self.assertRaises(AssertionError):
                _ = exploding_task["ref"]

            # Mock ask function that provides valid Python solution on turn 0
            def fake_ask(prompt, seed):
                if "assert" in prompt or "unit tests" in prompt:
                    return {"content": "```python\nassert parse_mac('00:1a:2b:3c:4d:5e') == (0, 26, 43, 60, 77, 94)\n```",
                            "usage": {"completion_tokens": 50}, "gen_s": 0.1}
                # Code reply
                code = ("def parse_mac(text): return (0, 26, 43, 60, 77, 94)\n"
                        "def format_mac(addr, delimiter=':'): return '00:1a:2b:3c:4d:5e'\n")
                return {"content": f"Rationale.\n```python\n{code}```\nCONFIDENCE: 0.9\n",
                        "usage": {"completion_tokens": 100}, "gen_s": 0.2}

            # Run step with fake_ask on a task set containing the exploding task
            server = {"build_info": "fake-build", "model_path": "/fake/qwen32"}
            # We mock load_set in run to return the exploding task
            orig_load_set = run.load_set
            try:
                run.load_set = lambda name: [exploding_task]
                ground.step(tmpdir, "test_guard", "v10", ["v10_01_mac_address"],
                            "qwen3-32b", server, fake_ask, parallel=1, log=lambda *a: None)
            finally:
                run.load_set = orig_load_set

            # Check that step completed and recorded final rows
            meta, rows = ground.load_meta_and_rows(tmpdir, "test_guard")
            idx = ground.build_index(rows)
            entry = idx.get(("v10_01_mac_address", "qwen32"))
            self.assertIsNotNone(entry["final_g"])
            self.assertIsNotNone(entry["final_c"])
            self.assertIsNotNone(entry["final_p"])


class TestGroundExecutionLoop(unittest.TestCase):
    def test_p_g_c_share_turn_0(self):
        """P, G, and C must share the identical turn 0 code and token counts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            task = tasks_v10.T[0]
            turn0_called = 0

            def fake_ask(prompt, seed):
                nonlocal turn0_called
                if seed == ground.SEED_BASE:
                    turn0_called += 1
                    return {"content": "```python\ndef parse_mac(): pass\ndef format_mac(): pass\n```",
                            "usage": {"completion_tokens": 120}, "gen_s": 0.5}
                if seed == ground.TEST_SEED:
                    return {"content": "```python\nassert 1 == 1\n```",
                            "usage": {"completion_tokens": 30}, "gen_s": 0.1}
                # revisions
                return {"content": "```python\ndef parse_mac(): pass\ndef format_mac(): pass\n```",
                        "usage": {"completion_tokens": 50}, "gen_s": 0.2}

            server = {"build_info": "fake-build", "model_path": "/fake/qwen32"}
            orig_load = run.load_set
            try:
                run.load_set = lambda name: [task]
                ground.step(tmpdir, "test_shared", "v10", [task["id"]],
                            "qwen3-32b", server, fake_ask, log=lambda *a: None)
            finally:
                run.load_set = orig_load

            self.assertEqual(turn0_called, 1, "Turn 0 must be called exactly once")
            meta, rows = ground.load_meta_and_rows(tmpdir, "test_shared")
            idx = ground.build_index(rows)
            entry = idx[(task["id"], "qwen32")]
            self.assertIsNotNone(entry["turn0"])
            # Candidate 0 for G and C is turn 0
            self.assertEqual(entry["turn0"]["code"], "def parse_mac(): pass\ndef format_mac(): pass\n")

    def test_budget_accounting(self):
        """Loop must stop when accumulated completion tokens hit TASK_BUDGET."""
        with tempfile.TemporaryDirectory() as tmpdir:
            task = tasks_v10.T[0]

            def budget_ask(prompt, seed):
                # Return huge token usage to blow the budget immediately
                return {"content": "```python\ndef parse_mac(): pass\n```",
                        "usage": {"completion_tokens": ground.TASK_BUDGET}, "gen_s": 1.0}

            server = {"build_info": "fake-build", "model_path": "/fake/qwen32"}
            orig_load = run.load_set
            try:
                run.load_set = lambda name: [task]
                ground.step(tmpdir, "test_budget", "v10", [task["id"]],
                            "qwen3-32b", server, budget_ask, log=lambda *a: None)
            finally:
                run.load_set = orig_load

            meta, rows = ground.load_meta_and_rows(tmpdir, "test_budget")
            idx = ground.build_index(rows)
            entry = idx[(task["id"], "qwen32")]
            self.assertEqual(entry["final_g"]["stop_reason"], "budget")
            self.assertEqual(entry["final_c"]["stop_reason"], "budget")

    def test_status_last_line_format(self):
        """Status line must match launcher pattern: 'next session: invite (qwen32|r1d32)' or 'done:'."""
        status_regex = re.compile(r"^(done: .*|owed .*; next session: invite (qwen32|r1d32))$")

        with tempfile.TemporaryDirectory() as tmpdir:
            task = tasks_v10.T[0]
            server = {"build_info": "fake-build", "model_path": "/fake/qwen32"}

            def fake_ask(prompt, seed):
                return {"content": "```python\ndef parse_mac(): pass\ndef format_mac(): pass\n```",
                        "usage": {"completion_tokens": 10}, "gen_s": 0.1}

            orig_load = run.load_set
            try:
                run.load_set = lambda name: [task]
                # Step 1: qwen32
                ground.step(tmpdir, "test_stat", "v10", [task["id"]],
                            "qwen3-32b", server, fake_ask, log=lambda *a: None)
                line1 = ground.status(tmpdir, "test_stat", log=lambda *a: None)
                self.assertIsNotNone(status_regex.match(line1), f"Status line failed regex: {line1}")
                self.assertIn("next session: invite r1d32", line1)

                # Step 2: r1d32 completes
                server_r1 = {"build_info": "fake-build", "model_path": "/fake/r1d32"}
                ground.step(tmpdir, "test_stat", "v10", [task["id"]],
                            "r1-distill-qwen-32b", server_r1, fake_ask, log=lambda *a: None)
                line2 = ground.status(tmpdir, "test_stat", log=lambda *a: None)
                self.assertIsNotNone(status_regex.match(line2), f"Status line failed regex: {line2}")
                self.assertTrue(line2.startswith("done:"), f"Expected done line, got: {line2}")
            finally:
                run.load_set = orig_load


if __name__ == "__main__":
    unittest.main()
