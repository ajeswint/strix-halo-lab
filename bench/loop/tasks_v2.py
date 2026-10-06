"""loop-v2: 30 held-out Python tasks for confirming the agentic loop (Roadmap item 2).

Same layout as tasks_v1.py: id, prompt, tests, ref. Written 2026-10-06, after agent.py was
designed on v1; none was used for prompt or loop iteration. Every test file has exactly one
random.seed(N) line, so agent.py's fresh-seed grade applies to all 30 (no no_fresh tasks).
v2_01-10 parsers/strings, v2_11-20 graphs/DP/data structures, v2_21-30 math/geometry/
dates/simulation. Seeded random cases are checked against an oracle inside the test
(stdlib or brute force); _banned() rejects stdlib calls that would trivialize a task.
"""

T = []


def task(id, prompt, tests, ref):
    T.append({"id": id, "prompt": prompt.strip(), "tests": tests.strip(), "ref": ref.strip()})


task("v2_01_csv_parse", r'''
Write `parse_csv(text: str) -> list[list[str]]` that parses CSV text into records (lists of
field strings). Rules:
- Records are separated by "\n" or "\r\n". A line terminator at the very end of the text is
  optional and does not start a new record. The empty string gives []. An empty line
  (two terminators in a row, or a text that is just a terminator) is a record with one
  empty field: "\n" gives [[""]], "a\n\nb" gives [["a"], [""], ["b"]].
- Fields are separated by ",". "a," is one record with two fields ["a", ""].
- A field is quoted if its first character is '"'. Inside a quoted field every character
  is literal, including ",", "\r" and "\n"; a doubled quote '""' stands for one '"'. The
  field ends at a single '"', which must be followed by ",", a line terminator, or the end
  of the text. '""' alone is an empty field.
- An unquoted field runs up to the next ",", line terminator or end of text, and must not
  contain '"'.
- Raise ValueError for: an unterminated quoted field; a '"' inside an unquoted field; any
  character other than ",", "\r\n", "\n" or end of text right after a closing quote; a "\r"
  outside quotes that is not followed by "\n".
Do not use the csv module.
''', r'''
_banned(mods=("csv", "_csv"))
import random
def bad(s):
    try:
        parse_csv(s)
    except ValueError:
        return True
    return False
assert parse_csv("") == []
assert parse_csv("\n") == [[""]]
assert parse_csv("\n\n") == [[""], [""]]
assert parse_csv("a") == [["a"]]
assert parse_csv("a,") == [["a", ""]]
assert parse_csv(",") == [["", ""]]
assert parse_csv("a,b\r\nc,d\n") == [["a", "b"], ["c", "d"]]
assert parse_csv("a\n\nb") == [["a"], [""], ["b"]]
assert parse_csv('""') == [[""]]
assert parse_csv('"a""b",c') == [['a"b', "c"]]
assert parse_csv('"x\r\ny,z"\r\n1') == [["x\r\ny,z"], ["1"]]
assert parse_csv('"",""\n') == [["", ""]]
assert parse_csv('""""') == [['"']]
for s in ['"abc', 'a"b', '"a"b', 'a\rb', 'a\r', '"a""', 'x,"y\n', '"a" ,b', 'a,b"']:
    assert bad(s), s
random.seed(17)
def enc_field(f, alone):
    need = any(c in f for c in ',"\r\n') or (alone and f == "")
    if need or random.random() < 0.25:
        return '"' + f.replace('"', '""') + '"'
    return f
for _ in range(3000):
    recs = [["".join(random.choice('ab,"\r\n x') for _ in range(random.randint(0, 4)))
             for _ in range(random.randint(1, 4))] for _ in range(random.randint(0, 5))]
    terms = [random.choice(["\n", "\r\n"]) for _ in recs]
    lines = []
    for r in recs:
        if r == [""] and random.random() < 0.5:
            lines.append("")
        else:
            lines.append(",".join(enc_field(f, False) for f in r))
    text = ""
    for i, (ln, t) in enumerate(zip(lines, terms)):
        text += ln
        if i < len(lines) - 1:
            text += t
    if recs and (lines[-1] == "" or random.random() < 0.5):
        text += terms[-1]
    assert parse_csv(text) == recs, (text, recs)
    if recs:
        junk = random.choice([',"ab', ',a"b', ',"a"b', ',a\rb', '\n"x""', ',"q"\rz'])
        assert bad(text + junk), text + junk
''', r'''
def parse_csv(text):
    if text == "":
        return []
    recs, rec, i, n = [], [], 0, len(text)
    while True:
        if i < n and text[i] == '"':
            i += 1
            buf = []
            while True:
                if i >= n:
                    raise ValueError("unterminated quoted field")
                c = text[i]
                if c == '"':
                    if i + 1 < n and text[i + 1] == '"':
                        buf.append('"')
                        i += 2
                        continue
                    i += 1
                    break
                buf.append(c)
                i += 1
            field = "".join(buf)
            if i < n and text[i] not in ",\r\n":
                raise ValueError("character after closing quote")
        else:
            j = i
            while j < n and text[j] not in ",\r\n":
                if text[j] == '"':
                    raise ValueError("quote in unquoted field")
                j += 1
            field = text[i:j]
            i = j
        rec.append(field)
        if i >= n:
            recs.append(rec)
            return recs
        c = text[i]
        if c == ",":
            i += 1
            continue
        if c == "\r":
            if i + 1 < n and text[i + 1] == "\n":
                i += 2
            else:
                raise ValueError("bare CR")
        else:
            i += 1
        recs.append(rec)
        rec = []
        if i >= n:
            return recs
''')


task("v2_02_int_eval", r'''
Write `int_eval(expr: str) -> int` that evaluates an integer expression with exactly
Python's semantics for the supported subset.
Tokens: non-negative decimal integer literals (no leading zeros: "0" is valid, "00" and
"07" are not; no underscores), the operators `+ - * // % **`, parentheses, and spaces
(only " ") between tokens. `**` and `//` are single tokens only when their two characters
are adjacent ("2* *3" and "7/ /2" are errors). A single "/" is an error.
Grammar and precedence, lowest first, as in Python:
- binary `+ -`, left-associative;
- binary `* // %`, left-associative;
- unary prefix `+ -` (may repeat: "--3" is 3);
- `**`, right-associative, binding tighter than a unary operator on its left but taking a
  unary expression as its right operand: "-2**2" is -4, "2**-1" parses, "2**-3**2" means
  2**(-(3**2)), "(-2)**2" is 4.
`//` and `%` round toward negative infinity like Python. The whole expression is parsed
before anything is evaluated, so any syntax error raises ValueError even if evaluation
would fail earlier. Errors:
- syntax errors (empty input, unbalanced parentheses, missing operand, two adjacent
  numbers, invalid character, leading zero, lone "/") -> ValueError;
- `//` or `%` by zero -> ZeroDivisionError;
- `**` with a negative exponent (including "0**-1") -> ValueError.
Evaluation order is left operand before right operand. Do not use eval, exec, compile or
the ast module.
''', r'''
_banned(mods=("ast", "code", "codeop", "subprocess", "builtins"), names=("eval", "exec", "compile", "__import__"))
import random, re, ast
def err(s):
    try:
        int_eval(s)
    except ValueError:
        return "V"
    except ZeroDivisionError:
        return "Z"
    return None
fixed = {"1": 1, "0": 0, " 1 + 2 ": 3, "2*3+4": 10, "2*(3+4)": 14, "7//2": 3, "-7//2": -4, "7//-2": -4,
         "-7%3": 2, "7%-3": -2, "-2**2": -4, "(-2)**2": 4, "2**3**2": 512, "2**-0": 1, "--3": 3,
         "-+-3": 3, "2 ** - - 2": 4, "10-4-3": 3, "100//7//2": 7, "2*-3": -6, "0**0": 1, "1+-2**2": -3,
         "(((5)))": 5, "8 % 3 * 2": 4, "-(2+3)**2": -25}
for s, v in fixed.items():
    r = int_eval(s)
    assert r == v and type(r) is int, (s, r, v)
for s in ["", " ", "1 +", "(1", "1)", "1 2", "00", "07", "1+07", "2* *3", "7/ /2", "7/2", "a", "1_0",
          "()", "2**-1", "0**-1", "2**-3**2", "1+(2**-1)", "(1//0)(3)", "1//0 2", "**2", "2***3"]:
    assert err(s) == "V", s
for s in ["1//0", "5%0", "1+2//(3-3)", "(1//0)**-1"]:
    assert err(s) == "Z", s
OK = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Add, ast.Sub, ast.Mult, ast.FloorDiv, ast.Mod, ast.Pow,
      ast.UAdd, ast.USub, ast.Constant)
def oracle(s):
    if re.search(r"(?<![0-9])0[0-9]", s) or re.search(r"[^0-9+\-*/%() ]", s) or "_" in s:
        return "V"
    try:
        tree = ast.parse(s.strip(), mode="eval")
    except SyntaxError:
        return "V"
    for nd in ast.walk(tree):
        if not isinstance(nd, OK) or (isinstance(nd, ast.Constant) and type(nd.value) is not int):
            return "V"
    try:
        v = eval(compile(tree, "<e>", "eval"))
    except ZeroDivisionError:
        return "Z"
    if type(v) is not int:
        return "V"
    return v
random.seed(23)
def num():
    return str(random.choice([0, 0, 1, 2, 3, 5, 7, 10, 13, 99, random.randint(0, 999)]))
def gen(d):
    r = random.random()
    sp = lambda: random.choice(["", "", " "])
    if d <= 0 or r < 0.3:
        a = num()
    elif r < 0.45:
        a = "(" + sp() + gen(d - 1) + sp() + ")"
    elif r < 0.55:
        return random.choice(["-", "+", "-"]) + sp() + gen(d - 1)
    elif r < 0.65:
        a = random.choice([num(), "(" + gen(d - 1) + ")"])
        return a + sp() + "**" + sp() + str(random.randint(0, 3))
    else:
        return gen(d - 1) + sp() + random.choice(["+", "-", "*", "//", "%", "*", "-"]) + sp() + gen(d - 1)
    return a
for _ in range(2500):
    s = gen(4)
    exp = oracle(s)
    got = err(s)
    if got is None:
        got = int_eval(s)
    assert got == exp, (s, got, exp)
    m = list(s)
    m.insert(random.randint(0, len(m)), random.choice("()+*/ 0"))
    s2 = "".join(m)
    exp = oracle(s2)
    got = err(s2)
    if got is None:
        got = int_eval(s2)
    assert got == exp, (s2, got, exp)
''', r'''
def _tokens(s):
    toks, i, n = [], 0, len(s)
    while i < n:
        c = s[i]
        if c == " ":
            i += 1
        elif c.isdigit() and c.isascii():
            j = i
            while j < n and s[j].isdigit() and s[j].isascii():
                j += 1
            lit = s[i:j]
            if len(lit) > 1 and lit[0] == "0":
                raise ValueError("leading zero")
            toks.append(("num", int(lit)))
            i = j
        elif s.startswith("**", i) or s.startswith("//", i):
            toks.append(("op", s[i:i + 2]))
            i += 2
        elif c in "+-*%()":
            toks.append(("op", c))
            i += 1
        else:
            raise ValueError("bad character")
    return toks


def _parse(toks):
    pos = 0

    def peek():
        return toks[pos][1] if pos < len(toks) and toks[pos][0] == "op" else None

    def expr():
        nonlocal pos
        node = term()
        while peek() in ("+", "-"):
            op = toks[pos][1]
            pos += 1
            node = ("bin", op, node, term())
        return node

    def term():
        nonlocal pos
        node = unary()
        while peek() in ("*", "//", "%"):
            op = toks[pos][1]
            pos += 1
            node = ("bin", op, node, unary())
        return node

    def unary():
        nonlocal pos
        if peek() in ("+", "-"):
            op = toks[pos][1]
            pos += 1
            return ("un", op, unary())
        return power()

    def power():
        nonlocal pos
        base = atom()
        if peek() == "**":
            pos += 1
            return ("bin", "**", base, unary())
        return base

    def atom():
        nonlocal pos
        if pos >= len(toks):
            raise ValueError("missing operand")
        kind, v = toks[pos]
        if kind == "num":
            pos += 1
            return ("num", v)
        if v == "(":
            pos += 1
            node = expr()
            if peek() != ")":
                raise ValueError("expected )")
            pos += 1
            return node
        raise ValueError("unexpected token")

    node = expr()
    if pos != len(toks):
        raise ValueError("trailing tokens")
    return node


def _ev(node):
    k = node[0]
    if k == "num":
        return node[1]
    if k == "un":
        v = _ev(node[2])
        return -v if node[1] == "-" else v
    a = _ev(node[2])
    b = _ev(node[3])
    op = node[1]
    if op == "+":
        return a + b
    if op == "-":
        return a - b
    if op == "*":
        return a * b
    if op == "//":
        return a // b
    if op == "%":
        return a % b
    if b < 0:
        raise ValueError("negative exponent")
    return a ** b


def int_eval(expr):
    return _ev(_parse(_tokens(expr)))
''')


task("v2_03_b64_strict", r'''
Write `b64decode_strict(s: str) -> bytes` that decodes standard Base64 (alphabet A-Z, a-z,
0-9, "+", "/", padding "=") and rejects every non-canonical input with ValueError:
- the length must be a multiple of 4 (the empty string decodes to b"");
- only alphabet characters and "=" are allowed (no whitespace, no "-" or "_");
- "=" may appear only at the end of the final 4-character group, at most two of them:
  a final group is either 4 data characters, 3 data characters + "=", or 2 data characters
  + "=="; anything else ("A===", "====", "=" inside the text, padding in a group that is
  not the last one) is an error;
- the unused low bits of the last data character must be zero: with "==" the last data
  character's low 4 bits, with "=" its low 2 bits ("QQ==" is valid, "QR==" is not).
Do not use the base64, binascii or codecs modules.
''', r'''
_banned(mods=("base64", "binascii", "codecs", "email", "quopri", "uu"), attrs=("b64decode",))
import base64, binascii, random
def bad(s):
    try:
        b64decode_strict(s)
    except ValueError:
        return True
    return False
assert b64decode_strict("") == b""
assert b64decode_strict("QQ==") == b"A"
assert b64decode_strict("QUI=") == b"AB"
assert b64decode_strict("QUJD") == b"ABC"
assert b64decode_strict("+/+/") == b"\xfb\xff\xbf"
assert b64decode_strict("AAAA") == b"\x00\x00\x00"
for s in ["Q", "QQ", "QQ=", "QR==", "QUJ=", "A===", "====", "QQ==QUJD", "QU=I", "QQ ==", "-_-_", "QUJD\n",
          "QQ=A", "QUJDQQ", "QUJD====", "=QUJ", "Qé=="]:
    assert bad(s), s
ALPHA = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
random.seed(31)
for _ in range(3000):
    raw = bytes(random.randrange(256) for _ in range(random.randint(0, 20)))
    s = base64.b64encode(raw).decode()
    assert b64decode_strict(s) == raw, s
    r = "".join(random.choice(ALPHA) for _ in range(4 * random.randint(0, 5)))
    assert b64decode_strict(r) == base64.b64decode(r), r
    kind = random.randrange(5)
    if kind == 0 and s:
        i = random.randrange(len(s))
        m = s[:i] + s[i + 1:]
    elif kind == 1 and s:
        i = random.randrange(len(s))
        m = s[:i] + random.choice("-_ .\n*") + s[i + 1:]
    elif kind == 2 and len(s) > 4:
        i = random.randrange(len(s) - 4)
        m = s[:i] + "=" + s[i + 1:]
    elif kind == 3 and s.endswith("=="):
        m = s[:-3] + random.choice([c for i, c in enumerate(ALPHA) if i & 15]) + "=="
    elif kind == 3 and s.endswith("="):
        m = s[:-2] + random.choice([c for i, c in enumerate(ALPHA) if i & 3]) + "="
    else:
        m = s + random.choice(["====", "A===", "QQ", "=", "QQ==QQ=="[:4 * random.randint(1, 2)] + "="])
    assert bad(m), m
''', r'''
_A = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
_IDX = {c: i for i, c in enumerate(_A)}


def b64decode_strict(s):
    if len(s) % 4:
        raise ValueError("length")
    out = bytearray()
    for g in range(0, len(s), 4):
        grp = s[g:g + 4]
        last = g + 4 == len(s)
        data = grp.rstrip("=")
        pad = 4 - len(data)
        if pad > 2 or (pad and not last):
            raise ValueError("padding")
        v = 0
        for c in data:
            if c not in _IDX:
                raise ValueError("character")
            v = v * 64 + _IDX[c]
        if pad == 0:
            out += v.to_bytes(3, "big")
        elif pad == 1:
            if v & 3:
                raise ValueError("non-canonical")
            out += (v >> 2).to_bytes(2, "big")
        else:
            if v & 15:
                raise ValueError("non-canonical")
            out.append(v >> 4)
    return bytes(out)
''')


