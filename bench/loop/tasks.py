"""loop-v0: 20 held-out Python tasks for the small-model loop (Roadmap item 2).

Each task: id, prompt (the spec the model sees), tests (asserts run against
`from solution import *`), ref (a reference solution; `run.py --selftest` checks
that every ref passes its tests). Standard library only. Written 2026-10-05 for
this set; none was used for prompt iteration or as a few-shot example.
"""

T = []


def task(id, prompt, tests, ref):
    T.append({"id": id, "prompt": prompt.strip(), "tests": tests.strip(), "ref": ref.strip()})


task("01_merge_intervals", """
Write `merge_intervals(intervals: list[list[int]]) -> list[list[int]]`.
Input: closed intervals [start, end] with start <= end, in any order, possibly empty.
Merge every pair that overlaps or touches ([1,2] and [2,3] merge to [1,3]).
Return the merged intervals sorted by start. Do not mutate the input.
""", """
assert merge_intervals([]) == []
assert merge_intervals([[1, 3]]) == [[1, 3]]
assert merge_intervals([[8, 10], [1, 3], [2, 6], [15, 18]]) == [[1, 6], [8, 10], [15, 18]]
assert merge_intervals([[1, 2], [2, 3]]) == [[1, 3]]
assert merge_intervals([[1, 10], [2, 3], [4, 5]]) == [[1, 10]]
assert merge_intervals([[5, 5], [1, 1], [3, 4]]) == [[1, 1], [3, 4], [5, 5]]
assert merge_intervals([[-5, -1], [-2, 0], [1, 2]]) == [[-5, 0], [1, 2]]
x = [[3, 4], [1, 2]]; merge_intervals(x); assert x == [[3, 4], [1, 2]]
""", """
def merge_intervals(intervals):
    out = []
    for s, e in sorted(intervals):
        if out and s <= out[-1][1]:
            out[-1][1] = max(out[-1][1], e)
        else:
            out.append([s, e])
    return out
""")

task("02_roman_to_int", """
Write `roman_to_int(s: str) -> int` for Roman numerals 1..3999 (I V X L C D M).
Accept only the canonical form (the one int->roman would produce: subtractive pairs
IV IX XL XC CD CM only, no more than three repeats of I X C M, no repeats of V L D).
Raise ValueError for anything else, including "", lowercase, "IIII", "IC", "VX", "MMMM".
""", """
assert roman_to_int("I") == 1
assert roman_to_int("IV") == 4
assert roman_to_int("IX") == 9
assert roman_to_int("LVIII") == 58
assert roman_to_int("MCMXCIV") == 1994
assert roman_to_int("MMMCMXCIX") == 3999
assert roman_to_int("CDXLIV") == 444
for bad in ["", "iv", "IIII", "IC", "VX", "MMMM", "VV", "XM", "IIV", "ABC", "XIIII", "CMM", "IXI"]:
    try:
        roman_to_int(bad)
    except ValueError:
        pass
    else:
        raise AssertionError(bad)
""", """
def _to_roman(n):
    vals = [(1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"),
            (50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]
    out = ""
    for v, r in vals:
        while n >= v:
            out += r; n -= v
    return out

_TABLE = {_to_roman(i): i for i in range(1, 4000)}

def roman_to_int(s):
    if s not in _TABLE:
        raise ValueError(s)
    return _TABLE[s]
""")

