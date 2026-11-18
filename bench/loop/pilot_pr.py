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
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import tasks_item6  # noqa: E402

API_URL = "http://127.0.0.1:8081"
SAMPLING = {"temperature": 0.6, "top_p": 0.95, "top_k": 20}
REASONING_BUDGET = 4096
MAX_TOKENS = 8192
MAX_TURNS_DEFAULT = 4
TASK_BUDGET_TOKENS = 32768
BUDGET_MESSAGE = "Reasoning budget reached. Write the code block now."

FIXED_SYSTEM_PATH = "/usr/local/bin:/usr/bin:/bin"
SAFE_ENV_KEYS = ("LANG", "LC_ALL", "LC_CTYPE", "TERM")


def build_minimal_env(home_dir=None, tmp_dir=None):
    """Return a minimal allowlisted environment with fixed system PATH, no GIT_*, no PYTHON*, and no repo paths."""
    env = {
        "PATH": FIXED_SYSTEM_PATH,
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    for k in SAFE_ENV_KEYS:
        val = os.environ.get(k)
        if val is not None:
            env[k] = val
    if home_dir is not None:
        env["HOME"] = home_dir
    if tmp_dir is not None:
        env["TMPDIR"] = tmp_dir
    return env


def prepare_isolated_home_and_tmp(base_dir):
    """Create or recreate fresh empty HOME and TMPDIR directories sibling to base_dir."""
    root = os.path.abspath(base_dir)
    home_dir = root + "_home"
    tmp_dir = root + "_tmp"
    for d in (home_dir, tmp_dir):
        if os.path.exists(d):
            shutil.rmtree(d, ignore_errors=True)
        os.makedirs(d, exist_ok=True)
    return home_dir, tmp_dir


def cleanup_isolated_home_and_tmp(base_dir):
    """Remove the sibling _home and _tmp directories for base_dir."""
    root = os.path.abspath(base_dir)
    for suffix in ("_home", "_tmp"):
        d = root + suffix
        if os.path.exists(d):
            shutil.rmtree(d, ignore_errors=True)


def _wrap_shell_with_isolated_python3(cmd, task_dir):
    """Prepend a bash function `python3` that always invokes `/usr/bin/python3 -I` with `task_dir` added to sys.path."""
    import base64
    real_py = "/usr/bin/python3" if os.path.exists("/usr/bin/python3") else (shutil.which("python3") or "/usr/bin/python3")
    td = os.path.abspath(task_dir)
    runner = (
        "import os, runpy, sys\n"
        f"td = {td!r}\n"
        f"real_py = {real_py!r}\n"
        "args = sys.argv[1:]\n"
        "while args and args[0] in ('-I', '-B'):\n"
        "    args = args[1:]\n"
        "if not args:\n"
        "    os.execv(real_py, [real_py, '-I', '-B'])\n"
        "if args[0] == '-c' and len(args) >= 2:\n"
        "    code = args[1]\n"
        "    sys.argv = ['-c'] + args[2:]\n"
        "    if td not in sys.path: sys.path.insert(0, td)\n"
        "    exec(compile(code, '<string>', 'exec'), {'__name__': '__main__'})\n"
        "elif args[0] == '-m' and len(args) >= 2:\n"
        "    mod = args[1]\n"
        "    sys.argv = [mod] + args[2:]\n"
        "    if td not in sys.path: sys.path.insert(0, td)\n"
        "    runpy.run_module(mod, run_name='__main__', alter_sys=True)\n"
        "elif not args[0].startswith('-'):\n"
        "    sp = os.path.abspath(args[0])\n"
        "    sd = os.path.dirname(sp)\n"
        "    sys.argv = args\n"
        "    if td not in sys.path: sys.path.insert(0, td)\n"
        "    if sd not in sys.path: sys.path.insert(0, sd)\n"
        "    runpy.run_path(sp, run_name='__main__')\n"
        "else:\n"
        "    os.execv(real_py, [real_py, '-I', '-B'] + args)\n"
    )
    b64 = base64.b64encode(runner.encode("utf-8")).decode("ascii")
    func_def = (
        f"python3() {{ {real_py} -I -B -c \"import base64; exec(base64.b64decode('{b64}').decode('utf-8'), {{'__name__': '__main__'}})\" \"$@\"; }}\n"
        "export -f python3\n"
    )
    return func_def + cmd



def has_bwrap():
    """Return True if bwrap is installed and can create a basic user/mount namespace sandbox."""
    if shutil.which("bwrap") is None:
        return False
    try:
        res = subprocess.run(
            ["bwrap", "--ro-bind", "/usr", "/usr", "--symlink", "usr/lib", "/lib", "--symlink", "usr/lib64", "/lib64",
             "--symlink", "usr/bin", "/bin", "--proc", "/proc", "--dev", "/dev", "--unshare-all", "true"],
            capture_output=True,
            timeout=5,
            env=build_minimal_env(),
        )
        return res.returncode == 0
    except Exception:
        return False



def check_prompt_leak(prompt, task):
    """Tripwire: assert no hidden fields, sentinels, or unredacted grading seeds appear in a prompt."""
    for hidden_key in ("hidden_diff", "merged_commit"):
        if dict.__contains__(task, hidden_key):
            val = dict.__getitem__(task, hidden_key)
            if val and isinstance(val, str) and len(val) >= 7 and val in prompt:
                raise AssertionError(f"LEAK TRIPWIRE TRIGGERED: '{hidden_key}' content leaked into prompt!")
    if "LEAK_SENTINEL" in prompt or "ORACLE-SENTINEL" in prompt:
        raise AssertionError("LEAK TRIPWIRE TRIGGERED: sentinel string leaked into prompt!")
    if "104729" in prompt:
        raise AssertionError("LEAK TRIPWIRE TRIGGERED: literal grading seed 104729 leaked into prompt!")


def redact_grading_seed(text):
    """Redact the literal grading seed 104729 from any context sent to the model."""
    return (text or "").replace("104729", "<REDACTED_SEED>")


def build_worktree_context(task, worktree_dir, max_chars_per_file=12000):
    """Read target files from worktree_dir at base_commit so the model can edit them accurately."""
    clean_task = tasks_item6.strip_hidden(task)
    sections = []
    for rel_path in clean_task.get("files", []):
        try:
            full_path = resolve_confined_path(worktree_dir, rel_path)
        except ValueError:
            continue
        if os.path.exists(full_path) and os.path.isfile(full_path) and not os.path.islink(full_path):
            try:
                with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                    body = redact_grading_seed(f.read())
                if len(body) > max_chars_per_file:
                    body = body[:max_chars_per_file] + "\n... [truncated] ...\n"
                sections.append(f"### Existing file: {rel_path}\n```\n{body}\n```")
            except OSError:
                pass
        else:
            sections.append(f"### Target file (new): {rel_path}")
    return "\n\n".join(sections)


def format_turn_prompt(task, last_code=None, test_error=None, worktree_dir=None):
    """Format the turn prompt for the agentic loop.

    Never includes reference diffs or oracle solutions.
    """
    clean_task = tasks_item6.strip_hidden(task)
    base_prompt = clean_task["prompt"]
    file_ctx = build_worktree_context(clean_task, worktree_dir) if worktree_dir else ""
    ctx_block = f"\n\nBase files in worktree:\n\n{file_ctx}" if file_ctx else ""

    if last_code is None and test_error is None:
        prompt = (
            f"{base_prompt}{ctx_block}\n\n"
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
        check_prompt_leak(prompt, task)
        return prompt

    err_text = redact_grading_seed((test_error or "").strip())
    if len(err_text) > 2500:
        err_text = "... [truncated] ...\n" + err_text[-2500:]

    prompt = (
        f"{base_prompt}{ctx_block}\n\n"
        "Your previous changes failed automated verification with the following error:\n"
        f"```\n{err_text}\n```\n\n"
        "Analyze the error, locate the cause, and output the corrected files or unified diff."
    )
    check_prompt_leak(prompt, task)
    return prompt


def resolve_confined_path(worktree_dir, rel_path):
    """Resolve rel_path inside worktree_dir and reject absolute paths, '..', or symlink escapes."""
    if not rel_path or not isinstance(rel_path, str):
        raise ValueError("Empty or non-string path")
    norm_input = rel_path.replace("\\", "/").strip()
    if os.path.isabs(norm_input) or norm_input.startswith("/"):
        raise ValueError(f"Absolute path rejected: {rel_path}")
    parts = [p for p in norm_input.split("/") if p not in ("", ".")]
    if not parts or any(p == ".." for p in parts):
        raise ValueError(f"Path traversal ('..') rejected: {rel_path}")
    if parts[0] == ".git":
        raise ValueError(f"Modification of .git rejected: {rel_path}")

    root_real = os.path.realpath(worktree_dir)
    curr = root_real
    for part in parts:
        candidate = os.path.join(curr, part)
        if os.path.islink(candidate):
            raise ValueError(f"Symlink component rejected: {rel_path} ({candidate})")
        curr_real = os.path.realpath(candidate)
        if curr_real != root_real and not curr_real.startswith(root_real + os.sep):
            raise ValueError(f"Path escapes scratch root: {rel_path}")
        curr = candidate

    final_real = os.path.realpath(curr)
    if final_real == root_real or not final_real.startswith(root_real + os.sep):
        raise ValueError(f"Resolved path outside scratch root: {rel_path}")
    return curr


def validate_patch_paths(worktree_dir, patch_text):
    """Verify every path in a unified diff patch is confined to worktree_dir and patch contains no symlinks."""
    if re.search(r"^(?:new|old|deleted) file mode 120000\b", patch_text, re.M):
        raise ValueError("Symlink mode 120000 in patch rejected")
    paths_found = []
    for line in patch_text.splitlines():
        if line.startswith("diff --git "):
            m = re.match(r"^diff --git a/(\S+) b/(\S+)", line)
            if not m:
                raise ValueError(f"Malformed diff --git header: {line}")
            paths_found.extend([m.group(1), m.group(2)])
        elif line.startswith("--- ") or line.startswith("+++ "):
            tok = line[4:].split("\t")[0].strip()
            if tok == "/dev/null":
                continue
            if tok.startswith("a/") or tok.startswith("b/"):
                tok = tok[2:]
            paths_found.append(tok)
    if not paths_found:
        raise ValueError("No valid file headers found in patch")
    for p in paths_found:
        resolve_confined_path(worktree_dir, p)



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
    """Apply extracted files or unified patch to worktree_dir with strict path confinement."""
    if not updates:
        return False, "No file updates or patch found in model response."

    if "__patch__" in updates:
        patch_text = updates["__patch__"]
        try:
            validate_patch_paths(worktree_dir, patch_text)
        except ValueError as e:
            return False, f"Rejected unsafe patch path: {e}"
        patch_file = os.path.join(worktree_dir, "_agent_update.patch")
        with open(patch_file, "w", encoding="utf-8") as f:
            f.write(patch_text + "\n")
        try:
            res = subprocess.run(
                ["git", "apply", "--whitespace=nowarn", patch_file],
                cwd=worktree_dir,
                env=build_minimal_env(),
                capture_output=True,
                text=True,
                timeout=15,
            )
            if os.path.exists(patch_file):
                os.remove(patch_file)
            if res.returncode == 0:
                return True, "Patch applied successfully."
            return False, f"git apply failed: {res.stderr}"
        except Exception as e:
            if os.path.exists(patch_file):
                os.remove(patch_file)
            return False, f"Exception applying patch: {e}"

    # Validate all paths before writing any file
    resolved_items = []
    for rel_path, content in updates.items():
        try:
            full_path = resolve_confined_path(worktree_dir, rel_path)
            resolved_items.append((rel_path, full_path, content))
        except ValueError as e:
            return False, f"Rejected unsafe file path: {e}"

    written = []
    try:
        for rel_path, full_path, content in resolved_items:
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
    Should only be called when task['has_tests'] is True.
    """
    clean_task = tasks_item6.strip_hidden(task)
    if not clean_task.get("has_tests"):
        raise AssertionError("run_tests must not be executed when has_tests is False")
    cmd = clean_task.get("test_cmd")
    if not cmd:
        return True, "No test command defined for task."

    iso_cmd = _wrap_shell_with_isolated_python3(cmd, worktree_dir)
    home_dir, tmp_dir = prepare_isolated_home_and_tmp(worktree_dir)
    env = build_minimal_env(home_dir=home_dir, tmp_dir=tmp_dir)
    try:
        res = subprocess.run(
            ["bash", "-c", iso_cmd],
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
    finally:
        cleanup_isolated_home_and_tmp(worktree_dir)


def capture_worktree_diff(worktree_dir, base_commit="HEAD"):
    """Capture full diff of worktree against base_commit (or HEAD in standalone scratch repo), including untracked files."""
    clean_env = build_minimal_env()
    subprocess.run(
        ["git", "add", "-N", "."],
        cwd=worktree_dir,
        env=clean_env,
        capture_output=True,
        text=True,
    )
    target_ref = base_commit
    check_ref = subprocess.run(
        ["git", "rev-parse", "--verify", f"{base_commit}^{{commit}}"],
        cwd=worktree_dir,
        env=clean_env,
        capture_output=True,
        text=True,
    )
    if check_ref.returncode != 0:
        target_ref = "HEAD"
    diff_res = subprocess.run(
        ["git", "diff", target_ref],
        cwd=worktree_dir,
        env=clean_env,
        capture_output=True,
        text=True,
    )
    return diff_res.stdout or ""


def create_isolated_scratch_repo(repo_root, base_commit, scratch_dir):
    """Create a standalone git repository in scratch_dir populated strictly from base_commit via git archive.

    Does NOT share the main repository's object store or write to .git/worktrees, so later commits
    (including merged_commit) do not exist in the scratch repo's object database.
    """
    os.makedirs(scratch_dir, exist_ok=True)
    clean_env = build_minimal_env()
    p1 = subprocess.Popen(
        ["git", "-C", repo_root, "archive", "--format=tar", base_commit],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=clean_env,
    )
    p2 = subprocess.Popen(
        ["tar", "-x", "-C", scratch_dir],
        stdin=p1.stdout,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=clean_env,
    )
    p1.stdout.close()
    _, err2 = p2.communicate()
    _, err1 = p1.communicate()
    if p1.returncode != 0:
        raise RuntimeError(f"git archive failed for {base_commit}: {err1.decode(errors='replace')}")
    if p2.returncode != 0:
        raise RuntimeError(f"tar extract failed: {err2.decode(errors='replace')}")

    subprocess.run(["git", "init", "-q"], cwd=scratch_dir, env=clean_env, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "pilot-runner"], cwd=scratch_dir, env=clean_env, check=True)
    subprocess.run(["git", "config", "user.email", "pilot@localhost"], cwd=scratch_dir, env=clean_env, check=True)
    subprocess.run(["git", "add", "-A"], cwd=scratch_dir, env=clean_env, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-q", "--allow-empty", "-m", f"base {base_commit}"],
        cwd=scratch_dir,
        env=clean_env,
        check=True,
        capture_output=True,
    )
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=scratch_dir, env=clean_env, text=True).strip()



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
    has_tests = bool(clean_task.get("has_tests"))
    history = []
    seen_code_hashes = set()
    last_code = None
    last_err = None
    accumulated_completion_tokens = 0
    stop_reason = "max_turns"

    for turn in range(max_turns):
        t0 = time.time()
        prompt = format_turn_prompt(clean_task, last_code, last_err, worktree_dir=worktree_dir)
        check_prompt_leak(prompt, task)
        seed = 6000 + clean_task["pr_number"] * 10 + turn

        reply = ask_fn(prompt, seed)
        gen_s = round(time.time() - t0, 2)
        comp_tokens = reply.get("usage", {}).get("completion_tokens", 0) or 0
        prompt_tokens = reply.get("usage", {}).get("prompt_tokens", 0) or 0
        accumulated_completion_tokens += comp_tokens

        content = reply.get("content", "")
        code_hash = hashlib.sha256(content.encode()).hexdigest()

        # Stop check: repeat code
        if code_hash in seen_code_hashes:
            history.append({
                "turn": turn,
                "seed": seed,
                "passed": False,
                "err": "repeat_code",
                "stop": "repeat_code",
                "gen_s": gen_s,
                "tokens": comp_tokens,
                "prompt_tokens": prompt_tokens,
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
        elif not has_tests:
            # No test command when has_tests is False: do not call run_tests
            passed = True
            test_out = ""
        else:
            # Run automated tests
            passed, test_out = run_tests(clean_task, worktree_dir)

        # Stop check: repeat error
        if not passed and last_err is not None and test_out.strip() == last_err.strip():
            history.append({
                "turn": turn,
                "seed": seed,
                "passed": False,
                "err": test_out,
                "stop": "repeat_error",
                "gen_s": gen_s,
                "tokens": comp_tokens,
                "prompt_tokens": prompt_tokens,
            })
            stop_reason = "repeat_error"
            break

        history.append({
            "turn": turn,
            "seed": seed,
            "passed": passed,
            "err": "" if passed else test_out,
            "gen_s": gen_s,
            "tokens": comp_tokens,
            "prompt_tokens": prompt_tokens,
        })

        if passed:
            stop_reason = "pass" if has_tests else "applied_no_tests"
            break

        if accumulated_completion_tokens >= task_budget:
            stop_reason = "budget"
            break

        last_code = content
        last_err = test_out

    final_diff = capture_worktree_diff(worktree_dir, clean_task["base_commit"])

    return {
        "task_id": clean_task["id"],
        "pr_number": clean_task["pr_number"],
        "has_tests": has_tests,
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


def served_model(requested=None, api=None):
    """Query GET /v1/models on the served endpoint (matching run.py / agent.py convention)."""
    api = api or API_URL
    with urllib.request.urlopen(f"{api}/v1/models", timeout=10) as r:
        ids = [m["id"] for m in json.load(r)["data"]]
    if len(ids) != 1:
        raise SystemExit(f"expected exactly one served model at {api}, got {ids}")
    if requested and requested != ids[0]:
        raise SystemExit(f"--model {requested} but {api} serves {ids[0]}")
    return ids[0]


def server_info(api=None):
    """Query GET /props on the served endpoint."""
    with urllib.request.urlopen(f"{api or API_URL}/props", timeout=10) as r:
        p = json.load(r)
    return {k: p.get(k) for k in ("build_info", "model_path", "model_alias")}


def server_ask(model, api=None):
    """Return an ask_fn(prompt, seed) that queries /v1/chat/completions on the served model."""
    api = api or API_URL

    def ask(prompt, seed):
        body = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": MAX_TOKENS,
            "reasoning_budget_tokens": REASONING_BUDGET,
            "reasoning_budget_message": BUDGET_MESSAGE,
            "seed": seed,
            **SAMPLING,
        }
        req = urllib.request.Request(
            f"{api}/v1/chat/completions",
            json.dumps(body).encode(),
            {"Content-Type": "application/json"},
        )
        t = time.time()
        with urllib.request.urlopen(req, timeout=3600) as r:
            resp = json.load(r)
        ch = resp["choices"][0]
        return {
            "content": ch["message"].get("content") or "",
            "reasoning_chars": len(ch["message"].get("reasoning_content") or ""),
            "finish": ch.get("finish_reason"),
            "usage": resp.get("usage", {}),
            "gen_s": round(time.time() - t, 2),
        }

    return ask


def compute_keep_drop(testable_passed, testable_total, approved_final, total_tasks, avg_hand_fix_lines):
    """Compute pre-registered KEEP / DROP / INCONCLUSIVE / PENDING_REVIEW decision (docs/item6-pilot.md Section 9).

    Bars:
    - KEEP: test_pass >= 3/6 (50.0%) AND final_approve >= 3/7 (42.9%) AND avg_hand_fix_lines <= 20.
    - DROP: test_pass < 2/6 (33.3%) OR (approved_final is not None and final_approve < 2/7 (28.6%)).
    - INCONCLUSIVE: intermediate (defaults to DROP unless extended).
    - PENDING_REVIEW: tests meet >= 2/6, but adversarial-reviewer verdicts have not been supplied yet.
    """
    test_rate = (testable_passed / testable_total) if testable_total > 0 else 0.0
    if test_rate < (2.0 / 6.0 - 1e-9):
        return "DROP"
    if approved_final is None:
        return "PENDING_REVIEW"
    app_rate = (approved_final / total_tasks) if total_tasks > 0 else 0.0
    if app_rate < (2.0 / 7.0 - 1e-9):
        return "DROP"
    if (
        test_rate >= (3.0 / 6.0 - 1e-9)
        and app_rate >= (3.0 / 7.0 - 1e-9)
        and (avg_hand_fix_lines is None or avg_hand_fix_lines <= 20.0)
    ):
        return "KEEP"
    return "INCONCLUSIVE"



def run_subcommand(label, tasks_arg=None, api=API_URL, model=None, max_turns=MAX_TURNS_DEFAULT,
                   task_budget=TASK_BUDGET_TOKENS, repo_root=None, results_dir=None, ask_fn=None):
    """Execute the `run` subcommand: per PR, create scratch git worktree at base_commit, run loop, save diff & JSONL."""
    if repo_root is None:
        repo_root = os.path.abspath(os.path.join(HERE, "..", ".."))
    if results_dir is None:
        results_dir = os.path.join(HERE, "results")
    os.makedirs(results_dir, exist_ok=True)
    diffs_dir = os.path.join(results_dir, f"{label}.diffs")
    os.makedirs(diffs_dir, exist_ok=True)
    jsonl_path = os.path.join(results_dir, f"{label}.jsonl")

    all_tasks = tasks_item6.load_tasks()
    if tasks_arg:
        want = [x.strip() for x in tasks_arg.split(",") if x.strip()]
        by_id = {t["id"]: t for t in all_tasks}
        unknown = [w for w in want if w not in by_id]
        if unknown:
            raise SystemExit(f"unknown task ids: {unknown}")
        selected_tasks = [by_id[w] for w in want]
    else:
        selected_tasks = all_tasks

    if ask_fn is None:
        resolved_model = served_model(model, api=api)
        srv_info = server_info(api=api)
        ask_fn = server_ask(resolved_model, api=api)
    else:
        resolved_model = model or "mock"
        srv_info = {"build_info": "mock", "model_path": "mock", "model_alias": resolved_model}

    # Load existing rows so running one task at a time updates/appends cleanly
    existing_by_id = {}
    if os.path.exists(jsonl_path):
        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    row = json.loads(line)
                    existing_by_id[row["task_id"]] = row

    results = []
    for task in selected_tasks:
        clean_task = tasks_item6.strip_hidden(task)
        task_id = clean_task["id"]
        base_sha = clean_task["base_commit"]
        wt_dir = tempfile.mkdtemp(prefix=f"wt_{label}_{task_id}_")
        t_start = time.time()
        try:
            create_isolated_scratch_repo(repo_root, base_sha, wt_dir)
            res = run_task_loop(
                clean_task,
                ask_fn,
                wt_dir,
                max_turns=max_turns,
                task_budget=task_budget,
            )
            res["wall_s"] = round(time.time() - t_start, 2)
            res["model"] = resolved_model
            res["server"] = srv_info

            diff_file = os.path.join(diffs_dir, f"{task_id}.diff")
            with open(diff_file, "w", encoding="utf-8") as df:
                df.write(res["final_diff"])
            res["diff_file"] = os.path.relpath(diff_file, repo_root) if diff_file.startswith(repo_root) else diff_file

            existing_by_id[task_id] = res
            results.append(res)
            print(
                f"{task_id:14} pr=#{res['pr_number']:<2} has_tests={str(res['has_tests']):<5} "
                f"passed={str(res['passed']):<5} stop={res['stop_reason']:<16} turns={res['turns_executed']} "
                f"tok={res['total_completion_tokens']} diff_lines={len(res['final_diff'].splitlines())}",
                flush=True,
            )
        finally:
            if os.path.exists(wt_dir):
                shutil.rmtree(wt_dir, ignore_errors=True)

    # Write updated JSONL in canonical task order
    order_ids = [t["id"] for t in all_tasks]
    ordered_rows = [existing_by_id[tid] for tid in order_ids if tid in existing_by_id]
    for tid, r in existing_by_id.items():
        if tid not in order_ids:
            ordered_rows.append(r)

    with open(jsonl_path, "w", encoding="utf-8") as f:
        for r in ordered_rows:
            f.write(json.dumps(r) + "\n")

    return results


def _extract_selftest_block(repo_root, merged_sha, rel_path):
    """Extract the authoritative `def selftest():` block from `merged_sha:rel_path` in the main repo."""
    src = subprocess.check_output(
        ["git", "-C", repo_root, "show", f"{merged_sha}:{rel_path}"],
        env=build_minimal_env(),
        text=True,
    )
    body = src.split("def selftest():", 1)[1].split("def main():", 1)[0]
    return "def selftest():" + body


def _run_harness_grade_spec(task, grade_dir, repo_root, timeout=180):
    """Execute a harness-owned grade wrapper in grade_dir with positive completion proof and exact test counts.

    Security & Isolation properties:
    - Never puts the per-run sentinel token in argv (/proc/self/cmdline) or os.environ (/proc/self/environ).
      Instead, the parent writes the sentinel token to standard input; the child wrapper reads the token from
      stdin and closes/replaces fd 0 with /dev/null BEFORE importing or executing any model-owned code.
    - Runs Python with `-I` (isolated mode: no user-site packages, no PYTHON* env vars, no automatic cwd on sys.path;
      the wrapper explicitly adds the task scratch root and module_dir to sys.path).
    - Creates a fresh empty HOME and TMPDIR for every grade invocation and uses a fixed system PATH.
    - Any sys.exit(0) or os._exit(0) inside a model module during import or test execution aborts before
      the wrapper reaches the count verification and sentinel write, causing grade to return False.
    """
    home_dir, tmp_dir = prepare_isolated_home_and_tmp(grade_dir)
    clean_env = build_minimal_env(home_dir=home_dir, tmp_dir=tmp_dir)
    merged_sha = dict.__getitem__(task, "merged_commit")
    spec = task.get("grade_spec")
    sentinel = f"@@PILOT_GRADE_OK_{secrets.token_hex(16)}@@"

    try:
        if not spec:
            cmd = task.get("test_cmd")
            if not cmd:
                return True, ""
            res = subprocess.run(
                ["bash", "-c", _wrap_shell_with_isolated_python3(cmd, grade_dir)],
                cwd=grade_dir,
                env=clean_env,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return (res.returncode == 0), (res.stdout or "") + (res.stderr or "")

        mode = spec["mode"]

        if mode == "shell":
            iso_shell_cmd = _wrap_shell_with_isolated_python3(spec["cmd"], grade_dir)
            wrapper_cmd = (
                "set -e\n"
                "IFS= read -r _PILOT_TOK\n"
                "exec </dev/null\n"
                f"{iso_shell_cmd}\n"
                "printf '%s\\n' \"$_PILOT_TOK\"\n"
            )
            res = subprocess.run(
                ["bash", "-c", wrapper_cmd],
                input=sentinel + "\n",
                cwd=grade_dir,
                env=clean_env,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            output = (res.stdout or "") + (res.stderr or "")
            if res.returncode != 0 or sentinel not in output:
                return False, output + "\n[grade_wrapper: missing sentinel or non-zero exit]"
            lines_without_sentinel = [ln.rstrip("\r\n") for ln in output.splitlines() if ln.strip() and ln.strip() != sentinel]
            pat = re.compile(spec["count_pattern"])
            matched_count = sum(1 for ln in lines_without_sentinel if pat.search(ln))
            if matched_count != spec["expected_test_count"]:
                return False, output + f"\n[grade_wrapper: expected count {spec['expected_test_count']}, got {matched_count}]"
            req_last = spec.get("required_last_line")
            if req_last and (not lines_without_sentinel or lines_without_sentinel[-1].strip() != req_last):
                return False, output + f"\n[grade_wrapper: expected last line {req_last!r}]"
            return True, output

        # Common Python preamble that reads the secret token from stdin and points fd 0 to /dev/null
        # before any model module is imported.
        stdin_token_preamble = (
            "import os, sys\n"
            "_tok = sys.stdin.readline().rstrip('\\r\\n')\n"
            "_devnull = os.open(os.devnull, os.O_RDONLY)\n"
            "os.dup2(_devnull, 0)\n"
            "os.close(_devnull)\n"
            "sys.stdin = open(os.devnull, 'r')\n"
            "sys.path.insert(0, os.getcwd())\n"
        )

        if mode == "selftest_file":
            st_code = _extract_selftest_block(repo_root, merged_sha, spec["source_file_at_merged"])
            st_path = os.path.join(grade_dir, "_pilot_merged_selftest.py")
            with open(st_path, "w", encoding="utf-8") as f:
                f.write(st_code)
            driver = (
                stdin_token_preamble
                + "import contextlib, io\n"
                + f"sys.path.insert(0, os.path.join(os.getcwd(), {spec['module_dir']!r}))\n"
                + f"import {spec['module_name']} as mod\n"
                + "with open('_pilot_merged_selftest.py', 'r', encoding='utf-8') as f:\n"
                + "    st_src = f.read()\n"
                + "exec(compile(st_src, '_pilot_merged_selftest.py', 'exec'), mod.__dict__)\n"
                + "buf = io.StringIO()\n"
                + "with contextlib.redirect_stdout(buf):\n"
                + "    rc = mod.selftest()\n"
                + "out = buf.getvalue()\n"
                + "sys.stdout.write(out)\n"
                + "ok_count = sum(1 for ln in out.splitlines() if ln.strip().startswith('ok '))\n"
                + "fail_count = sum(1 for ln in out.splitlines() if ln.strip().startswith('FAIL '))\n"
                + f"if rc == 0 and fail_count == 0 and ok_count == {spec['expected_test_count']}:\n"
                + "    print(_tok)\n"
                + "else:\n"
                + f"    print(f'[grade_wrapper: rc={{rc}} ok={{ok_count}}/{spec['expected_test_count']} fail={{fail_count}}]')\n"
                + "    sys.exit(1)\n"
            )
            res = subprocess.run(
                ["python3", "-I", "-B", "-c", driver],
                input=sentinel + "\n",
                cwd=grade_dir,
                env=clean_env,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            if os.path.exists(st_path):
                os.remove(st_path)
            output = (res.stdout or "") + (res.stderr or "")
            return (res.returncode == 0 and sentinel in output), output

        if mode == "unittest":
            driver = (
                stdin_token_preamble
                + "import unittest\n"
                + "sys.path.insert(0, os.path.join(os.getcwd(), 'bench/loop'))\n"
                + f"suite = unittest.defaultTestLoader.loadTestsFromName({spec['test_module'].replace('/', '.')[:-3]!r})\n"
                + "runner = unittest.TextTestRunner(stream=sys.stdout, verbosity=2)\n"
                + "result = runner.run(suite)\n"
                + f"if not result.wasSuccessful() or result.testsRun != {spec['expected_test_count']} or len(result.skipped) > 0:\n"
                + f"    print(f'[grade_wrapper: ran={{result.testsRun}}/{spec['expected_test_count']} skipped={{len(result.skipped)}}]')\n"
                + "    sys.exit(1)\n"
            )
            if spec.get("extra_cmd"):
                driver += (
                    "import tasks_v10\n"
                    "assert len(tasks_v10.TASKS) == 90\n"
                )
            driver += "print(_tok)\n"
            res = subprocess.run(
                ["python3", "-I", "-B", "-c", driver],
                input=sentinel + "\n",
                cwd=grade_dir,
                env=clean_env,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            output = (res.stdout or "") + (res.stderr or "")
            return (res.returncode == 0 and sentinel in output), output

        if mode == "unittest_and_selftest_file":
            st_code = _extract_selftest_block(repo_root, merged_sha, spec["source_file_at_merged"])
            st_path = os.path.join(grade_dir, "_pilot_merged_selftest.py")
            with open(st_path, "w", encoding="utf-8") as f:
                f.write(st_code)
            driver = (
                stdin_token_preamble
                + "import contextlib, io, unittest\n"
                + f"sys.path.insert(0, os.path.join(os.getcwd(), {spec['module_dir']!r}))\n"
                + f"suite = unittest.defaultTestLoader.loadTestsFromName({spec['test_module'].replace('/', '.')[:-3]!r})\n"
                + "runner = unittest.TextTestRunner(stream=sys.stdout, verbosity=2)\n"
                + "result = runner.run(suite)\n"
                + f"if not result.wasSuccessful() or result.testsRun != {spec['expected_test_count']} or len(result.skipped) > 0:\n"
                + f"    print(f'[grade_wrapper: unittest ran={{result.testsRun}}/{spec['expected_test_count']}]')\n"
                + "    sys.exit(1)\n"
                + f"import {spec['module_name']} as mod\n"
                + "with open('_pilot_merged_selftest.py', 'r', encoding='utf-8') as f:\n"
                + "    st_src = f.read()\n"
                + "exec(compile(st_src, '_pilot_merged_selftest.py', 'exec'), mod.__dict__)\n"
                + "buf = io.StringIO()\n"
                + "with contextlib.redirect_stdout(buf):\n"
                + "    rc = mod.selftest()\n"
                + "out = buf.getvalue()\n"
                + "sys.stdout.write(out)\n"
                + "ok_count = sum(1 for ln in out.splitlines() if ln.strip().startswith('ok '))\n"
                + "fail_count = sum(1 for ln in out.splitlines() if ln.strip().startswith('FAIL '))\n"
                + f"if rc == 0 and fail_count == 0 and ok_count == {spec['expected_selftest_count']}:\n"
                + "    print(_tok)\n"
                + "else:\n"
                + f"    print(f'[grade_wrapper: selftest rc={{rc}} ok={{ok_count}}/{spec['expected_selftest_count']} fail={{fail_count}}]')\n"
                + "    sys.exit(1)\n"
            )
            res = subprocess.run(
                ["python3", "-I", "-B", "-c", driver],
                input=sentinel + "\n",
                cwd=grade_dir,
                env=clean_env,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            if os.path.exists(st_path):
                os.remove(st_path)
            output = (res.stdout or "") + (res.stderr or "")
            return (res.returncode == 0 and sentinel in output), output

        raise ValueError(f"Unknown grade_spec mode: {mode}")
    finally:
        cleanup_isolated_home_and_tmp(grade_dir)


def regrade_task_diff(task, final_diff, repo_root=None, timeout=180):
    """Independently grade a task's final_diff in a fresh clean copy of base_commit with test files restored from merged_commit.

    Never trusts the in-loop `passed` flag or bare exit code 0:
    1. Creates a fresh standalone scratch tree at `base_commit`.
    2. Applies `final_diff` (if non-empty) with path confinement checks.
    3. Overwrites any `test_files` in the scratch tree with their authoritative versions from `merged_commit`
       so model edits to test files (e.g. an `exit 0` bypass) are ignored for grading.
    4. Runs the harness-owned grade wrapper (`_run_harness_grade_spec`) with a minimal allowlisted environment
       (no PILOT_REPO_ROOT, no GIT_*), requiring exact expected test counts and a post-completion sentinel.
    """
    if not task.get("has_tests"):
        return None, "Not a testable task"
    if repo_root is None:
        repo_root = os.path.abspath(os.path.join(HERE, "..", ".."))

    base_sha = dict.__getitem__(task, "base_commit")
    merged_sha = dict.__getitem__(task, "merged_commit")
    grade_dir = tempfile.mkdtemp(prefix=f"grade_{task['id']}_")
    clean_env = build_minimal_env()
    try:
        create_isolated_scratch_repo(repo_root, base_sha, grade_dir)
        if final_diff and final_diff.strip():
            ok, msg = apply_updates(grade_dir, {"__patch__": final_diff.rstrip("\n")})
            if not ok:
                return False, f"Failed applying final_diff during grade: {msg}"

        # Restore authoritative test files from merged_commit (overwriting any model tampering)
        for tf in task.get("test_files", []):
            full_tf = resolve_confined_path(grade_dir, tf)
            os.makedirs(os.path.dirname(full_tf), exist_ok=True)
            show_res = subprocess.run(
                ["git", "-C", repo_root, "show", f"{merged_sha}:{tf}"],
                env=clean_env,
                capture_output=True,
            )
            if show_res.returncode != 0:
                return False, f"Failed restoring test file {tf} from {merged_sha}"
            with open(full_tf, "wb") as f:
                f.write(show_res.stdout)

        return _run_harness_grade_spec(task, grade_dir, repo_root, timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, f"ERROR: grade test command timed out after {timeout} seconds."
    except Exception as e:
        return False, f"ERROR during regrade_task_diff: {e}"
    finally:
        shutil.rmtree(grade_dir, ignore_errors=True)



def grade_subcommand(label, reviews_file=None, repo_root=None, results_dir=None, tasks_override=None):
    """Execute the `grade` subcommand: score recorded diffs against hidden diffs, merge review verdicts, compute KEEP/DROP."""
    if repo_root is None:
        repo_root = os.path.abspath(os.path.join(HERE, "..", ".."))
    if results_dir is None:
        results_dir = os.path.join(HERE, "results")

    jsonl_path = os.path.join(results_dir, f"{label}.jsonl")
    if not os.path.exists(jsonl_path):
        raise SystemExit(f"Results file not found: {jsonl_path}")

    rows_by_id = {}
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                r = json.loads(line)
                rows_by_id[r["task_id"]] = r

    if reviews_file is None:
        default_rev = os.path.join(results_dir, f"{label}.reviews.json")
        if os.path.exists(default_rev):
            reviews_file = default_rev

    reviews_by_id = {}
    if reviews_file and os.path.exists(reviews_file):
        with open(reviews_file, "r", encoding="utf-8") as rf:
            rev_data = json.load(rf)
            if isinstance(rev_data, dict):
                reviews_by_id = rev_data.get("reviews", rev_data)
            elif isinstance(rev_data, list):
                reviews_by_id = {item["task_id"]: item for item in rev_data}

    all_tasks = tasks_override if tasks_override is not None else tasks_item6.load_tasks()
    per_task = []
    testable_total = 0
    testable_passed = 0
    approved_first = 0
    approved_final = 0
    has_all_reviews = True
    hand_fix_lines_approved = []

    for task in all_tasks:
        tid = task["id"]
        if tid not in rows_by_id:
            continue
        row = rows_by_id[tid]
        has_tests = bool(task.get("has_tests"))
        local_diff = row.get("final_diff", "")
        in_loop_passed = bool(row.get("passed")) if has_tests else None
        if has_tests:
            testable_total += 1
            passed, grade_test_out = regrade_task_diff(task, local_diff, repo_root=repo_root)
            if passed:
                testable_passed += 1
        else:
            passed = None
            grade_test_out = ""

        hidden_diff = task.get("hidden_diff") or tasks_item6.get_hidden_diff(task, repo_root=repo_root)
        diff_metrics = evaluate_diff(local_diff, hidden_diff)

        rev = reviews_by_id.get(tid)
        if rev is not None:
            if not isinstance(rev, dict):
                raise ValueError(f"Review record for {tid} must be a dict, got {type(rev).__name__}")
            v1 = rev.get("verdict") if "verdict" in rev else rev.get("first_verdict")
            v_final = rev.get("final_verdict", v1)
            if v1 not in ("APPROVE", "APPROVE-WITH-NITS", "REQUEST-CHANGES") or v_final not in (
                "APPROVE",
                "APPROVE-WITH-NITS",
                "REQUEST-CHANGES",
            ):
                raise ValueError(f"Review record for {tid} has missing or invalid verdict: {rev!r}")
            if "hand_fix_lines" not in rev or rev["hand_fix_lines"] is None or isinstance(rev["hand_fix_lines"], bool) or not isinstance(rev["hand_fix_lines"], (int, float)):
                raise ValueError(f"Review record for {tid} is missing numeric hand_fix_lines: {rev!r}")
            hf_lines = rev["hand_fix_lines"]
            is_app1 = v1 in ("APPROVE", "APPROVE-WITH-NITS")
            is_app_final = v_final in ("APPROVE", "APPROVE-WITH-NITS")
            if is_app1:
                approved_first += 1
            if is_app_final:
                approved_final += 1
                hand_fix_lines_approved.append(hf_lines)
        else:
            has_all_reviews = False
            v1 = None
            v_final = None
            hf_lines = None

        per_task.append({
            "task_id": tid,
            "pr_number": task["pr_number"],
            "has_tests": has_tests,
            "in_loop_passed": in_loop_passed,
            "test_passed": passed,
            "stop_reason": row.get("stop_reason"),
            "turns_executed": row.get("turns_executed"),
            "total_completion_tokens": row.get("total_completion_tokens"),
            "wall_s": row.get("wall_s"),
            "diff_file": row.get("diff_file"),
            "diff_metrics": diff_metrics,
            "first_verdict": v1,
            "final_verdict": v_final,
            "hand_fix_lines": hf_lines,
        })

    total_evaluated = len(per_task)
    final_app_count = approved_final if (has_all_reviews and total_evaluated > 0) else None
    avg_hf = (sum(hand_fix_lines_approved) / len(hand_fix_lines_approved)) if hand_fix_lines_approved else 0.0

    decision = compute_keep_drop(
        testable_passed=testable_passed,
        testable_total=testable_total,
        approved_final=final_app_count,
        total_tasks=total_evaluated,
        avg_hand_fix_lines=avg_hf if final_app_count is not None else None,
    )

    grade_summary = {
        "label": label,
        "tasks_evaluated": total_evaluated,
        "testable_tasks": testable_total,
        "testable_passed": testable_passed,
        "test_pass_rate": round(testable_passed / testable_total, 4) if testable_total > 0 else 0.0,
        "reviews_complete": has_all_reviews and total_evaluated > 0,
        "approved_first_pass": approved_first if has_all_reviews else None,
        "approved_final": final_app_count,
        "final_approve_rate": round(final_app_count / total_evaluated, 4) if (final_app_count is not None and total_evaluated > 0) else None,
        "avg_hand_fix_lines_per_approved": round(avg_hf, 2) if final_app_count is not None else None,
        "decision": decision,
        "per_task": per_task,
    }

    grade_path = os.path.join(results_dir, f"{label}.grade.json")
    with open(grade_path, "w", encoding="utf-8") as gf:
        json.dump(grade_summary, gf, indent=2)

    print(json.dumps({k: v for k, v in grade_summary.items() if k != "per_task"}, indent=2), flush=True)
    return grade_summary


def main(argv=None):
    parser = argparse.ArgumentParser(description="Item 6 Pilot PR Loop Runner")
    parser.add_argument("--selftest", action="store_true", help="Run CPU-only self-tests")
    parser.add_argument("--label", type=str, default="item6-pilot", help="Run label")
    parser.add_argument("--tasks", type=str, default=None, help="Comma-separated task IDs")
    parser.add_argument("--api", type=str, default=API_URL, help="Served model API URL (default :8081)")
    parser.add_argument("--model", type=str, default=None, help="Expected model alias")
    parser.add_argument("-k", "--max-turns", type=int, default=MAX_TURNS_DEFAULT, help="Max turns per task")
    parser.add_argument("--task-budget", type=int, default=TASK_BUDGET_TOKENS, help="Max completion tokens per task")

    subparsers = parser.add_subparsers(dest="subcommand")

    p_run = subparsers.add_parser("run", help="Run agentic loop on PR tasks in scratch worktrees")
    p_run.add_argument("--label", type=str, default="item6-pilot", help="Run label")
    p_run.add_argument("--tasks", type=str, default=None, help="Comma-separated task IDs")
    p_run.add_argument("--api", type=str, default=API_URL, help="Served model API URL (default :8081)")
    p_run.add_argument("--model", type=str, default=None, help="Expected model alias")
    p_run.add_argument("-k", "--max-turns", type=int, default=MAX_TURNS_DEFAULT, help="Max turns per task")
    p_run.add_argument("--task-budget", type=int, default=TASK_BUDGET_TOKENS, help="Max completion tokens per task")

    p_grade = subparsers.add_parser("grade", help="Grade recorded worktree diffs and compute KEEP/DROP")
    p_grade.add_argument("--label", type=str, default="item6-pilot", help="Run label")
    p_grade.add_argument("--reviews-file", type=str, default=None, help="Path to adversarial-reviewer verdicts JSON")

    args = parser.parse_args(argv)

    if args.selftest:
        sys.exit(selftest())

    if args.subcommand == "run":
        run_subcommand(
            label=args.label,
            tasks_arg=args.tasks,
            api=args.api,
            model=args.model,
            max_turns=args.max_turns,
            task_budget=args.task_budget,
        )
        return 0

    if args.subcommand == "grade":
        grade_subcommand(
            label=args.label,
            reviews_file=args.reviews_file,
        )
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
