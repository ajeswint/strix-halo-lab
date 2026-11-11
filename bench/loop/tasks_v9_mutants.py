"""Grader boundary checks for tasks_v9.py: simple wrong or naive variants of each reference that the tests must reject.

Each entry is (what the variant gets wrong, old, new): `old` must occur exactly once in the task's ref, and the ref
with `old` replaced by `new` must FAIL run.grade on the visible seed (test_tasks_v9.TestMutants). These are typical
off-by-one, rounding, validation and tie-break mistakes, not answers. Nothing here is shown to a model.
"""

MUTANTS = {
    "v9_01_perm_mode": [
        ("special bit always lower case", "out.append(on if b & 1 else off)", "out.append(on)"),
        ("bool accepted as a mode", "not isinstance(mode, int) or isinstance(mode, bool) or", "not isinstance(mode, int) or"),
    ],
    "v9_02_size_units": [
        ("tenths truncated, not rounded half up", "tenths = (20 * n + u) // (2 * u)", "tenths = 10 * n // u"),
        ("no promotion at 1024.0", "if tenths >= 10240 and k < 5:", "if False:"),
    ],
    "v9_03_tab_stops": [
        ("a single trailing space also becomes a tab", "if len(chunk) == width and n >= 2:", "if len(chunk) == width and n >= 1:"),
        ("tab always expands to width spaces", "pad = width - col % width", "pad = width"),
    ],
    "v9_04_quoted_printable": [
        ("final space written literally", "b == 32 and i != last", "b == 32"),
        ("76-character limit on every line", "limit = 76 if i == last else 75", "limit = 76"),
    ],
    "v9_05_header_params": [
        ("repeated parameter names accepted", "if name.lower() in params:", "if False:"),
        ("backslash not escaped when formatting", 'v.replace("\\\\", "\\\\\\\\").replace', "v.replace"),
    ],
    "v9_06_flatten_keys": [
        ("leaf/parent conflicts not detected", 'if ".".join(parts[:i]) in flat:', "if False:"),
        ("empty nested dicts dropped", "out[path] = {}", "pass"),
    ],
    "v9_07_page_ranges": [
        ("leading zeros accepted", 'or s[0] == "0" or', 'or s == "0" or'),
        ("a run of two written as a range", "if j - i >= 2:", "if j - i >= 1:"),
    ],
    "v9_08_outline_numbers": [
        ("level jumps accepted", 'raise ValueError("heading jumps a level: %r" % ln)', "pass"),
        ("numbers not checked against the sequence", "if parts != want:", "if False:"),
    ],
    "v9_09_zeckendorf": [
        ("trailing incomplete code accepted", "    if k:\n", "    if False:\n"),
        ("terminating 1 missing", '.rstrip("0") + "1"', '.rstrip("0")'),
    ],
    "v9_10_aliquot_chain": [
        ("aspiring reported as cyclic", 'kind = "aspiring" if L == 1 else "cyclic"', 'kind = "cyclic"'),
        ("one step short of limit", "for _ in range(limit):", "for _ in range(limit - 1):"),
    ],
    "v9_11_primitive_root": [
        ("2 * p**k not recognized", "f.get(2, 0) <= 1", "f.get(2, 0) == 0"),
        ("count uses phi(n - 1)", "return _phi(_factor(_phi(f)))", "return _phi(_factor(n - 1))"),
    ],
    "v9_12_factorial_zeros": [
        ("prime-power exponent of b ignored", "return min(_legendre(n, p) // e for p, e", "return min(_legendre(n, p) // 1 for p, e"),
        ("binomial ignores (n - k)!", "- _legendre(n - k, p)) // e", ") // e"),
    ],
    "v9_13_lucky_sieve": [
        ("deletes by value instead of position", "del lst[m - 1::m]", "lst[:] = [v for v in lst if v == m or v % m]"),
        ("first sieve step (3) skipped", "    i = 1\n", "    i = 2\n"),
    ],
    "v9_14_consecutive_sums": [
        ("single-term run included", "if k < 2:", "if k < 1:"),
        ("count is odd divisors, not minus one", "return len(_divisors(n)) - 1", "return len(_divisors(n))"),
    ],
    "v9_15_gaussian_gcd": [
        ("quotient floored, not rounded", "return (2 * num + den) // (2 * den)", "return num // den"),
        ("wrong associate chosen", "while not (x > 0 and y >= 0):", "while not (x >= 0 and y > 0):"),
    ],
    "v9_16_lca_queries": [
        ("distance is the depth difference", "depth[u] + depth[v] - 2 * depth[a]", "abs(depth[u] - depth[v])"),
        ("cycles not detected", "if len(order) != n:", "if False:"),
    ],
    "v9_17_key_maze": [
        ("doors ignored", 'if "A" <= ch <= "D" and not keys >> (ord(ch) - 65) & 1:', "if False:"),
        ("visited by cell only, not by keys held", "if st not in seen:\n                seen.add(st)",
         "if st[:2] not in seen:\n                seen.add(st[:2])"),
    ],
    "v9_18_eq_constraints": [
        ("only direct disequalities checked", 'ok = all(find(a) != find(b) for a, op, b in cs if op == "!=")',
         'ok = all(a != b for a, op, b in cs if op == "!=")'),
        ("singleton classes dropped", "return sorted(sorted(g) for g in groups.values())",
         "return sorted(sorted(g) for g in groups.values() if len(g) > 1)"),
    ],
    "v9_19_func_graph_tails": [
        ("cycle length taken as the whole walk", "tail[y], cyc[y], state[y] = 0, length, 2", "tail[y], cyc[y], state[y] = 0, len(path), 2"),
        ("tail not incremented", "tail[f[y]] + 1", "tail[f[y]]"),
    ],
    "v9_20_grid_line": [
        ("half rounded toward zero", "if 2 * r >= den:", "if 2 * r > den:"),
        ("endpoints block the line of sight", "for x, y in cells[1:-1])", "for x, y in cells)"),
    ],
    "v9_21_rdp_simplify": [
        ("distance equal to eps kept", "if bn > eps * eps * bd:", "if bn >= eps * eps * bd:"),
        ("distance to the line, not the segment, before A", "if vv == 0 or dot <= 0:", "if vv == 0:"),
    ],
    "v9_22_polar_order": [
        ("same-ray ties by distance descending", "return (du > dv) - (du < dv)", "return (du < dv) - (du > dv)"),
        ("negative x-axis in the upper half", "0 if v[1] > 0 or (v[1] == 0 and v[0] > 0) else 1", "0 if v[1] >= 0 else 1"),
    ],
    "v9_23_egg_drop": [
        ("lowest optimal first floor", "return min(floors, _cover(t - 1, eggs - 1, floors) + 1)",
         "return max(1, floors - _cover(t - 1, eggs, floors))"),
        ("zero floors needs one drop", "lo, hi = 0, floors", "lo, hi = 1, max(floors, 1)"),
    ],
    "v9_24_interleave_count": [
        ("count reduced modulo 1e9+7", "            row[j] = v\n", "            row[j] = v % 1000000007\n"),
        ("greedy labels without lookahead", 'if i < n and a[i] == c[i + j] and ok[i + 1][j]:\n            out.append("A")',
         'if i < n and a[i] == c[i + j]:\n            out.append("A")'),
    ],
    "v9_25_turmite_walk": [
        ("L and R swapped", 'd = (d + (1 if rule[c] == "R" else 3)) % 4', 'd = (d + (3 if rule[c] == "R" else 1)) % 4'),
        ("picture rows bottom-up", "for y in range(max(ys), min(ys) - 1, -1)]", "for y in range(min(ys), max(ys) + 1)]"),
    ],
    "v9_26_sandpile_topple": [
        ("counts batches, not topplings", "count += q", "count += 1"),
        ("input mutated", "g = [list(r) for r in grid]", "g = grid"),
    ],
    "v9_27_snake_game": [
        ("fatal move counted", "if not (0 <= r < height and 0 <= c < width):\n            return score, n\n",
         "if not (0 <= r < height and 0 <= c < width):\n            return score, n + 1\n"),
        ("all food on the board at once", "eat = k < len(cells) and cells[k] == (r, c)", "eat = (r, c) in cells[k:]"),
    ],
    "v9_28_tax_lots": [
        ("lifo treated as fifo", 'idx = 0 if method == "fifo" else len(lots) - 1', "idx = 0"),
        ("overselling not detected up front", "if qty > sum(l[0] for l in lots):", "if not lots:"),
    ],
    "v9_29_jump_reach": [
        ("jumps only from the end of the prefix", "far = max(far, i + lengths[i])", "far = max(far, end + lengths[end])"),
        ("one jump too many allowed", "if jumps > k:", "if jumps > k + 1:"),
    ],
    "v9_30_dice_totals": [
        ("leading zeros accepted in dice terms", 'TERM = re.compile(r"([1-9][0-9]*)d([1-9][0-9]*)|(0|[1-9][0-9]*)")',
         'TERM = re.compile(r"([0-9]+)d([0-9]+)|(0|[1-9][0-9]*)")'),
        ("strictly greater than target", "if t >= target)", "if t > target)"),
    ],
}