task("03_eval_expr", """
Write `eval_expr(s: str) -> float` that evaluates an arithmetic expression with
non-negative integer literals, + - * /, parentheses, unary minus (and unary plus),
and arbitrary spaces. * and / bind tighter than + and -; operators of equal
precedence are left-associative; / is true division. Return a float.
Raise ValueError for malformed input (e.g. "", "1+", "(1", "1)", "2*/3", "1 2").
Division by zero raises ZeroDivisionError. Do not use eval/exec/compile/ast.
""", """
def close(a, b): return abs(a - b) < 1e-9
assert close(eval_expr("1 + 2 * 3"), 7)
assert close(eval_expr("(1 + 2) * 3"), 9)
assert close(eval_expr("10 / 4"), 2.5)
assert close(eval_expr("8 - 3 - 2"), 3)
assert close(eval_expr("16 / 4 / 2"), 2)
assert close(eval_expr("-3 + 5"), 2)
assert close(eval_expr("2 * -3"), -6)
assert close(eval_expr("-(2 + 3) * 2"), -10)
assert close(eval_expr("--4"), 4)
assert close(eval_expr("+7"), 7)
assert close(eval_expr("  ( ( 42 ) ) "), 42)
assert close(eval_expr("1 - -1"), 2)
assert close(eval_expr("2 * (3 + 4) * 5 - 6 / 3"), 68)
for bad in ["", "1+", "(1", "1)", "2*/3", "1 2", "()", "*3", "3 + * 4"]:
    try:
        eval_expr(bad)
    except ValueError:
        pass
    else:
        raise AssertionError(bad)
try:
    eval_expr("1/0")
except ZeroDivisionError:
    pass
else:
    raise AssertionError("1/0")
""", """
import re

def eval_expr(s):
    toks = re.findall(r"\\d+|[-+*/()]|\\S", s)
    if any(not (t.isdigit() or t in "+-*/()") for t in toks):
        raise ValueError(s)
    pos = 0
    def peek():
        return toks[pos] if pos < len(toks) else None
    def take():
        nonlocal pos
        pos += 1
        return toks[pos - 1]
    def expr():
        v = term()
        while peek() in ("+", "-"):
            op = take(); r = term()
            v = v + r if op == "+" else v - r
        return v
    def term():
        v = unary()
        while peek() in ("*", "/"):
            op = take(); r = unary()
            v = v * r if op == "*" else v / r
        return v
    def unary():
        if peek() in ("+", "-"):
            op = take(); v = unary()
            return -v if op == "-" else v
        return atom()
    def atom():
        t = peek()
        if t is None:
            raise ValueError(s)
        if t == "(":
            take(); v = expr()
            if peek() != ")":
                raise ValueError(s)
            take(); return v
        if t.isdigit():
            take(); return float(t)
        raise ValueError(s)
    v = expr()
    if pos != len(toks):
        raise ValueError(s)
    return v
""")

task("04_semver_compare", """
Write `semver_compare(a: str, b: str) -> int` returning -1, 0 or 1 as a has lower,
equal or higher precedence than b under Semantic Versioning 2.0.0: compare
MAJOR.MINOR.PATCH numerically; a version with a pre-release (after "-") is lower
than the same version without one; pre-release identifiers (dot-separated) compare
numerically if all digits, else in ASCII order, numeric identifiers are lower than
alphanumeric ones, and a shorter list of identifiers is lower when all preceding
ones are equal. Build metadata (after "+") is ignored. Inputs are valid.
""", """
order = ["1.0.0-alpha", "1.0.0-alpha.1", "1.0.0-alpha.beta", "1.0.0-beta", "1.0.0-beta.2",
         "1.0.0-beta.11", "1.0.0-rc.1", "1.0.0", "1.0.1", "1.1.0", "1.10.0", "2.0.0"]
for i, a in enumerate(order):
    for j, b in enumerate(order):
        exp = (i > j) - (i < j)
        assert semver_compare(a, b) == exp, (a, b)
assert semver_compare("1.0.0+build.5", "1.0.0") == 0
assert semver_compare("1.0.0-alpha+001", "1.0.0-alpha+002") == 0
assert semver_compare("2.10.0", "2.9.0") == 1
assert semver_compare("1.0.0-2", "1.0.0-10") == -1
assert semver_compare("1.0.0-a-b", "1.0.0-a") == 1
""", """
def semver_compare(a, b):
    def key(v):
        v = v.split("+", 1)[0]
        core, _, pre = v.partition("-")
        nums = tuple(int(x) for x in core.split("."))
        if not pre:
            return nums, 1, ()
        ids = tuple((0, int(x), "") if x.isdigit() else (1, 0, x) for x in pre.split("."))
        return nums, 0, ids
    ka, kb = key(a), key(b)
    return (ka > kb) - (ka < kb)
""")

task("05_lru_cache", """
Write a class `LRUCache` with `__init__(self, capacity: int)`, `get(self, key) -> value`
returning -1 when the key is absent, and `put(self, key, value) -> None`. get and put
both mark the key as most recently used. When a put of a new key would exceed
capacity, evict the least recently used key first. Capacity 0 stores nothing.
Both operations must be O(1) on average.
""", """
c = LRUCache(2)
c.put(1, 1); c.put(2, 2)
assert c.get(1) == 1
c.put(3, 3)
assert c.get(2) == -1
c.put(4, 4)
assert c.get(1) == -1
assert c.get(3) == 3
assert c.get(4) == 4
c = LRUCache(2)
c.put(1, 1); c.put(2, 2); c.put(1, 10); c.put(3, 3)
assert c.get(1) == 10 and c.get(2) == -1 and c.get(3) == 3
z = LRUCache(0)
z.put(1, 1)
assert z.get(1) == -1
c = LRUCache(1)
c.put("a", 1); c.put("b", 2)
assert c.get("a") == -1 and c.get("b") == 2
import time
c = LRUCache(50000)
t = time.perf_counter()
for i in range(200000):
    c.put(i, i)
    c.get(i - 1000)
assert time.perf_counter() - t < 3.0
""", """
from collections import OrderedDict

class LRUCache:
    def __init__(self, capacity):
        self.cap = capacity
        self.d = OrderedDict()
    def get(self, key):
        if key not in self.d:
            return -1
        self.d.move_to_end(key)
        return self.d[key]
    def put(self, key, value):
        if self.cap <= 0:
            return
        if key in self.d:
            self.d.move_to_end(key)
        self.d[key] = value
        if len(self.d) > self.cap:
            self.d.popitem(last=False)
""")

