#!/usr/bin/env python3
"""CPU-only unit tests for Item 6 Pilot v4:
(a) turn_events telemetry (reasoning_chars, content_chars, finish_reason, repeat_code matched_turn/hash,
    truncated parse-error raw_snippet, and repeat_code compaction retention),
(b) Fix rank 1 (pressure-gated Stage 1 compaction + read-only repeat_code tolerance with bounded loop safeguard),
(c) Fix rank 2 (robust JSON tool-call parsing tested against the 7 logged frozen v3 parse-error cases + synthetics),
(d) Fix rank 3 (prompt run_tests instruction + end-of-loop auto-run kept distinct from stop_reason='pass'),
(e) Fix rank 4 (TOOL_RESULT_MAX_LINES == READ_FILE_MAX_LINES == 250 matching prompt),
(f) Unseen v4 task selection (select_v4.py -> exact frozen 7-PR lark-parser/lark list, bwrap fail@base/pass@merged,
    rule-built prompts, leak guards, Section 18 table integrity),
(g) v4 practice & counted launchers and run/grade plumbing.
"""
from datetime import datetime, timezone
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import pilot_pr  # noqa: E402
import select_v4  # noqa: E402
import tasks_item6  # noqa: E402
import tasks_item6_v3  # noqa: E402
import tasks_item6_v4  # noqa: E402


class ExplodingTaskDict(dict):
    """Tripwire dictionary that raises immediately if hidden keys are accessed in-loop."""

    def __getitem__(self, key):
        if key in ("hidden_diff", "merged_commit", "hidden_sentinel"):
            raise AssertionError(f"LEAK TRIPWIRE TRIGGERED: In-loop access to '{key}'!")
        return super().__getitem__(key)

    def get(self, key, default=None):
        if key in ("hidden_diff", "merged_commit", "hidden_sentinel"):
            raise AssertionError(f"LEAK TRIPWIRE TRIGGERED: In-loop get() for '{key}'!")
        return super().get(key, default)


def _make_git_scratch(py_src="def compute():\n    return 0\n", test_src="import mod\nassert mod.compute() == 42\n"):
    """Create a tiny standalone git scratch repo for CPU loop tests."""
    temp_dir = tempfile.mkdtemp(prefix="pilot_v4_wt_")
    subprocess.run(["git", "init", "-q"], cwd=temp_dir, check=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=temp_dir, check=True)
    subprocess.run(["git", "config", "user.email", "tester@example.org"], cwd=temp_dir, check=True)
    with open(os.path.join(temp_dir, "mod.py"), "w", encoding="utf-8") as f:
        f.write(py_src)
    with open(os.path.join(temp_dir, "test_mod.py"), "w", encoding="utf-8") as f:
        f.write(test_src)
    subprocess.run(["git", "add", "."], cwd=temp_dir, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "base"], cwd=temp_dir, check=True)
    base_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=temp_dir, text=True).strip()
    return temp_dir, base_sha


