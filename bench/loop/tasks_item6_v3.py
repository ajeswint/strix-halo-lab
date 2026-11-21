#!/usr/bin/env python3
"""Task definitions for Roadmap Item 6 Pilot v3: Unseen external-repo PR evaluation.

Frozen batch of 7 unseen merged PRs mechanically selected by `select_v3.py` from
`more-itertools/more-itertools` (pinned HEAD `e3f79f4fde5f7c107f70a20730b17240a05ba99b`),
all merged strictly after the Qwen3.6-35B-A3B Hugging Face release date
(`2026-04-15T05:59:19Z`, source: https://huggingface.co/Qwen/Qwen3.6-35B-A3B).

Rules enforced:
- Prompts are constructed deterministically by `build_v3_task_prompt` directly
  from the linked GitHub issue text (when linked) or PR title and body as
  written, with fenced code blocks removed; zero hand-written prose and zero
  inspection of merged diffs.
- Hidden tests, reference solutions, and literal grading seed 104729 never
  appear in this file or in any in-loop prompt.
- Offline bwrap verification confirms every task's merged-commit tests PASS at
  `merged_commit` and FAIL at `base_commit` with no network and stdlib only.
"""
import copy
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import select_v3  # noqa: E402
import tasks_item6  # noqa: E402

V3_REPO_SLUG = select_v3.V3_REPO_SLUG
V3_REPO_URL = select_v3.V3_REPO_URL
DEFAULT_V3_REPO_DIR = select_v3.DEFAULT_V3_REPO_DIR
V3_HEAD_COMMIT = select_v3.V3_HEAD_COMMIT
QWEN36_RELEASE_UTC = select_v3.QWEN36_RELEASE_UTC
QWEN36_RELEASE_SOURCE = select_v3.QWEN36_RELEASE_SOURCE


def strip_code_blocks_and_clean(text):
    """Mechanically remove HTML comments and fenced code blocks, and redact literal 104729."""
    s = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    s = re.sub(r"<!--.*?-->", "", s, flags=re.DOTALL)
    s = re.sub(
        r"(?m)^[ \t]*(```|~~~)[^\n]*\n.*?\n[ \t]*\1[ \t]*$",
        "[code block removed]",
        s,
        flags=re.DOTALL,
    )
    s = re.sub(
        r"(?m)^[ \t]*(```|~~~)[^\n]*\n.*$",
        "[code block removed]",
        s,
        flags=re.DOTALL,
    )
    s = s.replace("104729", "<REDACTED_SEED>")
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def build_v3_task_prompt(repo_slug, source_kind, raw_source_title, raw_source_body):
    """Build a v3 task prompt strictly by rule from verbatim issue or PR title and body."""
    title = strip_code_blocks_and_clean(raw_source_title)
    body = strip_code_blocks_and_clean(raw_source_body)
    return f"Repo {repo_slug} — {source_kind}: {title}\n\n{body}"