task("06_topo_sort", """
Write `topo_sort(n: int, edges: list[tuple[int, int]]) -> list[int]` for nodes 0..n-1,
where edge (u, v) means u must come before v. Whenever several nodes are available,
output the smallest-numbered one first (so the answer is unique). Duplicate edges
may appear. Raise ValueError if the graph has a cycle (a self-loop is a cycle).
""", """
assert topo_sort(0, []) == []
assert topo_sort(3, []) == [0, 1, 2]
assert topo_sort(4, [(3, 0), (2, 0), (1, 3)]) == [1, 2, 3, 0]
assert topo_sort(5, [(4, 1), (4, 0), (1, 0), (1, 0)]) == [2, 3, 4, 1, 0]
assert topo_sort(6, [(5, 2), (5, 0), (4, 0), (4, 1), (2, 3), (3, 1)]) == [4, 5, 0, 2, 3, 1]
for n, e in [(2, [(0, 1), (1, 0)]), (1, [(0, 0)]), (4, [(0, 1), (1, 2), (2, 3), (3, 1)])]:
    try:
        topo_sort(n, e)
    except ValueError:
        pass
    else:
        raise AssertionError(e)
""", """
import heapq

def topo_sort(n, edges):
    adj = [[] for _ in range(n)]
    indeg = [0] * n
    for u, v in edges:
        adj[u].append(v); indeg[v] += 1
    h = [i for i in range(n) if indeg[i] == 0]
    heapq.heapify(h)
    out = []
    while h:
        u = heapq.heappop(h); out.append(u)
        for v in adj[u]:
            indeg[v] -= 1
            if indeg[v] == 0:
                heapq.heappush(h, v)
    if len(out) != n:
        raise ValueError("cycle")
    return out
""")

task("07_parse_duration", """
Write `parse_duration(s: str) -> int` returning total seconds for strings like
"1h30m", "45s", "2d", "1h 5m 3s". Units are d (86400 s), h, m, s. Each component is a
non-negative integer immediately followed by its unit letter. Components may be
separated by single or multiple spaces or by nothing, units must appear in the order
d, h, m, s, each at most once, and at least one component is required.
Leading/trailing spaces are allowed. Raise ValueError for anything else
(e.g. "", "5", "1m1h", "1h1h", "-1s", "1.5h", "1 h", "1H").
""", """
assert parse_duration("45s") == 45
assert parse_duration("1h30m") == 5400
assert parse_duration("2d") == 172800
assert parse_duration("1h 5m 3s") == 3903
assert parse_duration("1d2h3m4s") == 93784
assert parse_duration("  0s ") == 0
assert parse_duration("90m") == 5400
assert parse_duration("1d   1s") == 86401
for bad in ["", "   ", "5", "1m1h", "1h1h", "-1s", "1.5h", "1 h", "1H", "h", "1h+2m", "1x"]:
    try:
        parse_duration(bad)
    except ValueError:
        pass
    else:
        raise AssertionError(bad)
""", """
import re

_RE = re.compile(r"(?:(\\d+)d)? *(?:(\\d+)h)? *(?:(\\d+)m)? *(?:(\\d+)s)?")

def parse_duration(s):
    t = s.strip()
    m = _RE.fullmatch(t)
    if not t or not m or all(g is None for g in m.groups()):
        raise ValueError(s)
    d, h, mi, se = (int(g) if g else 0 for g in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + se
""")