task("v2_04_ipv6_canonical", r'''
Write `ipv6_canonical(addr: str) -> str` that parses a textual IPv6 address and returns its
canonical form (RFC 5952), raising ValueError for invalid input.
Input rules:
- 8 groups of 1 to 4 hex digits (either case), separated by ":";
- at most one "::", which stands for one or more consecutive zero groups and may appear at
  the start, in the middle or at the end ("1::2:3:4:5:6:7" is valid, "::" alone is valid);
  without "::" there must be exactly 8 groups; with it, at most 7 written groups;
- the last 32 bits may be written as a dotted IPv4 address a.b.c.d (exactly 4 decimal
  parts, each 0-255, no leading zeros), counting as two groups; it must be the final part
  of the address;
- nothing else: no whitespace, no zone suffix ("%eth0"), no brackets, no prefix length, no
  empty groups other than the "::" itself (":1::2", "1::2:", ":::", "1::2::3" are errors).
Output rules: lowercase hex, no leading zeros within a group; the longest run of two or
more consecutive zero groups is replaced by "::" (on a tie, the first run); a single zero
group is written "0" and never compressed. Exception: an IPv4-mapped address (first 80
bits zero, next 16 bits ffff) is written "::ffff:" followed by its last 32 bits in dotted
decimal, e.g. "::ffff:192.0.2.1".
Do not use the ipaddress or socket modules.
''', r'''
_banned(mods=("ipaddress", "socket", "_socket"))
import ipaddress, random
def bad(s):
    try:
        ipv6_canonical(s)
    except ValueError:
        return True
    return False
fixed = {"::": "::", "::1": "::1", "1::": "1::", "0:0:0:0:0:0:0:0": "::", "2001:DB8:0:0:8:800:200C:417A":
         "2001:db8::8:800:200c:417a", "1:0:0:2:0:0:0:3": "1:0:0:2::3", "1:0:0:2:0:0:3:4": "1::2:0:0:3:4",
         "1:0:2:0:3:0:4:0": "1:0:2:0:3:0:4:0", "1::2:3:4:5:6:7": "1:0:2:3:4:5:6:7", "0001:00:000a::": "1:0:a::",
         "::ffff:192.0.2.1": "::ffff:192.0.2.1", "::ffff:c000:201": "::ffff:192.0.2.1", "::1.2.3.4": "::102:304",
         "1:2:3:4:5:6:1.2.3.4": "1:2:3:4:5:6:102:304", "::ffff:0:0": "::ffff:0.0.0.0", "FFFF::": "ffff::",
         "0:0:1::": "0:0:1::"}
for s, v in fixed.items():
    assert ipv6_canonical(s) == v, (s, ipv6_canonical(s), v)
for s in ["", ":", ":::", "1::2::3", ":1:2:3:4:5:6:7", "1:2:3:4:5:6:7:", "1:2:3:4:5:6:7:8:9", "1:2:3:4:5:6:7",
          "12345::", "g::", "::1.2.3", "::1.2.3.256", "::1.2.3.04", "1.2.3.4", "::1.2.3.4:5", "fe80::1%eth0",
          "[::1]", "::1/128", " ::1", "1:2:3:4:5:6:7:8::", "0::0:0:0:0:0:0:0", "1:2:3:4:5:6:7:1.2.3.4", "::-1"]:
    assert bad(s), s
random.seed(37)
def render(g):
    v4 = random.random() < 0.2
    words = ["%x" % x for x in g]
    if random.random() < 0.3:
        words = [w.rjust(random.randint(len(w), 4), "0") for w in words]
    if random.random() < 0.3:
        words = [w.upper() if random.random() < 0.5 else w for w in words]
    if v4:
        words = words[:6] + ["%d.%d.%d.%d" % (g[6] >> 8, g[6] & 255, g[7] >> 8, g[7] & 255)]
    runs = [(i, j) for i in range(len(words)) for j in range(i + 1, len(words) + 1)
            if all(w.strip("0") == "" and "." not in w for w in words[i:j])]
    if runs and random.random() < 0.7:
        i, j = random.choice(runs)
        return ":".join(words[:i]) + "::" + ":".join(words[j:])
    return ":".join(words)
for _ in range(3000):
    g = [random.choice([0, 0, 0, 1, 0xffff, random.randrange(65536)]) for _ in range(8)]
    if random.random() < 0.1:
        g = [0] * 5 + [0xffff] + g[6:]
    s = render(g)
    assert ipv6_canonical(s) == ipaddress.IPv6Address(s).compressed, (s, ipv6_canonical(s))
    m = random.choice([s + ":1", s + "::", "1:" + s, s.replace(":", ":::", 1), s + "0" * 5, s[:-1] + "g",
                       s + ".1", s + "%z", s.replace(":", "", 1), ":" + s, s + ":"])
    try:
        exp = ipaddress.IPv6Address(m).compressed
    except ValueError:
        exp = None
    if "%" in m:
        exp = None
    if exp is None:
        assert bad(m), m
    else:
        assert ipv6_canonical(m) == exp, (m, exp)
''', r'''
_HEX = set("0123456789abcdefABCDEF")


def _v4(p):
    parts = p.split(".")
    if len(parts) != 4:
        raise ValueError("ipv4")
    vals = []
    for x in parts:
        if not x or not all(c in "0123456789" for c in x) or (len(x) > 1 and x[0] == "0") or int(x) > 255:
            raise ValueError("ipv4 part")
        vals.append(int(x))
    return [vals[0] << 8 | vals[1], vals[2] << 8 | vals[3]]


def _groups(parts, v4_last):
    out = []
    for k, p in enumerate(parts):
        if "." in p:
            if not (v4_last and k == len(parts) - 1):
                raise ValueError("ipv4 not last")
            out += _v4(p)
        else:
            if not 1 <= len(p) <= 4 or not all(c in _HEX for c in p):
                raise ValueError("group")
            out.append(int(p, 16))
    return out


def ipv6_canonical(addr):
    if not addr or any(c not in _HEX and c not in ":." for c in addr):
        raise ValueError("character")
    if addr.count("::") > 1 or ":::" in addr:
        raise ValueError("::")
    if "::" in addr:
        head, tail = addr.split("::")
        hp = head.split(":") if head else []
        tp = tail.split(":") if tail else []
        h = _groups(hp, False)
        t = _groups(tp, True)
        if len(h) + len(t) > 7:
            raise ValueError("too many groups")
        g = h + [0] * (8 - len(h) - len(t)) + t
    else:
        g = _groups(addr.split(":"), True)
        if len(g) != 8:
            raise ValueError("group count")
    if g[:5] == [0] * 5 and g[5] == 0xffff:
        return "::ffff:%d.%d.%d.%d" % (g[6] >> 8, g[6] & 255, g[7] >> 8, g[7] & 255)
    best, bl, i = -1, 1, 0
    while i < 8:
        if g[i] == 0:
            j = i
            while j < 8 and g[j] == 0:
                j += 1
            if j - i > bl:
                best, bl = i, j - i
            i = j
        else:
            i += 1
    w = ["%x" % x for x in g]
    if best < 0:
        return ":".join(w)
    return ":".join(w[:best]) + "::" + ":".join(w[best + bl:])
''')


task("v2_05_shell_split", r'''
Write `shell_split(s: str) -> list[str]` that splits a command line into words like a
POSIX shell (no expansion of any kind):
- Outside quotes, whitespace (space, tab, "\n", "\r") separates words; runs of whitespace
  count as one separator; leading and trailing whitespace produce nothing.
- Outside quotes, a backslash makes the next character literal, whatever it is (space,
  quote, backslash, newline). A backslash at the very end raises ValueError.
- Single quotes: every character up to the next single quote is literal, backslashes
  included. Unterminated -> ValueError.
- Double quotes: characters are literal up to the closing double quote, except a
  backslash followed by '"' or by a backslash, which produces that one character; a
  backslash followed by anything else is kept together with that character
  ("a\$b" inside double quotes gives a\$b). Unterminated -> ValueError.
- Quoted and unquoted pieces that touch form a single word (a"b c"'d' gives "ab cd");
  a word made only of quotes ('' or "") is an empty-string word.
- "#" and every other character are ordinary.
Do not use the shlex module.
''', r'''
_banned(mods=("shlex",))
import random, shlex
def res(s):
    try:
        return shell_split(s)
    except ValueError:
        return "ERR"
def ora(s):
    try:
        return shlex.split(s)
    except ValueError:
        return "ERR"
assert shell_split("") == []
assert shell_split("  a  b\t\nc ") == ["a", "b", "c"]
assert shell_split("a\"b c\"'d'") == ["ab cd"]
assert shell_split("x '' y") == ["x", "", "y"]
assert shell_split('""') == [""]
assert shell_split(r"a\ b") == ["a b"]
assert shell_split(r"'a\b'") == [r"a\b"]
assert shell_split(r'"a\$b"') == [r"a\$b"]
assert shell_split(r'"a\"b\\c"') == ['a"b\\c']
assert shell_split("#x y#") == ["#x", "y#"]
assert shell_split("a\\\nb") == ["a\nb"]
for s in ["'abc", '"abc', "abc\\", '"abc\\"', "a 'b\"c"]:
    assert res(s) == "ERR", s
random.seed(41)
for _ in range(4000):
    s = "".join(random.choice("ab \t\n'\"\\#$") for _ in range(random.randint(0, 14)))
    assert res(s) == ora(s), (s, res(s), ora(s))
    words = ["".join(random.choice("ab $'\"\\\n#") for _ in range(random.randint(0, 5))) for _ in range(random.randint(0, 4))]
    s = random.choice([" ", "  ", "\t"]).join(shlex.quote(w) for w in words)
    assert res(s) == words, (s, words)
''', r'''
def shell_split(s):
    out, cur, have, i, n = [], [], False, 0, len(s)
    while i < n:
        c = s[i]
        if c in " \t\r\n":
            if have:
                out.append("".join(cur))
                cur, have = [], False
            i += 1
        elif c == "\\":
            if i + 1 >= n:
                raise ValueError("no escaped character")
            cur.append(s[i + 1])
            have = True
            i += 2
        elif c == "'":
            j = s.find("'", i + 1)
            if j < 0:
                raise ValueError("no closing quotation")
            cur.append(s[i + 1:j])
            have = True
            i = j + 1
        elif c == '"':
            i += 1
            have = True
            while True:
                if i >= n:
                    raise ValueError("no closing quotation")
                c = s[i]
                if c == '"':
                    i += 1
                    break
                if c == "\\":
                    if i + 1 >= n:
                        raise ValueError("no closing quotation")
                    d = s[i + 1]
                    cur.append(d if d in '"\\' else "\\" + d)
                    i += 2
                else:
                    cur.append(c)
                    i += 1
        else:
            cur.append(c)
            have = True
            i += 1
    if have:
        out.append("".join(cur))
    return out
''')


task("v2_06_str_literal", r"""
Write `parse_str_literal(src: str) -> str` that returns the value of a Python string
literal. `src` must be exactly one literal: an optional prefix "r" or "R", then an opening
quote (one ' or one ", or three ' or three " in a row for a triple-quoted string), the
body, and the same closing quote, with nothing before or after (no whitespace, no second
literal). The body ends at the first closing quote that is not consumed by a backslash pair.
Non-raw strings: escape sequences are backslash-newline (removed, line continuation),
\\, \', \", \a, \b, \f, \n, \r, \t, \v; \ooo with 1 to 3 octal digits (the value can exceed
255, e.g. \777 is chr(511)); \xhh with exactly 2 hex digits; \uhhhh with exactly 4;
\Uhhhhhhhh with exactly 8 and a value of at most 0x10FFFF. A backslash followed by any
other character is kept together with that character (\q stays backslash + q).
\N never appears in the tests.
Raw strings (prefix r/R): no escapes at all; a backslash and the character after it are
both kept, and a backslash before the quote character stops that quote from closing the
string (so a raw string cannot end with an odd number of backslashes).
Single-quoted (non-triple) strings may not contain a raw newline character, except as part
of a backslash-newline pair. Triple-quoted strings may contain newlines and lone quote
characters.
Raise ValueError for: missing or unterminated literal, unsupported prefix, raw newline in
a single-quoted string, malformed \x, \u or \U escapes (too few hex digits, \U value above
0x10FFFF), anything after the closing quote.
Do not use eval, exec, compile, the ast/tokenize/codecs modules, or bytes/str .decode.
""", r'''
_banned(mods=("ast", "tokenize", "codecs", "subprocess", "code", "codeop", "builtins", "json", "pickle"),
        names=("eval", "exec", "compile", "__import__", "literal_eval"), attrs=("decode", "literal_eval"))
import ast, io, random, tokenize, warnings
warnings.simplefilter("ignore")
S3, D3 = "'" * 3, '"' * 3
def res(s):
    try:
        return parse_str_literal(s)
    except ValueError:
        return "<ERR>"
def ora(s):
    try:
        toks = [t for t in tokenize.generate_tokens(io.StringIO(s).readline)
                if t.type not in (tokenize.NEWLINE, tokenize.NL, tokenize.ENDMARKER)]
    except (tokenize.TokenError, SyntaxError):
        return "<ERR>"
    if len(toks) != 1 or toks[0].type != tokenize.STRING or toks[0].string != s:
        return "<ERR>"
    try:
        v = ast.literal_eval(s)
    except (SyntaxError, ValueError):
        return "<ERR>"
    return v if type(v) is str else "<ERR>"
fixed = {"''": "", '""': "", S3 + S3: "", "'abc'": "abc", r"'a\nb'": "a\nb", r"'\x41é\U0001F600'": "Aé\U0001F600",
         r"'\101\0\777'": "A\x00ǿ", r"'\q\8'": "\\q\\8", r"'it\'s'": "it's", r'"\""': '"', "'a\\\nb'": "ab",
         r"r'\n'": "\\n", r"R'\''": "\\'", "r'a\\\nb'": "a\\\nb", S3 + "a'b''c" + S3: "a'b''c", D3 + "x\ny" + D3: "x\ny",
         r"'\\'": "\\", r"'\1234'": "S4", r"'\a\b\f\v\r\t'": "\a\b\f\v\r\t", D3 + 'a""b' + D3: 'a""b'}
for s, v in fixed.items():
    assert res(s) == v, (s, res(s), v)
for s in ["", "'", "'abc", "abc", "'a\nb'", "'a' 'b'", "'a'x", " 'a'", "'a' ", "b'a'", "f'a'", r"'\x4'", r"'\u12'",
          r"'\U00110000'", r"r'\'", S3 + "a" + S3 + "'", r"'\U0001F60'", "rr'a'", "'a\""]:
    assert res(s) == "<ERR>", s
random.seed(43)
TOK = ["a", "b", " ", "\n", "'", '"', "\\", "\\n", "\\x4", "\\x41", "\\u00e9", "\\u12", "\\U0001F600",
       "\\U00110000", "\\777", "\\0", "\\12", "\\8", "\\q", "\\\\", "\\\n", "é", "#", "\\'", '\\"', "\\t"]
for _ in range(4000):
    q = random.choice(["'", '"', S3, D3])
    s = random.choice(["", "", "r", "R"]) + q + "".join(random.choice(TOK) for _ in range(random.randint(0, 7))) + q
    assert res(s) == ora(s), (s, res(s), ora(s))
''', r'''
_SIMPLE = {"\\": "\\", "'": "'", '"': '"', "a": "\a", "b": "\b", "f": "\f", "n": "\n", "r": "\r", "t": "\t", "v": "\v"}
_HEXD = set("0123456789abcdefABCDEF")


def parse_str_literal(src):
    i, n, raw = 0, len(src), False
    if src[:1] in ("r", "R"):
        raw, i = True, 1
    if i >= n or src[i] not in "'\"":
        raise ValueError("no literal")
    q = src[i]
    if src[i:i + 3] == q * 3:
        close, triple = q * 3, True
    else:
        close, triple = q, False
    i += len(close)
    out = []
    while True:
        if i >= n:
            raise ValueError("unterminated")
        if src.startswith(close, i):
            i += len(close)
            break
        c = src[i]
        if c == "\n" and not triple:
            raise ValueError("newline in single-quoted string")
        if c != "\\":
            out.append(c)
            i += 1
            continue
        if i + 1 >= n:
            raise ValueError("unterminated")
        d = src[i + 1]
        if raw:
            out.append(c + d)
            i += 2
            continue
        if d == "\n":
            i += 2
        elif d in _SIMPLE:
            out.append(_SIMPLE[d])
            i += 2
        elif d in "01234567":
            j = i + 1
            while j < n and j < i + 4 and src[j] in "01234567":
                j += 1
            out.append(chr(int(src[i + 1:j], 8)))
            i = j
        elif d in "xuU":
            k = {"x": 2, "u": 4, "U": 8}[d]
            h = src[i + 2:i + 2 + k]
            if len(h) != k or not all(ch in _HEXD for ch in h):
                raise ValueError("bad escape")
            v = int(h, 16)
            if v > 0x10FFFF:
                raise ValueError("bad escape")
            out.append(chr(v))
            i += 2 + k
        else:
            out.append(c + d)
            i += 2
    if i != n:
        raise ValueError("trailing characters")
    return "".join(out)
''')


task("v2_07_path_glob", r'''
Write `glob_match(pattern: str, path: str) -> bool` for path globs.
Both strings are split on "/" into segments; empty segments are ordinary segments ("a//b"
has the segments "a", "", "b"; "" has one empty segment). A pattern segment that is exactly
"**" matches zero or more consecutive path segments of any content. Every other pattern
segment matches exactly one path segment, character by character:
- "*" matches any run of characters, possibly empty ("a**b" is just two "*");
- "?" matches exactly one character;
- "[...]" matches one character from a set; a leading "!" negates the set; a "]" right after
  "[" or "[!" is a literal member; "x-y" is an inclusive range when y is not the closing
  "]" (a "-" first or last is literal); inside brackets a backslash is an ordinary member;
- outside brackets, "\" makes the next character literal ("\*", "\?", "\[", "\\");
- any other character matches itself.
Patterns are well-formed: every "[" has a closing "]" with at least one member, ranges
have x <= y, and there is no trailing lone "\". The whole path must be matched.
It must run in polynomial time: e.g. "**/" * 20 + "z" against "a/" * 40 + "b", or
"*a*a*a*a*a*a*b" against "a" * 60, must return quickly. Do not use re, fnmatch, glob or
pathlib.
''', r'''
_banned(mods=("re", "fnmatch", "glob", "pathlib", "sre_compile", "sre_parse", "_sre"))
import random, re, time
from functools import lru_cache
def seg_re(p):
    i, out = 0, ""
    while i < len(p):
        c = p[i]
        if c == "\\":
            out += re.escape(p[i + 1]); i += 2
        elif c == "*":
            out += ".*"; i += 1
        elif c == "?":
            out += "."; i += 1
        elif c == "[":
            j = i + 1
            neg = p[j] == "!"
            if neg:
                j += 1
            items, first = [], True
            while first or p[j] != "]":
                first = False
                if j + 2 < len(p) and p[j + 1] == "-" and p[j + 2] != "]":
                    items.append(re.escape(p[j]) + "-" + re.escape(p[j + 2])); j += 3
                else:
                    items.append(re.escape(p[j])); j += 1
            out += "[" + ("^" if neg else "") + "".join(items) + "]"
            i = j + 1
        else:
            out += re.escape(c); i += 1
    return out
def oracle(pat, path):
    ps, ts = pat.split("/"), path.split("/")
    regs = [None if s == "**" else re.compile(seg_re(s), re.S) for s in ps]
    @lru_cache(None)
    def f(i, j):
        if i == len(ps):
            return j == len(ts)
        if regs[i] is None:
            return any(f(i + 1, k) for k in range(j, len(ts) + 1))
        return j < len(ts) and regs[i].fullmatch(ts[j]) is not None and f(i + 1, j + 1)
    return f(0, 0)
fixed = [("a/**/b", "a/b", True), ("a/**/b", "a/x/y/b", True), ("a/**/b", "a/x/y/c", False), ("**", "", True),
         ("**", "x/y/z", True), ("a/**", "a", True), ("**/b", "b", True), ("a/*", "a/b/c", False),
         ("a*b", "a/b", False), ("a**b", "axxb", True), ("?", "", False), ("?", "/", False), ("", "", True),
         ("a//b", "a//b", True), ("a//b", "a/b", False), ("[!a]", "b", True), ("[!a]", "a", False),
         ("[]a]", "]", True), ("[!]a]", "]", False), ("[a-]", "-", True), ("[-a]", "-", True), ("[\\]", "\\", True),
         ("\\*", "*", True), ("\\*", "a", False), ("\\[a]", "[a]", True), ("[a-c]x", "bx", True), ("[a-c]x", "dx", False),
         ("*.py", ".py", True), ("**/*.py", "src/a/b.py", True), ("**/*.py", "b.py", True), ("x/**/**/y", "x/y", True),
         ("\\\\", "\\", True), ("a/**/", "a/b/", True), ("a/**/", "a/b", False)]
for p, t, e in fixed:
    assert glob_match(p, t) is e, (p, t, e)
random.seed(47)
PT = ["a", "b", ".", "*", "?", "[ab]", "[!a]", "[a-b]", "\\*", "\\?", "[]a]", "[*]", "\\\\", "[!]]"]
def rseg():
    return "".join(random.choice("ab.*?[]\\") for _ in range(random.randint(0, 3)))
def rpat():
    segs = []
    for _ in range(random.randint(1, 4)):
        segs.append("**" if random.random() < 0.25 else "".join(random.choice(PT) for _ in range(random.randint(0, 3))))
    return "/".join(segs)
def from_path(path):
    out = []
    for s in path.split("/"):
        if random.random() < 0.2:
            out.append("**"); continue
        w = ""
        for c in s:
            r = random.random()
            if r < 0.15:
                w += "?"
            elif r < 0.25:
                w += "*"
            elif c in "*?[\\":
                w += "\\" + c
            elif c == "]":
                w += "[]]"
            else:
                w += c
        out.append(w)
    return "/".join(out)
for _ in range(3000):
    path = "/".join(rseg() for _ in range(random.randint(1, 4)))
    for pat in (rpat(), from_path(path)):
        assert glob_match(pat, path) == oracle(pat, path), (pat, path)
t0 = time.perf_counter()
assert glob_match("**/" * 20 + "z", "a/" * 40 + "b") is False
assert glob_match("*a*a*a*a*a*a*b", "a" * 60) is False
assert glob_match("**/" * 15 + "*a*a*a*b", "/".join(["a" * 30] * 20)) is False
assert glob_match("**/" * 15 + "a*", "/".join(["a" * 30] * 20)) is True
assert time.perf_counter() - t0 < 5.0
''', r'''
def _tokens(p):
    toks, i = [], 0
    while i < len(p):
        c = p[i]
        if c == "\\":
            toks.append(("lit", p[i + 1]))
            i += 2
        elif c == "*":
            toks.append(("star",))
            i += 1
        elif c == "?":
            toks.append(("any",))
            i += 1
        elif c == "[":
            j = i + 1
            neg = p[j] == "!"
            if neg:
                j += 1
            items, first = [], True
            while first or p[j] != "]":
                first = False
                if j + 2 < len(p) and p[j + 1] == "-" and p[j + 2] != "]":
                    items.append((p[j], p[j + 2]))
                    j += 3
                else:
                    items.append((p[j], p[j]))
                    j += 1
            toks.append(("cls", neg, items))
            i = j + 1
        else:
            toks.append(("lit", c))
            i += 1
    return toks


def _seg_match(toks, s):
    cur = {0}
    for t in toks:
        if t[0] == "star":
            cur = set(range(min(cur), len(s) + 1))
        elif t[0] == "any":
            cur = {i + 1 for i in cur if i < len(s)}
        elif t[0] == "lit":
            cur = {i + 1 for i in cur if i < len(s) and s[i] == t[1]}
        else:
            cur = {i + 1 for i in cur if i < len(s) and any(a <= s[i] <= b for a, b in t[2]) != t[1]}
        if not cur:
            return False
    return len(s) in cur


def glob_match(pattern, path):
    ps = [None if x == "**" else _tokens(x) for x in pattern.split("/")]
    ts = path.split("/")
    cur = {0}
    for seg in ps:
        if seg is None:
            cur = set(range(min(cur), len(ts) + 1))
        else:
            cur = {j + 1 for j in cur if j < len(ts) and _seg_match(seg, ts[j])}
        if not cur:
            return False
    return len(ts) in cur
''')


