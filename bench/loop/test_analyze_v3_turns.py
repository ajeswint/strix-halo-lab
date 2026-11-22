#!/usr/bin/env python3
"""CPU-only unit tests for bench/loop/analyze_v3_turns.py."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import analyze_v3_turns  # noqa: E402


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


class TestAnalyzeV3Turns(unittest.TestCase):
    RESULTS_DIR = REPO_ROOT / "bench" / "loop" / "results"
    PILOT_SOURCE = HERE / "pilot_pr.py"
    SHA256SUMS_PATH = RESULTS_DIR / "item6-pilot-v3.SHA256SUMS"

    def _read_frozen_checksums(self) -> dict[str, str]:
        expected: dict[str, str] = {}
        for line in self.SHA256SUMS_PATH.read_text(encoding="utf-8").splitlines():
            line_s = line.strip()
            if not line_s:
                continue
            digest, rel_path = line_s.split(None, 1)
            expected[rel_path.strip()] = digest.strip()
        return expected

    def test_committed_v3_analysis_counts_and_immutability(self):
        """Running analyze_v3_turns on committed v3 records yields exact measured counts and mutates zero frozen files."""
        expected_hashes = self._read_frozen_checksums()
        self.assertEqual(len(expected_hashes), 13)
        sha_file_before = _sha256_file(self.SHA256SUMS_PATH)

        summary = analyze_v3_turns.analyze_v3_records(
            results_dir=self.RESULTS_DIR,
            pilot_source_path=self.PILOT_SOURCE,
        )

        # Verify every frozen result file and SHA256SUMS itself stayed byte-identical
        self.assertEqual(_sha256_file(self.SHA256SUMS_PATH), sha_file_before)
        for rel_path, expected_digest in expected_hashes.items():
            actual = _sha256_file(self.RESULTS_DIR / rel_path)
            self.assertEqual(actual, expected_digest, f"Frozen input mutated: {rel_path}")

        # Meta & official decision unchanged
        meta = summary["meta"]
        self.assertEqual(meta["scope_label"], "descriptive, post-hoc, n=7, one repo")
        self.assertEqual(meta["official_decision_unchanged"], "DROP")
        self.assertEqual(meta["tasks_analyzed"], 7)
        self.assertEqual(meta["turns_executed_total"], 72)

        cc = meta["compaction_cross_check"]
        self.assertEqual(cc["turn_events_compaction_total"], 38)
        self.assertEqual(cc["turn_events_by_stage"], {"history_compact": 34, "tool_truncate": 4})
        self.assertEqual(cc["turn_events_history_compact_substages"], {"stale_tool_summary": 34})
        self.assertEqual(cc["run_log_compaction_total"], 38)
        self.assertEqual(cc["jsonl_top_level_compaction_events_sum"], 38)
        self.assertEqual(cc["jsonl_top_level_compaction_chars_saved_sum"], 65809)
        self.assertEqual(cc["jsonl_history_compaction_entries_sum"], 36)
        self.assertEqual(len(cc["history_omitted_on_repeat_code_turns"]), 2)
        self.assertEqual(cc["peak_prompt_tokens"]["usage_max"]["tokens"], 4763)
        self.assertEqual(cc["peak_prompt_tokens"]["preflight_max"]["tokens"], 4946)
        self.assertEqual(cc["peak_prompt_tokens"]["pre_compaction_max"]["tokens"], 5905)

        # 1. repeat_code & file re-reads after compaction
        rc = summary["repeat_code_and_compaction"]
        self.assertEqual(rc["repeat_code_task_count"], 3)
        self.assertEqual(rc["repeat_code_tasks"], ["item6v3_pr1305", "item6v3_pr1322", "item6v3_pr1311"])
        self.assertFalse(rc["exact_duplicated_reply_recorded"])
        self.assertEqual(rc["same_turn_stage1_compaction_before_stop_count"], 2)

        cases_by_id = {c["task_id"]: c for c in rc["cases"]}
        # pr1305: stop turn 10, same-turn compaction True, 0 edits, 67 tok exact match on turn 8
        c1305 = cases_by_id["item6v3_pr1305"]
        self.assertEqual(c1305["stop_turn"], 10)
        self.assertTrue(c1305["stage1_compaction_immediately_before_stop"]["same_turn_history_compact"])
        self.assertFalse(c1305["stage1_compaction_immediately_before_stop"]["jsonl_history_recorded_compaction"])
        self.assertEqual(c1305["preceding_tool_calls"]["edit_count"], 0)
        self.assertEqual(c1305["preceding_tool_calls"]["read_only_count"], 9)
        self.assertEqual(
            [m["turn"] for m in c1305["duplicated_reply_proxy"]["exact_token_match_earlier_turns"]],
            [8],
        )

        # pr1322: stop turn 4, same-turn compaction False (last was turn 3), 0 edits, 43 tok exact match on turn 3
        c1322 = cases_by_id["item6v3_pr1322"]
        self.assertEqual(c1322["stop_turn"], 4)
        self.assertFalse(c1322["stage1_compaction_immediately_before_stop"]["same_turn_history_compact"])
        self.assertEqual(c1322["stage1_compaction_immediately_before_stop"]["most_recent_history_compact_turn"], 3)
        self.assertEqual(c1322["preceding_tool_calls"]["edit_count"], 0)
        self.assertEqual(c1322["preceding_tool_calls"]["read_only_count"], 2)
        self.assertEqual(
            [m["turn"] for m in c1322["duplicated_reply_proxy"]["exact_token_match_earlier_turns"]],
            [3],
        )

        # pr1311: stop turn 7, same-turn compaction True, 0 edits, 497 tok > all earlier turns (max 210)
        c1311 = cases_by_id["item6v3_pr1311"]
        self.assertEqual(c1311["stop_turn"], 7)
        self.assertTrue(c1311["stage1_compaction_immediately_before_stop"]["same_turn_history_compact"])
        self.assertEqual(c1311["preceding_tool_calls"]["edit_count"], 0)
        self.assertEqual(c1311["preceding_tool_calls"]["read_only_count"], 9)
        self.assertTrue(c1311["duplicated_reply_proxy"]["stop_turn_exceeds_all_earlier_turns"])
        self.assertEqual(c1311["duplicated_reply_proxy"]["exact_token_match_earlier_turns"], [])

        rereads = rc["file_rereads_after_compaction"]
        self.assertEqual(rereads["overall"]["total_read_file_calls"], 36)
        self.assertEqual(rereads["overall"]["rereads_same_path_after_compact"], 21)
        self.assertEqual(rereads["overall"]["rereads_overlapping_range_after_compact"], 17)
        self.assertEqual(rereads["overall"]["rereads_exact_range_after_compact"], 2)
        self.assertEqual(
            {k: v["rereads_same_path_after_compact"] for k, v in rereads["per_task"].items()},
            {
                "item6v3_pr1260": 6,
                "item6v3_pr1269": 5,
                "item6v3_pr1305": 3,
                "item6v3_pr1322": 0,
                "item6v3_pr1342": 3,
                "item6v3_pr1345": 3,
                "item6v3_pr1311": 1,
            },
        )

        # 2. turn_parse_error
        pe = summary["turn_parse_errors"]
        self.assertEqual(pe["total_count"], 7)
        self.assertEqual(pe["tasks_affected_count"], 4)
        self.assertFalse(pe["raw_model_snippet_recorded"])
        self.assertEqual(
            pe["by_error_class"],
            {
                "json_expecting_comma_delimiter": 2,
                "json_extra_data": 2,
                "json_expecting_value": 1,
                "no_valid_tool_calls": 2,
            },
        )
        self.assertTrue(all(ev["result_chars_matches_err_len"] for ev in pe["events"]))

        # 3. Completion-length distribution & short turns
        cl = summary["completion_length_distribution"]
        self.assertFalse(cl["reasoning_tokens_recorded"])
        self.assertFalse(cl["reasoning_chars_recorded"])
        self.assertEqual(cl["reasoning_related_keys_in_committed_records"], [])
        self.assertEqual(cl["overall"]["turns_count"], 72)
        self.assertEqual(cl["overall"]["total_completion_tokens"], 22472)
        self.assertEqual(cl["overall"]["min"], 43)
        self.assertEqual(cl["overall"]["median"], 79.0)
        self.assertEqual(cl["overall"]["max"], 4213)
        self.assertEqual(cl["short_turns_lt100"]["count"], 41)
        self.assertEqual(
            cl["short_turns_lt100"]["by_turn_own_outcome"],
            {"read_only_tool_call": 35, "parse_error": 3, "repeat_code": 2, "edit_tool_call": 1},
        )

        # 4. Tool usage & reachability
        tu = summary["tool_usage_and_reachability"]
        self.assertEqual(tu["overall"]["total_tool_calls"], 71)
        self.assertEqual(tu["overall"]["by_tool"]["read_file"], {"total": 36, "ok": 36, "error": 0})
        self.assertEqual(tu["overall"]["by_tool"]["grep"], {"total": 28, "ok": 28, "error": 0})
        self.assertEqual(tu["overall"]["by_tool"]["search_replace"], {"total": 7, "ok": 5, "error": 2})
        self.assertEqual(tu["overall"]["by_tool"]["list_files"]["total"], 0)
        self.assertEqual(tu["overall"]["by_tool"]["create_file"]["total"], 0)
        self.assertTrue(tu["overall"]["run_tests_never_used"])
        self.assertTrue(tu["overall"]["finish_never_used"])

        ri = tu["reachability_inspection"]
        self.assertFalse(ri["uses_openai_tools_param"])
        self.assertTrue(ri["run_tests_in_system_prompt"])
        self.assertTrue(ri["run_tests_in_user_prompt"])
        self.assertTrue(ri["run_tests_in_dispatch"])
        self.assertTrue(ri["finish_in_system_prompt"])
        self.assertTrue(ri["finish_in_user_prompt"])
        self.assertTrue(ri["finish_in_final_turn_note"])
        self.assertTrue(ri["finish_in_dispatch"])
        self.assertFalse(ri["rules_section_mentions_run_tests"])
        for cite_name, cite_val in ri["code_citations"].items():
            self.assertIsNotNone(cite_val, f"Missing code citation: {cite_name}")
            if isinstance(cite_val, list):
                self.assertEqual(len(cite_val), 2)
                self.assertIsInstance(cite_val[0], int)
                self.assertIsInstance(cite_val[1], int)
                self.assertLessEqual(cite_val[0], cite_val[1])
            else:
                self.assertIsInstance(cite_val, int)

        # 5. dirty_since_last_test & pr1342 false pass
        dl = summary["dirty_since_last_test_and_pr1342_false_pass"]
        self.assertEqual(
            dl["tasks_triggering_end_of_loop_check"],
            ["item6v3_pr1269", "item6v3_pr1342", "item6v3_pr1345"],
        )
        self.assertEqual(dl["false_pass_tasks"], ["item6v3_pr1342"])
        self.assertTrue(dl["pr1342_detail"]["in_loop_passed"])
        self.assertFalse(dl["pr1342_detail"]["offline_test_passed"])
        self.assertFalse(dl["pr1342_detail"]["touched_test_file"])
        self.assertEqual(dl["pr1342_detail"]["successful_edit_turns"], [6])
        self.assertEqual(dl["pr1342_detail"]["failed_edit_turns"], [5])

    def test_committed_analysis_json_matches_fresh_run(self):
        """If item6-pilot-v3.analysis.json is present, it matches a fresh deterministic CLI run byte-for-byte."""
        committed_json = self.RESULTS_DIR / "item6-pilot-v3.analysis.json"
        if not committed_json.exists():
            self.skipTest("item6-pilot-v3.analysis.json not yet generated")
        with tempfile.TemporaryDirectory(prefix="analyze_v3_det_") as td:
            out_path = Path(td) / "out.json"
            rc = analyze_v3_turns.main(
                [
                    "--results-dir",
                    str(self.RESULTS_DIR),
                    "--pilot-source",
                    str(self.PILOT_SOURCE),
                    "--output",
                    str(out_path),
                ]
            )
            self.assertEqual(rc, 0)
            self.assertEqual(
                committed_json.read_text(encoding="utf-8"),
                out_path.read_text(encoding="utf-8"),
            )

    def test_synthetic_fixture_edge_cases(self):
        """Synthetic fixture verifies repeat_code, overlapping vs disjoint re-reads, and false-pass detection."""
        with tempfile.TemporaryDirectory(prefix="analyze_v3_syn_") as td:
            root = Path(td)
            run1 = root / "syn.run1"
            diffs = root / "syn.diffs"
            run1.mkdir()
            diffs.mkdir()

            jsonl_rows = [
                {
                    "task_id": "t_repeat",
                    "pr_number": 1,
                    "has_tests": True,
                    "passed": False,
                    "stop_reason": "repeat_code",
                    "diff_empty": True,
                    "turns_executed": 3,
                    "total_completion_tokens": 180,
                    "compaction_events_total": 1,
                    "compaction_chars_saved": 500,
                    "history": [
                        {
                            "turn": 0,
                            "tokens": 60,
                            "prompt_tokens": 500,
                            "preflight_prompt_tokens": 520,
                            "gen_s": 1.0,
                            "err": "",
                            "tool_calls": [{"tool": "read_file", "ok": True}],
                            "compaction": [],
                        },
                        {
                            "turn": 1,
                            "tokens": 60,
                            "prompt_tokens": 600,
                            "preflight_prompt_tokens": 620,
                            "gen_s": 1.0,
                            "err": "",
                            "tool_calls": [{"tool": "read_file", "ok": True}],
                            "compaction": [],
                        },
                        {
                            "turn": 2,
                            "tokens": 60,
                            "prompt_tokens": 550,
                            "preflight_prompt_tokens": 570,
                            "gen_s": 1.0,
                            "err": "repeat_code",
                            "stop": "repeat_code",
                        },
                    ],
                },
                {
                    "task_id": "t_false_pass",
                    "pr_number": 2,
                    "has_tests": True,
                    "passed": True,
                    "stop_reason": "pass",
                    "diff_empty": False,
                    "turns_executed": 12,
                    "total_completion_tokens": 1200,
                    "compaction_events_total": 0,
                    "compaction_chars_saved": 0,
                    "history": [
                        {
                            "turn": t,
                            "tokens": 100,
                            "prompt_tokens": 500,
                            "preflight_prompt_tokens": 520,
                            "gen_s": 1.0,
                            "err": "",
                            "tool_calls": [{"tool": "search_replace" if t == 0 else "read_file", "ok": True}],
                            "compaction": [],
                        }
                        for t in range(12)
                    ],
                },
            ]
            (root / "syn.jsonl").write_text(
                "\n".join(json.dumps(r) for r in jsonl_rows) + "\n", encoding="utf-8"
            )
            turn_events = [
                {
                    "ts": "2026-11-22T00:00:00Z",
                    "task_id": "t_repeat",
                    "turn": 0,
                    "event": "turn_tools",
                    "prompt_tokens": 500,
                    "completion_tokens": 60,
                    "tools": [{"tool": "read_file", "args": {"path": "a.py", "start": 1, "end": 50}, "ok": True, "result_chars": 400}],
                },
                {
                    "ts": "2026-11-22T00:00:01Z",
                    "task_id": "t_repeat",
                    "turn": 1,
                    "event": "compaction",
                    "stage": "history_compact",
                    "stages": ["stale_tool_summary"],
                    "msgs_compacted": 1,
                    "chars_before": 1000,
                    "chars_after": 500,
                    "chars_saved": 500,
                    "tokens_before": 300,
                    "tokens_after": 150,
                    "tokens_saved": 150,
                    "max_prompt_tokens": 57344,
                    "target_tokens": 43008,
                },
                {
                    "ts": "2026-11-22T00:00:02Z",
                    "task_id": "t_repeat",
                    "turn": 1,
                    "event": "turn_tools",
                    "prompt_tokens": 600,
                    "completion_tokens": 60,
                    "tools": [{"tool": "read_file", "args": {"path": "a.py", "start": 100, "end": 150}, "ok": True, "result_chars": 400}],
                },
            ]
            (run1 / "turn_events.jsonl").write_text(
                "\n".join(json.dumps(e) for e in turn_events) + "\n", encoding="utf-8"
            )
            (run1 / "run.log").write_text(
                "COMPACTION task=t_repeat turn=1 stage=stale_tool_summary msgs_compacted=1 msgs_dropped=0 chars=1000->500 tokens=300->150\n",
                encoding="utf-8",
            )
            (diffs / "t_repeat.diff").write_text("", encoding="utf-8")
            (diffs / "t_false_pass.diff").write_text(
                "diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n-x=1\n+x=2\n",
                encoding="utf-8",
            )
            (root / "syn.grade.json").write_text(
                json.dumps(
                    {
                        "decision": "DROP",
                        "testable_passed": 0,
                        "testable_tasks": 2,
                        "approved_final": 0,
                        "per_task": [
                            {"task_id": "t_repeat", "test_passed": False, "final_verdict": "NON-APPROVAL", "hand_fix_lines": None},
                            {"task_id": "t_false_pass", "test_passed": False, "final_verdict": "REQUEST-CHANGES", "hand_fix_lines": 5},
                        ],
                    }
                ),
                encoding="utf-8",
            )

            out = analyze_v3_turns.analyze_v3_records(root, self.PILOT_SOURCE, label="syn")
            rr = out["repeat_code_and_compaction"]["file_rereads_after_compaction"]["overall"]
            self.assertEqual(rr["rereads_same_path_after_compact"], 1)
            self.assertEqual(rr["rereads_overlapping_range_after_compact"], 0)
            self.assertEqual(rr["rereads_exact_range_after_compact"], 0)
            self.assertEqual(out["dirty_since_last_test_and_pr1342_false_pass"]["false_pass_tasks"], ["t_false_pass"])


if __name__ == "__main__":
    unittest.main()