task("08_spiral_order", """
Write `spiral_order(matrix: list[list[int]]) -> list[int]` returning the elements of
a rectangular matrix in clockwise spiral order starting at the top-left corner.
The matrix may be empty ([] or [[]]), a single row, or a single column.
""", """
assert spiral_order([]) == []
assert spiral_order([[]]) == []
assert spiral_order([[1]]) == [1]
assert spiral_order([[1, 2, 3]]) == [1, 2, 3]
assert spiral_order([[1], [2], [3]]) == [1, 2, 3]
assert spiral_order([[1, 2, 3], [4, 5, 6], [7, 8, 9]]) == [1, 2, 3, 6, 9, 8, 7, 4, 5]
assert spiral_order([[1, 2, 3, 4], [5, 6, 7, 8], [9, 10, 11, 12]]) == [1, 2, 3, 4, 8, 12, 11, 10, 9, 5, 6, 7]
assert spiral_order([[1, 2], [3, 4], [5, 6], [7, 8]]) == [1, 2, 4, 6, 8, 7, 5, 3]
""", """
def spiral_order(matrix):
    out = []
    m = [row[:] for row in matrix if row]
    while m:
        out += m.pop(0)
        m = [list(r) for r in zip(*m)][::-1] if m else []
    return out
""")

task("09_justify", """
Write `justify(words: list[str], width: int) -> list[str]` (full text justification).
Pack words greedily, as many per line as fit with at least one space between them.
Every line except the last is exactly `width` characters: distribute extra spaces
between words as evenly as possible, giving the leftmost gaps one more space when
uneven; a line with a single word is left-justified and padded on the right.
The last line is left-justified (single spaces) and padded with spaces to `width`.
Each word is non-empty and at most `width` long; words is non-empty.
""", """
assert justify(["This", "is", "an", "example", "of", "text", "justification."], 16) == [
    "This    is    an", "example  of text", "justification.  "]
assert justify(["What", "must", "be", "acknowledgment", "shall", "be"], 16) == [
    "What   must   be", "acknowledgment  ", "shall be        "]
assert justify(["a"], 1) == ["a"]
assert justify(["a", "b", "c", "d", "e"], 3) == ["a b", "c d", "e  "]
assert justify(["Science", "is", "what", "we", "understand", "well", "enough", "to", "explain",
                "to", "a", "computer.", "Art", "is", "everything", "else", "we", "do"], 20) == [
    "Science  is  what we", "understand      well", "enough to explain to",
    "a  computer.  Art is", "everything  else  we", "do                  "]
""", """
def justify(words, width):
    lines, cur = [], []
    for w in words:
        if cur and len(" ".join(cur + [w])) > width:
            lines.append(cur); cur = []
        cur.append(w)
    out = []
    for line in lines:
        if len(line) == 1:
            out.append(line[0].ljust(width)); continue
        gaps = len(line) - 1
        spaces = width - sum(map(len, line))
        q, r = divmod(spaces, gaps)
        s = ""
        for i, w in enumerate(line[:-1]):
            s += w + " " * (q + (1 if i < r else 0))
        out.append(s + line[-1])
    out.append(" ".join(cur).ljust(width))
    return out
""")

task("10_csv_split", """
Write `csv_split(line: str) -> list[str]` that splits one CSV record (no newlines
inside). Fields are separated by commas. A field that starts with a double quote is
quoted: it ends at the next lone double quote, "" inside it stands for one ", and
commas inside it are literal; the closing quote must be followed by a comma or the
end of the line. Unquoted fields are taken verbatim (no stripping) and may not
contain a double quote. "" (empty line) gives [""]. Raise ValueError for an
unterminated quoted field, text after a closing quote, or a quote inside an
unquoted field. Do not use the csv module.
""", """
assert csv_split("") == [""]
assert csv_split("a,b,c") == ["a", "b", "c"]
assert csv_split("a,,c,") == ["a", "", "c", ""]
assert csv_split(' a , b ') == [" a ", " b "]
assert csv_split('"x,y",z') == ["x,y", "z"]
assert csv_split('"he said ""hi""\",2') == ['he said "hi"', "2"]
assert csv_split('""') == [""]
assert csv_split('"",""') == ["", ""]
assert csv_split(',') == ["", ""]
assert csv_split('"a""\",b') == ['a"', "b"]
for bad in ['"abc', '"a"b,c', 'a"b', 'x,"y', '"a" ,b']:
    try:
        csv_split(bad)
    except ValueError:
        pass
    else:
        raise AssertionError(bad)
""", """
def csv_split(line):
    out, i, n = [], 0, len(line)
    while True:
        if i < n and line[i] == '"':
            i += 1; buf = []
            while True:
                if i >= n:
                    raise ValueError("unterminated")
                if line[i] == '"':
                    if i + 1 < n and line[i + 1] == '"':
                        buf.append('"'); i += 2; continue
                    i += 1; break
                buf.append(line[i]); i += 1
            if i < n and line[i] != ",":
                raise ValueError("text after quote")
            out.append("".join(buf))
        else:
            j = line.find(",", i)
            j = n if j < 0 else j
            f = line[i:j]
            if '"' in f:
                raise ValueError("quote in unquoted field")
            out.append(f); i = j
        if i >= n:
            return out
        i += 1
""")