task("v2_08_text_justify", r'''
Write `justify(text: str, width: int) -> list[str]` (width >= 1) that formats text into
fully justified lines of exactly `width` characters.
- Words are the maximal runs of non-whitespace characters in `text` (whitespace as in
  str.split()). No words -> [].
- A word longer than `width` is first cut into pieces of exactly `width` characters, the
  last piece holding the remainder; each piece is then an ordinary word.
- Lines are filled greedily: a line takes as many of the next words as fit with single
  spaces between them.
- Every line except the last: with two or more words, the spaces between words are
  widened so the line is exactly `width` long; gap sizes differ by at most one and the
  larger gaps come first (leftmost). A line with a single word is left-aligned and padded
  with spaces on the right.
- The last line: words joined by single spaces, padded with spaces on the right to `width`.
''', r'''
import random
def ora(text, width):
    words = []
    for w in text.split():
        while len(w) > width:
            words.append(w[:width]); w = w[width:]
        words.append(w)
    lines, cur = [], []
    for w in words:
        if cur and len(" ".join(cur + [w])) > width:
            lines.append(cur); cur = []
        cur.append(w)
    if cur:
        lines.append(cur)
    out = []
    for k, ln in enumerate(lines):
        if k == len(lines) - 1 or len(ln) == 1:
            out.append(" ".join(ln).ljust(width))
            continue
        spaces = width - sum(map(len, ln))
        g = len(ln) - 1
        s = ""
        for i, w in enumerate(ln[:-1]):
            s += w + " " * (spaces // g + (1 if i < spaces % g else 0))
        out.append(s + ln[-1])
    return out
assert justify("", 5) == []
assert justify("   \n\t ", 3) == []
assert justify("This is an example of text justification.", 16) == \
    ["This    is    an", "example  of text", "justification.  "]
assert justify("What must be acknowledgment shall be", 16) == ["What   must   be", "acknowledgment  ", "shall be        "]
assert justify("abcdefghij", 4) == ["abcd", "efgh", "ij  "]
assert justify("abcdefgh x", 4) == ["abcd", "efgh", "x   "]
assert justify("a b c d e", 1) == ["a", "b", "c", "d", "e"]
assert justify("a b c", 3) == ["a b", "c  "]
assert justify("aa b c dd", 7) == ["aa  b c", "dd     "]
random.seed(53)
for _ in range(3000):
    text = "".join(random.choice(["a", "b", "cc", "ddd", "eeeeeee", " ", " ", "\n", "\t", "  "]) for _ in range(random.randint(0, 30)))
    w = random.randint(1, 15)
    got = justify(text, w)
    assert got == ora(text, w), (text, w, got)
    assert all(len(x) == w for x in got)
''', r'''
def justify(text, width):
    words = []
    for w in text.split():
        while len(w) > width:
            words.append(w[:width])
            w = w[width:]
        words.append(w)
    out, i = [], 0
    while i < len(words):
        j, length = i + 1, len(words[i])
        while j < len(words) and length + 1 + len(words[j]) <= width:
            length += 1 + len(words[j])
            j += 1
        line = words[i:j]
        if j == len(words) or len(line) == 1:
            out.append(" ".join(line) + " " * (width - length))
        else:
            gaps = len(line) - 1
            total = width - sum(len(w) for w in line)
            q, r = divmod(total, gaps)
            s = ""
            for k, w in enumerate(line[:-1]):
                s += w + " " * (q + (1 if k < r else 0))
            out.append(s + line[-1])
        i = j
    return out
''')


task("v2_09_apply_patch", r'''
Write `apply_patch(old: list[str], patch: str) -> list[str]` that applies a unified diff to
a list of lines (lines carry no newline characters) and returns the new list.
Format of `patch` (lines separated by "\n"):
- The empty string means no changes: return a copy of `old`.
- Otherwise the first two lines are a header, "--- <name>" then "+++ <name>"; skip them.
  At least one hunk must follow.
- Each hunk starts with "@@ -S,C +S2,C2 @@" (exactly this shape); ",C" or ",C2" may be
  omitted, meaning a count of 1. S/C describe the old side, S2/C2 the new side. With a
  count of at least 1, S is the 1-based number of the hunk's first line; with a count of
  0 the hunk inserts (or deletes) at a point and S is the number of the line just before
  that point (0 = before the first line).
- Then come body lines. Each starts with " " (context, present in old and new), "-" (only
  in old) or "+" (only in new), followed by the line's text, which can be anything,
  including text that starts with "-", "+", "@@" or "--- ". The header counts decide where
  a hunk ends: the hunk has exactly C lines of kind " " or "-" and C2 lines of kind " " or
  "+". After a hunk comes the next "@@" header or the end of the patch.
Validation, raise ValueError when violated: header lines present; hunk headers well-formed;
context and "-" lines equal the corresponding old lines; a hunk never starts before the
end of the previous hunk or beyond the end of `old`; the body has exactly the stated counts
(a line whose kind would exceed its side's count, a line with another first character, or
the patch ending early is an error); the new-side start S2 is consistent: the hunk's
0-based new start (S2-1, or S2 when C2 is 0) must equal its 0-based old start (S-1, or S
when C is 0) plus the total (C2 - C) of all previous hunks.
Do not use difflib.
''', r'''
_banned(mods=("difflib",))
import difflib, random
def bad(old, p):
    try:
        apply_patch(old, p)
    except ValueError:
        return True
    return False
def mk(a, b, n=3):
    return "\n".join(difflib.unified_diff(a, b, "a", "b", n=n, lineterm=""))
assert apply_patch(["x"], "") == ["x"]
assert apply_patch([], mk([], ["a", "b"])) == ["a", "b"]
assert apply_patch(["a", "b"], mk(["a", "b"], [])) == []
assert apply_patch(["a"], "--- a\n+++ b\n@@ -1 +1 @@\n-a\n+b") == ["b"]
assert apply_patch(["a", "c"], "--- a\n+++ b\n@@ -1,0 +2 @@\n+b") == ["a", "b", "c"]
assert apply_patch(["-- x", "y"], "--- a\n+++ b\n@@ -1,2 +1,2 @@\n--- x\n+++ x\n y") == ["++ x", "y"]
assert apply_patch(["@@ -1 +1 @@", ""], "--- a\n+++ b\n@@ -1,2 +1,1 @@\n-@@ -1 +1 @@\n ") == [""]
assert apply_patch(["a", "b", "c"], "--- a\n+++ b\n@@ -2 +1,0 @@\n-b") == ["a", "c"]
for old, p in [(["a"], "@@ -1 +1 @@\n-a\n+b"), (["a"], "--- a\n+++ b"), (["a"], "--- a\n+++ b\n@@ -1 +1 @@\n-x\n+b"),
               (["a"], "--- a\n+++ b\n@@ -1,2 +1 @@\n-a\n+b"), (["a"], "--- a\n+++ b\n@@ -1 +1 @@\n-a\n+b\n+c"),
               (["a"], "--- a\n+++ b\n@@ -1 +2 @@\n-a\n+b"), (["a"], "--- a\n+++ b\n@@ -3,0 +4 @@\n+b"),
               (["a"], "--- a\n+++ b\n@@ -1 +1 @@\n*a\n+b"), (["a"], "--- a\n+++ b\n@@ -1 +1 @@ x\n-a\n+b"),
               (["a", "b"], "--- a\n+++ b\n@@ -2 +2 @@\n-b\n+c\n@@ -1 +1 @@\n-a\n+d"), (["a"], "--- a\n+++ b\n@@ -a +1 @@\n-a\n+b")]:
    assert bad(old, p), p
random.seed(59)
L = ["a", "b", "", "-- a", "++ b", "@@ c", " d", "x y", "--- a", "+++ b"]
for _ in range(2500):
    old = [random.choice(L) for _ in range(random.randint(0, 12))]
    new = []
    for x in old:
        r = random.random()
        if r < 0.15:
            continue
        if r < 0.3:
            new.append(random.choice(L))
        else:
            new.append(x)
        if random.random() < 0.15:
            new.append(random.choice(L))
    if random.random() < 0.2:
        new.insert(0, random.choice(L))
    p = mk(old, new, random.randint(0, 3))
    assert apply_patch(old, p) == new, (old, new, p)
    if not p:
        continue
    lines = p.split("\n")
    hunks = [i for i, x in enumerate(lines) if x.startswith("@@ -") and i >= 2]
    body = [i for i in range(2, len(lines)) if i not in hunks and lines[i][:1] in " -"]
    kind = random.randrange(3)
    if kind == 0 and body:
        i = random.choice(body)
        lines[i] = lines[i][0] + "XX" + lines[i][1:]
    elif kind == 1:
        i = random.choice(hunks)
        h = lines[i]
        mid = h.index(" +")
        lines[i] = h[:mid] + " +" + str(int(h[mid + 2:].split(",")[0].split(" ")[0]) + 1) + h[mid + 2 + len(h[mid + 2:].split(",")[0].split(" ")[0]):]
    else:
        i = random.choice(hunks)
        h = lines[i]
        old_part = h[4:h.index(" +")]
        s, _, c = old_part.partition(",")
        c = int(c) if c else 1
        lines[i] = "@@ -" + s + "," + str(c + 1) + h[h.index(" +"):]
    assert bad(old, "\n".join(lines)), (old, lines)
''', r'''
import re

_H = re.compile(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@\Z")


def apply_patch(old, patch):
    if patch == "":
        return list(old)
    lines = patch.split("\n")
    if len(lines) < 3 or not lines[0].startswith("--- ") or not lines[1].startswith("+++ "):
        raise ValueError("header")
    out, pos, delta, i = [], 0, 0, 2
    while i < len(lines):
        m = _H.match(lines[i])
        if not m:
            raise ValueError("hunk header")
        s, c = int(m.group(1)), int(m.group(2)) if m.group(2) is not None else 1
        s2, c2 = int(m.group(3)), int(m.group(4)) if m.group(4) is not None else 1
        start = s - 1 if c > 0 else s
        nstart = s2 - 1 if c2 > 0 else s2
        if start < pos or start > len(old) or start < 0:
            raise ValueError("hunk position")
        if nstart != start + delta:
            raise ValueError("new start")
        out.extend(old[pos:start])
        pos = start
        so = sn = 0
        i += 1
        while so < c or sn < c2:
            if i >= len(lines):
                raise ValueError("patch ends early")
            ln = lines[i]
            tag, body = ln[:1], ln[1:]
            if tag == " " and so < c and sn < c2:
                if pos >= len(old) or old[pos] != body:
                    raise ValueError("context mismatch")
                out.append(body)
                pos += 1
                so += 1
                sn += 1
            elif tag == "-" and so < c:
                if pos >= len(old) or old[pos] != body:
                    raise ValueError("removed line mismatch")
                pos += 1
                so += 1
            elif tag == "+" and sn < c2:
                out.append(body)
                sn += 1
            else:
                raise ValueError("bad body line")
            i += 1
        delta += c2 - c
    out.extend(old[pos:])
    return out
''')


task("v2_10_xml_lite", r'''
Write `parse_xml(s: str)` that parses a small XML subset and returns the root element as a
tuple `(tag, attrs, children)`: `attrs` is a dict of str -> str, `children` a list of str
and element tuples in document order. Adjacent text (including text produced by
references) is merged into one string; empty strings never appear; whitespace in text is
kept exactly, so whitespace-only text between elements is a child string.
Grammar:
- Document: optional whitespace, exactly one element, optional whitespace, end. Whitespace
  is space, tab, "\n", "\r". Nothing else may appear outside the root.
- Name: first character A-Z, a-z or "_", then any of A-Z, a-z, 0-9, "_", ".", "-".
- Element: "<" Name, then zero or more attributes each preceded by at least one
  whitespace character, then optional whitespace, then either "/>" (empty element) or ">"
  content "</" Name optional-whitespace ">" where the end name equals the start name
  (case-sensitive).
- Attribute: Name, optional whitespace, "=", optional whitespace, a value in single or
  double quotes. The value may not contain "<" or its own quote character; "&" starts a
  reference. Values are returned as written apart from references (no whitespace
  normalization). Attribute names within one element must be distinct.
- Content: text characters (anything except "<" and "&"; ">" is allowed), references, and
  child elements.
- References: &lt; &gt; &amp; &quot; &apos; (giving < > & " '), &#DDD; (decimal) and
  &#xHHH; (hex digits of either case, lowercase "x" only), at least one digit; the code
  point must be 1..0x10FFFF and not a surrogate (D800-DFFF).
Anything else raises ValueError, including: comments, processing instructions, CDATA or
doctype ("<!" or "<?"), unknown entities, a "&" not forming a reference, a missing ";",
a "<" not starting a tag, mismatched or unclosed tags, duplicate attributes, attributes
not separated by whitespace, unquoted values, two root elements, text outside the root,
empty input. Do not use the xml, html or pyexpat modules.
''', r'''
_banned(mods=("xml", "html", "pyexpat", "_elementtree", "xmlrpc", "plistlib"))
import random
def bad(s):
    try:
        parse_xml(s)
    except ValueError:
        return True
    return False
assert parse_xml("<a/>") == ("a", {}, [])
assert parse_xml(" \n<a></a>\t") == ("a", {}, [])
assert parse_xml("<a> </a>") == ("a", {}, [" "])
assert parse_xml("<a>x &lt; y &amp;&gt; z</a>") == ("a", {}, ["x < y &> z"])
assert parse_xml('<a k = "1"  j=\'2\' />') == ("a", {"k": "1", "j": "2"}, [])
assert parse_xml("<a>&#x1F600;&#65;&#X41;</a>".replace("&#X41;", "&#x4a;")) == ("a", {}, ["\U0001F600AJ"])
assert parse_xml("<a>\n <b/>\n</a >") == ("a", {}, ["\n ", ("b", {}, []), "\n"])
assert parse_xml("<a b=\"x>y\" c='\"' d=\"&apos;&quot;\"/>") == ("a", {"b": "x>y", "c": '"', "d": "'\""}, [])
assert parse_xml("<d.e-1><_x>t</_x>]]>u<y/></d.e-1>") == ("d.e-1", {}, [("_x", {}, ["t"]), "]]>u", ("y", {}, [])])
assert parse_xml("<a k='a\tb\nc'/>") == ("a", {"k": "a\tb\nc"}, [])
for s in ["", "   ", "<a>", "<a></A>", "<a></b>", "<1a/>", "<a/><b/>", "<a/>x", "x<a/>", "<a>< b/></a>",
          "<a>&foo;</a>", "<a>&amp</a>", "<a>a & b</a>", "<a>&#0;</a>", "<a>&#xD800;</a>", "<a>&#x110000;</a>",
          "<a>&#;</a>", "<a>&#x;</a>", "<a>&#X41;</a>", "<a><!-- c --></a>", "<a><?p?></a>", "<a><![CDATA[x]]></a>",
          '<a k="1" k="2"/>', '<a k="1"j="2"/>', "<a k=1/>", '<a k="a<b"/>', '<a k="1/>', "<a k/>", '<a k="&x;"/>',
          "<a k='a''/>", "<a/ >", "< a/>", "<a><b></a></b>", "<a>&amp ;</a>", "<!DOCTYPE a><a/>", "<?xml version='1.0'?><a/>"]:
    assert bad(s), s
random.seed(61)
TAGS = ["a", "b", "c_1", "d.e", "x-y", "_z", "A9"]
ANAMES = ["k", "id", "v-1", "_", "x.y"]
def S():
    return random.choice([" ", "  ", "\n", "\t "])
def S0():
    return random.choice(["", "", " ", "\n"])
def esc(c, q):
    if c == "<":
        opts = ["&lt;", "&#60;", "&#x3c;", "&#x3C;"]
    elif c == "&":
        opts = ["&amp;", "&#38;", "&#x26;"]
    elif c == q:
        opts = ["&quot;" if c == '"' else "&apos;", "&#%d;" % ord(c)]
    elif c in "\"'>":
        opts = [c, c, {'"': "&quot;", "'": "&apos;", ">": "&gt;"}[c]]
    else:
        opts = [c, c, c, "&#%d;" % ord(c), "&#x%x;" % ord(c), "&#x%X;" % ord(c)]
    return random.choice(opts)
def rstr(lo, hi, chars):
    return "".join(random.choice(chars) for _ in range(random.randint(lo, hi)))
def gen(d):
    tag = random.choice(TAGS)
    attrs = {n: rstr(0, 4, "ab <>&\"'é;") for n in random.sample(ANAMES, random.randint(0, 2))}
    raw = []
    for _ in range(random.randint(0, 4)):
        if d > 0 and random.random() < 0.5:
            raw.append(gen(d - 1))
        else:
            raw.append(rstr(1, 5, "ab <>&\"'\n\té;#x"))
    kids = []
    for x in raw:
        if isinstance(x, str) and kids and isinstance(kids[-1], str):
            kids[-1] += x
        else:
            kids.append(x)
    return (tag, attrs, kids)
def ser(e):
    tag, attrs, kids = e
    out = "<" + tag
    for n, v in attrs.items():
        q = random.choice("\"'")
        out += S() + n + S0() + "=" + S0() + q + "".join(esc(c, q) for c in v) + q
    out += S0()
    if not kids and random.random() < 0.5:
        return out + "/>"
    out += ">"
    for k in kids:
        out += "".join(esc(c, None) for c in k) if isinstance(k, str) else ser(k)
    return out + "</" + tag + S0() + ">"
BAD = ["< x", "a & b", "&foo;", "&#0;", "&#xD800;", "&#x110000;", "&lt", "&#;", "&#x;", "<!-- c -->", "<?pi?>",
       "<![CDATA[x]]>", "</q>", "<q>", "&#X41;", "&amp ;", "<q k='1'k='2'/>", "<q k='1' k='2'/>", "<q k=v/>"]
for _ in range(2500):
    e = gen(3)
    doc = S0() + ser(e) + S0()
    assert parse_xml(doc) == e, (doc, e)
    r = random.random()
    if r < 0.2:
        m = doc + random.choice(["<b/>", "x", "&amp;", "<"])
    elif r < 0.3:
        m = random.choice(["x", "&#65;", "<?p?>"]) + doc
    else:
        m = "<r>" + doc + random.choice(BAD) + "</r>"
    assert bad(m), m
''', r'''
_NS = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_")
_NC = _NS | set("0123456789.-")
_WS = " \t\n\r"
_ENT = {"lt": "<", "gt": ">", "amp": "&", "quot": '"', "apos": "'"}
_HEX = set("0123456789abcdefABCDEF")


def parse_xml(s):
    pos, n = 0, len(s)

    def ws():
        nonlocal pos
        start = pos
        while pos < n and s[pos] in _WS:
            pos += 1
        return pos > start

    def name():
        nonlocal pos
        if pos >= n or s[pos] not in _NS:
            raise ValueError("bad name")
        j = pos + 1
        while j < n and s[j] in _NC:
            j += 1
        nm, pos = s[pos:j], j
        return nm

    def expect(t):
        nonlocal pos
        if not s.startswith(t, pos):
            raise ValueError("expected " + t)
        pos += len(t)

    def ref():
        nonlocal pos
        j = s.find(";", pos)
        if j < 0:
            raise ValueError("missing ;")
        body = s[pos + 1:j]
        if body in _ENT:
            ch = _ENT[body]
        else:
            if body.startswith("#x") and len(body) > 2 and all(c in _HEX for c in body[2:]):
                cp = int(body[2:], 16)
            elif body.startswith("#") and len(body) > 1 and all(c in "0123456789" for c in body[1:]):
                cp = int(body[1:])
            else:
                raise ValueError("bad reference")
            if not 1 <= cp <= 0x10FFFF or 0xD800 <= cp <= 0xDFFF:
                raise ValueError("bad code point")
            ch = chr(cp)
        pos = j + 1
        return ch

    def element():
        nonlocal pos
        expect("<")
        tag = name()
        attrs = {}
        while True:
            had = ws()
            if s.startswith("/>", pos):
                pos += 2
                return (tag, attrs, [])
            if pos < n and s[pos] == ">":
                pos += 1
                break
            if not had:
                raise ValueError("attribute needs whitespace")
            an = name()
            ws()
            expect("=")
            ws()
            if pos >= n or s[pos] not in "\"'":
                raise ValueError("unquoted value")
            q = s[pos]
            pos += 1
            val = []
            while True:
                if pos >= n:
                    raise ValueError("unterminated value")
                c = s[pos]
                if c == q:
                    pos += 1
                    break
                if c == "<":
                    raise ValueError("< in value")
                if c == "&":
                    val.append(ref())
                else:
                    val.append(c)
                    pos += 1
            if an in attrs:
                raise ValueError("duplicate attribute")
            attrs[an] = "".join(val)
        kids, text = [], []
        while True:
            if pos >= n:
                raise ValueError("unclosed element")
            c = s[pos]
            if c == "<":
                if text:
                    kids.append("".join(text))
                    text = []
                if s.startswith("</", pos):
                    pos += 2
                    if name() != tag:
                        raise ValueError("mismatched end tag")
                    ws()
                    expect(">")
                    return (tag, attrs, kids)
                kids.append(element())
            elif c == "&":
                text.append(ref())
            else:
                text.append(c)
                pos += 1

    ws()
    if pos >= n or s[pos] != "<":
        raise ValueError("no root element")
    root = element()
    ws()
    if pos != n:
        raise ValueError("content after root")
    return root
''')


