"""loop-v1: 30 held-out Python tasks, harder than loop-v0 (Roadmap item 2).

Same layout as tasks.py: id, prompt, tests, ref. Written 2026-10-05 after loop-v0 hit
best-of-4 = 100%; none was used for prompt iteration or as a few-shot example.
Harder means: longer specs with more edge rules, parsers with error cases, exact
tie-breaks, and performance limits. Where a task could be solved by a stdlib call
(re, json, codecs, eval), the tests call _banned() (run.py PRELUDE) to reject it.
Most tests compare against a brute-force oracle inside the test on seeded random
inputs, so expected values are not hand-computed.
"""

T = []


def task(id, prompt, tests, ref):
    T.append({"id": id, "prompt": prompt.strip(), "tests": tests.strip(), "ref": ref.strip()})


task("v1_01_regex_match", r'''
Write `regex_match(pattern: str, text: str) -> bool` that returns True if the whole text
matches the pattern. Syntax: any ordinary character matches itself; `.` matches any one
character; `*`, `+`, `?` apply to the preceding atom (zero-or-more, one-or-more,
zero-or-one); an atom is a character, `.`, a bracket class, or a parenthesized group;
`|` is alternation with the lowest precedence (inside a group it is local to the group);
`[abc]` matches one listed character, ranges like `[a-z]` are allowed, `[^...]` negates;
inside brackets every character is literal except a leading `^`, a range `-`, and the
closing `]`; `\` outside brackets makes the next character literal (`\.`, `\*`, `\\`,
`\(`, `\|`, `\[`). Patterns are well-formed: groups and alternatives are non-empty and
a quantifier never follows another quantifier. Do not use the re or fnmatch modules.
Must run in polynomial time (patterns like `(a*)*b` against "aaaa...a" must be fast).
''', r'''
_banned(mods=("re", "fnmatch", "sre_compile", "sre_parse"))
import re, random, time
cases = [("", "", True), ("a", "a", True), ("a", "b", False), ("a.c", "abc", True), ("a.c", "ac", False),
         ("ab*c", "ac", True), ("ab*c", "abbbc", True), ("ab+c", "ac", False), ("ab?c", "abc", True),
         ("ab?c", "abbc", False), ("a|b", "b", True), ("ab|cd", "cd", True), ("ab|cd", "abd", False),
         ("(ab)*", "ababab", True), ("(ab)*", "aba", False), ("(a|b)*c", "abbac", True),
         ("[a-c]+", "abcab", True), ("[a-c]+", "abd", False), ("[^a]b", "cb", True), ("[^a]b", "ab", False),
         (r"a\.b", "a.b", True), (r"a\.b", "axb", False), (r"\*+", "***", True), (r"\(x\)", "(x)", True),
         (r"a\|b", "a|b", True), (r"a\|b", "a", False), ("x(a|bc)?y", "xbcy", True), ("x(a|bc)?y", "xaby", False),
         ("[.]", ".", True), ("[.]", "a", False), ("(a|ab)(c|bcd)(d*)", "abcd", True)]
for p, t, exp in cases:
    assert regex_match(p, t) is exp, (p, t, exp)
random.seed(11)
def gen(d):
    r = random.random()
    if d <= 0 or r < 0.35:
        a = random.choice(["a", "b", ".", "[ab]", "[^a]", "[a-c]"])
    elif r < 0.6:
        a = "(" + gen(d - 1) + ")"
    elif r < 0.8:
        a = gen(d - 1) + gen(d - 1)
        return a
    else:
        return "(" + gen(d - 1) + "|" + gen(d - 1) + ")"
    q = random.choice(["", "", "*", "+", "?"])
    return a + q
for _ in range(400):
    p = gen(3)
    for _ in range(5):
        t = "".join(random.choice("abc") for _ in range(random.randint(0, 6)))
        assert regex_match(p, t) == bool(re.fullmatch(p, t)), (p, t)
t0 = time.perf_counter()
assert regex_match("(a*)*b", "a" * 40) is False
assert regex_match("(a|aa)*c", "a" * 40) is False
assert regex_match("((a+)+)+", "a" * 60) is True
assert time.perf_counter() - t0 < 5.0
''', r'''
def _parse(p):
    pos = 0
    def peek():
        return p[pos] if pos < len(p) else None
    def alt():
        nonlocal pos
        br = [seq()]
        while peek() == "|":
            pos += 1
            br.append(seq())
        return ("alt", br) if len(br) > 1 else br[0]
    def seq():
        items = []
        while peek() is not None and peek() not in "|)":
            items.append(rep())
        return ("seq", items)
    def rep():
        nonlocal pos
        a = atom()
        while peek() is not None and peek() in "*+?":
            a = (p[pos], a)
            pos += 1
        return a
    def atom():
        nonlocal pos
        c = p[pos]
        if c == "(":
            pos += 1
            a = alt()
            pos += 1
            return a
        if c == "[":
            pos += 1
            neg = p[pos] == "^"
            if neg:
                pos += 1
            items = []
            while p[pos] != "]":
                if pos + 2 < len(p) and p[pos + 1] == "-" and p[pos + 2] != "]":
                    items.append((p[pos], p[pos + 2]))
                    pos += 3
                else:
                    items.append((p[pos], p[pos]))
                    pos += 1
            pos += 1
            return ("cls", neg, items)
        if c == ".":
            pos += 1
            return ("any",)
        if c == "\\":
            pos += 1
            c = p[pos]
        pos += 1
        return ("lit", c)
    return alt()

def regex_match(pattern, text):
    tree = _parse(pattern)
    n = len(text)
    def m(node, S):
        k = node[0]
        if k == "lit":
            return {i + 1 for i in S if i < n and text[i] == node[1]}
        if k == "any":
            return {i + 1 for i in S if i < n}
        if k == "cls":
            return {i + 1 for i in S if i < n and (any(a <= text[i] <= b for a, b in node[2]) != node[1])}
        if k == "seq":
            for it in node[1]:
                S = m(it, S)
                if not S:
                    break
            return S
        if k == "alt":
            out = set()
            for b in node[1]:
                out |= m(b, S)
            return out
        if k in "*+":
            res = set(S) if k == "*" else set()
            frontier = set(S)
            while frontier:
                new = m(node[1], frontier) - res
                res |= new
                frontier = new
            return res
        if k == "?":
            return set(S) | m(node[1], S)
    return n in m(tree, {0})
''')

task("v1_02_json_parse", r'''
Write `json_parse(s: str)` implementing strict RFC 8259 JSON. Values: object -> dict
(duplicate keys: last wins), array -> list, string -> str, number -> int if it has no
fraction and no exponent else float, true/false/null -> True/False/None. Whitespace
(space, tab, LF, CR only) may surround any token. Numbers: -?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][+-]?[0-9]+)?
with ASCII digits only. Strings: raw characters below U+0020 are not allowed; escapes
are \" \\ \/ \b \f \n \r \t and \uXXXX (hex, either case); a high surrogate escape
followed by a low surrogate escape combines into one character, any other surrogate
escape becomes that single code point. Raise ValueError for anything else, including
empty input, trailing non-whitespace, NaN/Infinity, leading zeros, trailing commas,
single quotes. Do not use the json or ast modules, eval or exec.
''', r'''
_banned(mods=("json", "ast", "simplejson"), names=("eval", "exec", "compile"))
import json, random
assert json_parse("0") == 0 and type(json_parse("0")) is int
assert json_parse("-0.0") == 0.0 and type(json_parse("-0.0")) is float
assert json_parse("1E2") == 100.0 and type(json_parse("1E2")) is float
assert json_parse(" [1, 2.5, \"x\", true, false, null] ") == [1, 2.5, "x", True, False, None]
assert json_parse('{"a": 1, "a": 2}') == {"a": 2}
assert json_parse('"\\ud83d\\ude00"') == "\U0001F600"
assert json_parse('"\\ud800"') == "\ud800"
assert json_parse('"\\ud800\\u0041"') == "\ud800A"
assert json_parse('"\\u00E9\\/\\b\\f\\n\\r\\t\\"\\\\"') == "é/\b\f\n\r\t\"\\"
assert json_parse("12345678901234567890") == 12345678901234567890
assert json_parse('{"k": {"n": [[], {}]}}') == {"k": {"n": [[], {}]}}
bad = ["", " ", "01", "1.", ".5", "+1", "-", "1e", "1e+", "[1,]", '{"a":1,}', "{'a':1}", "tru", "nul",
       '"\\x41"', '"a\tb"', "[1] x", "NaN", "Infinity", "-Infinity", '"\\u12"', '"\\u12G4"', '{"a" 1}', "[",
       '"abc', "[1 2]", '{"a":}', "{1:2}", " 1", "1 ", "0x10", "--1", "[,]", '{"a":1 "b":2}']
for b in bad:
    try:
        json_parse(b)
    except ValueError:
        pass
    else:
        raise AssertionError(repr(b))
random.seed(5)
def rstr():
    pool = "ab\"\\/\b\f\n\r\t\x01\x1f é中\U0001F600𐀀"
    return "".join(random.choice(pool) for _ in range(random.randint(0, 8)))
def rval(d):
    r = random.random()
    if d <= 0 or r < 0.4:
        return random.choice([random.randint(-10**20, 10**20), random.uniform(-1e6, 1e6), random.random() * 1e-7,
                              True, False, None, rstr()])
    if r < 0.7:
        return [rval(d - 1) for _ in range(random.randint(0, 4))]
    return {rstr(): rval(d - 1) for _ in range(random.randint(0, 4))}
for _ in range(400):
    v = rval(4)
    for kw in ({}, {"ensure_ascii": False}, {"indent": 2}, {"separators": (",", ":")}, {"indent": "\t", "ensure_ascii": False}):
        s = json.dumps(v, **kw)
        assert json_parse(s) == json.loads(s), s
''', r'''
_WS = " \t\n\r"
_ESC = {'"': '"', "\\": "\\", "/": "/", "b": "\b", "f": "\f", "n": "\n", "r": "\r", "t": "\t"}
_HEX = "0123456789abcdefABCDEF"
_DIG = "0123456789"

def json_parse(s):
    i = 0
    n = len(s)
    def ws():
        nonlocal i
        while i < n and s[i] in _WS:
            i += 1
    def value():
        nonlocal i
        ws()
        if i >= n:
            raise ValueError("eof")
        c = s[i]
        if c == "{":
            return obj()
        if c == "[":
            return arr()
        if c == '"':
            return string()
        for lit, v in (("true", True), ("false", False), ("null", None)):
            if s.startswith(lit, i):
                i += len(lit)
                return v
        return number()
    def obj():
        nonlocal i
        i += 1
        d = {}
        ws()
        if i < n and s[i] == "}":
            i += 1
            return d
        while True:
            ws()
            if i >= n or s[i] != '"':
                raise ValueError("key")
            k = string()
            ws()
            if i >= n or s[i] != ":":
                raise ValueError("colon")
            i += 1
            d[k] = value()
            ws()
            if i < n and s[i] == ",":
                i += 1
                continue
            if i < n and s[i] == "}":
                i += 1
                return d
            raise ValueError("object")
    def arr():
        nonlocal i
        i += 1
        out = []
        ws()
        if i < n and s[i] == "]":
            i += 1
            return out
        while True:
            out.append(value())
            ws()
            if i < n and s[i] == ",":
                i += 1
                continue
            if i < n and s[i] == "]":
                i += 1
                return out
            raise ValueError("array")
    def hex4():
        nonlocal i
        h = s[i:i + 4]
        if len(h) < 4 or any(c not in _HEX for c in h):
            raise ValueError("hex")
        i += 4
        return int(h, 16)
    def string():
        nonlocal i
        i += 1
        out = []
        while True:
            if i >= n:
                raise ValueError("unterminated")
            c = s[i]
            if c == '"':
                i += 1
                return "".join(out)
            if c == "\\":
                i += 1
                if i >= n:
                    raise ValueError("escape")
                e = s[i]
                i += 1
                if e in _ESC:
                    out.append(_ESC[e])
                elif e == "u":
                    cp = hex4()
                    if 0xD800 <= cp <= 0xDBFF and s.startswith("\\u", i):
                        save = i
                        i += 2
                        lo = hex4()
                        if 0xDC00 <= lo <= 0xDFFF:
                            cp = 0x10000 + ((cp - 0xD800) << 10) + (lo - 0xDC00)
                        else:
                            i = save
                    out.append(chr(cp))
                else:
                    raise ValueError("escape")
            elif ord(c) < 0x20:
                raise ValueError("control")
            else:
                out.append(c)
                i += 1
    def digits():
        nonlocal i
        st = i
        while i < n and s[i] in _DIG:
            i += 1
        if i == st:
            raise ValueError("digits")
    def number():
        nonlocal i
        st = i
        if s[i] == "-":
            i += 1
        if i < n and s[i] == "0":
            i += 1
        elif i < n and s[i] in "123456789":
            digits()
        else:
            raise ValueError("number")
        isf = False
        if i < n and s[i] == ".":
            i += 1
            digits()
            isf = True
        if i < n and s[i] in "eE":
            i += 1
            if i < n and s[i] in "+-":
                i += 1
            digits()
            isf = True
        t = s[st:i]
        return float(t) if isf else int(t)
    v = value()
    ws()
    if i != n:
        raise ValueError("trailing")
    return v
''')

