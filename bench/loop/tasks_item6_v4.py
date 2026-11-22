#!/usr/bin/env python3
"""Task definitions for Roadmap Item 6 Pilot v4: Unseen external-repo PR evaluation.

Frozen batch of 7 unseen merged PRs mechanically selected by `select_v4.py`:
  - Phase 1 (`more-itertools/more-itertools`, merged after 2026-11-17, excluding the
    7 frozen v3 development-set PRs): 0 qualifying PRs at pinned HEAD
    `e3f79f4fde5f7c107f70a20730b17240a05ba99b`.
  - Phase 2 (fixed priority shortlist of pure-Python, zero-dependency, stdlib-`unittest`
    repos stated before inspecting any candidate diff):
      1. `python-markdown/markdown` (HEAD `5609061bd3359e882b745de184ebfe5ef1c08011`): 0–1 verified (host-dependent via `/usr` bind-mount: 1 on this host with system `python3-markdown` 3.10.2, 0 without it; `< 7` either way)
      2. `pyparsing/pyparsing` (HEAD `810199f89bf916590426e1c5cb3d612584f11a2f`): 3 verified on this host (informational; `< 7`)
      3. `lark-parser/lark` (HEAD `9a4fb9c7458e8155636773a3cded0016d52516da`): 7 verified -> SELECTED

All 7 selected PRs were merged strictly after the Qwen3.6-35B-A3B Hugging Face release date
(`2026-04-15T05:59:19Z`, source: https://huggingface.co/Qwen/Qwen3.6-35B-A3B).

Rules enforced:
- Prompts are constructed deterministically by `build_v4_task_prompt` directly from:
    1. linked non-PR GitHub issue title and body (when linked: PRs #1601->#1598,
       #1619->#1618, #1613->#1500, #1632->#1630),
    2. linked PR title and body when the merge PR body is strictly a "Merges PR #M"
       wrapper (PR #1624->PR #1622),
    3. the PR's own title and body (PR #1543), or
    4. the verbatim git commit subject when GitHub returns 404 for the PR (PR #1641).
  All fenced code blocks are mechanically removed (`[code block removed]`), HTML comments
  stripped, and literal 104729 redacted; zero hand-written prose and zero inspection of
  merged diffs.
- Hidden tests, reference solutions, and literal grading seed 104729 never appear in this
  file or in any in-loop prompt.
- Offline bwrap verification confirms every task's merged-commit tests PASS at
  `merged_commit` and FAIL at `base_commit` with no network and stdlib only.
"""
import copy
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import select_v4  # noqa: E402
import tasks_item6  # noqa: E402
import tasks_item6_v3  # noqa: E402

DEFAULT_V4_REPOS_DIR = select_v4.DEFAULT_V4_REPOS_DIR
V4_PRIMARY_REPO_SLUG = select_v4.V4_PRIMARY_SPEC["slug"]
V4_PRIMARY_HEAD_COMMIT = select_v4.V4_PRIMARY_SPEC["pinned_head"]
V4_SELECTED_REPO_SLUG = "lark-parser/lark"
V4_SELECTED_REPO_NAME = "lark"
V4_SELECTED_REPO_URL = "https://github.com/lark-parser/lark.git"
V4_SELECTED_HEAD_COMMIT = "9a4fb9c7458e8155636773a3cded0016d52516da"
QWEN36_RELEASE_UTC = select_v4.QWEN36_RELEASE_UTC
QWEN36_RELEASE_SOURCE = select_v4.QWEN36_RELEASE_SOURCE


def strip_code_blocks_and_clean(text):
    """Mechanically remove HTML comments and fenced code blocks, and redact literal 104729."""
    return tasks_item6_v3.strip_code_blocks_and_clean(text)


def build_v4_task_prompt(repo_slug, source_kind, raw_source_title, raw_source_body):
    """Build a v4 task prompt strictly by rule from verbatim issue, PR, or commit metadata."""
    title = strip_code_blocks_and_clean(raw_source_title)
    body = strip_code_blocks_and_clean(raw_source_body)
    if body:
        return f"Repo {repo_slug} — {source_kind}: {title}\n\n{body}"
    return f"Repo {repo_slug} — {source_kind}: {title}"