task("v2_11_scc_order", r'''
Write `scc_order(n: int, edges: list[tuple[int, int]]) -> list[list[int]]` that returns the
strongly connected components of a directed graph with vertices 0..n-1. `edges` holds
directed edges (u, v); it may contain duplicates and self-loops. Every vertex belongs to
exactly one component (an isolated vertex is its own component).
Canonical output: each component is a list sorted ascending. The components are listed in
a topological order of the condensation: if any edge goes from a vertex of component A to a
vertex of component B (A != B), A comes before B. Among all such orders, build the list one
component at a time and always append the component, among those whose predecessors are all
already listed, whose smallest vertex is smallest. n = 0 returns [].
Must handle n up to 100000 and 200000 edges in a few seconds, including a single path
0 -> 1 -> ... -> n-1 (deep recursion will overflow the Python stack).
''', r'''
import random, time
def _oracle(n, edges):
    adj = [set() for _ in range(n)]
    for u, v in edges:
        adj[u].add(v)
    reach = []
    for s in range(n):
        seen = {s}; todo = [s]
        while todo:
            x = todo.pop()
            for y in adj[x]:
                if y not in seen:
                    seen.add(y); todo.append(y)
        reach.append(seen)
    comps, done = [], set()
    for v in range(n):
        if v not in done:
            c = sorted(u for u in range(n) if u in reach[v] and v in reach[u])
            done |= set(c); comps.append(c)
    out, left = [], comps[:]
    while left:
        def has_pred(c):
            cs = set(c)
            return any(o is not c and any(y in cs for x in o for y in adj[x]) for o in left)
        nxt = min((c for c in left if not has_pred(c)), key=lambda c: c[0])
        out.append(nxt); left.remove(nxt)
    return out
assert scc_order(0, []) == []
assert scc_order(1, [(0, 0)]) == [[0]]
assert scc_order(3, []) == [[0], [1], [2]]
assert scc_order(3, [(2, 0)]) == [[1], [2], [0]]
assert scc_order(4, [(0, 1), (1, 0), (2, 3), (3, 2), (3, 1)]) == [[2, 3], [0, 1]]
assert scc_order(5, [(4, 3), (3, 4), (1, 2), (2, 1), (2, 3), (0, 0)]) == [[0], [1, 2], [3, 4]]
random.seed(31)
for _ in range(600):
    n = random.randint(1, 10)
    m = random.randint(0, 2 * n)
    edges = [(random.randrange(n), random.randrange(n)) for _ in range(m)]
    assert scc_order(n, edges) == _oracle(n, edges), (n, edges)
n = 100000
t0 = time.perf_counter()
r = scc_order(n, [(i, i + 1) for i in range(n - 1)])
assert r == [[i] for i in range(n)]
r = scc_order(n, [(i, i + 1) for i in range(n - 1)] + [(n - 1, 0)])
assert r == [list(range(n))]
edges = [(random.randrange(n), random.randrange(n)) for _ in range(200000)]
r = scc_order(n, edges)
assert sorted(v for c in r for v in c) == list(range(n))
assert time.perf_counter() - t0 < 8.0
''', r'''
import heapq

def scc_order(n, edges):
    adj = [[] for _ in range(n)]
    for u, v in edges:
        adj[u].append(v)
    index = [-1] * n
    low = [0] * n
    onst = [False] * n
    it = [0] * n
    comp = [-1] * n
    st = []
    idx = nc = 0
    for s in range(n):
        if index[s] != -1:
            continue
        index[s] = low[s] = idx; idx += 1
        st.append(s); onst[s] = True
        stack = [s]
        while stack:
            v = stack[-1]
            if it[v] < len(adj[v]):
                w = adj[v][it[v]]; it[v] += 1
                if index[w] == -1:
                    index[w] = low[w] = idx; idx += 1
                    st.append(w); onst[w] = True
                    stack.append(w)
                elif onst[w] and index[w] < low[v]:
                    low[v] = index[w]
            else:
                stack.pop()
                if stack and low[v] < low[stack[-1]]:
                    low[stack[-1]] = low[v]
                if low[v] == index[v]:
                    while True:
                        w = st.pop(); onst[w] = False; comp[w] = nc
                        if w == v:
                            break
                    nc += 1
    members = [[] for _ in range(nc)]
    for v in range(n):
        members[comp[v]].append(v)
    cadj = [set() for _ in range(nc)]
    for u, v in edges:
        if comp[u] != comp[v]:
            cadj[comp[u]].add(comp[v])
    indeg = [0] * nc
    for c in range(nc):
        for d in cadj[c]:
            indeg[d] += 1
    h = [(members[c][0], c) for c in range(nc) if indeg[c] == 0]
    heapq.heapify(h)
    out = []
    while h:
        _, c = heapq.heappop(h)
        out.append(members[c])
        for d in cadj[c]:
            indeg[d] -= 1
            if indeg[d] == 0:
                heapq.heappush(h, (members[d][0], d))
    return out
''')


task("v2_12_min_cost_flow", r'''
Write `min_cost_max_flow(n: int, edges: list[tuple[int, int, int, int]], s: int, t: int) -> tuple[int, int]`.
The network has vertices 0..n-1 and directed edges (u, v, capacity, cost). Capacities are
integers >= 0 (they can be as large as 10**9); costs are integers and may be negative, but the
network contains no directed cycle of negative total cost. Parallel edges and edges in both
directions between the same pair are allowed and are independent; self-loops may appear and
are useless. Return (F, C): F is the maximum flow value from s to t, and C is the minimum total
cost (sum of flow * cost over edges) over all flows of value F. If s == t return (0, 0).
Must be fast for n up to 60 and 300 edges with capacities up to 10**9 (pushing flow one unit
at a time is far too slow).
''', r'''
import random, time
def _oracle(n, edges, s, t):
    if s == t:
        return (0, 0)
    g = [[] for _ in range(n)]
    fw = []
    for u, v, c, w in edges:
        a = [v, c, w, None]; b = [u, 0, -w, a]; a[3] = b
        g[u].append(a); g[v].append(b); fw.append((a, c, w))
    flow = 0
    while True:
        par = [None] * n; par[s] = -1; q = [s]
        for x in q:
            for e in g[x]:
                if e[1] > 0 and par[e[0]] is None:
                    par[e[0]] = e; q.append(e[0])
        if par[t] is None:
            break
        path, v = [], t
        while v != s:
            e = par[v]; path.append(e); v = e[3][0]
        b = min(e[1] for e in path)
        for e in path:
            e[1] -= b; e[3][1] += b
        flow += b
    while True:
        dist = [0] * n; pred = [None] * n; last = -1
        for _ in range(n):
            last = -1
            for x in range(n):
                for e in g[x]:
                    if e[1] > 0 and dist[x] + e[2] < dist[e[0]]:
                        dist[e[0]] = dist[x] + e[2]; pred[e[0]] = e; last = e[0]
        if last == -1:
            break
        for _ in range(n):
            last = pred[last][3][0]
        cyc, v = [], last
        while True:
            e = pred[v]; cyc.append(e); v = e[3][0]
            if v == last:
                break
        b = min(e[1] for e in cyc)
        for e in cyc:
            e[1] -= b; e[3][1] += b
    return (flow, sum((c - a[1]) * w for a, c, w in fw))
assert min_cost_max_flow(2, [], 0, 1) == (0, 0)
assert min_cost_max_flow(3, [(0, 1, 5, 2)], 1, 1) == (0, 0)
assert min_cost_max_flow(2, [(0, 1, 3, 4), (0, 1, 2, 1)], 0, 1) == (5, 14)
assert min_cost_max_flow(4, [(0, 1, 2, 1), (0, 2, 2, 5), (1, 3, 1, 1), (2, 3, 3, 1), (1, 2, 5, 1)], 0, 3) == (4, 17)
assert min_cost_max_flow(3, [(0, 1, 4, -3), (1, 2, 4, 1), (0, 2, 1, 7), (1, 1, 9, -1)], 0, 2) == (5, -1)
random.seed(47)
for _ in range(500):
    n = random.randint(2, 6)
    p = [random.randint(-4, 4) for _ in range(n)]
    edges = []
    for _ in range(random.randint(0, 14)):
        u, v = random.randrange(n), random.randrange(n)
        base = random.randint(0, 4)
        edges.append((u, v, random.choice([0, 1, 2, 3, 5, 9]), base + p[u] - p[v] if u != v else base))
    s, t = random.sample(range(n), 2) if random.random() < 0.95 else (0, 0)
    assert min_cost_max_flow(n, edges, s, t) == _oracle(n, edges, s, t), (n, edges, s, t)
t0 = time.perf_counter()
for _ in range(3):
    n = 60
    p = [random.randint(-1000, 1000) for _ in range(n)]
    edges = []
    for _ in range(300):
        u, v = random.randrange(n), random.randrange(n)
        base = random.randint(0, 1000)
        edges.append((u, v, random.randint(10**8, 10**9), base + p[u] - p[v] if u != v else base))
    r = min_cost_max_flow(n, edges, 0, n - 1)
    assert isinstance(r, tuple) and len(r) == 2
assert min_cost_max_flow(3, [(0, 1, 10**9, 1), (1, 2, 10**9, 1), (0, 2, 10**9 - 1, 3)], 0, 2) == (2 * 10**9 - 1, 2 * 10**9 + 3 * (10**9 - 1))
assert time.perf_counter() - t0 < 8.0
''', r'''
from collections import deque

def min_cost_max_flow(n, edges, s, t):
    if s == t:
        return (0, 0)
    to, cap, cost, head, nxt = [], [], [], [-1] * n, []
    def add(u, v, c, w):
        to.append(v); cap.append(c); cost.append(w); nxt.append(head[u]); head[u] = len(to) - 1
    for u, v, c, w in edges:
        if u == v:
            continue
        add(u, v, c, w); add(v, u, 0, -w)
    flow = total = 0
    INF = float("inf")
    while True:
        dist = [INF] * n; inq = [False] * n; pe = [-1] * n
        dist[s] = 0; q = deque([s]); inq[s] = True
        while q:
            x = q.popleft(); inq[x] = False
            e = head[x]
            while e != -1:
                if cap[e] > 0 and dist[x] + cost[e] < dist[to[e]]:
                    y = to[e]; dist[y] = dist[x] + cost[e]; pe[y] = e
                    if not inq[y]:
                        inq[y] = True; q.append(y)
                e = nxt[e]
        if dist[t] == INF:
            break
        b, v = INF, t
        while v != s:
            e = pe[v]; b = min(b, cap[e]); v = to[e ^ 1]
        v = t
        while v != s:
            e = pe[v]; cap[e] -= b; cap[e ^ 1] += b; v = to[e ^ 1]
        flow += b; total += b * dist[t]
    return (flow, total)
''')


task("v2_13_lex_matching", r'''
Write `lex_matching(n_left: int, n_right: int, edges: list[tuple[int, int]]) -> list[int]` for a
bipartite graph with left vertices 0..n_left-1 and right vertices 0..n_right-1; each edge
(i, j) allows left i to be matched with right j (duplicates possible). A matching uses each
vertex at most once. Return a list m of length n_left where m[i] is the right vertex matched
to left i, or -1 if left i is unmatched. The matching must have maximum size. Among all
maximum matchings return the lexicographically smallest list, where for this comparison -1
counts as larger than every right index (so m[0] is as small as possible, then m[1], ...).
Must handle n_left = n_right = 30 with a few hundred edges well within a second or two.
''', r'''
import random, time
def _oracle(nl, nr, edges):
    adj = [sorted({j for i2, j in edges if i2 == i}) for i in range(nl)]
    best = [None]
    def key(m):
        return (-sum(x != -1 for x in m), [x if x != -1 else nr + 1 for x in m])
    def rec(i, used, m):
        if i == nl:
            if best[0] is None or key(m) < key(best[0]):
                best[0] = m[:]
            return
        for j in adj[i]:
            if j not in used:
                used.add(j); m.append(j); rec(i + 1, used, m); m.pop(); used.discard(j)
        m.append(-1); rec(i + 1, used, m); m.pop()
    rec(0, set(), [])
    return best[0]
assert lex_matching(0, 3, []) == []
assert lex_matching(2, 0, []) == [-1, -1]
assert lex_matching(2, 2, [(0, 0), (1, 0)]) == [0, -1]
assert lex_matching(2, 2, [(0, 0), (0, 1), (1, 0)]) == [1, 0]
assert lex_matching(3, 3, [(0, 0), (0, 1), (1, 1), (2, 1), (2, 2)]) == [0, 1, 2]
assert lex_matching(3, 2, [(0, 0), (1, 0), (2, 1), (1, 1)]) == [0, 1, -1]
assert lex_matching(3, 2, [(0, 1), (1, 0), (2, 0)]) == [1, 0, -1]
random.seed(53)
for _ in range(700):
    nl, nr = random.randint(1, 6), random.randint(1, 6)
    edges = [(random.randrange(nl), random.randrange(nr)) for _ in range(random.randint(0, nl * nr))]
    assert lex_matching(nl, nr, edges) == _oracle(nl, nr, edges), (nl, nr, edges)
t0 = time.perf_counter()
for _ in range(3):
    nl = nr = 30
    edges = [(i, j) for i in range(nl) for j in range(nr) if random.random() < 0.3]
    m = lex_matching(nl, nr, edges)
    es = set(edges)
    assert len(m) == nl and all(x == -1 or (i, x) in es for i, x in enumerate(m))
    assert len({x for x in m if x != -1}) == sum(x != -1 for x in m)
assert time.perf_counter() - t0 < 6.0
''', r'''
def _max_match(adj, lefts, banned_right, nr):
    match_r = [-1] * nr
    def aug(i, seen):
        for j in adj[i]:
            if j in banned_right or seen[j]:
                continue
            seen[j] = True
            if match_r[j] == -1 or aug(match_r[j], seen):
                match_r[j] = i
                return True
        return False
    c = 0
    for i in lefts:
        if aug(i, [False] * nr):
            c += 1
    return c

def lex_matching(n_left, n_right, edges):
    adj = [sorted({j for i2, j in edges if i2 == i}) for i in range(n_left)]
    total = _max_match(adj, range(n_left), set(), n_right)
    res, used, got = [], set(), 0
    for i in range(n_left):
        rest = range(i + 1, n_left)
        chosen = -1
        for j in adj[i]:
            if j in used:
                continue
            used.add(j)
            if got + 1 + _max_match(adj, rest, used, n_right) == total:
                chosen = j
                break
            used.discard(j)
        if chosen != -1:
            got += 1
        res.append(chosen)
    return res
''')