task("v1_03_utf8_decode", r'''
Write `utf8_decode(b: bytes) -> str` decoding UTF-8 with replacement. Well-formed
sequences follow Unicode Table 3-7: 00-7F; C2-DF + 80-BF; E0 + A0-BF + 80-BF;
E1-EC or EE-EF + 80-BF + 80-BF; ED + 80-9F + 80-BF; F0 + 90-BF + 80-BF + 80-BF;
F1-F3 + 80-BF x3; F4 + 80-8F + 80-BF + 80-BF. On an ill-formed sequence, replace the
maximal subpart (the longest prefix of a well-formed sequence that was read before
the error, or the single offending byte if no well-formed sequence starts there) with
one U+FFFD and continue with the next byte after that subpart. A truncated sequence at
the end is one U+FFFD. Do not use bytes.decode, str(bytes, ...), codecs or io.
''', r'''
_banned(mods=("codecs", "io", "encodings"), attrs=("decode",))
import ast as _a2
for _n in _a2.walk(_a2.parse(open("solution.py").read())):
    if isinstance(_n, _a2.Call) and isinstance(_n.func, _a2.Name) and _n.func.id in ("str", "bytes"):
        assert len(_n.args) <= 1 and not _n.keywords, "str(bytes, encoding) is banned"
import random
fixed = [b"", b"abc", "é中\U0001F600".encode(), b"\xc0\xaf", b"\xe0\x80\xaf", b"\xed\xa0\x80",
         b"\xf4\x90\x80\x80", b"\xf0\x80\x80\x41", b"\xe2\x82", b"\xe2\x82\x41", b"\xff\xfe", b"\xc2",
         b"\xf1\x80\x80", b"\x80\x80", b"a\xf0\x9f\x98", b"\xef\xbf\xbf", b"\xf4\x8f\xbf\xbf"]
for b in fixed:
    assert utf8_decode(b) == b.decode("utf-8", "replace"), b
assert utf8_decode(b"\xf0\x80\x80\x41") == "���A"
assert utf8_decode(b"\xe2\x82\x41") == "�A"
random.seed(3)
interesting = [0x00, 0x41, 0x7f, 0x80, 0x8f, 0x90, 0x9f, 0xa0, 0xbf, 0xc0, 0xc1, 0xc2, 0xdf, 0xe0, 0xe1,
               0xec, 0xed, 0xee, 0xef, 0xf0, 0xf1, 0xf3, 0xf4, 0xf5, 0xff]
for _ in range(20000):
    b = bytes(random.choice(interesting) for _ in range(random.randint(0, 8)))
    assert utf8_decode(b) == b.decode("utf-8", "replace"), b
for _ in range(300):
    s = "".join(chr(random.choice([random.randint(0, 0x7f), random.randint(0x80, 0x7ff), random.randint(0x800, 0xd7ff),
                                   random.randint(0xe000, 0xffff), random.randint(0x10000, 0x10ffff)])) for _ in range(20))
    assert utf8_decode(s.encode()) == s
''', r'''
def utf8_decode(b):
    out = []
    i = 0
    n = len(b)
    while i < n:
        x = b[i]
        if x < 0x80:
            out.append(chr(x))
            i += 1
            continue
        if 0xC2 <= x <= 0xDF:
            need, lo, hi = 1, 0x80, 0xBF
        elif x == 0xE0:
            need, lo, hi = 2, 0xA0, 0xBF
        elif 0xE1 <= x <= 0xEC or 0xEE <= x <= 0xEF:
            need, lo, hi = 2, 0x80, 0xBF
        elif x == 0xED:
            need, lo, hi = 2, 0x80, 0x9F
        elif x == 0xF0:
            need, lo, hi = 3, 0x90, 0xBF
        elif 0xF1 <= x <= 0xF3:
            need, lo, hi = 3, 0x80, 0xBF
        elif x == 0xF4:
            need, lo, hi = 3, 0x80, 0x8F
        else:
            out.append("�")
            i += 1
            continue
        cp = x & (0x1F if need == 1 else 0x0F if need == 2 else 0x07)
        j = i + 1
        ok = True
        for k in range(need):
            if j >= n:
                ok = False
                break
            y = b[j]
            l, h = (lo, hi) if k == 0 else (0x80, 0xBF)
            if not l <= y <= h:
                ok = False
                break
            cp = (cp << 6) | (y & 0x3F)
            j += 1
        out.append(chr(cp) if ok else "�")
        i = j
    return "".join(out)
''')

task("v1_04_cron_next", r'''
Write `cron_next(expr: str, after: datetime.datetime) -> datetime.datetime | None` for
5-field cron expressions "minute hour day-of-month month day-of-week" separated by
whitespace. Ranges: minute 0-59, hour 0-23, day-of-month 1-31, month 1-12, day-of-week
0-7 (0 and 7 are Sunday, 1 is Monday). Each field is a comma-separated list of items;
an item is `*`, `n`, or `a-b` (a <= b), optionally followed by `/s` (step s >= 1);
`*/s` steps over the whole range, `n/s` means n to the field maximum stepping by s.
Only ASCII digits; no names. A field is "restricted" unless its text starts with `*`.
If both day-of-month and day-of-week are restricted, a day matches when EITHER
matches; otherwise both must match. Return the earliest matching time (seconds 0) that
is strictly later than `after` and not later than `after + 3000 days`; else None.
Raise ValueError for a malformed expression or out-of-range value. Naive datetimes.
''', r'''
from datetime import datetime, timedelta
import random
D = datetime
assert cron_next("*/15 * * * *", D(2026, 1, 1, 10, 7)) == D(2026, 1, 1, 10, 15)
assert cron_next("* * * * *", D(2026, 10, 5, 10, 0, 30)) == D(2026, 10, 5, 10, 1)
assert cron_next("* * * * *", D(2026, 10, 5, 10, 0)) == D(2026, 10, 5, 10, 1)
assert cron_next("0 0 1 1 *", D(2026, 1, 1, 0, 0)) == D(2027, 1, 1, 0, 0)
assert cron_next("0 0 29 2 *", D(2026, 3, 1)) == D(2028, 2, 29)
assert cron_next("0 0 30 2 *", D(2026, 3, 1)) is None
assert cron_next("30 9 * * 1-5", D(2026, 10, 9, 10, 0)) == D(2026, 10, 12, 9, 30)
assert cron_next("0 0 13 * 5", D(2026, 10, 5)) == D(2026, 10, 9)
assert cron_next("0 0 */2 * 5", D(2026, 10, 10)) == D(2026, 10, 23)
assert cron_next("0 12 * * 7", D(2026, 10, 5)) == D(2026, 10, 11, 12, 0)
assert cron_next("5/20 1-3/2 * * *", D(2026, 10, 5, 1, 45)) == D(2026, 10, 5, 3, 5)
assert cron_next("0 0 31 * *", D(2026, 4, 1)) == D(2026, 5, 31)
assert cron_next("59 23 31 12 *", D(2026, 12, 31, 23, 59)) == D(2027, 12, 31, 23, 59)
for bad in ["60 * * * *", "* * * *", "* * * * * *", "*/0 * * * *", "5-1 * * * *", "* * 0 * *", "a * * * *",
            "1,,2 * * * *", "* * * 13 *", "* * * * 8", "", "-1 * * * *", "1- * * * *", "*/ * * * *", "1/2/3 * * * *"]:
    try:
        cron_next(bad, D(2026, 1, 1))
    except ValueError:
        pass
    else:
        raise AssertionError(bad)
# brute force: minute by minute over a short horizon
def bf_field(t, lo, hi):
    out = set()
    for item in t.split(","):
        base, _, st = item.partition("/")
        st = int(st) if st else 1
        if base == "*":
            a, b = lo, hi
        elif "-" in base:
            a, b = map(int, base.split("-"))
        else:
            a = int(base)
            b = hi if "/" in item else a
        out |= set(range(a, b + 1, st))
    return out
def brute(expr, after, horizon_days):
    f = expr.split()
    mi, ho, dm, mo, dw = [bf_field(x, lo, hi) for x, (lo, hi) in zip(f, [(0, 59), (0, 23), (1, 31), (1, 12), (0, 7)])]
    if 7 in dw:
        dw.add(0)
    t = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    end = after + timedelta(days=horizon_days)
    while t <= end:
        a, b = t.day in dm, (t.isoweekday() % 7) in dw
        day = (a or b) if not (f[2].startswith("*") or f[4].startswith("*")) else (a and b)
        if t.minute in mi and t.hour in ho and t.month in mo and day:
            return t
        t += timedelta(minutes=1)
    return None
random.seed(9)
def item(lo, hi):
    r = random.random()
    if r < 0.4:
        return "*" if random.random() < 0.5 else "*/" + str(random.randint(1, 5))
    a = random.randint(lo, hi)
    if r < 0.7:
        return str(a)
    b = random.randint(a, hi)
    return f"{a}-{b}" + (f"/{random.randint(1, 3)}" if random.random() < 0.4 else "")
for _ in range(40):
    fields = [item(0, 59), item(0, 23), item(1, 31), "*" if random.random() < 0.7 else item(1, 12), item(0, 7)]
    expr = " ".join(fields)
    after = D(2026, random.randint(1, 12), random.randint(1, 28), random.randint(0, 23), random.randint(0, 59), random.randint(0, 59))
    exp = brute(expr, after, 20)
    if exp is not None:
        assert cron_next(expr, after) == exp, (expr, after)
''', r'''
from datetime import datetime, timedelta

_RANGES = [(0, 59), (0, 23), (1, 31), (1, 12), (0, 7)]

def _num(s):
    if not s or any(c not in "0123456789" for c in s):
        raise ValueError(s)
    return int(s)

def _field(text, lo, hi):
    if text == "":
        raise ValueError("empty field")
    vals = set()
    for item in text.split(","):
        base, sep, step = item.partition("/")
        st = _num(step) if sep else 1
        if st < 1:
            raise ValueError("step")
        if base == "*":
            a, b = lo, hi
        elif "-" in base:
            x, _, y = base.partition("-")
            a, b = _num(x), _num(y)
            if a > b:
                raise ValueError("range")
        else:
            a = _num(base)
            b = hi if sep else a
        if a < lo or b > hi:
            raise ValueError("out of range")
        vals.update(range(a, b + 1, st))
    return vals

def cron_next(expr, after):
    parts = expr.split()
    if len(parts) != 5:
        raise ValueError("need 5 fields")
    mins, hours, doms, mons, dows = [_field(p, lo, hi) for p, (lo, hi) in zip(parts, _RANGES)]
    if 7 in dows:
        dows = dows | {0}
    either = not (parts[2].startswith("*") or parts[4].startswith("*"))
    start = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    limit = after + timedelta(days=3000)
    d = start.date()
    hs, ms = sorted(hours), sorted(mins)
    while datetime(d.year, d.month, d.day) <= limit:
        if d.month in mons:
            a, b = d.day in doms, (d.isoweekday() % 7) in dows
            if (a or b) if either else (a and b):
                for h in hs:
                    for m in ms:
                        t = datetime(d.year, d.month, d.day, h, m)
                        if t > limit:
                            return None
                        if t >= start:
                            return t
        d += timedelta(days=1)
    return None
''')

task("v1_05_calendar_k", r'''
Write a class `Calendar` with `__init__(self, k: int)` (k >= 1) and
`book(self, start: int, end: int) -> bool` for half-open intervals [start, end),
start < end. A booking is accepted (stored, returns True) only if after adding it no
point is covered by more than k stored bookings; otherwise it is rejected (not stored,
returns False). 1000 bookings must complete in under 5 seconds.
''', r'''
import random, time
c = Calendar(2)
assert [c.book(*x) for x in [(10, 20), (50, 60), (10, 40), (5, 15), (5, 10), (25, 55)]] == [True, True, True, False, True, True]
c = Calendar(1)
assert c.book(1, 2) and c.book(2, 3) and not c.book(1, 3) and c.book(0, 1)
random.seed(4)
for k in (1, 2, 3):
    for _ in range(60):
        c = Calendar(k)
        cov = [0] * 60
        for _ in range(25):
            s = random.randint(0, 58)
            e = random.randint(s + 1, min(60, s + 15))
            ok = all(cov[x] + 1 <= k for x in range(s, e))
            assert c.book(s, e) == ok, (k, s, e)
            if ok:
                for x in range(s, e):
                    cov[x] += 1
c = Calendar(3)
t = time.perf_counter()
for i in range(1000):
    s = random.randint(0, 10**6)
    c.book(s, s + random.randint(1, 5000))
assert time.perf_counter() - t < 5.0
''', r'''
import bisect

class Calendar:
    def __init__(self, k):
        self.k = k
        self.xs = []      # sorted breakpoints
        self.cnt = {}     # coverage on [xs[i], xs[i+1])

    def _split(self, x):
        i = bisect.bisect_left(self.xs, x)
        if i < len(self.xs) and self.xs[i] == x:
            return
        prev = self.cnt[self.xs[i - 1]] if i > 0 else 0
        self.xs.insert(i, x)
        self.cnt[x] = prev

    def book(self, start, end):
        self._split(start)
        self._split(end)
        i = bisect.bisect_left(self.xs, start)
        j = bisect.bisect_left(self.xs, end)
        seg = self.xs[i:j]
        if any(self.cnt[x] + 1 > self.k for x in seg):
            return False
        for x in seg:
            self.cnt[x] += 1
        return True
''')