task("11_min_window", """
Write `min_window(s: str, t: str) -> str` returning the shortest substring of s that
contains every character of t with at least the same multiplicity. If several have
the same minimal length, return the leftmost. Return "" if none exists or t is empty.
Must run in O(len(s) + len(t)) time for the alphabet involved.
""", """
assert min_window("ADOBECODEBANC", "ABC") == "BANC"
assert min_window("a", "a") == "a"
assert min_window("a", "aa") == ""
assert min_window("aa", "aa") == "aa"
assert min_window("abc", "") == ""
assert min_window("", "a") == ""
assert min_window("bba", "ab") == "ba"
assert min_window("abcabc", "cb") == "bc"
assert min_window("xaxbxa", "aab") == "axbxa"
import time
s = "ab" * 100000 + "c"
t0 = time.perf_counter()
assert min_window(s, "abc") == "abc"
assert time.perf_counter() - t0 < 3.0
""", """
from collections import Counter

def min_window(s, t):
    if not t:
        return ""
    need = Counter(t); missing = len(t)
    best = (float("inf"), 0, 0); l = 0
    for r, ch in enumerate(s, 1):
        if need[ch] > 0:
            missing -= 1
        need[ch] -= 1
        if missing == 0:
            while need[s[l]] < 0:
                need[s[l]] += 1; l += 1
            if r - l < best[0]:
                best = (r - l, l, r)
            need[s[l]] += 1; missing += 1; l += 1
    return "" if best[0] == float("inf") else s[best[1]:best[2]]
""")

task("12_glob_match", """
Write `glob_match(pattern: str, text: str) -> bool` matching the whole text.
Pattern syntax: ? matches any one character; * matches any sequence including empty;
[abc] matches one listed character; ranges like [a-z0-9] are allowed inside brackets;
[!abc] matches one character not listed. Every other character matches itself.
Patterns are well-formed (every [ has a closing ] and the class is non-empty).
Do not use the fnmatch, glob or re modules. Must not take exponential time.
""", """
assert glob_match("", "")
assert not glob_match("", "a")
assert glob_match("*", "")
assert glob_match("*", "anything")
assert glob_match("a?c", "abc")
assert not glob_match("a?c", "ac")
assert glob_match("*.py", "run.py")
assert not glob_match("*.py", "run.pyc")
assert glob_match("[abc]x", "bx")
assert not glob_match("[abc]x", "dx")
assert glob_match("file[0-9][0-9]", "file42")
assert not glob_match("file[0-9]", "filex")
assert glob_match("[!a-c]z", "dz")
assert not glob_match("[!a-c]z", "bz")
assert glob_match("a*b*c", "aXXbYYc")
assert not glob_match("a*b*c", "aXXbYY")
assert glob_match("**a**", "bab")
import time
t = time.perf_counter()
assert not glob_match("a*" * 30 + "b", "a" * 60)
assert time.perf_counter() - t < 2.0
""", """
def _parse(p):
    toks, i = [], 0
    while i < len(p):
        c = p[i]
        if c == "[":
            k = i + 1
            neg = p[k:k + 1] == "!"
            if neg:
                k += 1
            j = p.index("]", k + 1)
            body = p[k:j]
            items, m = [], 0
            while m < len(body):
                if m + 2 < len(body) and body[m + 1] == "-":
                    items.append((body[m], body[m + 2])); m += 3
                else:
                    items.append((body[m], body[m])); m += 1
            toks.append(("cls", neg, items)); i = j + 1
        elif c == "*":
            toks.append(("star",)); i += 1
        elif c == "?":
            toks.append(("any",)); i += 1
        else:
            toks.append(("lit", c)); i += 1
    return toks

def _one(tok, ch):
    if tok[0] == "any":
        return True
    if tok[0] == "lit":
        return tok[1] == ch
    hit = any(a <= ch <= b for a, b in tok[2])
    return hit != tok[1]

def glob_match(pattern, text):
    toks = _parse(pattern)
    cur = [False] * (len(text) + 1)
    cur[0] = True
    for tok in toks:
        nxt = [False] * (len(text) + 1)
        if tok[0] == "star":
            seen = False
            for i in range(len(text) + 1):
                seen = seen or cur[i]
                nxt[i] = seen
        else:
            for i in range(len(text)):
                if cur[i] and _one(tok, text[i]):
                    nxt[i + 1] = True
        cur = nxt
    return cur[len(text)]
""")