task("v2_14_lfu_cache", r'''
Write `lfu_run(capacity: int, ops: list[tuple]) -> list` that simulates an LFU cache and returns
the results of all get operations in order. Operations:
- ("get", key): if key is cached, return its value and count one use of the key; otherwise
  return None (a miss does not change anything).
- ("put", key, value): if key is cached, replace its value and count one use. Otherwise, if
  the cache already holds `capacity` keys, first evict one key, then insert the new key with a
  use count of 1.
Every get hit and every put counts as a use and makes that key the most recently used.
Eviction removes the key with the smallest use count; among those, the key whose most recent
use is oldest. An evicted key that is put again starts from count 1. With capacity 0 every put
is ignored. Keys and values are hashable / arbitrary objects.
Must handle 200000 operations with capacity 5000 in a couple of seconds.
''', r'''
import random, time
def _oracle(cap, ops):
    store, cnt, last, out = {}, {}, {}, []
    for t, op in enumerate(ops):
        if op[0] == "get":
            k = op[1]
            if k in store:
                cnt[k] += 1; last[k] = t; out.append(store[k])
            else:
                out.append(None)
        else:
            _, k, v = op
            if cap == 0:
                continue
            if k in store:
                store[k] = v; cnt[k] += 1; last[k] = t
            else:
                if len(store) >= cap:
                    x = min(store, key=lambda q: (cnt[q], last[q]))
                    del store[x], cnt[x], last[x]
                store[k] = v; cnt[k] = 1; last[k] = t
    return out
assert lfu_run(0, [("put", 1, 1), ("get", 1)]) == [None]
assert lfu_run(2, [("put", 1, 1), ("put", 2, 2), ("get", 1), ("put", 3, 3), ("get", 2), ("get", 3), ("put", 4, 4), ("get", 1), ("get", 3), ("get", 4)]) == [1, None, 3, None, 3, 4]
assert lfu_run(1, [("put", "a", 1), ("put", "a", 2), ("get", "a"), ("put", "b", 3), ("get", "a"), ("get", "b")]) == [2, None, 3]
assert lfu_run(2, [("put", 1, "x"), ("put", 2, "y"), ("get", 9), ("put", 3, "z"), ("get", 1), ("get", 2)]) == [None, None, "y"]
random.seed(59)
for _ in range(400):
    cap = random.randint(0, 4)
    ops = []
    for _ in range(random.randint(0, 60)):
        k = random.randint(0, 6)
        ops.append(("get", k) if random.random() < 0.5 else ("put", k, random.randint(0, 99)))
    assert lfu_run(cap, ops) == _oracle(cap, ops), (cap, ops)
ops = []
for _ in range(200000):
    k = random.randrange(20000) if random.random() < 0.7 else int(random.paretovariate(1.1)) % 20000
    ops.append(("get", k) if random.random() < 0.5 else ("put", k, random.randint(0, 10**6)))
t0 = time.perf_counter()
r = lfu_run(5000, ops)
assert time.perf_counter() - t0 < 4.0
assert lfu_run(40, ops[:30000]) == _oracle(40, ops[:30000])
''', r'''
from collections import OrderedDict, defaultdict

def lfu_run(capacity, ops):
    vals, cnt = {}, {}
    buckets = defaultdict(OrderedDict)
    minf = 0
    out = []
    def touch(k):
        nonlocal minf
        f = cnt[k]
        del buckets[f][k]
        if not buckets[f]:
            del buckets[f]
            if minf == f:
                minf = f + 1
        cnt[k] = f + 1
        buckets[f + 1][k] = None
    for op in ops:
        if op[0] == "get":
            k = op[1]
            if k in vals:
                touch(k); out.append(vals[k])
            else:
                out.append(None)
        else:
            _, k, v = op
            if capacity == 0:
                continue
            if k in vals:
                vals[k] = v; touch(k)
            else:
                if len(vals) >= capacity:
                    x, _ = buckets[minf].popitem(last=False)
                    if not buckets[minf]:
                        del buckets[minf]
                    del vals[x], cnt[x]
                vals[k] = v; cnt[k] = 1; buckets[1][k] = None; minf = 1
    return out
''')


task("v2_15_distinct_subseq_len", r'''
Write `distinct_subseq_by_len(s: str) -> list[int]` that returns a list c of length len(s) + 1
where c[k] is the number of distinct strings of length k that are subsequences of s (obtained
by deleting any characters and keeping the order), modulo 1_000_000_007. c[0] = 1 (the empty
string), also for s = "". Two subsequences taken from different positions but spelling the
same string count once. s may contain any characters.
Must handle len(s) up to 800 in a few seconds.
''', r'''
import random, time
from itertools import combinations
def _oracle(s):
    c = [0] * (len(s) + 1)
    for k in range(len(s) + 1):
        c[k] = len({"".join(x) for x in combinations(s, k)}) % 1_000_000_007
    return c
assert distinct_subseq_by_len("") == [1]
assert distinct_subseq_by_len("a") == [1, 1]
assert distinct_subseq_by_len("aaa") == [1, 1, 1, 1]
assert distinct_subseq_by_len("abc") == [1, 3, 3, 1]
assert distinct_subseq_by_len("aba") == [1, 2, 3, 1]
assert distinct_subseq_by_len("abab") == [1, 2, 4, 4, 1]
random.seed(61)
for _ in range(400):
    s = "".join(random.choice(random.choice(["ab", "abc", "aab", "xyz1"])) for _ in range(random.randint(0, 12)))
    assert distinct_subseq_by_len(s) == _oracle(s), s
t0 = time.perf_counter()
s = "".join(random.choice("abcdefghij") for _ in range(800))
r = distinct_subseq_by_len(s)
assert len(r) == 801 and r[0] == 1 and r[1] == len(set(s)) and r[800] == 1
assert distinct_subseq_by_len("a" * 800) == [1] * 801
assert time.perf_counter() - t0 < 8.0
t = "".join(random.choice("ab") for _ in range(60))
tot = 1; last = {}; dp = [1]
for ch in t:
    v = 2 * dp[-1] - (dp[last[ch] - 1] if ch in last else 0)
    last[ch] = len(dp); dp.append(v)
assert sum(distinct_subseq_by_len(t)) % 1_000_000_007 == dp[-1] % 1_000_000_007
''', r'''
MOD = 1_000_000_007

def distinct_subseq_by_len(s):
    n = len(s)
    rows = [[1] + [0] * n]
    last = {}
    for i, ch in enumerate(s, 1):
        prev = rows[-1]
        cur = [1] + [(prev[k] + prev[k - 1]) for k in range(1, n + 1)]
        if ch in last:
            base = rows[last[ch] - 1]
            cur = [1] + [(cur[k] - base[k - 1]) % MOD for k in range(1, n + 1)]
        else:
            cur = [x % MOD for x in cur]
        last[ch] = i
        rows.append(cur)
    return rows[-1]
''')


task("v2_16_pal_partition", r'''
Write `pal_partition(s: str) -> list[str]` that splits s into the minimum number of non-empty
pieces such that every piece is a palindrome, and returns the pieces in order (their
concatenation is s). If several minimum partitions exist, return the one whose first piece is
as long as possible; among those, whose second piece is as long as possible; and so on.
pal_partition("") returns [].
Must handle len(s) up to 1200 in a few seconds.
''', r'''
import random, time
def _oracle(s):
    n = len(s)
    best = None
    for mask in range(1 << max(n - 1, 0)):
        parts, st = [], 0
        for i in range(1, n):
            if mask >> (i - 1) & 1:
                parts.append(s[st:i]); st = i
        if n:
            parts.append(s[st:])
        if all(p == p[::-1] for p in parts):
            k = (len(parts), [-len(p) for p in parts])
            if best is None or k < best[0]:
                best = (k, parts)
    return best[1] if n else []
assert pal_partition("") == []
assert pal_partition("a") == ["a"]
assert pal_partition("aab") == ["aa", "b"]
assert pal_partition("abba") == ["abba"]
assert pal_partition("abc") == ["a", "b", "c"]
assert pal_partition("aaba") == ["a", "aba"]
assert pal_partition("abaa") == ["aba", "a"]
assert pal_partition("abab") == ["aba", "b"]
random.seed(67)
for _ in range(500):
    s = "".join(random.choice(random.choice(["ab", "abc", "aab"])) for _ in range(random.randint(0, 12)))
    assert pal_partition(s) == _oracle(s), s
t0 = time.perf_counter()
s = "".join(random.choice("ab") for _ in range(1200))
r = pal_partition(s)
assert "".join(r) == s and all(p == p[::-1] for p in r)
assert pal_partition("a" * 1200) == ["a" * 1200]
r = pal_partition("ab" * 600)
assert r == ["ab" * 599 + "a", "b"]
assert time.perf_counter() - t0 < 8.0
''', r'''
def pal_partition(s):
    n = len(s)
    if n == 0:
        return []
    ends = [[] for _ in range(n)]
    for c in range(2 * n - 1):
        l = c // 2
        r = l + (c & 1)
        while l >= 0 and r < n and s[l] == s[r]:
            ends[l].append(r)
            l -= 1
            r += 1
    INF = n + 1
    best = [INF] * (n + 1)
    best[n] = 0
    for i in range(n - 1, -1, -1):
        b = INF
        for r in ends[i]:
            v = best[r + 1] + 1
            if v < b:
                b = v
        best[i] = b
    out, i = [], 0
    while i < n:
        j = max(r for r in ends[i] if best[r + 1] == best[i] - 1)
        out.append(s[i:j + 1])
        i = j + 1
    return out
''')


task("v2_17_tree_max_path", r'''
Write `tree_max_path(n: int, weights: list[int], edges: list[tuple[int, int]]) -> tuple[int, int]`.
The input is a tree with vertices 0..n-1 (n >= 1, exactly n-1 undirected edges, connected);
weights[v] is the integer weight of vertex v (may be negative or zero). For two vertices u and v
(u == v allowed) the path weight is the sum of the weights of all vertices on the unique path
between them, both ends included. Return (best, count): best is the maximum path weight over
all pairs, and count is the number of unordered pairs {u, v} (including u == v) whose path
weight equals best.
Must handle n up to 100000 in a few seconds, including a path-shaped tree (deep recursion will
overflow the Python stack).
''', r'''
import random, time
def _oracle(n, w, edges):
    adj = [[] for _ in range(n)]
    for a, b in edges:
        adj[a].append(b); adj[b].append(a)
    vals = []
    for u in range(n):
        dist = {u: w[u]}; todo = [u]
        while todo:
            x = todo.pop()
            for y in adj[x]:
                if y not in dist:
                    dist[y] = dist[x] + w[y]; todo.append(y)
        vals += [dist[v] for v in range(u, n)]
    b = max(vals)
    return (b, vals.count(b))
assert tree_max_path(1, [-5], []) == (-5, 1)
assert tree_max_path(2, [3, -1], [(0, 1)]) == (3, 1)
assert tree_max_path(2, [3, 0], [(0, 1)]) == (3, 2)
assert tree_max_path(3, [1, 1, 1], [(0, 1), (1, 2)]) == (3, 1)
assert tree_max_path(4, [0, 0, 0, 0], [(0, 1), (0, 2), (0, 3)]) == (0, 10)
assert tree_max_path(4, [-1, 2, 2, 2], [(0, 1), (0, 2), (0, 3)]) == (3, 3)
assert tree_max_path(3, [-2, -2, -2], [(0, 1), (1, 2)]) == (-2, 3)
random.seed(71)
for _ in range(800):
    n = random.randint(1, 9)
    edges = [(random.randrange(i), i) for i in range(1, n)]
    perm = list(range(n)); random.shuffle(perm)
    edges = [(perm[a], perm[b]) if random.random() < 0.5 else (perm[b], perm[a]) for a, b in edges]
    w = [random.randint(-3, 3) for _ in range(n)]
    assert tree_max_path(n, w, edges) == _oracle(n, w, edges), (n, w, edges)
t0 = time.perf_counter()
n = 100000
assert tree_max_path(n, [1] * n, [(i, i + 1) for i in range(n - 1)]) == (n, 1)
assert tree_max_path(n, [0] * n, [(i, i + 1) for i in range(n - 1)]) == (0, n * (n + 1) // 2)
edges = [(random.randrange(i), i) for i in range(1, n)]
r = tree_max_path(n, [random.randint(-5, 5) for _ in range(n)], edges)
assert isinstance(r, tuple) and r[1] >= 1
assert time.perf_counter() - t0 < 8.0
''', r'''
def tree_max_path(n, weights, edges):
    adj = [[] for _ in range(n)]
    for a, b in edges:
        adj[a].append(b); adj[b].append(a)
    parent = [-1] * n
    order = [0]
    parent[0] = 0
    for x in order:
        for y in adj[x]:
            if parent[y] == -1:
                parent[y] = x
                order.append(y)
    parent[0] = -1
    kids = [[] for _ in range(n)]
    for v in order[1:]:
        kids[parent[v]].append(v)
    dval = [0] * n
    dcnt = [0] * n
    gbest, gcnt = None, 0
    for v in reversed(order):
        w = weights[v]
        groups = {}
        for c in kids[v]:
            g = groups.setdefault(dval[c], [0, 0, 0])
            g[0] += dcnt[c]; g[1] += dcnt[c] * dcnt[c]; g[2] += 1
        cands = [(w, 1)]
        if groups:
            vs = sorted(groups, reverse=True)
            a = vs[0]; A, sq, k = groups[a]
            cands.append((w + a, A))
            if k >= 2:
                cands.append((w + 2 * a, (A * A - sq) // 2))
            elif len(vs) > 1:
                cands.append((w + a + vs[1], A * groups[vs[1]][0]))
            if a > 0:
                dval[v], dcnt[v] = w + a, A
            elif a == 0:
                dval[v], dcnt[v] = w, 1 + A
            else:
                dval[v], dcnt[v] = w, 1
        else:
            dval[v], dcnt[v] = w, 1
        m = max(x for x, _ in cands)
        c = sum(y for x, y in cands if x == m)
        if gbest is None or m > gbest:
            gbest, gcnt = m, c
        elif m == gbest:
            gcnt += c
    return (gbest, gcnt)
''')


task("v2_18_earliest_order", r'''
Write `earliest_order(n: int, edges: list[tuple[int, int]]) -> list[int]`. Vertices are 0..n-1;
an edge (u, v) means u must come before v (duplicates possible). Return an ordering of all n
vertices that respects every edge, chosen as follows: vertex 0 is placed as early as possible;
subject to that, vertex 1 is placed as early as possible; then vertex 2; and so on. In other
words, among all valid orders minimise the list (pos[0], pos[1], ..., pos[n-1])
lexicographically, where pos[v] is v's index in the order. Note this is NOT the same as the
lexicographically smallest order. If the constraints contain a cycle (including a self-loop),
return []. n = 0 returns [].
Must handle n up to 200000 and 300000 edges in a few seconds.
''', r'''
import random, time
from itertools import permutations
def _oracle(n, edges):
    best = None
    for p in permutations(range(n)):
        pos = [0] * n
        for i, v in enumerate(p):
            pos[v] = i
        if all(pos[u] < pos[v] for u, v in edges):
            if best is None or pos < best[0]:
                best = (pos, list(p))
    return best[1] if best else []
assert earliest_order(0, []) == []
assert earliest_order(1, [(0, 0)]) == []
assert earliest_order(3, [(2, 0)]) == [2, 0, 1]
assert earliest_order(3, [(1, 2), (2, 1)]) == []
assert earliest_order(4, [(3, 0), (2, 1)]) == [3, 0, 2, 1]
assert earliest_order(5, [(4, 1), (3, 0), (2, 0)]) == [2, 3, 0, 4, 1]
random.seed(73)
for _ in range(500):
    n = random.randint(1, 7)
    m = random.randint(0, n + 2)
    if random.random() < 0.85:
        perm = list(range(n)); random.shuffle(perm)
        edges = []
        for _ in range(m):
            a, b = sorted(random.sample(range(n), 2)) if n > 1 else (0, 0)
            if a != b:
                edges.append((perm[a], perm[b]))
    else:
        edges = [(random.randrange(n), random.randrange(n)) for _ in range(m)]
    assert earliest_order(n, edges) == _oracle(n, edges), (n, edges)
t0 = time.perf_counter()
n = 200000
perm = list(range(n)); random.shuffle(perm)
edges = []
for _ in range(300000):
    a, b = random.randrange(n), random.randrange(n)
    if a != b:
        a, b = min(a, b), max(a, b)
        edges.append((perm[a], perm[b]))
r = earliest_order(n, edges)
pos = [0] * n
for i, v in enumerate(r):
    pos[v] = i
assert len(r) == n and all(pos[u] < pos[v] for u, v in edges)
assert earliest_order(n, edges + [(perm[5], perm[3]), (perm[3], perm[5])]) == []
assert time.perf_counter() - t0 < 8.0
''', r'''
import heapq

def earliest_order(n, edges):
    radj = [[] for _ in range(n)]
    outdeg = [0] * n
    for u, v in edges:
        radj[v].append(u)
        outdeg[u] += 1
    h = [-v for v in range(n) if outdeg[v] == 0]
    heapq.heapify(h)
    rev = []
    while h:
        v = -heapq.heappop(h)
        rev.append(v)
        for u in radj[v]:
            outdeg[u] -= 1
            if outdeg[u] == 0:
                heapq.heappush(h, -u)
    if len(rev) < n:
        return []
    return rev[::-1]
''')


task("v2_19_rollback_dsu", r'''
Write `dsu_ops(n: int, ops: list[tuple]) -> list` for a union-find structure over elements
0..n-1 (initially every element is alone) that supports undo. Process ops in order and return
the answers of the queries in order:
- ("union", a, b): merge the sets of a and b (no-op if already the same set).
- ("same", a, b): append True if a and b are in the same set, else False.
- ("count",): append the current number of sets.
- ("save",): push a checkpoint.
- ("undo",): pop the most recent checkpoint and restore the structure to exactly the state it
  had when that checkpoint was pushed. If there is no checkpoint, restore the initial state
  (all singletons); later undos with no checkpoint do the same.
Checkpoints nest. Must handle n = 100000 and 200000 operations (including tens of thousands
of save/undo pairs) in a few seconds.
''', r'''
import random, time
def _oracle(n, ops):
    lab = list(range(n)); stack = []; out = []
    for op in ops:
        k = op[0]
        if k == "union":
            a, b = lab[op[1]], lab[op[2]]
            if a != b:
                lab = [a if x == b else x for x in lab]
        elif k == "same":
            out.append(lab[op[1]] == lab[op[2]])
        elif k == "count":
            out.append(len(set(lab)))
        elif k == "save":
            stack.append(lab[:])
        else:
            lab = stack.pop() if stack else list(range(n))
    return out
assert dsu_ops(3, [("count",), ("union", 0, 1), ("same", 0, 1), ("same", 1, 2), ("count",)]) == [3, True, False, 2]
assert dsu_ops(3, [("union", 0, 1), ("save",), ("union", 1, 2), ("count",), ("undo",), ("count",), ("same", 0, 2), ("same", 0, 1)]) == [1, 2, False, True]
assert dsu_ops(2, [("union", 0, 1), ("undo",), ("count",), ("union", 0, 1), ("undo",), ("undo",), ("same", 0, 1)]) == [2, False]
assert dsu_ops(4, [("save",), ("union", 0, 1), ("save",), ("union", 2, 3), ("save",), ("union", 0, 3), ("undo",), ("count",), ("undo",), ("count",), ("undo",), ("count",)]) == [2, 3, 4]
assert dsu_ops(1, [("union", 0, 0), ("count",), ("same", 0, 0)]) == [1, True]
random.seed(79)
for _ in range(400):
    n = random.randint(1, 8)
    ops = []
    for _ in range(random.randint(0, 40)):
        r = random.random()
        if r < 0.35:
            ops.append(("union", random.randrange(n), random.randrange(n)))
        elif r < 0.55:
            ops.append(("same", random.randrange(n), random.randrange(n)))
        elif r < 0.65:
            ops.append(("count",))
        elif r < 0.85:
            ops.append(("save",))
        else:
            ops.append(("undo",))
    assert dsu_ops(n, ops) == _oracle(n, ops), (n, ops)
t0 = time.perf_counter()
n = 100000
ops = [("union", random.randrange(n), random.randrange(n)) for _ in range(60000)]
for _ in range(35000):
    ops += [("save",), ("union", random.randrange(n), random.randrange(n)), ("same", random.randrange(n), random.randrange(n)), ("undo",)]
ops.append(("count",))
r = dsu_ops(n, ops)
assert len(r) == 35001
ops2 = [("union", i, i + 1) for i in range(n - 1)] + [("count",), ("undo",), ("count",)]
assert dsu_ops(n, ops2) == [1, n]
assert time.perf_counter() - t0 < 8.0
''', r'''
def dsu_ops(n, ops):
    parent = list(range(n))
    size = [1] * n
    hist = []
    saves = []
    comps = n
    out = []
    def find(x):
        while parent[x] != x:
            x = parent[x]
        return x
    for op in ops:
        k = op[0]
        if k == "union":
            a, b = find(op[1]), find(op[2])
            if a != b:
                if size[a] < size[b]:
                    a, b = b, a
                parent[b] = a
                size[a] += size[b]
                hist.append((a, b))
                comps -= 1
        elif k == "same":
            out.append(find(op[1]) == find(op[2]))
        elif k == "count":
            out.append(comps)
        elif k == "save":
            saves.append(len(hist))
        else:
            target = saves.pop() if saves else 0
            while len(hist) > target:
                a, b = hist.pop()
                parent[b] = b
                size[a] -= size[b]
                comps += 1
    return out
''')