task("v1_06_sudoku_solve", r'''
Write `sudoku_solve(board: list[str]) -> list[str] | None`. board is 9 strings of 9
characters, '1'-'9' or '.'. Return a completed board (9 strings of digits) that keeps
every given digit and has no repeated digit in any row, column or 3x3 box, or None if
the givens already conflict or no completion exists. If several completions exist,
return any. Every test puzzle must be solved within 10 seconds in total, including
very hard ones.
''', r'''
import time
def ok(p, r):
    if r is None or len(r) != 9 or any(len(x) != 9 for x in r):
        return False
    for i in range(9):
        for j in range(9):
            if p[i][j] != "." and p[i][j] != r[i][j]:
                return False
    groups = [r[i] for i in range(9)] + ["".join(r[i][j] for i in range(9)) for j in range(9)]
    groups += ["".join(r[i][j] for i in range(a, a + 3) for j in range(b, b + 3)) for a in (0, 3, 6) for b in (0, 3, 6)]
    return all(sorted(g) == list("123456789") for g in groups)
puzzles = [
    ["53..7....", "6..195...", ".98....6.", "8...6...3", "4..8.3..1", "7...2...6", ".6....28.", "...419..5", "....8..79"],
    ["8........", "..36.....", ".7..9.2..", ".5...7...", "....457..", "...1...3.", "..1....68", "..85...1.", ".9....4.."],
    ["." * 9] * 9,
]
import random
random.seed(17)
for _ in range(6):
    perm = list("123456789")
    random.shuffle(perm)
    full = [[perm[(r * 3 + r // 3 + c) % 9] for c in range(9)] for r in range(9)]
    holes = random.sample(range(81), 58)
    for h in holes:
        full[h // 9][h % 9] = "."
    puzzles.append(["".join(row) for row in full])
t = time.perf_counter()
for p in puzzles:
    assert ok(p, sudoku_solve(p)), p
unsolvable = ["12345678.", "........9", ".........", ".........", ".........", ".........", ".........", ".........", "........."]
assert sudoku_solve(unsolvable) is None
conflict = ["11.......", ".........", ".........", ".........", ".........", ".........", ".........", ".........", "........."]
assert sudoku_solve(conflict) is None
hard_none = ["..9.287..", "8.6..4..5", "..3.....4", "6........", ".2.71345.", "........2", "3.....5..", "9..4..8.7", "..125.3.."]
r = sudoku_solve(hard_none)
assert r is None or ok(hard_none, r)
assert time.perf_counter() - t < 10.0
''', r'''
def sudoku_solve(board):
    cells = [[0 if ch == "." else int(ch) for ch in row] for row in board]
    rows = [0] * 9
    cols = [0] * 9
    boxes = [0] * 9
    empty = []
    for i in range(9):
        for j in range(9):
            v = cells[i][j]
            if v:
                bit = 1 << v
                b = (i // 3) * 3 + j // 3
                if rows[i] & bit or cols[j] & bit or boxes[b] & bit:
                    return None
                rows[i] |= bit
                cols[j] |= bit
                boxes[b] |= bit
            else:
                empty.append((i, j))
    FULL = 0b1111111110
    def solve():
        best = None
        best_opts = None
        for (i, j) in empty:
            if cells[i][j]:
                continue
            opts = FULL & ~(rows[i] | cols[j] | boxes[(i // 3) * 3 + j // 3])
            c = bin(opts).count("1")
            if c == 0:
                return False
            if best is None or c < best_c:
                best, best_opts, best_c = (i, j), opts, c
                if c == 1:
                    break
        if best is None:
            return True
        i, j = best
        b = (i // 3) * 3 + j // 3
        for v in range(1, 10):
            bit = 1 << v
            if best_opts & bit:
                cells[i][j] = v
                rows[i] |= bit
                cols[j] |= bit
                boxes[b] |= bit
                if solve():
                    return True
                rows[i] &= ~bit
                cols[j] &= ~bit
                boxes[b] &= ~bit
                cells[i][j] = 0
        return False
    if not solve():
        return None
    return ["".join(str(v) for v in row) for row in cells]
''')

task("v1_07_min_semesters", r'''
Write `min_semesters(n: int, relations: list[list[int]], k: int) -> int`. Courses are
1..n (n <= 13). relations[i] = [a, b] means course a must be completed in an earlier
semester than course b. The prerequisite graph has no cycles. In one semester you may
take at most k courses whose prerequisites were all completed in earlier semesters.
Return the minimum number of semesters to take all courses. Must finish n = 13 cases
within a few seconds.
''', r'''
import random, time
from itertools import combinations
assert min_semesters(4, [[2, 1], [3, 1], [1, 4]], 2) == 3
assert min_semesters(5, [[2, 1], [3, 1], [4, 1], [1, 5]], 2) == 4
assert min_semesters(1, [], 1) == 1
assert min_semesters(3, [], 3) == 1
assert min_semesters(3, [], 2) == 2
def brute(n, rel, k):
    pre = [0] * n
    for a, b in rel:
        pre[b - 1] |= 1 << (a - 1)
    full = (1 << n) - 1
    frontier = {0}
    seen = {0}
    sem = 0
    while full not in frontier:
        sem += 1
        nxt = set()
        for m in frontier:
            av = [i for i in range(n) if not m >> i & 1 and pre[i] & m == pre[i]]
            for r in range(1, min(k, len(av)) + 1):
                for c in combinations(av, r):
                    mm = m
                    for i in c:
                        mm |= 1 << i
                    if mm not in seen:
                        seen.add(mm)
                        nxt.add(mm)
        frontier = nxt
    return sem
random.seed(2)
for _ in range(150):
    n = random.randint(1, 8)
    rel = [[a, b] for a in range(1, n + 1) for b in range(a + 1, n + 1) if random.random() < 0.25]
    perm = list(range(1, n + 1))
    random.shuffle(perm)
    rel = [[perm[a - 1], perm[b - 1]] for a, b in rel]
    k = random.randint(1, 4)
    assert min_semesters(n, rel, k) == brute(n, rel, k), (n, rel, k)
t = time.perf_counter()
rel = [[a, b] for a in range(1, 14) for b in range(a + 1, 14) if (a * 7 + b * 3) % 11 == 0]
r = min_semesters(13, rel, 3)
assert r == brute(13, rel, 3)
assert time.perf_counter() - t < 20.0
''', r'''
from itertools import combinations

def min_semesters(n, relations, k):
    pre = [0] * n
    for a, b in relations:
        pre[b - 1] |= 1 << (a - 1)
    full = (1 << n) - 1
    dist = {0: 0}
    frontier = [0]
    sem = 0
    while True:
        if full in dist:
            return dist[full]
        sem += 1
        nxt = []
        for m in frontier:
            av = [i for i in range(n) if not m >> i & 1 and pre[i] & m == pre[i]]
            choices = [av] if len(av) <= k else combinations(av, k)
            for c in choices:
                mm = m
                for i in c:
                    mm |= 1 << i
                if mm not in dist:
                    dist[mm] = sem
                    nxt.append(mm)
        frontier = nxt
''')

task("v1_08_poly_expand", r'''
Write `poly_expand(expr: str) -> str` that expands a polynomial in x with integer
coefficients. Grammar (spaces allowed between tokens):
  expr := term (('+' | '-') term)* ;  term := unary ('*' unary)* ;
  unary := '-' unary | power ;  power := atom ('^' INT)? ;  atom := INT | 'x' | '(' expr ')'
INT is a non-negative decimal integer; the exponent is an INT literal <= 20 (so -x^2
is -(x^2) and x^2^3 is invalid). Multiplication must be explicit ("2x" is invalid).
Output: terms in descending degree, separated by " + " or " - "; a negative leading
term starts with "-" and no space; coefficient 1 is omitted for degree >= 1 ("x",
"-x^3"); degree 1 is written "x", degree 0 is just the number; the zero polynomial is
"0". Examples: "(x+1)^2" -> "x^2 + 2x + 1", "x*(x-1) - x^2" -> "-x", "2*3^2" -> "18".
Raise ValueError for malformed input. Do not use eval, exec, compile, ast or sympy.
''', r'''
_banned(mods=("ast", "sympy"), names=("eval", "exec", "compile"))
import random
from fractions import Fraction
fixed = {"(x+1)^2": "x^2 + 2x + 1", "x*(x-1) - x^2": "-x", "2*3^2": "18", "-x^2": "-x^2", "(-x)^2": "x^2",
         "x - x": "0", "(x-1)^3": "x^3 - 3x^2 + 3x - 1", "-(2*x - 3)": "-2x + 3", "  x ^ 0 ": "1", "0*x": "0",
         "-1": "-1", "x": "x", "--x": "x", "3*x^2*x": "3x^3", "(2*x+3)*(2*x-3)": "4x^2 - 9", "-x + 1": "-x + 1",
         "x^10 - 1": "x^10 - 1", "10*x - 10": "10x - 10", "0": "0", "(x)": "x"}
for k, v in fixed.items():
    assert poly_expand(k) == v, (k, poly_expand(k), v)
for bad in ["", "2x", "x^", "x^-1", "x^x", "(x", "x)", "+x", "x**2", "y", "x^2^2", "x^(2)", "2 3", "x*", "()", "x^21"]:
    try:
        poly_expand(bad)
    except ValueError:
        pass
    else:
        raise AssertionError(bad)
def fmt(c):
    terms = [(d, c[d]) for d in sorted(c, reverse=True) if c[d]]
    if not terms:
        return "0"
    out = ""
    for idx, (d, a) in enumerate(terms):
        mag = abs(a)
        body = ("" if mag == 1 and d >= 1 else str(mag)) + ("" if d == 0 else "x" if d == 1 else "x^" + str(d))
        if idx == 0:
            out = ("-" if a < 0 else "") + body
        else:
            out += (" - " if a < 0 else " + ") + body
    return out
random.seed(8)
def gen(dep, budget):
    r = random.random()
    if dep <= 0 or r < 0.3:
        return random.choice(["x", str(random.randint(0, 9))]), None
    if r < 0.5:
        a, _ = gen(dep - 1, budget)
        b, _ = gen(dep - 1, budget)
        return "(" + a + random.choice([" + ", " - ", "-", "+"]) + b + ")", None
    if r < 0.75:
        a, _ = gen(dep - 1, budget)
        b, _ = gen(dep - 1, budget)
        return a + " * " + b, None
    if r < 0.88:
        a, _ = gen(dep - 1, budget)
        return "(" + a + ")^" + str(random.randint(0, 3)), None
    a, _ = gen(dep - 1, budget)
    return "-" + a if not a.startswith("-") else "-(" + a + ")", None
def deg_ok(s):
    return s.count("x") <= 4 and s.count("^") <= 1   # degree <= 4 * 3 = 12 < 25 points
def value(s, xv):
    return eval(s.replace("^", "**"), {"x": xv})
for _ in range(300):
    s, _ = gen(4, 0)
    if not deg_ok(s):
        continue
    pts = list(range(-12, 13))
    ys = [Fraction(value(s, p)) for p in pts]
    # Newton interpolation -> exact coefficients
    n = len(pts)
    coef = ys[:]
    for j in range(1, n):
        for i in range(n - 1, j - 1, -1):
            coef[i] = (coef[i] - coef[i - 1]) / (pts[i] - pts[i - j])
    poly = [Fraction(0)] * n
    basis = [Fraction(1)]
    for j in range(n):
        for d, b in enumerate(basis):
            poly[d] += coef[j] * b
        nb = [Fraction(0)] * (len(basis) + 1)
        for d, b in enumerate(basis):
            nb[d + 1] += b
            nb[d] -= b * pts[j]
        basis = nb
    c = {d: int(v) for d, v in enumerate(poly) if v}
    assert poly_expand(s) == fmt(c), (s, poly_expand(s), fmt(c))
''', r'''
def _tokens(s):
    toks = []
    i = 0
    while i < len(s):
        c = s[i]
        if c.isspace():
            i += 1
        elif c in "0123456789":
            j = i
            while j < len(s) and s[j] in "0123456789":
                j += 1
            toks.append(("int", int(s[i:j])))
            i = j
        elif c in "+-*^()x":
            toks.append((c, None))
            i += 1
        else:
            raise ValueError("bad char " + c)
    return toks

def _add(a, b, sign=1):
    out = dict(a)
    for d, v in b.items():
        out[d] = out.get(d, 0) + sign * v
    return {d: v for d, v in out.items() if v}

def _mul(a, b):
    out = {}
    for d1, v1 in a.items():
        for d2, v2 in b.items():
            out[d1 + d2] = out.get(d1 + d2, 0) + v1 * v2
    return {d: v for d, v in out.items() if v}

def poly_expand(expr):
    toks = _tokens(expr)
    pos = 0
    def peek():
        return toks[pos][0] if pos < len(toks) else None
    def take(kind):
        nonlocal pos
        if peek() != kind:
            raise ValueError("expected " + kind)
        pos += 1
        return toks[pos - 1][1]
    def e():
        v = t()
        while peek() in ("+", "-"):
            sign = 1 if peek() == "+" else -1
            take(peek())
            v = _add(v, t(), sign)
        return v
    def t():
        v = u()
        while peek() == "*":
            take("*")
            v = _mul(v, u())
        return v
    def u():
        if peek() == "-":
            take("-")
            return {d: -c for d, c in u().items()}
        return pw()
    def pw():
        v = atom()
        if peek() == "^":
            take("^")
            k = take("int")
            if k > 20:
                raise ValueError("exponent")
            r = {0: 1}
            for _ in range(k):
                r = _mul(r, v)
            v = r
        return v
    def atom():
        k = peek()
        if k == "int":
            n = take("int")
            return {0: n} if n else {}
        if k == "x":
            take("x")
            return {1: 1}
        if k == "(":
            take("(")
            v = e()
            take(")")
            return v
        raise ValueError("atom")
    poly = e()
    if pos != len(toks):
        raise ValueError("trailing")
    terms = sorted(poly.items(), reverse=True)
    if not terms:
        return "0"
    out = ""
    for idx, (d, a) in enumerate(terms):
        mag = abs(a)
        body = ("" if mag == 1 and d >= 1 else str(mag)) + ("" if d == 0 else "x" if d == 1 else "x^" + str(d))
        if idx == 0:
            out = ("-" if a < 0 else "") + body
        else:
            out += (" - " if a < 0 else " + ") + body
    return out
''')