def _legacy_v3_extract_tool_calls(response_text):
    """Exact copy of v3 extract_tool_calls (json.loads only) to prove v3 error-class parity."""
    calls = []
    parse_errors = []
    text = response_text or ""
    blocks = re.findall(r"```(?:tool|json)\s*\n(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if not blocks:
        stripped = text.strip()
        if stripped.startswith("{") or stripped.startswith("["):
            blocks = [stripped]
    for blk in blocks:
        blk_s = blk.strip()
        if not blk_s:
            continue
        try:
            parsed = json.loads(blk_s)
        except json.JSONDecodeError as e:
            parse_errors.append(f"Invalid JSON in tool block: {e}")
            continue
        items = parsed if isinstance(parsed, list) else [parsed]
        for item in items:
            norm = pilot_pr._normalize_tool_call_obj(item)
            if norm is not None:
                calls.append(norm)
            else:
                parse_errors.append(f"JSON object is not a valid tool call (missing 'tool' name): {str(item)[:160]}")
    return calls, parse_errors


class TestPilotPrV4(unittest.TestCase):

    # ------------------------------------------------------------------
    # (a) Required telemetry in turn_events & history
    # ------------------------------------------------------------------
    def test_v4_telemetry_all_turn_types_repeat_code_and_parse_error(self):
        """Every reply turn logs reasoning_chars, content_chars, finish_reason; repeat_code logs matched_turn+reply_hash; parse_error logs raw_snippet."""
        wt_dir, base_sha = _make_git_scratch()
        run_dir = tempfile.mkdtemp(prefix="pilot_v4_tel_run_")
        try:
            task = {
                "id": "v4_tel_task",
                "pr_number": 951,
                "title": "Telemetry test",
                "base_commit": base_sha,
                "merged_commit": "b" * 40,
                "has_tests": True,
                "test_cmd": "python3 test_mod.py",
                "prompt": "Fix compute() in mod.py.",
                "files": ["mod.py"],
            }
            turn_i = [0]
            bad_long_reply = "```json\n" + ('{"tool": "search_replace", "args": {"old": "x" "y": "' + ("Z" * 800) + '"}}\n') + "```"
            edit_reply = '```json\n{"tool": "search_replace", "args": {"path": "mod.py", "old": "nonexistent", "new": "x"}}\n```'
            expected_repeat_hash = hashlib.sha256(edit_reply.encode("utf-8")).hexdigest()

            # Verify _truncate_raw_snippet redacts literal grading seed and caps length
            redacted_snip = pilot_pr._truncate_raw_snippet("bad 104729 " + ("Q" * 800))
            self.assertNotIn("104729", redacted_snip)
            self.assertIn("<REDACTED_SEED>", redacted_snip)
            self.assertIn("truncated", redacted_snip)

            def mock_ask(messages, seed):
                t = turn_i[0]
                turn_i[0] += 1
                if t == 0:
                    # Valid read_file turn
                    txt = '```json\n{"tool": "read_file", "args": {"path": "mod.py", "start": 1, "end": 10}}\n```'
                    return {"content": txt, "reasoning_chars": 321, "finish_reason": "stop", "usage": {"prompt_tokens": 500, "completion_tokens": 45}}
                if t == 1:
                    # Unparseable broken JSON -> turn_parse_error with raw_snippet (seed redacted & truncated)
                    return {"content": bad_long_reply, "reasoning_chars": 111, "finish_reason": "length", "usage": {"prompt_tokens": 600, "completion_tokens": 90}}
                if t == 2:
                    # Non-read-only edit attempt (first occurrence -> turn 2)
                    return {"content": edit_reply, "reasoning_chars": 222, "finish_reason": "stop", "usage": {"prompt_tokens": 700, "completion_tokens": 55}}
                # Turn 3: exact duplicate of turn 2 edit -> repeat_code hard-stop
                return {"content": edit_reply, "reasoning_chars": 444, "finish_reason": "stop", "usage": {"prompt_tokens": 750, "completion_tokens": 60}}

            res = pilot_pr.run_task_loop(
                task, mock_ask, wt_dir, max_turns=6, run_dir=run_dir, label="v4-tel", token_counter=lambda m: 500
            )
            self.assertEqual(res["stop_reason"], "repeat_code")
            self.assertEqual(res["turns_executed"], 4)

            # Check history[turn] fields
            h0, h1, h2, h3 = res["history"]
            self.assertEqual(h0["reasoning_chars"], 321)
            self.assertEqual(h0["finish_reason"], "stop")
            self.assertGreater(h0["content_chars"], 20)
            self.assertEqual(h1["reasoning_chars"], 111)
            self.assertEqual(h1["finish_reason"], "length")
            self.assertIn("raw_snippet", h1)
            self.assertNotIn("104729", h1["raw_snippet"])
            self.assertEqual(h3["matched_turn"], 2)
            self.assertEqual(h3["reply_hash"], expected_repeat_hash)
            self.assertEqual(h3["reasoning_chars"], 444)
            self.assertEqual(h3["content_chars"], len(edit_reply))
            self.assertEqual(h3["finish_reason"], "stop")
            self.assertIn("compaction", h3)

            # Check turn_events.jsonl
            with open(os.path.join(run_dir, "turn_events.jsonl"), encoding="utf-8") as ef:
                events = [json.loads(ln) for ln in ef if ln.strip()]
            reply_evs = [e for e in events if e["event"] in ("turn_tools", "turn_parse_error", "turn_repeat_code")]
            self.assertEqual(len(reply_evs), 4)
            for ev in reply_evs:
                self.assertIn("reasoning_chars", ev)
                self.assertIn("content_chars", ev)
                self.assertIn("finish_reason", ev)

            pe_ev = next(e for e in reply_evs if e["event"] == "turn_parse_error")
            self.assertEqual(pe_ev["turn"], 1)
            self.assertEqual(pe_ev["reasoning_chars"], 111)
            self.assertEqual(pe_ev["content_chars"], len(bad_long_reply))
            self.assertEqual(pe_ev["finish_reason"], "length")
            self.assertIn("raw_snippet", pe_ev)
            self.assertIn("truncated", pe_ev["raw_snippet"])
            self.assertNotIn("104729", pe_ev["raw_snippet"])
            self.assertLessEqual(len(pe_ev["raw_snippet"]), pilot_pr.PARSE_ERROR_RAW_SNIPPET_MAX_CHARS + 64)

            rc_ev = next(e for e in reply_evs if e["event"] == "turn_repeat_code")
            self.assertEqual(rc_ev["turn"], 3)
            self.assertEqual(rc_ev["matched_turn"], 2)
            self.assertEqual(rc_ev["reply_hash"], expected_repeat_hash)
            self.assertEqual(rc_ev["reasoning_chars"], 444)
            self.assertEqual(rc_ev["content_chars"], len(edit_reply))
            self.assertEqual(rc_ev["finish_reason"], "stop")
            self.assertFalse(rc_ev["repeat_read_only"])
        finally:
            shutil.rmtree(wt_dir, ignore_errors=True)
            shutil.rmtree(run_dir, ignore_errors=True)

    # ------------------------------------------------------------------
    # (b) Fix rank 1: Pressure-gated Stage 1 compaction & read-only repeat_code
    # ------------------------------------------------------------------
    def test_fix_rank1_stage1_compaction_gated_on_token_pressure(self):
        """Stage 1 stale_tool_summary stays dormant below 50% of max_prompt_tokens (28,672 at 57,344) and fires above it."""
        self.assertEqual(pilot_pr.COMPACT_STAGE1_TRIGGER_RATIO, 0.50)
        old_tool_body = "Tool results:\n[1] read_file OK:\n" + "\n".join(f"{i:4d}: line_content_{i}" for i in range(90))
        msgs = [
            {"role": "system", "content": "SYS"},
            {"role": "user", "content": "TASK"},
            {"role": "assistant", "content": "a0"},
            {"role": "user", "content": old_tool_body},
            {"role": "assistant", "content": "a1"},
            {"role": "user", "content": "Tool results:\n[1] read_file OK:\nrecent1"},
            {"role": "assistant", "content": "a2"},
            {"role": "user", "content": "Tool results:\n[1] read_file OK:\nrecent2"},
        ]
        meta = [{}, {}, {"turn": 0, "tools": []}, {"turn": 0, "tools": [{"tool": "read_file", "args": {"path": "a.py"}, "ok": True, "result_chars": len(old_tool_body)}]},
                {"turn": 1, "tools": []}, {"turn": 1, "tools": []}, {"turn": 2, "tools": []}, {"turn": 2, "tools": []}]

        # At 5,905 tokens (v3 peak) vs 57,344 max (threshold 28,672): NO compaction
        kept_msgs, _, ev_low = pilot_pr.compact_conversation_messages(
            msgs, slot_ctx=65536, reserved_output=8192, token_counter=lambda m: 5905, msg_meta=meta
        )
        self.assertFalse(ev_low["compacted"])
        self.assertEqual(ev_low["stage1_trigger_tokens"], 28672)
        self.assertEqual(kept_msgs[3]["content"], old_tool_body)

        # Exactly at threshold (28,672): still NO compaction
        _, _, ev_at = pilot_pr.compact_conversation_messages(
            msgs, slot_ctx=65536, reserved_output=8192, token_counter=lambda m: 28672, msg_meta=meta
        )
        self.assertFalse(ev_at["compacted"])

        # Strictly above threshold (28,673): Stage 1 fires and compacts turn 0 while keeping recent2
        comp_msgs, _, ev_hi = pilot_pr.compact_conversation_messages(
            msgs, slot_ctx=65536, reserved_output=8192, token_counter=lambda m: 28673 if "line_content_0" in m[3]["content"] else 20000, msg_meta=meta
        )
        self.assertTrue(ev_hi["compacted"])
        self.assertIn("stale_tool_summary", ev_hi["stages"])
        self.assertTrue(comp_msgs[3]["content"].startswith("[compacted stale tool output from turn 0"))
        self.assertEqual(comp_msgs[7]["content"], "Tool results:\n[1] read_file OK:\nrecent2")

    def test_fix_rank1_readonly_repeat_allowed_once_but_bounded_against_infinite_loop(self):
        """Single read-only repeat (read_file/grep) does not hard-stop; consecutive/total caps still stop true loops."""
        wt_dir, base_sha = _make_git_scratch()
        run_dir = tempfile.mkdtemp(prefix="pilot_v4_ro_rep_")
        try:
            task = {
                "id": "v4_ro_task",
                "pr_number": 952,
                "title": "Read-only repeat test",
                "base_commit": base_sha,
                "merged_commit": "c" * 40,
                "has_tests": True,
                "test_cmd": "python3 test_mod.py",
                "prompt": "Fix compute().",
                "files": ["mod.py"],
            }
            read_reply = '```json\n{"tool": "read_file", "args": {"path": "mod.py", "start": 1, "end": 10}}\n```'
            grep_reply = '```json\n{"tool": "grep", "args": {"pattern": "compute", "path": "mod.py"}}\n```'

            # Case 1: Model repeats read_file once on turn 1, gets reminder, then edits + run_tests + finish -> PASS
            t_idx = [0]
            def ask_recover_after_ro_repeat(messages, seed):
                t = t_idx[0]
                t_idx[0] += 1
                if t in (0, 1):
                    return {"content": read_reply, "reasoning_chars": 10, "finish_reason": "stop", "usage": {"completion_tokens": 25}}
                # Turn 2: confirm reminder was delivered
                self.assertIn("identical read-only call on turn 0", messages[-1]["content"])
                calls = [
                    {"tool": "search_replace", "args": {"path": "mod.py", "old": "return 0", "new": "return 42"}},
                    {"tool": "run_tests", "args": {}},
                    {"tool": "finish", "args": {"summary": "fixed"}},
                ]
                return {"content": "```json\n" + json.dumps(calls) + "\n```", "reasoning_chars": 20, "finish_reason": "stop", "usage": {"completion_tokens": 40}}

            res1 = pilot_pr.run_task_loop(task, ask_recover_after_ro_repeat, wt_dir, max_turns=6, run_dir=run_dir, label="ro-ok", token_counter=lambda m: 500)
            self.assertTrue(res1["passed"])
            self.assertEqual(res1["stop_reason"], "pass")
            self.assertEqual(res1["turns_executed"], 3)

            # Reset scratch file for Case 2
            subprocess.run(["git", "checkout", "--", "mod.py"], cwd=wt_dir, check=True)

            # Case 2: Infinite read-only loop (turn 0 read, turn 1 repeat #1 allowed, turn 2 repeat #2 consecutive -> hard-stop repeat_code!)
            def ask_infinite_ro(messages, seed):
                return {"content": grep_reply, "reasoning_chars": 5, "finish_reason": "stop", "usage": {"completion_tokens": 20}}

            res2 = pilot_pr.run_task_loop(task, ask_infinite_ro, wt_dir, max_turns=10, run_dir=run_dir, label="ro-loop", token_counter=lambda m: 500)
            self.assertFalse(res2["passed"])
            self.assertEqual(res2["stop_reason"], "repeat_code")
            self.assertEqual(res2["turns_executed"], 3)  # t=0 original, t=1 allowed repeat, t=2 bounded hard-stop
            self.assertEqual(res2["history"][-1]["matched_turn"], 0)
            self.assertTrue(res2["history"][-1]["repeat_read_only"])

            # Case 3: Non-consecutive read-only repeats bounded by MAX_TOTAL_READ_ONLY_REPEATS (= 3)
            t3 = [0]
            def ask_spaced_ro_repeats(messages, seed):
                t = t3[0]
                t3[0] += 1
                seq = [
                    read_reply,  # t=0 new
                    grep_reply,  # t=1 new
                    read_reply,  # t=2 repeat #1 (total=1, consec=1 -> allowed)
                    '```json\n{"tool": "list_files", "args": {"path": "."}}\n```',  # t=3 new (consec reset)
                    grep_reply,  # t=4 repeat #2 (total=2, consec=1 -> allowed)
                    '```json\n{"tool": "read_file", "args": {"path": "test_mod.py", "start": 1, "end": 5}}\n```',  # t=5 new
                    read_reply,  # t=6 repeat #3 (total=3 == MAX_TOTAL_READ_ONLY_REPEATS -> hard-stop!)
                ]
                return {"content": seq[min(t, len(seq) - 1)], "reasoning_chars": 5, "finish_reason": "stop", "usage": {"completion_tokens": 20}}

            res3 = pilot_pr.run_task_loop(task, ask_spaced_ro_repeats, wt_dir, max_turns=10, run_dir=run_dir, label="ro-cap", token_counter=lambda m: 500)
            self.assertEqual(res3["stop_reason"], "repeat_code")
            self.assertEqual(res3["turns_executed"], 7)
            self.assertEqual(res3["history"][-1]["matched_turn"], 0)
        finally:
            shutil.rmtree(wt_dir, ignore_errors=True)
            shutil.rmtree(run_dir, ignore_errors=True)

    # ------------------------------------------------------------------
    # (c) Fix rank 2: Robust JSON parsing on 7 frozen v3 parse-error cases + synthetics
    # ------------------------------------------------------------------
    def test_fix_rank2_robust_json_parser_on_seven_logged_v3_cases_and_synthetics(self):
        """Read the 7 logged v3 parse-error cases from frozen v3 logs (read-only) and test v4 parser + synthetics."""
        # 1. Read-only audit of all 7 logged parse errors from frozen v3 JSONL
        repo_root = os.path.abspath(os.path.join(HERE, "..", ".."))
        frozen_candidates = [
            "/tmp/lab-seats/item6-v3-frozen/item6-pilot-v3.jsonl",
            os.path.join(repo_root, "bench", "loop", "results", "item6-pilot-v3.jsonl"),
        ]
        v3_jsonl = next((p for p in frozen_candidates if os.path.isfile(p)), None)
        self.assertIsNotNone(v3_jsonl, "Frozen v3 JSONL not found")

        logged_v3_errors = []
        with open(v3_jsonl, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                row = json.loads(line)
                for h in row.get("history") or []:
                    if h.get("tool_calls") == [] and h.get("err"):
                        logged_v3_errors.append((row["task_id"], h["turn"], h["err"]))
        self.assertEqual(len(logged_v3_errors), 7)

        # Reconstruct concrete representative payloads matching all 7 logged v3 error classes
        # (v3 did not persist raw model text; each fixture is verified to reproduce the exact v3 error class
        # under _legacy_v3_extract_tool_calls).
        v3_case_fixtures = [
            # 1. item6v3_pr1269 turn 7: Expecting ',' delimiter (missing comma between objects in array at >1500 chars)
            (
                "item6v3_pr1269", 7, "Expecting ',' delimiter", True,
                '```json\n[{"tool": "search_replace", "args": {"path": "more_itertools/more.py", "old": "' + ("a" * 700) + '", "new": "' + ("b" * 750) + '"}} {"tool": "run_tests", "args": {}}]\n```',
                2,
            ),
            # 2. item6v3_pr1305 turn 0: Extra data: line 2 column 1 (NDJSON multi-object in one fenced block)
            (
                "item6v3_pr1305", 0, "Extra data: line 2 column 1", True,
                '```json\n{"tool": "read_file", "args": {"path": "more_itertools/more.py", "start": 1, "end": 100}}\n{"tool": "grep", "args": {"pattern": "def ichunked", "path": "more_itertools/more.py"}}\n```',
                2,
            ),
            # 3. item6v3_pr1305 turn 2: Extra data: line 2 column 1 (NDJSON second occurrence)
            (
                "item6v3_pr1305", 2, "Extra data: line 2 column 1", True,
                '```json\n{"tool": "grep", "args": {"pattern": "def chunked", "path": "more_itertools/more.py"}}\n{"tool": "read_file", "args": {"path": "more_itertools/more.py", "start": 215, "end": 250}}\n```',
                2,
            ),
            # 4. item6v3_pr1305 turn 3: No valid tool calls found (leading/trailing prose around unfenced JSON)
            (
                "item6v3_pr1305", 3, "No valid tool calls", True,
                'Let me inspect ichunked next:\n{"tool": "read_file", "args": {"path": "more_itertools/more.py", "start": 3700, "end": 3760}}\nThanks.',
                1,
            ),
            # 5. item6v3_pr1322 turn 2: Expecting value: line 1 column 1 (prose/comment before JSON inside ```json fence)
            (
                "item6v3_pr1322", 2, "Expecting value: line 1 column 1", True,
                '```json\n// inspect peekable\n{"tool": "read_file", "args": {"path": "more_itertools/more.py", "start": 100, "end": 150}}\n```',
                1,
            ),
            # 6. item6v3_pr1322 turn 3: No valid tool calls found (bare ``` fence without json tag)
            (
                "item6v3_pr1322", 3, "No valid tool calls", True,
                '```\n{"tool": "grep", "args": {"pattern": "class peekable", "path": "more_itertools/more.py"}}\n```',
                1,
            ),
            # 7. item6v3_pr1345 turn 7: Expecting ',' delimiter (corrupted unescaped quote inside single-line JSON string -> must NOT mangle)
            (
                "item6v3_pr1345", 7, "Expecting ',' delimiter", False,
                '```json\n{"tool": "search_replace", "args": {"path": "more_itertools/more.py", "old": "' + ("x" * 1550) + '", "new": "a = "broken""}}\n```',
                0,
            ),
        ]

        self.assertEqual([(t, tn) for t, tn, _ in logged_v3_errors], [(t, tn) for t, tn, *_ in v3_case_fixtures])
        for (tid, tn, logged_err), (_, _, err_substr, should_recover, payload, exp_count) in zip(logged_v3_errors, v3_case_fixtures):
            self.assertIn(err_substr, logged_err, f"Logged v3 error mismatch for {tid} t={tn}")
            # Confirm old v3 parser fails on every single one of these 7 cases
            old_calls, old_errs = _legacy_v3_extract_tool_calls(payload)
            self.assertEqual(old_calls, [], f"Expected legacy v3 parser to fail on {tid} t={tn}")
            if err_substr != "No valid tool calls":
                self.assertTrue(any(err_substr in e for e in old_errs), f"Legacy err {old_errs} missing {err_substr}")

            # Confirm v4 parser recovers all 6 recoverable cases and safely rejects genuinely corrupted JSON (#7)
            new_calls, new_errs = pilot_pr.extract_tool_calls(payload)
            if should_recover:
                self.assertEqual(len(new_calls), exp_count, f"v4 parser failed to recover {tid} t={tn}: errs={new_errs}")
            else:
                self.assertEqual(new_calls, [], f"v4 parser must not silently mangle broken quote in {tid} t={tn}")
                self.assertTrue(len(new_errs) >= 1)

        # 2. Synthetic edge cases
        # 2a. Trailing commas in object & array (while preserving commas inside string values!)
        tc_payload = (
            "Here is the edit:\n"
            "```json\n"
            "[\n"
            '  {"tool": "search_replace", "args": {"path": "a.py", "old": "d = {1: 2,}", "new": "d = [1, 2,]",},},\n'
            '  {"tool": "run_tests", "args": {},},\n'
            "]\n"
            "```\n"
            "Let me know the test result."
        )
        calls, errs = pilot_pr.extract_tool_calls(tc_payload)
        self.assertEqual(errs, [])
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0]["args"]["old"], "d = {1: 2,}")
        self.assertEqual(calls[0]["args"]["new"], "d = [1, 2,]")
        self.assertEqual(calls[1]["tool"], "run_tests")

        # 2b. Unclosed trailing ```json fence
        unclosed = 'Sure:\n```json\n{"tool": "read_file", "args": {"path": "x.py", "start": 1, "end": 20}}'
        calls, errs = pilot_pr.extract_tool_calls(unclosed)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["tool"], "read_file")

        # 2c. Single object vs list without fences, with leading & trailing prose
        single_prose = 'I will check first: {"tool": "list_files", "args": {"path": "."}} done.'
        calls, errs = pilot_pr.extract_tool_calls(single_prose)
        self.assertEqual(errs, [])
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["tool"], "list_files")

        list_prose = 'Next steps: [{"tool": "grep", "args": {"pattern": "foo"}}, {"tool": "run_tests", "args": {}}] end.'
        calls, errs = pilot_pr.extract_tool_calls(list_prose)
        self.assertEqual(errs, [])
        self.assertEqual([c["tool"] for c in calls], ["grep", "run_tests"])

        # 2d. Unescaped literal newline inside JSON string value (strict=False)
        raw_nl = '```json\n{"tool": "search_replace", "args": {"path": "a.py", "old": "a\nb", "new": "a\nc"}}\n```'
        calls, errs = pilot_pr.extract_tool_calls(raw_nl)
        self.assertEqual(errs, [])
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["args"]["old"], "a\nb")

        # 2e. Plain prose with non-tool braces must NOT produce false positive tool calls
        plain = 'Consider the dict {"foo": "bar"} in Python.'
        calls, errs = pilot_pr.extract_tool_calls(plain)
        self.assertEqual(calls, [])

    # ------------------------------------------------------------------
    # (d) Fix rank 3: Prompt run_tests instruction & separate auto-run
    # ------------------------------------------------------------------
    def test_fix_rank3_prompt_instructs_run_tests_and_auto_run_never_marks_pass(self):
        """Prompt tells model to call run_tests after edits; end-of-loop auto-run runs once and NEVER sets stop_reason='pass' or passed=True."""
        wt_dir, base_sha = _make_git_scratch(
            py_src="def compute():\n    return 0\n",
            test_src="import mod\nassert mod.compute() in (0, 42)\n",  # passes at base (pr1342 false-pass pattern!)
        )
        run_dir = tempfile.mkdtemp(prefix="pilot_v4_autorun_")
        try:
            task = {
                "id": "v4_autorun_task",
                "pr_number": 953,
                "title": "Auto-run test",
                "base_commit": base_sha,
                "merged_commit": "d" * 40,
                "has_tests": True,
                "test_cmd": "python3 test_mod.py",
                "prompt": "Update compute().",
                "files": ["mod.py"],
            }
            msgs = pilot_pr.format_tool_messages(task, worktree_dir=wt_dir)
            sys_txt = msgs[0]["content"]
            usr_txt = msgs[1]["content"]
            rules_part = sys_txt.split("Rules:\n", 1)[1]
            self.assertIn("run_tests", rules_part)
            self.assertIn("run_tests", usr_txt.splitlines()[-1])

            # Case 1: Model edits mod.py on turn 0 (base tests pass!) and hits max_turns without calling run_tests/finish
            def mock_edit_no_test(messages, seed):
                calls = [{"tool": "search_replace", "args": {"path": "mod.py", "old": "return 0", "new": "return 42"}}]
                return {"content": "```json\n" + json.dumps(calls) + "\n```", "reasoning_chars": 15, "finish_reason": "stop", "usage": {"completion_tokens": 30}}

            res = pilot_pr.run_task_loop(task, mock_edit_no_test, wt_dir, max_turns=1, run_dir=run_dir, label="ar1", token_counter=lambda m: 500)
            self.assertEqual(res["stop_reason"], "max_turns")  # NEVER rewritten to "pass"
            self.assertFalse(res["passed"])                    # NEVER True from end-of-loop auto-run
            self.assertEqual(res["run_tests_calls"], 0)
            self.assertTrue(res["auto_run_tests"])
            self.assertTrue(res["end_of_loop_test_passed"])    # Recorded separately!
            self.assertFalse(res["history"][-1]["passed"])

            with open(os.path.join(run_dir, "turn_events.jsonl"), encoding="utf-8") as ef:
                events = [json.loads(ln) for ln in ef if ln.strip()]
            ar_evs = [e for e in events if e["event"] == "auto_run_tests"]
            self.assertEqual(len(ar_evs), 1)
            self.assertTrue(ar_evs[0]["passed"])
            self.assertTrue(ar_evs[0]["dirty_since_last_test"])

            # Case 2: Model never edits AND never calls run_tests -> auto-run STILL executes once at loop end
            subprocess.run(["git", "checkout", "--", "mod.py"], cwd=wt_dir, check=True)
            def mock_read_only_no_test(messages, seed):
                calls = [{"tool": "read_file", "args": {"path": "mod.py", "start": 1, "end": 5}}]
                return {"content": "```json\n" + json.dumps(calls) + "\n```", "reasoning_chars": 5, "finish_reason": "stop", "usage": {"completion_tokens": 20}}

            res2 = pilot_pr.run_task_loop(task, mock_read_only_no_test, wt_dir, max_turns=1, run_dir=run_dir, label="ar2", token_counter=lambda m: 500)
            self.assertEqual(res2["stop_reason"], "max_turns")
            self.assertFalse(res2["passed"])
            self.assertTrue(res2["auto_run_tests"])
            self.assertTrue(res2["end_of_loop_test_passed"])

            # Case 3: Model explicitly calls run_tests -> auto_run_tests is False (no redundant run)
            def mock_explicit_run_tests(messages, seed):
                calls = [{"tool": "run_tests", "args": {}}]
                return {"content": "```json\n" + json.dumps(calls) + "\n```", "reasoning_chars": 5, "finish_reason": "stop", "usage": {"completion_tokens": 20}}

            res3 = pilot_pr.run_task_loop(task, mock_explicit_run_tests, wt_dir, max_turns=1, run_dir=run_dir, label="ar3", token_counter=lambda m: 500)
            self.assertEqual(res3["run_tests_calls"], 1)
            self.assertFalse(res3["auto_run_tests"])
            self.assertIsNone(res3["end_of_loop_test_passed"])
        finally:
            shutil.rmtree(wt_dir, ignore_errors=True)
            shutil.rmtree(run_dir, ignore_errors=True)

    # ------------------------------------------------------------------
    # (e) Fix rank 4: TOOL_RESULT_MAX_LINES aligned with prompt (250)
    # ------------------------------------------------------------------
    def test_fix_rank4_tool_result_max_lines_aligned_with_prompt_250(self):
        """TOOL_RESULT_MAX_LINES == READ_FILE_MAX_LINES == 250, matches prompt text, and does not truncate a 250-line read."""
        self.assertEqual(pilot_pr.READ_FILE_MAX_LINES, 250)
        self.assertEqual(pilot_pr.TOOL_RESULT_MAX_LINES, pilot_pr.READ_FILE_MAX_LINES)
        self.assertEqual(pilot_pr.TOOL_RESULT_HEAD_LINES + pilot_pr.TOOL_RESULT_TAIL_LINES, 250)

        task = {
            "id": "v4_align",
            "pr_number": 954,
            "title": "Align test",
            "base_commit": "0" * 40,
            "merged_commit": "1" * 40,
            "has_tests": True,
            "test_cmd": "python3 -m unittest",
            "prompt": "Check alignment.",
            "files": ["a.py"],
        }
        msgs = pilot_pr.format_tool_messages(task)
        m = re.search(r"max (\d+) lines/call", msgs[0]["content"])
        self.assertIsNotNone(m)
        self.assertEqual(int(m.group(1)), pilot_pr.TOOL_RESULT_MAX_LINES)

        # A 250-line Python read (~10k chars) must NOT be elided by compact_tool_output or compact_turn_feedback
        lines_250 = "\n".join(f"{i:4d}: x_{i:03d} = {i}  # sample python code" for i in range(1, 251))
        out, info = pilot_pr.compact_tool_output(lines_250)
        self.assertFalse(info["truncated"], f"250-line read should not truncate: {info}")
        self.assertEqual(out, lines_250)
        fb, fb_info = pilot_pr.compact_turn_feedback([f"[1] read_file OK:\n{out}"])
        self.assertFalse(fb_info["truncated"], f"Single 250-line read should fit in turn feedback: {fb_info}")

    # ------------------------------------------------------------------
    # (f) Unseen v4 task selection, contamination cutoff, prompts, bwrap, Section 18 table
    # ------------------------------------------------------------------
    def test_v4_mechanical_selection_matches_frozen_list(self):
        """select_v4.py reproduces the exact frozen 7-PR lark-parser/lark list in tasks_item6_v4.py (Phase 1=0, Phase 2=lark).

        Note: audit counts for skipped earlier shortlist repos (`python-markdown/markdown` and
        `pyparsing/pyparsing`) are informational only and can vary across hosts because outer
        `/usr/bin/bwrap` read-only bind-mounts `/usr` (e.g. system `python3-markdown` entry
        points affect markdown PR #1621: 1 verified with it, 0 without it). Both are strictly
        below 7 either way, so the frozen `lark-parser/lark` selection is invariant.
        """
        repos_dir = tasks_item6_v4.DEFAULT_V4_REPOS_DIR
        self.assertTrue(os.path.isdir(repos_dir), f"v4 bare repos dir missing: {repos_dir}")
        frozen = tasks_item6_v4.load_tasks()
        self.assertEqual(len(frozen), 7)

        res = select_v4.select_v4_batch(repos_dir=repos_dir, verify_bwrap=True)
        self.assertEqual(res["primary_selected"], [])
        self.assertEqual(res["fallback_repo_slug"], "lark-parser/lark")
        self.assertEqual(res["shortfall"], 0)
        # Prior shortlist audit entries (markdown, pyparsing) are informational only; assert only < 7.
        for audit_entry in res["fallback_audit"]:
            if audit_entry["slug"] in ("python-markdown/markdown", "pyparsing/pyparsing"):
                self.assertLess(audit_entry["verified_count"], select_v4.V4_BATCH_SIZE)
        selected = res["selected"]
        self.assertEqual(len(selected), 7)
        self.assertEqual([p["pr_number"] for p in selected], [t["pr_number"] for t in frozen])

        for p, t in zip(selected, frozen):
            self.assertEqual(p["repo_slug"], t["repo_slug"])
            self.assertEqual(p["base_commit"], t["base_commit"])
            self.assertEqual(p["merged_commit"], t["merged_commit"])
            self.assertEqual(p["merged_at_utc"], t["merged_at_utc"])
            self.assertEqual(p["files"], sorted(t["files"]))
            self.assertEqual(p["test_files"], sorted(t["test_files"]))
            self.assertEqual(p["test_cmd"], t["test_cmd"])
            self.assertEqual(p["expected_test_count"], t["grade_spec"]["expected_test_count"])
            self.assertEqual(p["total_changed_lines"], t["total_changed_lines"])

    def test_search_replace_preserves_crlf_and_lf_line_endings(self):
        """tool_search_replace preserves CRLF on CRLF files and LF on LF files, and captured diffs apply cleanly."""
        wt_dir = tempfile.mkdtemp(prefix="pilot_v4_eol_")
        try:
            subprocess.run(["git", "init", "-q"], cwd=wt_dir, check=True)
            subprocess.run(["git", "config", "user.name", "Tester"], cwd=wt_dir, check=True)
            subprocess.run(["git", "config", "user.email", "tester@example.org"], cwd=wt_dir, check=True)

            crlf_path = os.path.join(wt_dir, "crlf_mod.py")
            lf_path = os.path.join(wt_dir, "lf_mod.py")
            with open(crlf_path, "wb") as f:
                f.write(b"def alpha():\r\n    return 1\r\n\r\ndef beta():\r\n    return 2\r\n")
            with open(lf_path, "wb") as f:
                f.write(b"def gamma():\n    return 3\n\ndef delta():\n    return 4\n")
            subprocess.run(["git", "add", "."], cwd=wt_dir, check=True)
            subprocess.run(["git", "commit", "-q", "-m", "base"], cwd=wt_dir, check=True)
            base_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=wt_dir, text=True).strip()

            # Edit both files using LF old/new strings (as produced from read_file output)
            ok_c, msg_c = pilot_pr.tool_search_replace(
                wt_dir, "crlf_mod.py", "def alpha():\n    return 1", "def alpha():\n    return 10"
            )
            self.assertTrue(ok_c, msg_c)
            ok_l, msg_l = pilot_pr.tool_search_replace(
                wt_dir, "lf_mod.py", "def gamma():\n    return 3", "def gamma():\n    return 30"
            )
            self.assertTrue(ok_l, msg_l)

            with open(crlf_path, "rb") as f:
                crlf_after = f.read()
            with open(lf_path, "rb") as f:
                lf_after = f.read()

            # CRLF file must retain \r\n on every line (no bare \n)
            self.assertEqual(crlf_after, b"def alpha():\r\n    return 10\r\n\r\ndef beta():\r\n    return 2\r\n")
            self.assertNotIn(b"\n", crlf_after.replace(b"\r\n", b""))
            # LF file must retain pure \n (no \r)
            self.assertEqual(lf_after, b"def gamma():\n    return 30\n\ndef delta():\n    return 4\n")
            self.assertNotIn(b"\r", lf_after)

            # Captured diff must be targeted (not a whole-file CRLF flip) and re-apply cleanly on base
            diff_text = pilot_pr.capture_worktree_diff(wt_dir, base_sha)
            self.assertIn("\r\n", diff_text)
            self.assertNotIn("-def beta():", diff_text)
            subprocess.run(["git", "checkout", "--", "crlf_mod.py", "lf_mod.py"], cwd=wt_dir, check=True)
            ap_ok, ap_msg = pilot_pr.apply_updates(wt_dir, {"__patch__": diff_text.rstrip("\n")})
            self.assertTrue(ap_ok, f"CRLF/LF diff failed to re-apply: {ap_msg}")
            with open(crlf_path, "rb") as f:
                self.assertEqual(f.read(), crlf_after)
            with open(lf_path, "rb") as f:
                self.assertEqual(f.read(), lf_after)
        finally:
            shutil.rmtree(wt_dir, ignore_errors=True)

    def test_analyze_v3_turns_warns_to_stderr_on_git_show_fallback(self):
        """analyze_v3_turns._read_pilot_source_text prints a warning to stderr on git show failure and stays silent when ddcbbfb succeeds."""
        import io
        from contextlib import redirect_stderr
        from pathlib import Path
        import analyze_v3_turns

        pilot_path = Path(HERE) / "pilot_pr.py"

        # 1. Valid pinned v3 commit -> silent on stderr
        buf_ok = io.StringIO()
        with redirect_stderr(buf_ok):
            txt_ok = analyze_v3_turns._read_pilot_source_text(
                pilot_source_path=pilot_path,
                pilot_git_rev=analyze_v3_turns.V3_RUN_GIT_REV,
            )
        self.assertTrue(len(txt_ok) > 1000)
        self.assertEqual(buf_ok.getvalue(), "")

        # 2. Invalid git rev -> warns loudly on stderr before falling back to working tree
        buf_warn = io.StringIO()
        bad_rev = "0000000000000000000000000000000000000000"
        with redirect_stderr(buf_warn):
            txt_fb = analyze_v3_turns._read_pilot_source_text(
                pilot_source_path=pilot_path,
                pilot_git_rev=bad_rev,
            )
        self.assertIn("WARNING:", buf_warn.getvalue())
        self.assertIn(bad_rev, buf_warn.getvalue())
        self.assertIn("falling back", buf_warn.getvalue())
        self.assertEqual(txt_fb, pilot_path.read_text(encoding="utf-8"))

    def test_v4_contamination_cutoff_and_disjoint_from_v2_v3(self):
        """All 7 v4 tasks are strictly post-Qwen3.6-35B-A3B release and disjoint from v2/v3 development sets."""
        cutoff = datetime.fromisoformat(tasks_item6_v4.QWEN36_RELEASE_UTC.replace("Z", "+00:00"))
        win_start = datetime.fromisoformat(select_v4.V4_FALLBACK_WINDOW_START.replace("Z", "+00:00"))
        win_end = datetime.fromisoformat(select_v4.V4_FALLBACK_WINDOW_END.replace("Z", "+00:00"))
        self.assertGreater(win_start, cutoff)
        self.assertIn("huggingface.co/Qwen/Qwen3.6-35B-A3B", tasks_item6_v4.QWEN36_RELEASE_SOURCE)

        v2_ids = {t["id"] for t in tasks_item6.load_tasks()}
        v3_ids = {t["id"] for t in tasks_item6_v3.load_tasks()}
        for t in tasks_item6_v4.load_tasks():
            self.assertNotIn(t["id"], v2_ids)
            self.assertNotIn(t["id"], v3_ids)
            self.assertEqual(t["repo_slug"], "lark-parser/lark")
            dt = datetime.fromisoformat(t["merged_at_utc"].replace("Z", "+00:00"))
            self.assertGreater(dt, cutoff)
            self.assertTrue(win_start <= dt <= win_end)

    def test_v4_prompts_rule_built_no_code_blocks_no_leaks(self):
        """Every v4 prompt matches build_v4_task_prompt, strips code blocks, and passes ExplodingTaskDict + leak check."""
        for t in tasks_item6_v4.load_tasks():
            rebuilt = tasks_item6_v4.build_v4_task_prompt(
                t["repo_slug"], t["source_kind"], t["raw_source_title"], t["raw_source_body"]
            )
            self.assertEqual(t["prompt"], rebuilt)
            self.assertNotIn("```", t["prompt"])
            self.assertNotIn("~~~", t["prompt"])
            self.assertNotIn("104729", t["prompt"])
            self.assertNotIn(t["merged_commit"], t["prompt"])
            self.assertNotIn(t["merged_commit"][:10], t["prompt"])

            exploding = ExplodingTaskDict(t)
            clean = tasks_item6_v4.strip_hidden(exploding)
            self.assertNotIn("merged_commit", clean)
            self.assertNotIn("hidden_diff", clean)
            self.assertNotIn("test_files", clean)
            self.assertNotIn("grade_spec", clean)

            msgs = pilot_pr.format_tool_messages(clean)
            pilot_pr.check_prompt_leak(msgs, t, run_sentinel=pilot_pr.generate_run_sentinel())

    def test_v4_all_seven_tasks_fail_at_base_and_pass_at_merged_in_bwrap(self):
        """Offline CPU check in bwrap: every v4 task's merged tests FAIL at base_commit and PASS at merged_commit."""
        repos_dir = tasks_item6_v4.DEFAULT_V4_REPOS_DIR
        self.assertTrue(os.path.isdir(repos_dir))
        for t in tasks_item6_v4.load_tasks():
            task_repo = os.path.join(repos_dir, f"{t['repo_name']}.git")
            base_ok, base_out = pilot_pr.regrade_task_diff(t, "", repo_root=task_repo, timeout=120)
            self.assertFalse(base_ok, f"Expected {t['id']} to FAIL at base_commit, got PASS:\n{base_out[:400]}")

            hidden_diff = tasks_item6_v4.get_hidden_diff(t, repo_root=repos_dir)
            self.assertTrue(hidden_diff.strip(), f"Empty hidden diff for {t['id']}")
            merged_ok, merged_out = pilot_pr.regrade_task_diff(t, hidden_diff, repo_root=task_repo, timeout=120)
            self.assertTrue(merged_ok, f"Expected {t['id']} to PASS at merged_commit in bwrap:\n{merged_out[:600]}")

    def test_v4_prereg_doc_section_18_5_shas_match_tasks_and_mirror(self):
        """Section 18.5 table in docs/item6-pilot.md matches tasks_item6_v4.py and mirror first-parent base SHAs verbatim."""
        repo_root = os.path.abspath(os.path.join(HERE, "..", ".."))
        with open(os.path.join(repo_root, "docs", "item6-pilot.md"), encoding="utf-8") as df:
            doc_text = df.read()
        m = re.search(r"### 18\.5 Frozen v4 Unseen Task List.*?\n(.*?)\n### 18\.6 ", doc_text, re.DOTALL)
        self.assertIsNotNone(m, "Section 18.5 table not found in docs/item6-pilot.md")

        table_rows = {}
        for line in m.group(1).splitlines():
            line = line.strip()
            if not line.startswith("| `item6v4_pr"):
                continue
            cols = [c.strip() for c in line.strip("|").split("|")]
            self.assertGreaterEqual(len(cols), 9)
            tid = cols[0].strip("`")
            table_rows[tid] = {
                "pr_number": int(cols[1].lstrip("#")),
                "merged_at_utc": cols[2].strip("`"),
                "total_changed_lines": int(cols[3]),
                "base_commit": cols[4].strip("`"),
                "test_cmd": cols[6].strip("`"),
                "expected_test_count": int(cols[7]),
            }

        frozen = tasks_item6_v4.load_tasks()
        self.assertEqual(len(table_rows), len(frozen))
        mirror = os.path.join(tasks_item6_v4.DEFAULT_V4_REPOS_DIR, "lark.git")
        for t in frozen:
            row = table_rows[t["id"]]
            self.assertEqual(row["pr_number"], t["pr_number"])
            self.assertEqual(row["merged_at_utc"], t["merged_at_utc"])
            self.assertEqual(row["total_changed_lines"], t["total_changed_lines"])
            self.assertEqual(len(row["base_commit"]), 40)
            self.assertEqual(row["base_commit"], t["base_commit"])
            self.assertEqual(row["test_cmd"], t["test_cmd"])
            self.assertEqual(row["expected_test_count"], t["grade_spec"]["expected_test_count"])
            mirror_base = subprocess.check_output(
                ["git", "-C", mirror, "rev-parse", f"{t['merged_commit']}^1"], text=True
            ).strip()
            self.assertEqual(t["base_commit"], mirror_base)

    # ------------------------------------------------------------------
    # (g) v4 practice & counted launchers + plumbing
    # ------------------------------------------------------------------
    def test_v4_launchers_guards_freeze_and_practice_criteria(self):
        """Verify syntax, frozen-label refusal (v1/v2/v3), placeholder refusal, and v4 practice/counted launcher configs."""
        repo_root = os.path.abspath(os.path.join(HERE, "..", ".."))
        prac_sh = os.path.join(repo_root, "bench", "loop", "runs", "item6-v4-practice", "run.sh")
        v4_sh = os.path.join(repo_root, "bench", "loop", "runs", "item6-pilot-v4", "run.sh")

        for sh in (prac_sh, v4_sh):
            self.assertTrue(os.path.isfile(sh))
            chk = subprocess.run(["bash", "-n", sh], capture_output=True, text=True)
            self.assertEqual(chk.returncode, 0, f"bash -n failed for {sh}: {chk.stderr}")
            for frozen_lbl in ("item6-pilot", "item6-pilot-v2", "item6-pilot-v3"):
                env = dict(os.environ, WT=repo_root, EXPECT_HEAD="0" * 40, LABEL=frozen_lbl)
                res = subprocess.run(["bash", sh], cwd=repo_root, env=env, capture_output=True, text=True)
                self.assertNotEqual(res.returncode, 0, f"{sh} must refuse frozen label {frozen_lbl}")
                self.assertIn("frozen", res.stderr.lower())
            env_wt = dict(os.environ, EXPECT_HEAD="0" * 40)
            env_wt.pop("WT", None)
            env_wt.pop("LABEL", None)
            res_wt = subprocess.run(["bash", sh], cwd=repo_root, env=env_wt, capture_output=True, text=True)
            self.assertNotEqual(res_wt.returncode, 0)
            self.assertIn("WT must be set", res_wt.stderr)

        with open(prac_sh, encoding="utf-8") as pf:
            prac_txt = pf.read()
        self.assertIn('CEILING_SECONDS="${CEILING_SECONDS:-4320}"', prac_txt)
        self.assertIn('TASK_WALL_BUDGET="${TASK_WALL_BUDGET:-617}"', prac_txt)
        self.assertIn("--task-suite v3", prac_txt)
        self.assertNotIn("pilot_pr.py grade", prac_txt)
        self.assertIn("reasoning_chars", prac_txt)
        self.assertIn("content_chars", prac_txt)
        self.assertIn("finish_reason", prac_txt)
        self.assertIn("run_tests_calls", prac_txt)
        self.assertIn("auto_run_tests", prac_txt)
        for t in tasks_item6_v3.load_tasks():
            self.assertIn(f'"{t["id"]}"', prac_txt)

        with open(v4_sh, encoding="utf-8") as vf:
            v4_txt = vf.read()
        self.assertIn('CEILING_SECONDS="${CEILING_SECONDS:-4320}"', v4_txt)
        self.assertIn('TASK_WALL_BUDGET="${TASK_WALL_BUDGET:-617}"', v4_txt)
        self.assertIn("INVITE_OPTS=(--ctx 65536 --np 1)", v4_txt)
        self.assertIn("prereg-guard.sh --head", v4_txt)
        self.assertIn("--task-suite v4", v4_txt)
        self.assertIn(tasks_item6_v4.V4_SELECTED_HEAD_COMMIT, v4_txt)
        for t in tasks_item6_v4.load_tasks():
            self.assertIn(f'"{t["id"]}"', v4_txt)

    def test_v4_run_and_grade_subcommand_plumbing(self):
        """run_subcommand and grade_subcommand with task_suite='v4' work cleanly against /data/datasets/item6-v4-repos."""
        results_dir = tempfile.mkdtemp(prefix="pilot_v4_plumb_res_")
        run_dir = tempfile.mkdtemp(prefix="pilot_v4_plumb_run_")
        try:
            def mock_v4_ask(messages, seed):
                calls = [
                    {"tool": "read_file", "args": {"path": "lark/tree_templates.py", "start": 1, "end": 20}},
                    {"tool": "create_file", "args": {"path": "v4_probe_note.txt", "content": "probe\n"}},
                ]
                return {
                    "content": "```json\n" + json.dumps(calls) + "\n```",
                    "reasoning_chars": 77,
                    "finish_reason": "stop",
                    "usage": {"completion_tokens": 25},
                }

            rows = pilot_pr.run_subcommand(
                label="v4-plumb-test",
                tasks_arg="item6v4_pr1632",
                max_turns=1,
                results_dir=results_dir,
                run_dir=run_dir,
                ask_fn=mock_v4_ask,
                token_counter=lambda m: 1200,
                task_suite="v4",
                target_repo=tasks_item6_v4.DEFAULT_V4_REPOS_DIR,
            )
            self.assertEqual(len(rows), 1)
            r = rows[0]
            self.assertEqual(r["task_id"], "item6v4_pr1632")
            self.assertFalse(r["harness_failure"])
            self.assertEqual(r["stop_reason"], "max_turns")
            self.assertFalse(r["passed"])
            self.assertTrue(r["auto_run_tests"])
            self.assertIn("v4_probe_note.txt", r["final_diff"])

            rev_path = os.path.join(results_dir, "v4-plumb-test.reviews.json")
            with open(rev_path, "w", encoding="utf-8") as rf:
                json.dump({
                    "item6v4_pr1632": {
                        "verdict": "REQUEST-CHANGES",
                        "hand_fix_lines": 10,
                        "tamper": False,
                        "fresh_session": True,
                    }
                }, rf)

            grade = pilot_pr.grade_subcommand(
                label="v4-plumb-test",
                reviews_file=rev_path,
                results_dir=results_dir,
                task_suite="v4",
                target_repo=tasks_item6_v4.DEFAULT_V4_REPOS_DIR,
            )
            self.assertEqual(grade["tasks_evaluated"], 1)
            self.assertEqual(grade["testable_tasks"], 1)
            self.assertEqual(grade["testable_passed"], 0)
            self.assertEqual(grade["decision"], "DROP")
        finally:
            shutil.rmtree(results_dir, ignore_errors=True)
            shutil.rmtree(run_dir, ignore_errors=True)

    def test_v4_committed_results_sha256sums_grade_and_reviews(self):
        """Committed item6-pilot-v4 results match frozen & final SHA256SUMS, exclude run.pid/leaks, and encode official INCONCLUSIVE grade."""
        repo_root = os.path.abspath(os.path.join(HERE, "..", ".."))
        res_dir = os.path.join(repo_root, "bench", "loop", "results")
        frozen_sums_path = os.path.join(res_dir, "item6-pilot-v4.SHA256SUMS")
        final_sums_path = os.path.join(res_dir, "item6-pilot-v4.final.SHA256SUMS")
        self.assertTrue(os.path.isfile(frozen_sums_path), f"Missing v4 frozen SHA256SUMS: {frozen_sums_path}")
        self.assertTrue(os.path.isfile(final_sums_path), f"Missing v4 final SHA256SUMS: {final_sums_path}")

        # Must never commit run.pid or leak histories
        run1_dir = os.path.join(res_dir, "item6-pilot-v4.run1")
        self.assertTrue(os.path.isdir(run1_dir))
        self.assertFalse(os.path.exists(os.path.join(run1_dir, "run.pid")), "run.pid must not be committed")
        for fn in os.listdir(run1_dir):
            self.assertFalse(fn.startswith("leak_history_"), f"leak history must not be committed: {fn}")

        def _verify_sums(path):
            entries = {}
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    digest, rel = line.split(None, 1)
                    entries[rel] = digest
                    full_p = os.path.join(res_dir, rel)
                    self.assertTrue(os.path.isfile(full_p), f"Missing file listed in {os.path.basename(path)}: {rel}")
                    with open(full_p, "rb") as rf:
                        raw = rf.read()
                    self.assertEqual(hashlib.sha256(raw).hexdigest(), digest, f"SHA256 mismatch on {rel}")
                    text = raw.decode("utf-8")
                    self.assertNotIn("104729", text, f"Forbidden literal seed in {rel}")
                    self.assertNotIn("PILOT-RUN-SENTINEL", text, f"Forbidden run sentinel in {rel}")
            return entries

        expected_tids = [t["id"] for t in tasks_item6_v4.load_tasks()]
        frozen_entries = _verify_sums(frozen_sums_path)
        self.assertEqual(len(frozen_entries), 9)
        self.assertIn("item6-pilot-v4.jsonl", frozen_entries)
        self.assertIn("item6-pilot-v4.grade.json", frozen_entries)
        for tid in expected_tids:
            self.assertIn(f"item6-pilot-v4.diffs/{tid}.diff", frozen_entries)

        final_entries = _verify_sums(final_sums_path)
        self.assertEqual(len(final_entries), 15)
        for required in (
            "item6-pilot-v4.jsonl",
            "item6-pilot-v4.grade.json",
            "item6-pilot-v4.reviews.json",
            "item6-pilot-v4.official-grade.json",
            "item6-pilot-v4.run1/run.log",
            "item6-pilot-v4.run1/run.status",
            "item6-pilot-v4.run1/turn_events.jsonl",
            "item6-pilot-v4.run1/AJ-GO-COUNTED.txt",
        ):
            self.assertIn(required, final_entries)

        # Verify JSONL completeness & zero overflow / harness failures
        with open(os.path.join(res_dir, "item6-pilot-v4.jsonl"), "r", encoding="utf-8") as f:
            rows = [json.loads(line) for line in f if line.strip()]
        self.assertEqual([r["task_id"] for r in rows], expected_tids)
        for r in rows:
            self.assertEqual(r.get("schema_version"), 2)
            self.assertNotEqual(r.get("stop_reason"), "context_overflow")
            self.assertFalse(r.get("harness_failure"))

        # Verify verbatim Tier 2 reviews structure
        with open(os.path.join(res_dir, "item6-pilot-v4.reviews.json"), "r", encoding="utf-8") as f:
            rev_doc = json.load(f)
        reviews = rev_doc["reviews"]
        self.assertEqual(
            set(reviews.keys()),
            {"item6v4_pr1543", "item6v4_pr1619", "item6v4_pr1624", "item6v4_pr1632", "item6v4_pr1641"},
        )
        self.assertEqual(set(rev_doc["meta"]["auto_non_approval"].keys()), {"item6v4_pr1601", "item6v4_pr1613"})
        self.assertEqual(reviews["item6v4_pr1543"]["verdict"], "APPROVE-WITH-NITS")
        self.assertEqual(reviews["item6v4_pr1543"]["hand_fix_lines"], 0)
        self.assertEqual(reviews["item6v4_pr1619"]["verdict"], "APPROVE-WITH-NITS")
        self.assertEqual(reviews["item6v4_pr1619"]["hand_fix_lines"], 0)
        self.assertEqual(reviews["item6v4_pr1624"]["verdict"], "REQUEST-CHANGES")
        self.assertEqual(reviews["item6v4_pr1624"]["hand_fix_lines"], 1)
        self.assertEqual(reviews["item6v4_pr1632"]["verdict"], "REQUEST-CHANGES")
        self.assertEqual(reviews["item6v4_pr1632"]["hand_fix_lines"], 5)
        self.assertEqual(reviews["item6v4_pr1641"]["verdict"], "REQUEST-CHANGES")
        self.assertEqual(reviews["item6v4_pr1641"]["hand_fix_lines"], 15)
        for tid, rv in reviews.items():
            self.assertIs(rv["tamper"], False, f"{tid} tamper must be False")
            self.assertIs(rv["fresh_session"], True, f"{tid} fresh_session must be True")

        # Verify frozen unofficial run-time grade.json stays untouched (PENDING_REVIEW)
        with open(os.path.join(res_dir, "item6-pilot-v4.grade.json"), "r", encoding="utf-8") as f:
            rt_grade = json.load(f)
        self.assertFalse(rt_grade["reviews_complete"])
        self.assertEqual(rt_grade["decision"], "PENDING_REVIEW")
        self.assertEqual(rt_grade["testable_passed"], 4)

        # Verify official post-review grade under Section 18.1 bars
        with open(os.path.join(res_dir, "item6-pilot-v4.official-grade.json"), "r", encoding="utf-8") as f:
            grade = json.load(f)
        self.assertEqual(grade["schema_version"], 2)
        self.assertEqual(grade["label"], "item6-pilot-v4")
        self.assertEqual(grade["tasks_evaluated"], 7)
        self.assertEqual(grade["testable_tasks"], 7)
        self.assertEqual(grade["testable_passed"], 4)
        self.assertEqual(grade["test_pass_rate"], 0.5714)
        self.assertTrue(grade["reviews_complete"])
        self.assertEqual(grade["approved_first_pass"], 2)
        self.assertEqual(grade["approved_final"], 2)
        self.assertEqual(grade["final_approve_rate"], 0.2857)
        self.assertEqual(grade["avg_hand_fix_lines_per_approved"], 0.0)
        self.assertEqual(grade["decision"], "INCONCLUSIVE")

        by_tid = {p["task_id"]: p for p in grade["per_task"]}
        self.assertEqual(list(by_tid.keys()), expected_tids)
        # In-loop vs authoritative discrepancies
        for tid in ("item6v4_pr1543", "item6v4_pr1619"):
            self.assertIs(by_tid[tid]["in_loop_passed"], True)
            self.assertIs(by_tid[tid]["test_passed"], True)
            self.assertEqual(by_tid[tid]["final_verdict"], "APPROVE-WITH-NITS")
        for tid in ("item6v4_pr1624", "item6v4_pr1632"):
            self.assertIs(by_tid[tid]["in_loop_passed"], False)
            self.assertIs(by_tid[tid]["test_passed"], True)
            self.assertEqual(by_tid[tid]["final_verdict"], "REQUEST-CHANGES")
        self.assertIs(by_tid["item6v4_pr1641"]["in_loop_passed"], True)
        self.assertIs(by_tid["item6v4_pr1641"]["test_passed"], False)
        self.assertEqual(by_tid["item6v4_pr1641"]["final_verdict"], "REQUEST-CHANGES")
        for empty_tid in ("item6v4_pr1601", "item6v4_pr1613"):
            self.assertIs(by_tid[empty_tid]["diff_empty"], True)
            self.assertIsNone(by_tid[empty_tid]["tamper"])
            self.assertEqual(by_tid[empty_tid]["final_verdict"], "NON-APPROVAL")
            self.assertIsNone(by_tid[empty_tid]["hand_fix_lines"])


if __name__ == "__main__":
    unittest.main()