task("v2_20_edit_script", r'''
Write `edit_script(a: str, b: str) -> list[str]` that returns an edit script turning a into b
with the minimum number of edits. The script is read left to right over both strings; each
operation is one string:
- "=x": keep character x (the next characters of a and b are both x; costs 0)
- "~xy": substitute the next character x of a with y, only when x != y (costs 1)
- "-x": delete the next character x of a (costs 1)
- "+y": insert the next character y of b (costs 1)
Applying the script must consume all of a and produce exactly b, and the total cost must be the
minimum (the Levenshtein distance). Among all minimum-cost scripts return the canonical one:
at each step, take the first operation type in the priority order "=", "~", "-", "+" that can
still be completed into a minimum-cost script.
Must handle strings of length 700 each in a few seconds.
''', r'''
import random, time
def _oracle(a, b):
    rank = {"=": 0, "~": 1, "-": 2, "+": 3}
    allv = []
    def rec(i, j, ops, cost):
        if i == len(a) and j == len(b):
            allv.append((cost, [rank[o[0]] for o in ops], ops[:])); return
        if i < len(a) and j < len(b):
            if a[i] == b[j]:
                ops.append("=" + a[i]); rec(i + 1, j + 1, ops, cost); ops.pop()
            else:
                ops.append("~" + a[i] + b[j]); rec(i + 1, j + 1, ops, cost + 1); ops.pop()
        if i < len(a):
            ops.append("-" + a[i]); rec(i + 1, j, ops, cost + 1); ops.pop()
        if j < len(b):
            ops.append("+" + b[j]); rec(i, j + 1, ops, cost + 1); ops.pop()
    rec(0, 0, [], 0)
    return min(allv)[2]
def _lev(a, b):
    prev = list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        cur = [i] + [0] * len(b)
        for j in range(1, len(b) + 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] != b[j - 1]))
        prev = cur
    return prev[-1]
def _apply(a, ops):
    i, out = 0, []
    for o in ops:
        if o[0] == "=":
            assert a[i] == o[1]; out.append(o[1]); i += 1
        elif o[0] == "~":
            assert a[i] == o[1] and o[1] != o[2]; out.append(o[2]); i += 1
        elif o[0] == "-":
            assert a[i] == o[1]; i += 1
        else:
            out.append(o[1])
    assert i == len(a)
    return "".join(out)
assert edit_script("", "") == []
assert edit_script("", "ab") == ["+a", "+b"]
assert edit_script("ab", "") == ["-a", "-b"]
assert edit_script("abc", "abc") == ["=a", "=b", "=c"]
assert edit_script("abc", "axc") == ["=a", "~bx", "=c"]
assert edit_script("ab", "ba") == ["~ab", "~ba"]
assert edit_script("abc", "bc") == ["-a", "=b", "=c"]
assert edit_script("aa", "a") == ["=a", "-a"]
assert edit_script("kitten", "sitting") == ["~ks", "=i", "=t", "=t", "~ei", "=n", "+g"]
random.seed(83)
for _ in range(500):
    a = "".join(random.choice("abc") for _ in range(random.randint(0, 5)))
    b = "".join(random.choice("abc") for _ in range(random.randint(0, 5)))
    assert edit_script(a, b) == _oracle(a, b), (a, b)
t0 = time.perf_counter()
a = "".join(random.choice("acgt") for _ in range(700))
b = "".join(random.choice("acgt") for _ in range(700))
r = edit_script(a, b)
assert _apply(a, r) == b
assert time.perf_counter() - t0 < 6.0
assert sum(o[0] != "=" for o in r) == _lev(a, b)
''', r'''
def edit_script(a, b):
    n, m = len(a), len(b)
    D = [[0] * (m + 1) for _ in range(n + 1)]
    for j in range(m + 1):
        D[n][j] = m - j
    for i in range(n - 1, -1, -1):
        row, nrow = D[i], D[i + 1]
        row[m] = n - i
        ai = a[i]
        for j in range(m - 1, -1, -1):
            d = nrow[j + 1] + (ai != b[j])
            x = nrow[j] + 1
            if x < d:
                d = x
            x = row[j + 1] + 1
            if x < d:
                d = x
            row[j] = d
    out, i, j = [], 0, 0
    while i < n or j < m:
        cur = D[i][j]
        if i < n and j < m and a[i] == b[j] and D[i + 1][j + 1] == cur:
            out.append("=" + a[i]); i += 1; j += 1
        elif i < n and j < m and a[i] != b[j] and D[i + 1][j + 1] + 1 == cur:
            out.append("~" + a[i] + b[j]); i += 1; j += 1
        elif i < n and D[i + 1][j] + 1 == cur:
            out.append("-" + a[i]); i += 1
        else:
            out.append("+" + b[j]); j += 1
    return out
''')


task("v2_21_crt_general", r'''
Write `crt_solve(congruences: list[tuple[int, int]]) -> tuple[int, int] | None` that solves
the system x = a_i (mod m_i) for every pair (a_i, m_i) in the list. The moduli need NOT be
pairwise coprime. Rules: every m_i must be an int >= 1, otherwise raise ValueError (check all
pairs before solving); a_i may be any int (negative, or larger than m_i). If the system has a
solution, return (x, L) where L is the least common multiple of all moduli and x is the unique
solution with 0 <= x < L (the full solution set is x + L*k). If the system has no solution,
return None. The empty list returns (0, 1). Must be fast: 50 congruences with moduli up to
10**30 must take well under 0.05 s.
''', r'''
import random
import math, time
from functools import reduce
assert crt_solve([]) == (0, 1)
assert crt_solve([(2, 3), (3, 5), (2, 7)]) == (23, 105)
assert crt_solve([(1, 4), (3, 6)]) == (9, 12)
assert crt_solve([(1, 4), (2, 6)]) is None
assert crt_solve([(-1, 5)]) == (4, 5)
assert crt_solve([(17, 5)]) == (2, 5)
assert crt_solve([(0, 1), (5, 1)]) == (0, 1)
assert crt_solve([(3, 6), (3, 6), (9, 12)]) == (9, 12)
assert crt_solve([(5, 6), (1, 10), (11, 15)]) == (11, 30)
for bad in ([(1, 0)], [(1, -3)], [(2, 3), (1, 0)], [(1, 0), (1, 2), (0, 2)]):
    try:
        crt_solve(bad)
        assert False, ("expected ValueError", bad)
    except ValueError:
        pass
random.seed(2101)
lcm = lambda ms: reduce(lambda a, b: a * b // math.gcd(a, b), ms, 1)
for _ in range(400):
    cs = [(random.randint(-30, 30), random.randint(1, 10)) for _ in range(random.randint(1, 4))]
    L = lcm([m for _, m in cs])
    sols = [x for x in range(L) if all((x - a) % m == 0 for a, m in cs)]
    exp = (sols[0], L) if sols else None
    assert crt_solve(cs) == exp, (cs, exp)
t0 = time.perf_counter()
for _ in range(200):
    ms = [random.randint(1, 10**30) for _ in range(random.randint(1, 50))]
    x = random.randint(0, 10**200)
    cs = [(x % m + m * random.randint(-5, 5), m) for m in ms]
    random.shuffle(cs)
    L = lcm(ms)
    assert crt_solve(cs) == (x % L, L)
    m = max(ms)
    if m > 1:
        assert crt_solve(cs + [((x + 1) % m, m * random.randint(1, 3))]) is None
assert time.perf_counter() - t0 < 5.0
''', r'''
from math import gcd

def crt_solve(congruences):
    for a, m in congruences:
        if m < 1:
            raise ValueError("modulus must be >= 1")
    x, L = 0, 1
    for a, m in congruences:
        g = gcd(L, m)
        if (a - x) % g:
            return None
        mg = m // g
        t = ((a - x) // g * pow(L // g, -1, mg)) % mg if mg > 1 else 0
        x += L * t
        L *= mg
        x %= L
    return (x, L)
''')


task("v2_22_perfect_power", r'''
Write `perfect_power(n: int) -> tuple[int, int]` that writes n as b**e with the LARGEST
possible exponent e >= 1 and returns (b, e). Rules: n is an int with abs(n) >= 2; for
abs(n) < 2 raise ValueError. For n > 0, b >= 2. For n < 0 only odd exponents are possible,
so b is negative and e is odd: perfect_power(-64) == (-4, 3) (not (-2, 6), since
(-2)**6 == 64), perfect_power(-4) == (-4, 1), perfect_power(-8) == (-2, 3). A number that is
no perfect power returns (n, 1). n can have up to 600 decimal digits, so floating point
cannot be used for roots (it overflows or rounds wrong); use exact integer arithmetic.
300 calls on 500-digit inputs must take a few seconds at most.
''', r'''
import random
import time
assert perfect_power(2) == (2, 1)
assert perfect_power(4) == (2, 2)
assert perfect_power(64) == (2, 6)
assert perfect_power(-64) == (-4, 3)
assert perfect_power(-8) == (-2, 3)
assert perfect_power(-4) == (-4, 1)
assert perfect_power(-2) == (-2, 1)
assert perfect_power(72) == (72, 1)
assert perfect_power(3**40) == (3, 40)
assert perfect_power(-(3**40)) == (-(3**8), 5)
assert perfect_power(10**100) == (10, 100)
assert perfect_power(10**100 + 1) == (10**100 + 1, 1)
assert perfect_power(2**127 - 1) == (2**127 - 1, 1)
assert perfect_power((2**89 - 1) ** 7) == (2**89 - 1, 7)
assert perfect_power(-(6**12)) == (-(6**4), 3)
for bad in (-1, 0, 1):
    try:
        perfect_power(bad)
        assert False, ("expected ValueError", bad)
    except ValueError:
        pass
def small(v):
    for e in range(40, 0, -1):
        r = int(round(v ** (1.0 / e)))
        for c in (r - 1, r, r + 1):
            if c >= 2 and c ** e == v:
                return c, e
    return v, 1
def expect(sign, B, E):
    if sign > 0:
        return (B, E)
    e = E
    while e % 2 == 0:
        e //= 2
    return (-(B ** (E // e)), e)
random.seed(2202)
for _ in range(1500):
    v = random.choice([random.randint(2, 10**6), random.randint(2, 40) ** random.randint(2, 12)])
    if v > 10**12:
        continue
    s = random.choice([1, -1])
    B, E = small(v)
    assert perfect_power(s * v) == expect(s, B, E), s * v
t0 = time.perf_counter()
for _ in range(300):
    b0, e0, s = random.randint(2, 10**6), random.randint(1, 90), random.choice([1, -1])
    B0, E0 = small(b0)
    n = b0 ** e0
    assert perfect_power(s * n) == expect(s, B0, E0 * e0), (s, b0, e0)
    if e0 >= 2:
        d = random.choice([1, -1])
        if n + d not in (8, 9):
            assert perfect_power(s * (n + d)) == (s * (n + d), 1), (s, b0, e0, d)
assert time.perf_counter() - t0 < 8.0
''', r'''
def _iroot(n, k):
    if n < 2:
        return n
    x = 1 << ((n.bit_length() + k - 1) // k)
    while True:
        y = ((k - 1) * x + n // x ** (k - 1)) // k
        if y >= x:
            return x
        x = y

def _primes(limit):
    s = bytearray([1]) * (limit + 1)
    s[0:2] = b"\x00\x00"
    for i in range(2, int(limit ** 0.5) + 1):
        if s[i]:
            s[i * i::i] = bytearray(len(s[i * i::i]))
    return [i for i in range(limit + 1) if s[i]]

def perfect_power(n):
    if abs(n) < 2:
        raise ValueError("abs(n) must be >= 2")
    m, E = abs(n), 1
    changed = True
    while changed:
        changed = False
        for p in _primes(m.bit_length()):
            r = _iroot(m, p)
            if r >= 2 and r ** p == m:
                m, E, changed = r, E * p, True
                break
    if n > 0:
        return (m, E)
    e = E
    while e % 2 == 0:
        e //= 2
    return (-(m ** (E // e)), e)
''')


task("v2_23_point_in_polygon", r'''
Write `point_in_polygon(poly: list[tuple[int, int]], pt: tuple[int, int]) -> str` that
returns "inside", "outside" or "boundary". poly is a simple polygon (edges do not cross or
touch except consecutive edges at their shared vertex) given by its vertices in order,
clockwise or counter-clockwise, with an implicit closing edge from the last vertex to the
first. It has at least 3 vertices, nonzero area, no repeated vertices, and may contain
collinear consecutive vertices and horizontal or vertical edges. All coordinates are ints of
any size (up to 10**15 and beyond), so use exact integer arithmetic, no floats. "boundary"
means pt lies on an edge, including its endpoints. Take care with points whose horizontal
line passes exactly through a vertex or along a horizontal edge, and with reflex (concave)
vertices.
''', r'''
import random
import math
from fractions import Fraction as F
sq = [(0, 0), (4, 0), (4, 4), (0, 4)]
for poly in (sq, sq[::-1]):
    assert point_in_polygon(poly, (2, 2)) == "inside"
    assert point_in_polygon(poly, (4, 2)) == "boundary"
    assert point_in_polygon(poly, (0, 0)) == "boundary"
    assert point_in_polygon(poly, (2, 4)) == "boundary"
    assert point_in_polygon(poly, (5, 2)) == "outside"
    assert point_in_polygon(poly, (-1, 4)) == "outside"
    assert point_in_polygon(poly, (-1, 0)) == "outside"
    assert point_in_polygon(poly, (2, 5)) == "outside"
cc = [(0, 0), (6, 0), (6, 6), (3, 2), (0, 6)]
for poly in (cc, cc[::-1], cc[2:] + cc[:2]):
    assert point_in_polygon(poly, (3, 4)) == "outside"
    assert point_in_polygon(poly, (3, 2)) == "boundary"
    assert point_in_polygon(poly, (1, 4)) == "inside"
    assert point_in_polygon(poly, (5, 4)) == "inside"
    assert point_in_polygon(poly, (1, 2)) == "inside"
    assert point_in_polygon(poly, (-1, 2)) == "outside"
    assert point_in_polygon(poly, (7, 2)) == "outside"
    assert point_in_polygon(poly, (7, 6)) == "outside"
    assert point_in_polygon(poly, (3, 6)) == "outside"
    assert point_in_polygon(poly, (0, 3)) == "boundary"
col = [(0, 0), (2, 0), (4, 0), (4, 2), (4, 4), (2, 2), (0, 4)]
assert point_in_polygon(col, (1, 0)) == "boundary"
assert point_in_polygon(col, (3, 1)) == "inside"
assert point_in_polygon(col, (2, 3)) == "outside"
assert point_in_polygon(col, (-2, 2)) == "outside"
assert point_in_polygon(col, (1, 2)) == "inside"
def onseg(p, a, b):
    return ((b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0]) == 0
            and min(a[0], b[0]) <= p[0] <= max(a[0], b[0]) and min(a[1], b[1]) <= p[1] <= max(a[1], b[1]))
def oracle(poly, pt):
    # ray from pt in direction (1000, 1): with coordinates in [-22, 22] it meets no lattice point but pt
    px, py = pt
    n, cnt = len(poly), 0
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        if onseg(pt, a, b):
            return "boundary"
        dx, dy = b[0] - a[0], b[1] - a[1]
        det = dx - 1000 * dy
        if det == 0:
            continue
        t = F(-(a[0] - px) * dy + dx * (a[1] - py), det)
        s = F(1000 * (a[1] - py) - (a[0] - px), det)
        if t > 0 and 0 <= s <= 1:
            cnt += 1
    return "inside" if cnt % 2 else "outside"
def gen_poly():
    while True:
        cx, cy = random.uniform(-6, 6), random.uniform(-6, 6)
        pts = list({(random.randint(-20, 20), random.randint(-20, 20)) for _ in range(random.randint(3, 12))})
        if len(pts) < 3:
            continue
        ang = sorted((math.atan2(y - cy, x - cx), x, y) for x, y in pts)
        a = [t[0] for t in ang]
        gaps = [a[i + 1] - a[i] for i in range(len(a) - 1)] + [a[0] + 2 * math.pi - a[-1]]
        if min(gaps) < 1e-9 or max(gaps) > math.pi - 1e-9:
            continue
        poly = [(x, y) for _, x, y in ang]
        if random.random() < 0.5:
            poly.reverse()
        k = random.randrange(len(poly))
        return poly[k:] + poly[:k]
random.seed(2303)
for _ in range(250):
    poly = gen_poly()
    qs = [(random.randint(-22, 22), random.randint(-22, 22)) for _ in range(30)] + list(poly)
    qs += [((poly[i][0] + poly[i - 1][0]) // 2, (poly[i][1] + poly[i - 1][1]) // 2) for i in range(len(poly))]
    qs += [(random.randint(-22, 22), y) for _, y in poly]
    for q in qs:
        exp = oracle(poly, q)
        assert point_in_polygon(poly, q) == exp, (poly, q, exp)
    S, ox, oy = 10**15 + 7, -3 * 10**17, 5 * 10**16
    big = [(x * S + ox, y * S + oy) for x, y in poly]
    for q in qs[:10]:
        assert point_in_polygon(big, (q[0] * S + ox, q[1] * S + oy)) == oracle(poly, q)
''', r'''
def point_in_polygon(poly, pt):
    px, py = pt
    n = len(poly)
    inside = False
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if ((x2 - x1) * (py - y1) - (y2 - y1) * (px - x1) == 0
                and min(x1, x2) <= px <= max(x1, x2) and min(y1, y2) <= py <= max(y1, y2)):
            return "boundary"
        if (y1 > py) != (y2 > py):
            lhs = (px - x1) * (y2 - y1)
            rhs = (py - y1) * (x2 - x1)
            if (lhs < rhs) if y2 > y1 else (lhs > rhs):
                inside = not inside
    return "inside" if inside else "outside"
''')