task("v1_09_rational_eval", r'''
Write `rational_eval(expr: str) -> str` that evaluates an expression exactly over the
rationals. Grammar (spaces allowed between tokens):
  expr := term (('+' | '-') term)* ;  term := unary (('*' | '/') unary)* ;
  unary := '-' unary | power ;  power := atom ('^' unary)? ;  atom := INT | '(' expr ')'
So ^ is right-associative and binds tighter than unary minus (-2^2 = -4, 2^-1 = 1/2,
2^3^2 = 512). The exponent must evaluate to an integer (else ValueError); 0^0 = 1.
Return "p" for an integer or "p/q" in lowest terms with q > 1 (sign on p).
Raise ZeroDivisionError for division by zero or 0 to a negative power, ValueError for
malformed input. Do not use eval, exec, compile or ast.
''', r'''
_banned(mods=("ast",), names=("eval", "exec", "compile"))
import random
from fractions import Fraction
fixed = {"1 + 2 * 3": "7", "(1+2)*3": "9", "1/3 + 1/6": "1/2", "2^3^2": "512", "(2^3)^2": "64", "-2^2": "-4",
         "(-2)^2": "4", "2^-1": "1/2", "2^-2^2": "1/16", "2*-3": "-6", "6/4": "3/2", "1-1/2-1/4": "1/4",
         "8/4/2": "1", "(1/2)^-2": "4", "0^0": "1", "-(3)": "-3", "--3": "3", "7/-14": "-1/2", "4^(1/1)": "4",
         "(2/3)^3": "8/27", "  10  ": "10", "-0": "0", "1/3*3": "1"}
for k, v in fixed.items():
    assert rational_eval(k) == v, (k, rational_eval(k), v)
for bad in ["", "1+", "2^(1/2)", "()", "1 2", "1/", "^2", "2^", "+1", "1.5", "(1", "1)", "2**3", "a"]:
    try:
        rational_eval(bad)
    except ValueError:
        pass
    else:
        raise AssertionError(bad)
for z in ["1/0", "0^-1", "1/(2-2)", "(1-1)^-2"]:
    try:
        rational_eval(z)
    except ZeroDivisionError:
        pass
    else:
        raise AssertionError(z)
random.seed(6)
def gen(d):
    if d <= 0 or random.random() < 0.3:
        n = random.randint(0, 12)
        return str(n), Fraction(n)
    op = random.choice("+-*/^")
    a, va = gen(d - 1)
    if op == "^":
        k = random.randint(-3, 3)
        if va == 0 and k < 0:
            k = -k
        return f"({a})^({k})", va ** k
    b, vb = gen(d - 1)
    if op == "/" and vb == 0:
        return f"({a})+({b})", va + vb
    v = {"+": va + vb, "-": va - vb, "*": va * vb, "/": va / vb if vb else None}[op]
    return f"({a}){op}({b})", v
def show(f):
    return str(f.numerator) if f.denominator == 1 else f"{f.numerator}/{f.denominator}"
for _ in range(500):
    s, v = gen(4)
    assert rational_eval(s) == show(v), s
''', r'''
from fractions import Fraction

def _tokens(s):
    toks = []
    i = 0
    while i < len(s):
        c = s[i]
        if c.isspace():
            i += 1
        elif c in "0123456789":
            j = i
            while j < len(s) and s[j] in "0123456789":
                j += 1
            toks.append(s[i:j])
            i = j
        elif c in "+-*/^()":
            toks.append(c)
            i += 1
        else:
            raise ValueError("bad char")
    return toks

def rational_eval(expr):
    toks = _tokens(expr)
    pos = 0
    def peek():
        return toks[pos] if pos < len(toks) else None
    def take():
        nonlocal pos
        pos += 1
        return toks[pos - 1]
    def e():
        v = t()
        while peek() in ("+", "-"):
            op = take()
            r = t()
            v = v + r if op == "+" else v - r
        return v
    def t():
        v = u()
        while peek() in ("*", "/"):
            op = take()
            r = u()
            if op == "/":
                if r == 0:
                    raise ZeroDivisionError("division by zero")
                v = v / r
            else:
                v = v * r
        return v
    def u():
        if peek() == "-":
            take()
            return -u()
        return pw()
    def pw():
        b = atom()
        if peek() == "^":
            take()
            k = u()
            if k.denominator != 1:
                raise ValueError("non-integer exponent")
            k = int(k)
            if b == 0 and k < 0:
                raise ZeroDivisionError("0 to negative power")
            return b ** k
        return b
    def atom():
        c = peek()
        if c is None:
            raise ValueError("eof")
        if c == "(":
            take()
            v = e()
            if peek() != ")":
                raise ValueError("paren")
            take()
            return v
        if c.isdigit():
            take()
            return Fraction(int(c))
        raise ValueError("atom")
    v = e()
    if pos != len(toks):
        raise ValueError("trailing")
    return str(v.numerator) if v.denominator == 1 else f"{v.numerator}/{v.denominator}"
''')

task("v1_10_int_to_english", r'''
Write `int_to_english(n: int) -> str` for 0 <= n < 10**15 using the American short scale
without "and" or hyphens, every word capitalized and single-space separated: "Zero",
"One Hundred Twenty Three", "One Million Ten", scales Thousand, Million, Billion,
Trillion. Omit zero groups entirely. Raise ValueError for n outside the range.
''', r'''
cases = {0: "Zero", 5: "Five", 13: "Thirteen", 20: "Twenty", 21: "Twenty One", 40: "Forty", 90: "Ninety",
         100: "One Hundred", 101: "One Hundred One", 110: "One Hundred Ten", 123: "One Hundred Twenty Three",
         1000: "One Thousand", 1001: "One Thousand One", 12345: "Twelve Thousand Three Hundred Forty Five",
         100000: "One Hundred Thousand", 1000000: "One Million", 1000010: "One Million Ten",
         1000000001: "One Billion One", 10**12: "One Trillion",
         1234567891: "One Billion Two Hundred Thirty Four Million Five Hundred Sixty Seven Thousand Eight Hundred Ninety One",
         999999999999999: "Nine Hundred Ninety Nine Trillion Nine Hundred Ninety Nine Billion Nine Hundred Ninety Nine Million Nine Hundred Ninety Nine Thousand Nine Hundred Ninety Nine",
         7000000000000: "Seven Trillion", 15000019: "Fifteen Million Nineteen", 80080: "Eighty Thousand Eighty"}
for k, v in cases.items():
    assert int_to_english(k) == v, (k, int_to_english(k))
for bad in [-1, 10**15]:
    try:
        int_to_english(bad)
    except ValueError:
        pass
    else:
        raise AssertionError(bad)
''', r'''
_ONES = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten", "Eleven", "Twelve",
         "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen"]
_TENS = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]
_SCALES = ["", "Thousand", "Million", "Billion", "Trillion"]

def _three(n):
    w = []
    if n >= 100:
        w += [_ONES[n // 100], "Hundred"]
        n %= 100
    if n >= 20:
        w.append(_TENS[n // 10])
        n %= 10
    if n:
        w.append(_ONES[n])
    return w

def int_to_english(n):
    if not 0 <= n < 10**15:
        raise ValueError(n)
    if n == 0:
        return "Zero"
    words = []
    for i in range(4, -1, -1):
        g = n // 1000**i % 1000
        if g:
            words += _three(g) + ([_SCALES[i]] if i else [])
    return " ".join(words)
''')

task("v1_11_sliding_median", r'''
Write `sliding_median(nums: list[int], k: int) -> list[float]` returning the median of
every window of k consecutive elements, left to right (len(nums) - k + 1 values,
1 <= k <= len(nums)). For even k the median is the mean of the two middle values.
Return floats. len(nums) up to 100000 with k up to 5000 must finish in under 10 s.
''', r'''
import random, statistics, time
assert sliding_median([1, 3, -1, -3, 5, 3, 6, 7], 3) == [1.0, -1.0, -1.0, 3.0, 5.0, 6.0]
assert sliding_median([1, 2, 3, 4, 2, 3, 1, 4, 2], 4) == [2.5, 2.5, 3.0, 2.5, 2.5, 2.5]
assert sliding_median([5], 1) == [5.0]
assert all(isinstance(x, float) for x in sliding_median([1, 2, 3], 2))
random.seed(12)
for _ in range(300):
    n = random.randint(1, 40)
    a = [random.randint(-5, 5) for _ in range(n)]
    k = random.randint(1, n)
    assert sliding_median(a, k) == [float(statistics.median(a[i:i + k])) for i in range(n - k + 1)], (a, k)
big = [random.randint(-10**9, 10**9) for _ in range(100000)]
t = time.perf_counter()
r = sliding_median(big, 5000)
assert time.perf_counter() - t < 10.0
assert len(r) == 95001 and r[0] == float(statistics.median(big[:5000])) and r[-1] == float(statistics.median(big[-5000:]))
''', r'''
import bisect

def sliding_median(nums, k):
    w = sorted(nums[:k])
    out = []
    def med():
        if k % 2:
            return float(w[k // 2])
        return (w[k // 2 - 1] + w[k // 2]) / 2
    out.append(med())
    for i in range(k, len(nums)):
        del w[bisect.bisect_left(w, nums[i - k])]
        bisect.insort(w, nums[i])
        out.append(med())
    return out
''')

task("v1_12_count_smaller", r'''
Write `count_smaller(nums: list[int]) -> list[int]` where result[i] is the number of
elements to the right of index i that are strictly smaller than nums[i]. len(nums) up
to 100000, values any Python ints; must finish in under 10 s.
''', r'''
import random, time
assert count_smaller([5, 2, 6, 1]) == [2, 1, 1, 0]
assert count_smaller([]) == []
assert count_smaller([-1, -1]) == [0, 0]
assert count_smaller([3, 3, 1, 3]) == [1, 1, 0, 0]
random.seed(13)
for _ in range(300):
    a = [random.randint(-6, 6) for _ in range(random.randint(0, 30))]
    assert count_smaller(a) == [sum(a[j] < a[i] for j in range(i + 1, len(a))) for i in range(len(a))], a
big = [random.randint(-10**12, 10**12) for _ in range(100000)]
t = time.perf_counter()
r = count_smaller(big)
assert time.perf_counter() - t < 10.0
assert r[-1] == 0 and r[-2] == (1 if big[-1] < big[-2] else 0)
assert r[0] == sum(x < big[0] for x in big[1:])
''', r'''
def count_smaller(nums):
    ranks = {v: i + 1 for i, v in enumerate(sorted(set(nums)))}
    m = len(ranks)
    tree = [0] * (m + 1)
    out = [0] * len(nums)
    for i in range(len(nums) - 1, -1, -1):
        r = ranks[nums[i]]
        s = 0
        j = r - 1
        while j > 0:
            s += tree[j]
            j -= j & -j
        out[i] = s
        j = r
        while j <= m:
            tree[j] += 1
            j += j & -j
    return out
''')