task("13_lis", """
Write `lis(nums: list[int]) -> list[int]` returning a longest strictly increasing
subsequence of nums (as values, in order). If there are several of maximal length,
return the one that is lexicographically smallest as a list of values.
nums may be empty (return []). len(nums) <= 2000.
""", """
assert lis([]) == []
assert lis([5]) == [5]
assert lis([3, 2, 1]) == [1]
assert lis([10, 9, 2, 5, 3, 7, 101, 18]) == [2, 3, 7, 18]
assert lis([0, 1, 0, 3, 2, 3]) == [0, 1, 2, 3]
assert lis([7, 7, 7]) == [7]
assert lis([1, 3, 2, 4]) == [1, 2, 4]
assert lis([4, 5, 1, 2, 3]) == [1, 2, 3]
assert lis([2, 1, 3, 0, 4]) == [1, 3, 4]
assert lis([5, 1, 6, 2, 7, 3, 8]) == [1, 2, 3, 8]
import random, time
random.seed(7)
big = [random.randint(0, 10**6) for _ in range(2000)]
t = time.perf_counter()
r = lis(big)
assert time.perf_counter() - t < 5.0
assert all(a < b for a, b in zip(r, r[1:]))
""", """
def lis(nums):
    n = len(nums)
    best = [None] * n
    for i in range(n - 1, -1, -1):
        cand = [nums[i]]
        for j in range(i + 1, n):
            if nums[j] > nums[i]:
                c = [nums[i]] + best[j]
                if len(c) > len(cand) or (len(c) == len(cand) and c < cand):
                    cand = c
        best[i] = cand
    out = []
    for c in best:
        if len(c) > len(out) or (len(c) == len(out) and c < out):
            out = c
    return out
""")

task("14_shortest_path", """
Write `shortest_path(n: int, edges: list[tuple[int, int, int]], src: int, dst: int)
-> tuple[int, list[int]]` for an undirected graph on nodes 0..n-1 with edges (u, v, w),
integer weights w >= 1 (parallel edges allowed). Return (total weight, node list from
src to dst). Among minimum-weight paths choose the one with the fewest edges, then
the lexicographically smallest node list. If dst is unreachable return (-1, []).
If src == dst return (0, [src]).
""", """
assert shortest_path(1, [], 0, 0) == (0, [0])
assert shortest_path(2, [], 0, 1) == (-1, [])
assert shortest_path(3, [(0, 1, 1), (1, 2, 1), (0, 2, 5)], 0, 2) == (2, [0, 1, 2])
assert shortest_path(3, [(0, 1, 1), (1, 2, 1), (0, 2, 2)], 0, 2) == (2, [0, 2])
assert shortest_path(4, [(0, 1, 1), (1, 3, 1), (0, 2, 1), (2, 3, 1)], 0, 3) == (2, [0, 1, 3])
assert shortest_path(4, [(0, 2, 1), (2, 3, 1), (0, 1, 1), (1, 3, 1)], 3, 0) == (2, [3, 1, 0])
assert shortest_path(3, [(0, 1, 5), (0, 1, 2), (1, 2, 1)], 0, 2) == (3, [0, 1, 2])
assert shortest_path(5, [(0, 4, 4), (0, 1, 1), (1, 2, 1), (2, 3, 1), (3, 4, 1)], 0, 4) == (4, [0, 4])
assert shortest_path(6, [(0, 3, 1), (3, 5, 2), (0, 1, 1), (1, 2, 1), (2, 5, 1), (0, 4, 2), (4, 5, 1)], 0, 5) == (3, [0, 3, 5])
""", """
import heapq

def shortest_path(n, edges, src, dst):
    adj = [[] for _ in range(n)]
    for u, v, w in edges:
        adj[u].append((v, w)); adj[v].append((u, w))
    best = {}
    h = [(0, 0, [src])]
    while h:
        d, k, path = heapq.heappop(h)
        u = path[-1]
        if u in best:
            continue
        best[u] = (d, path)
        if u == dst:
            return d, path
        for v, w in adj[u]:
            if v not in best:
                heapq.heappush(h, (d + w, k + 1, path + [v]))
    return -1, []
""")