task("v2_24_convex_hull", r'''
Write `convex_hull(points: list[tuple[int, int]]) -> list[tuple[int, int]]` returning the
vertices of the convex hull of the points as a list of (x, y) tuples. Rules: the list is in
counter-clockwise order and starts at the point with the smallest y, ties broken by smallest
x. Only true corners are returned: points lying on a hull edge (collinear with two hull
vertices) are excluded. Input may contain duplicates. Special cases: empty input returns [];
if all points are identical return [that point]; if all points are collinear return the two
extreme points [start, other end], where start follows the same smallest-y-then-smallest-x
rule. Coordinates are ints up to 10**9 in absolute value; use exact integer arithmetic.
Must handle 40000 points in well under 2 seconds.
''', r'''
import random
import time
assert convex_hull([]) == []
assert convex_hull([(1, 1)]) == [(1, 1)]
assert convex_hull([(1, 1), (1, 1)]) == [(1, 1)]
assert convex_hull([(0, 0), (2, 2), (1, 1)]) == [(0, 0), (2, 2)]
assert convex_hull([(2, 2), (0, 0)]) == [(0, 0), (2, 2)]
assert convex_hull([(3, 0), (1, 0), (2, 0)]) == [(1, 0), (3, 0)]
assert convex_hull([(0, 3), (0, -1), (0, 1)]) == [(0, -1), (0, 3)]
assert convex_hull([(2, 0), (0, 2), (1, 1)]) == [(2, 0), (0, 2)]
assert convex_hull([(0, 0), (1, 0), (2, 0), (2, 2), (0, 2), (1, 1), (2, 1), (0, 0)]) == [(0, 0), (2, 0), (2, 2), (0, 2)]
assert convex_hull([(0, 1), (2, 0), (4, 0), (3, 3)]) == [(2, 0), (4, 0), (3, 3), (0, 1)]
assert convex_hull([(5, 5), (-5, 5), (0, -5), (0, 0), (0, 5)]) == [(0, -5), (5, 5), (-5, 5)]
def cross(o, a, b):
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
def jarvis(pts):
    P = sorted(set(pts))
    if len(P) <= 1:
        return P
    start = min(P, key=lambda p: (p[1], p[0]))
    hull, cur = [start], start
    d2 = lambda a, b: (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2
    while True:
        cand = None
        for q in P:
            if q == cur:
                continue
            if cand is None:
                cand = q
                continue
            c = cross(cur, cand, q)
            if c < 0 or (c == 0 and d2(cur, q) > d2(cur, cand)):
                cand = q
        if cand == start:
            return hull
        hull.append(cand)
        cur = cand
random.seed(2404)
for _ in range(1500):
    r = random.choice([1, 2, 3, 5, 8])
    n = random.randint(1, 30)
    if random.random() < 0.2:
        ax, ay, bx, by = [random.randint(-3, 3) for _ in range(4)]
        pts = [(ax + t * bx, ay + t * by) for t in (random.randint(-4, 4) for _ in range(n))]
    else:
        pts = [(random.randint(-r, r), random.randint(-r, r)) for _ in range(n)]
    exp = jarvis(pts)
    got = convex_hull(list(pts))
    assert [tuple(p) for p in got] == exp, (pts, exp, got)
pts = [(random.randint(-10**9, 10**9), random.randint(-10**9, 10**9)) for _ in range(40000)]
pts += [(10**9, y) for y in range(-5, 6)] + [(x, -10**9 - 1) for x in range(-3, 4)]
t0 = time.perf_counter()
got = convex_hull(pts)
assert time.perf_counter() - t0 < 4.0
assert [tuple(p) for p in got] == jarvis(pts)
''', r'''
def convex_hull(points):
    P = sorted(set(map(tuple, points)))
    if len(P) <= 1:
        return P
    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower, upper = [], []
    for p in P:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(P):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    hull = lower[:-1] + upper[:-1]
    i = min(range(len(hull)), key=lambda k: (hull[k][1], hull[k][0]))
    return hull[i:] + hull[:i]
''')


task("v2_25_segment_intersect", r'''
Write `segment_intersection(s1, s2)` for two closed line segments, each given as
((x1, y1), (x2, y2)) with int coordinates (any size). A segment may be degenerate (both
endpoints equal, i.e. a single point). Return:
- None if the segments have no common point;
- (x, y) if they have exactly one common point, with x and y as fractions.Fraction
  (exact; intersections are generally not lattice points);
- ((x1, y1), (x2, y2)) if they share a segment of positive length (collinear overlap),
  giving its two endpoints as Fraction pairs with the lexicographically smaller point
  (compare x, then y) first.
Collinear segments that only touch at an endpoint share exactly one point. The direction
in which a segment is given (which endpoint comes first) must not matter. Use exact
arithmetic only, no floats.
''', r'''
import random
from fractions import Fraction as F
si = segment_intersection
assert si(((0, 0), (4, 4)), ((0, 4), (4, 0))) == (2, 2)
assert si(((0, 0), (1, 1)), ((1, 0), (2, 1))) is None
assert si(((0, 0), (4, 0)), ((2, 0), (6, 0))) == ((2, 0), (4, 0))
assert si(((0, 0), (2, 0)), ((2, 0), (5, 0))) == (2, 0)
assert si(((0, 0), (2, 0)), ((3, 0), (5, 0))) is None
assert si(((0, 0), (0, 0)), ((0, 0), (0, 0))) == (0, 0)
assert si(((0, 0), (0, 0)), ((1, 0), (1, 0))) is None
assert si(((1, 1), (1, 1)), ((0, 0), (2, 2))) == (1, 1)
assert si(((1, 2), (1, 2)), ((0, 0), (2, 2))) is None
assert si(((0, 0), (3, 1)), ((0, 1), (3, 0))) == (F(3, 2), F(1, 2))
assert si(((4, 4), (0, 0)), ((6, 6), (2, 2))) == ((2, 2), (4, 4))
assert si(((0, 0), (2, 0)), ((1, 0), (1, 3))) == (1, 0)
assert si(((0, 0), (2, 0)), ((1, 1), (1, 3))) is None
assert si(((0, 5), (0, 1)), ((0, 2), (0, 9))) == ((0, 2), (0, 5))
assert si(((3, 0), (0, 3)), ((2, 1), (1, 2))) == ((1, 2), (2, 1))
assert si(((0, 0), (5, 1)), ((5, 0), (0, 1))) == (F(5, 2), F(1, 2))
r = si(((0, 0), (3, 1)), ((0, 1), (3, 0)))
assert isinstance(r[0], F) and r[0] == F(3, 2)
def onseg(p, a, b):
    return ((b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0]) == 0
            and min(a[0], b[0]) <= p[0] <= max(a[0], b[0]) and min(a[1], b[1]) <= p[1] <= max(a[1], b[1]))
def oracle(s1, s2):
    (a, b), (c, d) = s1, s2
    cands = [a, b, c, d]
    den = (b[0] - a[0]) * (d[1] - c[1]) - (b[1] - a[1]) * (d[0] - c[0])
    if den:
        t = F((c[0] - a[0]) * (d[1] - c[1]) - (c[1] - a[1]) * (d[0] - c[0]), den)
        cands.append((a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])))
    common = sorted({(F(x), F(y)) for x, y in cands if onseg((x, y), a, b) and onseg((x, y), c, d)})
    if not common:
        return None
    return common[0] if len(common) == 1 else (common[0], common[-1])
random.seed(2505)
P = lambda: (random.randint(0, 6), random.randint(0, 6))
for _ in range(6000):
    if random.random() < 0.35:
        ox, oy, dx, dy = random.randint(-2, 2), random.randint(-2, 2), random.randint(-2, 2), random.randint(-2, 2)
        a, b, c, d = [(ox + t * dx, oy + t * dy) for t in (random.randint(-3, 3) for _ in range(4))]
    else:
        a, b, c, d = P(), P(), P(), P()
        if random.random() < 0.1:
            b = a
        if random.random() < 0.1:
            d = c
    exp = oracle((a, b), (c, d))
    got = si((a, b), (c, d))
    assert got == exp, ((a, b), (c, d), exp, got)
    assert si((d, c), (b, a)) == exp
    S, o = 10**18 + 9, -7 * 10**20
    sc = lambda p: (p[0] * S + o, p[1] * S - o)
    if exp is not None and random.random() < 0.2:
        g = si((sc(a), sc(b)), (sc(c), sc(d)))
        if isinstance(exp[0], tuple):
            assert g == (sc(exp[0]), sc(exp[1]))
        else:
            assert g == sc(exp)
''', r'''
from fractions import Fraction as F

def segment_intersection(s1, s2):
    (a, b), (c, d) = (tuple(s1[0]), tuple(s1[1])), (tuple(s2[0]), tuple(s2[1]))
    pt = lambda p: (F(p[0]), F(p[1]))
    def cr(o, p, q):
        return (p[0] - o[0]) * (q[1] - o[1]) - (p[1] - o[1]) * (q[0] - o[0])
    def on(p, u, v):
        return (cr(u, v, p) == 0 and min(u[0], v[0]) <= p[0] <= max(u[0], v[0])
                and min(u[1], v[1]) <= p[1] <= max(u[1], v[1]))
    if a == b and c == d:
        return pt(a) if a == c else None
    if a == b:
        return pt(a) if on(a, c, d) else None
    if c == d:
        return pt(c) if on(c, a, b) else None
    d1, d2, d3, d4 = cr(c, d, a), cr(c, d, b), cr(a, b, c), cr(a, b, d)
    if d1 == 0 and d2 == 0:
        p1, p2 = sorted([a, b])
        q1, q2 = sorted([c, d])
        lo, hi = max(p1, q1), min(p2, q2)
        if lo > hi:
            return None
        return pt(lo) if lo == hi else (pt(lo), pt(hi))
    if (d1 > 0 and d2 > 0) or (d1 < 0 and d2 < 0) or (d3 > 0 and d4 > 0) or (d3 < 0 and d4 < 0):
        return None
    t = F(d1, d1 - d2)
    return (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))
''')


task("v2_26_iso_week", r'''
Write two functions for ISO 8601 week dates in the proleptic Gregorian calendar, years
1 through 9999:
- `to_iso_week(year: int, month: int, day: int) -> tuple[int, int, int]` returns
  (iso_year, iso_week, iso_weekday).
- `from_iso_week(iso_year: int, week: int, weekday: int) -> tuple[int, int, int]` returns
  (year, month, day).
ISO rules: weeks start on Monday (weekday 1) and end on Sunday (7); week 1 of an ISO year is
the week containing January 4; an ISO year has 52 or 53 weeks; dates in late December or
early January can belong to the neighbouring ISO year. 0001-01-01 is a Monday.
Raise ValueError for: an invalid calendar date (month outside 1..12, day outside the month,
Feb 29 in a non-leap year; leap years are divisible by 4, except centuries not divisible by
400); a year outside 1..9999 (for to_iso_week the calendar year, for from_iso_week the ISO
year); a weekday outside 1..7; a week outside 1..(number of weeks in that ISO year); and any
from_iso_week result whose calendar date falls outside 0001-01-01 .. 9999-12-31. Do not use
the datetime, calendar or time modules.
''', r'''
import random
_banned(mods=("datetime", "_datetime", "_pydatetime", "calendar", "time", "_strptime", "zoneinfo", "email"))
from datetime import date
def call(f, *a):
    try:
        return tuple(f(*a))
    except ValueError:
        return "err"
def exp_to(y, m, d):
    try:
        return tuple(date(y, m, d).isocalendar())
    except (ValueError, OverflowError):
        return "err"
def exp_from(y, w, d):
    try:
        r = date.fromisocalendar(y, w, d)
        return (r.year, r.month, r.day)
    except (ValueError, OverflowError):
        return "err"
assert to_iso_week(2008, 12, 29) == (2009, 1, 1)
assert to_iso_week(2010, 1, 3) == (2009, 53, 7)
assert to_iso_week(1, 1, 1) == (1, 1, 1)
assert from_iso_week(2009, 53, 7) == (2010, 1, 3)
assert from_iso_week(2009, 1, 1) == (2008, 12, 29)
for args in [(1900, 2, 29), (2023, 2, 29), (2024, 13, 1), (2024, 0, 1), (2024, 4, 31), (2024, 1, 0), (0, 1, 1), (10000, 1, 1)]:
    assert call(to_iso_week, *args) == "err", args
assert call(to_iso_week, 2000, 2, 29) == exp_to(2000, 2, 29)
for args in [(2024, 0, 1), (2024, 1, 0), (2024, 1, 8), (2010, 53, 1), (0, 10, 1), (10000, 1, 1), (2024, -1, 3)]:
    assert call(from_iso_week, *args) == "err", args
for args in [(9999, 52, 5), (9999, 52, 6), (9999, 52, 7), (1, 1, 1), (2020, 53, 4), (2015, 53, 7), (2026, 53, 1)]:
    assert call(from_iso_week, *args) == exp_from(*args), args
for args in [(9999, 12, 31), (9999, 12, 27), (1, 1, 7), (2000, 1, 1)]:
    assert call(to_iso_week, *args) == exp_to(*args), args
random.seed(2606)
mx = date.max.toordinal()
for _ in range(4000):
    r = date.fromordinal(random.randint(1, mx))
    assert to_iso_week(r.year, r.month, r.day) == exp_to(r.year, r.month, r.day), r
for _ in range(300):
    y = random.choice([random.randint(1, 9999), random.randint(1890, 2210), 1, 9999])
    for m, d in [(12, k) for k in range(24, 32)] + [(1, k) for k in range(1, 8)]:
        assert call(to_iso_week, y, m, d) == exp_to(y, m, d), (y, m, d)
    for w in (1, 52, 53):
        for wd in range(1, 8):
            assert call(from_iso_week, y, w, wd) == exp_from(y, w, wd), (y, w, wd)
for _ in range(4000):
    a = (random.choice([random.randint(1, 9999), random.randint(-2, 3), random.randint(9997, 10001)]),
         random.randint(-1, 54), random.randint(-1, 8))
    assert call(from_iso_week, *a) == exp_from(*a), a
    b = (random.randint(-1, 10001), random.randint(-1, 13), random.randint(-1, 32))
    assert call(to_iso_week, *b) == exp_to(*b), b
''', r'''
_CUM = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]

def _leap(y):
    return y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)

def _dim(y, m):
    return [31, 29 if _leap(y) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1]

def _ord(y, m, d):
    yy = y - 1
    return yy * 365 + yy // 4 - yy // 100 + yy // 400 + _CUM[m - 1] + (m > 2 and _leap(y)) + d

def _week1(y):
    o = _ord(y, 1, 4)
    return o - (o - 1) % 7

def _from_ord(o):
    y = max(1, (o - 1) // 366)
    while _ord(y + 1, 1, 1) <= o:
        y += 1
    m = 1
    while m < 12 and _ord(y, m + 1, 1) <= o:
        m += 1
    return (y, m, o - _ord(y, m, 1) + 1)

_MAXORD = _ord(9999, 12, 31)

def to_iso_week(year, month, day):
    if not (1 <= year <= 9999 and 1 <= month <= 12 and 1 <= day <= _dim(year, month)):
        raise ValueError("invalid date")
    o = _ord(year, month, day)
    iy = year
    if o >= _week1(year + 1):
        iy = year + 1
    elif o < _week1(year):
        iy = year - 1
    return (iy, (o - _week1(iy)) // 7 + 1, (o - 1) % 7 + 1)

def from_iso_week(iso_year, week, weekday):
    if not 1 <= iso_year <= 9999:
        raise ValueError("year out of range")
    if not 1 <= weekday <= 7:
        raise ValueError("bad weekday")
    weeks = (_week1(iso_year + 1) - _week1(iso_year)) // 7
    if not 1 <= week <= weeks:
        raise ValueError("bad week")
    o = _week1(iso_year) + (week - 1) * 7 + weekday - 1
    if not 1 <= o <= _MAXORD:
        raise ValueError("date out of range")
    return _from_ord(o)
''')


task("v2_27_business_days", r'''
Write `add_business_days(start: str, n: int, holidays: list[str]) -> str`. Dates are
strings "YYYY-MM-DD" (exactly 4-digit year, 2-digit month, 2-digit day, ASCII digits,
dashes, nothing else) in the proleptic Gregorian calendar (leap years: divisible by 4, except
centuries not divisible by 400). A business day is a Monday-Friday that is neither a holiday
nor an observed holiday. Observed rule: a holiday falling on a Saturday is also observed on
the preceding Friday; a holiday falling on a Sunday is also observed on the following Monday
(this can cross a month or year boundary). An observed day is never shifted further, even if
it is itself a holiday. The holiday list may be unsorted and contain duplicates.
Result: for n > 0, the n-th business day strictly after start; for n < 0, the abs(n)-th
business day strictly before start; for n == 0, start itself if it is a business day, else
the first business day after it. start itself does not need to be a business day.
Raise ValueError if start or any holiday is not a valid date in the exact format above
(e.g. "2024-2-03", "2023-02-29", "2024-13-01", "2024/01/01"). Return the result in the same
format. Do not use the datetime, calendar or time modules. abs(n) can be up to 5000.
''', r'''
import random
_banned(mods=("datetime", "_datetime", "_pydatetime", "calendar", "time", "_strptime", "zoneinfo", "email"))
from datetime import date, timedelta
abd = add_business_days
assert abd("2024-01-05", 1, []) == "2024-01-08"
assert abd("2024-01-06", 0, []) == "2024-01-08"
assert abd("2024-01-08", 0, []) == "2024-01-08"
assert abd("2024-01-08", -1, []) == "2024-01-05"
assert abd("2024-01-06", -1, []) == "2024-01-05"
assert abd("2024-01-06", 1, []) == "2024-01-08"
assert abd("2021-12-30", 1, ["2022-01-01"]) == "2022-01-03"
assert abd("2022-12-30", 1, ["2023-01-01"]) == "2023-01-03"
assert abd("2023-01-03", -1, ["2023-01-01"]) == "2022-12-30"
assert abd("2024-02-28", 1, []) == "2024-02-29"
assert abd("2023-02-28", 1, []) == "2023-03-01"
assert abd("2024-07-03", 1, ["2024-07-04", "2024-07-04"]) == "2024-07-05"
assert abd("2020-07-02", 1, ["2020-07-04"]) == "2020-07-06"
assert abd("2020-07-03", 0, ["2020-07-04"]) == "2020-07-06"
assert abd("2024-12-31", 0, ["2024-12-31"]) == "2025-01-01"
for bad in ["2024-2-03", "2023-02-29", "2024-13-01", "2024-00-10", "2024-01-32", "24-01-01", "2024-01-01x",
            "2024/01/01", " 2024-01-01", "1900-02-29", "2024-04-31", "20240101", ""]:
    for args in [(bad, 1, []), ("2024-01-02", 1, ["2024-01-05", bad])]:
        try:
            abd(*args)
            assert False, ("expected ValueError", args)
        except ValueError:
            pass
assert abd("2000-02-28", 1, []) == "2000-02-29"
def oracle(start, n, hols):
    hs = set()
    for h in hols:
        d = date.fromisoformat(h)
        hs.add(d)
        if d.weekday() == 5:
            hs.add(d - timedelta(1))
        elif d.weekday() == 6:
            hs.add(d + timedelta(1))
    biz = lambda d: d.weekday() < 5 and d not in hs
    d = date.fromisoformat(start)
    if n == 0:
        while not biz(d):
            d += timedelta(1)
        return d.isoformat()
    step, k = timedelta(1 if n > 0 else -1), abs(n)
    while k:
        d += step
        if biz(d):
            k -= 1
    return d.isoformat()
random.seed(2707)
for _ in range(500):
    o = random.randint(date(1890, 1, 1).toordinal(), date(2210, 12, 31).toordinal())
    start = date.fromordinal(o).isoformat()
    n = random.choice([0, random.randint(-10, 10), random.randint(-400, 400), random.randint(-5000, 5000)])
    hols = [date.fromordinal(o + random.randint(-800, 800)).isoformat() for _ in range(random.randint(0, 25))]
    hols += [date.fromordinal(o + random.randint(-3, 3)).isoformat() for _ in range(random.randint(0, 3))]
    if hols and random.random() < 0.3:
        hols.append(random.choice(hols))
    random.shuffle(hols)
    exp = oracle(start, n, hols)
    assert abd(start, n, list(hols)) == exp, (start, n, hols, exp)
''', r'''
_CUM = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]

def _leap(y):
    return y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)

def _ord(y, m, d):
    yy = y - 1
    return yy * 365 + yy // 4 - yy // 100 + yy // 400 + _CUM[m - 1] + (m > 2 and _leap(y)) + d

def _parse(s):
    if not isinstance(s, str) or len(s) != 10 or s[4] != "-" or s[7] != "-":
        raise ValueError("bad date " + repr(s))
    digits = s[:4] + s[5:7] + s[8:]
    if any(c not in "0123456789" for c in digits):
        raise ValueError("bad date " + repr(s))
    y, m, d = int(s[:4]), int(s[5:7]), int(s[8:])
    if not 1 <= m <= 12 or y < 1:
        raise ValueError("bad date " + repr(s))
    dim = [31, 29 if _leap(y) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1]
    if not 1 <= d <= dim:
        raise ValueError("bad date " + repr(s))
    return _ord(y, m, d)

def _fmt(o):
    y = max(1, (o - 1) // 366)
    while _ord(y + 1, 1, 1) <= o:
        y += 1
    m = 1
    while m < 12 and _ord(y, m + 1, 1) <= o:
        m += 1
    return "%04d-%02d-%02d" % (y, m, o - _ord(y, m, 1) + 1)

def add_business_days(start, n, holidays):
    o = _parse(start)
    off = set()
    for h in holidays:
        x = _parse(h)
        off.add(x)
        wd = (x - 1) % 7   # 0 = Monday
        if wd == 5:
            off.add(x - 1)
        elif wd == 6:
            off.add(x + 1)
    biz = lambda x: (x - 1) % 7 < 5 and x not in off
    if n == 0:
        while not biz(o):
            o += 1
        return _fmt(o)
    step, k = (1 if n > 0 else -1), abs(n)
    while k:
        o += step
        if biz(o):
            k -= 1
    return _fmt(o)
''')


