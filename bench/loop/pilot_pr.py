#!/usr/bin/env python3
"""Item 6 Pilot: Real-PR evaluation harness and runner.

Executes the small-model agentic loop with test feedback on real repository PR tasks.
Can be executed with:
  python3 bench/loop/pilot_pr.py --selftest      # runs CPU-only selftest with mock model
  python3 bench/loop/pilot_pr.py run --label L   # runs benchmark loop against :8081
  python3 bench/loop/pilot_pr.py grade --label L # offline evaluation of local diffs against hidden reference
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import tasks_item6  # noqa: E402

API_URL = "http://127.0.0.1:8081"
MAX_TURNS_DEFAULT = 4
TASK_BUDGET_TOKENS = 32768


def format_turn_prompt(task, last_code=None, test_error=None):
    """Format the turn prompt for the agentic loop.

    Never includes reference diffs or oracle solutions.
    """
    clean_task = tasks_item6.strip_hidden(task)
    base_prompt = clean_task["prompt"]

    if last_code is None and test_error is None:
        return (
            f"{base_prompt}\n\n"
            "Working directory: Clean git worktree at base commit.\n"
            "Instructions:\n"
            "- Implement all required changes.\n"
            "- Output your edits in markdown code blocks with file path headers, e.g.:\n"
            "  ### path/to/file.py\n"
            "  ```python\n"
            "  # updated contents\n"
            "  ```\n"
            "- Or provide a valid unified git diff in a ```diff block.\n"
            "- Standard library or repository dependencies only; no unrequested subagents; no GPU work."
        )

    err_text = (test_error or "").strip()
    if len(err_text) > 2500:
        err_text = "... [truncated] ...\n" + err_text[-2500:]

    return (
        f"{base_prompt}\n\n"
        "Your previous changes failed automated verification with the following error:\n"
        f"```\n{err_text}\n```\n\n"
        "Analyze the error, locate the cause, and output the corrected files or unified diff."
    )


def extract_file_updates(response_text):
    """Extract file updates from model response.

    Supports:
      1. Annotated headers: `### path/to/file` or `**File: path/to/file**` followed by code fence.
      2. Code fences with path annotation: ```python:path/to/file
      3. Unified git diff: ```diff
    Returns a dict mapping relative filepath -> full content, or a diff string.
    """
    files = {}

    # 1. Check for unified diff fence
    diff_match = re.search(r"```(?:diff|patch)\n(diff --git a/.*?)\n```", response_text, re.DOTALL)
    if diff_match:
        return {"__patch__": diff_match.group(1)}

    # 2. Check for fenced blocks with language:path
    lang_path_blocks = re.findall(
        r"```[a-zA-Z0-9_-]+[:\s]+([a-zA-Z0-9_\-\./\\]+)\n(.*?)```", response_text, re.DOTALL
    )
    for path, code in lang_path_blocks:
        path = path.strip()
        if "/" in path or "." in path:
            files[path] = code

    # 3. Check for ### path/to/file followed by code block
    header_blocks = re.findall(
        r"(?:###|\*\*File:?|\bFile:)\s*[`\*]?([a-zA-Z0-9_\-\./\\]+)[`\*]?\s*\n+```[a-zA-Z0-9_-]*\n(.*?)```",
        response_text,
        re.DOTALL | re.IGNORECASE,
    )
    for path, code in header_blocks:
        path = path.strip()
        if "/" in path or "." in path:
            files[path] = code

    return files


def apply_updates(worktree_dir, updates):
    """Apply extracted files or unified patch to worktree_dir."""
    if not updates:
        return False, "No file updates or patch found in model response."

    if "__patch__" in updates:
        patch_text = updates["__patch__"]
        patch_file = os.path.join(worktree_dir, "_agent_update.patch")
        with open(patch_file, "w", encoding="utf-8") as f:
            f.write(patch_text + "\n")
        try:
            res = subprocess.run(
                ["git", "apply", "--whitespace=nowarn", patch_file],
                cwd=worktree_dir,
                capture_output=True,
                text=True,
                timeout=15,
            )
            if res.returncode == 0:
                os.remove(patch_file)
                return True, "Patch applied successfully."
            else:
                os.remove(patch_file)
                return False, f"git apply failed: {res.stderr}"
        except Exception as e:
            if os.path.exists(patch_file):
                os.remove(patch_file)
            return False, f"Exception applying patch: {e}"

    # Multiple files dict
    written = []
    try:
        for rel_path, content in updates.items():
            full_path = os.path.join(worktree_dir, rel_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)
            written.append(rel_path)
        return True, f"Wrote files: {', '.join(written)}"
    except Exception as e:
        return False, f"Failed writing files: {e}"


def run_tests(task, worktree_dir, timeout=60):
    """Run test command for the task in worktree_dir.

    Returns (passed: bool, output_str: str).
    """
    clean_task = tasks_item6.strip_hidden(task)
    cmd = clean_task.get("test_cmd")
    if not cmd:
        return True, "No test command defined for task."

    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    try:
        res = subprocess.run(
            ["bash", "-c", cmd],
            cwd=worktree_dir,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        passed = (res.returncode == 0)
        output = (res.stdout or "") + (res.stderr or "")
        return passed, output
    except subprocess.TimeoutExpired:
        return False, f"ERROR: test command timed out after {timeout} seconds."
    except Exception as e:
        return False, f"ERROR executing test command: {e}"


def evaluate_diff(local_diff, hidden_diff):
    """Compute offline grading metrics between local diff and hidden reference diff.

    Never shown to model.
    """
    local_lines = set(line.strip() for line in local_diff.splitlines() if line.startswith(("+", "-")) and not line.startswith(("+++", "---")))
    hidden_lines = set(line.strip() for line in hidden_diff.splitlines() if line.startswith(("+", "-")) and not line.startswith(("+++", "---")))

    if not hidden_lines:
        overlap = 1.0 if not local_lines else 0.0
    else:
        intersection = len(local_lines & hidden_lines)
        union = len(local_lines | hidden_lines)
        overlap = intersection / union if union > 0 else 0.0

    return {
        "local_diff_lines": len(local_diff.splitlines()),
        "hidden_diff_lines": len(hidden_diff.splitlines()),
        "line_overlap_jaccard": round(overlap, 4),
    }


def run_task_loop(task, ask_fn, worktree_dir, max_turns=MAX_TURNS_DEFAULT, task_budget=TASK_BUDGET_TOKENS):
    """Execute the agentic loop on a task in worktree_dir."""
    clean_task = tasks_item6.strip_hidden(task)
    history = []
    seen_code_hashes = set()
    last_code = None
    last_err = None
    accumulated_completion_tokens = 0
    stop_reason = "max_turns"

    for turn in range(max_turns):
        t0 = time.time()
        prompt = format_turn_prompt(clean_task, last_code, last_err)
        seed = 6000 + clean_task["pr_number"] * 10 + turn

        reply = ask_fn(prompt, seed)
        gen_s = round(time.time() - t0, 2)
        comp_tokens = reply.get("usage", {}).get("completion_tokens", 0)
        accumulated_completion_tokens += comp_tokens

        content = reply.get("content", "")
        code_hash = hashlib.sha256(content.encode()).hexdigest()

        # Stop check: repeat code
        if code_hash in seen_code_hashes:
            history.append({
                "turn": turn,
                "passed": False,
                "err": "repeat_code",
                "stop": "repeat_code",
                "gen_s": gen_s,
                "tokens": comp_tokens,
            })
            stop_reason = "repeat_code"
            break
        seen_code_hashes.add(code_hash)

        # Apply updates
        updates = extract_file_updates(content)
        ok, msg = apply_updates(worktree_dir, updates)

        if not ok:
            passed = False
            test_out = f"Failed to apply updates: {msg}"
        else:
            # Run automated tests
            passed, test_out = run_tests(clean_task, worktree_dir)

        # Stop check: repeat error
        if last_err is not None and test_out.strip() == last_err.strip():
            history.append({
                "turn": turn,
                "passed": False,
                "err": test_out,
                "stop": "repeat_error",
                "gen_s": gen_s,
                "tokens": comp_tokens,
            })
            stop_reason = "repeat_error"
            break

        history.append({
            "turn": turn,
            "passed": passed,
            "err": "" if passed else test_out,
            "gen_s": gen_s,
            "tokens": comp_tokens,
        })

        if passed:
            stop_reason = "pass"
            break

        if accumulated_completion_tokens >= task_budget:
            stop_reason = "budget"
            break

        last_code = content
        last_err = test_out

    # Collect final local diff
    diff_res = subprocess.run(
        ["git", "diff", clean_task["base_commit"], "HEAD"],
        cwd=worktree_dir,
        capture_output=True,
        text=True,
    )
    final_diff = diff_res.stdout or ""

    return {
        "task_id": clean_task["id"],
        "pr_number": clean_task["pr_number"],
        "passed": history[-1]["passed"] if history else False,
        "stop_reason": stop_reason,
        "turns_executed": len(history),
        "history": history,
        "total_completion_tokens": accumulated_completion_tokens,
        "final_diff": final_diff,
    }


def selftest():
    """Run comprehensive CPU-only self-tests for task definitions and loop mechanics."""
    print("=== STARTING PILOT_PR SELFTEST ===")

    # 1. Load tasks check
    tasks = tasks_item6.load_tasks()
    assert len(tasks) == 7, f"Expected 7 tasks, found {len(tasks)}"
    pr_nums = [t["pr_number"] for t in tasks]
    assert pr_nums == [6, 8, 13, 14, 15, 16, 20], f"Unexpected PR numbers: {pr_nums}"
    print("[OK] Task loading and PR numbers verified (7 tasks)")

    # 2. Leak prevention check
    for t in tasks:
        clean = tasks_item6.strip_hidden(t)
        assert "hidden_diff" not in clean, f"Leak in {t['id']}: hidden_diff present"
        assert "merged_commit" not in clean, f"Leak in {t['id']}: merged_commit present"
        p = format_turn_prompt(t)
        assert t["merged_commit"] not in p, f"Leak in prompt for {t['id']}: merged commit SHA present"
    print("[OK] Leak prevention and strip_hidden verified")

    # 3. File extraction checks
    test_response_annotated = (
        "Here is the solution:\n\n"
        "### foo/bar.py\n"
        "```python\n"
        "def hello():\n    return 'world'\n"
        "```\n\n"
        "### config.json\n"
        "```json\n"
        "{\"status\": \"ok\"}\n"
        "```\n"
    )
    updates = extract_file_updates(test_response_annotated)
    assert "foo/bar.py" in updates, "foo/bar.py not extracted"
    assert "config.json" in updates, "config.json not extracted"
    assert "return 'world'" in updates["foo/bar.py"]

    diff_response = (
        "Here is a patch:\n"
        "```diff\n"
        "diff --git a/a.txt b/a.txt\n"
        "--- a/a.txt\n"
        "+++ b/a.txt\n"
        "@@ -1 +1 @@\n"
        "-old\n"
        "+new\n"
        "```\n"
    )
    updates_diff = extract_file_updates(diff_response)
    assert "__patch__" in updates_diff, "Patch not extracted"
    print("[OK] File updates extraction verified")

    # 4. In-memory temporary worktree loop test
    temp_dir = tempfile.mkdtemp(prefix="pilot_pr_test_")
    try:
        subprocess.run(["git", "init"], cwd=temp_dir, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=temp_dir, check=True)
        subprocess.run(["git", "config", "user.email", "test@test.org"], cwd=temp_dir, check=True)

        # Create initial test file
        test_py = os.path.join(temp_dir, "test_target.py")
        with open(test_py, "w") as f:
            f.write("def compute():\n    return 0\n")
        runner_py = os.path.join(temp_dir, "test_check.py")
        with open(runner_py, "w") as f:
            f.write("import test_target\nassert test_target.compute() == 42\n")

        subprocess.run(["git", "add", "."], cwd=temp_dir, check=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=temp_dir, check=True, capture_output=True)
        base_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=temp_dir, text=True).strip()

        mock_task = {
            "id": "mock_task",
            "pr_number": 999,
            "title": "Mock Task",
            "base_commit": base_commit,
            "merged_commit": "00000000",
            "has_tests": True,
            "test_cmd": "python3 test_check.py",
            "prompt": "Fix compute() to return 42 in test_target.py",
            "files": ["test_target.py"],
            "hidden_diff": "+def compute():\n+    return 42",
        }

        # Case A: Fails turn 0, model fixes in turn 1 with test error feedback
        def mock_model_turn1_pass(prompt, seed):
            if "failed automated verification" not in prompt:
                # Turn 0: produce buggy code
                return {
                    "content": "### test_target.py\n```python\ndef compute():\n    return 1\n```",
                    "usage": {"completion_tokens": 50},
                }
            # Turn 1: fix code based on error
            return {
                "content": "### test_target.py\n```python\ndef compute():\n    return 42\n```",
                "usage": {"completion_tokens": 50},
            }

        res = run_task_loop(mock_task, mock_model_turn1_pass, temp_dir, max_turns=3)
        assert res["passed"] is True, "Mock task expected to pass in turn 1"
        assert res["turns_executed"] == 2, f"Expected 2 turns, got {res['turns_executed']}"
        assert res["stop_reason"] == "pass", f"Expected stop_reason 'pass', got {res['stop_reason']}"
        print("[OK] Mock loop execution with feedback pass verified")

        # Case B: Repeat code stop check
        def mock_model_repeat(prompt, seed):
            return {
                "content": "### test_target.py\n```python\ndef compute():\n    return 10\n```",
                "usage": {"completion_tokens": 40},
            }

        res_repeat = run_task_loop(mock_task, mock_model_repeat, temp_dir, max_turns=4)
        assert res_repeat["passed"] is False
        assert res_repeat["stop_reason"] == "repeat_code"
        print("[OK] Repeat code stop rule verified")

    finally:
        shutil.rmtree(temp_dir)

    print("=== ALL PILOT_PR SELFTESTS PASSED ===")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Item 6 Pilot PR Loop Runner")
    parser.add_argument("--selftest", action="store_true", help="Run CPU-only self-tests")
    parser.add_argument("--label", type=str, default="item6-pilot", help="Run label")
    parser.add_argument("--tasks", type=str, default=None, help="Comma-separated task IDs")
    args = parser.parse_args()

    if args.selftest:
        sys.exit(selftest())

    print(f"pilot_pr.py runner: label={args.label}. Model execution requires ACTIVE session via llmctl.")


if __name__ == "__main__":
    main()