task("v1_13_max_points", r'''
Write `max_points(points: list[tuple[int, int]]) -> int` returning the maximum number of
points that lie on one straight line. Points may repeat (each copy counts). Coordinates
are integers with absolute value up to 10**9, so floating-point slopes are not exact
enough. Up to 300 points.
''', r'''
import random, time
assert max_points([]) == 0
assert max_points([(1, 1)]) == 1
assert max_points([(1, 1), (1, 1)]) == 2
assert max_points([(1, 1), (2, 2), (3, 3)]) == 3
assert max_points([(1, 1), (3, 2), (5, 3), (4, 1), (2, 3), (1, 4)]) == 4
assert max_points([(0, 0), (1000000000, 999999999), (999999999, 999999998)]) == 2
assert max_points([(0, 0), (0, 0), (5, 5), (1, 2)]) == 3
assert max_points([(2, 3), (2, 7), (2, -1), (5, 3)]) == 3
def brute(p):
    n = len(p)
    if n <= 2:
        return n
    best = max(p.count(q) for q in p)
    for i in range(n):
        for j in range(n):
            if p[i] != p[j]:
                (x1, y1), (x2, y2) = p[i], p[j]
                best = max(best, sum((x2 - x1) * (y - y1) == (y2 - y1) * (x - x1) for x, y in p))
    return best
random.seed(14)
for _ in range(200):
    p = [(random.randint(-3, 3), random.randint(-3, 3)) for _ in range(random.randint(0, 12))]
    assert max_points(p) == brute(p), p
pts = [(random.randint(-10**9, 10**9), random.randint(-10**9, 10**9)) for _ in range(300)]
t = time.perf_counter()
max_points(pts)
assert time.perf_counter() - t < 5.0
''', r'''
from math import gcd

def max_points(points):
    n = len(points)
    if n <= 2:
        return n
    best = 0
    for i in range(n):
        x1, y1 = points[i]
        same = 0
        slopes = {}
        for j in range(n):
            x2, y2 = points[j]
            dx, dy = x2 - x1, y2 - y1
            if dx == 0 and dy == 0:
                same += 1
                continue
            g = gcd(dx, dy)
            dx, dy = dx // g, dy // g
            if dx < 0 or (dx == 0 and dy < 0):
                dx, dy = -dx, -dy
            slopes[(dx, dy)] = slopes.get((dx, dy), 0) + 1
        best = max(best, same + (max(slopes.values()) if slopes else 0))
    return best
''')

task("v1_14_skyline", r'''
Write `skyline(buildings: list[list[int]]) -> list[list[int]]`. Each building is
[left, right, height] with integers left < right, height > 0, covering [left, right).
Return the skyline as key points [x, h] sorted by x: at each x where the maximum height
of the buildings covering [x, x + epsilon) changes, emit [x, new height]; the last key
point has height 0. Never emit two consecutive points with the same height.
Up to 10000 buildings must finish in under 5 s.
''', r'''
import random, time
assert skyline([]) == []
assert skyline([[2, 9, 10], [3, 7, 15], [5, 12, 12], [15, 20, 10], [19, 24, 8]]) == [[2, 10], [3, 15], [7, 12], [12, 0], [15, 10], [20, 8], [24, 0]]
assert skyline([[0, 2, 3], [2, 5, 3]]) == [[0, 3], [5, 0]]
assert skyline([[1, 2, 1], [1, 2, 2], [1, 2, 3]]) == [[1, 3], [2, 0]]
def brute(b):
    if not b:
        return []
    hi = max(r for _, r, _ in b)
    out, prev = [], 0
    for x in range(min(l for l, _, _ in b), hi + 1):
        h = max([hh for l, r, hh in b if l <= x < r], default=0)
        if h != prev:
            out.append([x, h])
            prev = h
    return out
random.seed(15)
for _ in range(300):
    b = []
    for _ in range(random.randint(0, 8)):
        l = random.randint(0, 20)
        b.append([l, random.randint(l + 1, 25), random.randint(1, 6)])
    assert skyline(b) == brute(b), b
big = []
for _ in range(10000):
    l = random.randint(0, 10**8)
    big.append([l, l + random.randint(1, 10**5), random.randint(1, 10**6)])
t = time.perf_counter()
skyline(big)
assert time.perf_counter() - t < 5.0
''', r'''
import heapq

def skyline(buildings):
    events = sorted({b[0] for b in buildings} | {b[1] for b in buildings})
    bs = sorted(buildings)
    heap = []
    out = []
    i = 0
    for x in events:
        while i < len(bs) and bs[i][0] <= x:
            heapq.heappush(heap, (-bs[i][2], bs[i][1]))
            i += 1
        while heap and heap[0][1] <= x:
            heapq.heappop(heap)
        h = -heap[0][0] if heap else 0
        if not out or out[-1][1] != h:
            out.append([x, h])
    return out
''')

task("v1_15_trap_rain_2d", r'''
Write `trap_rain_2d(height: list[list[int]]) -> int` returning how much water a 2D
elevation map traps after rain (water flows to the 4 neighbours and escapes over the
outer border cells). height is m x n with non-negative integers; it may be empty or
have fewer than 3 rows or columns (then 0). 200 x 200 must finish in under 5 s.
''', r'''
import random, time
assert trap_rain_2d([]) == 0
assert trap_rain_2d([[1, 4, 3, 1, 3, 2], [3, 2, 1, 3, 2, 4], [2, 3, 3, 2, 3, 1]]) == 4
assert trap_rain_2d([[3, 3, 3, 3, 3], [3, 2, 2, 2, 3], [3, 2, 1, 2, 3], [3, 2, 2, 2, 3], [3, 3, 3, 3, 3]]) == 10
assert trap_rain_2d([[5, 5], [5, 5]]) == 0
def brute(h):
    m = len(h)
    n = len(h[0]) if m else 0
    if m < 3 or n < 3:
        return 0
    INF = 10**9
    lvl = [[h[i][j] if i in (0, m - 1) or j in (0, n - 1) else INF for j in range(n)] for i in range(m)]
    changed = True
    while changed:
        changed = False
        for i in range(1, m - 1):
            for j in range(1, n - 1):
                v = max(h[i][j], min(lvl[i - 1][j], lvl[i + 1][j], lvl[i][j - 1], lvl[i][j + 1]))
                if v < lvl[i][j]:
                    lvl[i][j] = v
                    changed = True
    return sum(lvl[i][j] - h[i][j] for i in range(m) for j in range(n))
random.seed(16)
for _ in range(200):
    m, n = random.randint(1, 7), random.randint(1, 7)
    h = [[random.randint(0, 6) for _ in range(n)] for _ in range(m)]
    assert trap_rain_2d(h) == brute(h), h
big = [[random.randint(0, 10**6) for _ in range(200)] for _ in range(200)]
t = time.perf_counter()
trap_rain_2d(big)
assert time.perf_counter() - t < 5.0
''', r'''
import heapq

def trap_rain_2d(height):
    m = len(height)
    n = len(height[0]) if m else 0
    if m < 3 or n < 3:
        return 0
    seen = [[False] * n for _ in range(m)]
    heap = []
    for i in range(m):
        for j in range(n):
            if i in (0, m - 1) or j in (0, n - 1):
                heapq.heappush(heap, (height[i][j], i, j))
                seen[i][j] = True
    water = 0
    while heap:
        h, i, j = heapq.heappop(heap)
        for a, b in ((i + 1, j), (i - 1, j), (i, j + 1), (i, j - 1)):
            if 0 <= a < m and 0 <= b < n and not seen[a][b]:
                seen[a][b] = True
                water += max(0, h - height[a][b])
                heapq.heappush(heap, (max(h, height[a][b]), a, b))
    return water
''')

task("v1_16_alien_order", r'''
Write `alien_order(words: list[str]) -> str`. The words (lowercase letters) are sorted
lexicographically under an unknown ordering of the alphabet. Return an ordering of
exactly the letters that appear in the words, consistent with the list: for each pair
of adjacent words, the first differing letter gives "a before b"; a word must not be
followed by a proper prefix of itself. If no ordering is consistent, return "". When
several letters could come next, always place the alphabetically smallest first (so
the answer is unique).
''', r'''
import random
from itertools import permutations
assert alien_order(["wrt", "wrf", "er", "ett", "rftt"]) == "wertf"
assert alien_order(["z", "x"]) == "zx"
assert alien_order(["z", "x", "z"]) == ""
assert alien_order(["abc", "ab"]) == ""
assert alien_order(["ab", "abc"]) == "abc"
assert alien_order(["z"]) == "z"
assert alien_order(["ba", "bc", "ac", "cab"]) == "bac"
def brute(words):
    letters = sorted(set("".join(words)))
    for perm in permutations(letters):
        rank = {c: i for i, c in enumerate(perm)}
        keys = [[rank[c] for c in w] for w in words]
        if all(keys[i] <= keys[i + 1] for i in range(len(keys) - 1)):
            return "".join(perm)
    return ""
random.seed(18)
for _ in range(400):
    alpha = "abcdef"[:random.randint(1, 6)]
    hidden = list(alpha)
    random.shuffle(hidden)
    rank = {c: i for i, c in enumerate(hidden)}
    ws = ["".join(random.choice(alpha) for _ in range(random.randint(1, 4))) for _ in range(random.randint(1, 6))]
    ws.sort(key=lambda w: [rank[c] for c in w])
    if random.random() < 0.3 and len(ws) > 1:
        i = random.randrange(len(ws) - 1)
        ws[i], ws[i + 1] = ws[i + 1], ws[i]
    assert alien_order(ws) == brute(ws), ws
''', r'''
import heapq

def alien_order(words):
    letters = set("".join(words))
    succ = {c: set() for c in letters}
    indeg = {c: 0 for c in letters}
    for a, b in zip(words, words[1:]):
        for x, y in zip(a, b):
            if x != y:
                if y not in succ[x]:
                    succ[x].add(y)
                    indeg[y] += 1
                break
        else:
            if len(a) > len(b):
                return ""
    heap = [c for c in letters if indeg[c] == 0]
    heapq.heapify(heap)
    out = []
    while heap:
        c = heapq.heappop(heap)
        out.append(c)
        for d in succ[c]:
            indeg[d] -= 1
            if indeg[d] == 0:
                heapq.heappush(heap, d)
    return "".join(out) if len(out) == len(letters) else ""
''')

task("v1_17_word_ladders", r'''
Write `word_ladders(begin: str, end: str, words: list[str]) -> list[list[str]]` returning
all shortest transformation sequences from begin to end. Each step changes exactly one
letter, and every word after begin must be in `words` (begin need not be). All words
have the same length; begin != end. Return the sequences sorted lexicographically (as
lists); return [] if end is not in words or unreachable. Must handle a dictionary of
all 81 four-letter words over "abc" quickly.
''', r'''
import random, time
from itertools import product
assert word_ladders("hit", "cog", ["hot", "dot", "dog", "lot", "log", "cog"]) == [
    ["hit", "hot", "dot", "dog", "cog"], ["hit", "hot", "lot", "log", "cog"]]
assert word_ladders("hit", "cog", ["hot", "dot", "dog", "lot", "log"]) == []
assert word_ladders("a", "c", ["a", "b", "c"]) == [["a", "c"]]
assert word_ladders("ab", "cd", ["ad", "cb", "cd"]) == [["ab", "ad", "cd"], ["ab", "cb", "cd"]]
def brute(b, e, ws):
    ws = set(ws)
    if e not in ws:
        return []
    best = []
    def dfs(path, limit):
        if path[-1] == e:
            best.append(list(path))
            return
        if len(path) > limit:
            return
        w = path[-1]
        for i in range(len(w)):
            for c in "abcdefghijklmnopqrstuvwxyz":
                nw = w[:i] + c + w[i + 1:]
                if nw != w and nw in ws and nw not in path:
                    path.append(nw)
                    dfs(path, limit)
                    path.pop()
    for limit in range(1, len(ws) + 2):
        dfs([b], limit)
        if best:
            m = min(map(len, best))
            return sorted(p for p in best if len(p) == m)
    return []
random.seed(19)
for _ in range(150):
    ws = list({"".join(random.choice("abc") for _ in range(3)) for _ in range(random.randint(1, 9))})
    b = "".join(random.choice("abc") for _ in range(3))
    e = random.choice(ws)
    if b == e:
        continue
    assert word_ladders(b, e, ws) == brute(b, e, ws), (b, e, ws)
allw = ["".join(p) for p in product("abc", repeat=4)]
t = time.perf_counter()
r = word_ladders("aaaa", "cccc", allw)
assert time.perf_counter() - t < 5.0
assert len(r) == 24 and r == sorted(r) and all(len(p) == 5 for p in r)
assert all(sum(x != y for x, y in zip(p[i], p[i + 1])) == 1 for p in r for i in range(4))
''', r'''
from collections import defaultdict

def word_ladders(begin, end, words):
    ws = set(words)
    if end not in ws:
        return []
    parents = defaultdict(set)
    level = {begin}
    seen = {begin}
    found = False
    while level and not found:
        nxt = set()
        for w in level:
            for i in range(len(w)):
                for c in "abcdefghijklmnopqrstuvwxyz":
                    nw = w[:i] + c + w[i + 1:]
                    if nw != w and nw in ws and nw not in seen:
                        parents[nw].add(w)
                        nxt.add(nw)
                        if nw == end:
                            found = True
        seen |= nxt
        level = nxt
    if not found:
        return []
    out = []
    def back(w, path):
        if w == begin:
            out.append([begin] + path[::-1])
            return
        for p in parents[w]:
            back(p, path + [w])
    back(end, [])
    return sorted(out)
''')