task("v2_28_bank_queue", r'''
Write `serve(k: int, customers: list[tuple]) -> list[tuple]` simulating a bank with k
tellers numbered 0..k-1. Each customer is (cid, arrival, duration, vip, patience): cid is a
unique int, arrival an int >= 0, duration an int >= 1, vip a bool, patience None (waits
forever) or an int >= 0. Time is integer. At each time t the following happens in order:
1. every service ending at t finishes and its teller becomes free;
2. every customer arriving at t joins the waiting line;
3. every waiting customer with arrival + patience < t leaves for good (abandoned); so a
   customer can still be served at time arrival + patience exactly;
4. while a teller is free and someone is waiting: the next customer is chosen by VIP first,
   then earliest arrival, then smallest cid; they go to the free teller with the LOWEST
   number and are served from t to t + duration.
Return one tuple per customer, sorted by cid: (cid, teller, start, end) for served
customers, (cid, -1, None, None) for abandoned ones. Raise ValueError if k < 1, a cid is
duplicated, or any arrival < 0, duration < 1 or patience < 0. Times can be as large as
10**9 and there can be 100000 customers; it must finish in a couple of seconds, so do not
step through time one unit at a time.
''', r'''
import random
import time
assert serve(1, []) == []
assert serve(1, [(1, 0, 5, False, None), (2, 1, 2, False, None)]) == [(1, 0, 0, 5), (2, 0, 5, 7)]
assert serve(1, [(1, 0, 5, False, None), (2, 1, 2, False, 4)]) == [(1, 0, 0, 5), (2, 0, 5, 7)]
assert serve(1, [(1, 0, 5, False, None), (2, 1, 2, False, 3)]) == [(1, 0, 0, 5), (2, -1, None, None)]
assert serve(1, [(1, 0, 3, False, None), (2, 1, 1, False, None), (3, 2, 1, True, None)]) == [(1, 0, 0, 3), (2, 0, 4, 5), (3, 0, 3, 4)]
assert serve(2, [(5, 0, 4, False, None), (3, 0, 4, False, None), (9, 0, 1, False, None)]) == [(3, 0, 0, 4), (5, 1, 0, 4), (9, 0, 4, 5)]
assert serve(2, [(1, 0, 2, False, None), (2, 0, 9, False, None), (3, 2, 1, False, None)]) == [(1, 0, 0, 2), (2, 1, 0, 9), (3, 0, 2, 3)]
assert serve(3, [(1, 0, 1, False, None), (2, 0, 1, False, None), (3, 1, 1, False, 0)]) == [(1, 0, 0, 1), (2, 1, 0, 1), (3, 0, 1, 2)]
assert serve(1, [(1, 0, 2, False, None), (2, 0, 1, False, 1), (3, 1, 1, True, 0)]) == [(1, 0, 0, 2), (2, -1, None, None), (3, -1, None, None)]
assert serve(1, [(7, 10**9, 10**9, True, 0)]) == [(7, 0, 10**9, 2 * 10**9)]
for bad in [(0, []), (1, [(1, 0, 1, False, None), (1, 2, 1, False, None)]), (1, [(1, 0, 0, False, None)]),
            (2, [(1, -1, 1, False, None)]), (1, [(1, 0, 1, False, -1)])]:
    try:
        serve(*bad)
        assert False, ("expected ValueError", bad)
    except ValueError:
        pass
def oracle(k, cs):
    free_at, waiting, res = [0] * k, [], {}
    by_t = {}
    for c in cs:
        by_t.setdefault(c[1], []).append(c)
    t = 0
    while len(res) < len(cs):
        waiting += by_t.get(t, [])
        keep = []
        for c in waiting:
            if c[4] is not None and c[1] + c[4] < t:
                res[c[0]] = (c[0], -1, None, None)
            else:
                keep.append(c)
        waiting = keep
        while waiting:
            free = [i for i in range(k) if free_at[i] <= t]
            if not free:
                break
            c = min(waiting, key=lambda c: (not c[3], c[1], c[0]))
            waiting.remove(c)
            res[c[0]] = (c[0], free[0], t, t + c[2])
            free_at[free[0]] = t + c[2]
        t += 1
    return [res[i] for i in sorted(res)]
def gen(n, T, D, P, vipp):
    ids = random.sample(range(1, 10 * n + 10), n)
    return [(i, random.randint(0, T), random.randint(1, D), random.random() < vipp,
             None if random.random() < 0.4 else random.randint(0, P)) for i in ids]
random.seed(2808)
for _ in range(1200):
    k = random.randint(1, 3)
    cs = gen(random.randint(1, 15), random.randint(0, 30), random.randint(1, 8), 10, random.choice([0, 0.2, 0.5]))
    exp = oracle(k, cs)
    assert serve(k, list(cs)) == exp, (k, cs, exp)
cs = gen(800, 2000, 9, 30, 0.2)
assert serve(3, cs) == oracle(3, cs)
cs = gen(100000, 10**9, 10**6, 10**6, 0.1)
t0 = time.perf_counter()
out = serve(7, cs)
assert time.perf_counter() - t0 < 4.0
assert [r[0] for r in out] == sorted(c[0] for c in cs)
''', r'''
import heapq

def serve(k, customers):
    if k < 1:
        raise ValueError("k must be >= 1")
    seen = set()
    for cid, a, dur, vip, pat in customers:
        if cid in seen or a < 0 or dur < 1 or (pat is not None and pat < 0):
            raise ValueError("bad customer")
        seen.add(cid)
    arr = sorted(customers, key=lambda c: (c[1], c[0]))
    free = list(range(k))
    busy, queue, res = [], [], {}
    i, n = 0, len(arr)
    inf = float("inf")
    while i < n or busy:
        t = min(arr[i][1] if i < n else inf, busy[0][0] if busy else inf)
        while busy and busy[0][0] == t:
            heapq.heappush(free, heapq.heappop(busy)[1])
        while i < n and arr[i][1] == t:
            c = arr[i]
            heapq.heappush(queue, (0 if c[3] else 1, c[1], c[0], c))
            i += 1
        while free and queue:
            _, a, cid, c = heapq.heappop(queue)
            if c[4] is not None and a + c[4] < t:
                res[cid] = (cid, -1, None, None)
                continue
            tel = heapq.heappop(free)
            res[cid] = (cid, tel, t, t + c[2])
            heapq.heappush(busy, (t + c[2], tel))
    for _, a, cid, c in queue:
        res[cid] = (cid, -1, None, None)
    return [res[c] for c in sorted(res)]
''')


task("v2_29_gf_solve", r'''
Write `gf_solve(A: list[list[int]], b: list[int], p: int)` that solves the linear system
A x = b over the integers modulo a prime p (GF(p)). A is an m x n matrix (m >= 1 rows,
n >= 1 columns) of arbitrary ints (reduce them mod p, negatives included), b has m entries.
Raise ValueError if A is empty, a row is empty, rows have different lengths, len(b) != m,
or p < 2 (you may assume p is prime otherwise).
If the system has no solution return None. Otherwise return (x, d): d = n - rank(A) is the
dimension of the solution space, and x is a list of n ints in 0..p-1 chosen as follows.
Call column j a pivot column if it is NOT a linear combination of columns 0..j-1 (these are
exactly the pivot columns of the reduced row echelon form); every other column is free.
x is the unique solution in which every free variable is 0.
p can be as large as 10**9 + 7; a 100 x 100 system must take at most a couple of seconds.
''', r'''
import random
import time
from itertools import product
assert gf_solve([[1, 1], [1, 1]], [1, 0], 2) is None
assert gf_solve([[2, 4], [1, 2]], [2, 1], 5) == ([1, 0], 1)
assert gf_solve([[0, 3]], [6], 3) == ([0, 0], 2)
assert gf_solve([[0, 1]], [5], 7) == ([0, 5], 1)
assert gf_solve([[1, 2], [3, 4]], [5, 6], 7) == ([3, 1], 0)
assert gf_solve([[-1]], [1], 13) == ([12], 0)
assert gf_solve([[0, 0, 1], [0, 0, 2]], [1, 2], 5) == ([0, 0, 1], 2)
assert gf_solve([[1, 1, 0], [0, 0, 1], [1, 1, 1]], [1, 2, 0], 3) == ([1, 0, 2], 1)
for bad in [([], [], 5), ([[]], [1], 5), ([[1, 2], [3]], [1, 2], 5), ([[1, 2]], [1, 2], 5), ([[1]], [1], 1)]:
    try:
        gf_solve(*bad)
        assert False, ("expected ValueError", bad)
    except ValueError:
        pass
def span_size(cols, p, m):
    return len({tuple(sum(c[i] * y for c, y in zip(cols, ys)) % p for i in range(m))
                for ys in product(range(p), repeat=len(cols))})
def oracle(A, b, p):
    m, n = len(A), len(A[0])
    cols = [[A[i][j] for i in range(m)] for j in range(n)]
    piv = [j for j in range(n) if span_size(cols[:j + 1], p, m) > span_size(cols[:j], p, m)]
    sols = [x for x in product(range(p), repeat=n)
            if all((sum(A[i][j] * x[j] for j in range(n)) - b[i]) % p == 0 for i in range(m))]
    if not sols:
        return None
    d = n - len(piv)
    assert len(sols) == p ** d
    x0 = [x for x in sols if all(x[j] == 0 for j in range(n) if j not in piv)]
    assert len(x0) == 1
    return (list(x0[0]), d)
random.seed(2909)
for _ in range(400):
    p = random.choice([2, 3, 5])
    m, n = random.randint(1, 4), random.randint(1, 4)
    A = [[random.randint(-7, 7) for _ in range(n)] for _ in range(m)]
    if random.random() < 0.3:
        A = [[x * random.randint(0, 1) for x in row] for row in A]
    if random.random() < 0.6:
        x = [random.randint(0, p - 1) for _ in range(n)]
        b = [sum(a * y for a, y in zip(row, x)) + p * random.randint(-3, 3) for row in A]
    else:
        b = [random.randint(-9, 9) for _ in range(m)]
    exp = oracle(A, b, p)
    got = gf_solve([r[:] for r in A], b[:], p)
    assert got == exp, (A, b, p, exp, got)
P = 10**9 + 7
t0 = time.perf_counter()
A = [[random.randint(-P, 2 * P) for _ in range(100)] for _ in range(100)]
x0 = [random.randint(0, P - 1) for _ in range(100)]
b = [sum(a * y for a, y in zip(row, x0)) for row in A]
assert gf_solve(A, b, P) == (x0, 0)
B = [row[:80] + row[:20] for row in A]
xb = [random.randint(0, P - 1) for _ in range(80)] + [0] * 20
bb = [sum(a * y for a, y in zip(row, xb)) for row in B]
assert gf_solve(B + [B[3][:]], bb + [bb[3]], P) == (xb, 20)
assert gf_solve(B + [B[3][:]], bb + [bb[3] + 1], P) is None
assert time.perf_counter() - t0 < 6.0
''', r'''
def gf_solve(A, b, p):
    if p < 2 or not A or not A[0] or len(b) != len(A) or any(len(r) != len(A[0]) for r in A):
        raise ValueError("bad input")
    m, n = len(A), len(A[0])
    M = [[x % p for x in row] + [bi % p] for row, bi in zip(A, b)]
    piv, r = [], 0
    for c in range(n):
        i = next((i for i in range(r, m) if M[i][c]), None)
        if i is None:
            continue
        M[r], M[i] = M[i], M[r]
        inv = pow(M[r][c], p - 2, p)
        M[r] = [v * inv % p for v in M[r]]
        pr = M[r]
        for i in range(m):
            if i != r and M[i][c]:
                f = M[i][c]
                M[i] = [(v - f * w) % p for v, w in zip(M[i], pr)]
        piv.append(c)
        r += 1
        if r == m:
            break
    if any(M[i][n] for i in range(r, m)):
        return None
    x = [0] * n
    for i, c in enumerate(piv):
        x[c] = M[i][n]
    return (x, n - r)
''')


task("v2_30_best_rational", r'''
Write `best_rational(num: int, den: int, max_den: int) -> tuple[int, int]` returning the
fraction p/q closest to x = num/den among all fractions with 1 <= q <= max_den. Return
(p, q) in lowest terms with q >= 1 (the sign goes on p; 0 is (0, 1)). num and den are ints
of any sign and size; den == 0 or max_den < 1 raises ValueError. Ties in distance: prefer
the smaller q; if still tied, the smaller value p/q. If x itself has a reduced denominator
<= max_den, return x reduced. Examples: best_rational(314159, 100000, 100) == (311, 99);
best_rational(1, 2, 1) == (0, 1); best_rational(5, 4, 2) == (1, 1).
Do not use the fractions or decimal modules, and no floats (inputs reach 10**40 with
max_den up to 10**30). 2000 calls must finish in well under a second, so a search over
denominators is far too slow.
''', r'''
import random
_banned(mods=("fractions", "decimal", "_pydecimal", "_decimal"))
import time
from fractions import Fraction as F
from math import floor
br = best_rational
assert br(3, 1, 5) == (3, 1)
assert br(1, 3, 10) == (1, 3)
assert br(2, 4, 10) == (1, 2)
assert br(-1, -3, 10) == (1, 3)
assert br(1, -3, 10) == (-1, 3)
assert br(314159, 100000, 7) == (22, 7)
assert br(314159, 100000, 100) == (311, 99)
assert br(1, 2, 1) == (0, 1)
assert br(-1, 2, 1) == (-1, 1)
assert br(3, 2, 1) == (1, 1)
assert br(5, 4, 2) == (1, 1)
assert br(-5, 4, 2) == (-1, 1)
assert br(0, 5, 3) == (0, 1)
assert br(0, -5, 1) == (0, 1)
assert br(7, 12, 4) == (1, 2)
assert br(10**40 + 1, 10**40, 10**30) == (1, 1)
for bad in [(1, 0, 5), (1, 2, 0), (1, 2, -3)]:
    try:
        br(*bad)
        assert False, ("expected ValueError", bad)
    except ValueError:
        pass
def brute(num, den, N):
    x = F(num, den)
    best = None
    for q in range(1, N + 1):
        f0 = floor(x * q)
        for p in (f0, f0 + 1):
            f = F(p, q)
            key = (abs(f - x), f.denominator, f)
            if best is None or key < best:
                best = key
    return (best[2].numerator, best[2].denominator)
random.seed(3010)
for _ in range(3000):
    num, den, N = random.randint(-200, 200), random.choice([-1, 1]) * random.randint(1, 60), random.randint(1, 40)
    exp = brute(num, den, N)
    assert br(num, den, N) == exp, (num, den, N, exp)
for _ in range(300):
    q = random.randint(1, 30)
    num, den = 2 * random.randint(-100, 100) + 1, 2 * q
    N = random.randint(1, 40)
    assert br(num, den, N) == brute(num, den, N), (num, den, N)
cases = [(random.randint(-10**40, 10**40), random.choice([-1, 1]) * random.randint(1, 10**40), random.randint(1, 10**30))
         for _ in range(2000)]
t0 = time.perf_counter()
outs = [br(*c) for c in cases]
assert time.perf_counter() - t0 < 2.0
for (num, den, N), (p, q) in zip(cases, outs):
    x = F(num, den)
    L = x.limit_denominator(N)
    assert 1 <= q <= N and F(p, q).numerator == p and F(p, q).denominator == q
    assert abs(F(p, q) - x) == abs(L - x), (num, den, N)
    if (p, q) != (L.numerator, L.denominator):
        assert q < L.denominator or (q == L.denominator and F(p, q) < L)
''', r'''
from math import gcd

def best_rational(num, den, max_den):
    if den == 0 or max_den < 1:
        raise ValueError("bad input")
    if den < 0:
        num, den = -num, -den
    g = gcd(num, den)
    n, d = num // g, den // g
    if d <= max_den:
        return (n, d)
    p0, q0, p1, q1 = 0, 1, 1, 0
    nn, dd = n, d
    while True:
        a = nn // dd
        q2 = q0 + a * q1
        if q2 > max_den:
            break
        p0, q0, p1, q1 = p1, q1, p0 + a * p1, q2
        nn, dd = dd, nn - a * dd
    k = (max_den - q0) // q1
    c1, c2 = (p0 + k * p1, q0 + k * q1), (p1, q1)
    e1 = abs(c1[0] * d - n * c1[1]) * c2[1]
    e2 = abs(c2[0] * d - n * c2[1]) * c1[1]
    if e1 != e2:
        return c1 if e1 < e2 else c2
    if c1[1] != c2[1]:
        return c1 if c1[1] < c2[1] else c2
    return c1 if c1[0] < c2[0] else c2
''')

TASKS = T