task("15_sudoku_valid", """
Write `sudoku_valid(board) -> bool`. board should be a list of 9 strings of length 9,
each character '1'-'9' or '.' (empty). Return True if the board has that shape and
no digit repeats in any row, column or 3x3 box (empty cells are fine; the board need
not be solvable). Return False for a wrong shape, a wrong type, or any other character.
""", """
good = ["53..7....", "6..195...", ".98....6.", "8...6...3", "4..8.3..1",
        "7...2...6", ".6....28.", "...419..5", "....8..79"]
assert sudoku_valid(good) is True
assert sudoku_valid(["." * 9] * 9) is True
bad_row = good[:]; bad_row[0] = "53..7...5"
assert sudoku_valid(bad_row) is False
bad_col = good[:]; bad_col[8] = "5...8..79"
assert sudoku_valid(bad_col) is False
bad_box = good[:]; bad_box[1] = "63.195..."
assert sudoku_valid(bad_box) is False
assert sudoku_valid(good[:8]) is False
assert sudoku_valid([r + "." for r in good]) is False
z = good[:]; z[4] = "4..8.3..0"
assert sudoku_valid(z) is False
assert sudoku_valid(None) is False
assert sudoku_valid([list(r) for r in good]) is False
""", """
def sudoku_valid(board):
    if not isinstance(board, list) or len(board) != 9:
        return False
    if any(not isinstance(r, str) or len(r) != 9 for r in board):
        return False
    if any(c not in "123456789." for r in board for c in r):
        return False
    groups = [[board[r][c] for c in range(9)] for r in range(9)]
    groups += [[board[r][c] for r in range(9)] for c in range(9)]
    groups += [[board[r][c] for r in range(br, br + 3) for c in range(bc, bc + 3)]
               for br in (0, 3, 6) for bc in (0, 3, 6)]
    for g in groups:
        d = [x for x in g if x != "."]
        if len(d) != len(set(d)):
            return False
    return True
""")

task("16_bracket_error", """
Write `bracket_error(s: str) -> int` checking the brackets ()[]{}<> in s (other
characters are ignored). Return -1 if every bracket is correctly matched and nested.
Otherwise return the index of the first error: a closing bracket that does not match
the most recent unclosed opening bracket (or has none) is an error at its own index;
if the string ends with unclosed brackets, return len(s).
""", """
assert bracket_error("") == -1
assert bracket_error("abc") == -1
assert bracket_error("([]{<>})") == -1
assert bracket_error("a(b)c") == -1
assert bracket_error(")") == 0
assert bracket_error("(]") == 1
assert bracket_error("(()") == 3
assert bracket_error("([)]") == 2
assert bracket_error("x<y>z>") == 5
assert bracket_error("{[") == 2
assert bracket_error("()}{") == 2
""", """
def bracket_error(s):
    pair = {")": "(", "]": "[", "}": "{", ">": "<"}
    st = []
    for i, c in enumerate(s):
        if c in "([{<":
            st.append(c)
        elif c in pair:
            if not st or st[-1] != pair[c]:
                return i
            st.pop()
    return len(s) if st else -1
""")

task("17_knapsack", """
Write `knapsack(items: list[tuple[int, int]], cap: int) -> list[int]` for 0/1 knapsack.
items[i] = (weight, value), weight >= 1, value >= 1, cap >= 0. Return the sorted list
of indices of a subset with total weight <= cap and maximum total value. If several
subsets reach the maximum value, return the lexicographically smallest sorted index
list. len(items) <= 100, cap <= 10000.
""", """
assert knapsack([], 10) == []
assert knapsack([(5, 10)], 4) == []
assert knapsack([(5, 10)], 5) == [0]
assert knapsack([(1, 1), (3, 4), (4, 5), (5, 7)], 7) == [1, 2]
assert knapsack([(2, 3), (2, 3), (4, 6)], 4) == [0, 1]
assert knapsack([(2, 3), (1, 3)], 2) == [0]
assert knapsack([(10, 60), (20, 100), (30, 120)], 50) == [1, 2]
assert knapsack([(3, 5), (3, 5), (3, 5)], 6) == [0, 1]
import time
items = [((i * 37) % 97 + 1, (i * 53) % 89 + 1) for i in range(100)]
t = time.perf_counter()
r = knapsack(items, 10000 // 4)
assert time.perf_counter() - t < 10.0
assert sum(items[i][0] for i in r) <= 2500
""", """
def knapsack(items, cap):
    n = len(items)
    # best[i][c] = max value using items i.. with capacity c
    best = [[0] * (cap + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        w, v = items[i]
        row, nxt = best[i], best[i + 1]
        for c in range(cap + 1):
            row[c] = nxt[c]
            if w <= c and nxt[c - w] + v >= row[c]:
                row[c] = nxt[c - w] + v
    out, c = [], cap
    for i in range(n):
        w, v = items[i]
        if w <= c and best[i + 1][c - w] + v == best[i][c]:
            out.append(i); c -= w
    return out
""")