task("v1_18_min_window_subseq", r'''
Write `min_window_subseq(s: str, t: str) -> str` returning the shortest contiguous
substring of s that contains t as a subsequence (characters of t in order, not
necessarily adjacent). If several have minimal length, return the leftmost. Return ""
if none exists or t is empty. len(s) up to 20000 and len(t) up to 100 must finish in
under 5 s.
''', r'''
import random, time
assert min_window_subseq("abcdebdde", "bde") == "bcde"
assert min_window_subseq("jmeqksfrsdcmsiwvaovztaqenprpvnbstl", "u") == ""
assert min_window_subseq("abc", "") == ""
assert min_window_subseq("aaa", "aa") == "aa"
assert min_window_subseq("cnhczmccqouqadqtmjjzl", "mm") == "mccqouqadqtm"
def is_sub(t, w):
    it = iter(w)
    return all(c in it for c in t)
def brute(s, t):
    if not t:
        return ""
    for L in range(len(t), len(s) + 1):
        for i in range(len(s) - L + 1):
            if is_sub(t, s[i:i + L]):
                return s[i:i + L]
    return ""
random.seed(20)
for _ in range(400):
    s = "".join(random.choice("abc") for _ in range(random.randint(0, 14)))
    t = "".join(random.choice("abc") for _ in range(random.randint(0, 4)))
    assert min_window_subseq(s, t) == brute(s, t), (s, t)
s = "".join(random.choice("ab") for _ in range(20000))
t = "".join(random.choice("ab") for _ in range(100))
t0 = time.perf_counter()
r = min_window_subseq(s, t)
assert time.perf_counter() - t0 < 5.0
assert is_sub(t, r)
''', r'''
def min_window_subseq(s, t):
    if not t:
        return ""
    n, m = len(s), len(t)
    best = None
    i = 0
    while i < n:
        j = 0
        k = i
        while k < n:
            if s[k] == t[j]:
                j += 1
                if j == m:
                    break
            k += 1
        if k >= n:
            break
        end = k
        j = m - 1
        while k >= i:
            if s[k] == t[j]:
                j -= 1
                if j < 0:
                    break
            k -= 1
        start = k
        if best is None or end - start + 1 < best[1] - best[0]:
            best = (start, end + 1)
        i = start + 1
    return "" if best is None else s[best[0]:best[1]]
''')

task("v1_19_bool_equiv", r'''
Write `bool_equiv(a: str, b: str) -> bool` returning True if two propositional formulas
are logically equivalent. Grammar (spaces allowed between tokens): variables are runs
of lowercase letters; operators by decreasing precedence: `!` (prefix not), `&`, `|`,
`->` (implication, right-associative), `<->` (equivalence, left-associative);
parentheses group. A variable that appears in only one formula is still a variable
(e.g. "a" vs "a & (b | !b)" are equivalent). At most 12 distinct variables in total.
Raise ValueError if either formula is malformed. Do not use eval, exec, compile or ast.
''', r'''
_banned(mods=("ast", "sympy"), names=("eval", "exec", "compile"))
import random, itertools
assert bool_equiv("a -> b", "!a | b")
assert bool_equiv("a -> b -> c", "a -> (b -> c)")
assert not bool_equiv("a -> b -> c", "(a -> b) -> c")
assert bool_equiv("a | b & c", "a | (b & c)")
assert not bool_equiv("a | b & c", "(a | b) & c")
assert bool_equiv("!a & b", "(!a) & b")
assert not bool_equiv("!a & b", "!(a & b)")
assert bool_equiv("a", "a & (b | !b)")
assert bool_equiv("a <-> b", "(a -> b) & (b -> a)")
assert bool_equiv("!!x", "x")
assert not bool_equiv("p", "q")
assert bool_equiv("a & b -> c", "(a & b) -> c")
assert bool_equiv("a <-> b <-> c", "(a <-> b) <-> c")
assert not bool_equiv("a -> b <-> c", "a -> (b <-> c)")
for bad in [("a &", "a"), ("a", "(a"), ("a b", "a"), ("", "a"), ("a", "a -> "), ("A", "a"), ("a", "a <- b"), ("a", "!")]:
    try:
        bool_equiv(*bad)
    except ValueError:
        pass
    else:
        raise AssertionError(bad)
random.seed(21)
VARS = ["p", "q", "r", "s"]
def gen(d):
    if d <= 0 or random.random() < 0.25:
        v = random.choice(VARS)
        return v, (lambda e, v=v: e[v])
    op = random.choice(["!", "&", "|", "->", "<->"])
    if op == "!":
        s, f = gen(d - 1)
        return "!(" + s + ")", (lambda e, f=f: not f(e))
    s1, f1 = gen(d - 1)
    s2, f2 = gen(d - 1)
    fn = {"&": lambda x, y: x and y, "|": lambda x, y: x or y, "->": lambda x, y: (not x) or y, "<->": lambda x, y: x == y}[op]
    return "(" + s1 + ") " + op + " (" + s2 + ")", (lambda e, f1=f1, f2=f2, fn=fn: fn(f1(e), f2(e)))
def transform(s):
    return random.choice(["!!(" + s + ")", "(" + s + ") & ((p) | !(p))", "!(" + s + ") -> (" + s + ")", "(" + s + ") | ((q) & !(q))"])
for _ in range(400):
    s1, f1 = gen(3)
    if random.random() < 0.5:
        s2, f2 = transform(s1), f1
    else:
        s2, f2 = gen(3)
    exp = all(bool(f1(dict(zip(VARS, bits)))) == bool(f2(dict(zip(VARS, bits)))) for bits in itertools.product([False, True], repeat=4))
    assert bool_equiv(s1, s2) == exp, (s1, s2)
''', r'''
from itertools import product

def _tokens(s):
    toks = []
    i = 0
    while i < len(s):
        c = s[i]
        if c.isspace():
            i += 1
        elif "a" <= c <= "z":
            j = i
            while j < len(s) and "a" <= s[j] <= "z":
                j += 1
            toks.append(("var", s[i:j]))
            i = j
        elif s.startswith("<->", i):
            toks.append(("<->", None))
            i += 3
        elif s.startswith("->", i):
            toks.append(("->", None))
            i += 2
        elif c in "!&|()":
            toks.append((c, None))
            i += 1
        else:
            raise ValueError("bad char")
    return toks

def _parse(s):
    toks = _tokens(s)
    pos = 0
    def peek():
        return toks[pos][0] if pos < len(toks) else None
    def take(k):
        nonlocal pos
        if peek() != k:
            raise ValueError("expected " + k)
        pos += 1
        return toks[pos - 1][1]
    def eqv():
        a = imp()
        while peek() == "<->":
            take("<->")
            a = ("<->", a, imp())
        return a
    def imp():
        a = orr()
        if peek() == "->":
            take("->")
            return ("->", a, imp())
        return a
    def orr():
        a = andd()
        while peek() == "|":
            take("|")
            a = ("|", a, andd())
        return a
    def andd():
        a = nott()
        while peek() == "&":
            take("&")
            a = ("&", a, nott())
        return a
    def nott():
        if peek() == "!":
            take("!")
            return ("!", nott())
        if peek() == "(":
            take("(")
            a = eqv()
            take(")")
            return a
        if peek() == "var":
            return ("var", take("var"))
        raise ValueError("atom")
    tree = eqv()
    if pos != len(toks):
        raise ValueError("trailing")
    return tree

def _vars(t, out):
    if t[0] == "var":
        out.add(t[1])
    else:
        for c in t[1:]:
            _vars(c, out)
    return out

def _ev(t, e):
    k = t[0]
    if k == "var":
        return e[t[1]]
    if k == "!":
        return not _ev(t[1], e)
    a, b = _ev(t[1], e), _ev(t[2], e)
    if k == "&":
        return a and b
    if k == "|":
        return a or b
    if k == "->":
        return (not a) or b
    return a == b

def bool_equiv(a, b):
    ta, tb = _parse(a), _parse(b)
    vs = sorted(_vars(ta, set()) | _vars(tb, set()))
    for bits in product([False, True], repeat=len(vs)):
        e = dict(zip(vs, bits))
        if _ev(ta, e) != _ev(tb, e):
            return False
    return True
''')

task("v1_20_determinant", r'''
Write `determinant(m: list[list[int]]) -> int` returning the exact determinant of a
square integer matrix (n from 0 to 12; the determinant of the 0x0 matrix is 1).
Entries can be large; the result must be exact (no floating point). Do not use numpy.
''', r'''
_banned(mods=("numpy", "sympy"))
import random
from itertools import permutations
assert determinant([]) == 1
assert determinant([[7]]) == 7
assert determinant([[1, 2], [3, 4]]) == -2
assert determinant([[0, 1], [1, 0]]) == -1
assert determinant([[2, 0, 0], [0, 3, 0], [0, 0, 4]]) == 24
assert determinant([[1, 2, 3], [4, 5, 6], [7, 8, 9]]) == 0
assert determinant([[0, 0, 1], [0, 1, 0], [1, 0, 0]]) == -1
def leib(m):
    n = len(m)
    tot = 0
    for p in permutations(range(n)):
        inv = sum(p[i] > p[j] for i in range(n) for j in range(i + 1, n))
        prod = 1
        for i in range(n):
            prod *= m[i][p[i]]
        tot += -prod if inv % 2 else prod
    return tot
random.seed(22)
for _ in range(300):
    n = random.randint(1, 6)
    m = [[random.randint(-9, 9) for _ in range(n)] for _ in range(n)]
    if random.random() < 0.2:
        m[random.randrange(n)] = [0] * n
    assert determinant(m) == leib(m), m
big = [[random.randint(-10**12, 10**12) for _ in range(5)] for _ in range(5)]
assert determinant(big) == leib(big)
v = [[i ** j for j in range(12)] for i in range(1, 13)]
exp = 1
for i in range(1, 13):
    for j in range(i + 1, 13):
        exp *= j - i
assert determinant(v) == exp
''', r'''
def determinant(m):
    n = len(m)
    if n == 0:
        return 1
    a = [row[:] for row in m]
    sign = 1
    prev = 1
    for k in range(n - 1):
        if a[k][k] == 0:
            for r in range(k + 1, n):
                if a[r][k] != 0:
                    a[k], a[r] = a[r], a[k]
                    sign = -sign
                    break
            else:
                return 0
        for i in range(k + 1, n):
            for j in range(k + 1, n):
                a[i][j] = (a[i][j] * a[k][k] - a[i][k] * a[k][j]) // prev
        prev = a[k][k]
    return sign * a[n - 1][n - 1]
''')

task("v1_21_next_palindrome", r'''
Write `next_palindrome(s: str) -> str`. s is a non-negative integer in decimal without
leading zeros (or "0"), up to 2000 digits. Return the smallest palindromic integer
strictly greater than it, as a decimal string without leading zeros.
''', r'''
import random, time
for k, v in {"0": "1", "8": "9", "9": "11", "10": "11", "11": "22", "99": "101", "123": "131", "808": "818",
             "1991": "2002", "999": "1001", "12921": "13031", "1234": "1331", "94187978322": "94188088149"}.items():
    assert next_palindrome(k) == v, (k, next_palindrome(k), v)
def brute(n):
    m = n + 1
    while str(m) != str(m)[::-1]:
        m += 1
    return str(m)
for n in range(0, 3000):
    assert next_palindrome(str(n)) == brute(n), n
random.seed(23)
for _ in range(200):
    n = random.randint(10**6, 10**7)
    assert next_palindrome(str(n)) == brute(n), n
big = "9" * 2000
t = time.perf_counter()
assert next_palindrome(big) == "1" + "0" * 1999 + "1"
s = "1" + "0" * 1998 + "2"
assert next_palindrome(s) == "1" + "0" * 998 + "11" + "0" * 998 + "1"
assert time.perf_counter() - t < 2.0
''', r'''
def next_palindrome(s):
    n = len(s)
    if set(s) == {"9"}:
        return "1" + "0" * (n - 1) + "1"
    half = s[:(n + 1) // 2]
    def mirror(h):
        return h + h[:n // 2][::-1]
    p = mirror(half)
    if p > s:
        return p
    digits = list(half)
    i = len(digits) - 1
    while digits[i] == "9":
        digits[i] = "0"
        i -= 1
    digits[i] = str(int(digits[i]) + 1)
    return mirror("".join(digits))
''')