_RAW_V4_SPECS = [
    {
        "id": "item6v4_pr1543",
        "pr_number": 1543,
        "repo_slug": "lark-parser/lark",
        "repo_name": "lark",
        "title": "Miscellaneous improvements to the behavior and documentation of Visitor, Transformer, Interpreter, and friends",
        "base_commit": "1573ca82a7b4af3a81919245e31a84a68b40f5b7",
        "merged_commit": "3421420fb9544f8acd2b3d68db730413dc42274b",
        "merged_at_utc": "2026-05-02T19:50:46Z",
        "total_changed_lines": 80,
        "has_tests": True,
        "needs_bwrap": True,
        "test_cmd": "python3 -m unittest tests.test_trees",
        "test_files": ["tests/test_trees.py"],
        "grade_spec": {
            "mode": "unittest",
            "test_module": "tests.test_trees",
            "cmd": "python3 -m unittest tests.test_trees",
            "expected_test_count": 22,
        },
        "files": ["docs/visitors.rst", "lark/visitors.py", "tests/test_trees.py"],
        "source_kind": "PR #1543",
        "raw_source_title": "Miscellaneous improvements to the behavior and documentation of Visitor, Transformer, Interpreter, and friends",
        "raw_source_body": (
            "This PR makes the following improvements.\r\n\r\n"
            "Documentation:\r\n"
            "- Add docstrings for `visit_children_decor` and various methods of `Interpreter`.\r\n"
            "- Correct the top-level docs for `Visitor` to clarify that it can traverse the tree in either direction.\r\n"
            "- Move utilities into their own section and add documentation for `visit_children_decor`, which was previously not visible.\r\n\r\n"
            "Behavior:\r\n"
            "- Have `visit_children_decor` raise a `TypeError` if applied to a method of any class other than `Interpreter`."
        ),
    },
    {
        "id": "item6v4_pr1601",
        "pr_number": 1601,
        "repo_slug": "lark-parser/lark",
        "repo_name": "lark",
        "title": "Fix empty SPPF node from xearley ignore carry-over (fixes #1598)",
        "base_commit": "71ab62450cbb6f48d91a73b7e385aca5d4f6994f",
        "merged_commit": "5718472e57a08aac3728c2f26f902de56c48d64c",
        "merged_at_utc": "2026-06-03T07:20:38Z",
        "total_changed_lines": 21,
        "has_tests": True,
        "needs_bwrap": True,
        "test_cmd": "python3 -m unittest tests.test_parser",
        "test_files": ["tests/test_parser.py"],
        "grade_spec": {
            "mode": "unittest",
            "test_module": "tests.test_parser",
            "cmd": "python3 -m unittest tests.test_parser",
            "expected_test_count": 1146,
        },
        "files": ["lark/parsers/xearley.py", "tests/test_parser.py"],
        "source_kind": "Issue #1598 (PR #1601)",
        "raw_source_title": "Bug: RuntimeError: Earley should not generate multiple start symbol items! Please report this bug.",
        "raw_source_body": (
            "**Describe the bug**\n\n"
            "Upon trying to test my toy language, I was given the error \"RuntimeError: Earley should not generate multiple start symbol items! Please report this bug.\"\n\n"
            "**To Reproduce**\n"
            "\"orca.lark\"\n"
            "```lark\n"
            "start: (declaration _NL)+ declaration?\n\n"
            "?declaration: function\n\n"
            "function: \"func\" NAME arg_list [\"->\" type] block\n\n"
            "arg_list: \"(\" _commasep{arg}? \")\"\n"
            "arg: NAME [\":\" type]\n\n"
            "block: \"{\" (statement _NL)* statement? \"}\"\n\n"
            "?statement: expr\n"
            "          | assign\n"
            "          | block\n"
            "          | if\n"
            "          | for\n"
            "          | while\n\n"
            "assign: \"let\" NAME \"=\" conditional_expr -> let\n"
            "      | \"const\" NAME \"=\" conditional_expr -> const\n\n"
            "if: \"if\" expr block _NL? elseif* else?\n"
            "elseif: \"else\" \"if\" expr block _NL?\n"
            "else: \"else\" block\n\n"
            "for: \"for\" [expr] \";\" [expr] \";\" [expr] block\n\n"
            "while: \"while\" expr block\n\n\n"
            "// operator precedence stuff\n"
            "?assignable: NAME\n"
            "           | call_expr \".\" (NAME | INT)\n\n"
            "INC: \"++\"\n"
            "DEC: \"--\"\n\n"
            "?atom: assignable\n"
            "     | DEC assignable -> pre_dec_expr\n"
            "     | assignable DEC -> post_dec_expr\n"
            "     | INT\n"
            "     | FLOAT\n"
            "     | \"(\" expr \")\"\n"
            "     | \"func\" arg_list [\"->\" type] block _NL? -> lambda_expr\n\n"
            "?call_expr: atom\n"
            "          | call_expr \"(\" _commasep{expr}? \")\"\n\n"
            "?pow_expr: call_expr\n"
            "         | call_expr \"**\" pow_expr\n\n"
            "?unary_expr: pow_expr\n"
            "           | \"-\" pow_expr -> neg_expr\n"
            "           | \"!\" pow_expr -> not_expr\n\n"
            "?mult_expr: unary_expr\n"
            "          | mult_expr \"*\" unary_expr\n"
            "          | mult_expr \"/\" unary_expr -> div_expr\n"
            "          | mult_expr \"%\" unary_expr -> mod_expr\n\n"
            "?add_expr: mult_expr\n"
            "         | add_expr \"+\" mult_expr\n"
            "         | add_expr \"-\" mult_expr -> sub_expr\n\n"
            "?shift_expr: add_expr\n"
            "           | shift_expr \"<<\" add_expr -> leftshift_expr\n"
            "           | shift_expr \">>\" add_expr -> rightshift_expr\n\n"
            "?bit_and_expr: shift_expr\n"
            "             | bit_and_expr \"&\" shift_expr\n\n"
            "?bit_xor_expr: bit_and_expr\n"
            "             | bit_xor_expr \"^\" bit_and_expr\n\n"
            "?bit_or_expr: bit_xor_expr\n"
            "            | bit_or_expr \"|\" bit_xor_expr\n\n"
            "?comp_expr: _separated{bit_or_expr, COMP_OP}\n"
            "COMP_OP: \"==\" | \"!=\" | \">\" | \"<\" | \">=\" | \"<=\"\n\n"
            "?logical_and_expr: comp_expr\n"
            "                 | logical_and_expr \"&&\" comp_expr\n\n"
            "?logical_or_expr: logical_and_expr\n"
            "                | logical_or_expr \"||\" logical_and_expr\n\n"
            "?conditional_expr: logical_or_expr\n"
            "                 | logical_or_expr \"?\" conditional_expr \":\" conditional_expr\n\n"
            "?expr: conditional_expr\n"
            "     | assignable ASSIGN_OP expr -> assign_expr\n\n"
            "ASSIGN_OP: [\"**\"\n"
            "          | \"*\" | \"/\" | \"%\"\n"
            "          | \"+\" | \"-\"\n"
            "          | \"<<\" | \">>\"\n"
            "          | \"&\" | \"^\" | \"|\"\n"
            "          | \"&&\" | \"||\"] \"=\"\n\n"
            "fqn: NAME (\".\" (NAME|INT))*\n"
            "type: fqn\n\n"
            "_separated{x, sep}: x (sep x)*\n"
            "_commasep{x}: x (\",\" x)* \",\"?\n\n"
            "_NL.1: (/\\r?\\n/ WS_INLINE*)+\n\n"
            "// a name is a letter, followed by 0 or more letters or numbers,\n"
            "// but not any keyword\n"
            "NAME: /\\b(?!(func|if|else|for|while|let|const)\\b)[a-zA-Z][a-zA-Z0-9]*\\b/\n\n"
            "%import common (INT, WS_INLINE, FLOAT)\n\n"
            "%import common (WS, C_COMMENT, CPP_COMMENT)\n"
            "%ignore WS\n"
            "%ignore C_COMMENT\n"
            "%ignore CPP_COMMENT\n"
            "```\n"
            "\"main.py\"\n"
            "```python\n"
            "import logging\n\n"
            "from lark import Lark, logger\n\n"
            "logger.setLevel(logging.DEBUG)\n\n\n"
            "orca_parser = Lark.open(\n"
            "    \"orca.lark\",\n"
            "    rel_to=__file__,\n"
            "    debug=True,\n"
            "    #parser=\"lalr\",\n"
            "    #lexer=\"contextual\",\n"
            ")\n\n"
            "with open(\"t.orca\") as f:\n"
            "    print(orca_parser.parse(f.read()).pretty())\n"
            "```\n"
            "\"t.orca\"\n"
            "```orca\n\n"
            "func f(functy: t.x.0) {\n"
            "    t(func (a, b) -> t {}\n"
            "    )\n"
            "    // one comment\n"
            "    while a {\n"
            "        /* another comment */\n"
            "        let x = d\n"
            "        const y = b\n"
            "    }\n\n\n"
            "    if 0.3e8 {}\n"
            "    else if 14 {}\n"
            "    else {\n"
            "        for a; 0; 8.2 {}\n"
            "    }\n"
            "    if a {\n"
            "        y\n"
            "    } else if b {\n"
            "        z\n"
            "    } else {\n\n\n"
            "    }\n"
            "    if elsey {}}\n\n"
            "func other() -> c {}\n\n"
            "func c() {\n"
            "    c.3.x = 4\n"
            "}\n"
            "```\n"
            "\"pyproject.toml\"\n"
            "```toml\n"
            "[project]\n"
            "name = \"orca\"\n"
            "version = \"0.1.0\"\n"
            "description = \"Add your description here\"\n"
            "readme = \"README.md\"\n"
            "requires-python = \">=3.13\"\n"
            "dependencies = [\n"
            "    \"lark[interegular,interregular]>=1.3.1\",\n"
            "]\n\n"
            "[dependency-groups]\n"
            "dev = [\n"
            "    \"python-lsp-ruff>=2.3.1\",\n"
            "]\n"
            "```\n\n"
            "Output\n"
            "```\n"
            "Unused terminals: [Token('TERMINAL', 'WS_INLINE'), 'INC']\n"
            "Traceback (most recent call last):\n"
            "  File \"/home/finally/orca/main.py\", line 17, in <module>\n"
            "    print(orca_parser.parse(f.read()).pretty())\n"
            "          ~~~~~~~~~~~~~~~~~^^^^^^^^^^\n"
            "  File \"/home/finally/orca/.venv/lib/python3.13/site-packages/lark/lark.py\", line 677, in parse\n"
            "    return self.parser.parse(text, start=start, on_error=on_error)\n"
            "           ~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n"
            "  File \"/home/finally/orca/.venv/lib/python3.13/site-packages/lark/parser_frontends.py\", line 131, in parse\n"
            "    return self.parser.parse(stream, chosen_start, **kw)\n"
            "           ~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n"
            "  File \"/home/finally/orca/.venv/lib/python3.13/site-packages/lark/parsers/earley.py\", line 290, in parse\n"
            "    raise RuntimeError('Earley should not generate multiple start symbol items! Please report this bug.')\n"
            "RuntimeError: Earley should not generate multiple start symbol items! Please report this bug.\n"
            "```"
        ),
    },
    {
        "id": "item6v4_pr1619",
        "pr_number": 1619,
        "repo_slug": "lark-parser/lark",
        "repo_name": "lark",
        "title": "Fix lexer_callbacks silently dropped for keyword terminals (#1618)",
        "base_commit": "5892df12bd6badd3ee555db3b2ae54a4e5911147",
        "merged_commit": "332acf8982f1320a0b29a7c074e0da29a6d32b98",
        "merged_at_utc": "2026-07-19T07:41:12Z",
        "total_changed_lines": 28,
        "has_tests": True,
        "needs_bwrap": True,
        "test_cmd": "python3 -m unittest tests.test_grammar",
        "test_files": ["tests/test_grammar.py"],
        "grade_spec": {
            "mode": "unittest",
            "test_module": "tests.test_grammar",
            "cmd": "python3 -m unittest tests.test_grammar",
            "expected_test_count": 27,
        },
        "files": ["lark/lexer.py", "tests/test_grammar.py"],
        "source_kind": "Issue #1618 (PR #1619)",
        "raw_source_title": "Bug in lexer_callbacks, causing some callbacks to be skipped in some grammars",
        "raw_source_body": (
            "## Bug description\n\n"
            "When two or more terminals each have both an `UnlessCallback` (they absorb a\n"
            "same-priority keyword literal) **and** a `lexer_callbacks` entry, every user\n"
            "callback except the last one silently never fires. The tokens themselves lex\n"
            "correctly, so nothing surfaces the drop.\n\n\n"
            "## Reproduce \n"
            "```python\n"
            "from lark import Lark\n\n"
            "fired = []\n"
            "p = Lark(r'''\n"
            "    start: (A | B | AKW | BKW)+\n"
            "    A: /[a-z]+/\n"
            "    B: /[0-9]+/\n"
            "    AKW: \"foo\"\n"
            "    BKW: \"123\"\n"
            "    %ignore \" \"\n"
            "''', parser='lalr', lexer='basic',\n"
            "    lexer_callbacks={'A': lambda t: fired.append('A') or t,\n"
            "                     'B': lambda t: fired.append('B') or t})\n\n"
            "list(p.lex(\"bar 456\"))\n"
            "print(fired)   # actual: ['B']  — expected: ['A', 'B']\n"
            "```\n\n"
            "`\"bar\"` lexes as `A` and is never re-typed, yet the `A` callback doesn't run.\n\n"
            "## Cause\n\n"
            "`_build_scanner` creates each `CallChain` gate inside the loop over\n"
            "`user_callbacks`:\n\n"
            "```python\n"
            "self.callback[type_] = CallChain(self.callback[type_], f,\n"
            "                                 lambda t: t.type == type_)\n"
            "```\n\n"
            "The lambda closes over the loop **variable** `type_` and only reads it when\n"
            "called — during lexing, after the loop has finished — so every gate compares\n"
            "against the *last* terminal's name. In the example above, `A`'s gate asks\n"
            "`t.type == \"B\"`.\n\n"
            "Fix can be a simple one-line. I will create a PR soon, but meanwhile, this issue documents it."
        ),
    },
    {
        "id": "item6v4_pr1613",
        "pr_number": 1613,
        "repo_slug": "lark-parser/lark",
        "repo_name": "lark",
        "title": "Add template support to Reconstructor",
        "base_commit": "51272c044e76f729238f5a93ee0337eac2f07396",
        "merged_commit": "f17d08d06e16e91745da3df15bee6c62b021ce2b",
        "merged_at_utc": "2026-08-25T11:32:09Z",
        "total_changed_lines": 30,
        "has_tests": True,
        "needs_bwrap": True,
        "test_cmd": "python3 -m unittest tests.test_reconstructor",
        "test_files": ["tests/test_reconstructor.py"],
        "grade_spec": {
            "mode": "unittest",
            "test_module": "tests.test_reconstructor",
            "cmd": "python3 -m unittest tests.test_reconstructor",
            "expected_test_count": 9,
        },
        "files": ["lark/reconstruct.py", "tests/test_reconstructor.py"],
        "source_kind": "Issue #1500 (PR #1613)",
        "raw_source_title": "Python reconstructor list comprehension error",
        "raw_source_body": (
            "**Describe the bug**\r\n\r\n"
            "Using the official Lark Python parser and using the PythonReconstructor from the [examples](https://lark-parser.readthedocs.io/en/latest/examples/advanced/reconstruct_python.html), list comprehension produces `AssertionError` when the code is valid Python code.\r\n\r\n"
            "E.g. The inputs `\"[a for a in range(10)]\"` produces the error\r\n"
            "```\r\n"
            "AssertionError: (NonTerminal('comprehension{test_or_star_expr}'), Tree(Token('RULE', 'comprehension'), [Tree('var', [Tree(Token('RULE', 'name'), [Token('NAME', 'a')])]), Tree('comp_fors'), [Tree(Token('RULE', 'comp_for'), [Tree('var', [Tree(Token('RULE', 'name'), [Token('NAME', 'a')])]), Tree('funccall', [Tree('var', [Tree(Token('RULE', 'name'), [Token('NAME', 'range')])]), Tree(Token('RULE', 'arguments'), [Tree(Token('RULE', 'number'), [Token('DEC_NUMBER', '10')])])])])])]))\r\n"
            "```\r\n\r\n"
            "**To Reproduce**\r\n\r\n"
            "The reproduction test script is the code from [the example](https://lark-parser.readthedocs.io/en/latest/examples/advanced/reconstruct_python.html) but given the input `\"[a for a in range(10)]\"`\r\n\r\n"
            "This is the full script:\r\n"
            "```\r\n"
            "from lark import Token, Lark\r\n"
            "from lark.reconstruct import Reconstructor\r\n"
            "from lark.indenter import PythonIndenter\r\n\r\n"
            "# Official Python grammar by Lark\r\n"
            "python_parser3 = Lark.open_from_package(\r\n"
            "    \"lark\",\r\n"
            "    \"python.lark\",\r\n"
            "    [\"grammars\"],\r\n"
            "    parser=\"lalr\",\r\n"
            "    postlex=PythonIndenter(),\r\n"
            "    start=\"file_input\",\r\n"
            "    maybe_placeholders=False,  # Necessary for reconstructor\r\n"
            ")\r\n\r\n"
            "SPACE_AFTER = set(',+-*/~@<>=\"|:')\r\n"
            "SPACE_BEFORE = (SPACE_AFTER - set(\",:\")) | set(\"'\")\r\n\r\n\r\n"
            "def special(sym):\r\n"
            "    return Token(\"SPECIAL\", sym.name)\r\n\r\n\r\n"
            "def postproc(items):\r\n"
            "    stack = [\"\\n\"]\r\n"
            "    actions = []\r\n"
            "    last_was_whitespace = True\r\n"
            "    for item in items:\r\n"
            "        if isinstance(item, Token) and item.type == \"SPECIAL\":\r\n"
            "            actions.append(item.value)\r\n"
            "        else:\r\n"
            "            if actions:\r\n"
            "                assert actions[0] == \"_NEWLINE\" and \"_NEWLINE\" not in actions[1:], actions\r\n\r\n"
            "                for a in actions[1:]:\r\n"
            "                    if a == \"_INDENT\":\r\n"
            "                        stack.append(stack[-1] + \" \" * 4)\r\n"
            "                    else:\r\n"
            "                        assert a == \"_DEDENT\"\r\n"
            "                        stack.pop()\r\n"
            "                actions.clear()\r\n"
            "                yield stack[-1]\r\n"
            "                last_was_whitespace = True\r\n"
            "            if not last_was_whitespace:\r\n"
            "                if item[0] in SPACE_BEFORE:\r\n"
            "                    yield \" \"\r\n"
            "            yield item\r\n"
            "            last_was_whitespace = item[-1].isspace()\r\n"
            "            if not last_was_whitespace:\r\n"
            "                if item[-1] in SPACE_AFTER:\r\n"
            "                    yield \" \"\r\n"
            "                    last_was_whitespace = True\r\n"
            "    yield \"\\n\"\r\n\r\n\r\n"
            "class PythonReconstructor:\r\n"
            "    def __init__(self, parser):\r\n"
            "        self._recons = Reconstructor(parser, {\"_NEWLINE\": special, \"_DEDENT\": special, \"_INDENT\": special})\r\n\r\n"
            "    def reconstruct(self, tree):\r\n"
            "        return self._recons.reconstruct(tree, postproc)\r\n\r\n\r\n"
            "python_reconstructor = PythonReconstructor(python_parser3)\r\n\r\n"
            "self_contents = \"[a for a in range(10)]\"\r\n\r\n"
            "tree = python_parser3.parse(self_contents + \"\\n\")\r\n"
            "output = python_reconstructor.reconstruct(tree)\r\n\r\n"
            "tree_new = python_parser3.parse(output)\r\n"
            "print(tree.pretty())\r\n"
            "print(tree_new.pretty())\r\n"
            "# assert tree.pretty() == tree_new.pretty()\r\n"
            "assert tree == tree_new\r\n"
            "```\r\n\r\n"
            "Running the script produces the described error. Here's the full trace:\r\n"
            "```\r\n"
            "Traceback (most recent call last):\r\n"
            "  File \"/Users/ellieyhc/Documents/test/venv/lib/python3.12/site-packages/lark/visitors.py\", line 115, in _call_userfunc\r\n"
            "    f = getattr(self, tree.data)\r\n"
            "        ^^^^^^^^^^^^^^^^^^^^^^^^\r\n"
            "AttributeError: 'WriteTokensTransformer' object has no attribute 'list_comprehension'\r\n\r\n"
            "During handling of the above exception, another exception occurred:\r\n\r\n"
            "Traceback (most recent call last):\r\n"
            "  File \"/Users/ellieyhc/Documents/test/test.py\", line 69, in <module>\r\n"
            "    output = python_reconstructor.reconstruct(tree)\r\n"
            "             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\r\n"
            "  File \"/Users/ellieyhc/Documents/test/test.py\", line 61, in reconstruct\r\n"
            "    return self._recons.reconstruct(tree, postproc)\r\n"
            "           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\r\n"
            "  File \"/Users/ellieyhc/Documents/test/venv/lib/python3.12/site-packages/lark/reconstruct.py\", line 102, in reconstruct\r\n"
            "    for item in x:\r\n"
            "                ^\r\n"
            "  File \"/Users/ellieyhc/Documents/test/test.py\", line 28, in postproc\r\n"
            "    for item in items:\r\n"
            "                ^^^^^\r\n"
            "  File \"/Users/ellieyhc/Documents/test/venv/lib/python3.12/site-packages/lark/reconstruct.py\", line 92, in _reconstruct\r\n"
            "    yield from self._reconstruct(item)\r\n"
            "  File \"/Users/ellieyhc/Documents/test/venv/lib/python3.12/site-packages/lark/reconstruct.py\", line 92, in _reconstruct\r\n"
            "    yield from self._reconstruct(item)\r\n"
            "  File \"/Users/ellieyhc/Documents/test/venv/lib/python3.12/site-packages/lark/reconstruct.py\", line 88, in _reconstruct\r\n"
            "    res = self.write_tokens.transform(unreduced_tree)\r\n"
            "          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\r\n"
            "  File \"/Users/ellieyhc/Documents/test/venv/lib/python3.12/site-packages/lark/visitors.py\", line 286, in transform\r\n"
            "    return self._transform_tree(tree)\r\n"
            "           ^^^^^^^^^^^^^^^^^^^^^^^^^^\r\n"
            "  File \"/Users/ellieyhc/Documents/test/venv/lib/python3.12/site-packages/lark/visitors.py\", line 280, in _transform_tree\r\n"
            "    return self._call_userfunc(tree)\r\n"
            "           ^^^^^^^^^^^^^^^^^^^^^^^^^\r\n"
            "  File \"/Users/ellieyhc/Documents/test/venv/lib/python3.12/site-packages/lark/visitors.py\", line 117, in _call_userfunc\r\n"
            "    return self.__default__(tree.data, children, tree.meta)\r\n"
            "           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\r\n"
            "  File \"/Users/ellieyhc/Documents/test/venv/lib/python3.12/site-packages/lark/reconstruct.py\", line 58, in __default__\r\n"
            "    assert NonTerminal(x.data) == sym, (sym, x)\r\n"
            "           ^^^^^^^^^^^^^^^^^^^^^^^^^^\r\n"
            "AssertionError: (NonTerminal('comprehension{test_or_star_expr}'), Tree(Token('RULE', 'comprehension'), [Tree('var', [Tree(Token('RULE', 'name'), [Token('NAME', 'a')])]), Tree('comp_fors'), [Tree(Token('RULE', 'comp_for'), [Tree('var', [Tree(Token('RULE', 'name'), [Token('NAME', 'a')])]), Tree('funccall', [Tree('var', [Tree(Token('RULE', 'name'), [Token('NAME', 'range')])]), Tree(Token('RULE', 'arguments'), [Tree(Token('RULE', 'number'), [Token('DEC_NUMBER', '10')])])])])])]))\r\n"
            "```\r\n"
        ),
    },
    {
        "id": "item6v4_pr1624",
        "pr_number": 1624,
        "repo_slug": "lark-parser/lark",
        "repo_name": "lark",
        "title": "Merge PR 1622 - fix small collision with previous PR",
        "base_commit": "e1817787d2ed2a10477734b1f784cbc7eee8dfa4",
        "merged_commit": "b2e462182eb194d4425e4e2ac5f1c169ea8c94de",
        "merged_at_utc": "2026-08-25T13:21:10Z",
        "total_changed_lines": 33,
        "has_tests": True,
        "needs_bwrap": True,
        "test_cmd": "python3 -m unittest tests.test_trees",
        "test_files": ["tests/test_trees.py"],
        "grade_spec": {
            "mode": "unittest",
            "test_module": "tests.test_trees",
            "cmd": "python3 -m unittest tests.test_trees",
            "expected_test_count": 25,
        },
        "files": ["lark/visitors.py", "tests/test_trees.py"],
        "source_kind": "PR #1622 (merged via PR #1624)",
        "raw_source_title": "Fix Transformer_NonRecursive corrupting the tree on a non-last Discard",
        "raw_source_body": (
            "### Problem\n\n"
            "`Transformer_NonRecursive` corrupts the tree when a callback returns `Discard` for a node that is **not** the last child processed. It slices its internal stack by `len(x.children)`, but discarded children were never pushed onto that stack, so the slice over-consumes and pulls an unrelated sibling into the wrong parent:\n\n"
            "```python\n"
            "from lark import Tree, Token\n"
            "from lark.visitors import Transformer, Transformer_NonRecursive, Discard\n\n"
            "class Drop:\n"
            "    def drop(self, children): return Discard\n\n"
            "tree = Tree('start', [Tree('keep', [Token('T', 'x')]), Tree('wrap', [Tree('drop', [])])])\n\n"
            "class TBase(Drop, Transformer): pass\n"
            "class TNR(Drop, Transformer_NonRecursive): pass\n\n"
            "TBase().transform(tree)   # Tree('start', [Tree('keep', [Token('T','x')]), Tree('wrap', [])])   (correct)\n"
            "TNR().transform(tree)     # Tree('start', [Tree('wrap', [Tree('keep', [Token('T','x')])])])       (WRONG)\n"
            "```\n\n"
            "`keep` is silently dropped from `start` and re-parented under `wrap`. `Transformer_NonRecursive` is documented as *\"Same as Transformer\"*, and the base `Transformer` (unaffected) is the correct twin. A differential run of 3000 random trees using `Discard` gave 307 mismatches vs the base `Transformer` before this change, 0 after.\n\n"
            "### Cause\n\n"
            "In `Transformer_NonRecursive.transform`, `size = len(x.children)` counts all original children, but a child whose callback returned `Discard` was never pushed (`if res is not Discard: stack.append(res)`), so `stack[-size:]` reaches into earlier siblings.\n\n"
            "### Fix\n\n"
            "Push discarded results as placeholders so every node consumes exactly `len(children)` slots, and filter the placeholders when building a parent's args. A wholly-discarded tree now returns `None` instead of mis-unpacking an empty stack.\n\n"
            "Existing tests pass (`test_transformer_variants` only exercised `Discard` on a *last* child, which masked this); added `test_transformer_variants_discard_with_preceding_sibling` covering all four transformer variants. `mypy` clean.\n\n"
            "### Note on #1614\n\n"
            "As a side effect of the stack-alignment fix, a fully-discarded root now returns `None` — the same case #1614 targets for the crash. The interior-sibling corruption fixed here is distinct (it survives #1614's `if not stack` guard), but there is overlap on the root case; happy to rebase around #1614 or adjust if you'd prefer to keep them separate.\n\n"
            "---\n\n"
            "*Disclosure: authored by an AI coding agent (Claude Code) running on this account — it found the bug, wrote the repro/fuzz, the fix and this description. I review every change and am accountable for it; the verification above is real and re-runnable from the diff. If this isn't a change you want, say so and I'll close it.*\n"
        ),
    },
    {
        "id": "item6v4_pr1632",
        "pr_number": 1632,
        "repo_slug": "lark-parser/lark",
        "repo_name": "lark",
        "title": "Fix Template.search() dropping zero-variable matches",
        "base_commit": "bb11b5398b9a96865ff7c57e04739410273434df",
        "merged_commit": "e7c2564859ba865618d81db1a5aa0b9a3ce5ec8e",
        "merged_at_utc": "2026-08-26T19:56:53Z",
        "total_changed_lines": 30,
        "has_tests": True,
        "needs_bwrap": True,
        "test_cmd": "python3 -m unittest tests.test_tree_templates",
        "test_files": ["tests/test_tree_templates.py"],
        "grade_spec": {
            "mode": "unittest",
            "test_module": "tests.test_tree_templates",
            "cmd": "python3 -m unittest tests.test_tree_templates",
            "expected_test_count": 21,
        },
        "files": ["lark/tree_templates.py", "tests/test_tree_templates.py"],
        "source_kind": "Issue #1630 (PR #1632)",
        "raw_source_title": "Fix Template.search() to yield zero-variable matches",
        "raw_source_body": (
            "Fix Template.search() in lark/tree_templates.py so it correctly yields matches when the template contains no template variables. Today, Template.match() returns an empty dict when a pattern with no variable placeholders successfully matches a subtree, which is the correct sentinel for \"match found, nothing to bind\". But search() checks the result with a plain truthiness test, and an empty dict is falsy in Python, so every zero-variable match is silently dropped. As a result, search() always returns an empty iterator when the template has no variables, and translate() never replaces anything in that case, even when the source pattern appears in the tree. The fix must distinguish between None (no match) and {} (match with no variable bindings), which is already the contract that match() documents and tests confirm.\n\n"
            "Two existing tests in tests/test_tree_templates.py were written to match the broken behavior and assert an empty result for zero-variable templates; they must be corrected to assert the match that the fixed implementation correctly yields."
        ),
    },
    {
        "id": "item6v4_pr1641",
        "pr_number": 1641,
        "repo_slug": "lark-parser/lark",
        "repo_name": "lark",
        "title": "Fix InteractiveParser.copy() sharing the lexer thread with the original (#1641)",
        "base_commit": "e7c2564859ba865618d81db1a5aa0b9a3ce5ec8e",
        "merged_commit": "b974caecc8fcffa014afa22ee15b1fdb4a24e489",
        "merged_at_utc": "2026-08-27T11:07:40Z",
        "total_changed_lines": 29,
        "has_tests": True,
        "needs_bwrap": True,
        "test_cmd": "python3 -m unittest tests.test_parser",
        "test_files": ["tests/test_parser.py"],
        "grade_spec": {
            "mode": "unittest",
            "test_module": "tests.test_parser",
            "cmd": "python3 -m unittest tests.test_parser",
            "expected_test_count": 1166,
        },
        "files": [
            "lark/parsers/lalr_interactive_parser.py",
            "lark/parsers/lalr_parser_state.py",
            "tests/test_parser.py",
        ],
        "source_kind": "Commit subject (PR #1641; GitHub PR/issue 404)",
        "raw_source_title": "Fix InteractiveParser.copy() sharing the lexer thread with the original (#1641)",
        "raw_source_body": "",
    },
]

