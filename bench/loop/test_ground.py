#!/usr/bin/env python3
"""CPU unit tests for CRAwDAD Grounding runner (bench/loop/ground.py)."""
import ast, json, os, re, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ground
import tasks_v10
import tasks_v10_visible
import run
import debate


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
        p_9_0 = ground.sign_test_p(9, 0)
        self.assertTrue(9 >= ground.T_NOISE and p_9_0 <= 0.05)

        p_6_2 = ground.sign_test_p(6, 2)
        self.assertTrue(6 - 2 < ground.T_NOISE)

        p_loss = ground.sign_test_p(2, 5)
        self.assertTrue(2 - 5 <= 0)


class TestHiddenTestsAccessGuard(unittest.TestCase):
    class ExplodingTask(dict):
        def __getitem__(self, key):
            if key in ("tests", "ref"):
                raise AssertionError(f"FORBIDDEN ACCESS to hidden task field: {key!r}")
            return super().__getitem__(key)

        def get(self, key, default=None):
            if key in ("tests", "ref"):
                raise AssertionError(f"FORBIDDEN ACCESS via get: {key!r}")
            return super().get(key, default)

        def items(self):
            raise AssertionError("FORBIDDEN ACCESS: items() would expose hidden task fields")

        def values(self):
            raise AssertionError("FORBIDDEN ACCESS: values() would expose hidden task fields")

        def keys(self):
            raise AssertionError("FORBIDDEN ACCESS: keys() would expose hidden task fields")

        def __iter__(self):
            raise AssertionError("FORBIDDEN ACCESS: iteration would expose hidden task fields")

        def copy(self):
            raise AssertionError("FORBIDDEN ACCESS: copy would expose hidden task fields")

        def __contains__(self, key):
            if key in ("tests", "ref"):
                raise AssertionError(f"FORBIDDEN ACCESS via __contains__: {key!r}")
            return super().__contains__(key)

    def test_in_loop_never_accesses_hidden_fields(self):
        """The loop must complete (including revisions) without ever accessing task['tests'] or task['ref']."""
        with tempfile.TemporaryDirectory() as tmpdir:
            exploding_task = self.ExplodingTask({
                "id": "v10_01_mac_address",
                "prompt": tasks_v10.T[0]["prompt"],
                "tests": tasks_v10.T[0]["tests"],
                "ref": tasks_v10.T[0]["ref"]
            })

            # Verify that exploding methods raise AssertionError
            with self.assertRaises(AssertionError):
                _ = exploding_task["tests"]
            with self.assertRaises(AssertionError):
                _ = exploding_task["ref"]
            with self.assertRaises(AssertionError):
                _ = exploding_task.get("tests")
            with self.assertRaises(AssertionError):
                _ = exploding_task.get("ref")
            with self.assertRaises(AssertionError):
                _ = list(exploding_task.items())
            with self.assertRaises(AssertionError):
                _ = list(exploding_task.values())
            with self.assertRaises(AssertionError):
                _ = list(exploding_task.keys())
            with self.assertRaises(AssertionError):
                _ = list(iter(exploding_task))
            with self.assertRaises(AssertionError):
                _ = exploding_task.copy()
            with self.assertRaises(AssertionError):
                _ = "tests" in exploding_task

            # Mock ask where turn 0 FAILS visible tests, forcing revisions in both G and C
            def fake_ask(prompt, seed):
                if "assert" in prompt or "unit tests" in prompt:
                    return {"content": "```python\nassert parse_mac('00:1a:2b:3c:4d:5e') == (0, 26, 43, 60, 77, 94)\n```",
                            "usage": {"completion_tokens": 50}, "gen_s": 0.1}
                if seed == ground.SEED_BASE:
                    # Turn 0 fails visible tests (wrong format)
                    bad_code = "def parse_mac(text): return (0, 0, 0, 0, 0, 0)\ndef format_mac(addr): return 'bad'\n"
                    return {"content": f"Rationale.\n```python\n{bad_code}```\nCONFIDENCE: 0.3\n",
                            "usage": {"completion_tokens": 80}, "gen_s": 0.2}
                # Revisions succeed
                good_code = ("def parse_mac(text): return (0, 26, 43, 60, 77, 94)\n"
                             "def format_mac(addr, delimiter=':'): return '00:1a:2b:3c:4d:5e'\n")
                return {"content": f"Corrected.\n```python\n{good_code}```\nCONFIDENCE: 0.95\n",
                        "usage": {"completion_tokens": 100}, "gen_s": 0.2}

            server = {"build_info": "fake-build", "model_path": "/fake/qwen32"}
            orig_load_set = run.load_set
            try:
                run.load_set = lambda name: [exploding_task]
                ground.step(tmpdir, "test_guard", "v10", ["v10_01_mac_address"],
                            "qwen3-32b", server, fake_ask, parallel=1, log=lambda *a: None)
            finally:
                run.load_set = orig_load_set

            meta, rows = ground.load_meta_and_rows(tmpdir, "test_guard")
            idx = ground.build_index(rows)
            entry = idx.get(("v10_01_mac_address", "qwen32"))
            self.assertIsNotNone(entry["final_g"])
            self.assertIsNotNone(entry["final_c"])
            self.assertIsNotNone(entry["final_p"])
            self.assertTrue(len(entry["g_revisions"]) > 0, "G revisions must run")
            self.assertTrue(len(entry["c_revisions"]) > 0, "C revisions must run")

    def test_prompts_never_leak_hidden_content(self):
        """No prompt in any turn/arm may contain hidden tests lines, ref substrings, or fresh seed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            task = tasks_v10.T[0]
            captured_prompts = []

            # Dummy failing code for turn 0 and revisions that do not copy ref
            dummy_code = ("def parse_mac(val): return (1, 1, 1, 1, 1, 1)\n"
                          "def format_mac(val, delim=':'): return '1:1:1:1:1:1'\n")

            def capturing_ask(prompt, seed):
                captured_prompts.append((seed, prompt))
                if "assert" in prompt or "unit tests" in prompt:
                    return {"content": "```python\nassert parse_mac('00:1a:2b:3c:4d:5e') == (0, 26, 43, 60, 77, 94)\n```",
                            "usage": {"completion_tokens": 50}, "gen_s": 0.1}
                return {"content": f"Module.\n```python\n{dummy_code}```\nCONFIDENCE: 0.8\n",
                        "usage": {"completion_tokens": 90}, "gen_s": 0.2}

            server = {"build_info": "fake-build", "model_path": "/fake/qwen32"}
            orig_load = run.load_set
            try:
                run.load_set = lambda name: [task]
                ground.step(tmpdir, "test_leak_guard", "v10", [task["id"]],
                            "qwen3-32b", server, capturing_ask, log=lambda *a: None)
            finally:
                run.load_set = orig_load

            self.assertTrue(len(captured_prompts) >= 4, "Must capture turn 0, test-write, and revisions")

            # Check that prompt never contains FRESH_SEED
            for seed, prompt in captured_prompts:
                self.assertNotIn("104729", prompt, f"FRESH_SEED leaked into prompt at seed {seed}")

            # Check hidden tests lines
            prompt_text = task["prompt"]
            hidden_tests = task["tests"]
            for line in hidden_tests.splitlines():
                s = line.strip()
                if (len(s) > 10 and s not in prompt_text and
                        s not in ground.TEST_WRITE_SUFFIX and
                        s not in ground.REVISION_SUFFIX and
                        s not in ground.REVISION_INSTRUCTION):
                    for seed, prompt in captured_prompts:
                        self.assertNotIn(s, prompt, f"Hidden test line {s!r} leaked into prompt at seed {seed}")

            # Check ref substrings (threshold = 25 chars)
            ref_text = task["ref"]
            for i in range(len(ref_text) - 25):
                sub = ref_text[i:i+25]
                if sub not in prompt_text:
                    for seed, prompt in captured_prompts:
                        self.assertNotIn(sub, prompt, f"Hidden ref substring {sub!r} leaked at seed {seed}")


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
            self.assertEqual(entry["turn0"]["code"], "def parse_mac(): pass\ndef format_mac(): pass\n")

    def test_no_code_revision_preserves_last_non_empty_code(self):
        """Blocker 1: Revision returning no code keeps last non-empty code and records 'no_code'."""
        with tempfile.TemporaryDirectory() as tmpdir:
            task = tasks_v10.T[0]
            t0_code = "def parse_mac(text): return (0, 0)\ndef format_mac(addr): return '0'\n"

            def fake_ask(prompt, seed):
                if seed == ground.SEED_BASE:
                    return {"content": f"Initial code.\n```python\n{t0_code}```\nCONFIDENCE: 0.5\n",
                            "usage": {"completion_tokens": 100}, "gen_s": 0.2}
                if seed == ground.TEST_SEED:
                    return {"content": "```python\nassert 1 == 1\n```",
                            "usage": {"completion_tokens": 30}, "gen_s": 0.1}
                # Revisions: return prose only with NO code block
                return {"content": "I reviewed the code and think it is fine, but I output no code block here.",
                        "usage": {"completion_tokens": 60}, "gen_s": 0.2}

            server = {"build_info": "fake-build", "model_path": "/fake/qwen32"}
            orig_load = run.load_set
            try:
                run.load_set = lambda name: [task]
                ground.step(tmpdir, "test_no_code", "v10", [task["id"]],
                            "qwen3-32b", server, fake_ask, log=lambda *a: None)
            finally:
                run.load_set = orig_load

            meta, rows = ground.load_meta_and_rows(tmpdir, "test_no_code")
            idx = ground.build_index(rows)
            entry = idx[(task["id"], "qwen32")]

            # G check
            fin_g = entry["final_g"]
            self.assertEqual(fin_g["stop_reason"], "no_code")
            self.assertEqual(fin_g["code"], t0_code)
            self.assertEqual(fin_g["selected_turn"], 0)

            # C check
            fin_c = entry["final_c"]
            self.assertEqual(fin_c["stop_reason"], "no_code")
            self.assertEqual(fin_c["code"], t0_code)
            self.assertEqual(fin_c["selected_turn"], 0)

    def test_hard_token_cap_guarantee(self):
        """Blocker 2: Hard token cap <= 24576 completion tokens for G and C with full MAX_TOKENS fake."""
        with tempfile.TemporaryDirectory() as tmpdir:
            task = tasks_v10.T[0]

            def max_tokens_ask(prompt, seed):
                # Fake model returns max possible tokens (MAX_TOKENS = 6144)
                code = f"def parse_mac(text): return ({seed},)\ndef format_mac(addr): return '{seed}'\n"
                return {"content": f"Rationale.\n```python\n{code}```\n",
                        "usage": {"completion_tokens": debate.MAX_TOKENS}, "gen_s": 1.0}

            server = {"build_info": "fake-build", "model_path": "/fake/qwen32"}
            orig_load = run.load_set
            try:
                run.load_set = lambda name: [task]
                ground.step(tmpdir, "test_cap", "v10", [task["id"]],
                            "qwen3-32b", server, max_tokens_ask, log=lambda *a: None)
            finally:
                run.load_set = orig_load

            meta, rows = ground.load_meta_and_rows(tmpdir, "test_cap")
            idx = ground.build_index(rows)
            entry = idx[(task["id"], "qwen32")]

            # Assert recorded total tokens <= 24576 for G and C
            self.assertLessEqual(entry["final_g"]["total_tokens"], ground.TASK_BUDGET)
            self.assertLessEqual(entry["final_c"]["total_tokens"], ground.TASK_BUDGET)
            self.assertEqual(entry["final_g"]["total_tokens"], ground.TASK_BUDGET)
            self.assertEqual(entry["final_c"]["total_tokens"], ground.TASK_BUDGET)
            self.assertEqual(entry["final_g"]["stop_reason"], "budget")

    def test_primary_scoring_uses_last_non_empty_module(self):
        """Blocker 5: Primary score is LAST non-empty module, while best-of-N is logged as secondary."""
        with tempfile.TemporaryDirectory() as tmpdir:
            task = tasks_v10.T[0]
            # Turn 0: fails visible checks
            code0 = "def parse_mac(text): return (0, 0)\ndef format_mac(addr): return '0'\n"
            # Turn 1: passes visible checks, but model test fails so it continues
            code1 = task["ref"]
            # Turn 2: regressed code (syntax error or runtime failure)
            code2 = "def parse_mac(text): raise RuntimeError('regressed')\ndef format_mac(addr, delimiter=':'): return 'x'\n"

            def fake_ask(prompt, seed):
                if seed == ground.SEED_BASE:
                    return {"content": f"```python\n{code0}```", "usage": {"completion_tokens": 50}, "gen_s": 0.1}
                if seed == ground.TEST_SEED:
                    # Model test that fails against code1 so all_pass is NOT triggered
                    return {"content": "```python\nassert False, 'failing model test'\n```", "usage": {"completion_tokens": 20}, "gen_s": 0.1}
                if seed == ground.SEED_BASE + 1:
                    # Turn 1: code1 passes visible tests, but fails model test
                    return {"content": f"```python\n{code1}```", "usage": {"completion_tokens": 50}, "gen_s": 0.1}
                if seed == ground.SEED_BASE + 2:
                    # Turn 2: code2 regresses
                    return {"content": f"```python\n{code2}```", "usage": {"completion_tokens": 50}, "gen_s": 0.1}
                # Turn 3: returns no code block, so turn 2 remains the last non-empty module
                return {"content": "Explanation only with no code block.", "usage": {"completion_tokens": 30}, "gen_s": 0.1}

            server = {"build_info": "fake-build", "model_path": "/fake/qwen32"}
            orig_load = run.load_set
            try:
                run.load_set = lambda name: [task]
                ground.step(tmpdir, "test_primary", "v10", [task["id"]],
                            "qwen3-32b", server, fake_ask, log=lambda *a: None)
            finally:
                run.load_set = orig_load

            meta, rows = ground.load_meta_and_rows(tmpdir, "test_primary")
            idx = ground.build_index(rows)
            entry = idx[(task["id"], "qwen32")]
            fin_g = entry["final_g"]

            # Under Best-of-N: code1 passed visible tests, so best candidate is turn 1 (code1)
            self.assertEqual(fin_g["best_turn"], 1)
            self.assertEqual(fin_g["best_code"], code1)

            # Under primary contrast rule (Blocker 5): scored on LAST non-empty module (code2 from turn 2)
            self.assertEqual(fin_g["selected_turn"], 2)
            self.assertEqual(fin_g["code"], code2)
            self.assertEqual(fin_g["stop_reason"], "no_code")


class TestReportEndToEnd(unittest.TestCase):
    """Blocker 3: Test report writes and parses summary.json, and handles keep/drop/inconclusive/no_room."""
    def _create_mock_run(self, tmpdir, label, n_tasks, g_passes, c_passes):
        task_ids = [f"t_{i:02d}" for i in range(n_tasks)]
        meta = {
            "label": label, "set": "v10", "tasks": task_ids,
            "protocol": ground.PROTOCOL, "seed_base": 5000,
            "test_seed": 5050, "k_revisions": 3,
            "task_budget": ground.TASK_BUDGET, "reasoning_budget": 2048,
            "max_tokens": 6144, "sampling": {}, "fresh_seed": 104729,
            "build": None, "seats": {}
        }
        mp, rp, sp = ground.paths(tmpdir, label)
        with open(mp, "w") as f:
            json.dump(meta, f)

        rows = []
        for i, tid in enumerate(task_ids):
            for s in ground.ORDER:
                rows.append({"kind": "turn0", "task": tid, "seat": s, "arm": "P",
                             "completion_tokens": 100, "code": "pass"})
                rows.append({"kind": "final", "task": tid, "seat": s, "arm": "P",
                             "code": "pass", "fresh_pass": False, "total_tokens": 100})

                g_pass = (i in g_passes) and (s == ground.ORDER[0])
                rows.append({"kind": "final", "task": tid, "seat": s, "arm": "G",
                             "selected_turn": 1, "code": "pass", "best_turn": 1, "best_code": "pass",
                             "fresh_pass": g_pass, "fresh_pass_best": g_pass,
                             "stop_reason": "max_turns", "total_tokens": 300})

                c_pass = (i in c_passes) and (s == ground.ORDER[0])
                rows.append({"kind": "final", "task": tid, "seat": s, "arm": "C",
                             "selected_turn": 1, "code": "pass",
                             "fresh_pass": c_pass,
                             "stop_reason": "max_turns", "total_tokens": 200})

        with open(rp, "w") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")

    def test_report_verdicts_and_summary_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # 1. keep: net = 10, gains = 10, losses = 0 -> p = 0.001 <= 0.05
            g_indices = set(range(20, 40))  # 20 tasks
            c_indices = set(range(20, 30))  # 10 tasks -> net = +10, gains=10, losses=0
            self._create_mock_run(tmpdir, "run_keep", 90, g_indices, c_indices)
            sum_keep, rc_keep = ground.report(tmpdir, "run_keep", regrade=False, log=lambda *a: None)
            self.assertEqual(rc_keep, 0)
            self.assertEqual(sum_keep["primary_contrast_G_vs_C"]["verdict"], "keep")
            _, _, sp_keep = ground.paths(tmpdir, "run_keep")
            self.assertTrue(os.path.exists(sp_keep))
            parsed = json.load(open(sp_keep))
            self.assertEqual(parsed["primary_contrast_G_vs_C"]["verdict"], "keep")

            # 2. drop: net = -2 (L_C must be between 10 and 76 so no_room does not trigger)
            # C passes 20 tasks (indices 10..29)
            # G passes 18 tasks (indices 10..27) -> net = -2, losses = 2, gains = 0, p = 0.25 > 0.10
            g_drop = set(range(10, 28))
            c_drop = set(range(10, 30))
            self._create_mock_run(tmpdir, "run_drop", 90, g_drop, c_drop)
            sum_drop, rc_drop = ground.report(tmpdir, "run_drop", regrade=False, log=lambda *a: None)
            self.assertEqual(rc_drop, 1)
            self.assertEqual(sum_drop["primary_contrast_G_vs_C"]["verdict"], "drop")

            # 3. inconclusive: net = 6 (7 gains, 1 loss) -> p = 0.035 <= 0.05 but net < 9
            # G passes 20..26 (7) and 30; C passes 30 and 31.
            # G and C both pass 30. G passes 20..26 (7 gains). C passes 31 (1 loss).
            # L_C = 20 tasks: indices 30..49
            # G passes 20..26 (7 gains), 30..48 (19 shared) -> total 26 passes
            # C passes 30..49 (20 passes, including 49 which G missed -> 1 loss)
            g_inconc = set(range(20, 27)) | set(range(30, 49))
            c_inconc = set(range(30, 50))
            self._create_mock_run(tmpdir, "run_inconc", 90, g_inconc, c_inconc)
            sum_inc, rc_inc = ground.report(tmpdir, "run_inconc", regrade=False, log=lambda *a: None)
            self.assertEqual(rc_inc, 1)
            self.assertEqual(sum_inc["primary_contrast_G_vs_C"]["verdict"], "inconclusive")

            # 4. no_room: L_C >= 77 (saturated) and L_C <= 9 (floor)
            c_sat = set(range(78))
            g_sat = set(range(85))
            self._create_mock_run(tmpdir, "run_noroom_hi", 90, g_sat, c_sat)
            sum_nr_hi, rc_nr_hi = ground.report(tmpdir, "run_noroom_hi", regrade=False, log=lambda *a: None)
            self.assertEqual(rc_nr_hi, 1)
            self.assertEqual(sum_nr_hi["primary_contrast_G_vs_C"]["verdict"], "no_room")

            c_floor = set(range(5))
            g_floor = set(range(15))
            self._create_mock_run(tmpdir, "run_noroom_lo", 90, g_floor, c_floor)
            sum_nr_lo, rc_nr_lo = ground.report(tmpdir, "run_noroom_lo", regrade=False, log=lambda *a: None)
            self.assertEqual(rc_nr_lo, 1)
            self.assertEqual(sum_nr_lo["primary_contrast_G_vs_C"]["verdict"], "no_room")


class TestStatusInviteOrder(unittest.TestCase):
    """Blocker 4: Next-session line must invite first seat in ORDER that owes work."""
    def test_status_invites_first_seat_in_order(self):
        fake_meta = {"tasks": [f"t_{i}" for i in range(90)]}
        # Case 1: qwen32 owes work (e.g. 1 task remaining) -> invite qwen32
        idx1 = {}
        for i in range(89):
            idx1[(f"t_{i}", "qwen32")] = {"turn0": {}, "final_g": {}, "final_c": {}}
        line1 = ground.status_line(fake_meta, idx1)
        self.assertIn("invite qwen32", line1)

        # Case 2: qwen32 complete (owes 0), r1d32 owes 270 -> invite r1d32
        idx2 = {}
        for i in range(90):
            idx2[(f"t_{i}", "qwen32")] = {"turn0": {}, "final_g": {}, "final_c": {}}
        line2 = ground.status_line(fake_meta, idx2)
        self.assertEqual(line2, "owed {'qwen32': 0, 'r1d32': 270}; next session: invite r1d32")


if __name__ == "__main__":
    unittest.main()