task("18_decimal_to_fraction", """
Write `decimal_to_fraction(x: str) -> str` converting a decimal string with an
optional repeating part in parentheses to a fraction in lowest terms "p/q" with q >= 1.
Examples: "0.5" -> "1/2", "0.(3)" -> "1/3", "0.1(6)" -> "1/6", "2.5" -> "5/2",
"-0.(3)" -> "-1/3", "3" -> "3/1", "1.(9)" -> "2/1", "-0" -> "0/1".
Input matches: optional "-", digits, optionally "." followed by digits and/or a
non-empty "(digits)" group. The sign goes on the numerator; zero is "0/1".
""", """
cases = {"0.5": "1/2", "0.(3)": "1/3", "0.1(6)": "1/6", "2.5": "5/2", "-0.(3)": "-1/3",
         "3": "3/1", "1.(9)": "2/1", "-0": "0/1", "0.(142857)": "1/7", "12.34(56)": "61111/4950",
         "-2.25": "-9/4", "0.(0)": "0/1", "0.0(9)": "1/10", "10": "10/1", "0.125": "1/8"}
for k, v in cases.items():
    assert decimal_to_fraction(k) == v, (k, decimal_to_fraction(k), v)
""", """
from fractions import Fraction

def decimal_to_fraction(x):
    neg = x.startswith("-")
    if neg:
        x = x[1:]
    ip, _, frac = x.partition(".")
    rep = ""
    if "(" in frac:
        frac, rep = frac.split("(")
        rep = rep.rstrip(")")
    f = Fraction(int(ip or "0"))
    if frac:
        f += Fraction(int(frac), 10 ** len(frac))
    if rep:
        f += Fraction(int(rep), (10 ** len(rep) - 1) * 10 ** len(frac))
    if neg:
        f = -f
    return f"{f.numerator}/{f.denominator}"
""")

task("19_top_words", """
Write `top_words(text: str, k: int) -> list[tuple[str, int]]`. A word is a maximal run
of ASCII letters and apostrophes, lowercased, with leading and trailing apostrophes
removed; runs that become empty are ignored. Return the k most frequent words as
(word, count), sorted by count descending, then word ascending. If there are fewer
than k distinct words, return all of them. k >= 0.
""", """
assert top_words("", 3) == []
assert top_words("a b a", 0) == []
assert top_words("The the THE cat", 2) == [("the", 3), ("cat", 1)]
assert top_words("b a c b a", 5) == [("a", 2), ("b", 2), ("c", 1)]
assert top_words("don't Don't 'quoted' ''' rock'n'roll", 10) == [("don't", 2), ("quoted", 1), ("rock'n'roll", 1)]
assert top_words("x1y x-y", 3) == [("x", 2), ("y", 2)]
assert top_words("café cafe", 3) == [("caf", 1), ("cafe", 1)]
""", """
import re
from collections import Counter

def top_words(text, k):
    words = [w.strip("'").lower() for w in re.findall(r"[A-Za-z']+", text)]
    c = Counter(w for w in words if w)
    return sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))[:k]
""")

task("20_decode_ways", """
Write `decode_ways(s: str) -> int`. Letters A-Z are encoded as "1".."26". s contains
digits and '*', where '*' stands for any digit 1-9 (not 0). Return the number of ways
to decode s into letters, modulo 1_000_000_007. Return 0 if s cannot be decoded
(e.g. starts with "0"). len(s) <= 100000; must run in linear time.
""", """
assert decode_ways("12") == 2
assert decode_ways("226") == 3
assert decode_ways("0") == 0
assert decode_ways("06") == 0
assert decode_ways("10") == 1
assert decode_ways("*") == 9
assert decode_ways("1*") == 18
assert decode_ways("2*") == 15
assert decode_ways("**") == 96
assert decode_ways("*0") == 2
assert decode_ways("3*") == 9
assert decode_ways("100") == 0
import time
t = time.perf_counter()
r = decode_ways("*1" * 50000)
assert time.perf_counter() - t < 5.0
assert 0 <= r < 1_000_000_007
""", """
def decode_ways(s):
    M = 1_000_000_007
    def one(c):
        return 9 if c == "*" else (0 if c == "0" else 1)
    def two(a, b):
        if a == "*":
            if b == "*":
                return 15
            return 2 if b <= "6" else 1
        if a == "1":
            return 9 if b == "*" else 1
        if a == "2":
            if b == "*":
                return 6
            return 1 if b <= "6" else 0
        return 0
    prev2, prev1 = 1, one(s[0]) if s else 1
    for i in range(1, len(s)):
        cur = (one(s[i]) * prev1 + two(s[i - 1], s[i]) * prev2) % M
        prev2, prev1 = prev1, cur
    return prev1 % M
""")

TASKS = T