_RAW_V3_SPECS = [{'id': 'item6v3_pr1260',
  'pr_number': 1260,
  'repo_slug': 'more-itertools/more-itertools',
  'title': 'Validate running window sizes through the index protocol',
  'base_commit': 'd634820be7a23b6a85441ee67051530fb0a8a960',
  'merged_commit': '1da45ae4b61a832ed080f08a8833784aad0a9534',
  'merged_at_utc': '2026-09-18T19:49:04Z',
  'total_changed_lines': 54,
  'has_tests': True,
  'needs_bwrap': True,
  'test_cmd': 'python3 -m unittest tests.test_recipes',
  'test_files': ['tests/test_recipes.py'],
  'grade_spec': {'mode': 'unittest',
                 'test_module': 'tests.test_recipes',
                 'cmd': 'python3 -m unittest tests.test_recipes',
                 'expected_test_count': 200},
  'files': ['docs/versions.rst', 'more_itertools/recipes.py', 'tests/test_recipes.py'],
  'source_kind': 'PR #1260',
  'raw_source_title': 'Validate running window sizes through the index protocol',
  'raw_source_body': 'With `maxlen=2.5`, `running_min` and `running_max` never expire the oldest '
                     'candidate and silently compute an unbounded result; `running_mean` silently '
                     'uses a different window size. Integer-like objects implementing `__index__` '
                     'also fail despite working with `running_median`.\n'
                     '\n'
                     'Normalize `maxlen` through the index protocol in these functions and in '
                     '`running_statistics`, which also needs integer `Stats.size` values. Add '
                     'regressions for invalid floats, index-protocol objects, and nonpositive '
                     'sizes, plus a changelog entry.\n'
                     '\n'
                     'Validation: regressions fail before the change; all 913 unittest tests pass '
                     'on CPython 3.12.14; Ruff lint and formatting pass.\n'
                     '\n'
                     'Implemented and locally validated with OpenAI Codex.\n'
                     '\n'
                     'Issue tracking: Found during source inspection; no matching open issue was '
                     'identified for this fix.\n'},
 {'id': 'item6v3_pr1269',
  'pr_number': 1269,
  'repo_slug': 'more-itertools/more-itertools',
  'title': 'Issue 1268: seekable.peek/bool no longer drop items when maxlen is 0',
  'base_commit': '1da45ae4b61a832ed080f08a8833784aad0a9534',
  'merged_commit': 'b5e3886a37209bb880f17d82fbf4ba00ece0e41e',
  'merged_at_utc': '2026-09-21T16:16:22Z',
  'total_changed_lines': 19,
  'has_tests': True,
  'needs_bwrap': True,
  'test_cmd': 'python3 -m unittest tests.test_more',
  'test_files': ['tests/test_more.py'],
  'grade_spec': {'mode': 'unittest',
                 'test_module': 'tests.test_more',
                 'cmd': 'python3 -m unittest tests.test_more',
                 'expected_test_count': 731},
  'files': ['more_itertools/more.py', 'tests/test_more.py'],
  'source_kind': 'Issue #1268 (PR #1269)',
  'raw_source_title': 'seekable(..., maxlen=0): peek() and bool() drop items',
  'raw_source_body': '`seekable(..., maxlen=0)` is supposed to disable the history cache '
                     '(`elements()` stays empty) while still iterating the source. `peek()` and '
                     '`bool()` (which calls `peek()`) currently consume an item that they cannot '
                     'put back, because a `deque(maxlen=0)` discards on append.\n'
                     '\n'
                     '```python\n'
                     'from more_itertools import seekable\n'
                     '\n'
                     's = seekable([10, 20, 30], maxlen=0)\n'
                     's.peek()\n'
                     'list(s)  # [20, 30]  — 10 is gone\n'
                     '\n'
                     's = seekable([10, 20, 30], maxlen=0)\n'
                     'bool(s)  # True\n'
                     'list(s)  # [20, 30]  — 10 is gone\n'
                     '```\n'
                     '\n'
                     'Default `maxlen=None` is fine (`peek` is stable; `bool` does not consume). '
                     '`test_maxlen_zero` only checks `list(s)` and does not cover '
                     'peek/truthiness.\n'
                     '\n'
                     'Happy to send a PR.'},
 {'id': 'item6v3_pr1305',
  'pr_number': 1305,
  'repo_slug': 'more-itertools/more-itertools',
  'title': 'Issue 1304: ichunked matches chunked for n=0 and negative n',
  'base_commit': '790bb0bb2c03e7a07282e5f16f4b1fde35b8fcf5',
  'merged_commit': '1ea82a711c69f590054987b5cb194157f8ce8ac4',
  'merged_at_utc': '2026-09-29T20:28:23Z',
  'total_changed_lines': 20,
  'has_tests': True,
  'needs_bwrap': True,
  'test_cmd': 'python3 -m unittest tests.test_more',
  'test_files': ['tests/test_more.py'],
  'grade_spec': {'mode': 'unittest',
                 'test_module': 'tests.test_more',
                 'cmd': 'python3 -m unittest tests.test_more',
                 'expected_test_count': 733},
  'files': ['docs/versions.rst', 'more_itertools/more.py', 'tests/test_more.py'],
  'source_kind': 'Issue #1304 (PR #1305)',
  'raw_source_title': "ichunked(..., 0) raises islice's ValueError on a nonempty iterable",
  'raw_source_body': '`ichunked` is documented as being like `chunked`, but with lazy chunks. '
                     '`chunked` treats `n=0` as "yield nothing". `ichunked` only does that when '
                     'the source is already empty; with any remaining items it calls '
                     '`islice(iterator, n - 1)` and blows up.\n'
                     '\n'
                     'I hit this switching a streaming pipeline from `chunked` to `ichunked` so '
                     'batches would not be materialized as lists. Chunk size comes from the same '
                     'config in both paths; `0` means "this stage is disabled, emit nothing."\n'
                     '\n'
                     '```python\n'
                     'from more_itertools import chunked, ichunked\n'
                     '\n'
                     'rows = ["a", "b", "c"]  # e.g. leftover rows from a DB cursor\n'
                     'chunk_size = 0          # config: skip this sink\n'
                     '\n'
                     'print(list(chunked(rows, chunk_size)))\n'
                     '# []\n'
                     '\n'
                     'print([list(c) for c in ichunked(rows, chunk_size)])\n'
                     '# ValueError: Stop argument for islice() must be None or an integer: 0 <= x '
                     '<= sys.maxsize.\n'
                     '```\n'
                     '\n'
                     '`IchunkedTests.test_zero` only uses `iterable = []`, which never enters the '
                     '`for first in iterator` loop, so the `islice(..., n - 1)` path is untested.\n'
                     '\n'
                     'Negative `n` has the same leak: `chunked` raises `ValueError: n must be at '
                     'least 0`, `ichunked` raises islice\'s "Indices for islice() must be None or '
                     'an integer...".\n'
                     '\n'
                     'Happy to send a PR.'},
 {'id': 'item6v3_pr1322',
  'pr_number': 1322,
  'repo_slug': 'more-itertools/more-itertools',
  'title': 'peekable: avoid caching entire iterable on negative slice with omitted stop',
  'base_commit': '4aeb4338ae1407d8da9723e86da99efeb446f719',
  'merged_commit': '69dbc3392928afe1cc892a387bf0e721522f21c2',
  'merged_at_utc': '2026-10-30T14:45:20Z',
  'total_changed_lines': 53,
  'has_tests': True,
  'needs_bwrap': True,
  'test_cmd': 'python3 -m unittest tests.test_more',
  'test_files': ['tests/test_more.py'],
  'grade_spec': {'mode': 'unittest',
                 'test_module': 'tests.test_more',
                 'cmd': 'python3 -m unittest tests.test_more',
                 'expected_test_count': 736},
  'files': ['docs/versions.rst', 'more_itertools/more.py', 'tests/test_more.py'],
  'source_kind': 'PR #1322',
  'raw_source_title': 'peekable: avoid caching entire iterable on negative slice with omitted stop',
  'raw_source_body': '### Issue reference\n'
                     'None\n'
                     '\n'
                     '### Changes\n'
                     'A reverse slice with an omitted stop, such as `peekable(count())[5::-1]`, '
                     'ends at index 0. The old implementation treated the internal negative stop '
                     'sentinel as right-relative indexing and cached the entire source. This hangs '
                     'on an infinite iterator and buffers unnecessary items on a large finite '
                     'source.\n'
                     '\n'
                     'Cache only through `start + 1` for this case; retain full caching for actual '
                     'negative indices or an omitted reverse start. The release note is under '
                     'Unreleased, above the existing 11.2.1/11.2.0 history.\n'
                     '\n'
                     '### Checks and tests\n'
                     '- Preserve the finite-source regression and add a guarded infinite source: '
                     'prefill three cached items, take repeated reverse slices, then verify normal '
                     'iteration order. A seventh source read fails immediately instead of hanging. '
                     "Adapted from @carlitogwapito's [test-only "
                     'commit](https://github.com/carlitogwapito/more-itertools/commit/383711aab0b06db2a27df46af3871d02819e7d8a).\n'
                     '- The same guarded test fails with the exact read-bound assertion on master '
                     '`4aeb433` and passes on this branch. Imports were checked against each '
                     'checkout.\n'
                     '- Python 3.13.3: full unittest run, 932 tests with 5 skipped; 100% statement '
                     'coverage.\n'
                     '- Ruff format/check, stubtest, Sphinx with `-W`, Flit sdist/wheel build, and '
                     'Twine checks passed. Gate components ran individually with pinned '
                     'development tools; the literal `make all-checks` target and the full '
                     'version/OS matrix were not run.\n'},
 {'id': 'item6v3_pr1342',
  'pr_number': 1342,
  'repo_slug': 'more-itertools/more-itertools',
  'title': 'fix: validate the chunk size in chunked_even',
  'base_commit': '20c4ee5c63f8f8c35a37aee3b69d95cd2450c09a',
  'merged_commit': '08dca284ba5446a026afdc34067b658f9da989eb',
  'merged_at_utc': '2026-10-30T14:50:27Z',
  'total_changed_lines': 18,
  'has_tests': True,
  'needs_bwrap': True,
  'test_cmd': 'python3 -m unittest tests.test_more',
  'test_files': ['tests/test_more.py'],
  'grade_spec': {'mode': 'unittest',
                 'test_module': 'tests.test_more',
                 'cmd': 'python3 -m unittest tests.test_more',
                 'expected_test_count': 738},
  'files': ['more_itertools/more.py', 'tests/test_more.py'],
  'source_kind': 'PR #1342',
  'raw_source_title': 'fix: validate the chunk size in chunked_even',
  'raw_source_body': '### Issue reference\n'
                     '\n'
                     'N/A — trivial boundary fix; no issue was filed.\n'
                     '\n'
                     '### Changes\n'
                     '\n'
                     '`chunked_even(iterable, n)` did not validate `n` before handing it to '
                     '`islice`. A negative size leaked `ValueError: Indices for islice()...`; a '
                     'zero size leaked `ValueError: Step for islice()...` and consumed two source '
                     'items before raising. Its sibling sizing functions (`chunked`, `ichunked`, '
                     '`sliced`) already define the contract: `n == 0` yields nothing without '
                     "consuming the source, `n < 0` raises `ValueError('n must be at least 0')`.\n"
                     '\n'
                     'The fix adds those two guards at the top of `chunked_even`, before '
                     '`iter(iterable)`, so invalid sizes fail before any source consumption and '
                     'match the rest of the module.\n'
                     '\n'
                     '### Checks and tests\n'
                     '\n'
                     'The new `test_zero_chunk_size` and `test_negative_chunk_size` fail on '
                     '`4aeb433` with the `islice` errors and pass on this branch. They also assert '
                     'the source iterator is untouched after the error/empty result.\n'
                     '\n'
                     '`pytest -q` → 767 passed, 21,194 subtests passed. `ruff check more_itertools '
                     'tests` and `ruff format --check more_itertools tests` pass.\n'
                     '\n'
                     '<details><summary>Details</summary>\n'
                     '\n'
                     '`chunked_even(..., None)` remains unsupported (`TypeError`), unchanged. '
                     'Other itertools recipes with bare `ValueError` tests (`take`, `nth`, '
                     '`consume`, `spy`, `nth_or_last`) are outside this change because they have '
                     'no sibling-consistency contract.\n'
                     '\n'
                     '</details>\n'},
 {'id': 'item6v3_pr1345',
  'pr_number': 1345,
  'repo_slug': 'more-itertools/more-itertools',
  'title': 'Fix numeric_range equality and hashing above sys.maxsize',
  'base_commit': '08dca284ba5446a026afdc34067b658f9da989eb',
  'merged_commit': 'f42daddf205f335fea6e200dad46049f33e71221',
  'merged_at_utc': '2026-11-04T00:20:44Z',
  'total_changed_lines': 34,
  'has_tests': True,
  'needs_bwrap': True,
  'test_cmd': 'python3 -m unittest tests.test_more',
  'test_files': ['tests/test_more.py'],
  'grade_spec': {'mode': 'unittest',
                 'test_module': 'tests.test_more',
                 'cmd': 'python3 -m unittest tests.test_more',
                 'expected_test_count': 740},
  'files': ['more_itertools/more.py', 'tests/test_more.py'],
  'source_kind': 'Issue #1344 (PR #1345)',
  'raw_source_title': 'numeric_range equality and hashing overflow for lengths above sys.maxsize',
  'raw_source_body': '### Problem\n'
                     '\n'
                     '`numeric_range` equality and hashing raise `OverflowError` when the number '
                     'of values exceeds `sys.maxsize`, although constructing the range and testing '
                     'its truth value work. The built-in `range` supports both operations on the '
                     'same arguments.\n'
                     '\n'
                     '```python\n'
                     'from more_itertools import numeric_range\n'
                     '\n'
                     'numeric_range(10**30) == numeric_range(10**30)\n'
                     "# OverflowError: cannot fit 'int' into an index-sized integer\n"
                     'hash(numeric_range(10**30))\n'
                     "# OverflowError: cannot fit 'int' into an index-sized integer\n"
                     '\n'
                     'range(10**30) == range(10**30)  # True\n'
                     'hash(range(10**30))             # succeeds\n'
                     '```\n'
                     '\n'
                     'Reproduced on current master (08dca28), CPython 3.13.9 on Windows. Both '
                     'methods call `len()`, which imposes the platform index-size limit; '
                     '`numeric_range._len` already holds the arbitrary-precision length. A small '
                     'fix can use `_len` internally while preserving the expected `OverflowError` '
                     'from an explicit `len(r)`.\n'
                     '\n'
                     'I have a patch with regression tests for ascending/descending ranges, '
                     'equivalent stops, unequal starts/steps/lengths, and dictionary-key lookup. I '
                     'will link the PR here.\n'
                     '\n'
                     '**AI assistance:** This was discovered through source review and '
                     'reproduced/tested by OpenAI Codex, at my request to find and fix bugs in '
                     'active open-source projects. It is not a claimed production incident or an '
                     'independently human-reviewed finding.\n'},
 {'id': 'item6v3_pr1311',
  'pr_number': 1311,
  'repo_slug': 'more-itertools/more-itertools',
  'title': 'fix: honour a falsey key in all_unique',
  'base_commit': '0fcdde9cce8bfdc3ba5e84711a990a32b74564a4',
  'merged_commit': 'c0ede7fcd50340170bc7f428b7b658f6e767a34c',
  'merged_at_utc': '2026-11-17T22:49:38Z',
  'total_changed_lines': 18,
  'has_tests': True,
  'needs_bwrap': True,
  'test_cmd': 'python3 -m unittest tests.test_more',
  'test_files': ['tests/test_more.py'],
  'grade_spec': {'mode': 'unittest',
                 'test_module': 'tests.test_more',
                 'cmd': 'python3 -m unittest tests.test_more',
                 'expected_test_count': 741},
  'files': ['docs/versions.rst', 'more_itertools/more.py', 'tests/test_more.py'],
  'source_kind': 'PR #1311',
  'raw_source_title': 'fix: honour a falsey key in all_unique',
  'raw_source_body': '### Issue reference\n'
                     'no issue, trivial bug. same fix as #1309, applied to `all_unique`.\n'
                     '\n'
                     '### Changes\n'
                     '`all_unique` applies the key with `map(key, iterable) if key else iterable`, '
                     'so a falsey callable (e.g. one whose `__bool__` returns false) is silently '
                     'ignored. it now checks `key is not None`, like the other `key` functions in '
                     '`more.py`.\n'
                     '\n'
                     '- regression test with a falsey key\n'
                     '- changelog entry under unreleased\n'
                     '\n'
                     '### Checks and tests\n'
                     '- new test fails without the fix (`True != False`) and passes with it\n'
                     '- `python -m unittest`: 934 tests ok\n'
                     '- `ruff format --check .` and `ruff check more_itertools tests`: clean\n'}]

