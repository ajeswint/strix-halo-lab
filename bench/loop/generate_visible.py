import os, sys, re, ast

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import tasks_v10
import run

def split_top_level(s, sep=','):
    parts = []
    cur = []
    depth = 0
    in_quote = None
    escape = False
    for ch in s:
        if escape:
            cur.append(ch); escape = False; continue
        if ch == '\\':
            cur.append(ch); escape = True; continue
        if in_quote:
            cur.append(ch)
            if ch == in_quote: in_quote = None
            continue
        if ch in ('"', "'"):
            in_quote = ch
            cur.append(ch)
            continue
        if ch in '([{':
            depth += 1
            cur.append(ch)
        elif ch in ')]}':
            depth -= 1
            cur.append(ch)
        elif ch == sep and depth == 0:
            parts.append(''.join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    if cur:
        parts.append(''.join(cur).strip())
    return [p for p in parts if p]

def strip_trailing_comment(s):
    s = s.strip()
    parts = split_top_level(s, sep='#')
    s = parts[0].strip()
    if " - " in s:
        s = s.split(" - ", 1)[0].strip()
    if s.endswith(')'):
        depth = 0
        start = None
        for i in range(len(s) - 1, -1, -1):
            if s[i] == ')':
                depth += 1
            elif s[i] == '(':
                depth -= 1
                if depth == 0:
                    start = i
                    break
        if start is not None and start > 0 and s[start - 1].isspace():
            cand = s[:start].strip()
            try:
                ast.parse(cand)
                s = cand
            except SyntaxError:
                pass
    return s

def extract_from_prompt(prompt):
    idx = prompt.find("Examples:")
    if idx == -1:
        idx = prompt.find("Example:")
    if idx == -1:
        return []
    block = prompt[idx:]
    lines = block.splitlines()
    bullets = []
    cur = []
    for line in lines[1:]:
        if line.startswith("- "):
            if cur:
                bullets.append("\n".join(cur))
            cur = [line[2:]]
        elif cur:
            cur.append(line)
    if cur:
        bullets.append("\n".join(cur))

    extracted = []
    for b in bullets:
        b_lines = [l.rstrip() for l in b.splitlines()]
        b_joined = "\n".join(b_lines)
        if "ValueError:" in b_lines[0] or (len(b_lines) > 1 and "ValueError:" in b_joined):
            after = b_joined.split("ValueError:", 1)[1].strip()
            chars = []
            in_q, esc = None, False
            for ch in after:
                if esc:
                    chars.append(ch); esc = False; continue
                if ch == '\\':
                    chars.append(ch); esc = True; continue
                if in_q:
                    chars.append(ch)
                    if ch == in_q: in_q = None
                    continue
                if ch in ('"', "'"):
                    in_q = ch; chars.append(ch); continue
                if ch == '\n':
                    chars.append(' ')
                else:
                    chars.append(ch)
            normalized_after = "".join(chars)
            calls = split_top_level(normalized_after)
            for c in calls:
                cleaned = strip_trailing_comment(c)
                try:
                    ast.parse(cleaned)
                    extracted.append(('val_err', cleaned, 'ValueError', f"_expect_val_err(lambda: {cleaned})"))
                except SyntaxError:
                    pass
            continue

        if "-> ValueError" in b_joined:
            before = b_joined.split("-> ValueError", 1)[0].strip()
            cleaned = strip_trailing_comment(before)
            try:
                ast.parse(cleaned)
                extracted.append(('val_err', cleaned, 'ValueError', f"_expect_val_err(lambda: {cleaned})"))
            except SyntaxError:
                pass
            continue

        if "raises ValueError" in b_joined:
            before = b_joined.split("raises ValueError", 1)[0].strip()
            cleaned = strip_trailing_comment(before)
            try:
                ast.parse(cleaned)
                extracted.append(('val_err', cleaned, 'ValueError', f"_expect_val_err(lambda: {cleaned})"))
            except SyntaxError:
                pass
            continue

        chars = []
        in_q, esc = None, False
        for ch in b_joined:
            if esc:
                chars.append(ch); esc = False; continue
            if ch == '\\':
                chars.append(ch); esc = True; continue
            if in_q:
                chars.append(ch)
                if ch == in_q: in_q = None
                continue
            if ch in ('"', "'"):
                in_q = ch; chars.append(ch); continue
            if ch == '\n':
                chars.append(' ')
            else:
                chars.append(ch)
        line = "".join(chars).strip()
        cleaned = strip_trailing_comment(line)
        if " == " in cleaned or " is " in cleaned or " in " in cleaned:
            try:
                tree = ast.parse(f"assert {cleaned}")
                if isinstance(tree.body[0], ast.Assert) and isinstance(tree.body[0].test, (ast.Compare, ast.BoolOp)):
                    extracted.append(('compare', cleaned, '', f"assert {cleaned}"))
            except SyntaxError:
                pass
    return extracted

def generate():
    out_lines = [
        '"""Auto-extracted visible tests for loop-v10 from task prompts.',
        'Extracted deterministically on CPU from prompt "Examples:" blocks only.',
        'Never reads from tasks_v10.py "tests".',
        '"""',
        '',
        'HEADER = """def _expect_val_err(func):',
        '    try:',
        '        func()',
        '    except ValueError:',
        '        return',
        '    assert False, "expected ValueError"',
        '"""',
        '',
        'NO_VISIBLE = ["v10_74_minkowski_sum_convex"]',
        '',
        '# Mapping: task_id -> list of check dicts: {"kind": str, "expr": str, "code": str}',
        'CHECKS = {'
    ]

    total_valid = 0
    checks_dict = {}
    tests_dict = {}

    for t in tasks_v10.T:
        tid = t["id"]
        raw_checks = extract_from_prompt(t["prompt"])
        valid_checks = []
        for c in raw_checks:
            kind, expr, exp_s, code = c
            # Filter out known invalid checks:
            # - v10_39 and v10_66 value examples depend on unbound variables (b and poly); keep only ValueError asserts.
            # - v10_57, v10_76, v10_81 have prompt typos in example output values.
            # - v10_74 examples depend on multi-line assignments (poly1, poly2); 0 valid standalone asserts (no_visible).
            if tid == "v10_39_uuid_urn" and bool(re.search(r'\bb\b(?!["\'])', code)):
                continue
            if tid == "v10_57_ramanujan_sum" and "ramanujan_sum(6, 2) == -2" in code:
                continue
            if tid == "v10_66_point_in_convex" and bool(re.search(r'\bpoly\b', code)):
                continue
            if tid == "v10_74_minkowski_sum_convex" and bool(re.search(r'\bpoly[12]\b', code)):
                continue
            if tid == "v10_76_elevator_scan" and '== (9, [7, 3])' in code:
                continue
            if tid == "v10_81_turing_machine_1d" and '== ("accepted", 2, "111")' in code:
                continue
            valid_checks.append({"kind": kind, "expr": expr, "code": code})
            total_valid += 1

        checks_dict[tid] = valid_checks
        if valid_checks:
            test_body = "\n".join(vc["code"] for vc in valid_checks)
            tests_dict[tid] = 'def _expect_val_err(func):\n    try:\n        func()\n    except ValueError:\n        return\n    assert False, "expected ValueError"\n\n' + test_body + "\n"
        else:
            tests_dict[tid] = ""

        # Format checks for tid
        out_lines.append(f'    {repr(tid)}: [')
        for vc in valid_checks:
            out_lines.append(f'        {repr(vc)},')
        out_lines.append('    ],')

    out_lines.append('}')
    out_lines.append('')
    out_lines.append(f'# Total valid checks: {total_valid}')
    out_lines.append('# Mapping: task_id -> complete executable visible test source string')
    out_lines.append('VISIBLE_TESTS = {')
    for tid in sorted(tests_dict.keys()):
        val = tests_dict[tid]
        out_lines.append(f'    {repr(tid)}: {repr(val)},')
    out_lines.append('}')
    out_lines.append('')

    target_path = os.path.join(HERE, "tasks_v10_visible.py")
    with open(target_path, "w") as f:
        f.write("\n".join(out_lines))
    print(f"Wrote {target_path}: {total_valid} checks across {len(tests_dict)} tasks.")

if __name__ == "__main__":
    generate()