PR_TASKS_V4 = []
for _spec in _RAW_V4_SPECS:
    _task = copy.deepcopy(_spec)
    _task["prompt"] = build_v4_task_prompt(
        _task["repo_slug"],
        _task["source_kind"],
        _task["raw_source_title"],
        _task["raw_source_body"],
    )
    PR_TASKS_V4.append(_task)


def load_tasks():
    """Return a deep copy of all 7 frozen v4 unseen PR tasks."""
    return copy.deepcopy(PR_TASKS_V4)


def get_task(task_id_or_number):
    """Find a v4 task by task ID (e.g. 'item6v4_pr1543') or PR number (e.g. 1543)."""
    for t in PR_TASKS_V4:
        if t["id"] == task_id_or_number or t["pr_number"] == task_id_or_number:
            return copy.deepcopy(t)
    raise KeyError(f"v4 task not found: {task_id_or_number}")


def strip_hidden(task):
    """Strip hidden fields before entering the model loop."""
    return tasks_item6.strip_hidden(task)


def get_hidden_diff(task, repo_root=None):
    """Retrieve ground truth diff between base_commit and merged_commit from the bare repo for offline grading."""
    base_dir = repo_root or DEFAULT_V4_REPOS_DIR
    if os.path.isdir(base_dir) and task.get("repo_name"):
        cand = os.path.join(base_dir, f"{task['repo_name']}.git")
        if os.path.isdir(cand):
            base_dir = cand
    return tasks_item6.get_hidden_diff(task, repo_root=base_dir)


