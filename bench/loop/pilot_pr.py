#!/usr/bin/env python3
"""Item 6 Pilot: Real-PR evaluation harness and runner.

Executes the small-model agentic loop with test feedback on real repository PR tasks.
Can be executed with:
  python3 bench/loop/pilot_pr.py --selftest      # runs CPU-only selftest with mock model
  python3 bench/loop/pilot_pr.py run --label L   # runs benchmark loop against :8081
  python3 bench/loop/pilot_pr.py grade --label L # offline evaluation of local diffs against hidden reference
"""
import argparse
import ast
import fnmatch
import hashlib
import json
import math
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import tasks_item6  # noqa: E402

API_URL = "http://127.0.0.1:8081"
SAMPLING = {"temperature": 0.6, "top_p": 0.95, "top_k": 20}
REASONING_BUDGET = 4096
MAX_TOKENS = 8192
SLOT_CTX_DEFAULT = 65536
RESERVED_OUTPUT_TOKENS = MAX_TOKENS
MAX_TURNS_DEFAULT = 12
TASK_BUDGET_TOKENS = 32768
CEILING_SECONDS_DEFAULT = 4320
TASK_WALL_BUDGET_DEFAULT = CEILING_SECONDS_DEFAULT // 7  # 617 s per task across 7 tasks (7 * 617 = 4319 <= 4320)
BUDGET_MESSAGE = "Reasoning budget reached. Output your tool call JSON block now."

READ_FILE_MAX_LINES = 250
GREP_MAX_MATCHES = 50
LIST_FILES_MAX_ENTRIES = 200
MAX_EXISTING_FILE_OVERWRITES = 1
MIN_OVERWRITE_JUSTIFICATION_LEN = 15
SEARCH_REPLACE_REWRITE_MIN_LINES = 80
SEARCH_REPLACE_REWRITE_MAX_RATIO = 0.80
STUB_GUARD_MIN_REMOVED_LINES = 40
STUB_GUARD_MIN_REMOVED_RATIO = 0.50
STUB_GUARD_MOVE_MATCH_MIN_RATIO = 0.50
TOOL_RESULT_MAX_CHARS = 12000

RECORD_SCHEMA_VERSION = 2
ABORT_STOP_REASONS = frozenset({
    "task_error",
    "context_overflow",
    "request_error",
    "prompt_leak",
    "task_wall_budget",
})

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
    """Create fresh empty HOME, TMPDIR, and private (mode 0700) inner-bwrap wrapper directories."""
    root = os.path.abspath(base_dir)
    home_dir = root + "_home"
    tmp_dir = root + "_tmp"
    shim_dir = root + "_shim"
    for d in (home_dir, tmp_dir, shim_dir):
        if os.path.exists(d):
            shutil.rmtree(d, ignore_errors=True)
    os.makedirs(home_dir, mode=0o700, exist_ok=False)
    os.makedirs(tmp_dir, mode=0o700, exist_ok=False)
    os.makedirs(shim_dir, mode=0o700, exist_ok=False)
    _write_inner_bwrap_wrapper(shim_dir)
    return home_dir, tmp_dir, shim_dir


def cleanup_isolated_home_and_tmp(base_dir):
    """Remove the sibling _home, _tmp, and _shim directories for base_dir."""
    root = os.path.abspath(base_dir)
    for suffix in ("_home", "_tmp", "_shim"):
        d = root + suffix
        if os.path.exists(d):
            shutil.rmtree(d, ignore_errors=True)


def _write_inner_bwrap_wrapper(shim_dir):
    """Write a fresh inner `bwrap` wrapper script in shim_dir (mode 0700, created exclusively).

    When running inside the outer `/usr/bin/bwrap` sandbox (which isolates PID, mount, user,
    and network namespaces), inner `bwrap` calls from `run.py` invoke this wrapper. It validates
    that outer sandbox isolation is in place and the requested mount layout is honored, failing closed
    if outer isolation or required paths are missing. Never copies any system binary and never adds
    a fallback that runs without isolation.
    """
    shim_path = os.path.join(shim_dir, "bwrap")
    script = (
        "#!/usr/bin/env python3\n"
        "import os, sys\n\n"
        "def fail():\n"
        "    sys.exit(1)\n\n"
        "if not os.path.exists('/pilot_shim'):\n"
        "    fail()\n\n"
        "argv = sys.argv[1:]\n"
        "bind_map = {}\n"
        "chdir_to, clear_env, env_vars, new_sess, cmd = None, False, {}, False, []\n"
        "i = 0\n"
        "while i < len(argv):\n"
        "    arg = argv[i]\n"
        "    if arg in ('--bind', '--ro-bind', '--dev-bind'):\n"
        "        if i + 2 >= len(argv): fail()\n"
        "        bind_map[argv[i+2]] = argv[i+1]\n"
        "        i += 3\n"
        "    elif arg == '--symlink':\n"
        "        if i + 2 >= len(argv): fail()\n"
        "        i += 3\n"
        "    elif arg in ('--proc', '--dev', '--tmpfs', '--dir'):\n"
        "        if i + 1 >= len(argv): fail()\n"
        "        i += 2\n"
        "    elif arg == '--chdir':\n"
        "        if i + 1 >= len(argv): fail()\n"
        "        chdir_to = argv[i+1]\n"
        "        i += 2\n"
        "    elif arg == '--setenv':\n"
        "        if i + 2 >= len(argv): fail()\n"
        "        env_vars[argv[i+1]] = argv[i+2]\n"
        "        i += 3\n"
        "    elif arg == '--unsetenv':\n"
        "        if i + 1 >= len(argv): fail()\n"
        "        env_vars.pop(argv[i+1], None)\n"
        "        i += 2\n"
        "    elif arg == '--clearenv':\n"
        "        clear_env = True\n"
        "        i += 1\n"
        "    elif arg == '--new-session':\n"
        "        new_sess = True\n"
        "        i += 1\n"
        "    elif arg in ('--unshare-all', '--die-with-parent') or arg.startswith('--unshare-'):\n"
        "        i += 1\n"
        "    elif arg == '--':\n"
        "        cmd = argv[i+1:]\n"
        "        break\n"
        "    elif arg.startswith('--'):\n"
        "        i += 1\n"
        "    else:\n"
        "        cmd = argv[i:]\n"
        "        break\n"
        "if not cmd: fail()\n\n"
        "for req in ('/usr', '/proc', '/dev', '/tmp'):\n"
        "    if not os.path.exists(req): fail()\n\n"
        "for dst, src in bind_map.items():\n"
        "    if not os.path.exists(src): fail()\n"
        "    if dst != src and not os.path.exists(dst):\n"
        "        try: os.symlink(src, dst)\n"
        "        except OSError: pass\n\n"
        "target_cwd = bind_map.get(chdir_to, chdir_to)\n"
        "if target_cwd:\n"
        "    try: os.chdir(target_cwd)\n"
        "    except OSError: fail()\n\n"
        "final_env = dict(env_vars) if clear_env else {**os.environ, **env_vars}\n"
        "if new_sess:\n"
        "    try: os.setsid()\n"
        "    except OSError: pass\n\n"
        "try:\n"
        "    os.execvpe(cmd[0], cmd, final_env)\n"
        "except Exception:\n"
        "    fail()\n"
    )
    fd = os.open(shim_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o700)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(script)
    return shim_path


def build_outer_bwrap_cmd(task_dir, home_dir, tmp_dir, shim_dir, inner_argv, env_dict, ro_binds=None):
    """Wrap inner_argv in an outer /usr/bin/bwrap sandbox that isolates filesystem, PID, and network namespaces.

    Sandbox invariants:
    - Always invokes the system `/usr/bin/bwrap` directly (never copies the binary).
    - Fails closed if `/usr/bin/bwrap` is missing.
    - Read-only binds `/usr`, `/bin`, `/lib`, `/lib64`, `/etc` and mounts the private `shim_dir` read-only at
      `/pilot_shim` (placed first on `PATH` so inner `bwrap` calls from `run.py` invoke the wrapper in the
      already-isolated namespace without creating a second user namespace).
    - Mounts fresh `--dev /dev` and `--proc /proc`, and fresh `--tmpfs` over `/tmp`, `/home`, and `/data`
      so the main checkout (`/home/aj/projects/strix-halo-lab`), this worktree, `/data`, and the real user
      home directory are absent and unreadable.
    - Writable binds `task_dir` (at `/work`), `home_dir` (at `/home/pilot`), and `tmp_dir` (at `/tmp`),
      with `--chdir /work`.
    - If ro_binds is provided, mounts each (src, dst) read-only over `/work` after the writable bind.
    """
    bwrap_bin = "/usr/bin/bwrap"
    if not os.path.exists(bwrap_bin):
        raise RuntimeError("/usr/bin/bwrap is required for sandboxed execution; refusing to run unsandboxed")

    cmd = [
        bwrap_bin,
        "--ro-bind", "/usr", "/usr",
        "--symlink", "usr/lib", "/lib",
        "--symlink", "usr/lib64", "/lib64",
        "--symlink", "usr/bin", "/bin",
        "--ro-bind", "/etc", "/etc",
        "--ro-bind", os.path.abspath(shim_dir), "/pilot_shim",
        "--proc", "/proc",
        "--dev", "/dev",
        "--tmpfs", "/tmp",
        "--tmpfs", "/home",
        "--tmpfs", "/data",
        "--bind", os.path.abspath(tmp_dir), "/tmp",
        "--bind", os.path.abspath(home_dir), "/home/pilot",
        "--bind", os.path.abspath(task_dir), "/work",
    ]
    if ro_binds:
        for src, dst in ro_binds:
            cmd.extend(["--ro-bind", os.path.abspath(src), dst])
    cmd.extend([
        "--chdir", "/work",
        "--unshare-user",
        "--unshare-pid",
        "--unshare-net",
        "--unshare-ipc",
        "--unshare-uts",
        "--as-pid-1",
        "--die-with-parent",
        "--clearenv",
    ])
    sandbox_env = dict(env_dict)
    sandbox_env["HOME"] = "/home/pilot"
    sandbox_env["TMPDIR"] = "/tmp"
    sandbox_env["PATH"] = f"/pilot_shim:{FIXED_SYSTEM_PATH}"
    for k, v in sorted(sandbox_env.items()):
        cmd.extend(["--setenv", str(k), str(v)])
    cmd.extend(inner_argv)
    return cmd


def _wrap_shell_with_isolated_python3(cmd, task_dir="/work"):
    """Prepend a bash function `python3` that always invokes `/usr/bin/python3 -I -B` with `task_dir` added to sys.path."""
    import base64
    real_py = "/usr/bin/python3" if os.path.exists("/usr/bin/bwrap") else (shutil.which("python3") or "/usr/bin/python3")
    td = task_dir
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
    """Return True if /usr/bin/bwrap is installed and can create a user/mount namespace sandbox directly."""
    bwrap_bin = "/usr/bin/bwrap"
    if not os.path.exists(bwrap_bin):
        return False
    try:
        res = subprocess.run(
            [bwrap_bin, "--ro-bind", "/usr", "/usr", "--symlink", "usr/lib", "/lib", "--symlink", "usr/lib64", "/lib64",
             "--symlink", "usr/bin", "/bin", "--proc", "/proc", "--dev", "/dev", "--unshare-all", "true"],
            capture_output=True,
            timeout=5,
            env=build_minimal_env(),
        )
        return res.returncode == 0
    except Exception:
        return False



def messages_to_text(prompt_or_messages):
    """Flatten either a prompt string or a list of chat message dicts into plain text."""
    if isinstance(prompt_or_messages, str):
        return prompt_or_messages
    if isinstance(prompt_or_messages, list):
        parts = []
        for m in prompt_or_messages:
            if isinstance(m, dict):
                role = m.get("role", "")
                content = m.get("content") or ""
                parts.append(f"{role}: {content}")
            else:
                parts.append(str(m))
        return "\n\n".join(parts)
    return str(prompt_or_messages or "")


def estimate_tokens_heuristic(prompt_or_messages):
    """Conservative offline token estimator calibrated against Qwen3.6 on item6_pr15 (3.191 chars/tok)."""
    text = messages_to_text(prompt_or_messages)
    n_msgs = len(prompt_or_messages) if isinstance(prompt_or_messages, list) else 1
    return math.ceil(len(text) / 3.0) + (16 * n_msgs) + 64