PR_TASKS_V3 = []
for _spec in _RAW_V3_SPECS:
    _task = copy.deepcopy(_spec)
    _task["prompt"] = build_v3_task_prompt(
        _task["repo_slug"],
        _task["source_kind"],
        _task["raw_source_title"],
        _task["raw_source_body"],
    )
    PR_TASKS_V3.append(_task)


def load_tasks():
    """Return a deep copy of all 7 frozen v3 unseen PR tasks."""
    return copy.deepcopy(PR_TASKS_V3)


def get_task(task_id_or_number):
    """Find a v3 task by task ID (e.g. 'item6v3_pr1260') or PR number (e.g. 1260)."""
    for t in PR_TASKS_V3:
        if t["id"] == task_id_or_number or t["pr_number"] == task_id_or_number:
            return copy.deepcopy(t)
    raise KeyError(f"v3 task not found: {task_id_or_number}")


def strip_hidden(task):
    """Strip hidden fields (merged_commit, hidden_diff, test_files, grade_spec, raw source) before entering the model loop."""
    return tasks_item6.strip_hidden(task)


def get_hidden_diff(task, repo_root=None):
    """Retrieve ground truth diff between base_commit and merged_commit from the external bare repo for offline grading."""
    target_repo = repo_root or DEFAULT_V3_REPO_DIR
    return tasks_item6.get_hidden_diff(task, repo_root=target_repo)


if __name__ == "__main__":
    sel, exc = select_v3.enumerate_and_filter_v3_prs(verify_bwrap=True)
    sel_nums = [p["pr_number"] for p in sel]
    task_nums = [t["pr_number"] for t in PR_TASKS_V3]
    assert sel_nums == task_nums, f"Selected PRs {sel_nums} != PR_TASKS_V3 {task_nums}"
    for p, t in zip(sel, PR_TASKS_V3):
        assert p["base_commit"] == t["base_commit"], f"PR #{p['pr_number']} base mismatch"
        assert p["merged_commit"] == t["merged_commit"], f"PR #{p['pr_number']} merged mismatch"
        assert p["files"] == sorted(t["files"]), f"PR #{p['pr_number']} files mismatch"
        assert p["test_files"] == sorted(t["test_files"]), f"PR #{p['pr_number']} test_files mismatch"
        assert p["expected_test_count"] == t["grade_spec"]["expected_test_count"]
    print(f"OK: v3 mechanical PR selection verified ({len(sel)} selected: {sel_nums}; {len(exc)} excluded)")