if __name__ == "__main__":
    res = select_v4.select_v4_batch(repos_dir=DEFAULT_V4_REPOS_DIR, verify_bwrap=True)
    sel = res["selected"]
    sel_nums = [p["pr_number"] for p in sel]
    task_nums = [t["pr_number"] for t in PR_TASKS_V4]
    assert res["shortfall"] == 0, f"Unexpected shortfall: {res['shortfall']}"
    assert sel_nums == task_nums, f"Selected PRs {sel_nums} != PR_TASKS_V4 {task_nums}"
    for p, t in zip(sel, PR_TASKS_V4):
        assert p["repo_slug"] == t["repo_slug"], f"PR #{p['pr_number']} repo mismatch"
        assert p["base_commit"] == t["base_commit"], f"PR #{p['pr_number']} base mismatch"
        assert p["merged_commit"] == t["merged_commit"], f"PR #{p['pr_number']} merged mismatch"
        assert p["files"] == sorted(t["files"]), f"PR #{p['pr_number']} files mismatch"
        assert p["test_files"] == sorted(t["test_files"]), f"PR #{p['pr_number']} test_files mismatch"
        assert p["expected_test_count"] == t["grade_spec"]["expected_test_count"]
    print(f"OK: v4 mechanical PR selection verified ({len(sel)} selected from {res['fallback_repo_slug']}: {sel_nums})")