def server_tokenize(api=None):
    """Return a token_counter(prompt_or_messages) using llama-server POST /tokenize with heuristic fallback."""
    api = api or API_URL

    def count_tokens(prompt_or_messages):
        text = messages_to_text(prompt_or_messages)
        n_msgs = len(prompt_or_messages) if isinstance(prompt_or_messages, list) else 1
        body = {"content": text, "add_special": True}
        req = urllib.request.Request(
            f"{api}/tokenize",
            json.dumps(body).encode("utf-8"),
            {"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                resp = json.load(r)
            tokens = resp.get("tokens")
            if isinstance(tokens, list):
                return len(tokens) + (16 * n_msgs) + 64
        except Exception:
            pass
        return estimate_tokens_heuristic(prompt_or_messages)

    return count_tokens


def count_prompt_tokens(prompt_or_messages, token_counter=None):
    """Measure prompt tokens via token_counter if provided, else conservative heuristic."""
    if token_counter is not None:
        return int(token_counter(prompt_or_messages))
    return estimate_tokens_heuristic(prompt_or_messages)


def check_context_preflight(
    prompt_or_messages,
    slot_ctx=SLOT_CTX_DEFAULT,
    reserved_output=RESERVED_OUTPUT_TOKENS,
    token_counter=None,
):
    """Preflight check ensuring prompt fits within slot_ctx minus reserved output budget.

    Returns (fits: bool, prompt_tokens: int, max_prompt_tokens: int).
    """
    max_prompt_tokens = max(0, int(slot_ctx) - int(reserved_output))
    prompt_tokens = count_prompt_tokens(prompt_or_messages, token_counter=token_counter)
    return (prompt_tokens <= max_prompt_tokens), prompt_tokens, max_prompt_tokens


class PromptLeakError(AssertionError):
    """Raised by check_prompt_leak when hidden content, a per-run sentinel, or literal 104729 enters a prompt."""

    def __init__(self, message, branch="unknown", leaked_prompt=None):
        super().__init__(message)
        self.branch = branch
        self.leaked_prompt = leaked_prompt


def generate_run_sentinel():
    """Generate a random per-run sentinel token that cannot collide with repository text."""
    return f"PILOT-RUN-SENTINEL-{secrets.token_hex(16)}"


def default_run_dir(label):
    """Return the default uncommitted run instrumentation directory under /tmp/lab-seats/<label>/."""
    safe_label = re.sub(r"[^A-Za-z0-9._-]", "_", str(label or "item6-pilot-v2"))
    return os.path.join("/tmp/lab-seats", safe_label)


def _summarize_tool_args(tool_name, args):
    """Return a compact dict of tool arguments (path/pattern and payload sizes) for per-turn logging."""
    if not isinstance(args, dict):
        return {}
    summary = {}
    for key in (
        "path",
        "pattern",
        "glob",
        "glob_pattern",
        "start",
        "end",
        "max_matches",
        "max_entries",
        "overwrite",
        "executable",
    ):
        if key in args and args[key] is not None:
            summary[key] = args[key]
    if "old" in args and isinstance(args["old"], str):
        summary["old_chars"] = len(args["old"])
    if "new" in args and isinstance(args["new"], str):
        summary["new_chars"] = len(args["new"])
    if "content" in args and isinstance(args["content"], str):
        summary["content_chars"] = len(args["content"])
    if "summary" in args and isinstance(args["summary"], str):
        summary["summary_chars"] = len(args["summary"])
    return summary


def _safe_uncommitted_run_dir(run_dir, label=None, repo_root=None):
    """Resolve run_dir and guarantee instrumentation/leak histories never write inside the git repo."""
    if not run_dir:
        return None
    if repo_root is None:
        repo_root = os.path.abspath(os.path.join(HERE, "..", ".."))
    real_run = os.path.realpath(run_dir)
    real_repo = os.path.realpath(repo_root)
    if real_run == real_repo or real_run.startswith(real_repo + os.sep):
        return default_run_dir(label or "item6-pilot-v2")
    return run_dir


def _append_turn_log(run_dir, record, label=None, repo_root=None):
    """Append one per-turn instrumentation JSON line into run_dir/turn_events.jsonl (never inside repo)."""
    target_dir = _safe_uncommitted_run_dir(run_dir, label=label, repo_root=repo_root)
    if not target_dir:
        return None
    os.makedirs(target_dir, exist_ok=True)
    log_path = os.path.join(target_dir, "turn_events.jsonl")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
    return log_path


def _save_leak_history(run_dir, task_id, turn, leak_branch, messages, label=None, repo_root=None):
    """Persist the leaked message history under run_dir (mode 0o600, never inside repo, never committed)."""
    target_dir = _safe_uncommitted_run_dir(run_dir, label=label, repo_root=repo_root)
    if not target_dir:
        return None
    os.makedirs(target_dir, exist_ok=True)
    hist_path = os.path.join(target_dir, f"leak_history_{task_id}_turn{turn}.json")
    payload = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "task_id": task_id,
        "turn": turn,
        "leak_branch": leak_branch,
        "messages": messages,
    }
    fd = os.open(hist_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return hist_path


def check_prompt_leak(prompt, task, run_sentinel=None):
    """Tripwire: assert no hidden fields, per-run sentinel, or unredacted grading seed 104729 appear in a prompt or message list.

    For `hidden_diff` and `merged_commit`, matches strictly against the whole hidden string value
    (never individual context lines or hunks), so reading base-commit target files touched by the
    reference diff cannot misfire. Error messages name only the branch, never the hidden value.
    """
    text = messages_to_text(prompt)
    for hidden_key in ("hidden_diff", "merged_commit"):
        if dict.__contains__(task, hidden_key):
            val = dict.__getitem__(task, hidden_key)
            # Match whole hidden value only (never split into context lines/hunks)
            if val and isinstance(val, str) and len(val) >= 7 and val in text:
                raise PromptLeakError(
                    f"LEAK TRIPWIRE TRIGGERED: '{hidden_key}' content leaked into prompt!",
                    branch=hidden_key,
                    leaked_prompt=prompt,
                )
    sentinels = []
    if run_sentinel and isinstance(run_sentinel, str):
        sentinels.append(run_sentinel)
    if dict.__contains__(task, "hidden_sentinel"):
        hs = dict.__getitem__(task, "hidden_sentinel")
        if hs and isinstance(hs, str) and hs not in sentinels:
            sentinels.append(hs)
    for sentinel in sentinels:
        if sentinel in text:
            raise PromptLeakError(
                "LEAK TRIPWIRE TRIGGERED: per-run sentinel string leaked into prompt!",
                branch="run_sentinel",
                leaked_prompt=prompt,
            )
    if "104729" in text:
        raise PromptLeakError(
            "LEAK TRIPWIRE TRIGGERED: literal grading seed 104729 leaked into prompt!",
            branch="grading_seed_104729",
            leaked_prompt=prompt,
        )


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


def format_turn_prompt(task, last_code=None, test_error=None, worktree_dir=None, run_sentinel=None):
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
        check_prompt_leak(prompt, task, run_sentinel=run_sentinel)
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
    check_prompt_leak(prompt, task, run_sentinel=run_sentinel)
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


def resolve_confined_dir(worktree_dir, rel_path="."):
    """Resolve a directory (or file) path confined inside worktree_dir, allowing '.' for the root."""
    root_real = os.path.realpath(worktree_dir)
    if rel_path is None:
        return root_real
    if not isinstance(rel_path, str):
        raise ValueError("Non-string path")
    norm = rel_path.replace("\\", "/").strip()
    if norm in ("", ".", "./"):
        return root_real
    return resolve_confined_path(worktree_dir, rel_path)


def tool_list_files(worktree_dir, path=".", glob_pattern=None, max_entries=LIST_FILES_MAX_ENTRIES):
    """List regular non-symlink files under a confined path inside worktree_dir, skipping .git."""
    try:
        target = resolve_confined_dir(worktree_dir, path)
    except ValueError as e:
        return False, f"list_files error: {e}"
    root_real = os.path.realpath(worktree_dir)
    if not os.path.exists(target):
        return False, f"list_files error: path not found: {path}"
    if os.path.isfile(target):
        rel = os.path.relpath(target, root_real).replace(os.sep, "/")
        return True, rel

    entries = []
    truncated = False
    for dirpath, dirnames, filenames in os.walk(target, followlinks=False):
        dirnames[:] = sorted(
            d for d in dirnames
            if d != ".git" and not os.path.islink(os.path.join(dirpath, d))
        )
        for fn in sorted(filenames):
            full = os.path.join(dirpath, fn)
            if os.path.islink(full):
                continue
            rel = os.path.relpath(full, root_real).replace(os.sep, "/")
            if glob_pattern and not (
                fnmatch.fnmatch(rel, glob_pattern) or fnmatch.fnmatch(fn, glob_pattern)
            ):
                continue
            entries.append(rel)
            if len(entries) >= max_entries:
                truncated = True
                break
        if truncated:
            break
    if not entries:
        return True, "(no matching files)"
    out = "\n".join(entries)
    if truncated:
        out += f"\n... [truncated at {max_entries} entries]"
    return True, out


def tool_grep(worktree_dir, pattern, path=".", max_matches=GREP_MAX_MATCHES):
    """Search confined text files under path using a regex pattern, redacting grading seed 104729."""
    if not pattern or not isinstance(pattern, str):
        return False, "grep error: 'pattern' must be a non-empty string."
    try:
        regex = re.compile(pattern)
    except re.error as e:
        return False, f"grep error: invalid regex {pattern!r}: {e}"
    try:
        target = resolve_confined_dir(worktree_dir, path)
    except ValueError as e:
        return False, f"grep error: {e}"
    if not os.path.exists(target):
        return False, f"grep error: path not found: {path}"

    root_real = os.path.realpath(worktree_dir)
    files_to_scan = []
    if os.path.isfile(target) and not os.path.islink(target):
        files_to_scan.append(target)
    else:
        for dirpath, dirnames, filenames in os.walk(target, followlinks=False):
            dirnames[:] = sorted(
                d for d in dirnames
                if d != ".git" and not os.path.islink(os.path.join(dirpath, d))
            )
            for fn in sorted(filenames):
                full = os.path.join(dirpath, fn)
                if not os.path.islink(full):
                    files_to_scan.append(full)

    matches = []
    truncated = False
    for full in files_to_scan:
        try:
            with open(full, "rb") as bf:
                raw = bf.read(262144)
            if b"\x00" in raw:
                continue
            text = redact_grading_seed(raw.decode("utf-8", errors="replace"))
        except OSError:
            continue
        rel = os.path.relpath(full, root_real).replace(os.sep, "/")
        for idx, line in enumerate(text.splitlines(), start=1):
            if regex.search(line):
                snippet = line if len(line) <= 200 else (line[:200] + "...")
                matches.append(f"{rel}:{idx}: {snippet}")
                if len(matches) >= max_matches:
                    truncated = True
                    break
        if truncated:
            break

    if not matches:
        return True, f"(no matches for {pattern!r})"
    out = "\n".join(matches)
    if truncated:
        out += f"\n... [truncated at {max_matches} matches]"
    return True, out


def tool_read_file(worktree_dir, path, start=1, end=None, max_lines=READ_FILE_MAX_LINES):
    """Read a confined file's 1-indexed line window (capped at max_lines), redacting grading seed 104729."""
    try:
        full_path = resolve_confined_path(worktree_dir, path)
    except ValueError as e:
        return False, f"read_file error: {e}"
    if not os.path.exists(full_path):
        return False, f"read_file error: file does not exist: {path}"
    if not os.path.isfile(full_path) or os.path.islink(full_path):
        return False, f"read_file error: not a regular file: {path}"

    try:
        start_i = int(start) if start is not None else 1
        end_i = int(end) if end is not None else None
    except (TypeError, ValueError):
        return False, "read_file error: 'start' and 'end' must be integers."
    if start_i < 1:
        return False, f"read_file error: 'start' must be >= 1 (got {start_i})."
    if end_i is not None and end_i < start_i:
        return False, f"read_file error: 'end' ({end_i}) must be >= 'start' ({start_i})."

    try:
        with open(full_path, "r", encoding="utf-8", errors="replace") as f:
            raw_text = redact_grading_seed(f.read())
    except OSError as e:
        return False, f"read_file error ({path}): {e}"

    lines = raw_text.splitlines()
    total = len(lines)
    if total == 0:
        return True, f"File: {path} (empty, 0 lines)"
    if start_i > total:
        return False, f"read_file error ({path}): start line {start_i} exceeds file length ({total} lines)."

    eff_end = min(total, end_i) if end_i is not None else total
    capped = False
    if eff_end - start_i + 1 > max_lines:
        eff_end = start_i + max_lines - 1
        capped = True

    numbered = [f"{i:4d}: {lines[i - 1]}" for i in range(start_i, eff_end + 1)]
    header = f"File: {path} (lines {start_i}-{eff_end} of {total})"
    body = "\n".join(numbered)
    if capped and eff_end < total:
        body += f"\n... [truncated at {max_lines} lines; call read_file(path={path!r}, start={eff_end + 1}) to continue]"
    return True, f"{header}\n{body}"


def _norm_rel_path(rel_path):
    """Normalize a relative worktree path to forward slashes for set/dict keys."""
    return os.path.normpath((rel_path or "").replace("\\", "/").strip()).replace(os.sep, "/")


def _other_workspace_lines(worktree_dir, exclude_rel_path, touched_paths=None):
    """Collect stripped non-empty lines from other created or edited files in worktree_dir."""
    root_real = os.path.realpath(worktree_dir)
    excl_norm = _norm_rel_path(exclude_rel_path)
    rel_paths = set()

    if touched_paths is not None:
        for rp in touched_paths:
            rel_paths.add(_norm_rel_path(rp))
    else:
        git_dir = os.path.join(root_real, ".git")
        if os.path.isdir(git_dir):
            res = subprocess.run(
                ["git", "status", "--porcelain", "-uall"],
                cwd=root_real,
                env=build_minimal_env(),
                capture_output=True,
                text=True,
            )
            if res.returncode == 0:
                for line in res.stdout.splitlines():
                    if len(line) >= 4:
                        p = line[3:].strip()
                        if " -> " in p:
                            p = p.split(" -> ", 1)[1]
                        rel_paths.add(_norm_rel_path(p))
        else:
            for dirpath, dirnames, filenames in os.walk(root_real, followlinks=False):
                dirnames[:] = [
                    d for d in dirnames
                    if d != ".git" and not os.path.islink(os.path.join(dirpath, d))
                ]
                for fn in filenames:
                    full = os.path.join(dirpath, fn)
                    if not os.path.islink(full):
                        rel_paths.add(_norm_rel_path(os.path.relpath(full, root_real)))

    lines = set()
    for rp in rel_paths:
        if rp == excl_norm:
            continue
        try:
            full = resolve_confined_path(root_real, rp)
        except ValueError:
            continue
        if os.path.isfile(full) and not os.path.islink(full):
            try:
                with open(full, "r", encoding="utf-8", errors="replace") as f:
                    for ln in f:
                        s = ln.strip()
                        if s:
                            lines.add(s)
            except OSError:
                continue
    return lines


def check_stub_truncation(worktree_dir, rel_path, orig_content, new_content, touched_paths=None):
    """Reject large unrelocated removals (stub/truncation pattern) while allowing genuine file splits/moves.

    Triggers only when an existing file loses >= STUB_GUARD_MIN_REMOVED_LINES (40) net lines AND
    >= STUB_GUARD_MIN_REMOVED_RATIO (50%) of its lines, AND fewer than STUB_GUARD_MOVE_MATCH_MIN_RATIO
    (50%) of the removed substantive lines reappear in other files created or edited in the same task.
    Returns (ok: bool, error_message: str).
    """
    orig_lines = orig_content.splitlines()
    new_lines = new_content.splitlines()
    total_orig = len(orig_lines)
    if total_orig == 0:
        return True, ""
    net_removed = total_orig - len(new_lines)
    if net_removed < STUB_GUARD_MIN_REMOVED_LINES:
        return True, ""
    removed_ratio = net_removed / total_orig
    if removed_ratio < STUB_GUARD_MIN_REMOVED_RATIO:
        return True, ""

    new_set = {ln.strip() for ln in new_lines if ln.strip()}
    removed_sig = [ln.strip() for ln in orig_lines if ln.strip() and ln.strip() not in new_set]
    if len(removed_sig) < STUB_GUARD_MIN_REMOVED_LINES:
        return True, ""

    other_lines = _other_workspace_lines(worktree_dir, rel_path, touched_paths=touched_paths)
    relocated = sum(1 for ln in removed_sig if ln in other_lines)
    reloc_ratio = relocated / len(removed_sig)
    if reloc_ratio < STUB_GUARD_MOVE_MATCH_MIN_RATIO:
        pct = int(round(removed_ratio * 100))
        return (
            False,
            f"stub/truncation guard rejected ({rel_path}): removing {net_removed}/{total_orig} lines ({pct}%) "
            f"without relocating the removed content to other files in this task "
            f"({relocated}/{len(removed_sig)} removed lines found in other created/edited files). "
            f"If you are splitting or moving content out of {rel_path}, create or update the destination "
            f"files first before removing the moved sections from {rel_path}.",
        )
    return True, ""


def tool_search_replace(worktree_dir, path, old, new, base_content=None, touched_paths=None):
    """Apply an exact, unique search-and-replace edit to an existing confined file with rewrite & stub guards."""
    try:
        full_path = resolve_confined_path(worktree_dir, path)
    except ValueError as e:
        return False, f"search_replace error: {e}"
    if not os.path.exists(full_path):
        return False, f"search_replace error ({path}): file does not exist. Use create_file for new files."
    if not os.path.isfile(full_path) or os.path.islink(full_path):
        return False, f"search_replace error ({path}): not a regular file."
    if not isinstance(old, str) or old == "":
        return False, f"search_replace error ({path}): 'old' must be a non-empty string."
    if not isinstance(new, str):
        return False, f"search_replace error ({path}): 'new' must be a string."
    if old == new:
        return False, f"search_replace error ({path}): 'old' and 'new' are identical (no-op edit)."

    try:
        with open(full_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except OSError as e:
        return False, f"search_replace error ({path}): {e}"

    occurrences = content.count(old)
    if occurrences == 0:
        return (
            False,
            f"search_replace error ({path}): 'old' text not found (0 matches). "
            "Use read_file to inspect exact lines and whitespace before retrying.",
        )
    if occurrences > 1:
        return (
            False,
            f"search_replace error ({path}): 'old' text is ambiguous ({occurrences} matches; must match uniquely). "
            "Include more surrounding context lines to make the match unique.",
        )

    total_lines = len(content.splitlines())
    old_lines = len(old.splitlines())
    new_lines = len(new.splitlines())
    if (
        total_lines >= SEARCH_REPLACE_REWRITE_MIN_LINES
        and (old_lines / max(total_lines, 1)) >= SEARCH_REPLACE_REWRITE_MAX_RATIO
        and new_lines >= SEARCH_REPLACE_REWRITE_MIN_LINES
    ):
        return (
            False,
            f"search_replace rejected ({path}): whole-file rewrite cap exceeded "
            f"({old_lines}/{total_lines} lines replaced with {new_lines} lines). "
            "Make smaller, targeted edits instead of rewriting the whole file.",
        )

    updated = content.replace(old, new, 1)

    ref_orig = base_content if base_content is not None else content
    stub_ok, stub_err = check_stub_truncation(
        worktree_dir, path, ref_orig, updated, touched_paths=touched_paths
    )
    if not stub_ok:
        return False, stub_err

    try:
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(updated)
    except OSError as e:
        return False, f"search_replace error ({path}): failed writing file: {e}"

    return True, f"search_replace OK ({path}): replaced {old_lines} lines with {new_lines} lines."


def tool_create_file(
    worktree_dir,
    path,
    content,
    overwrite=False,
    justification="",
    executable=False,
    overwrites_used=0,
    max_overwrites=MAX_EXISTING_FILE_OVERWRITES,
    base_content=None,
    touched_paths=None,
):
    """Create a new confined file; reject overwriting existing files unless explicitly justified, within cap, and non-stub.

    Returns (ok: bool, message: str, overwrote_existing: bool).
    """
    try:
        full_path = resolve_confined_path(worktree_dir, path)
    except ValueError as e:
        return False, f"create_file error: {e}", False
    if not isinstance(content, str):
        return False, f"create_file error ({path}): 'content' must be a string.", False

    existed = os.path.exists(full_path)
    if existed:
        if os.path.isdir(full_path):
            return False, f"create_file error ({path}): path is a directory.", False
        if not overwrite:
            return (
                False,
                f"create_file rejected ({path}): file already exists. Use search_replace for targeted edits "
                f"to existing files, or pass overwrite=true with a clear justification if a full rewrite is "
                f"strictly required (cap: {max_overwrites} existing-file overwrite per task).",
                False,
            )
        if not isinstance(justification, str) or len(justification.strip()) < MIN_OVERWRITE_JUSTIFICATION_LEN:
            return (
                False,
                f"create_file rejected ({path}): overwrite=true requires a justification of at least "
                f"{MIN_OVERWRITE_JUSTIFICATION_LEN} characters explaining why search_replace is insufficient.",
                False,
            )
        if overwrites_used >= max_overwrites:
            return (
                False,
                f"create_file rejected ({path}): whole-file overwrite cap reached "
                f"({overwrites_used}/{max_overwrites} used in this task). Use search_replace for targeted edits.",
                False,
            )
        if base_content is not None:
            ref_orig = base_content
        else:
            try:
                with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                    ref_orig = f.read()
            except OSError:
                ref_orig = ""
        stub_ok, stub_err = check_stub_truncation(
            worktree_dir, path, ref_orig, content, touched_paths=touched_paths
        )
        if not stub_ok:
            return False, stub_err, False

    try:
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
        if executable:
            os.chmod(full_path, 0o755)
    except OSError as e:
        return False, f"create_file error ({path}): {e}", False

    suffix = " (overwrote existing)" if existed else ""
    if executable:
        suffix += " (chmod +x)"
    return True, f"create_file OK ({path}): wrote {len(content.splitlines())} lines{suffix}.", existed


class ToolSession:
    """Stateful tool executor for a single task inside a confined scratch worktree."""

    def __init__(self, worktree_dir, max_overwrites=MAX_EXISTING_FILE_OVERWRITES):
        self.worktree_dir = worktree_dir
        self.max_overwrites = max_overwrites
        self.overwrites_used = 0
        self.edits_applied = 0
        self.touched_paths = set()
        self.base_contents = {}

    def _snapshot_base_if_existing(self, rel_path):
        """Record original content of an existing confined file before its first edit in this task."""
        norm = _norm_rel_path(rel_path)
        if norm in self.base_contents:
            return self.base_contents[norm]
        try:
            full = resolve_confined_path(self.worktree_dir, rel_path)
        except ValueError:
            return None
        if os.path.isfile(full) and not os.path.islink(full):
            try:
                with open(full, "r", encoding="utf-8", errors="replace") as f:
                    data = f.read()
                self.base_contents[norm] = data
                return data
            except OSError:
                return None
        return None

    def check_no_unrelocated_truncations(self):
        """Verify at finish time that no edited existing file was left truncated without relocated content."""
        for norm, base_text in sorted(self.base_contents.items()):
            try:
                full = resolve_confined_path(self.worktree_dir, norm)
            except ValueError:
                continue
            if not os.path.isfile(full) or os.path.islink(full):
                continue
            try:
                with open(full, "r", encoding="utf-8", errors="replace") as f:
                    curr_text = f.read()
            except OSError:
                continue
            ok, err = check_stub_truncation(
                self.worktree_dir, norm, base_text, curr_text, touched_paths=self.touched_paths
            )
            if not ok:
                return False, err
        return True, ""

    def execute(self, call):
        """Execute one normalized tool call dict {'tool': str, 'args': dict}.

        Returns (ok: bool, output: str, is_edit: bool).
        """
        if not isinstance(call, dict):
            return False, "Tool call must be a JSON object with 'tool' and 'args'.", False
        name = call.get("tool")
        args = call.get("args")
        if not isinstance(name, str) or not name.strip():
            return False, "Tool call missing 'tool' name.", False
        if args is None:
            args = {}
        if not isinstance(args, dict):
            return False, f"Tool '{name}' 'args' must be a JSON object.", False
        name = name.strip()

        if name == "list_files":
            raw_me = args.get("max_entries")
            try:
                max_entries = LIST_FILES_MAX_ENTRIES if raw_me is None else max(1, min(int(raw_me), LIST_FILES_MAX_ENTRIES))
            except (TypeError, ValueError):
                return False, "list_files error: 'max_entries' must be an integer.", False
            ok, out = tool_list_files(
                self.worktree_dir,
                path=args.get("path", "."),
                glob_pattern=args.get("glob") or args.get("glob_pattern"),
                max_entries=max_entries,
            )
            return ok, out, False

        if name == "grep":
            raw_mm = args.get("max_matches")
            try:
                max_matches = GREP_MAX_MATCHES if raw_mm is None else max(1, min(int(raw_mm), GREP_MAX_MATCHES))
            except (TypeError, ValueError):
                return False, "grep error: 'max_matches' must be an integer.", False
            ok, out = tool_grep(
                self.worktree_dir,
                pattern=args.get("pattern", ""),
                path=args.get("path", "."),
                max_matches=max_matches,
            )
            return ok, out, False

        if name == "read_file":
            ok, out = tool_read_file(
                self.worktree_dir,
                path=args.get("path", ""),
                start=args.get("start", 1),
                end=args.get("end"),
            )
            return ok, out, False

        if name == "search_replace":
            rel_p = args.get("path", "")
            base_c = self._snapshot_base_if_existing(rel_p)
            ok, out = tool_search_replace(
                self.worktree_dir,
                path=rel_p,
                old=args.get("old"),
                new=args.get("new"),
                base_content=base_c,
                touched_paths=self.touched_paths,
            )
            if ok:
                self.edits_applied += 1
                self.touched_paths.add(_norm_rel_path(rel_p))
            return ok, out, ok

        if name == "create_file":
            rel_p = args.get("path", "")
            base_c = self._snapshot_base_if_existing(rel_p)
            ok, out, overwrote = tool_create_file(
                self.worktree_dir,
                path=rel_p,
                content=args.get("content"),
                overwrite=bool(args.get("overwrite", False)),
                justification=args.get("justification") or args.get("reason") or "",
                executable=bool(args.get("executable", False)),
                overwrites_used=self.overwrites_used,
                max_overwrites=self.max_overwrites,
                base_content=base_c,
                touched_paths=self.touched_paths,
            )
            if ok:
                self.edits_applied += 1
                self.touched_paths.add(_norm_rel_path(rel_p))
                if overwrote:
                    self.overwrites_used += 1
            return ok, out, ok

        return False, f"Unknown tool: {name!r}. Valid tools: list_files, grep, read_file, search_replace, create_file, run_tests, finish.", False


def _normalize_tool_call_obj(obj):
    """Normalize a single parsed JSON dict into {'tool': name, 'args': dict}."""
    if not isinstance(obj, dict):
        return None
    if "function" in obj and isinstance(obj["function"], dict):
        fn = obj["function"]
        name = fn.get("name")
        raw_args = fn.get("arguments", {})
    else:
        name = obj.get("tool") or obj.get("name")
        if "args" in obj:
            raw_args = obj["args"]
        elif "arguments" in obj:
            raw_args = obj["arguments"]
        else:
            raw_args = {k: v for k, v in obj.items() if k not in ("tool", "name")}
    if not isinstance(name, str) or not name.strip():
        return None
    if isinstance(raw_args, str):
        try:
            raw_args = json.loads(raw_args)
        except json.JSONDecodeError:
            return None
    if raw_args is None:
        raw_args = {}
    if not isinstance(raw_args, dict):
        return None
    return {"tool": name.strip(), "args": raw_args}


def extract_tool_calls(response_text, raw_tool_calls=None):
    """Extract structured tool calls from OpenAI tool_calls or fenced ```json / ```tool blocks.

    Returns (calls: list[dict], parse_errors: list[str]).
    """
    calls = []
    parse_errors = []

    if raw_tool_calls and isinstance(raw_tool_calls, list):
        for tc in raw_tool_calls:
            norm = _normalize_tool_call_obj(tc)
            if norm is not None:
                calls.append(norm)
            else:
                parse_errors.append(f"Invalid structured tool_call object: {tc!r}")
        if calls:
            return calls, parse_errors

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
            norm = _normalize_tool_call_obj(item)
            if norm is not None:
                calls.append(norm)
            else:
                parse_errors.append(f"JSON object is not a valid tool call (missing 'tool' name): {str(item)[:160]}")

    return calls, parse_errors


def build_target_file_manifest(task, worktree_dir):
    """Build a compact manifest of target files (paths + line counts) without dumping full file contents."""
    clean_task = tasks_item6.strip_hidden(task)
    lines = []
    for rel_path in clean_task.get("files", []):
        if worktree_dir:
            try:
                full_path = resolve_confined_path(worktree_dir, rel_path)
            except ValueError:
                continue
            if os.path.exists(full_path) and os.path.isfile(full_path) and not os.path.islink(full_path):
                try:
                    with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                        n_lines = len(f.read().splitlines())
                    lines.append(f"- `{rel_path}` (existing, {n_lines} lines)")
                except OSError:
                    lines.append(f"- `{rel_path}` (existing)")
            else:
                lines.append(f"- `{rel_path}` (new file)")
        else:
            lines.append(f"- `{rel_path}`")
    return "\n".join(lines)


def format_tool_messages(task, worktree_dir=None, run_sentinel=None):
    """Build initial [system, user] messages for the v2 structured-edit tool loop.

    Never includes reference diffs, merged commits, or full target-file dumps.
    """
    clean_task = tasks_item6.strip_hidden(task)
    has_tests = bool(clean_task.get("has_tests"))
    test_tool_doc = (
        '- `{"tool": "run_tests", "args": {}}`: run the task\'s verification command in the sandbox.\n'
        if has_tests
        else ""
    )
    system_msg = (
        "You are a software engineer editing a clean git scratch repository at its base commit.\n"
        "You MUST make changes using structured tool calls inside a ```json code block.\n"
        "You may emit a single JSON object or a JSON array of tool calls per turn.\n\n"
        "Available tools:\n"
        '- `{"tool": "list_files", "args": {"path": ".", "glob": "*.py"}}`: list files under path (glob optional).\n'
        '- `{"tool": "grep", "args": {"pattern": "regex", "path": "."}}`: search text files (path optional).\n'
        '- `{"tool": "read_file", "args": {"path": "rel/path", "start": 1, "end": 200}}`: read numbered lines (max 250 lines/call).\n'
        '- `{"tool": "search_replace", "args": {"path": "rel/path", "old": "exact unique text", "new": "replacement"}}`: '
        "targeted edit on an existing file (`old` must match uniquely; whole-file rewrites of large files and "
        "large unrelocated truncations >= 40 lines and >= 50% of a file are rejected — create destination files first when splitting/moving content).\n"
        '- `{"tool": "create_file", "args": {"path": "rel/path", "content": "...", "executable": false}}`: '
        "create a new file (refuses existing files unless `overwrite: true` and `justification` >= 15 chars, capped at 1 per task).\n"
        f"{test_tool_doc}"
        '- `{"tool": "finish", "args": {"summary": "brief summary"}}`: finish and verify your edits.\n\n'
        "Rules:\n"
        "- Always read files with `read_file` or `grep` before editing them.\n"
        "- Make targeted edits with `search_replace`; never emit raw unified diffs.\n"
        "- The harness applies your edits and generates the git diff automatically.\n"
        "- Standard library or repository dependencies only; no unrequested subagents; no GPU work."
    )

    manifest = build_target_file_manifest(clean_task, worktree_dir)
    test_note = (
        f"\n\nVerification command (`run_tests`): `{clean_task['test_cmd']}`"
        if has_tests and clean_task.get("test_cmd")
        else "\n\nThis task has no automated test command; call `finish` once all edits are applied."
    )
    user_msg = (
        f"{clean_task['prompt']}\n\n"
        f"Expected target files:\n{manifest}{test_note}\n\n"
        "Start by reading the relevant files using `read_file` / `grep`, then apply targeted edits "
        "with `search_replace` / `create_file`, and call `finish` when done."
    )
    messages = [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": user_msg},
    ]
    check_prompt_leak(messages, task, run_sentinel=run_sentinel)
    return messages


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
    """Run test command for the task in worktree_dir inside the outer bwrap sandbox.

    Returns (passed: bool, output_str: str).
    Should only be called when task['has_tests'] is True. Fails closed if bwrap cannot start.
    """
    clean_task = tasks_item6.strip_hidden(task)
    if not clean_task.get("has_tests"):
        raise AssertionError("run_tests must not be executed when has_tests is False")
    cmd = clean_task.get("test_cmd")
    if not cmd:
        return True, "No test command defined for task."
    if not has_bwrap():
        raise RuntimeError("bwrap sandbox is unavailable; refusing to execute run_tests unsandboxed")

    iso_cmd = _wrap_shell_with_isolated_python3(cmd, "/work")
    home_dir, tmp_dir, shim_dir = prepare_isolated_home_and_tmp(worktree_dir)
    env = build_minimal_env(home_dir="/home/pilot", tmp_dir="/tmp")
    bwrap_argv = build_outer_bwrap_cmd(worktree_dir, home_dir, tmp_dir, shim_dir, ["bash", "-c", iso_cmd], env)
    try:
        res = subprocess.run(
            bwrap_argv,
            stdin=subprocess.DEVNULL,
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


def _is_context_overflow_error(err_text: str) -> bool:
    """Detect if an HTTP error message indicates model context overflow."""
    low = err_text.lower()
    return "context" in low and any(w in low for w in ("size", "overflow", "exceed", "window", "limit", "length"))


def _truncate_tool_output(text, max_chars=TOOL_RESULT_MAX_CHARS):
    """Bound individual tool result payloads so context does not blow up unexpectedly."""
    s = redact_grading_seed(text or "")
    if len(s) > max_chars:
        return s[:max_chars] + f"\n... [truncated {len(s) - max_chars} chars] ..."
    return s


def _run_task_loop_turns(
    task,
    clean_task,
    has_tests,
    messages,
    ask_fn,
    worktree_dir,
    max_turns,
    task_budget,
    slot_ctx,
    reserved_output_tokens,
    token_counter,
    task_wall_budget,
    clock_fn,
    run_sentinel,
    run_dir,
    label,
    repo_root,
    history,
    loop_state,
):
    """Run the turn loop body while updating `history` and `loop_state` in place for fault isolation."""
    tool_session = ToolSession(worktree_dir)
    seen_code_hashes = set()
    last_test_err = None
    last_turn_err = None
    dirty_since_last_test = False
    accumulated_completion_tokens = 0
    stop_reason = "max_turns"
    final_passed = False
    leak_branch = None
    loop_start = clock_fn()
    final_turn_note = "\n\nNote: This is your final turn. Apply any remaining edits and call `finish`."

    def _wall_elapsed():
        return clock_fn() - loop_start

    def _wall_exceeded():
        return task_wall_budget is not None and task_wall_budget > 0 and _wall_elapsed() >= task_wall_budget

    for turn in range(max_turns):
        t0 = time.time()
        loop_state["turn"] = turn
        loop_state["t0"] = t0
        seed = 6000 + clean_task["pr_number"] * 100 + turn

        # Per-task wall budget check before sending request
        if _wall_exceeded():
            elapsed_w = _wall_elapsed()
            stop_reason = "task_wall_budget"
            history.append({
                "turn": turn,
                "seed": seed,
                "passed": False,
                "err": f"task wall budget exceeded ({elapsed_w:.1f}s >= {task_wall_budget}s)",
                "stop": stop_reason,
                "gen_s": 0.0,
                "tokens": 0,
                "prompt_tokens": 0,
            })
            break

        # Attach final-turn notice directly to the active user prompt ONLY on the actual final turn (turn == max_turns - 1)
        if max_turns > 1 and turn == max_turns - 1 and messages and messages[-1].get("role") == "user":
            if final_turn_note.strip() not in (messages[-1].get("content") or ""):
                messages[-1] = {
                    "role": "user",
                    "content": (messages[-1].get("content") or "") + final_turn_note,
                }

        try:
            check_prompt_leak(messages, task, run_sentinel=run_sentinel)
        except PromptLeakError as exc:
            leak_branch = exc.branch
            if run_dir:
                hist_file = _save_leak_history(
                    run_dir, clean_task["id"], turn, leak_branch, messages, label=label, repo_root=repo_root
                )
                _append_turn_log(
                    run_dir,
                    {
                        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        "task_id": clean_task["id"],
                        "turn": turn,
                        "event": "prompt_leak",
                        "leak_branch": leak_branch,
                        "message": str(exc),
                        "history_file": hist_file,
                    },
                    label=label,
                    repo_root=repo_root,
                )
            stop_reason = "prompt_leak"
            history.append({
                "turn": turn,
                "seed": seed,
                "passed": False,
                "err": str(exc),
                "stop": stop_reason,
                "leak_branch": leak_branch,
                "gen_s": round(time.time() - t0, 2),
                "tokens": 0,
                "prompt_tokens": 0,
            })
            break

        # Prompt-size preflight before sending request to server
        fits, est_prompt_tokens, max_prompt_tokens = check_context_preflight(
            messages,
            slot_ctx=slot_ctx,
            reserved_output=reserved_output_tokens,
            token_counter=token_counter,
        )
        if not fits:
            err_text = (
                f"prompt preflight overflow: {est_prompt_tokens} tokens exceeds slot budget "
                f"{max_prompt_tokens} (slot_ctx={slot_ctx}, reserved_output={reserved_output_tokens})"
            )
            stop_reason = "context_overflow"
            history.append({
                "turn": turn,
                "seed": seed,
                "passed": False,
                "err": err_text,
                "stop": stop_reason,
                "gen_s": round(time.time() - t0, 2),
                "tokens": 0,
                "prompt_tokens": est_prompt_tokens,
                "preflight_prompt_tokens": est_prompt_tokens,
            })
            break

        try:
            if getattr(ask_fn, "_accepts_timeout", False) and task_wall_budget is not None and task_wall_budget > 0:
                rem_timeout = max(1.0, float(task_wall_budget) - _wall_elapsed())
                reply = ask_fn(messages, seed, timeout=rem_timeout)
            else:
                reply = ask_fn(messages, seed)
        except (TimeoutError, socket.timeout) as e:
            elapsed_w = _wall_elapsed()
            stop_reason = "task_wall_budget"
            history.append({
                "turn": turn,
                "seed": seed,
                "passed": False,
                "err": f"task wall budget timeout ({elapsed_w:.1f}s / {task_wall_budget}s): {e}",
                "stop": stop_reason,
                "gen_s": round(time.time() - t0, 2),
                "tokens": 0,
                "prompt_tokens": est_prompt_tokens,
                "preflight_prompt_tokens": est_prompt_tokens,
            })
            break
        except urllib.error.HTTPError as e:
            err_body = ""
            try:
                err_body = e.read().decode("utf-8", errors="replace")
            except Exception:
                pass
            err_text = f"HTTP Error {e.code}: {e.reason}"
            if err_body:
                err_text = f"{err_text} - {err_body}"
            stop_reason = "context_overflow" if _is_context_overflow_error(err_text) else "request_error"
            history.append({
                "turn": turn,
                "seed": seed,
                "passed": False,
                "err": err_text,
                "stop": stop_reason,
                "gen_s": round(time.time() - t0, 2),
                "tokens": 0,
                "prompt_tokens": est_prompt_tokens,
                "preflight_prompt_tokens": est_prompt_tokens,
            })
            break
        except urllib.error.URLError as e:
            if isinstance(getattr(e, "reason", None), (TimeoutError, socket.timeout)) and _wall_exceeded():
                elapsed_w = _wall_elapsed()
                stop_reason = "task_wall_budget"
                history.append({
                    "turn": turn,
                    "seed": seed,
                    "passed": False,
                    "err": f"task wall budget timeout ({elapsed_w:.1f}s / {task_wall_budget}s): {e.reason}",
                    "stop": stop_reason,
                    "gen_s": round(time.time() - t0, 2),
                    "tokens": 0,
                    "prompt_tokens": est_prompt_tokens,
                    "preflight_prompt_tokens": est_prompt_tokens,
                })
                break
            err_text = f"URL Error: {e.reason}"
            stop_reason = "context_overflow" if _is_context_overflow_error(err_text) else "request_error"
            history.append({
                "turn": turn,
                "seed": seed,
                "passed": False,
                "err": err_text,
                "stop": stop_reason,
                "gen_s": round(time.time() - t0, 2),
                "tokens": 0,
                "prompt_tokens": est_prompt_tokens,
                "preflight_prompt_tokens": est_prompt_tokens,
            })
            break

        gen_s = round(time.time() - t0, 2)
        comp_tokens = reply.get("usage", {}).get("completion_tokens", 0) or 0
        prompt_tokens = reply.get("usage", {}).get("prompt_tokens", 0) or est_prompt_tokens
        accumulated_completion_tokens += comp_tokens
        loop_state["tokens"] = accumulated_completion_tokens

        content = reply.get("content", "") or ""
        raw_tool_calls = reply.get("tool_calls")
        hash_payload = content + (json.dumps(raw_tool_calls, sort_keys=True) if raw_tool_calls else "")
        code_hash = hashlib.sha256(hash_payload.encode("utf-8")).hexdigest()

        # Stop check: repeat code / identical reply
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
                "preflight_prompt_tokens": est_prompt_tokens,
            })
            stop_reason = "repeat_code"
            break
        seen_code_hashes.add(code_hash)

        messages.append({"role": "assistant", "content": content})

        calls, parse_errors = extract_tool_calls(content, raw_tool_calls=raw_tool_calls)
        if not calls:
            err_msg = (
                "; ".join(parse_errors)
                if parse_errors
                else "No valid tool calls found. Respond with a ```json block containing a tool call or list of tool calls."
            )
            if run_dir:
                _append_turn_log(
                    run_dir,
                    {
                        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        "task_id": clean_task["id"],
                        "turn": turn,
                        "event": "turn_parse_error",
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": comp_tokens,
                        "tools": [],
                        "result_chars": len(err_msg),
                    },
                    label=label,
                    repo_root=repo_root,
                )
            if last_turn_err is not None and err_msg.strip() == last_turn_err.strip():
                history.append({
                    "turn": turn,
                    "seed": seed,
                    "passed": False,
                    "err": err_msg,
                    "stop": "repeat_error",
                    "gen_s": gen_s,
                    "tokens": comp_tokens,
                    "prompt_tokens": prompt_tokens,
                    "preflight_prompt_tokens": est_prompt_tokens,
                })
                stop_reason = "repeat_error"
                break
            history.append({
                "turn": turn,
                "seed": seed,
                "passed": False,
                "err": err_msg,
                "tool_calls": [],
                "gen_s": gen_s,
                "tokens": comp_tokens,
                "prompt_tokens": prompt_tokens,
                "preflight_prompt_tokens": est_prompt_tokens,
            })
            last_turn_err = err_msg
            if accumulated_completion_tokens >= task_budget:
                stop_reason = "budget"
                break
            if _wall_exceeded():
                stop_reason = "task_wall_budget"
                history[-1]["stop"] = stop_reason
                break
            if turn < max_turns - 1:
                messages.append({"role": "user", "content": f"Tool error: {err_msg}"})
            continue

        result_lines = []
        if parse_errors:
            result_lines.append("Parse warnings: " + "; ".join(parse_errors))

        call_summaries = []
        turn_tool_events = []
        any_edit_ok = False
        any_tool_ok = False
        turn_errors = []
        requested_finish = False
        ran_tests_this_turn = False
        test_passed_this_turn = False
        test_out_this_turn = ""

        for idx, call in enumerate(calls, start=1):
            tname = call.get("tool", "")
            targs_summary = _summarize_tool_args(tname, call.get("args") or {})
            if tname == "finish":
                requested_finish = True
                call_summaries.append({"tool": "finish", "ok": True})
                turn_tool_events.append({"tool": "finish", "args": targs_summary, "ok": True, "result_chars": 0})
                continue
            if tname == "run_tests":
                if not has_tests:
                    msg = "This task has no automated test command; call finish when your edits are complete."
                    call_summaries.append({"tool": "run_tests", "ok": True})
                    turn_tool_events.append({"tool": "run_tests", "args": targs_summary, "ok": True, "result_chars": len(msg)})
                    result_lines.append(f"[{idx}] run_tests: {msg}")
                    any_tool_ok = True
                    continue
                t_ok, t_out = run_tests(clean_task, worktree_dir)
                t_out_clean = redact_grading_seed((t_out or "").strip())
                if len(t_out_clean) > 2500:
                    t_out_clean = "... [truncated] ...\n" + t_out_clean[-2500:]
                ran_tests_this_turn = True
                test_passed_this_turn = t_ok
                test_out_this_turn = t_out_clean
                dirty_since_last_test = False
                call_summaries.append({"tool": "run_tests", "ok": t_ok})
                turn_tool_events.append({"tool": "run_tests", "args": targs_summary, "ok": t_ok, "result_chars": len(t_out_clean)})
                if t_ok:
                    any_tool_ok = True
                    result_lines.append(f"[{idx}] run_tests PASSED:\n{t_out_clean}")
                else:
                    turn_errors.append(t_out_clean)
                    result_lines.append(f"[{idx}] run_tests FAILED:\n{t_out_clean}")
                continue

            ok, out, is_edit = tool_session.execute(call)
            call_summaries.append({"tool": tname, "ok": ok})
            turn_tool_events.append({"tool": tname, "args": targs_summary, "ok": ok, "result_chars": len(out or "")})
            if ok:
                any_tool_ok = True
                if is_edit:
                    any_edit_ok = True
                    dirty_since_last_test = True
                result_lines.append(f"[{idx}] {tname} OK:\n{_truncate_tool_output(out)}")
            else:
                turn_errors.append(out)
                result_lines.append(f"[{idx}] {tname} ERROR:\n{_truncate_tool_output(out)}")

        if run_dir:
            _append_turn_log(
                run_dir,
                {
                    "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "task_id": clean_task["id"],
                    "turn": turn,
                    "event": "turn_tools",
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": comp_tokens,
                    "tools": turn_tool_events,
                },
                label=label,
                repo_root=repo_root,
            )

        # Handle finish request
        if requested_finish:
            stub_ok, stub_err = tool_session.check_no_unrelocated_truncations()
            curr_diff = capture_worktree_diff(worktree_dir, clean_task["base_commit"])
            if not stub_ok:
                turn_errors.append(stub_err)
                result_lines.append(f"finish ERROR: {stub_err}")
            elif not curr_diff.strip():
                no_diff_err = "Cannot finish: git diff is empty. Apply edits with search_replace or create_file first."
                turn_errors.append(no_diff_err)
                result_lines.append(f"finish ERROR: {no_diff_err}")
            elif not has_tests:
                final_passed = True
                stop_reason = "applied_no_tests"
                history.append({
                    "turn": turn,
                    "seed": seed,
                    "passed": True,
                    "err": "",
                    "tool_calls": call_summaries,
                    "gen_s": gen_s,
                    "tokens": comp_tokens,
                    "prompt_tokens": prompt_tokens,
                    "preflight_prompt_tokens": est_prompt_tokens,
                })
                break
            else:
                if not ran_tests_this_turn or dirty_since_last_test:
                    t_ok, t_out = run_tests(clean_task, worktree_dir)
                    t_out_clean = redact_grading_seed((t_out or "").strip())
                    if len(t_out_clean) > 2500:
                        t_out_clean = "... [truncated] ...\n" + t_out_clean[-2500:]
                    ran_tests_this_turn = True
                    test_passed_this_turn = t_ok
                    test_out_this_turn = t_out_clean
                    dirty_since_last_test = False
                if test_passed_this_turn:
                    final_passed = True
                    stop_reason = "pass"
                    history.append({
                        "turn": turn,
                        "seed": seed,
                        "passed": True,
                        "err": "",
                        "tool_calls": call_summaries,
                        "gen_s": gen_s,
                        "tokens": comp_tokens,
                        "prompt_tokens": prompt_tokens,
                        "preflight_prompt_tokens": est_prompt_tokens,
                    })
                    break
                turn_errors.append(test_out_this_turn)
                result_lines.append(f"finish verification FAILED:\n{test_out_this_turn}")

        # Repeat-error stop check on repeated identical test failure
        if ran_tests_this_turn and not test_passed_this_turn:
            if last_test_err is not None and test_out_this_turn.strip() == last_test_err.strip():
                history.append({
                    "turn": turn,
                    "seed": seed,
                    "passed": False,
                    "err": test_out_this_turn,
                    "stop": "repeat_error",
                    "tool_calls": call_summaries,
                    "gen_s": gen_s,
                    "tokens": comp_tokens,
                    "prompt_tokens": prompt_tokens,
                    "preflight_prompt_tokens": est_prompt_tokens,
                })
                stop_reason = "repeat_error"
                break
            last_test_err = test_out_this_turn

        # Repeat-error stop check when a turn makes no progress and repeats the identical tool error
        joined_err = "\n".join(turn_errors).strip()
        if not any_tool_ok and joined_err:
            if last_turn_err is not None and joined_err == last_turn_err.strip():
                history.append({
                    "turn": turn,
                    "seed": seed,
                    "passed": False,
                    "err": joined_err,
                    "stop": "repeat_error",
                    "tool_calls": call_summaries,
                    "gen_s": gen_s,
                    "tokens": comp_tokens,
                    "prompt_tokens": prompt_tokens,
                    "preflight_prompt_tokens": est_prompt_tokens,
                })
                stop_reason = "repeat_error"
                break
            last_turn_err = joined_err
        else:
            last_turn_err = None

        history.append({
            "turn": turn,
            "seed": seed,
            "passed": bool(ran_tests_this_turn and test_passed_this_turn),
            "err": joined_err,
            "tool_calls": call_summaries,
            "gen_s": gen_s,
            "tokens": comp_tokens,
            "prompt_tokens": prompt_tokens,
            "preflight_prompt_tokens": est_prompt_tokens,
        })

        if accumulated_completion_tokens >= task_budget:
            stop_reason = "budget"
            break

        if _wall_exceeded():
            stop_reason = "task_wall_budget"
            history[-1]["stop"] = stop_reason
            break

        if turn < max_turns - 1:
            feedback = "Tool results:\n" + "\n\n".join(result_lines)
            messages.append({"role": "user", "content": feedback})

    # If the loop stopped on max_turns/budget after edits without a final test check, evaluate final state once
    if stop_reason in ("max_turns", "budget") and has_tests and dirty_since_last_test:
        t_ok, _ = run_tests(clean_task, worktree_dir)
        if t_ok:
            final_passed = True
            stop_reason = "pass"
            if history:
                history[-1]["passed"] = True

    return stop_reason, final_passed, leak_branch, accumulated_completion_tokens


def _capture_diff_safe(worktree_dir, base_commit):
    """Capture worktree diff if worktree_dir is a git repo, returning (diff_str, error_or_None)."""
    if not os.path.isdir(os.path.join(worktree_dir, ".git")):
        return "", None
    try:
        return capture_worktree_diff(worktree_dir, base_commit), None
    except Exception as exc:
        return "", f"{type(exc).__name__}: {exc}"


def _derive_abort_reason(stop_reason, history, explicit=None):
    """Return a non-empty abort reason string for abort/error stop reasons, else None."""
    if explicit is not None and str(explicit).strip():
        return str(explicit).strip()
    if stop_reason not in ABORT_STOP_REASONS:
        return None
    if history and isinstance(history[-1], dict):
        last_err = history[-1].get("err")
        if last_err and str(last_err).strip():
            return str(last_err).strip()
    return stop_reason


def run_task_loop(
    task,
    ask_fn,
    worktree_dir,
    max_turns=MAX_TURNS_DEFAULT,
    task_budget=TASK_BUDGET_TOKENS,
    slot_ctx=SLOT_CTX_DEFAULT,
    reserved_output_tokens=RESERVED_OUTPUT_TOKENS,
    token_counter=None,
    task_wall_budget=TASK_WALL_BUDGET_DEFAULT,
    clock_fn=time.monotonic,
    run_sentinel=None,
    run_dir=None,
    label=None,
    repo_root=None,
):
    """Execute the v2 structured-edit tool loop with prompt-size preflight, per-task wall budget, and instrumentation."""
    clean_task = tasks_item6.strip_hidden(task)
    has_tests = bool(clean_task.get("has_tests"))
    leak_branch = None
    abort_reason = None
    history = []
    loop_state = {"turn": 0, "t0": time.time(), "tokens": 0}
    try:
        messages = format_tool_messages(task, worktree_dir=worktree_dir, run_sentinel=run_sentinel)
    except PromptLeakError as exc:
        leak_branch = exc.branch
        if run_dir:
            hist_file = _save_leak_history(
                run_dir, clean_task["id"], 0, leak_branch, exc.leaked_prompt, label=label, repo_root=repo_root
            )
            _append_turn_log(
                run_dir,
                {
                    "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "task_id": clean_task["id"],
                    "turn": 0,
                    "event": "prompt_leak",
                    "leak_branch": leak_branch,
                    "message": str(exc),
                    "history_file": hist_file,
                },
                label=label,
                repo_root=repo_root,
            )
        final_diff, _ = _capture_diff_safe(worktree_dir, clean_task["base_commit"])
        return {
            "schema_version": RECORD_SCHEMA_VERSION,
            "task_id": clean_task["id"],
            "pr_number": clean_task["pr_number"],
            "has_tests": has_tests,
            "passed": False,
            "stop_reason": "prompt_leak",
            "stop": "prompt_leak",
            "harness_failure": False,
            "abort_reason": str(exc),
            "diff_empty": not bool(final_diff.strip()),
            "leak_branch": leak_branch,
            "turns_executed": 1,
            "history": [{
                "turn": 0,
                "seed": 6000 + clean_task["pr_number"] * 100,
                "passed": False,
                "err": str(exc),
                "stop": "prompt_leak",
                "leak_branch": leak_branch,
                "gen_s": 0.0,
                "tokens": 0,
                "prompt_tokens": 0,
            }],
            "total_completion_tokens": 0,
            "final_diff": final_diff,
        }
    except Exception as exc:
        err_text = f"{type(exc).__name__}: {exc}"
        final_diff, _ = _capture_diff_safe(worktree_dir, clean_task["base_commit"])
        return {
            "schema_version": RECORD_SCHEMA_VERSION,
            "task_id": clean_task["id"],
            "pr_number": clean_task["pr_number"],
            "has_tests": has_tests,
            "passed": False,
            "stop_reason": "task_error",
            "stop": "task_error",
            "harness_failure": True,
            "abort_reason": err_text,
            "diff_empty": not bool(final_diff.strip()),
            "turns_executed": 0,
            "history": [{
                "turn": 0,
                "seed": 6000 + clean_task["pr_number"] * 100,
                "passed": False,
                "err": err_text,
                "stop": "task_error",
                "gen_s": 0.0,
                "tokens": 0,
                "prompt_tokens": 0,
            }],
            "total_completion_tokens": 0,
            "final_diff": final_diff,
        }

    try:
        stop_reason, final_passed, leak_branch, accumulated_completion_tokens = _run_task_loop_turns(
            task=task,
            clean_task=clean_task,
            has_tests=has_tests,
            messages=messages,
            ask_fn=ask_fn,
            worktree_dir=worktree_dir,
            max_turns=max_turns,
            task_budget=task_budget,
            slot_ctx=slot_ctx,
            reserved_output_tokens=reserved_output_tokens,
            token_counter=token_counter,
            task_wall_budget=task_wall_budget,
            clock_fn=clock_fn,
            run_sentinel=run_sentinel,
            run_dir=run_dir,
            label=label,
            repo_root=repo_root,
            history=history,
            loop_state=loop_state,
        )
    except Exception as exc:
        err_text = f"{type(exc).__name__}: {exc}"
        stop_reason = "task_error"
        final_passed = False
        abort_reason = err_text
        accumulated_completion_tokens = loop_state["tokens"]
        err_turn = loop_state["turn"]
        history.append({
            "turn": err_turn,
            "seed": 6000 + clean_task["pr_number"] * 100 + err_turn,
            "passed": False,
            "err": err_text,
            "stop": "task_error",
            "gen_s": round(time.time() - loop_state["t0"], 2),
            "tokens": 0,
            "prompt_tokens": 0,
        })
        if run_dir:
            _append_turn_log(
                run_dir,
                {
                    "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "task_id": clean_task["id"],
                    "turn": err_turn,
                    "event": "task_error",
                    "abort_reason": err_text,
                },
                label=label,
                repo_root=repo_root,
            )

    if stop_reason in ("context_overflow", "request_error"):
        final_diff = ""
    else:
        final_diff, diff_err = _capture_diff_safe(worktree_dir, clean_task["base_commit"])
        if diff_err is not None and stop_reason != "task_error":
            stop_reason = "task_error"
            final_passed = False
            abort_reason = diff_err

    abort_reason = _derive_abort_reason(stop_reason, history, explicit=abort_reason)
    out_res = {
        "schema_version": RECORD_SCHEMA_VERSION,
        "task_id": clean_task["id"],
        "pr_number": clean_task["pr_number"],
        "has_tests": has_tests,
        "passed": False if stop_reason in ABORT_STOP_REASONS else final_passed,
        "stop_reason": stop_reason,
        "stop": stop_reason,
        "harness_failure": stop_reason == "task_error",
        "abort_reason": abort_reason,
        "diff_empty": not bool(final_diff.strip()),
        "turns_executed": len(history),
        "history": history,
        "total_completion_tokens": accumulated_completion_tokens,
        "final_diff": final_diff,
    }
    if leak_branch is not None:
        out_res["leak_branch"] = leak_branch
    return out_res


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

        # Case A: Model reads, makes a failed search_replace, retries & fixes, then finishes
        def mock_model_turn1_pass(messages, seed):
            joined = messages_to_text(messages)
            if "Tool results:" not in joined:
                # Turn 0: read file and submit buggy edit + finish
                calls = [
                    {"tool": "read_file", "args": {"path": "test_target.py", "start": 1, "end": 10}},
                    {"tool": "search_replace", "args": {"path": "test_target.py", "old": "return 0", "new": "return 1"}},
                    {"tool": "finish", "args": {"summary": "attempt 1"}},
                ]
                return {
                    "content": "```json\n" + json.dumps(calls) + "\n```",
                    "usage": {"completion_tokens": 50},
                }
            # Turn 1: fix code based on test error
            calls = [
                {"tool": "search_replace", "args": {"path": "test_target.py", "old": "return 1", "new": "return 42"}},
                {"tool": "finish", "args": {"summary": "fixed"}},
            ]
            return {
                "content": "```json\n" + json.dumps(calls) + "\n```",
                "usage": {"completion_tokens": 50},
            }

        res = run_task_loop(mock_task, mock_model_turn1_pass, temp_dir, max_turns=4)
        assert res["passed"] is True, f"Mock task expected to pass in turn 1: {res}"
        assert res["turns_executed"] == 2, f"Expected 2 turns, got {res['turns_executed']}"
        assert res["stop_reason"] == "pass", f"Expected stop_reason 'pass', got {res['stop_reason']}"
        assert "+    return 42" in res["final_diff"], "Harness did not capture git diff"
        print("[OK] Structured edit loop with feedback pass verified")

        # Case B: Repeat code stop check
        def mock_model_repeat(messages, seed):
            calls = [
                {"tool": "search_replace", "args": {"path": "test_target.py", "old": "nonexistent", "new": "x"}},
            ]
            return {
                "content": "```json\n" + json.dumps(calls) + "\n```",
                "usage": {"completion_tokens": 40},
            }

        res_repeat = run_task_loop(mock_task, mock_model_repeat, temp_dir, max_turns=4)
        assert res_repeat["passed"] is False
        assert res_repeat["stop_reason"] == "repeat_code"
        print("[OK] Repeat code stop rule verified")

        # Case C: Context preflight overflow check (never invokes ask_fn)
        called_overflow = []
        def should_not_be_called(messages, seed):
            called_overflow.append(True)
            return {"content": "", "usage": {}}

        res_ovf = run_task_loop(
            mock_task,
            should_not_be_called,
            temp_dir,
            slot_ctx=100,
            reserved_output_tokens=50,
            token_counter=lambda m: 999,
        )
        assert not called_overflow, "ask_fn must not be called when preflight detects overflow"
        assert res_ovf["schema_version"] == RECORD_SCHEMA_VERSION
        assert res_ovf["stop_reason"] == "context_overflow"
        assert res_ovf["final_diff"] == ""
        assert res_ovf["diff_empty"] is True
        assert res_ovf["abort_reason"] and "overflow" in res_ovf["abort_reason"]
        assert res_ovf["harness_failure"] is False
        print("[OK] Context preflight overflow verified")

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
    info = {k: p.get(k) for k in ("build_info", "model_path", "model_alias", "total_slots")}
    dgs = p.get("default_generation_settings") or {}
    if "n_ctx" in dgs:
        info["n_ctx"] = dgs["n_ctx"]
    return info


def server_ask(model, api=None):
    """Return an ask_fn(prompt_or_messages, seed, timeout=3600) querying /v1/chat/completions on the served model."""
    api = api or API_URL

    def ask(prompt_or_messages, seed, timeout=3600):
        messages = (
            prompt_or_messages
            if isinstance(prompt_or_messages, list)
            else [{"role": "user", "content": prompt_or_messages}]
        )
        body = {
            "model": model,
            "messages": messages,
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
        req_timeout = max(1.0, float(timeout)) if timeout is not None else 3600.0
        with urllib.request.urlopen(req, timeout=req_timeout) as r:
            resp = json.load(r)
        ch = resp["choices"][0]
        msg = ch.get("message") or {}
        return {
            "content": msg.get("content") or "",
            "tool_calls": msg.get("tool_calls"),
            "reasoning_chars": len(msg.get("reasoning_content") or ""),
            "finish": ch.get("finish_reason"),
            "usage": resp.get("usage", {}),
            "gen_s": round(time.time() - t, 2),
        }

    ask._accepts_timeout = True
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
        and avg_hand_fix_lines is not None
        and avg_hand_fix_lines <= 20.0
    ):
        return "KEEP"
    return "INCONCLUSIVE"



def run_subcommand(label, tasks_arg=None, api=API_URL, model=None, max_turns=MAX_TURNS_DEFAULT,
                   task_budget=TASK_BUDGET_TOKENS, slot_ctx=None,
                   reserved_output_tokens=RESERVED_OUTPUT_TOKENS,
                   task_wall_budget=TASK_WALL_BUDGET_DEFAULT, clock_fn=time.monotonic,
                   repo_root=None, results_dir=None, ask_fn=None, token_counter=None, resume=False,
                   run_dir=None, run_sentinel=None, tasks_override=None):
    """Execute the `run` subcommand: per PR, create scratch git worktree at base_commit, run loop, save diff & JSONL."""
    resume = resume or (os.environ.get("RESUME") == "1")
    if repo_root is None:
        repo_root = os.path.abspath(os.path.join(HERE, "..", ".."))
    if results_dir is None:
        results_dir = os.path.join(HERE, "results")
    os.makedirs(results_dir, exist_ok=True)
    diffs_dir = os.path.join(results_dir, f"{label}.diffs")
    os.makedirs(diffs_dir, exist_ok=True)
    jsonl_path = os.path.join(results_dir, f"{label}.jsonl")

    if run_sentinel is None:
        run_sentinel = generate_run_sentinel()
    if run_dir is None and ask_fn is None:
        run_dir = default_run_dir(label)

    all_tasks = tasks_override if tasks_override is not None else tasks_item6.load_tasks()
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
        if token_counter is None:
            token_counter = server_tokenize(api=api)
        eff_slot_ctx = slot_ctx if slot_ctx is not None else (srv_info.get("n_ctx") or SLOT_CTX_DEFAULT)
    else:
        resolved_model = model or "mock"
        srv_info = {"build_info": "mock", "model_path": "mock", "model_alias": resolved_model}
        eff_slot_ctx = slot_ctx if slot_ctx is not None else SLOT_CTX_DEFAULT

    # Load existing rows so running one task at a time updates/appends cleanly
    existing_by_id = {}
    existing_raw_by_id = {}
    if os.path.exists(jsonl_path):
        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    row = json.loads(line)
                    existing_by_id[row["task_id"]] = row
                    existing_raw_by_id[row["task_id"]] = line.rstrip("\r\n")

    if resume:
        selected_tasks = [t for t in selected_tasks if tasks_item6.strip_hidden(t)["id"] not in existing_by_id]

    def _flush_jsonl():
        order_ids = [t["id"] for t in all_tasks]
        ordered_tids = [tid for tid in order_ids if tid in existing_by_id]
        for tid in existing_by_id:
            if tid not in ordered_tids:
                ordered_tids.append(tid)
        selected_ids = {tasks_item6.strip_hidden(t)["id"] for t in selected_tasks}
        with open(jsonl_path, "w", encoding="utf-8") as f:
            for tid in ordered_tids:
                if tid in existing_raw_by_id and (resume or tid not in selected_ids):
                    f.write(existing_raw_by_id[tid] + "\n")
                else:
                    f.write(json.dumps(existing_by_id[tid]) + "\n")

    results = []
    for task in selected_tasks:
        clean_task = tasks_item6.strip_hidden(task)
        task_id = clean_task["id"]
        base_sha = clean_task["base_commit"]
        # Host-memory-only guard task: hidden_diff, merged_commit, and hidden_sentinel live strictly
        # in host-side process memory for check_prompt_leak and are NEVER written to wt_dir, sandbox
        # TMPDIR/env/argv, run.log, or turn_events.jsonl (run_task_loop strips them via strip_hidden).
        guard_task = dict(clean_task)
        if dict.__contains__(task, "merged_commit"):
            guard_task["merged_commit"] = dict.__getitem__(task, "merged_commit")
        if dict.__contains__(task, "hidden_diff"):
            guard_task["hidden_diff"] = dict.__getitem__(task, "hidden_diff")
        elif "merged_commit" in guard_task:
            guard_task["hidden_diff"] = tasks_item6.get_hidden_diff(task, repo_root=repo_root)
        guard_task["hidden_sentinel"] = run_sentinel

        wt_dir = tempfile.mkdtemp(prefix=f"wt_{label}_{task_id}_")
        t_start = time.time()
        try:
            create_isolated_scratch_repo(repo_root, base_sha, wt_dir)
            res = run_task_loop(
                guard_task,
                ask_fn,
                wt_dir,
                max_turns=max_turns,
                task_budget=task_budget,
                slot_ctx=eff_slot_ctx,
                reserved_output_tokens=reserved_output_tokens,
                token_counter=token_counter,
                task_wall_budget=task_wall_budget,
                clock_fn=clock_fn,
                run_sentinel=run_sentinel,
                run_dir=run_dir,
                label=label,
                repo_root=repo_root,
            )
        except PromptLeakError as exc:
            partial_diff, _ = _capture_diff_safe(wt_dir, base_sha)
            if run_dir:
                hist_file = _save_leak_history(
                    run_dir, task_id, 0, exc.branch, exc.leaked_prompt, label=label, repo_root=repo_root
                )
                _append_turn_log(
                    run_dir,
                    {
                        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        "task_id": task_id,
                        "turn": 0,
                        "event": "prompt_leak",
                        "leak_branch": exc.branch,
                        "message": str(exc),
                        "history_file": hist_file,
                    },
                    label=label,
                    repo_root=repo_root,
                )
            res = {
                "schema_version": RECORD_SCHEMA_VERSION,
                "task_id": task_id,
                "pr_number": clean_task["pr_number"],
                "has_tests": bool(clean_task.get("has_tests")),
                "passed": False,
                "stop_reason": "prompt_leak",
                "stop": "prompt_leak",
                "harness_failure": False,
                "abort_reason": str(exc),
                "diff_empty": not bool(partial_diff.strip()),
                "leak_branch": exc.branch,
                "turns_executed": 1,
                "history": [{"turn": 0, "passed": False, "err": str(exc), "stop": "prompt_leak", "leak_branch": exc.branch}],
                "total_completion_tokens": 0,
                "final_diff": partial_diff,
            }
        except Exception as exc:
            # Isolate per-task failures (including AssertionError) so one task never aborts the remaining tasks
            partial_diff, _ = _capture_diff_safe(wt_dir, base_sha)
            err_text = f"{type(exc).__name__}: {exc}"
            res = {
                "schema_version": RECORD_SCHEMA_VERSION,
                "task_id": task_id,
                "pr_number": clean_task["pr_number"],
                "has_tests": bool(clean_task.get("has_tests")),
                "passed": False,
                "stop_reason": "task_error",
                "stop": "task_error",
                "harness_failure": True,
                "abort_reason": err_text,
                "diff_empty": not bool(partial_diff.strip()),
                "turns_executed": 0,
                "history": [{"turn": 0, "passed": False, "err": err_text, "stop": "task_error"}],
                "total_completion_tokens": 0,
                "final_diff": partial_diff,
            }
        finally:
            if os.path.exists(wt_dir):
                shutil.rmtree(wt_dir, ignore_errors=True)

        res["wall_s"] = round(time.time() - t_start, 2)
        res["model"] = resolved_model
        res["server"] = srv_info

        diff_file = os.path.join(diffs_dir, f"{task_id}.diff")
        with open(diff_file, "w", encoding="utf-8") as df:
            df.write(res["final_diff"])
        res["diff_file"] = os.path.relpath(diff_file, repo_root) if diff_file.startswith(repo_root) else diff_file

        existing_by_id[task_id] = res
        results.append(res)
        _flush_jsonl()
        print(
            f"{task_id:14} pr=#{res['pr_number']:<2} has_tests={str(res['has_tests']):<5} "
            f"passed={str(res['passed']):<5} stop={res['stop_reason']:<16} turns={res['turns_executed']} "
            f"tok={res['total_completion_tokens']} diff_lines={len(res['final_diff'].splitlines())}",
            flush=True,
        )

    if not results and os.path.exists(jsonl_path):
        _flush_jsonl()

    return results


def _verify_grade_output(task, returncode, output):
    """Host-side decision logic verifying exit code and expected test counts from sandbox output."""
    if returncode != 0:
        return False, f"Test command exited with code {returncode}:\n{output}"

    spec = task.get("grade_spec")
    if not spec:
        return True, output

    mode = spec.get("mode")
    lines = [ln.rstrip("\r\n") for ln in output.splitlines() if ln.strip()]

    if mode == "shell":
        pat = re.compile(spec["count_pattern"])
        count = sum(1 for ln in lines if pat.search(ln))
        if count != spec["expected_test_count"]:
            return False, f"Expected {spec['expected_test_count']} matching tests, got {count}:\n{output}"
        req_last = spec.get("required_last_line")
        if req_last and (not lines or lines[-1].strip() != req_last):
            return False, f"Expected last line {req_last!r}:\n{output}"
        return True, output

    if mode == "selftest_file":
        ok_count = sum(1 for ln in lines if ln.strip().startswith("ok "))
        fail_count = sum(1 for ln in lines if ln.strip().startswith("FAIL "))
        if fail_count > 0 or ok_count != spec["expected_test_count"]:
            return False, f"Expected {spec['expected_test_count']} ok checks (0 fail), got ok={ok_count} fail={fail_count}:\n{output}"
        if "selftest OK" not in output:
            return False, f"Missing 'selftest OK' in output:\n{output}"
        return True, output

    if mode == "unittest":
        m = re.search(r"Ran (\d+) tests?", output)
        if not m:
            return False, f"Did not find 'Ran X tests' in unittest output:\n{output}"
        ran = int(m.group(1))
        if ran != spec["expected_test_count"]:
            return False, f"Expected {spec['expected_test_count']} unittests, ran {ran}:\n{output}"
        if "FAILED" in output or "ERROR" in output:
            return False, f"Unittest reported failure or error:\n{output}"
        if "OK" not in output:
            return False, f"Unittest missing 'OK':\n{output}"
        return True, output

    if mode == "unittest_and_selftest_file":
        m = re.search(r"Ran (\d+) tests?", output)
        if not m:
            return False, f"Did not find 'Ran X tests' in unittest output:\n{output}"
        ran = int(m.group(1))
        if ran != spec["expected_test_count"]:
            return False, f"Expected {spec['expected_test_count']} unittests, ran {ran}:\n{output}"
        if "FAILED" in output or "ERROR" in output:
            return False, f"Unittest reported failure or error:\n{output}"
        ok_count = sum(1 for ln in lines if ln.strip().startswith("ok "))
        fail_count = sum(1 for ln in lines if ln.strip().startswith("FAIL "))
        if fail_count > 0 or ok_count != spec["expected_selftest_count"]:
            return False, f"Expected {spec['expected_selftest_count']} selftest checks (0 fail), got ok={ok_count} fail={fail_count}:\n{output}"
        if "Selftest PASSED" not in output:
            return False, f"Missing 'Selftest PASSED' in output:\n{output}"
        return True, output

    raise ValueError(f"Unknown grade_spec mode: {mode}")


def _extract_selftest_block(repo_root, commit_sha, rel_path):
    """Extract def selftest(): function source code from a file at commit_sha using AST."""
    show_res = subprocess.run(
        ["git", "-C", repo_root, "show", f"{commit_sha}:{rel_path}"],
        capture_output=True,
        text=True,
        check=True,
    )
    src = show_res.stdout
    tree = ast.parse(src)
    st_node = None
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "selftest":
            st_node = node
            break
    if st_node is None:
        raise ValueError(f"Function 'selftest' not found in {commit_sha}:{rel_path}")
    lines = src.splitlines(keepends=True)
    return "".join(lines[st_node.lineno - 1 : st_node.end_lineno])


def _build_merged_selftest_runner(module_dir, module_name, selftest_code):
    """Generate python script for standalone runner that imports candidate module and executes merged selftest."""
    return (
        "#!/usr/bin/env python3\n"
        "import importlib\n"
        "import os\n"
        "import sys\n\n"
        "work_dir = '/work'\n"
        f"mod_dir = os.path.join(work_dir, {module_dir!r})\n"
        "for p in (mod_dir, work_dir):\n"
        "    if p not in sys.path:\n"
        "        sys.path.insert(0, p)\n\n"
        f"mod = importlib.import_module({module_name!r})\n\n"
        f"_ST_CODE = {selftest_code!r}\n"
        "_code = compile(_ST_CODE, '<merged_selftest>', 'exec')\n"
        "exec(_code, mod.__dict__)\n\n"
        "rc = mod.selftest()\n"
        "sys.exit(rc if isinstance(rc, int) else (0 if (rc is None or rc) else 1))\n"
    )


def _run_harness_grade_spec(task, grade_dir, repo_root, ro_binds=None, timeout=180):
    """Execute tests in grade_dir inside outer bwrap sandbox with host-side evaluation only.

    Security & Isolation properties:
    - The trusted grader runs entirely on the host side, outside the sandbox, and never
      imports or runs anything from the scratch tree.
    - Decides only from the sandbox's exit code, output, and expected count of tests run.
    - No token, no grade script, and no grader process live inside the sandbox.
    - Outer /usr/bin/bwrap uses --unshare-pid with fresh --proc /proc and --die-with-parent,
      so only the test run's own processes are visible.
    - Restored merged-commit test files are mounted read-only via ro_binds over /work.
    """
    if not has_bwrap():
        raise RuntimeError("bwrap sandbox is unavailable; refusing to execute grade unsandboxed")
    home_dir, tmp_dir, shim_dir = prepare_isolated_home_and_tmp(grade_dir)
    clean_env = build_minimal_env(home_dir="/home/pilot", tmp_dir="/tmp")

    spec = task.get("grade_spec")
    if spec and spec.get("cmd"):
        cmd = spec["cmd"]
    elif spec and spec.get("mode") == "selftest_file":
        cmd = "python3 /work/_merged_selftest_runner.py"
    elif spec and spec.get("mode") == "unittest_and_selftest_file":
        test_mod = spec.get("test_module", "")
        cmd = f"python3 -m unittest {test_mod} && python3 /work/_merged_selftest_runner.py"
    else:
        cmd = task.get("test_cmd")
    if not cmd:
        return True, ""

    iso_cmd = _wrap_shell_with_isolated_python3(cmd, "/work")
    bwrap_cmd = build_outer_bwrap_cmd(
        grade_dir, home_dir, tmp_dir, shim_dir, ["bash", "-c", iso_cmd], clean_env, ro_binds=ro_binds
    )

    try:
        res = subprocess.run(
            bwrap_cmd,
            stdin=subprocess.DEVNULL,
            cwd=grade_dir,
            env=clean_env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = (res.stdout or "") + (res.stderr or "")
        return _verify_grade_output(task, res.returncode, output)
    finally:
        cleanup_isolated_home_and_tmp(grade_dir)


def regrade_task_diff(task, final_diff, repo_root=None, timeout=180):
    """Independently grade a task's final_diff in a fresh clean copy of base_commit with test files restored from merged_commit.

    Never trusts the in-loop `passed` flag or bare exit code 0:
    1. Creates a fresh standalone scratch tree at `base_commit`.
    2. Applies `final_diff` (if non-empty) with path confinement checks.
    3. Authoritative test files from `merged_commit` are staged in a separate host directory and
       mounted read-only over `/work` inside the sandbox, preventing tampering or deletion.
    4. Trusted grader runs on the host outside the sandbox, evaluating sandbox exit code and test counts.
    """
    if not task.get("has_tests"):
        return None, "Not a testable task"
    if repo_root is None:
        repo_root = os.path.abspath(os.path.join(HERE, "..", ".."))

    base_sha = dict.__getitem__(task, "base_commit")
    merged_sha = dict.__getitem__(task, "merged_commit")
    grade_dir = tempfile.mkdtemp(prefix=f"grade_{task['id']}_")
    ro_tests_dir = tempfile.mkdtemp(prefix=f"ro_{task['id']}_")
    clean_env = build_minimal_env()
    try:
        create_isolated_scratch_repo(repo_root, base_sha, grade_dir)
        if final_diff and final_diff.strip():
            ok, msg = apply_updates(grade_dir, {"__patch__": final_diff.rstrip("\n")})
            if not ok:
                return False, f"Failed applying final_diff during grade: {msg}"

        # Restore authoritative test files from merged_commit into ro_tests_dir for read-only bind mount
        ro_binds = []
        for tf in task.get("test_files", []):
            host_tf = resolve_confined_path(ro_tests_dir, tf)
            os.makedirs(os.path.dirname(host_tf), exist_ok=True)
            show_res = subprocess.run(
                ["git", "-C", repo_root, "show", f"{merged_sha}:{tf}"],
                env=clean_env,
                capture_output=True,
            )
            if show_res.returncode != 0:
                return False, f"Failed restoring test file {tf} from {merged_sha}"
            with open(host_tf, "wb") as f:
                f.write(show_res.stdout)
            ro_binds.append((host_tf, os.path.join("/work", tf)))

        spec = task.get("grade_spec")
        if spec and spec.get("mode") in ("selftest_file", "unittest_and_selftest_file") and spec.get("source_file_at_merged"):
            st_code = _extract_selftest_block(repo_root, merged_sha, spec["source_file_at_merged"])
            runner_content = _build_merged_selftest_runner(
                module_dir=spec.get("module_dir", "bench/loop"),
                module_name=spec["module_name"],
                selftest_code=st_code,
            )
            runner_host_path = os.path.join(ro_tests_dir, "_merged_selftest_runner.py")
            with open(runner_host_path, "w", encoding="utf-8") as f:
                f.write(runner_content)
            ro_binds.append((runner_host_path, "/work/_merged_selftest_runner.py"))

        return _run_harness_grade_spec(task, grade_dir, repo_root, ro_binds=ro_binds, timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, f"ERROR: grade test command timed out after {timeout} seconds."
    except RuntimeError:
        raise
    except Exception as e:
        return False, f"ERROR during regrade_task_diff: {e}"
    finally:
        shutil.rmtree(grade_dir, ignore_errors=True)
        shutil.rmtree(ro_tests_dir, ignore_errors=True)



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
    max_schema_version = 1

    for task in all_tasks:
        tid = task["id"]
        if tid not in rows_by_id:
            continue
        row = rows_by_id[tid]
        row_schema_version = int(row.get("schema_version") or 1)
        if row_schema_version > max_schema_version:
            max_schema_version = row_schema_version
        has_tests = bool(task.get("has_tests"))
        local_diff = row.get("final_diff", "")
        diff_empty = not bool(local_diff.strip())
        stop_reason = row.get("stop_reason")
        in_loop_passed = bool(row.get("passed")) if has_tests else None
        if has_tests:
            testable_total += 1
            if diff_empty:
                passed = False
                grade_test_out = "empty diff"
            else:
                passed, grade_test_out = regrade_task_diff(task, local_diff, repo_root=repo_root)
        else:
            passed = None
            grade_test_out = ""

        hidden_diff = task.get("hidden_diff") or tasks_item6.get_hidden_diff(task, repo_root=repo_root)
        diff_metrics = evaluate_diff(local_diff, hidden_diff)

        rev = reviews_by_id.get(tid)
        if diff_empty and rev is None:
            # Amendment, Nov 18 2026: a task with an empty diff (including context_overflow,
            # and pr13's empty diff) is an automatic non-approval with no Grok review,
            # hand_fix_lines n/a and excluded from the hand-fix average.
            # Amendment, Nov 21 2026 (schema v2+): unreviewed tasks record tamper=None (null)
            # instead of False, while legacy v1/v2 frozen rows preserve tamper=False.
            is_app1 = False
            is_app_final = False
            v1 = "NON-APPROVAL"
            v_final = "NON-APPROVAL"
            hf_lines = None
            tamper = None if row_schema_version >= 2 else False
            fresh_session = True
        elif rev is not None:
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
            if "tamper" not in rev or not isinstance(rev["tamper"], bool):
                raise ValueError(f"Review record for {tid} is missing required boolean 'tamper' field: {rev!r}")
            tamper = rev["tamper"]
            fresh_session = rev.get("fresh_session")
            if fresh_session is False:
                raise ValueError(f"Review record for {tid} must use a fresh reviewer session (fresh_session=False)")
            hf_lines = rev["hand_fix_lines"]
            if tamper:
                if has_tests:
                    passed = False
                is_app1 = False
                is_app_final = False
            else:
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
            tamper = None
            fresh_session = None

        if has_tests and passed:
            testable_passed += 1

        entry = {
            "task_id": tid,
            "pr_number": task["pr_number"],
            "has_tests": has_tests,
            "in_loop_passed": in_loop_passed,
            "test_passed": passed,
            "tamper": tamper,
            "fresh_session": fresh_session,
            "stop_reason": stop_reason,
            "turns_executed": row.get("turns_executed"),
            "total_completion_tokens": row.get("total_completion_tokens"),
            "wall_s": row.get("wall_s"),
            "diff_file": row.get("diff_file"),
            "diff_metrics": diff_metrics,
            "first_verdict": v1,
            "final_verdict": v_final,
            "hand_fix_lines": hf_lines,
        }
        if row_schema_version >= 2:
            entry["diff_empty"] = diff_empty
            entry["abort_reason"] = _derive_abort_reason(
                stop_reason, row.get("history"), explicit=row.get("abort_reason")
            )
            entry["harness_failure"] = (
                bool(row["harness_failure"]) if "harness_failure" in row else (stop_reason == "task_error")
            )
        per_task.append(entry)

    total_evaluated = len(per_task)
    final_app_count = approved_final if (has_all_reviews and total_evaluated > 0) else None
    avg_hf = (sum(hand_fix_lines_approved) / len(hand_fix_lines_approved)) if hand_fix_lines_approved else None

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
        "avg_hand_fix_lines_per_approved": round(avg_hf, 2) if (final_app_count is not None and avg_hf is not None) else None,
        "decision": decision,
        "per_task": per_task,
    }
    if max_schema_version >= 2:
        grade_summary = {"schema_version": max_schema_version, **grade_summary}

    grade_path = os.path.join(results_dir, f"{label}.grade.json")
    with open(grade_path, "w", encoding="utf-8") as gf:
        json.dump(grade_summary, gf, indent=2)

    print(json.dumps({k: v for k, v in grade_summary.items() if k != "per_task"}, indent=2), flush=True)
    return grade_summary


def main(argv=None):
    parser = argparse.ArgumentParser(description="Item 6 Pilot PR Loop Runner")
    parser.add_argument("--selftest", action="store_true", help="Run CPU-only self-tests")
    parser.add_argument("--label", type=str, default="item6-pilot-v2", help="Run label")
    parser.add_argument("--tasks", type=str, default=None, help="Comma-separated task IDs")
    parser.add_argument("--api", type=str, default=API_URL, help="Served model API URL (default :8081)")
    parser.add_argument("--model", type=str, default=None, help="Expected model alias")
    parser.add_argument("-k", "--max-turns", type=int, default=MAX_TURNS_DEFAULT, help="Max turns per task")
    parser.add_argument("--task-budget", type=int, default=TASK_BUDGET_TOKENS, help="Max completion tokens per task")
    parser.add_argument("--slot-ctx", type=int, default=None, help="Per-slot context window (default from /props or 65536)")
    parser.add_argument("--reserved-output-tokens", type=int, default=RESERVED_OUTPUT_TOKENS, help="Output token budget reserved in context preflight")
    parser.add_argument("--task-wall-budget", type=float, default=TASK_WALL_BUDGET_DEFAULT, help="Per-task wall time budget in seconds (default floor(4320/7)=617)")
    parser.add_argument("--resume", action="store_true", default=False, help="Resume run: skip already completed tasks")
    parser.add_argument("--run-dir", type=str, default=None, help="Uncommitted scratch run dir for per-turn instrumentation and leak histories (default /tmp/lab-seats/<label>/)")

    subparsers = parser.add_subparsers(dest="subcommand")

    p_run = subparsers.add_parser("run", help="Run agentic loop on PR tasks in scratch worktrees")
    p_run.add_argument("--label", type=str, default="item6-pilot-v2", help="Run label")
    p_run.add_argument("--tasks", type=str, default=None, help="Comma-separated task IDs")
    p_run.add_argument("--api", type=str, default=API_URL, help="Served model API URL (default :8081)")
    p_run.add_argument("--model", type=str, default=None, help="Expected model alias")
    p_run.add_argument("-k", "--max-turns", type=int, default=MAX_TURNS_DEFAULT, help="Max turns per task")
    p_run.add_argument("--task-budget", type=int, default=TASK_BUDGET_TOKENS, help="Max completion tokens per task")
    p_run.add_argument("--slot-ctx", type=int, default=None, help="Per-slot context window (default from /props or 65536)")
    p_run.add_argument("--reserved-output-tokens", type=int, default=RESERVED_OUTPUT_TOKENS, help="Output token budget reserved in context preflight")
    p_run.add_argument("--task-wall-budget", type=float, default=TASK_WALL_BUDGET_DEFAULT, help="Per-task wall time budget in seconds (default floor(4320/7)=617)")
    p_run.add_argument("--resume", action="store_true", default=False, help="Resume run: skip already completed tasks")
    p_run.add_argument("--run-dir", type=str, default=None, help="Uncommitted scratch run dir for per-turn instrumentation and leak histories (default /tmp/lab-seats/<label>/)")

    p_grade = subparsers.add_parser("grade", help="Grade recorded worktree diffs and compute KEEP/DROP")
    p_grade.add_argument("--label", type=str, default="item6-pilot-v2", help="Run label")
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
            slot_ctx=args.slot_ctx,
            reserved_output_tokens=args.reserved_output_tokens,
            task_wall_budget=args.task_wall_budget,
            resume=getattr(args, "resume", False),
            run_dir=getattr(args, "run_dir", None),
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
