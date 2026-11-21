#!/usr/bin/env python3
"""CPU-only unit tests for Item 6 Pilot v3: tool/history compaction, unseen external-repo task selection,
rule-built prompts, offline bwrap base-fails/merged-passes verification, and v3/practice launchers.
"""
from datetime import datetime, timezone
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import pilot_pr  # noqa: E402
import select_v3  # noqa: E402
import tasks_item6  # noqa: E402
import tasks_item6_v3  # noqa: E402


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


class TestPilotPrV3(unittest.TestCase):

    def test_head_tail_truncation_markers_for_tool_and_test_output(self):
        """Tool and test outputs cap lines & chars, keeping head and tail with explicit elided-lines markers and redacting 104729."""
        # 1. Line-capped tool output (> TOOL_RESULT_MAX_LINES)
        lines_250 = [f"L{i:04d}: payload content row {i}" for i in range(250)]
        lines_250[0] = "L0000: head sentinel seed 104729"
        lines_250[-1] = "L0249: tail sentinel"
        out_tool, info_tool = pilot_pr.compact_tool_output("\n".join(lines_250))
        self.assertTrue(info_tool["truncated"])
        self.assertEqual(info_tool["orig_lines"], 250)
        self.assertGreater(info_tool["elided_lines"], 0)
        self.assertIn("L0000: head sentinel seed <REDACTED_SEED>", out_tool)
        self.assertIn("L0249: tail sentinel", out_tool)
        self.assertNotIn("104729", out_tool)
        self.assertRegex(out_tool, r"\.\.\. \[elided \d+ lines.*\] \.\.\.")
        self.assertLessEqual(len(out_tool), pilot_pr.TOOL_RESULT_MAX_CHARS + 120)

        # 2. Char-capped tool output (few lines, huge line length)
        long_lines = "\n".join([f"H{i}: " + ("A" * 2000) for i in range(5)])
        out_chars, info_chars = pilot_pr.compact_tool_output(long_lines)
        self.assertTrue(info_chars["truncated"])
        self.assertIn("H0:", out_chars)
        self.assertIn("A", out_chars[-200:])
        self.assertRegex(out_chars, r"\.\.\. \[elided \d+ lines, \d+ chars\] \.\.\.")
        self.assertLessEqual(len(out_chars), pilot_pr.TOOL_RESULT_MAX_CHARS + 120)

        # 3. Line-capped test output (> TEST_OUTPUT_MAX_LINES) keeps head and tail traceback
        test_lines = [f"test_case_{i:03d} ... ok" for i in range(150)]
        test_lines[0] = "FAIL: test_first_header"
        test_lines[-1] = "AssertionError: final_failure_marker"
        out_test, info_test = pilot_pr.compact_test_output("\n".join(test_lines))
        self.assertTrue(info_test["truncated"])
        self.assertIn("FAIL: test_first_header", out_test)
        self.assertIn("AssertionError: final_failure_marker", out_test)
        self.assertRegex(out_test, r"\.\.\. \[elided \d+ lines.*\] \.\.\.")
        self.assertLessEqual(len(out_test), pilot_pr.TEST_OUTPUT_MAX_CHARS + 120)

        # 4. Short output passes untouched (except seed redaction)
        short_out, short_info = pilot_pr.compact_tool_output("short ok\nline 2")
        self.assertFalse(short_info["truncated"])
        self.assertEqual(short_out, "short ok\nline 2")
        self.assertEqual(short_info["chars_saved"], 0)

    def test_per_turn_combined_feedback_cap(self):
        """Multiple large tool outputs in a single turn are capped under TURN_FEEDBACK_MAX_CHARS."""
        chunks = [f"[{i}] read_file OK:\n" + "\n".join(f"c{i}_line_{j}: " + ("z" * 45) for j in range(90)) for i in range(1, 7)]
        fb, info = pilot_pr.compact_turn_feedback(chunks)
        self.assertTrue(info["truncated"])
        self.assertGreater(info["chars_saved"], 0)
        self.assertIn("Tool results:", fb)
        self.assertRegex(fb, r"\.\.\. \[elided \d+ lines.*\] \.\.\.")
        self.assertLessEqual(len(fb), pilot_pr.TURN_FEEDBACK_MAX_CHARS + 120)

    def test_stale_tool_output_compaction_keeps_recent_and_initial(self):
        """Stage 1 compacts stale tool-result messages older than COMPACT_KEEP_RECENT_TURNS while preserving [0], [1], and recent turns."""
        big_body_0 = "Tool results:\n[1] read_file OK:\n" + "\n".join(f"{i:4d}: old_turn0_line_{i}" for i in range(100))
        big_body_1 = "Tool results:\n[1] grep OK:\n" + "\n".join(f"src.py:{i}: match_{i}" for i in range(80))
        recent_2 = "Tool results:\n[1] read_file OK:\nrecent_turn_2_content"
        recent_3 = "Tool results:\n[1] read_file OK:\nrecent_turn_3_content"

        msgs = [
            {"role": "system", "content": "SYSTEM_PROMPT_KEEP"},
            {"role": "user", "content": "INITIAL_TASK_PROMPT_KEEP"},
            {"role": "assistant", "content": "asst_0"},
            {"role": "user", "content": big_body_0},
            {"role": "assistant", "content": "asst_1"},
            {"role": "user", "content": big_body_1},
            {"role": "assistant", "content": "asst_2"},
            {"role": "user", "content": recent_2},
            {"role": "assistant", "content": "asst_3"},
            {"role": "user", "content": recent_3},
        ]
        meta = [
            {}, {},
            {"turn": 0, "tools": [{"tool": "read_file", "args": {"path": "a.py", "start": 1, "end": 100}, "ok": True, "result_chars": len(big_body_0)}]},
            {"turn": 0, "tools": [{"tool": "read_file", "args": {"path": "a.py", "start": 1, "end": 100}, "ok": True, "result_chars": len(big_body_0)}]},
            {"turn": 1, "tools": [{"tool": "grep", "args": {"pattern": "foo", "path": "."}, "ok": True, "result_chars": len(big_body_1)}]},
            {"turn": 1, "tools": [{"tool": "grep", "args": {"pattern": "foo", "path": "."}, "ok": True, "result_chars": len(big_body_1)}]},
            {"turn": 2, "tools": []}, {"turn": 2, "tools": []},
            {"turn": 3, "tools": []}, {"turn": 3, "tools": []},
        ]

        comp_msgs, comp_meta, ev = pilot_pr.compact_conversation_messages(msgs, msg_meta=meta)
        self.assertTrue(ev["compacted"])
        self.assertIn("stale_tool_summary", ev["stages"])
        self.assertEqual(ev["msgs_compacted"], 2)
        self.assertEqual(ev["msgs_dropped"], 0)
        self.assertGreater(ev["chars_saved"], 2000)

        # System + initial user prompt untouched
        self.assertEqual(comp_msgs[0]["content"], "SYSTEM_PROMPT_KEEP")
        self.assertEqual(comp_msgs[1]["content"], "INITIAL_TASK_PROMPT_KEEP")
        # Stale user tool messages (turns 0, 1) summarized with tool/path info
        self.assertTrue(comp_msgs[3]["content"].startswith("[compacted stale tool output from turn 0"))
        self.assertIn("read_file(path='a.py'", comp_msgs[3]["content"])
        self.assertTrue(comp_msgs[5]["content"].startswith("[compacted stale tool output from turn 1"))
        self.assertIn("grep(path='.', pattern='foo')", comp_msgs[5]["content"])
        # Recent 2 user messages kept verbatim
        self.assertEqual(comp_msgs[7]["content"], recent_2)
        self.assertEqual(comp_msgs[9]["content"], recent_3)

        # Idempotent on immediate second call
        comp_msgs2, _, ev2 = pilot_pr.compact_conversation_messages(comp_msgs, msg_meta=comp_meta)
        self.assertFalse(ev2["compacted"])
        self.assertEqual(comp_msgs2, comp_msgs)

    def test_budget_driven_stage2_assistant_summary_and_stale_turn_drop(self):
        """Stage 2 progressively summarizes stale assistant payloads, reduces recent turns, and drops oldest pairs to stay under max_prompt_tokens."""
        msgs = [
            {"role": "system", "content": "SYS"},
            {"role": "user", "content": "TASK"},
        ]
        meta = [{}, {}]
        for t in range(6):
            asst_payload = f"```json\n{{\"tool\": \"create_file\", \"args\": {{\"path\": \"f{t}.py\", \"content\": \"" + ("Q" * 3000) + "\"}}}\n```"
            user_payload = f"Tool results:\n[1] read_file OK:\n" + "\n".join(f"t{t}_l{j}: " + ("W" * 80) for j in range(40))
            msgs.append({"role": "assistant", "content": asst_payload})
            meta.append({"turn": t, "tools": [{"tool": "create_file", "args": {"path": f"f{t}.py"}, "ok": True, "result_chars": 3000}]})
            msgs.append({"role": "user", "content": user_payload})
            meta.append({"turn": t, "tools": [{"tool": "read_file", "args": {"path": f"f{t}.py"}, "ok": True, "result_chars": len(user_payload)}]})

        # Tight slot_ctx so Stage 1 alone is not enough and Stage 2a/2b/2c must engage
        slot_ctx = 3000
        reserved = 500  # max_prompt_tokens = 2500
        comp_msgs, _, ev = pilot_pr.compact_conversation_messages(
            msgs,
            slot_ctx=slot_ctx,
            reserved_output=reserved,
            msg_meta=meta,
        )
        self.assertTrue(ev["compacted"])
        self.assertIn("stale_tool_summary", ev["stages"])
        self.assertIn("stale_assistant_summary", ev["stages"])
        self.assertLessEqual(ev["tokens_after"], slot_ctx - reserved)
        self.assertEqual(comp_msgs[0]["content"], "SYS")
        self.assertEqual(comp_msgs[1]["content"], "TASK")
        self.assertGreaterEqual(len(comp_msgs), 4)

    def test_budget_driven_compaction_prevents_midrun_overflow_and_logs_events(self):
        """Simulated 7-turn read-heavy loop avoids context_overflow via compaction and emits visible COMPACTION logs & turn_events."""
        temp_dir = tempfile.mkdtemp(prefix="pilot_v3_compact_loop_")
        run_dir = tempfile.mkdtemp(prefix="pilot_v3_compact_run_")
        try:
            subprocess.run(["git", "init", "-q"], cwd=temp_dir, check=True)
            subprocess.run(["git", "config", "user.name", "Tester"], cwd=temp_dir, check=True)
            subprocess.run(["git", "config", "user.email", "tester@example.org"], cwd=temp_dir, check=True)
            # Create a 600-line file (240 lines per read_file window would rapidly overflow without compaction)
            big_file = os.path.join(temp_dir, "big_mod.py")
            with open(big_file, "w", encoding="utf-8") as f:
                f.write("def target():\n    return 0\n")
                for i in range(600):
                    f.write(f"# filler line {i:04d} " + ("x" * 60) + "\n")
            with open(os.path.join(temp_dir, "test_big.py"), "w", encoding="utf-8") as f:
                f.write("import big_mod\nassert big_mod.target() == 7\n")
            subprocess.run(["git", "add", "."], cwd=temp_dir, check=True)
            subprocess.run(["git", "commit", "-q", "-m", "base"], cwd=temp_dir, check=True)
            base_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=temp_dir, text=True).strip()

            task = {
                "id": "mock_overflow_prone",
                "pr_number": 913,
                "title": "Simulated pr13-style heavy reads",
                "base_commit": base_sha,
                "merged_commit": "a" * 40,
                "has_tests": True,
                "test_cmd": "python3 test_big.py",
                "prompt": "Read big_mod.py across slices and update target() to return 7.",
                "files": ["big_mod.py"],
            }

            turn_idx = [0]
            seen_prompt_tokens = []

            def char_proportional_counter(msgs):
                return pilot_pr.estimate_tokens_heuristic(msgs)

            def heavy_reader_model(messages, seed):
                t = turn_idx[0]
                turn_idx[0] += 1
                seen_prompt_tokens.append(char_proportional_counter(messages))
                if t < 5:
                    start_ln = 1 + t * 100
                    calls = [
                        {"tool": "read_file", "args": {"path": "big_mod.py", "start": start_ln, "end": start_ln + 240}},
                    ]
                    return {"content": "```json\n" + json.dumps(calls) + "\n```", "usage": {"completion_tokens": 35}}
                calls = [
                    {"tool": "search_replace", "args": {"path": "big_mod.py", "old": "return 0", "new": "return 7"}},
                    {"tool": "finish", "args": {"summary": "updated target to return 7"}},
                ]
                return {"content": "```json\n" + json.dumps(calls) + "\n```", "usage": {"completion_tokens": 40}}

            buf = io.StringIO()
            with redirect_stdout(buf):
                res = pilot_pr.run_task_loop(
                    task,
                    heavy_reader_model,
                    temp_dir,
                    max_turns=8,
                    slot_ctx=8000,
                    reserved_output_tokens=1500,  # max_prompt_tokens = 6500
                    token_counter=char_proportional_counter,
                    run_dir=run_dir,
                    label="compact-sim",
                )
            stdout_text = buf.getvalue()

            self.assertTrue(res["passed"], f"Expected task to pass without overflow: {res}")
            self.assertEqual(res["stop_reason"], "pass")
            self.assertFalse(res["harness_failure"])
            self.assertGreater(res["compaction_events_total"], 0)
            self.assertGreater(res["compaction_chars_saved"], 0)
            self.assertTrue(all(pt <= 6500 for pt in seen_prompt_tokens), f"Prompt tokens exceeded budget: {seen_prompt_tokens}")
            # Visible compaction lines in stdout (captured in run.log)
            self.assertIn("COMPACTION task=mock_overflow_prone", stdout_text)
            self.assertIn("stage=tool_truncate", stdout_text)
            self.assertTrue(
                "stale_tool_summary" in stdout_text or "recent_tool_summary" in stdout_text,
                f"Expected history compaction stage in stdout:\n{stdout_text}",
            )

            # Compaction events logged to turn_events.jsonl
            events_path = os.path.join(run_dir, "turn_events.jsonl")
            self.assertTrue(os.path.exists(events_path))
            with open(events_path, "r", encoding="utf-8") as ef:
                events = [json.loads(line) for line in ef if line.strip()]
            comp_events = [e for e in events if e.get("event") == "compaction"]
            self.assertGreater(len(comp_events), 0)
            self.assertTrue(any(e.get("stage") == "tool_truncate" for e in comp_events))
            self.assertTrue(any(e.get("stage") == "history_compact" for e in comp_events))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
            shutil.rmtree(run_dir, ignore_errors=True)

    def test_v3_mechanical_selection_matches_frozen_list(self):
        """Mechanical selection script `select_v3.py` reproduces the exact frozen 7-PR list in `tasks_item6_v3.py`."""
        self.assertTrue(
            os.path.isdir(tasks_item6_v3.DEFAULT_V3_REPO_DIR),
            f"External bare repo missing at {tasks_item6_v3.DEFAULT_V3_REPO_DIR}",
        )
        frozen = tasks_item6_v3.load_tasks()
        self.assertEqual(len(frozen), 7)

        selected, excluded = select_v3.enumerate_and_filter_v3_prs(
            repo_dir=tasks_item6_v3.DEFAULT_V3_REPO_DIR,
            head_ref=tasks_item6_v3.V3_HEAD_COMMIT,
            verify_bwrap=True,
        )
        self.assertEqual(len(selected), 7)
        self.assertGreater(len(excluded), 0)

        self.assertEqual(
            [p["pr_number"] for p in selected],
            [t["pr_number"] for t in frozen],
        )
        for p, t in zip(selected, frozen):
            self.assertEqual(p["base_commit"], t["base_commit"])
            self.assertEqual(p["merged_commit"], t["merged_commit"])
            self.assertEqual(p["merged_at_utc"], t["merged_at_utc"])
            self.assertEqual(p["files"], sorted(t["files"]))
            self.assertEqual(p["test_files"], sorted(t["test_files"]))
            self.assertEqual(p["test_cmd"], t["test_cmd"])
            self.assertEqual(p["expected_test_count"], t["grade_spec"]["expected_test_count"])
            self.assertEqual(p["total_changed_lines"], t["total_changed_lines"])
            self.assertGreaterEqual(p["total_changed_lines"], select_v3.V3_MIN_CHANGED_LINES)
            self.assertLessEqual(p["total_changed_lines"], select_v3.V3_MAX_CHANGED_LINES)

    def test_v3_contamination_cutoff_post_qwen36_release(self):
        """All 7 unseen v3 PRs are from an external repo and merged strictly after Qwen3.6-35B-A3B release (2026-04-15)."""
        cutoff = datetime.fromisoformat(tasks_item6_v3.QWEN36_RELEASE_UTC.replace("Z", "+00:00"))
        win_start = datetime.fromisoformat(select_v3.V3_WINDOW_START.replace("Z", "+00:00"))
        win_end = datetime.fromisoformat(select_v3.V3_WINDOW_END.replace("Z", "+00:00"))
        self.assertGreater(win_start, cutoff)
        self.assertNotEqual(tasks_item6_v3.V3_REPO_SLUG.lower(), "ajeswint/strix-halo-lab")
        self.assertIn("huggingface.co/Qwen/Qwen3.6-35B-A3B", tasks_item6_v3.QWEN36_RELEASE_SOURCE)

        v2_prs = {t["pr_number"] for t in tasks_item6.load_tasks()}
        for t in tasks_item6_v3.load_tasks():
            self.assertNotIn(t["pr_number"], v2_prs)
            self.assertEqual(t["repo_slug"], "more-itertools/more-itertools")
            dt = datetime.fromisoformat(t["merged_at_utc"].replace("Z", "+00:00"))
            self.assertGreater(dt, cutoff, f"PR #{t['pr_number']} merged before Qwen3.6 release!")
            self.assertTrue(win_start <= dt <= win_end)

    def test_v3_prompts_built_strictly_by_rule_no_code_blocks_no_leaks(self):
        """Every v3 task prompt matches the deterministic rule output, strips code blocks, and passes exploding-dict leak guards."""
        for t in tasks_item6_v3.load_tasks():
            rebuilt = tasks_item6_v3.build_v3_task_prompt(
                t["repo_slug"],
                t["source_kind"],
                t["raw_source_title"],
                t["raw_source_body"],
            )
            self.assertEqual(t["prompt"], rebuilt)
            self.assertNotIn("```", t["prompt"])
            self.assertNotIn("~~~", t["prompt"])
            self.assertNotIn("104729", t["prompt"])
            self.assertNotIn(t["merged_commit"], t["prompt"])
            self.assertNotIn(t["merged_commit"][:10], t["prompt"])

            exploding = ExplodingTaskDict(t)
            clean = tasks_item6_v3.strip_hidden(exploding)
            self.assertNotIn("merged_commit", clean)
            self.assertNotIn("hidden_diff", clean)
            self.assertNotIn("test_files", clean)
            self.assertNotIn("grade_spec", clean)

            msgs = pilot_pr.format_tool_messages(clean)
            pilot_pr.check_prompt_leak(msgs, t, run_sentinel=pilot_pr.generate_run_sentinel())

    def test_v3_all_seven_tasks_fail_at_base_and_pass_at_merged_in_bwrap(self):
        """Offline CPU check in bwrap: every v3 task's merged tests FAIL at base_commit and PASS at merged_commit."""
        repo_dir = tasks_item6_v3.DEFAULT_V3_REPO_DIR
        self.assertTrue(os.path.isdir(repo_dir), f"External bare repo missing: {repo_dir}")
        for t in tasks_item6_v3.load_tasks():
            # Empty diff (base_commit) must FAIL under read-only merged test files
            base_ok, base_out = pilot_pr.regrade_task_diff(t, "", repo_root=repo_dir, timeout=120)
            self.assertFalse(
                base_ok,
                f"Expected {t['id']} to FAIL at base_commit under merged tests, got PASS:\n{base_out[:400]}",
            )
            # Reference diff (merged_commit) must PASS under read-only merged test files with exact expected_test_count
            hidden_diff = tasks_item6_v3.get_hidden_diff(t, repo_root=repo_dir)
            self.assertTrue(hidden_diff.strip(), f"Empty hidden diff for {t['id']}")
            merged_ok, merged_out = pilot_pr.regrade_task_diff(t, hidden_diff, repo_root=repo_dir, timeout=120)
            self.assertTrue(
                merged_ok,
                f"Expected {t['id']} to PASS at merged_commit in bwrap, got FAIL:\n{merged_out[:600]}",
            )

    def test_v3_prereg_doc_section_15_4_shas_match_tasks_and_mirror(self):
        """Section 15.4 table in docs/item6-pilot.md matches tasks_item6_v3.py and mirror first-parent base SHAs verbatim."""
        repo_root = os.path.abspath(os.path.join(HERE, "..", ".."))
        doc_path = os.path.join(repo_root, "docs", "item6-pilot.md")
        with open(doc_path, "r", encoding="utf-8") as f:
            doc_text = f.read()

        m = re.search(r"### 15\.4 Frozen v3 Unseen Task List.*?\n(.*?)\n### 15\.5 ", doc_text, re.DOTALL)
        self.assertIsNotNone(m, "Section 15.4 table not found in docs/item6-pilot.md")
        sec = m.group(1)

        table_rows = {}
        for line in sec.splitlines():
            line = line.strip()
            if not line.startswith("| `item6v3_pr"):
                continue
            cols = [c.strip() for c in line.strip("|").split("|")]
            self.assertGreaterEqual(len(cols), 9, f"Unexpected Section 15.4 table row: {line}")
            tid = cols[0].strip("`")
            pr_num = int(cols[1].lstrip("#"))
            merged_utc = cols[2].strip("`")
            lines_cnt = int(cols[3])
            base_sha = cols[4].strip("`")
            test_cmd = cols[6].strip("`")
            exp_tests = int(cols[7])
            table_rows[tid] = {
                "pr_number": pr_num,
                "merged_at_utc": merged_utc,
                "total_changed_lines": lines_cnt,
                "base_commit": base_sha,
                "test_cmd": test_cmd,
                "expected_test_count": exp_tests,
            }

        frozen = tasks_item6_v3.load_tasks()
        self.assertEqual(len(table_rows), len(frozen), f"Expected {len(frozen)} rows in Section 15.4, found {len(table_rows)}")
        mirror = tasks_item6_v3.DEFAULT_V3_REPO_DIR
        self.assertTrue(os.path.isdir(mirror), f"External bare mirror missing: {mirror}")

        for t in frozen:
            tid = t["id"]
            self.assertIn(tid, table_rows, f"Missing {tid} in docs/item6-pilot.md Section 15.4")
            row = table_rows[tid]
            self.assertEqual(row["pr_number"], t["pr_number"])
            self.assertEqual(row["merged_at_utc"], t["merged_at_utc"])
            self.assertEqual(row["total_changed_lines"], t["total_changed_lines"])
            self.assertEqual(len(row["base_commit"]), 40, f"Base SHA for {tid} must be full 40 chars")
            self.assertEqual(row["base_commit"], t["base_commit"], f"Section 15.4 base SHA mismatch for {tid}")
            self.assertEqual(row["test_cmd"], t["test_cmd"])
            self.assertEqual(row["expected_test_count"], t["grade_spec"]["expected_test_count"])

            # Cross-check against pinned external bare mirror first parent of merged_commit
            mirror_base = subprocess.check_output(
                ["git", "-C", mirror, "rev-parse", f"{t['merged_commit']}^1"],
                text=True,
            ).strip()
            self.assertEqual(t["base_commit"], mirror_base, f"tasks_item6_v3 base SHA mismatch vs mirror for {tid}")

    def test_v3_launchers_guards_freeze_and_practice_config(self):
        """Verify syntax, freeze guards (across ALL Item 6 launchers), placeholder refusal, and pre-registered settings."""
        repo_root = os.path.abspath(os.path.join(HERE, "..", ".."))
        legacy_sh = os.path.join(repo_root, "bench", "loop", "runs", "item6-pilot", "run.sh")
        practice_sh = os.path.join(repo_root, "bench", "loop", "runs", "item6-v3-practice", "run.sh")
        v3_sh = os.path.join(repo_root, "bench", "loop", "runs", "item6-pilot-v3", "run.sh")

        for sh in (legacy_sh, practice_sh, v3_sh):
            self.assertTrue(os.path.isfile(sh), f"Missing launcher: {sh}")
            chk = subprocess.run(["bash", "-n", sh], capture_output=True, text=True)
            self.assertEqual(chk.returncode, 0, f"bash -n failed for {sh}: {chk.stderr}")

            with open(sh, "r", encoding="utf-8") as f:
                sh_txt = f.read()
            # No launcher may default to a frozen label
            self.assertNotIn('LABEL="${LABEL:-item6-pilot}"', sh_txt, f"{sh} must not default to frozen item6-pilot")
            self.assertNotIn('LABEL="${LABEL:-item6-pilot-v2}"', sh_txt, f"{sh} must not default to frozen item6-pilot-v2")

            # Every Item 6 launcher refuses both frozen v1 and v2 labels
            for frozen_lbl in ("item6-pilot", "item6-pilot-v2"):
                env = dict(os.environ, WT=repo_root, EXPECT_HEAD="0" * 40, LABEL=frozen_lbl)
                res = subprocess.run(["bash", sh], cwd=repo_root, env=env, capture_output=True, text=True)
                self.assertNotEqual(res.returncode, 0, f"{sh} must refuse frozen label {frozen_lbl}")
                self.assertIn("frozen", res.stderr.lower())

            # Refuses placeholder WT
            env_wt = dict(os.environ, EXPECT_HEAD="0" * 40)
            env_wt.pop("WT", None)
            env_wt.pop("LABEL", None)
            res_wt = subprocess.run(["bash", sh], cwd=repo_root, env=env_wt, capture_output=True, text=True)
            self.assertNotEqual(res_wt.returncode, 0)
            self.assertIn("WT must be set", res_wt.stderr)

        # Legacy item6-pilot launcher must also refuse unset/empty LABEL when WT and EXPECT_HEAD are set
        env_no_lbl = dict(os.environ, WT=repo_root, EXPECT_HEAD="0" * 40)
        env_no_lbl.pop("LABEL", None)
        res_no_lbl = subprocess.run(["bash", legacy_sh], cwd=repo_root, env=env_no_lbl, capture_output=True, text=True)
        self.assertNotEqual(res_no_lbl.returncode, 0)
        self.assertIn("LABEL must be set", res_no_lbl.stderr)

        with open(practice_sh, "r", encoding="utf-8") as f:
            prac_txt = f.read()
        self.assertIn("CEILING_SECONDS=\"${CEILING_SECONDS:-1851}\"", prac_txt)
        self.assertIn("TASK_WALL_BUDGET=\"${TASK_WALL_BUDGET:-617}\"", prac_txt)
        self.assertIn('"item6_pr13"', prac_txt)
        self.assertIn('"item6_pr14"', prac_txt)
        self.assertIn('"item6_pr16"', prac_txt)
        self.assertIn("INVITE_OPTS=(--ctx 65536 --np 1)", prac_txt)
        self.assertIn("prereg-guard.sh --head", prac_txt)
        self.assertNotIn("pilot_pr.py grade", prac_txt)
        self.assertIn("context_overflow", prac_txt)
        self.assertIn("harness_failure", prac_txt)
        self.assertIn("COMPACTION ", prac_txt)

        with open(v3_sh, "r", encoding="utf-8") as f:
            v3_txt = f.read()
        self.assertIn("CEILING_SECONDS=\"${CEILING_SECONDS:-4320}\"", v3_txt)
        self.assertIn("TASK_WALL_BUDGET=\"${TASK_WALL_BUDGET:-617}\"", v3_txt)
        self.assertIn("INVITE_OPTS=(--ctx 65536 --np 1)", v3_txt)
        self.assertIn("total_slots 1 n_ctx 65536 ", v3_txt)
        self.assertIn("prereg-guard.sh --head", v3_txt)
        self.assertIn("--task-suite v3", v3_txt)
        for t in tasks_item6_v3.load_tasks():
            self.assertIn(f'"{t["id"]}"', v3_txt)

    def test_v3_run_and_grade_subcommand_plumbing_external_repo(self):
        """run_subcommand and grade_subcommand with task_suite='v3' operate cleanly against the external bare repo."""
        results_dir = tempfile.mkdtemp(prefix="pilot_v3_plumb_res_")
        run_dir = tempfile.mkdtemp(prefix="pilot_v3_plumb_run_")
        try:
            def mock_v3_ask(messages, seed):
                calls = [
                    {"tool": "read_file", "args": {"path": "more_itertools/more.py", "start": 1, "end": 20}},
                    {"tool": "create_file", "args": {"path": "v3_probe_note.txt", "content": "probe\n"}},
                    {"tool": "finish", "args": {"summary": "probe edit"}},
                ]
                return {"content": "```json\n" + json.dumps(calls) + "\n```", "usage": {"completion_tokens": 25}}

            rows = pilot_pr.run_subcommand(
                label="v3-plumb-test",
                tasks_arg="item6v3_pr1311",
                max_turns=1,
                results_dir=results_dir,
                run_dir=run_dir,
                ask_fn=mock_v3_ask,
                token_counter=lambda m: 1200,
                task_suite="v3",
                target_repo=tasks_item6_v3.DEFAULT_V3_REPO_DIR,
            )
            self.assertEqual(len(rows), 1)
            r = rows[0]
            self.assertEqual(r["task_id"], "item6v3_pr1311")
            self.assertEqual(r["schema_version"], pilot_pr.RECORD_SCHEMA_VERSION)
            self.assertFalse(r["harness_failure"])
            self.assertIn("v3_probe_note.txt", r["final_diff"])

            rev_path = os.path.join(results_dir, "v3-plumb-test.reviews.json")
            with open(rev_path, "w", encoding="utf-8") as rf:
                json.dump({
                    "item6v3_pr1311": {
                        "verdict": "REQUEST-CHANGES",
                        "hand_fix_lines": 10,
                        "tamper": False,
                        "fresh_session": True,
                    }
                }, rf)

            grade = pilot_pr.grade_subcommand(
                label="v3-plumb-test",
                reviews_file=rev_path,
                results_dir=results_dir,
                task_suite="v3",
                target_repo=tasks_item6_v3.DEFAULT_V3_REPO_DIR,
            )
            self.assertEqual(grade["tasks_evaluated"], 1)
            self.assertEqual(grade["testable_tasks"], 1)
            self.assertEqual(grade["testable_passed"], 0)
            self.assertEqual(grade["decision"], "DROP")
            self.assertFalse(grade["per_task"][0]["test_passed"])
        finally:
            shutil.rmtree(results_dir, ignore_errors=True)
            shutil.rmtree(run_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