task("v1_22_count_digit", r'''
Write `count_digit(n: int, d: int) -> int` returning how many times digit d (0-9)
appears in the decimal representations of all integers 0, 1, ..., n (n >= 0, up to
10**18). Numbers are written without leading zeros and 0 is written "0", so it counts
once for d = 0. Must be fast for n = 10**18.
''', r'''
import random
def brute(n, d):
    return sum(str(i).count(str(d)) for i in range(n + 1))
assert count_digit(0, 0) == 1 and count_digit(0, 1) == 0
assert count_digit(13, 1) == 6
assert count_digit(100, 0) == 12
assert count_digit(10**18, 1) == 18 * 10**17 + 1
acc = {d: 0 for d in range(10)}
for n in range(0, 2500):
    for ch in str(n):
        acc[int(ch)] += 1
    for d in range(10):
        assert count_digit(n, d) == acc[d], (n, d)
random.seed(24)
for _ in range(30):
    n = random.randint(0, 200000)
    d = random.randint(0, 9)
    assert count_digit(n, d) == brute(n, d), (n, d)
''', r'''
def count_digit(n, d):
    total = 1 if d == 0 else 0
    p = 1
    while p <= n:
        high, cur, low = n // (p * 10), (n // p) % 10, n % p
        if d:
            total += high * p + (p if cur > d else low + 1 if cur == d else 0)
        elif high:
            total += (high - 1) * p + (p if cur > 0 else low + 1)
        p *= 10
    return total
''')

task("v1_23_kth_lexicographic", r'''
Write `kth_lexicographic(n: int, k: int) -> int` returning the k-th smallest integer
(1-indexed) among 1..n when the integers are sorted as decimal strings
(lexicographically). 1 <= k <= n <= 10**12. Must be fast for large n.
''', r'''
import random
assert kth_lexicographic(13, 2) == 10
assert kth_lexicographic(1, 1) == 1
assert kth_lexicographic(100, 10) == 17
for n in range(1, 400):
    order = sorted(range(1, n + 1), key=str)
    for k in range(1, n + 1):
        assert kth_lexicographic(n, k) == order[k - 1], (n, k)
random.seed(25)
for _ in range(50):
    n = random.randint(1, 50000)
    k = random.randint(1, n)
    assert kth_lexicographic(n, k) == sorted(range(1, n + 1), key=str)[k - 1], (n, k)
assert kth_lexicographic(10**12, 10**12) == 999999999999
assert kth_lexicographic(10**12, 1) == 1
assert kth_lexicographic(10**12, 2) == 10
''', r'''
def kth_lexicographic(n, k):
    cur = 1
    k -= 1
    while k:
        steps = 0
        a, b = cur, cur + 1
        while a <= n:
            steps += min(n + 1, b) - a
            a *= 10
            b *= 10
        if steps <= k:
            k -= steps
            cur += 1
        else:
            k -= 1
            cur *= 10
    return cur
''')

task("v1_24_add_duration", r'''
Write `add_duration(dt: str, dur: str) -> str`. dt is "YYYY-MM-DDTHH:MM:SS" exactly
(zero-padded, a valid date and time, naive). dur is an ISO 8601 duration
"[-]P[nY][nM][nW][nD][T[nH][nM][nS]]" with non-negative integer components in that
order, at least one component, and at least one component after "T" if "T" is present;
uppercase only. Apply it as: total months = 12*Y + M added first (or subtracted if the
duration is negative), clamping the day to the last day of the resulting month; then
add (or subtract) W weeks, D days, H hours, M minutes and S seconds as exact elapsed
time. Return the result in the same format. Raise ValueError for malformed input
(including invalid dates like "2026-02-30T00:00:00").
''', r'''
cases = [("2026-01-31T10:00:00", "P1M", "2026-02-28T10:00:00"),
         ("2024-01-31T00:00:00", "P1M", "2024-02-29T00:00:00"),
         ("2024-02-29T00:00:00", "P1Y", "2025-02-28T00:00:00"),
         ("2026-10-05T23:30:00", "PT45M", "2026-10-06T00:15:00"),
         ("2026-03-31T12:00:00", "-P1M", "2026-02-28T12:00:00"),
         ("2026-01-01T00:00:00", "-PT1S", "2025-12-31T23:59:59"),
         ("2026-01-31T00:00:00", "P1M1D", "2026-03-01T00:00:00"),
         ("2026-01-01T00:00:00", "P2W", "2026-01-15T00:00:00"),
         ("2026-12-15T08:00:00", "P1Y2M3DT4H5M6S", "2028-02-18T12:05:06"),
         ("2026-05-31T00:00:00", "P13M", "2027-06-30T00:00:00"),
         ("2026-03-01T00:30:00", "-PT1H", "2026-02-28T23:30:00"),
         ("2026-01-01T00:00:00", "P0D", "2026-01-01T00:00:00"),
         ("2026-01-01T00:00:00", "PT36H", "2026-01-02T12:00:00"),
         ("2026-01-31T00:00:00", "-P1M1D", "2025-12-30T00:00:00"),
         ("2026-01-01T00:00:00", "PT90M", "2026-01-01T01:30:00"),
         ("0999-12-31T23:59:59", "PT1S", "1000-01-01T00:00:00"),
         ("2026-08-31T00:00:00", "P1Y6M", "2028-02-29T00:00:00")]
for a, d, exp in cases:
    assert add_duration(a, d) == exp, (a, d, add_duration(a, d), exp)
for a, d in [("2026-01-01T00:00:00", x) for x in ["P", "PT", "P1H", "1D", "P1.5D", "PT1D", "P1DT", "P-1D", "p1d",
                                                   "P1M1Y", "", "-P", "P1D2", "P 1D", "+P1D", "PT1H1H"]] + \
            [(x, "P1D") for x in ["2026-02-30T00:00:00", "2026-1-05T00:00:00", "2026-01-05 00:00:00", "2026-01-05T24:00:00",
                                  "2026-01-05T00:00", "x"]]:
    try:
        add_duration(a, d)
    except ValueError:
        pass
    else:
        raise AssertionError((a, d))
''', r'''
import re
from datetime import datetime, timedelta
import calendar

_DUR = re.compile(r"(-)?P(?:([0-9]+)Y)?(?:([0-9]+)M)?(?:([0-9]+)W)?(?:([0-9]+)D)?(?:T(?:([0-9]+)H)?(?:([0-9]+)M)?(?:([0-9]+)S)?)?")
_DT = re.compile(r"([0-9]{4})-([0-9]{2})-([0-9]{2})T([0-9]{2}):([0-9]{2}):([0-9]{2})")

def add_duration(dt, dur):
    m = _DT.fullmatch(dt)
    if not m:
        raise ValueError("datetime")
    base = datetime(*map(int, m.groups()))
    d = _DUR.fullmatch(dur)
    if not d:
        raise ValueError("duration")
    sign, Y, Mo, W, D, H, Mi, S = d.groups()
    if all(g is None for g in (Y, Mo, W, D, H, Mi, S)):
        raise ValueError("empty duration")
    if "T" in dur and H is None and Mi is None and S is None:
        raise ValueError("empty time part")
    sg = -1 if sign else 1
    v = lambda g: int(g) if g else 0
    months = sg * (12 * v(Y) + v(Mo))
    idx = base.year * 12 + base.month - 1 + months
    year, month = divmod(idx, 12)
    month += 1
    if not 1 <= year <= 9999:
        raise ValueError("year out of range")
    day = min(base.day, calendar.monthrange(year, month)[1])
    out = base.replace(year=year, month=month, day=day)
    try:
        out = out + sg * timedelta(weeks=v(W), days=v(D), hours=v(H), minutes=v(Mi), seconds=v(S))
    except OverflowError:
        raise ValueError("out of range")
    return f"{out.year:04d}-{out.month:02d}-{out.day:02d}T{out.hour:02d}:{out.minute:02d}:{out.second:02d}"
''')

task("v1_25_weighted_interval", r'''
Write `weighted_interval(jobs: list[tuple[int, int, int]]) -> list[int]`. jobs[i] =
(start, end, weight) with start < end and weight >= 1, occupying [start, end); two jobs
are compatible if they do not overlap (touching ends are fine). Return the sorted list
of indices of a pairwise compatible subset with maximum total weight. If several
subsets reach the maximum, return the lexicographically smallest sorted index list.
Up to 300 jobs must finish in under 10 s.
''', r'''
import random, time
from itertools import combinations
assert weighted_interval([]) == []
assert weighted_interval([(1, 3, 5)]) == [0]
assert weighted_interval([(1, 3, 5), (2, 5, 6), (4, 6, 5), (6, 7, 4)]) == [0, 2, 3]
assert weighted_interval([(0, 2, 1), (2, 4, 1), (0, 4, 2)]) == [0, 1]
assert weighted_interval([(0, 4, 2), (0, 2, 1), (2, 4, 1)]) == [0]
def brute(jobs):
    n = len(jobs)
    best = (0, [])
    for r in range(1, n + 1):
        for c in combinations(range(n), r):
            if all(jobs[a][1] <= jobs[b][0] or jobs[b][1] <= jobs[a][0] for a, b in combinations(c, 2)):
                w = sum(jobs[i][2] for i in c)
                if w > best[0] or (w == best[0] and list(c) < best[1]):
                    best = (w, list(c))
    return best[1]
random.seed(26)
for _ in range(300):
    jobs = []
    for _ in range(random.randint(0, 9)):
        s = random.randint(0, 10)
        jobs.append((s, random.randint(s + 1, 12), random.randint(1, 4)))
    assert weighted_interval(jobs) == brute(jobs), jobs
big = []
for _ in range(300):
    s = random.randint(0, 10**6)
    big.append((s, s + random.randint(1, 10**4), random.randint(1, 3)))
t = time.perf_counter()
r = weighted_interval(big)
assert time.perf_counter() - t < 10.0
assert r == sorted(set(r))
''', r'''
import bisect

def _best(cands):
    cands = sorted(cands, key=lambda j: j[1])
    ends = [j[1] for j in cands]
    dp = [0] * (len(cands) + 1)
    for i, (s, e, w) in enumerate(cands):
        p = bisect.bisect_right(ends, s, 0, i)
        dp[i + 1] = max(dp[i], dp[p] + w)
    return dp[-1]

def weighted_interval(jobs):
    n = len(jobs)
    def compat(a, b):
        return a[1] <= b[0] or b[1] <= a[0]
    def value(forced, excluded):
        fj = [jobs[i] for i in forced]
        rest = [jobs[i] for i in range(n) if i not in forced and i not in excluded
                and all(compat(jobs[i], f) for f in fj)]
        return sum(f[2] for f in fj) + _best(rest)
    opt = value(set(), set())
    forced, excluded = set(), set()
    for i in range(n):
        if all(compat(jobs[i], jobs[f]) for f in forced) and value(forced | {i}, excluded) == opt:
            forced.add(i)
        else:
            excluded.add(i)
    return sorted(forced)
''')

task("v1_26_maximal_rectangle", r'''
Write `maximal_rectangle(grid: list[str]) -> int` returning the area of the largest
axis-aligned rectangle containing only '1' characters in a grid of '0'/'1' strings
(all rows the same length; the grid may be empty). 200 x 200 must finish in under 5 s.
''', r'''
import random, time
assert maximal_rectangle([]) == 0
assert maximal_rectangle(["10100", "10111", "11111", "10010"]) == 6
assert maximal_rectangle(["0"]) == 0
assert maximal_rectangle(["1"]) == 1
assert maximal_rectangle(["111", "111"]) == 6
def brute(g):
    m = len(g)
    n = len(g[0]) if m else 0
    best = 0
    for r1 in range(m):
        for r2 in range(r1, m):
            for c1 in range(n):
                for c2 in range(c1, n):
                    if all(g[r][c] == "1" for r in range(r1, r2 + 1) for c in range(c1, c2 + 1)):
                        best = max(best, (r2 - r1 + 1) * (c2 - c1 + 1))
    return best
random.seed(27)
for _ in range(200):
    m, n = random.randint(1, 6), random.randint(1, 6)
    g = ["".join(random.choice("0111") for _ in range(n)) for _ in range(m)]
    assert maximal_rectangle(g) == brute(g), g
big = ["".join(random.choice("01111") for _ in range(200)) for _ in range(200)]
t = time.perf_counter()
maximal_rectangle(big)
assert time.perf_counter() - t < 5.0
''', r'''
def maximal_rectangle(grid):
    if not grid:
        return 0
    n = len(grid[0])
    h = [0] * n
    best = 0
    for row in grid:
        for j in range(n):
            h[j] = h[j] + 1 if row[j] == "1" else 0
        st = []
        for j in range(n + 1):
            cur = h[j] if j < n else 0
            while st and h[st[-1]] >= cur:
                top = st.pop()
                left = st[-1] + 1 if st else 0
                best = max(best, h[top] * (j - left))
            st.append(j)
    return best
''')

