#!/usr/bin/env python3
"""CPU-only post-hoc analysis of Item 6 Pilot v3 turn events and committed records.

Reads only committed v3 artifacts under bench/loop/results/ plus bench/loop/pilot_pr.py
(for exact line citations and tool/prompt reachability checks). Does not mutate inputs,
does not invoke any model or GPU, does not access network, and does not read hidden
tests or reference solutions.

Scope: descriptive, post-hoc, n=7, one repo. Does not alter the frozen DROP decision.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
import os
from pathlib import Path
import re
import statistics
import subprocess
import sys
from typing import Any

# Commit SHA of bench/loop/pilot_pr.py that actually executed Item 6 Pilot v3 (docs/item6-pilot.md Section 16).
V3_RUN_GIT_REV = "ddcbbfb94403926c46644eaac978db268f8df848"

KNOWN_TOOLS = (
    "list_files",
    "grep",
    "read_file",
    "search_replace",
    "create_file",
    "run_tests",
    "finish",
)
READ_ONLY_TOOLS = frozenset({"list_files", "grep", "read_file"})
EDIT_TOOLS = frozenset({"search_replace", "create_file"})
VERIFY_TOOLS = frozenset({"run_tests", "finish"})

SHORT_TURN_THRESHOLD = 100
ERROR_SNIPPET_MAX_CHARS = 160


def _percentile(sorted_vals: list[int | float], q: float) -> float:
    """Linear-interpolated percentile on an already-sorted non-empty list."""
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return float(sorted_vals[0])
    pos = (len(sorted_vals) - 1) * q
    lo = int(pos)
    hi = min(len(sorted_vals) - 1, lo + 1)
    frac = pos - lo
    return round(sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * frac, 2)


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line_s = line.strip()
            if line_s:
                rows.append(json.loads(line_s))
    return rows


def _classify_parse_error(err_msg: str) -> tuple[str, str]:
    """Classify a turn_parse_error message and return (error_class, pilot_pr_code_path)."""
    msg = (err_msg or "").strip()
    if "Expecting ',' delimiter" in msg:
        return (
            "json_expecting_comma_delimiter",
            "extract_tool_calls -> json.loads JSONDecodeError (bench/loop/pilot_pr.py:1261-1265)",
        )
    if "Extra data:" in msg:
        return (
            "json_extra_data",
            "extract_tool_calls -> json.loads JSONDecodeError (bench/loop/pilot_pr.py:1261-1265)",
        )
    if "Expecting value:" in msg:
        return (
            "json_expecting_value",
            "extract_tool_calls -> json.loads JSONDecodeError (bench/loop/pilot_pr.py:1261-1265)",
        )
    if msg.startswith("Invalid JSON in tool block:"):
        return (
            "json_other_decode_error",
            "extract_tool_calls -> json.loads JSONDecodeError (bench/loop/pilot_pr.py:1261-1265)",
        )
    if msg.startswith("No valid tool calls found."):
        return (
            "no_valid_tool_calls",
            "_run_task_loop_turns empty-calls fallback (bench/loop/pilot_pr.py:2281-2287)",
        )
    if msg.startswith("JSON object is not a valid tool call"):
        return (
            "invalid_tool_call_object",
            "extract_tool_calls -> _normalize_tool_call_obj (bench/loop/pilot_pr.py:1268-1272)",
        )
    return (
        "other_parse_error",
        "_run_task_loop_turns parse error branch (bench/loop/pilot_pr.py:2281-2303)",
    )


def _classify_history_turn(entry: dict[str, Any]) -> str:
    """Classify a single history entry into a compact outcome label."""
    if entry.get("stop") == "repeat_code":
        return "repeat_code"
    if entry.get("stop") == "repeat_error":
        return "repeat_error"
    if entry.get("stop") in ("context_overflow", "request_error", "task_wall_budget", "prompt_leak"):
        return str(entry["stop"])
    tool_calls = entry.get("tool_calls") or []
    if not tool_calls and entry.get("err"):
        return "parse_error"
    tools = [tc.get("tool", "") for tc in tool_calls]
    if any(t in VERIFY_TOOLS for t in tools):
        return "verify_finish_call"
    if any(t in EDIT_TOOLS for t in tools):
        return "edit_tool_call"
    if tools:
        return "read_only_tool_call"
    return "empty_turn"


def _parse_run_log_compactions(run_log_path: Path) -> list[dict[str, Any]]:
    """Extract COMPACTION lines (with 1-based line numbers) from run.log."""
    entries: list[dict[str, Any]] = []
    pat = re.compile(r"^COMPACTION\s+task=(\S+)\s+turn=(\d+)\s+stage=(\S+)(.*)$")
    with run_log_path.open("r", encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh, start=1):
            line = raw.rstrip("\n")
            m = pat.match(line)
            if not m:
                continue
            entries.append(
                {
                    "line_number": lineno,
                    "task_id": m.group(1),
                    "turn": int(m.group(2)),
                    "stage": m.group(3),
                    "raw_line": line,
                }
            )
    return entries


def _parse_diff_files(diff_text: str) -> list[str]:
    """Extract repo-relative paths touched by a unified git diff."""
    paths: list[str] = []
    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            m = re.match(r"^diff --git a/(\S+) b/(\S+)", line)
            if m:
                p = m.group(2)
                if p not in paths:
                    paths.append(p)
    return paths


def _read_pilot_source_text(
    pilot_source_path: Path | None = None,
    pilot_git_rev: str | None = V3_RUN_GIT_REV,
) -> str:
    """Read bench/loop/pilot_pr.py from the pinned v3 run git commit (default) or a disk path.

    Emits a warning to stderr if `pilot_git_rev` is requested but `git show` fails and falls back
    to the working-tree file.
    """
    fallback_path = pilot_source_path if pilot_source_path is not None else (Path(__file__).resolve().parent / "pilot_pr.py")
    if pilot_git_rev:
        repo_root = Path(__file__).resolve().parents[2]
        res = subprocess.run(
            ["git", "-C", str(repo_root), "show", f"{pilot_git_rev}:bench/loop/pilot_pr.py"],
            capture_output=True,
            text=True,
        )
        if res.returncode == 0 and res.stdout:
            return res.stdout
        err_detail = (res.stderr or "").strip() or f"rc={res.returncode}, empty stdout"
        print(
            f"WARNING: analyze_v3_turns could not read {pilot_git_rev}:bench/loop/pilot_pr.py "
            f"({err_detail}); falling back to working-tree file {fallback_path}",
            file=sys.stderr,
        )
    return fallback_path.read_text(encoding="utf-8")


def inspect_pilot_source(
    pilot_source_path: Path | None = None,
    pilot_git_rev: str | None = V3_RUN_GIT_REV,
) -> dict[str, Any]:
    """Inspect bench/loop/pilot_pr.py statically to cite exact line numbers and reachability."""
    lines = _read_pilot_source_text(pilot_source_path, pilot_git_rev=pilot_git_rev).splitlines()

    def _find_first(substr: str, start_line: int = 1, end_line: int | None = None) -> int | None:
        end_idx = len(lines) if end_line is None else min(len(lines), end_line)
        for idx in range(start_line, end_idx + 1):
            if substr in lines[idx - 1]:
                return idx
        return None

    def _find_block_end(def_line: int | None) -> int | None:
        if def_line is None:
            return None
        end_line = len(lines)
        for idx in range(def_line + 1, len(lines) + 1):
            ln = lines[idx - 1]
            if ln and not ln[0].isspace() and (ln.startswith("def ") or ln.startswith("class ")):
                end_line = idx - 1
                break
        while end_line > def_line and not lines[end_line - 1].strip():
            end_line -= 1
        return end_line

    fmt_start = _find_first("def format_tool_messages(")
    fmt_end = _find_block_end(fmt_start)
    ext_start = _find_first("def extract_tool_calls(")
    ext_end = _find_block_end(ext_start)
    compact_start = _find_first("def compact_conversation_messages(")
    compact_end = _find_block_end(compact_start)
    loop_start = _find_first("def _run_task_loop_turns(")
    loop_end = _find_block_end(loop_start)
    ask_start = _find_first("def server_ask(")
    ask_end = _find_block_end(ask_start)
    regrade_start = _find_first("def regrade_task_diff(")

    run_tests_sys_line = _find_first('{"tool": "run_tests"', fmt_start or 1, fmt_end)
    finish_sys_line = _find_first('{"tool": "finish"', fmt_start or 1, fmt_end)
    run_tests_user_line = _find_first("Verification command (`run_tests`)", fmt_start or 1, fmt_end)
    user_closing_line = _find_first("call `finish` when done", fmt_start or 1, fmt_end)
    rules_start = _find_first('"Rules:\\n"', fmt_start or 1, fmt_end)
    rules_end = _find_first("manifest = build_target_file_manifest", fmt_start or 1, fmt_end)
    rules_block = "\n".join(lines[(rules_start - 1) : (rules_end - 1)]) if (rules_start and rules_end) else ""

    final_turn_note_line = _find_first("final_turn_note =", loop_start or 1, loop_end)
    final_turn_attach_line = _find_first("if max_turns > 1 and turn == max_turns - 1", loop_start or 1, loop_end)
    repeat_code_check_line = _find_first("if code_hash in seen_code_hashes:", loop_start or 1, loop_end)
    parse_err_event_line = _find_first('"event": "turn_parse_error"', loop_start or 1, loop_end)
    finish_dispatch_line = _find_first('if tname == "finish":', loop_start or 1, loop_end)
    run_tests_dispatch_line = _find_first('if tname == "run_tests":', loop_start or 1, loop_end)
    dirty_init_line = _find_first("dirty_since_last_test = False", loop_start or 1, loop_end)
    dirty_set_line = _find_first("dirty_since_last_test = True", loop_start or 1, loop_end)
    dirty_end_check_line = _find_first(
        'if stop_reason in ("max_turns", "budget") and has_tests and dirty_since_last_test:',
        loop_start or 1,
        loop_end,
    )
    stale_stage1_line = _find_first("Stage 1:", compact_start or 1, compact_end)
    stale_re_inspect_line = _find_first("[Use read_file/grep to re-inspect if needed.]")
    reasoning_chars_line = _find_first('"reasoning_chars":', ask_start or 1, ask_end)
    reasoning_budget_const_line = _find_first("REASONING_BUDGET =")
    read_file_max_const_line = _find_first("READ_FILE_MAX_LINES =")
    tool_result_max_const_line = _find_first("TOOL_RESULT_MAX_LINES =")
    keep_recent_const_line = _find_first("COMPACT_KEEP_RECENT_TURNS =")

    # Check whether server_ask sends an OpenAI "tools" parameter in the JSON request body
    ask_block = "\n".join(lines[(ask_start - 1) : ask_end]) if (ask_start and ask_end) else ""
    uses_openai_tools_param = bool(re.search(r'"tools"\s*:', ask_block))

    return {
        "pilot_source_file": "bench/loop/pilot_pr.py",
        "uses_openai_tools_param": uses_openai_tools_param,
        "tool_declaration_mechanism": "free-text system/user prompt in format_tool_messages; parsed from fenced ```json/```tool blocks in extract_tool_calls",
        "run_tests_in_system_prompt": run_tests_sys_line is not None,
        "run_tests_in_user_prompt": run_tests_user_line is not None,
        "run_tests_in_dispatch": run_tests_dispatch_line is not None,
        "finish_in_system_prompt": finish_sys_line is not None,
        "finish_in_user_prompt": user_closing_line is not None,
        "finish_in_final_turn_note": final_turn_note_line is not None,
        "finish_in_dispatch": finish_dispatch_line is not None,
        "rules_section_mentions_run_tests": "run_tests" in rules_block,
        "rules_section_mentions_finish": "finish" in rules_block,
        "code_citations": {
            "REASONING_BUDGET": reasoning_budget_const_line,
            "READ_FILE_MAX_LINES": read_file_max_const_line,
            "TOOL_RESULT_MAX_LINES": tool_result_max_const_line,
            "COMPACT_KEEP_RECENT_TURNS": keep_recent_const_line,
            "extract_tool_calls": [ext_start, ext_end],
            "format_tool_messages": [fmt_start, fmt_end],
            "run_tests_system_prompt_line": run_tests_sys_line,
            "finish_system_prompt_line": finish_sys_line,
            "run_tests_user_prompt_line": run_tests_user_line,
            "finish_user_prompt_line": user_closing_line,
            "rules_section": [rules_start, rules_end - 1] if (rules_start and rules_end) else None,
            "stale_tool_re_inspect_hint_line": stale_re_inspect_line,
            "compact_conversation_messages": [compact_start, compact_end],
            "stage1_stale_tool_summary_line": stale_stage1_line,
            "final_turn_note_line": final_turn_note_line,
            "final_turn_attach_line": final_turn_attach_line,
            "repeat_code_check_line": repeat_code_check_line,
            "turn_parse_error_event_line": parse_err_event_line,
            "finish_dispatch_line": finish_dispatch_line,
            "run_tests_dispatch_line": run_tests_dispatch_line,
            "dirty_since_last_test_init_line": dirty_init_line,
            "dirty_since_last_test_set_line": dirty_set_line,
            "dirty_since_last_test_end_check_line": dirty_end_check_line,
            "server_ask": [ask_start, ask_end],
            "server_ask_reasoning_chars_line": reasoning_chars_line,
            "regrade_task_diff_line": regrade_start,
        },
    }


def analyze_v3_records(
    results_dir: Path,
    pilot_source_path: Path | None = None,
    label: str = "item6-pilot-v3",
    pilot_git_rev: str | None = V3_RUN_GIT_REV,
) -> dict[str, Any]:
    """Analyze committed v3 records and return the structured JSON-serializable summary."""
    jsonl_path = results_dir / f"{label}.jsonl"
    run1_dir = results_dir / f"{label}.run1"
    turn_events_path = run1_dir / "turn_events.jsonl"
    run_log_path = run1_dir / "run.log"
    diffs_dir = results_dir / f"{label}.diffs"
    grade_path = results_dir / f"{label}.grade.json"

    jsonl_rows = _load_jsonl(jsonl_path)
    turn_events = _load_jsonl(turn_events_path)
    run_log_compactions = _parse_run_log_compactions(run_log_path)
    grade_data = json.loads(grade_path.read_text(encoding="utf-8")) if grade_path.exists() else {}
    grade_by_task = {item["task_id"]: item for item in grade_data.get("per_task", [])}
    source_info = inspect_pilot_source(pilot_source_path, pilot_git_rev=pilot_git_rev)

    # Index turn_events by task_id preserving file order and 1-based line number
    events_by_task: dict[str, list[dict[str, Any]]] = {r["task_id"]: [] for r in jsonl_rows}
    for lineno, ev in enumerate(turn_events, start=1):
        ev_with_line = dict(ev)
        ev_with_line["_line_number"] = lineno
        events_by_task.setdefault(ev["task_id"], []).append(ev_with_line)

    run_log_comp_by_task_turn: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for entry in run_log_compactions:
        run_log_comp_by_task_turn.setdefault((entry["task_id"], entry["turn"]), []).append(entry)

    # ---- Cross-check compaction counts ----
    te_compactions = [e for e in turn_events if e.get("event") == "compaction"]
    te_stage_counts = Counter(e.get("stage", "") for e in te_compactions)
    te_substages_counts = Counter(
        ",".join(e.get("stages") or [])
        for e in te_compactions
        if e.get("stage") == "history_compact"
    )
    rl_stage_counts = Counter(e["stage"] for e in run_log_compactions)
    jsonl_top_comp_sum = sum(int(r.get("compaction_events_total", 0)) for r in jsonl_rows)
    jsonl_top_chars_saved_sum = sum(int(r.get("compaction_chars_saved", 0)) for r in jsonl_rows)
    jsonl_hist_comp_sum = sum(
        len(h.get("compaction") or []) for r in jsonl_rows for h in r.get("history", [])
    )

    history_omitted_compactions: list[dict[str, Any]] = []
    for r in jsonl_rows:
        tid = r["task_id"]
        hist_by_turn = {h["turn"]: h for h in r.get("history", [])}
        for ev in events_by_task.get(tid, []):
            if ev.get("event") == "compaction":
                h = hist_by_turn.get(ev["turn"])
                if h is not None and "compaction" not in h:
                    history_omitted_compactions.append(
                        {
                            "task_id": tid,
                            "turn": ev["turn"],
                            "stage": ev.get("stage"),
                            "stages": ev.get("stages"),
                            "chars_saved": ev.get("chars_saved", 0),
                            "stop": h.get("stop"),
                        }
                    )

    # Peak prompt tokens
    usage_peaks = [
        (int(h.get("prompt_tokens", 0)), r["task_id"], int(h["turn"]))
        for r in jsonl_rows
        for h in r.get("history", [])
    ]
    preflight_peaks = [
        (int(h.get("preflight_prompt_tokens", 0)), r["task_id"], int(h["turn"]))
        for r in jsonl_rows
        for h in r.get("history", [])
    ]
    pre_compact_peaks = [
        (int(e.get("tokens_before", 0)), e["task_id"], int(e["turn"]))
        for e in te_compactions
        if e.get("stage") == "history_compact"
    ]
    max_usage = max(usage_peaks) if usage_peaks else (0, "", -1)
    max_preflight = max(preflight_peaks) if preflight_peaks else (0, "", -1)
    max_precompact = max(pre_compact_peaks) if pre_compact_peaks else (0, "", -1)
    max_prompt_cap = next(
        (int(e["max_prompt_tokens"]) for e in te_compactions if "max_prompt_tokens" in e),
        57344,
    )
    stage2_target = next(
        (int(e["target_tokens"]) for e in te_compactions if "target_tokens" in e),
        43008,
    )

    # ---- Area 1: repeat_code stops & file re-reads after compaction ----
    repeat_code_cases: list[dict[str, Any]] = []
    for r in jsonl_rows:
        if r.get("stop_reason") != "repeat_code":
            continue
        tid = r["task_id"]
        hist = r.get("history", [])
        stop_entry = next((h for h in hist if h.get("stop") == "repeat_code"), hist[-1])
        stop_turn = int(stop_entry["turn"])
        stop_tokens = int(stop_entry.get("tokens", 0))
        te_list = events_by_task.get(tid, [])
        te_tools_by_turn = {
            int(e["turn"]): e.get("tools", []) for e in te_list if e.get("event") == "turn_tools"
        }

        # Preceding turns summary & tool classification
        by_tool_before: Counter[str] = Counter()
        read_only_before = 0
        edit_before = 0
        verify_before = 0
        parse_error_turns_before: list[int] = []
        earlier_turns_detail: list[dict[str, Any]] = []
        for h in hist:
            t_idx = int(h["turn"])
            if t_idx >= stop_turn:
                continue
            kind = _classify_history_turn(h)
            if kind == "parse_error":
                parse_error_turns_before.append(t_idx)
            for tc in h.get("tool_calls") or []:
                tname = tc.get("tool", "")
                by_tool_before[tname] += 1
                if tname in READ_ONLY_TOOLS:
                    read_only_before += 1
                elif tname in EDIT_TOOLS:
                    edit_before += 1
                elif tname in VERIFY_TOOLS:
                    verify_before += 1
            earlier_turns_detail.append(
                {
                    "turn": t_idx,
                    "completion_tokens": int(h.get("tokens", 0)),
                    "gen_s": h.get("gen_s"),
                    "kind": kind,
                    "tools": te_tools_by_turn.get(t_idx, []),
                    "err": (h.get("err") or "")[:ERROR_SNIPPET_MAX_CHARS],
                }
            )

        exact_tok_matches = [
            et for et in earlier_turns_detail if et["completion_tokens"] == stop_tokens
        ]
        nearest_tok_turns = sorted(
            earlier_turns_detail,
            key=lambda et: (abs(et["completion_tokens"] - stop_tokens), et["turn"]),
        )[:3]
        max_earlier_tok = max((et["completion_tokens"] for et in earlier_turns_detail), default=0)

        # Stage 1 stale_tool_summary compaction before the stop
        hist_compacts = [
            e
            for e in te_list
            if e.get("event") == "compaction"
            and e.get("stage") == "history_compact"
            and "stale_tool_summary" in (e.get("stages") or [])
        ]
        same_turn_comp = next((e for e in hist_compacts if int(e["turn"]) == stop_turn), None)
        last_comp = hist_compacts[-1] if hist_compacts else None
        rl_same_turn = [
            e
            for e in run_log_comp_by_task_turn.get((tid, stop_turn), [])
            if e["stage"] == "stale_tool_summary"
        ]

        same_turn_summary = None
        if same_turn_comp is not None:
            same_turn_summary = {
                "turn_events_line": same_turn_comp["_line_number"],
                "run_log_line": rl_same_turn[0]["line_number"] if rl_same_turn else None,
                "stage": same_turn_comp.get("stage"),
                "stages": same_turn_comp.get("stages"),
                "msgs_compacted": same_turn_comp.get("msgs_compacted"),
                "chars_before": same_turn_comp.get("chars_before"),
                "chars_after": same_turn_comp.get("chars_after"),
                "chars_saved": same_turn_comp.get("chars_saved"),
                "tokens_before": same_turn_comp.get("tokens_before"),
                "tokens_after": same_turn_comp.get("tokens_after"),
                "tokens_saved": same_turn_comp.get("tokens_saved"),
            }

        repeat_code_cases.append(
            {
                "task_id": tid,
                "pr_number": r.get("pr_number"),
                "stop_turn": stop_turn,
                "turns_executed": int(r.get("turns_executed", len(hist))),
                "diff_empty": bool(r.get("diff_empty")),
                "stop_turn_completion_tokens": stop_tokens,
                "stop_turn_gen_s": stop_entry.get("gen_s"),
                "stop_turn_prompt_tokens": stop_entry.get("prompt_tokens"),
                "stop_turn_preflight_prompt_tokens": stop_entry.get("preflight_prompt_tokens"),
                "exact_duplicated_reply_recorded": False,
                "duplicated_reply_proxy": {
                    "stop_turn_completion_tokens": stop_tokens,
                    "max_earlier_turn_completion_tokens": max_earlier_tok,
                    "stop_turn_exceeds_all_earlier_turns": stop_tokens > max_earlier_tok,
                    "exact_token_match_earlier_turns": exact_tok_matches,
                    "nearest_token_earlier_turns": nearest_tok_turns,
                    "proxy_caveat": (
                        "Exact reply text and code_hash are not recorded in committed files. "
                        "usage.completion_tokens can exceed the visible reply (consistent with but not proof of "
                        "unrecorded reasoning tokens), whereas repeat_code hashes visible content + tool_calls only; "
                        "token count is a proxy, not proof."
                    ),
                },
                "preceding_tool_calls": {
                    "total": sum(by_tool_before.values()),
                    "read_only_count": read_only_before,
                    "edit_count": edit_before,
                    "verify_count": verify_before,
                    "by_tool": {t: by_tool_before.get(t, 0) for t in KNOWN_TOOLS if by_tool_before.get(t, 0)},
                    "parse_error_turns": parse_error_turns_before,
                    "turns_before_stop": earlier_turns_detail,
                },
                "stage1_compaction_immediately_before_stop": {
                    "same_turn_history_compact": same_turn_comp is not None,
                    "same_turn_event": same_turn_summary,
                    "jsonl_history_recorded_compaction": "compaction" in stop_entry,
                    "most_recent_history_compact_turn": int(last_comp["turn"]) if last_comp else None,
                    "turns_since_last_history_compact": (
                        stop_turn - int(last_comp["turn"]) if last_comp else None
                    ),
                    "total_history_compact_events_in_task": len(hist_compacts),
                },
            }
        )

    # File re-reads after compaction (same path read again after a stale_tool_summary / history_compact event)
    rereads_per_task: dict[str, Any] = {}
    total_read_file_calls = 0
    total_rereads_same_path = 0
    total_rereads_overlap = 0
    total_rereads_exact = 0
    for r in jsonl_rows:
        tid = r["task_id"]
        seen_reads: dict[str, list[dict[str, Any]]] = {}
        compacted_seen = False
        task_read_count = 0
        task_rereads: list[dict[str, Any]] = []
        for ev in events_by_task.get(tid, []):
            if (
                ev.get("event") == "compaction"
                and ev.get("stage") == "history_compact"
                and "stale_tool_summary" in (ev.get("stages") or [])
            ):
                compacted_seen = True
            elif ev.get("event") == "turn_tools":
                for tc in ev.get("tools", []):
                    if tc.get("tool") != "read_file":
                        continue
                    task_read_count += 1
                    total_read_file_calls += 1
                    args = tc.get("args") or {}
                    path = args.get("path", "")
                    start = args.get("start")
                    end = args.get("end")
                    if compacted_seen and path in seen_reads:
                        prior = seen_reads[path]
                        overlap_turns: list[int] = []
                        exact_turns: list[int] = []
                        for pr in prior:
                            ps, pe = pr["start"], pr["end"]
                            if ps == start and pe == end:
                                exact_turns.append(pr["turn"])
                            if (
                                ps is not None
                                and pe is not None
                                and start is not None
                                and end is not None
                                and not (end < ps or start > pe)
                            ):
                                overlap_turns.append(pr["turn"])
                        overlaps = bool(overlap_turns)
                        exact = bool(exact_turns)
                        total_rereads_same_path += 1
                        if overlaps:
                            total_rereads_overlap += 1
                        if exact:
                            total_rereads_exact += 1
                        task_rereads.append(
                            {
                                "turn": int(ev["turn"]),
                                "path": path,
                                "start": start,
                                "end": end,
                                "overlaps_prior_read": overlaps,
                                "exact_match_prior_read": exact,
                                "prior_read_turns_for_path": [pr["turn"] for pr in prior],
                                "overlapping_prior_turns": overlap_turns,
                                "exact_prior_turns": exact_turns,
                            }
                        )
                    seen_reads.setdefault(path, []).append(
                        {"turn": int(ev["turn"]), "start": start, "end": end}
                    )
        rereads_per_task[tid] = {
            "total_read_file_calls": task_read_count,
            "rereads_same_path_after_compact": len(task_rereads),
            "rereads_overlapping_range_after_compact": sum(
                1 for x in task_rereads if x["overlaps_prior_read"]
            ),
            "rereads_exact_range_after_compact": sum(
                1 for x in task_rereads if x["exact_match_prior_read"]
            ),
            "events": task_rereads,
        }

    # ---- Area 2: turn_parse_error events ----
    parse_error_events: list[dict[str, Any]] = []
    parse_error_classes: Counter[str] = Counter()
    parse_error_per_task: dict[str, int] = {r["task_id"]: 0 for r in jsonl_rows}
    rows_by_task = {r["task_id"]: r for r in jsonl_rows}

    for lineno, ev in enumerate(turn_events, start=1):
        if ev.get("event") != "turn_parse_error":
            continue
        tid = ev["task_id"]
        turn = int(ev["turn"])
        row = rows_by_task[tid]
        hist = row.get("history", [])
        h_idx = next(i for i, h in enumerate(hist) if int(h["turn"]) == turn)
        h = hist[h_idx]
        err_msg = h.get("err", "")
        err_class, code_path = _classify_parse_error(err_msg)
        parse_error_classes[err_class] += 1
        parse_error_per_task[tid] += 1
        if h_idx + 1 < len(hist):
            next_outcome = _classify_history_turn(hist[h_idx + 1])
        else:
            next_outcome = f"task_end_{row.get('stop_reason')}"
        parse_error_events.append(
            {
                "turn_events_line": lineno,
                "ts": ev.get("ts"),
                "task_id": tid,
                "pr_number": row.get("pr_number"),
                "turn": turn,
                "prompt_tokens": ev.get("prompt_tokens"),
                "preflight_prompt_tokens": h.get("preflight_prompt_tokens"),
                "completion_tokens": ev.get("completion_tokens"),
                "gen_s": h.get("gen_s"),
                "result_chars": ev.get("result_chars"),
                "error_class": err_class,
                "error_message": err_msg[:ERROR_SNIPPET_MAX_CHARS],
                "error_message_source": "item6-pilot-v3.jsonl history[turn].err",
                "result_chars_matches_err_len": ev.get("result_chars") == len(err_msg),
                "code_path": code_path,
                "raw_model_snippet_recorded": False,
                "next_turn_outcome": next_outcome,
            }
        )

    # ---- Area 3: Completion-length distribution & short turns (<100 tokens) ----
    all_turn_tokens: list[int] = []
    per_task_completion: dict[str, Any] = {}
    short_turns: list[dict[str, Any]] = []
    short_own_outcomes: Counter[str] = Counter()
    short_next_outcomes: Counter[str] = Counter()

    grand_total_tokens = sum(int(r.get("total_completion_tokens", 0)) for r in jsonl_rows)
    for r in jsonl_rows:
        tid = r["task_id"]
        hist = r.get("history", [])
        te_tools_by_turn = {
            int(e["turn"]): e.get("tools", [])
            for e in events_by_task.get(tid, [])
            if e.get("event") == "turn_tools"
        }
        task_toks = [int(h.get("tokens", 0)) for h in hist]
        all_turn_tokens.extend(task_toks)
        short_cnt = sum(1 for x in task_toks if x < SHORT_TURN_THRESHOLD)
        per_task_completion[tid] = {
            "turns_executed": len(task_toks),
            "total_completion_tokens": sum(task_toks),
            "share_of_total_tokens_pct": round(
                (100.0 * sum(task_toks) / grand_total_tokens) if grand_total_tokens else 0.0, 2
            ),
            "min": min(task_toks) if task_toks else 0,
            "median": round(float(statistics.median(task_toks)), 2) if task_toks else 0.0,
            "mean": round(float(statistics.mean(task_toks)), 2) if task_toks else 0.0,
            "max": max(task_toks) if task_toks else 0,
            "short_turns_lt100_count": short_cnt,
            "short_turns_lt100_pct": round((100.0 * short_cnt / len(task_toks)) if task_toks else 0.0, 2),
        }
        for i, h in enumerate(hist):
            tok = int(h.get("tokens", 0))
            if tok >= SHORT_TURN_THRESHOLD:
                continue
            t_idx = int(h["turn"])
            own_outcome = _classify_history_turn(h)
            short_own_outcomes[own_outcome] += 1
            if i + 1 < len(hist):
                nh = hist[i + 1]
                next_turn_idx: int | None = int(nh["turn"])
                next_outcome = _classify_history_turn(nh)
                next_tokens: int | None = int(nh.get("tokens", 0))
            else:
                next_turn_idx = None
                next_outcome = f"task_end_{r.get('stop_reason')}"
                next_tokens = None
            short_next_outcomes[next_outcome] += 1
            short_turns.append(
                {
                    "task_id": tid,
                    "turn": t_idx,
                    "completion_tokens": tok,
                    "gen_s": h.get("gen_s"),
                    "turn_outcome": own_outcome,
                    "tools": [tc.get("tool") for tc in (h.get("tool_calls") or [])],
                    "tool_args": [tc.get("args") for tc in te_tools_by_turn.get(t_idx, [])],
                    "next_turn": next_turn_idx,
                    "next_turn_outcome": next_outcome,
                    "next_turn_tokens": next_tokens,
                }
            )

    sorted_toks = sorted(all_turn_tokens)
    token_buckets = {
        "<50": sum(1 for x in sorted_toks if x < 50),
        "50-99": sum(1 for x in sorted_toks if 50 <= x < 100),
        "100-199": sum(1 for x in sorted_toks if 100 <= x < 200),
        "200-499": sum(1 for x in sorted_toks if 200 <= x < 500),
        "500-999": sum(1 for x in sorted_toks if 500 <= x < 1000),
        ">=1000": sum(1 for x in sorted_toks if x >= 1000),
    }

    # Check if any reasoning fields ever appear in the committed records
    all_jsonl_keys = {k for r in jsonl_rows for k in r.keys()}
    all_hist_keys = {k for r in jsonl_rows for h in r.get("history", []) for k in h.keys()}
    all_te_keys = {k for e in turn_events for k in e.keys()}
    reasoning_keys_present = sorted(
        k
        for k in (all_jsonl_keys | all_hist_keys | all_te_keys)
        if "reasoning" in k.lower() or "thought" in k.lower() or "visible" in k.lower()
    )

    # ---- Area 4: Tool-usage counts & reachability ----
    overall_tool_total: Counter[str] = Counter()
    overall_tool_ok: Counter[str] = Counter()
    overall_tool_err: Counter[str] = Counter()
    per_task_tools: dict[str, Any] = {}

    for r in jsonl_rows:
        tid = r["task_id"]
        t_total: Counter[str] = Counter()
        t_ok: Counter[str] = Counter()
        t_err: Counter[str] = Counter()
        first_ok_edit_turn: int | None = None
        for h in r.get("history", []):
            for tc in h.get("tool_calls") or []:
                tname = tc.get("tool", "")
                ok = bool(tc.get("ok"))
                t_total[tname] += 1
                overall_tool_total[tname] += 1
                if ok:
                    t_ok[tname] += 1
                    overall_tool_ok[tname] += 1
                    if tname in EDIT_TOOLS and first_ok_edit_turn is None:
                        first_ok_edit_turn = int(h["turn"])
                else:
                    t_err[tname] += 1
                    overall_tool_err[tname] += 1
        ro_cnt = sum(t_total[t] for t in READ_ONLY_TOOLS)
        ed_cnt = sum(t_total[t] for t in EDIT_TOOLS)
        vf_cnt = sum(t_total[t] for t in VERIFY_TOOLS)
        per_task_tools[tid] = {
            "total_tool_calls": sum(t_total.values()),
            "read_only_count": ro_cnt,
            "edit_count": ed_cnt,
            "verify_finish_count": vf_cnt,
            "first_successful_edit_turn": first_ok_edit_turn,
            "by_tool": {
                t: {"total": t_total[t], "ok": t_ok[t], "error": t_err[t]}
                for t in KNOWN_TOOLS
            },
        }

    overall_total_calls = sum(overall_tool_total.values())
    overall_ro_calls = sum(overall_tool_total[t] for t in READ_ONLY_TOOLS)
    overall_ed_calls = sum(overall_tool_total[t] for t in EDIT_TOOLS)
    overall_vf_calls = sum(overall_tool_total[t] for t in VERIFY_TOOLS)

    # ---- Area 5: End-of-loop dirty_since_last_test check & pr1342 false pass ----
    dirty_check_per_task: dict[str, Any] = {}
    triggered_dirty_tasks: list[str] = []
    false_pass_tasks: list[str] = []

    for r in jsonl_rows:
        tid = r["task_id"]
        pt_tools = per_task_tools[tid]
        had_ok_edit = pt_tools["first_successful_edit_turn"] is not None
        called_run_tests = pt_tools["by_tool"]["run_tests"]["total"] > 0
        called_finish = pt_tools["by_tool"]["finish"]["total"] > 0
        reached_max_turns = int(r.get("turns_executed", 0)) >= 12 and r.get("stop_reason") in (
            "max_turns",
            "pass",
        )
        triggered_dirty = bool(
            r.get("has_tests") and had_ok_edit and not called_run_tests and not called_finish and reached_max_turns
        )
        if triggered_dirty:
            triggered_dirty_tasks.append(tid)

        g = grade_by_task.get(tid, {})
        in_loop_passed = bool(r.get("passed"))
        offline_test_passed = g.get("test_passed")
        is_false_pass = bool(in_loop_passed and offline_test_passed is False)
        if is_false_pass:
            false_pass_tasks.append(tid)

        diff_path = diffs_dir / f"{tid}.diff"
        diff_text = diff_path.read_text(encoding="utf-8") if diff_path.exists() else ""
        diff_lines = len(diff_text.splitlines())
        diff_files = _parse_diff_files(diff_text)

        dirty_check_per_task[tid] = {
            "had_successful_edit": had_ok_edit,
            "first_successful_edit_turn": pt_tools["first_successful_edit_turn"],
            "called_run_tests": called_run_tests,
            "called_finish": called_finish,
            "turns_executed": int(r.get("turns_executed", 0)),
            "triggered_end_of_loop_dirty_check": triggered_dirty,
            "jsonl_stop_reason": r.get("stop_reason"),
            "in_loop_passed": in_loop_passed,
            "offline_test_passed": offline_test_passed,
            "false_pass": is_false_pass,
            "tier2_verdict": g.get("final_verdict"),
            "hand_fix_lines": g.get("hand_fix_lines"),
            "diff_lines": diff_lines,
            "diff_files_touched": diff_files,
        }

    # Detailed pr1342 record
    pr1342_row = rows_by_task.get("item6v3_pr1342")
    pr1342_detail: dict[str, Any] | None = None
    if pr1342_row is not None:
        pr1342_hist = pr1342_row.get("history", [])
        edit_turns = [
            int(h["turn"])
            for h in pr1342_hist
            if any(tc.get("tool") in EDIT_TOOLS and tc.get("ok") for tc in (h.get("tool_calls") or []))
        ]
        failed_edit_turns = [
            int(h["turn"])
            for h in pr1342_hist
            if any(tc.get("tool") in EDIT_TOOLS and not tc.get("ok") for tc in (h.get("tool_calls") or []))
        ]
        last_edit_turn = max(edit_turns) if edit_turns else -1
        post_edit_turns = [
            {
                "turn": int(h["turn"]),
                "tools": [tc.get("tool") for tc in (h.get("tool_calls") or [])],
                "completion_tokens": int(h.get("tokens", 0)),
            }
            for h in pr1342_hist
            if int(h["turn"]) > last_edit_turn
        ]
        pr1342_dirty = dirty_check_per_task["item6v3_pr1342"]
        pr1342_detail = {
            "task_id": "item6v3_pr1342",
            "failed_edit_turns": failed_edit_turns,
            "successful_edit_turns": edit_turns,
            "post_edit_turns": post_edit_turns,
            "diff_file": pr1342_row.get("diff_file"),
            "diff_lines": pr1342_dirty["diff_lines"],
            "diff_files_touched": pr1342_dirty["diff_files_touched"],
            "touched_test_file": any(p.startswith("tests/") for p in pr1342_dirty["diff_files_touched"]),
            "jsonl_stop_reason": pr1342_dirty["jsonl_stop_reason"],
            "in_loop_passed": pr1342_dirty["in_loop_passed"],
            "offline_test_passed": pr1342_dirty["offline_test_passed"],
            "tier2_verdict": pr1342_dirty["tier2_verdict"],
            "hand_fix_lines": pr1342_dirty["hand_fix_lines"],
            "mechanism": (
                "Turn 6 search_replace dirtied the scratch worktree (dirty_since_last_test=True) with only the n<0 check; "
                "turns 7-11 ran read_file/grep only without calling run_tests or finish. At max_turns=12, "
                "bench/loop/pilot_pr.py end-of-loop check ran run_tests once against base_commit tests/test_more.py "
                "(which lacks n==0 / n<0 regression tests for chunked_even), exited 0, and rewrote stop_reason from "
                "'max_turns' to 'pass'. Offline regrade_task_diff mounted merged_commit tests/test_more.py read-only "
                "and failed (test_passed=false)."
            ),
            "section_16_reference": (
                "docs/item6-pilot.md Section 16 "
                "('Why item6v3_pr1342 Passed In-Loop (in_loop_passed = true) but Failed Offline (test_passed = false)')"
            ),
        }

    return {
        "meta": {
            "label": label,
            "scope_label": "descriptive, post-hoc, n=7, one repo",
            "official_decision_unchanged": grade_data.get("decision", "DROP"),
            "official_testable_passed": grade_data.get("testable_passed"),
            "official_testable_tasks": grade_data.get("testable_tasks"),
            "official_approved_final": grade_data.get("approved_final"),
            "tasks_analyzed": len(jsonl_rows),
            "turns_executed_total": len(all_turn_tokens),
            "inputs_read": [
                f"bench/loop/results/{label}.jsonl",
                f"bench/loop/results/{label}.run1/turn_events.jsonl",
                f"bench/loop/results/{label}.run1/run.log",
                f"bench/loop/results/{label}.diffs/",
                f"bench/loop/results/{label}.grade.json",
                "bench/loop/pilot_pr.py",
            ],
            "compaction_cross_check": {
                "turn_events_compaction_total": len(te_compactions),
                "turn_events_by_stage": dict(te_stage_counts),
                "turn_events_history_compact_substages": dict(te_substages_counts),
                "run_log_compaction_total": len(run_log_compactions),
                "run_log_by_stage": dict(rl_stage_counts),
                "jsonl_top_level_compaction_events_sum": jsonl_top_comp_sum,
                "jsonl_top_level_compaction_chars_saved_sum": jsonl_top_chars_saved_sum,
                "jsonl_history_compaction_entries_sum": jsonl_hist_comp_sum,
                "history_omitted_on_repeat_code_turns": history_omitted_compactions,
                "peak_prompt_tokens": {
                    "usage_max": {"tokens": max_usage[0], "task_id": max_usage[1], "turn": max_usage[2]},
                    "preflight_max": {
                        "tokens": max_preflight[0],
                        "task_id": max_preflight[1],
                        "turn": max_preflight[2],
                    },
                    "pre_compaction_max": {
                        "tokens": max_precompact[0],
                        "task_id": max_precompact[1],
                        "turn": max_precompact[2],
                    },
                    "max_prompt_tokens_cap": max_prompt_cap,
                    "stage2_target_tokens": stage2_target,
                },
            },
        },
        "repeat_code_and_compaction": {
            "repeat_code_task_count": len(repeat_code_cases),
            "repeat_code_tasks": [c["task_id"] for c in repeat_code_cases],
            "exact_duplicated_reply_recorded": False,
            "exact_duplicated_reply_note": (
                "Neither the raw assistant reply text, nor the SHA-256 code_hash, nor the matched earlier turn index "
                "is persisted in item6-pilot-v3.jsonl, turn_events.jsonl, or run.log "
                "(bench/loop/pilot_pr.py hashes content+tool_calls in memory and breaks before _append_turn_log)."
            ),
            "same_turn_stage1_compaction_before_stop_count": sum(
                1 for c in repeat_code_cases if c["stage1_compaction_immediately_before_stop"]["same_turn_history_compact"]
            ),
            "cases": repeat_code_cases,
            "file_rereads_after_compaction": {
                "definition": (
                    "read_file calls whose path was already read by an earlier read_file in the same task "
                    "and that occurred after at least one history_compact (stale_tool_summary) event in that task"
                ),
                "overall": {
                    "total_read_file_calls": total_read_file_calls,
                    "rereads_same_path_after_compact": total_rereads_same_path,
                    "rereads_overlapping_range_after_compact": total_rereads_overlap,
                    "rereads_exact_range_after_compact": total_rereads_exact,
                    "tasks_with_rereads_after_compact": sum(
                        1 for v in rereads_per_task.values() if v["rereads_same_path_after_compact"] > 0
                    ),
                },
                "per_task": rereads_per_task,
            },
        },
        "turn_parse_errors": {
            "total_count": len(parse_error_events),
            "tasks_affected_count": sum(1 for cnt in parse_error_per_task.values() if cnt > 0),
            "raw_model_snippet_recorded": False,
            "recording_sources_note": (
                "turn_events.jsonl records prompt_tokens, completion_tokens, tools=[], and result_chars, "
                "but omits the error text and raw model reply. run.log does not log turn_parse_error. "
                "The exact parser error string (matching result_chars in length on all 7 events) is recorded in "
                "item6-pilot-v3.jsonl history[turn].err; the raw model reply / offending JSON snippet is not "
                "recorded anywhere in the committed records."
            ),
            "by_error_class": dict(parse_error_classes),
            "per_task_counts": parse_error_per_task,
            "events": parse_error_events,
        },
        "completion_length_distribution": {
            "reasoning_tokens_recorded": False,
            "reasoning_chars_recorded": False,
            "reasoning_related_keys_in_committed_records": reasoning_keys_present,
            "visible_vs_reasoning_note": (
                "Visible vs reasoning tokens are not recorded separately in any committed v3 record. "
                "server_ask() computes reasoning_chars from msg.get('reasoning_content'), but _run_task_loop_turns() "
                "discards reasoning_chars and finish_reason and logs only usage.completion_tokens "
                "(as history[turn].tokens and turn_events.completion_tokens). "
                "Two observations show the count exceeds the visible reply; consistent with but not proof of "
                "unrecorded reasoning tokens: "
                "(1) item6v3_pr1311 turn 7 logged 497 completion tokens yet matched an earlier turn's visible code_hash "
                "when the maximum earlier turn was 210 tokens; "
                "(2) item6v3_pr1269 turns 5-6 logged 4,171 and 4,213 completion tokens (just above REASONING_BUDGET=4096) "
                "to emit 1-2 short read_file calls."
            ),
            "overall": {
                "turns_count": len(sorted_toks),
                "total_completion_tokens": sum(sorted_toks),
                "mean": round(float(statistics.mean(sorted_toks)), 2) if sorted_toks else 0.0,
                "stdev": round(float(statistics.stdev(sorted_toks)), 2) if len(sorted_toks) > 1 else 0.0,
                "min": sorted_toks[0] if sorted_toks else 0,
                "p10": _percentile(sorted_toks, 0.10),
                "p25": _percentile(sorted_toks, 0.25),
                "median": round(float(statistics.median(sorted_toks)), 2) if sorted_toks else 0.0,
                "p75": _percentile(sorted_toks, 0.75),
                "p90": _percentile(sorted_toks, 0.90),
                "p95": _percentile(sorted_toks, 0.95),
                "max": sorted_toks[-1] if sorted_toks else 0,
                "buckets": token_buckets,
            },
            "per_task": per_task_completion,
            "short_turns_lt100": {
                "threshold_tokens": SHORT_TURN_THRESHOLD,
                "count": len(short_turns),
                "share_of_all_turns_pct": round(
                    (100.0 * len(short_turns) / len(sorted_toks)) if sorted_toks else 0.0, 2
                ),
                "by_turn_own_outcome": dict(short_own_outcomes),
                "by_next_turn_outcome": dict(short_next_outcomes),
                "turns": short_turns,
            },
        },
        "tool_usage_and_reachability": {
            "known_tools": list(KNOWN_TOOLS),
            "overall": {
                "total_tool_calls": overall_total_calls,
                "by_tool": {
                    t: {
                        "total": overall_tool_total[t],
                        "ok": overall_tool_ok[t],
                        "error": overall_tool_err[t],
                    }
                    for t in KNOWN_TOOLS
                },
                "by_category": {
                    "read_only": overall_ro_calls,
                    "edit": overall_ed_calls,
                    "verify_finish": overall_vf_calls,
                },
                "read_only_share_pct": round(
                    (100.0 * overall_ro_calls / overall_total_calls) if overall_total_calls else 0.0, 2
                ),
                "edit_share_pct": round(
                    (100.0 * overall_ed_calls / overall_total_calls) if overall_total_calls else 0.0, 2
                ),
                "run_tests_never_used": overall_tool_total["run_tests"] == 0,
                "finish_never_used": overall_tool_total["finish"] == 0,
            },
            "per_task": per_task_tools,
            "reachability_inspection": source_info,
        },
        "dirty_since_last_test_and_pr1342_false_pass": {
            "code_citations": {
                "dirty_since_last_test_init_line": source_info["code_citations"]["dirty_since_last_test_init_line"],
                "dirty_since_last_test_set_line": source_info["code_citations"]["dirty_since_last_test_set_line"],
                "dirty_since_last_test_end_check_line": source_info["code_citations"][
                    "dirty_since_last_test_end_check_line"
                ],
                "regrade_task_diff_line": source_info["code_citations"]["regrade_task_diff_line"],
            },
            "tasks_triggering_end_of_loop_check": triggered_dirty_tasks,
            "false_pass_tasks": false_pass_tasks,
            "per_task": dirty_check_per_task,
            "pr1342_detail": pr1342_detail,
        },
    }


def main(argv: list[str] | None = None) -> int:
    repo_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(
        description="CPU-only post-hoc analysis of Item 6 Pilot v3 committed turn records."
    )
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=repo_root / "bench" / "loop" / "results",
        help="Directory containing committed item6-pilot-v3* result files.",
    )
    parser.add_argument(
        "--pilot-source",
        type=Path,
        default=repo_root / "bench" / "loop" / "pilot_pr.py",
        help="Path to bench/loop/pilot_pr.py (fallback when --pilot-git-rev is empty).",
    )
    parser.add_argument(
        "--pilot-git-rev",
        default=V3_RUN_GIT_REV,
        help="Git revision of bench/loop/pilot_pr.py that ran v3 (default: ddcbbfb; pass '' to read --pilot-source).",
    )
    parser.add_argument(
        "--label",
        default="item6-pilot-v3",
        help="Result file label prefix (default: item6-pilot-v3).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional output JSON path. If omitted, prints JSON to stdout.",
    )
    args = parser.parse_args(argv)

    summary = analyze_v3_records(
        results_dir=args.results_dir,
        pilot_source_path=args.pilot_source,
        label=args.label,
        pilot_git_rev=args.pilot_git_rev or None,
    )
    rendered = json.dumps(summary, indent=2) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