task("v1_27_merge_stones", r'''
Write `merge_stones(stones: list[int], k: int) -> int`. A move merges exactly k
consecutive piles into one pile, costing the total number of stones in those k piles.
Return the minimum total cost to merge all piles into one pile, or -1 if impossible.
k >= 2, len(stones) up to 30, pile sizes up to 100. A single pile costs 0.
''', r'''
import random
from functools import lru_cache
assert merge_stones([3, 2, 4, 1], 2) == 20
assert merge_stones([3, 2, 4, 1], 3) == -1
assert merge_stones([3, 5, 1, 2, 6], 3) == 25
assert merge_stones([7], 2) == 0
assert merge_stones([1, 1], 3) == -1
def brute(stones, k):
    @lru_cache(None)
    def go(t):
        if len(t) == 1:
            return 0
        best = None
        for i in range(len(t) - k + 1):
            s = sum(t[i:i + k])
            r = go(t[:i] + (s,) + t[i + k:])
            if r is not None and (best is None or r + s < best):
                best = r + s
        return best
    r = go(tuple(stones))
    return -1 if r is None else r
random.seed(28)
for _ in range(150):
    k = random.randint(2, 4)
    st = [random.randint(1, 9) for _ in range(random.randint(1, 8))]
    assert merge_stones(st, k) == brute(st, k), (st, k)
assert merge_stones([random.randint(1, 100) for _ in range(29)], 3) >= 0
''', r'''
def merge_stones(stones, k):
    n = len(stones)
    if (n - 1) % (k - 1):
        return -1
    pre = [0]
    for s in stones:
        pre.append(pre[-1] + s)
    INF = float("inf")
    dp = [[0] * n for _ in range(n)]
    for length in range(k, n + 1):
        for i in range(n - length + 1):
            j = i + length - 1
            best = INF
            for mid in range(i, j, k - 1):
                best = min(best, dp[i][mid] + dp[mid + 1][j])
            if (length - 1) % (k - 1) == 0:
                best += pre[j + 1] - pre[i]
            dp[i][j] = best
    return dp[0][n - 1]
''')

task("v1_28_reach_target", r'''
Write `reach_target(nums: list[int], target: int) -> str | None`. Using every number in
nums exactly once (1 to 5 positive integers), the binary operators + - * / and
parentheses, build an expression whose exact rational value equals target. Return
the expression as a string of integer literals, operators, parentheses and spaces (no
unary minus, no other operators), or None if impossible. Division is exact rational
division; dividing by zero is not allowed. Each call with 5 numbers must finish in
under 5 s.
''', r'''
import ast, random, time
from fractions import Fraction
from itertools import combinations
def val(node):
    if isinstance(node, ast.Constant) and type(node.value) is int:
        return Fraction(node.value), [node.value]
    assert isinstance(node, ast.BinOp) and type(node.op) in (ast.Add, ast.Sub, ast.Mult, ast.Div), ast.dump(node)
    a, la = val(node.left)
    b, lb = val(node.right)
    if isinstance(node.op, ast.Add):
        return a + b, la + lb
    if isinstance(node.op, ast.Sub):
        return a - b, la + lb
    if isinstance(node.op, ast.Mult):
        return a * b, la + lb
    assert b != 0
    return a / b, la + lb
def check(nums, target, s):
    assert isinstance(s, str) and set(s) <= set("0123456789+-*/() "), s
    v, lits = val(ast.parse(s, mode="eval").body)
    assert sorted(lits) == sorted(nums) and v == target, (nums, target, s)
def possible(nums, target):
    def go(vals):
        if len(vals) == 1:
            return vals[0] == target
        for i, j in combinations(range(len(vals)), 2):
            a, b = vals[i], vals[j]
            rest = [vals[x] for x in range(len(vals)) if x not in (i, j)]
            cand = [a + b, a - b, b - a, a * b] + ([a / b] if b else []) + ([b / a] if a else [])
            if any(go(rest + [c]) for c in cand):
                return True
        return False
    return go([Fraction(x) for x in nums])
for nums, target in [([4, 7, 8, 8], 24), ([3, 3, 8, 8], 24), ([1, 5, 5, 5], 24), ([5], 5), ([2, 3], 6)]:
    check(nums, target, reach_target(nums, target))
assert reach_target([1, 1, 1, 1], 24) is None
assert reach_target([5], 4) is None
random.seed(29)
t = time.perf_counter()
for _ in range(60):
    nums = [random.randint(1, 13) for _ in range(random.randint(1, 4))]
    target = random.randint(0, 30)
    r = reach_target(nums, target)
    if possible(nums, target):
        check(nums, target, r)
    else:
        assert r is None, (nums, target, r)
for nums, target in [([1, 2, 3, 4, 5], 119), ([13, 13, 13, 13, 13], 1), ([2, 3, 5, 7, 11], 997)]:
    r = reach_target(nums, target)
    if possible(nums, target):
        check(nums, target, r)
    else:
        assert r is None
assert time.perf_counter() - t < 60.0
''', r'''
from fractions import Fraction
from itertools import combinations

def reach_target(nums, target):
    target = Fraction(target)
    seen = set()
    def go(items):
        if len(items) == 1:
            return items[0][1] if items[0][0] == target else None
        key = tuple(sorted(v for v, _ in items))
        if key in seen:
            return None
        for i, j in combinations(range(len(items)), 2):
            (a, sa), (b, sb) = items[i], items[j]
            rest = [items[x] for x in range(len(items)) if x not in (i, j)]
            cand = [(a + b, f"({sa} + {sb})"), (a - b, f"({sa} - {sb})"), (b - a, f"({sb} - {sa})"), (a * b, f"({sa} * {sb})")]
            if b:
                cand.append((a / b, f"({sa} / {sb})"))
            if a:
                cand.append((b / a, f"({sb} / {sa})"))
            for v, s in cand:
                r = go(rest + [(v, s)])
                if r is not None:
                    return r
        seen.add(key)
        return None
    return go([(Fraction(x), str(x)) for x in nums])
''')

task("v1_29_fraction_to_base", r'''
Write `fraction_to_base(p: int, q: int, b: int) -> str` writing the rational p/q
(q != 0) in base b (2 <= b <= 36) with digits 0-9 then a-z. Format: "-" if negative,
the integer part (at least one digit, no leading zeros), then if the fractional part is
nonzero a "." followed by the non-repeating digits and, if the expansion repeats, the
repeating block in parentheses. Use the shortest form: the smallest possible
non-repeating part and the shortest repeating block, never a repeating block of only
zeros, and never a repeating block of only the digit b-1 (write the terminating form
instead). Examples: (1, 3, 10) -> "0.(3)", (1, 6, 10) -> "0.1(6)", (-7, 3, 10) ->
"-2.(3)", (255, 1, 16) -> "ff", (1, 3, 2) -> "0.(01)", (0, -5, 7) -> "0".
''', r'''
import random
from fractions import Fraction
fixed = {(1, 3, 10): "0.(3)", (1, 6, 10): "0.1(6)", (5, 2, 10): "2.5", (1, 2, 2): "0.1", (-7, 3, 10): "-2.(3)",
         (1, 7, 10): "0.(142857)", (255, 1, 16): "ff", (1, 3, 2): "0.(01)", (0, -5, 7): "0", (1, -4, 10): "-0.25",
         (22, 7, 10): "3.(142857)", (1, 12, 10): "0.08(3)", (35, 36, 36): "0.z", (1, 9, 3): "0.01", (10, 3, 3): "10.1"}
for (p, q, b), v in fixed.items():
    assert fraction_to_base(p, q, b) == v, ((p, q, b), fraction_to_base(p, q, b), v)
D = "0123456789abcdefghijklmnopqrstuvwxyz"
def parse(s, b):
    neg = s.startswith("-")
    s = s[1:] if neg else s
    ip, _, fr = s.partition(".")
    pre, _, rep = fr.partition("(")
    rep = rep.rstrip(")")
    val = Fraction(int(ip, b))
    if pre:
        val += Fraction(int(pre, b), b ** len(pre))
    if rep:
        val += Fraction(int(rep, b), (b ** len(rep) - 1) * b ** len(pre))
    return -val if neg else val, ip, pre, rep
random.seed(30)
for _ in range(1500):
    b = random.randint(2, 36)
    p = random.randint(-10**4, 10**4)
    q = random.choice([1, -1]) * random.randint(1, 300)
    s = fraction_to_base(p, q, b)
    assert set(s) <= set(D[:b] + "-.()"), s
    v, ip, pre, rep = parse(s, b)
    assert v == Fraction(p, q), (p, q, b, s)
    assert ip == "0" or ip[0] != "0", s
    assert not s.startswith("-0") or s != "-0", s
    if v == 0:
        assert s == "0"
    if "." not in s:
        assert Fraction(p, q).denominator == 1
    if rep:
        assert set(rep) != {"0"} and set(rep) != {D[b - 1]}, s
        assert not any(len(rep) % L == 0 and rep == rep[:L] * (len(rep) // L) for L in range(1, len(rep))), s
        assert not pre or pre[-1] != rep[-1], s
    elif pre:
        assert pre[-1] != "0", s
''', r'''
_D = "0123456789abcdefghijklmnopqrstuvwxyz"

def _int(n, b):
    if n == 0:
        return "0"
    out = []
    while n:
        n, r = divmod(n, b)
        out.append(_D[r])
    return "".join(reversed(out))

def fraction_to_base(p, q, b):
    neg = (p < 0) != (q < 0) and p != 0
    p, q = abs(p), abs(q)
    ip, r = divmod(p, q)
    s = ("-" if neg else "") + _int(ip, b)
    if r == 0:
        return s
    digits = []
    pos = {}
    while r and r not in pos:
        pos[r] = len(digits)
        r *= b
        d, r = divmod(r, q)
        digits.append(_D[d])
    if r == 0:
        return s + "." + "".join(digits)
    k = pos[r]
    return s + "." + "".join(digits[:k]) + "(" + "".join(digits[k:]) + ")"
''')

task("v1_30_brace_expansion", r'''
Write `brace_expansion(expr: str) -> list[str]` returning the sorted list of distinct
words described by expr. Grammar: a lowercase letter is the set containing that one
letter; "{e1,e2,...,ek}" (k >= 2) is the union of the sets of the comma-separated
expressions; writing expressions next to each other is concatenation (every word of
the first followed by every word of the second). Expressions are well-formed.
''', r'''
assert brace_expansion("{a,b}{c,{d,e}}") == ["ac", "ad", "ae", "bc", "bd", "be"]
assert brace_expansion("{{a,z},a{b,c},{ab,z}}") == ["a", "ab", "ac", "z"]
assert brace_expansion("a{b,c}{d,e}f{g,h}") == ["abdfg", "abdfh", "abefg", "abefh", "acdfg", "acdfh", "acefg", "acefh"]
assert brace_expansion("{a,b}{b,a}") == ["aa", "ab", "ba", "bb"]
assert brace_expansion("abc") == ["abc"]
assert brace_expansion("{a,{a,{a,a}}}") == ["a"]
assert brace_expansion("{a{b,c},d}e") == ["abe", "ace", "de"]
assert brace_expansion("{a,b}{c,d}{e,f}") == sorted(x + y + z for x in "ab" for y in "cd" for z in "ef")
assert brace_expansion("{{a,b}{c,d},e}") == ["ac", "ad", "bc", "bd", "e"]
assert brace_expansion("x{y,{z,w}v}") == ["xwv", "xy", "xzv"]
''', r'''
def brace_expansion(expr):
    pos = 0
    def union():
        nonlocal pos
        out = concat()
        while pos < len(expr) and expr[pos] == ",":
            pos += 1
            out |= concat()
        return out
    def concat():
        nonlocal pos
        cur = {""}
        while pos < len(expr) and expr[pos] not in ",}":
            if expr[pos] == "{":
                pos += 1
                part = union()
                pos += 1
            else:
                part = {expr[pos]}
                pos += 1
            cur = {a + b for a in cur for b in part}
        return cur
    return sorted(union())
''')

TASKS = T
